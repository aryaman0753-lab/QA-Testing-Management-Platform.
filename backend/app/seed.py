"""Development seed data.

Run with:  python -m app.seed

Creates one user per role plus a sample project, all idempotent (safe to
re-run). Never run this against a production database - it uses a
publicly-documented development password.
"""
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.database.database import SessionLocal
from app.database.models.project import Project
from app.database.models.project_member import ProjectMember, ProjectRole
from app.database.models.user import User, UserRole
from app.database.models.bug import Bug, BugPriority, BugSeverity, BugStatus

configure_logging()
logger = get_logger(__name__)

DEV_PASSWORD = "Password123!"

SEED_USERS = [
    ("Alice Admin", "admin@example.com", UserRole.ADMIN),
    ("Quinn QA", "qa@example.com", UserRole.QA_ENGINEER),
    ("Dev Developer", "developer@example.com", UserRole.DEVELOPER),
    ("Pat Manager", "pm@example.com", UserRole.PROJECT_MANAGER),
]


def seed() -> None:
    db = SessionLocal()
    try:
        users_by_email: dict[str, User] = {}
        for full_name, email, role in SEED_USERS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(
                    full_name=full_name,
                    email=email,
                    password_hash=hash_password(DEV_PASSWORD),
                    role=role,
                )
                db.add(user)
                db.flush()
                logger.info("Seeded user %s (%s)", email, role.value)
            users_by_email[email] = user

        admin = users_by_email["admin@example.com"]
        project = db.query(Project).filter(Project.key == "DEMO").first()
        if project is None:
            project = Project(
                name="Demo Project",
                key="DEMO",
                description="Sample project created by the seed script.",
                created_by=admin.id,
            )
            db.add(project)
            db.flush()
            db.add(ProjectMember(project_id=project.id, user_id=admin.id, project_role=ProjectRole.OWNER))
            for email, role in [("qa@example.com", ProjectRole.MEMBER), ("developer@example.com", ProjectRole.MEMBER)]:
                db.add(
                    ProjectMember(
                        project_id=project.id, user_id=users_by_email[email].id, project_role=role
                    )
                )
            logger.info("Seeded demo project DEMO")

        ecom = db.query(Project).filter(Project.key == "ECOM").first()
        if ecom is None:
            ecom = Project(
                name="E-Commerce Application",
                key="ECOM",
                description="Sample storefront used to demonstrate the Phase 2 bug workflow.",
                created_by=admin.id,
            )
            db.add(ecom)
            db.flush()
            for email, role in [
                ("admin@example.com", ProjectRole.OWNER),
                ("qa@example.com", ProjectRole.MEMBER),
                ("developer@example.com", ProjectRole.MEMBER),
                ("pm@example.com", ProjectRole.VIEWER),
            ]:
                db.add(ProjectMember(project_id=ecom.id, user_id=users_by_email[email].id, project_role=role))
            db.flush()

        if db.query(Bug).filter(Bug.project_id == ecom.id).count() == 0:
            samples = [
                ("Checkout button is unresponsive", BugStatus.NEW, BugSeverity.CRITICAL, BugPriority.URGENT, None),
                ("Cart total does not refresh", BugStatus.IN_PROGRESS, BugSeverity.HIGH, BugPriority.HIGH, users_by_email["developer@example.com"].id),
                ("Product thumbnail is misaligned", BugStatus.QA_VERIFICATION, BugSeverity.LOW, BugPriority.LOW, users_by_email["developer@example.com"].id),
                ("Coupon error message is unclear", BugStatus.CLOSED, BugSeverity.MEDIUM, BugPriority.MEDIUM, users_by_email["developer@example.com"].id),
                ("Saved address disappears after refresh", BugStatus.REOPENED, BugSeverity.HIGH, BugPriority.HIGH, users_by_email["developer@example.com"].id),
            ]
            for number, (title, status, severity, priority, assignee) in enumerate(samples, 1):
                db.add(Bug(
                    project_id=ecom.id,
                    bug_number=number,
                    title=title,
                    description=f"Development sample: {title}.",
                    steps_to_reproduce=["Sign in to the storefront", "Perform the affected action", "Observe the result"],
                    expected_result="The storefront should complete the action successfully.",
                    actual_result=title,
                    severity=severity,
                    priority=priority,
                    status=status,
                    environment="QA",
                    browser="Chrome",
                    operating_system="Windows 11",
                    device="Desktop",
                    reported_by=users_by_email["qa@example.com"].id,
                    assigned_to=assignee,
                ))
            ecom.next_bug_number = len(samples)
            logger.info("Seeded ECOM project with %s sample bugs", len(samples))

        db.commit()
        print("Seed complete. Development accounts (password for all: 'Password123!'):")
        for _, email, role in SEED_USERS:
            print(f"  {email:<25} role={role.value}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
