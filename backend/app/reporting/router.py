import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.reporting import service

router = APIRouter(prefix="/projects/{project_id}", tags=["Reporting"])


@router.get("/reports/qa")
def qa_report(project_id: uuid.UUID, environment_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.build_report(db, project_id, user, environment_id, date_from, date_to)


@router.get("/reports/export")
def export_report(project_id: uuid.UUID, format: str = Query("json", pattern="^(json|csv|pdf)$"), environment_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report = service.build_report(db, project_id, user, environment_id, date_from, date_to)
    body, media_type, extension = service.export_report(report, format)
    return Response(content=body, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="qahub-{report["project"]["key"]}-report.{extension}"', "X-Content-Type-Options": "nosniff"})


@router.get("/automation/compare")
def compare_automation(project_id: uuid.UUID, run_a: uuid.UUID, run_b: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.compare_automation_runs(db, project_id, run_a, run_b, user)


@router.get("/automation/flaky-tests")
def flaky_tests(project_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.flaky_tests(db, project_id, user, limit)


@router.get("/qa-dashboard")
def dashboard(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.project_dashboard(db, project_id, user)
