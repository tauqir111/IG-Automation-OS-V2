"""Crash / restart recovery for the publisher queue (Phase 2 §13).

Rules:
    * Any Job left in RUNNING at startup is uncertain — mark it
      ACTION_REQUIRED with a note. Never auto-requeue, because Instagram
      might have accepted the previous attempt and requeuing would produce
      a duplicate post.
    * Any Account left with session_status = 'busy' is released back to a
      neutral state so it can be re-verified.
"""
from datetime import datetime, timezone

from ..database import SessionLocal
from ..models import Account, Job
from ..services.logger import log


def recover_on_startup() -> dict:
    db = SessionLocal()
    try:
        stale_jobs = db.query(Job).filter(Job.status == "running").all()
        for j in stale_jobs:
            j.status = "action_required"
            j.completed_at = datetime.now(timezone.utc)
            j.error_message = (
                "Backend restarted while this job was RUNNING. "
                "Manually verify on Instagram before retrying to avoid a duplicate post."
            )
            log(db, "WARNING",
                f"Job #{j.id} was RUNNING at restart → ACTION_REQUIRED (manual review)",
                campaign_id=j.campaign_id, account_id=j.account_id)

        stale_accounts = (
            db.query(Account).filter(Account.session_status == "busy").all()
        )
        for a in stale_accounts:
            # Reset to 'unknown' so the next Verify picks up real state.
            a.session_status = "unknown"
            log(db, "INFO",
                f"Account '{a.account_name}' released after backend restart",
                account_id=a.id)

        db.commit()
        return {"jobs_marked_action_required": len(stale_jobs),
                "accounts_released": len(stale_accounts)}
    finally:
        db.close()
