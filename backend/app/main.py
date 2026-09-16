from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.api_testing.router import api_router as api_testing_router, project_router as project_api_router
from app.load_testing.router import load_router, project_router as project_load_router
from app.bugs.router import attachment_router, bug_router, project_router as project_bugs_router
from app.common.exceptions import AppError
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.projects.router import members_router as project_members_router
from app.projects.router import router as projects_router
from app.system.router import router as system_router
from app.users.router import router as users_router

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
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


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
