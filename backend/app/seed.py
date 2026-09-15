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

        db.commit()
        print("Seed complete. Development accounts (password for all: 'Password123!'):")
        for _, email, role in SEED_USERS:
            print(f"  {email:<25} role={role.value}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
