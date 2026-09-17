import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.automation import service
from app.automation.schemas import CaseCreate, CaseOut, CaseUpdate, Page, ReorderInput, RunDetail, RunOut, ScheduleCreate, ScheduleOut, ScheduleUpdate, StartRunInput, StepCreate, StepOut, StepResultOut, StepUpdate, SuiteCreate, SuiteOut, SuiteUpdate
from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User

project_router = APIRouter(prefix="/projects/{project_id}/automation", tags=["Automation"])
router = APIRouter(prefix="/automation", tags=["Automation"])


@project_router.get("/suites", response_model=Page)
def suites(project_id: uuid.UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: Literal["DRAFT", "ACTIVE", "DISABLED", "ARCHIVED"] | None = None, search: str | None = Query(None, max_length=255), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_suites(db, project_id, user, page, page_size, status, search)


@project_router.post("/suites", response_model=SuiteOut, status_code=201)
def create_suite(project_id: uuid.UUID, payload: SuiteCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_suite(db, project_id, payload, user)


@router.get("/suites/{suite_id}", response_model=SuiteOut)
def suite(suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.suite_out(service.get_suite(db, suite_id, user))


@router.patch("/suites/{suite_id}", response_model=SuiteOut)
def update_suite(suite_id: uuid.UUID, payload: SuiteUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_suite(db, suite_id, payload, user)


@router.delete("/suites/{suite_id}", status_code=204)
def delete_suite(suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.delete_suite(db, suite_id, user)
    return Response(status_code=204)


@router.post("/suites/{suite_id}/cases", response_model=CaseOut, status_code=201)
def create_case(suite_id: uuid.UUID, payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_case(db, suite_id, payload, user)


@router.patch("/cases/{case_id}", response_model=CaseOut)
def update_case(case_id: uuid.UUID, payload: CaseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_case(db, case_id, payload, user)


@router.delete("/cases/{case_id}", status_code=204)
def delete_case(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.delete_case(db, case_id, user)
    return Response(status_code=204)


@router.put("/suites/{suite_id}/cases/reorder", response_model=SuiteOut)
def reorder_cases(suite_id: uuid.UUID, payload: ReorderInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.reorder(db, suite_id, payload.ids, user)


@router.post("/cases/{case_id}/steps", response_model=StepOut, status_code=201)
def create_step(case_id: uuid.UUID, payload: StepCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_step(db, case_id, payload, user)


@router.patch("/steps/{step_id}", response_model=StepOut)
def update_step(step_id: uuid.UUID, payload: StepUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_step(db, step_id, payload, user)


@router.delete("/steps/{step_id}", status_code=204)
def delete_step(step_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.delete_step(db, step_id, user)
    return Response(status_code=204)


@router.put("/cases/{case_id}/steps/reorder", response_model=SuiteOut)
def reorder_steps(case_id: uuid.UUID, payload: ReorderInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.reorder(db, case_id, payload.ids, user, steps=True)


@router.post("/suites/{suite_id}/run", response_model=RunOut, status_code=202)
def start_run(suite_id: uuid.UUID, payload: StartRunInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.run_out(db, service.create_run(db, suite_id, payload, user))


@router.get("/runs/{run_id}", response_model=RunDetail)
def run(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.run_out(db, service.get_run(db, run_id, user), detail=True)


@router.get("/runs/{run_id}/results", response_model=list[StepResultOut])
def results(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_run(db, run_id, user).results


@router.post("/runs/{run_id}/stop", response_model=RunOut)
def stop(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.stop_run(db, run_id, user)


def run_filters(suite_id: uuid.UUID | None = None, environment_id: uuid.UUID | None = None, status: Literal["QUEUED", "RUNNING", "PASSED", "FAILED", "CANCELLED"] | None = None, created_from: date | None = None, created_to: date | None = None):
    return {"suite_id": suite_id, "environment_id": environment_id, "status": status, "created_from": created_from, "created_to": created_to}


@project_router.get("/runs", response_model=Page)
def history(project_id: uuid.UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), filters: dict = Depends(run_filters), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_runs(db, project_id, user, page, page_size, **filters)


@project_router.get("/schedules", response_model=Page)
def schedules(project_id: uuid.UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_schedules(db, project_id, user, page, page_size)


@project_router.post("/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(project_id: uuid.UUID, payload: ScheduleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_schedule(db, project_id, payload, user)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: uuid.UUID, payload: ScheduleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.update_schedule(db, schedule_id, payload, user)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.delete_schedule(db, schedule_id, user)
    return Response(status_code=204)


@project_router.get("/statistics")
def statistics(project_id: uuid.UUID, filters: dict = Depends(run_filters), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.statistics(db, project_id, user, **filters)


@project_router.get("/audit", response_model=Page)
def audit(project_id: uuid.UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_audit(db, project_id, user, page, page_size)
