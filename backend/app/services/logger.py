"""Central log writer — stores structured logs in SQLite."""
from typing import Optional
from sqlalchemy.orm import Session

from ..models import LogEntry


def log(
    db: Session,
    level: str,
    message: str,
    campaign_id: Optional[int] = None,
    account_id: Optional[int] = None,
) -> LogEntry:
    """Persist a log entry. Never log secrets, cookies or passwords."""
    entry = LogEntry(
        level=level.upper(),
        message=message,
        campaign_id=campaign_id,
        account_id=account_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
