import uuid

from fastapi import APIRouter, Depends, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.bugs.schemas import BugCreate, BugDetail
from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.load_testing import service
from app.load_testing.schemas import (
    AllowlistSettings, BugFromLoadRunCreate, ComparisonOut, EndpointMetricOut,
    ErrorMetricOut, LoadRunDetail, LoadRunOut, LoadTestCreate, LoadTestOut,
    MetricOut, PaginatedLoadRuns, StartRunInput,
)

project_router = APIRouter(prefix="/projects/{project_id}/load-tests", tags=["Load Tests"])
load_router = APIRouter(prefix="/load-tests", tags=["Load Tests"])


@project_router.post("", response_model=LoadTestOut, status_code=201)
def create(project_id: uuid.UUID, payload: LoadTestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_test(db, project_id, payload, user)


@project_router.get("", response_model=list[LoadTestOut])
def list_definitions(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_tests(db, project_id, user)


@project_router.get("/settings", response_model=AllowlistSettings, tags=["Load Test Security"])
def settings(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_settings_for_project(db, project_id, user)


@project_router.put("/settings", response_model=AllowlistSettings, tags=["Load Test Security"])
def update_settings(project_id: uuid.UUID, payload: AllowlistSettings, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_settings(db, project_id, payload, user)


@project_router.get("/runs", response_model=PaginatedLoadRuns, tags=["Load Test Runs"])
def list_runs(project_id: uuid.UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_runs(db, project_id, user, page, page_size)


@project_router.get("/runs/compare", response_model=ComparisonOut, tags=["Load Test Runs"])
def compare(project_id: uuid.UUID, run_a: uuid.UUID, run_b: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.compare_runs(db, project_id, run_a, run_b, user)


@load_router.get("/runs/{run_id}", response_model=LoadRunDetail, tags=["Load Test Runs"])
def run_detail(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.run_detail(service.get_run(db, run_id, user))


@load_router.get("/runs/{run_id}/metrics", response_model=list[MetricOut], tags=["Load Test Metrics"])
def metrics(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_run(db, run_id, user).metrics


@load_router.get("/runs/{run_id}/endpoints", response_model=list[EndpointMetricOut], tags=["Load Test Metrics"])
def endpoints(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_run(db, run_id, user).endpoints


@load_router.get("/runs/{run_id}/errors", response_model=list[ErrorMetricOut], tags=["Load Test Metrics"])
def errors(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_run(db, run_id, user).errors


@load_router.post("/runs/{run_id}/stop", response_model=LoadRunOut, tags=["Load Test Execution"])
def stop(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.stop_run(db, run_id, user)


@load_router.post("/runs/{run_id}/baseline", response_model=LoadRunOut, tags=["Load Test Runs"])
def baseline(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.mark_baseline(db, run_id, user)


@load_router.get("/runs/{run_id}/report.json", tags=["Load Test Reports"])
def json_report(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = service.get_run(db, run_id, user)
    return JSONResponse(content=jsonable_encoder(service.report_data(run)), headers={"Content-Disposition": f'attachment; filename="{run.run_key}.json"'})


@load_router.get("/runs/{run_id}/report.csv", tags=["Load Test Reports"])
def csv_report(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = service.get_run(db, run_id, user)
    return Response(service.report_csv(run), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{run.run_key}.csv"'})


@load_router.get("/runs/{run_id}/bug-suggestion", response_model=BugCreate, tags=["Load Test Runs"])
def bug_suggestion(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.bug_suggestion(db, run_id, user)


@load_router.post("/runs/{run_id}/bugs", response_model=BugDetail, status_code=201, tags=["Load Test Runs"])
def create_bug(run_id: uuid.UUID, payload: BugFromLoadRunCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_bug_from_run(db, run_id, payload, user)


@load_router.post("/{test_id}/run", response_model=LoadRunOut, status_code=202, tags=["Load Test Execution"])
async def run(test_id: uuid.UUID, payload: StartRunInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return await service.start_run(db, test_id, user, payload.confirm_production)


@load_router.get("/{test_id}", response_model=LoadTestOut)
def get_definition(test_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.load_test_out(service.get_test(db, test_id, user))


@load_router.patch("/{test_id}", response_model=LoadTestOut)
def update_definition(test_id: uuid.UUID, payload: LoadTestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_test(db, test_id, payload, user)


@load_router.delete("/{test_id}", status_code=204)
def archive_definition(test_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.archive_test(db, test_id, user); return Response(status_code=204)
