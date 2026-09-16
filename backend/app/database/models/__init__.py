"""Import every model here so Alembic's autogenerate and Base.metadata.create_all
(used only by tests) can discover them from a single import.
"""
from app.database.models.base import Base  # noqa: F401
from app.database.models.user import User, UserRole  # noqa: F401
from app.database.models.project import Project, ProjectStatus  # noqa: F401
from app.database.models.project_member import ProjectMember, ProjectRole  # noqa: F401
from app.database.models.bug import (  # noqa: F401
    Bug, BugAttachment, BugComment, BugHistory, BugPriority, BugSeverity, BugStatus,
)
from app.database.models.api_testing import (  # noqa: F401
    ApiAssertion, ApiAuditLog, ApiCollection, ApiEnvironment, ApiExtractor,
    ApiRequest, ApiTestResult, ApiTestRun, AssertionOperator, AssertionType,
    AuthenticationType, BodyType, ExecutionStatus, ExtractorSource, HttpMethod,
)
from app.database.models.load_testing import (  # noqa: F401
    EnvironmentClassification, LoadTest, LoadTestAuditLog, LoadTestEndpointMetric,
    LoadTestError, LoadTestMetric, LoadTestProfile, LoadTestResultStatus,
    LoadTargetType, LoadTestRun, LoadTestStatus,
)

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Project",
    "ProjectStatus",
    "ProjectMember",
    "ProjectRole",
    "Bug", "BugAttachment", "BugComment", "BugHistory", "BugPriority", "BugSeverity", "BugStatus",
    "ApiAssertion", "ApiAuditLog", "ApiCollection", "ApiEnvironment", "ApiExtractor",
    "ApiRequest", "ApiTestResult", "ApiTestRun", "AssertionOperator", "AssertionType",
    "AuthenticationType", "BodyType", "ExecutionStatus", "ExtractorSource", "HttpMethod",
    "EnvironmentClassification", "LoadTest", "LoadTestAuditLog", "LoadTestEndpointMetric",
    "LoadTestError", "LoadTestMetric", "LoadTestProfile", "LoadTestResultStatus",
    "LoadTargetType", "LoadTestRun", "LoadTestStatus",
]
