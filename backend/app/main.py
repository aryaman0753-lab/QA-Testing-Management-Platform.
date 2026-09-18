from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.router import router as auth_router
from app.automation.router import router as automation_router, project_router as project_automation_router
from app.api_testing.router import api_router as api_testing_router, project_router as project_api_router
from app.load_testing.router import load_router, project_router as project_load_router
from app.bugs.router import attachment_router, bug_router, project_router as project_bugs_router
from app.common.exceptions import AppError
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.projects.router import members_router as project_members_router
from app.projects.router import router as projects_router
from app.operations.router import ci_router, notification_router, project_router as project_operations_router
from app.reporting.router import router as reporting_router
from app.system.router import admin_router as admin_system_router, router as system_router
from app.users.router import router as users_router
from app.core.observability import allow_request, limit_for_path, new_request_id, record_request, request_id_context
from app.core.security import InvalidTokenError, decode_access_token

settings = get_settings()

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s starting up in '%s' environment.", settings.APP_NAME, settings.ENVIRONMENT)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="QAHub API - projects, bugs, functional API testing, and isolated performance testing.",
    version="0.6.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def operational_middleware(request: Request, call_next):
    request_id = new_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    token = request_id_context.set(request_id)
    started = perf_counter()
    settings = get_settings()
    user_id = None
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer ") and not authorization.lower().startswith("bearer qh_"):
        try: user_id = str(decode_access_token(authorization[7:]))
        except InvalidTokenError: pass
    def finish(response):
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.ENVIRONMENT.lower() in {"production", "prod"}:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        duration = perf_counter() - started
        record_request(request.method, request.url.path, response.status_code, duration)
        extra = {"method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": round(duration * 1000, 2)}
        if user_id: extra["user_id"] = user_id
        logger.info("http_request", extra=extra)
        return response
    try:
        content_length = request.headers.get("content-length")
        if content_length:
            try: too_large = int(content_length) > settings.MAX_REQUEST_SIZE_MB * 1024 * 1024
            except ValueError: too_large = True
            if too_large:
                return finish(JSONResponse(status_code=413, content={"error": {"code": "request_too_large", "message": "Request body exceeds the configured limit.", "request_id": request_id}}))
        rate = limit_for_path(request.url.path)
        if rate and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            allowed, remaining = allow_request(request, *rate)
            if not allowed:
                response = JSONResponse(status_code=429, content={"error": {"code": "rate_limit_exceeded", "message": "Too many requests. Try again later.", "request_id": request_id}}, headers={"Retry-After": "60", "X-RateLimit-Remaining": str(remaining)})
                return finish(response)
        response = await call_next(request)
        return finish(response)
    finally:
        request_id_context.reset(token)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.detail, "request_id": getattr(request.state, "request_id", "-")}})


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic's `input` and `ctx` may contain submitted passwords or tokens.
    errors = [{key: value for key, value in error.items() if key in {"type", "loc", "msg"}} for error in exc.errors()]
    message = "; ".join(error.get("msg", "Invalid input") for error in errors)
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": message, "request_id": getattr(request.state, "request_id", "-"), "details": jsonable_encoder(errors)}})


@app.exception_handler(StarletteHTTPException)
def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed."
    code = "not_found" if exc.status_code == 404 else "http_error"
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", "-")}})


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "Internal server error.", "request_id": getattr(request.state, "request_id", "-")}})


app.include_router(system_router)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(projects_router, prefix=settings.API_V1_PREFIX)
app.include_router(project_members_router, prefix=settings.API_V1_PREFIX)
app.include_router(project_bugs_router, prefix=settings.API_V1_PREFIX)
app.include_router(bug_router, prefix=settings.API_V1_PREFIX)
app.include_router(attachment_router, prefix=settings.API_V1_PREFIX)
app.include_router(project_api_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_testing_router, prefix=settings.API_V1_PREFIX)
app.include_router(project_load_router, prefix=settings.API_V1_PREFIX)
app.include_router(load_router, prefix=settings.API_V1_PREFIX)
app.include_router(project_automation_router, prefix=settings.API_V1_PREFIX)
app.include_router(automation_router, prefix=settings.API_V1_PREFIX)
app.include_router(project_operations_router, prefix=settings.API_V1_PREFIX)
app.include_router(notification_router, prefix=settings.API_V1_PREFIX)
app.include_router(ci_router, prefix=settings.API_V1_PREFIX)
app.include_router(reporting_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_system_router, prefix=settings.API_V1_PREFIX)
