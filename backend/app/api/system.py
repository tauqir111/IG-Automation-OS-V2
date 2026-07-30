"""Settings + Logs endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Setting, LogEntry
from ..schemas import SettingsUpdate, LogOut
from ..services.logger import log as write_log

router = APIRouter(tags=["system"])


@router.get("/v1/settings")
async def get_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    return {r.key: r.value for r in rows}


@router.put("/v1/settings")
async def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    changed = []
    for key, value in payload.model_dump(exclude_none=True).items():
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Setting(key=key, value=value))
        changed.append(key)
    if changed:
        write_log(db, "INFO", f"Settings updated: {', '.join(changed)}")
    db.commit()
    return {"updated": changed}


@router.get("/v1/logs", response_model=List[LogOut])
async def list_logs(
    db: Session = Depends(get_db),
    level: Optional[str] = Query(default=None),
    campaign_id: Optional[int] = Query(default=None),
    limit: int = Query(default=200, le=1000),
):
    q = db.query(LogEntry)
    if level:
        q = q.filter(LogEntry.level == level.upper())
    if campaign_id is not None:
        q = q.filter(LogEntry.campaign_id == campaign_id)
    return q.order_by(LogEntry.created_at.desc()).limit(limit).all()
