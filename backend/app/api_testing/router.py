import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api_testing import service
from app.api_testing.rate_limit import execution_rate_limiter
from app.api_testing.schemas import (
    ApiAnalytics, BugFromResultCreate, CollectionCreate, CollectionDetail,
    CollectionOut, EnvironmentCreate, EnvironmentOut, ExecuteInput,
    HealthCheckInput, HealthCheckResult, PaginatedRuns, RequestCreate,
    RequestOut, ResultOut, RunDetail,
)
from app.bugs.schemas import BugCreate, BugDetail
from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User

project_router = APIRouter(prefix="/projects/{project_id}/api", tags=["API Collections"])
api_router = APIRouter(prefix="/api", tags=["API Requests"])


@project_router.post("/collections", response_model=CollectionOut, status_code=201)
def create_collection(project_id: uuid.UUID, payload: CollectionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_collection(db, project_id, payload, user)


@project_router.get("/collections", response_model=list[CollectionOut])
def list_collections(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_collections(db, project_id, user)


@project_router.post("/environments", response_model=EnvironmentOut, status_code=201, tags=["API Environments"])
def create_environment(project_id: uuid.UUID, payload: EnvironmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_environment(db, project_id, payload, user)


@project_router.get("/environments", response_model=list[EnvironmentOut], tags=["API Environments"])
def list_environments(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_environments(db, project_id, user)


@project_router.post("/health-check", response_model=HealthCheckResult, tags=["API Execution"])
async def health_check(project_id: uuid.UUID, payload: HealthCheckInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    execution_rate_limiter.check(user.id)
    return await service.health_check(db, project_id, payload, user)


@project_router.get("/analytics", response_model=ApiAnalytics, tags=["API Test Runs"])
def analytics(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.analytics(db, project_id, user)


@api_router.get("/collections/{collection_id}", response_model=CollectionDetail, tags=["API Collections"])
def get_collection(collection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.collection_out(service.get_collection(db, collection_id, user), detail=True)


@api_router.put("/collections/{collection_id}", response_model=CollectionOut, tags=["API Collections"])
def update_collection(collection_id: uuid.UUID, payload: CollectionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_collection(db, collection_id, payload, user)


@api_router.delete("/collections/{collection_id}", status_code=204, tags=["API Collections"])
def delete_collection(collection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.archive_collection(db, collection_id, user); return Response(status_code=204)


@api_router.post("/collections/{collection_id}/requests", response_model=RequestOut, status_code=201)
def create_request(collection_id: uuid.UUID, payload: RequestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_request(db, collection_id, payload, user)


@api_router.get("/collections/{collection_id}/requests", response_model=list[RequestOut])
def list_requests(collection_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_requests(db, collection_id, user)


@api_router.post("/collections/{collection_id}/execute", response_model=RunDetail, tags=["API Execution"])
async def execute_collection(collection_id: uuid.UUID, payload: ExecuteInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    execution_rate_limiter.check(user.id)
    return await service.execute_collection(db, collection_id, payload, user)


@api_router.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.request_out(service.get_request(db, request_id, user))


@api_router.put("/requests/{request_id}", response_model=RequestOut)
def update_request(request_id: uuid.UUID, payload: RequestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_request(db, request_id, payload, user)


@api_router.delete("/requests/{request_id}", status_code=204)
def delete_request(request_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.archive_request(db, request_id, user); return Response(status_code=204)


@api_router.post("/requests/{request_id}/execute", response_model=RunDetail, tags=["API Execution"])
async def execute_request(request_id: uuid.UUID, payload: ExecuteInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    execution_rate_limiter.check(user.id)
    return await service.execute_request(db, request_id, payload, user)


@api_router.get("/environments/{environment_id}", response_model=EnvironmentOut, tags=["API Environments"])
def get_environment(environment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.environment_out(service.get_environment(db, environment_id, user))


@api_router.put("/environments/{environment_id}", response_model=EnvironmentOut, tags=["API Environments"])
def update_environment(environment_id: uuid.UUID, payload: EnvironmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_environment(db, environment_id, payload, user)


@api_router.delete("/environments/{environment_id}", status_code=204, tags=["API Environments"])
def delete_environment(environment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.delete_environment(db, environment_id, user); return Response(status_code=204)


@api_router.get("/runs", response_model=PaginatedRuns, tags=["API Test Runs"])
def list_runs(project_id: uuid.UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_runs(db, user, project_id, page, page_size)


@api_router.get("/runs/{run_id}", response_model=RunDetail, tags=["API Test Runs"])
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_run_detail(db, run_id, user)


@api_router.get("/results/{result_id}", response_model=ResultOut, tags=["API Test Runs"])
def get_result(result_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.result_out(service.get_result(db, result_id, user))


@api_router.get("/results/{result_id}/bug-suggestion", response_model=BugCreate, tags=["API Test Runs"])
def get_bug_suggestion(result_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.bug_suggestion(db, result_id, user)


@api_router.post("/results/{result_id}/bugs", response_model=BugDetail, status_code=201, tags=["API Test Runs"])
def create_bug_from_result(result_id: uuid.UUID, payload: BugFromResultCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_bug_from_result(db, result_id, payload, user)
