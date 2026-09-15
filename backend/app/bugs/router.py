import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.bugs import service
from app.bugs.schemas import (
    AssigneeUpdate,
    BugAnalytics,
    BugAttachmentOut,
    BugCommentOut,
    BugCreate,
    BugDetail,
    BugHistoryOut,
    BugListItem,
    BugUpdate,
    CommentCreate,
    CommentUpdate,
    PaginatedBugs,
    StatusUpdate,
)
from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.bug import BugPriority, BugSeverity, BugStatus
from app.database.models.user import User

project_router = APIRouter(prefix="/projects/{project_id}/bugs", tags=["Bugs"])
bug_router = APIRouter(prefix="/bugs", tags=["Bugs"])
attachment_router = APIRouter(prefix="/bug-attachments", tags=["Bug Attachments"])


@project_router.post("", response_model=BugDetail, status_code=201)
def create_bug_endpoint(
    project_id: uuid.UUID,
    payload: BugCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugDetail:
    return BugDetail.model_validate(service.create_bug(db, project_id, payload, current_user))


@project_router.get("", response_model=PaginatedBugs)
def list_bugs_endpoint(
    project_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: list[BugStatus] | None = Query(None),
    severity: list[BugSeverity] | None = Query(None),
    priority: list[BugPriority] | None = Query(None),
    assigned_to: uuid.UUID | None = None,
    reported_by: uuid.UUID | None = None,
    environment: str | None = Query(None, max_length=100),
    search: str | None = Query(None, max_length=500),
    created_from: date | None = None,
    created_to: date | None = None,
    updated_from: date | None = None,
    updated_to: date | None = None,
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|priority|severity|status|bug_number)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedBugs:
    items, total = service.list_bugs(
        db, project_id, current_user, page, page_size, status, severity, priority,
        assigned_to, reported_by, environment, search, created_from, created_to,
        updated_from, updated_to, sort_by, sort_order,
    )
    return PaginatedBugs(
        items=[BugListItem.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size),
    )


@project_router.get("/analytics", response_model=BugAnalytics, tags=["Bug Analytics"])
def project_analytics_endpoint(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugAnalytics:
    return BugAnalytics.model_validate(service.analytics(db, current_user, project_id))


@project_router.get("/report.csv", tags=["Bug Analytics"])
def bug_report_endpoint(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    content = service.export_csv(db, project_id, current_user)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bug-report.csv"'},
    )


@bug_router.get("/dashboard", response_model=BugAnalytics, tags=["Bug Analytics"])
def dashboard_analytics_endpoint(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> BugAnalytics:
    return BugAnalytics.model_validate(service.analytics(db, current_user))


@bug_router.get("/{bug_id}", response_model=BugDetail)
def get_bug_endpoint(
    bug_id: uuid.UUID,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugDetail:
    return BugDetail.model_validate(service.get_bug(db, bug_id, current_user, include_archived))


@bug_router.patch("/{bug_id}", response_model=BugDetail)
def update_bug_endpoint(
    bug_id: uuid.UUID,
    payload: BugUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugDetail:
    return BugDetail.model_validate(service.update_bug(db, bug_id, payload, current_user))


@bug_router.patch("/{bug_id}/assignee", response_model=BugDetail)
def assign_bug_endpoint(
    bug_id: uuid.UUID,
    payload: AssigneeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugDetail:
    return BugDetail.model_validate(service.assign_bug(db, bug_id, payload.assigned_to, current_user))


@bug_router.patch("/{bug_id}/status", response_model=BugDetail)
def change_status_endpoint(
    bug_id: uuid.UUID,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugDetail:
    return BugDetail.model_validate(service.change_status(db, bug_id, payload.status, current_user))


@bug_router.delete("/{bug_id}", status_code=204)
def archive_bug_endpoint(
    bug_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    service.archive_bug(db, bug_id, current_user)
    return Response(status_code=204)


@bug_router.post("/{bug_id}/comments", response_model=BugCommentOut, status_code=201, tags=["Bug Comments"])
def add_comment_endpoint(
    bug_id: uuid.UUID,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugCommentOut:
    return BugCommentOut.model_validate(service.add_comment(db, bug_id, payload.comment, current_user))


@bug_router.get("/{bug_id}/comments", response_model=list[BugCommentOut], tags=["Bug Comments"])
def list_comments_endpoint(
    bug_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BugCommentOut]:
    return [BugCommentOut.model_validate(item) for item in service.list_comments(db, bug_id, current_user)]


@bug_router.put("/{bug_id}/comments/{comment_id}", response_model=BugCommentOut, tags=["Bug Comments"])
def update_comment_endpoint(
    bug_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugCommentOut:
    return BugCommentOut.model_validate(service.update_comment(db, bug_id, comment_id, payload.comment, current_user))


@bug_router.delete("/{bug_id}/comments/{comment_id}", status_code=204, tags=["Bug Comments"])
def delete_comment_endpoint(
    bug_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    service.delete_comment(db, bug_id, comment_id, current_user)
    return Response(status_code=204)


@bug_router.get("/{bug_id}/history", response_model=list[BugHistoryOut], tags=["Bug History"])
def bug_history_endpoint(
    bug_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BugHistoryOut]:
    return [BugHistoryOut.model_validate(row) for row in service.get_bug(db, bug_id, current_user).history]


@bug_router.post("/{bug_id}/attachments", response_model=BugAttachmentOut, status_code=201, tags=["Bug Attachments"])
async def upload_attachment_endpoint(
    bug_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BugAttachmentOut:
    limit = get_settings().MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    content = await file.read(limit + 1)
    return BugAttachmentOut.model_validate(service.add_attachment(db, bug_id, file.filename or "", content, current_user))


@attachment_router.get("/{attachment_id}/download")
def download_attachment_endpoint(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    attachment, path = service.get_attachment(db, attachment_id, current_user)
    return FileResponse(path, media_type=attachment.mime_type, filename=attachment.file_name)


@attachment_router.delete("/{attachment_id}", status_code=204)
def delete_attachment_endpoint(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    service.delete_attachment(db, attachment_id, current_user)
    return Response(status_code=204)
