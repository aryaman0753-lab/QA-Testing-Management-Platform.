"""Re-exported for callers that conceptually want "auth" dependencies.

The real implementation lives in app.core.dependencies so both the auth
module and every other module share one source of truth for "who is the
current user".
"""
from app.core.dependencies import get_current_user, require_admin, require_roles  # noqa: F401
