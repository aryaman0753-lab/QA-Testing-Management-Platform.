"""Domain exceptions.

Services raise these instead of HTTPException so business logic stays
framework-agnostic (useful later for workers/CLI tools that reuse services
without going through FastAPI). Routers/handlers translate them to HTTP
responses in one place - see app.main.register_exception_handlers.
"""


class AppError(Exception):
    """Base class for all domain errors."""

    status_code = 400
    detail = "An error occurred."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    detail = "Resource already exists."


class UnauthorizedError(AppError):
    status_code = 401
    detail = "Not authenticated."


class ForbiddenError(AppError):
    status_code = 403
    detail = "You do not have permission to perform this action."


class ValidationAppError(AppError):
    status_code = 422
    detail = "Invalid input."
