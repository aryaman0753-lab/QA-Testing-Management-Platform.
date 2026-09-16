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
from app.database.models.api_testing import (
    ApiAssertion, ApiCollection, ApiEnvironment, ApiRequest, AssertionOperator,
    AssertionType, AuthenticationType, BodyType, HttpMethod,
)
from app.api_testing.secrets import encrypt
from app.database.models.load_testing import LoadTargetType, LoadTest, LoadTestProfile

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

        api_collection = db.query(ApiCollection).filter(ApiCollection.project_id == ecom.id, ApiCollection.name == "ECOM API").first()
        if api_collection is None:
            environment = ApiEnvironment(
                project_id=ecom.id, name="QA", classification="QA", created_by=admin.id,
                variables={
                    "base_url": {"value": "https://api.example.test", "is_secret": False},
                    "user_id": {"value": "1", "is_secret": False},
                    "access_token": {"value": encrypt("replace-me"), "is_secret": True},
                },
            )
            api_collection = ApiCollection(project_id=ecom.id, name="ECOM API", description="Editable examples; configure a permitted public test host before execution.", created_by=admin.id)
            db.add_all([environment, api_collection]); db.flush()
            examples = [
                ("Get Users", HttpMethod.GET, "{{base_url}}/users", BodyType.NONE, None),
                ("Get User", HttpMethod.GET, "{{base_url}}/users/{{user_id}}", BodyType.NONE, None),
                ("Create User", HttpMethod.POST, "{{base_url}}/users", BodyType.JSON, '{"name":"QA Test User"}'),
                ("Update User", HttpMethod.PUT, "{{base_url}}/users/{{user_id}}", BodyType.JSON, '{"name":"Updated QA User"}'),
                ("Delete User", HttpMethod.DELETE, "{{base_url}}/users/{{user_id}}", BodyType.NONE, None),
            ]
            for position, (name, method, url, body_type, body) in enumerate(examples):
                api_request = ApiRequest(
                    project_id=ecom.id, collection_id=api_collection.id, name=name, method=method,
                    url=url, headers=[{"key": "Accept", "value": "application/json", "enabled": True}],
                    query_parameters=[], body=body, body_type=body_type,
                    authentication_type=AuthenticationType.NONE, authentication_config={},
                    position=position, created_by=admin.id,
                )
                db.add(api_request); db.flush()
                db.add(ApiAssertion(request_id=api_request.id, assertion_type=AssertionType.STATUS_CODE, operator=AssertionOperator.LESS_THAN, expected_value="400", position=0))
            logger.info("Seeded ECOM API collection and QA environment")

        environment = db.query(ApiEnvironment).filter(ApiEnvironment.project_id == ecom.id, ApiEnvironment.name == "QA").first()
        source_request = db.query(ApiRequest).filter(ApiRequest.project_id == ecom.id, ApiRequest.name == "Get Users").first()
        ecom.load_allowlist_enabled = True
        ecom.load_allowed_hosts = ["api.example.test"]
        if environment and source_request and db.query(LoadTest).filter(LoadTest.project_id == ecom.id, LoadTest.name == "ECOM API Baseline").first() is None:
            db.add(LoadTest(
                project_id=ecom.id, name="ECOM API Baseline",
                description="Safe starter definition. Replace the example host with an authorized QA target before running.",
                target_type=LoadTargetType.API_REQUEST,
                api_request_id=source_request.id, environment_id=environment.id,
                target_url=source_request.url, request_method=source_request.method,
                headers=[], query_parameters=[], body=None, body_type=BodyType.NONE,
                authentication_type=AuthenticationType.NONE, authentication_config={},
                profile=LoadTestProfile.BASELINE, virtual_users=5, spawn_rate=1,
                duration_seconds=60, timeout_seconds=10, target_rps=5,
                thresholds={"max_p95_ms": 750, "max_p99_ms": 1500, "max_failure_rate": 1, "max_error_count": 0},
                created_by=admin.id,
            ))
            logger.info("Seeded ECOM API baseline load test")

        db.commit()
        print("Seed complete. Development accounts (password for all: 'Password123!'):")
        for _, email, role in SEED_USERS:
            print(f"  {email:<25} role={role.value}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
