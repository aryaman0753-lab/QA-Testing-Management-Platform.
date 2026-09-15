import csv
import io
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.bugs.schemas import BugCreate, BugUpdate
from app.bugs.storage import LocalStorage, detect_mime, safe_filename
from app.common.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.core.config import get_settings
from app.database.models.bug import (
    Bug,
    BugAttachment,
    BugComment,
    BugHistory,
    BugPriority,
    BugSeverity,
    BugStatus,
)
from app.database.models.project import Project
from app.database.models.project_member import ProjectMember
from app.database.models.user import User, UserRole
from app.projects.service import get_membership, get_project_for_read

settings = get_settings()

OPEN_STATUSES = {
    BugStatus.NEW,
    BugStatus.ASSIGNED,
    BugStatus.IN_PROGRESS,
    BugStatus.FIXED,
    BugStatus.QA_VERIFICATION,
    BugStatus.REOPENED,
}

STATUS_TRANSITIONS: dict[BugStatus, set[BugStatus]] = {
    BugStatus.NEW: {BugStatus.ASSIGNED, BugStatus.DUPLICATE, BugStatus.WONT_FIX},
    BugStatus.ASSIGNED: {BugStatus.IN_PROGRESS, BugStatus.DUPLICATE, BugStatus.WONT_FIX},
    BugStatus.IN_PROGRESS: {BugStatus.FIXED, BugStatus.DUPLICATE, BugStatus.WONT_FIX},
    BugStatus.FIXED: {BugStatus.QA_VERIFICATION, BugStatus.REOPENED},
    BugStatus.QA_VERIFICATION: {BugStatus.VERIFIED, BugStatus.REOPENED},
    BugStatus.VERIFIED: {BugStatus.CLOSED, BugStatus.REOPENED},
    BugStatus.CLOSED: {BugStatus.REOPENED},
    BugStatus.REOPENED: {BugStatus.IN_PROGRESS, BugStatus.WONT_FIX},
    BugStatus.DUPLICATE: {BugStatus.REOPENED},
    BugStatus.WONT_FIX: {BugStatus.REOPENED},
}

DEVELOPER_TRANSITIONS = {
    (BugStatus.ASSIGNED, BugStatus.IN_PROGRESS),
    (BugStatus.REOPENED, BugStatus.IN_PROGRESS),
    (BugStatus.IN_PROGRESS, BugStatus.FIXED),
    (BugStatus.FIXED, BugStatus.QA_VERIFICATION),
}

DEVELOPER_EDIT_FIELDS = {
    "description", "steps_to_reproduce", "expected_result", "actual_result",
    "environment", "browser", "operating_system", "device",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _history(
    db: Session,
    bug: Bug,
    user: User,
    action: str,
    field_name: str | None = None,
    old_value: object | None = None,
    new_value: object | None = None,
) -> None:
    def display(value: object | None) -> str | None:
        if value is None:
            return None
        return str(getattr(value, "value", value))

    db.add(BugHistory(
        bug_id=bug.id,
        user_id=user.id,
        action=action,
        field_name=field_name,
        old_value=display(old_value),
        new_value=display(new_value),
        created_at=_now(),
    ))


def _base_detail_query():
    return select(Bug).options(
        joinedload(Bug.project),
        joinedload(Bug.reporter),
        joinedload(Bug.assignee),
        selectinload(Bug.comments).joinedload(BugComment.user),
        selectinload(Bug.attachments).joinedload(BugAttachment.uploader),
        selectinload(Bug.history).joinedload(BugHistory.user),
    )


def _can_read_bug(db: Session, bug: Bug, user: User) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if get_membership(db, bug.project_id, user.id) is None:
        return False
    if user.role == UserRole.DEVELOPER:
        return bug.assigned_to == user.id
    return True


def get_bug(db: Session, bug_id: uuid.UUID, current_user: User, include_archived: bool = False) -> Bug:
    bug = db.scalar(_base_detail_query().where(Bug.id == bug_id))
    if bug is None or (bug.is_archived and (not include_archived or current_user.role != UserRole.ADMIN)) or not _can_read_bug(db, bug, current_user):
        raise NotFoundError("Bug not found.")
    bug.comments.sort(key=lambda row: row.created_at)
    bug.attachments.sort(key=lambda row: row.created_at)
    bug.history.sort(key=lambda row: row.created_at, reverse=True)
    return bug


def _require_bug_creator(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = get_project_for_read(db, project_id, user)
    if user.role not in {UserRole.ADMIN, UserRole.QA_ENGINEER}:
        raise ForbiddenError("Only administrators and QA engineers can create bugs.")
    return project


def _validate_assignee(db: Session, project_id: uuid.UUID, user_id: uuid.UUID | None) -> User | None:
    if user_id is None:
        return None
    assignee = db.get(User, user_id)
    if assignee is None or not assignee.is_active or get_membership(db, project_id, user_id) is None:
        raise ValidationAppError("Assignee must be an active member of this project.")
    return assignee


def create_bug(db: Session, project_id: uuid.UUID, payload: BugCreate, current_user: User) -> Bug:
    _require_bug_creator(db, project_id, current_user)
    _validate_assignee(db, project_id, payload.assigned_to)

    # Lock the project counter so two simultaneous reports cannot receive the same key.
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise NotFoundError("Project not found.")
    project.next_bug_number += 1
    bug = Bug(
        project_id=project.id,
        bug_number=project.next_bug_number,
        reported_by=current_user.id,
        status=BugStatus.ASSIGNED if payload.assigned_to else BugStatus.NEW,
        **payload.model_dump(),
    )
    db.add(bug)
    db.flush()
    _history(db, bug, current_user, "CREATED")
    if payload.assigned_to:
        _history(db, bug, current_user, "ASSIGNEE_CHANGED", "assigned_to", None, payload.assigned_to)
    db.commit()
    return get_bug(db, bug.id, current_user)


def list_bugs(
    db: Session,
    project_id: uuid.UUID,
    current_user: User,
    page: int,
    page_size: int,
    statuses: list[BugStatus] | None = None,
    severities: list[BugSeverity] | None = None,
    priorities: list[BugPriority] | None = None,
    assigned_to: uuid.UUID | None = None,
    reported_by: uuid.UUID | None = None,
    environment: str | None = None,
    search: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    updated_from: date | None = None,
    updated_to: date | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Bug], int]:
    get_project_for_read(db, project_id, current_user)
    conditions = [Bug.project_id == project_id, Bug.is_archived.is_(False)]
    if current_user.role == UserRole.DEVELOPER:
        conditions.append(Bug.assigned_to == current_user.id)
    if statuses:
        conditions.append(Bug.status.in_(statuses))
    if severities:
        conditions.append(Bug.severity.in_(severities))
    if priorities:
        conditions.append(Bug.priority.in_(priorities))
    if assigned_to:
        conditions.append(Bug.assigned_to == assigned_to)
    if reported_by:
        conditions.append(Bug.reported_by == reported_by)
    if environment:
        conditions.append(func.lower(Bug.environment) == environment.strip().lower())
    if created_from:
        conditions.append(Bug.created_at >= datetime.combine(created_from, datetime.min.time(), tzinfo=timezone.utc))
    if created_to:
        conditions.append(Bug.created_at < datetime.combine(created_to, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1))
    if updated_from:
        conditions.append(Bug.updated_at >= datetime.combine(updated_from, datetime.min.time(), tzinfo=timezone.utc))
    if updated_to:
        conditions.append(Bug.updated_at < datetime.combine(updated_to, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1))
    if search and search.strip():
        term = search.strip()
        predicates = [Bug.title.ilike(f"%{term}%"), Bug.description.ilike(f"%{term}%")]
        project = db.get(Project, project_id)
        prefix = f"{project.key}-" if project else ""
        if term.upper().startswith(prefix):
            try:
                predicates.append(Bug.bug_number == int(term[len(prefix):]))
            except ValueError:
                pass
        conditions.append(or_(*predicates))

    priority_order = case({BugPriority.URGENT: 4, BugPriority.HIGH: 3, BugPriority.MEDIUM: 2, BugPriority.LOW: 1}, value=Bug.priority)
    severity_order = case({BugSeverity.CRITICAL: 5, BugSeverity.HIGH: 4, BugSeverity.MEDIUM: 3, BugSeverity.LOW: 2, BugSeverity.TRIVIAL: 1}, value=Bug.severity)
    sort_columns = {
        "created_at": Bug.created_at,
        "updated_at": Bug.updated_at,
        "bug_number": Bug.bug_number,
        "priority": priority_order,
        "severity": severity_order,
        "status": Bug.status,
    }
    sort_column = sort_columns.get(sort_by, Bug.created_at)
    ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    total = db.scalar(select(func.count(Bug.id)).where(*conditions)) or 0
    stmt = (
        select(Bug)
        .options(joinedload(Bug.project), joinedload(Bug.reporter), joinedload(Bug.assignee))
        .where(*conditions)
        .order_by(ordering, Bug.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt)), total


def update_bug(db: Session, bug_id: uuid.UUID, payload: BugUpdate, current_user: User) -> Bug:
    bug = get_bug(db, bug_id, current_user)
    fields = payload.model_fields_set
    if current_user.role == UserRole.DEVELOPER:
        if bug.assigned_to != current_user.id:
            raise ForbiddenError("Developers may only update bugs assigned to them.")
        disallowed = {
            field for field in fields - DEVELOPER_EDIT_FIELDS
            if getattr(bug, field) != getattr(payload, field)
        }
        if disallowed:
            raise ForbiddenError(f"Developers cannot update: {', '.join(sorted(disallowed))}.")
    elif current_user.role not in {UserRole.ADMIN, UserRole.QA_ENGINEER}:
        raise ForbiddenError("You do not have permission to edit bugs.")

    for field in fields:
        old = getattr(bug, field)
        new = getattr(payload, field)
        if old != new:
            setattr(bug, field, new)
            _history(db, bug, current_user, "FIELD_CHANGED", field, old, new)
    db.commit()
    return get_bug(db, bug.id, current_user)


def assign_bug(db: Session, bug_id: uuid.UUID, assignee_id: uuid.UUID | None, current_user: User) -> Bug:
    bug = get_bug(db, bug_id, current_user)
    if current_user.role not in {UserRole.ADMIN, UserRole.QA_ENGINEER}:
        raise ForbiddenError("Only administrators and QA engineers can assign bugs.")
    _validate_assignee(db, bug.project_id, assignee_id)
    old = bug.assigned_to
    if old != assignee_id:
        bug.assigned_to = assignee_id
        _history(db, bug, current_user, "ASSIGNEE_CHANGED", "assigned_to", old, assignee_id)
        if bug.status == BugStatus.NEW and assignee_id:
            bug.status = BugStatus.ASSIGNED
            _history(db, bug, current_user, "STATUS_CHANGED", "status", BugStatus.NEW, BugStatus.ASSIGNED)
        elif bug.status == BugStatus.ASSIGNED and assignee_id is None:
            bug.status = BugStatus.NEW
            _history(db, bug, current_user, "STATUS_CHANGED", "status", BugStatus.ASSIGNED, BugStatus.NEW)
    db.commit()
    return get_bug(db, bug.id, current_user)


def change_status(db: Session, bug_id: uuid.UUID, new_status: BugStatus, current_user: User) -> Bug:
    bug = get_bug(db, bug_id, current_user)
    old_status = bug.status
    if old_status == new_status:
        return bug
    if current_user.role == UserRole.ADMIN:
        pass
    elif current_user.role == UserRole.DEVELOPER:
        if bug.assigned_to != current_user.id or (old_status, new_status) not in DEVELOPER_TRANSITIONS:
            raise ForbiddenError("Developers may only advance the workflow for bugs assigned to them.")
    elif current_user.role == UserRole.QA_ENGINEER:
        if new_status not in STATUS_TRANSITIONS.get(old_status, set()):
            raise ValidationAppError(f"Invalid status transition: {old_status.value} -> {new_status.value}.")
    else:
        raise ForbiddenError("You do not have permission to change bug status.")

    if current_user.role != UserRole.ADMIN and new_status not in STATUS_TRANSITIONS.get(old_status, set()):
        raise ValidationAppError(f"Invalid status transition: {old_status.value} -> {new_status.value}.")
    if new_status == BugStatus.ASSIGNED and bug.assigned_to is None:
        raise ValidationAppError("Assign the bug to a project member before setting ASSIGNED.")
    bug.status = new_status
    if new_status == BugStatus.FIXED:
        bug.resolved_at = _now()
    elif new_status == BugStatus.REOPENED:
        bug.resolved_at = None
        bug.closed_at = None
    if new_status == BugStatus.CLOSED:
        bug.closed_at = _now()
    _history(db, bug, current_user, "STATUS_CHANGED", "status", old_status, new_status)
    db.commit()
    return get_bug(db, bug.id, current_user)


def archive_bug(db: Session, bug_id: uuid.UUID, current_user: User) -> None:
    bug = get_bug(db, bug_id, current_user)
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only administrators can archive bugs.")
    bug.is_archived = True
    bug.archived_at = _now()
    bug.archived_by = current_user.id
    _history(db, bug, current_user, "ARCHIVED")
    db.commit()


def add_comment(db: Session, bug_id: uuid.UUID, text: str, current_user: User) -> BugComment:
    bug = get_bug(db, bug_id, current_user)
    comment = BugComment(bug_id=bug.id, user_id=current_user.id, comment=text)
    db.add(comment)
    db.flush()
    _history(db, bug, current_user, "COMMENT_ADDED", "comment", None, comment.id)
    db.commit()
    return db.scalar(select(BugComment).options(joinedload(BugComment.user)).where(BugComment.id == comment.id))


def list_comments(db: Session, bug_id: uuid.UUID, current_user: User) -> list[BugComment]:
    bug = get_bug(db, bug_id, current_user)
    return list(db.scalars(select(BugComment).options(joinedload(BugComment.user)).where(BugComment.bug_id == bug.id).order_by(BugComment.created_at)))


def update_comment(db: Session, bug_id: uuid.UUID, comment_id: uuid.UUID, text: str, current_user: User) -> BugComment:
    bug = get_bug(db, bug_id, current_user)
    comment = db.scalar(select(BugComment).options(joinedload(BugComment.user)).where(BugComment.id == comment_id, BugComment.bug_id == bug.id))
    if comment is None:
        raise NotFoundError("Comment not found.")
    if comment.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You may only edit your own comments.")
    comment.comment = text
    _history(db, bug, current_user, "COMMENT_EDITED", "comment", None, comment.id)
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, bug_id: uuid.UUID, comment_id: uuid.UUID, current_user: User) -> None:
    bug = get_bug(db, bug_id, current_user)
    comment = db.scalar(select(BugComment).where(BugComment.id == comment_id, BugComment.bug_id == bug.id))
    if comment is None:
        raise NotFoundError("Comment not found.")
    if comment.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You may only delete your own comments.")
    _history(db, bug, current_user, "COMMENT_DELETED", "comment", comment.id, None)
    db.delete(comment)
    db.commit()


def add_attachment(db: Session, bug_id: uuid.UUID, filename: str, content: bytes, current_user: User) -> BugAttachment:
    bug = get_bug(db, bug_id, current_user)
    if current_user.role not in {UserRole.ADMIN, UserRole.QA_ENGINEER, UserRole.DEVELOPER}:
        raise ForbiddenError("You do not have permission to upload bug evidence.")
    if current_user.role == UserRole.DEVELOPER and bug.assigned_to != current_user.id:
        raise ForbiddenError("Developers may only attach evidence to assigned bugs.")
    max_size = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    if not content:
        raise ValidationAppError("Attachment cannot be empty.")
    if len(content) > max_size:
        raise ValidationAppError(f"Attachment exceeds the {settings.MAX_ATTACHMENT_SIZE_MB} MB limit.")
    clean_name = safe_filename(filename)
    mime = detect_mime(clean_name, content)
    storage = LocalStorage(settings.ATTACHMENT_STORAGE_DIR)
    relative_path = storage.save(bug.id, clean_name, content)
    attachment = BugAttachment(
        bug_id=bug.id, uploaded_by=current_user.id, file_name=clean_name,
        file_path=relative_path, file_size=len(content), mime_type=mime, created_at=_now(),
    )
    try:
        db.add(attachment)
        db.flush()
        _history(db, bug, current_user, "ATTACHMENT_ADDED", "attachment", None, clean_name)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(relative_path)
        raise
    return db.scalar(select(BugAttachment).options(joinedload(BugAttachment.uploader)).where(BugAttachment.id == attachment.id))


def get_attachment(db: Session, attachment_id: uuid.UUID, current_user: User) -> tuple[BugAttachment, object]:
    attachment = db.get(BugAttachment, attachment_id)
    if attachment is None:
        raise NotFoundError("Attachment not found.")
    get_bug(db, attachment.bug_id, current_user)
    return attachment, LocalStorage(settings.ATTACHMENT_STORAGE_DIR).resolve(attachment.file_path)


def delete_attachment(db: Session, attachment_id: uuid.UUID, current_user: User) -> None:
    attachment = db.get(BugAttachment, attachment_id)
    if attachment is None:
        raise NotFoundError("Attachment not found.")
    bug = get_bug(db, attachment.bug_id, current_user)
    if attachment.uploaded_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You may only delete your own attachments.")
    LocalStorage(settings.ATTACHMENT_STORAGE_DIR).delete(attachment.file_path)
    _history(db, bug, current_user, "ATTACHMENT_DELETED", "attachment", attachment.file_name, None)
    db.delete(attachment)
    db.commit()


def analytics(db: Session, current_user: User, project_id: uuid.UUID | None = None) -> dict:
    conditions = [Bug.is_archived.is_(False)]
    if project_id:
        get_project_for_read(db, project_id, current_user)
        conditions.append(Bug.project_id == project_id)
    elif current_user.role != UserRole.ADMIN:
        project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
        conditions.append(Bug.project_id.in_(project_ids))
    if current_user.role == UserRole.DEVELOPER:
        conditions.append(Bug.assigned_to == current_user.id)
    def grouped(column) -> Counter:
        return Counter({getattr(value, "value", value): count for value, count in db.execute(select(column, func.count(Bug.id)).where(*conditions).group_by(column))})

    total = db.scalar(select(func.count(Bug.id)).where(*conditions)) or 0
    status_counts = grouped(Bug.status)
    severity_counts = grouped(Bug.severity)
    priority_counts = grouped(Bug.priority)
    date_rows = db.execute(
        select(func.date(Bug.created_at), func.count(Bug.id))
        .where(*conditions)
        .group_by(func.date(Bug.created_at))
        .order_by(func.date(Bug.created_at))
    )
    return {
        "total": total,
        "open": sum(status_counts[s.value] for s in OPEN_STATUSES),
        "critical": severity_counts[BugSeverity.CRITICAL.value],
        "high_priority": priority_counts[BugPriority.HIGH.value],
        "by_status": {item.value: status_counts[item.value] for item in BugStatus},
        "by_severity": {item.value: severity_counts[item.value] for item in BugSeverity},
        "by_priority": {item.value: priority_counts[item.value] for item in BugPriority},
        "created_over_time": [{"date": day, "count": count} for day, count in date_rows],
    }


def export_csv(db: Session, project_id: uuid.UUID, current_user: User) -> str:
    bugs, _ = list_bugs(db, project_id, current_user, page=1, page_size=100000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Bug ID", "Title", "Status", "Severity", "Priority", "Assignee", "Reporter", "Created"])
    for bug in bugs:
        writer.writerow([
            bug.bug_key, bug.title, bug.status.value, bug.severity.value, bug.priority.value,
            bug.assignee.full_name if bug.assignee else "", bug.reporter.full_name, bug.created_at.isoformat(),
        ])
    return output.getvalue()
