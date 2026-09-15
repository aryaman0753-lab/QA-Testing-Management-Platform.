from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.database import get_db

router = APIRouter(tags=["System"])
logger = get_logger(__name__)


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:  # noqa: BLE001 - health check must never leak internals
        logger.exception("Health check database connectivity failed.")
        db_status = "unavailable"

    return {"status": "healthy", "database": db_status}
