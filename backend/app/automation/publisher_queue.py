"""Publishing queue — controlled concurrency + retry policy (Phase 2).

* One asyncio task per job.
* Global asyncio.Semaphore caps concurrent Chromium sessions.
* Per-account lock (from `browser_session._lock_for`) prevents the same
  persistent profile from being opened twice.
* Retry policy: MAX_ATTEMPTS = 2. ACTION_REQUIRED never retries.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from ..database import SessionLocal
from ..models import Account, Campaign, Job
from ..services.logger import log
from . import publisher

MAX_ATTEMPTS = 2  # per spec §9


class PublisherQueue:
    def __init__(self):
        self._sem: Optional[asyncio.Semaphore] = None
        self._max = 3
        self._tasks: dict[int, asyncio.Task] = {}

    def configure(self, max_concurrent: int):
        max_concurrent = max(1, int(max_concurrent))
        # If we're re-configuring on the fly, keep any existing sem in place
        # (Semaphore values can't be dynamically resized; workers already
        # holding permits will drain naturally.)
        if self._sem is None:
            self._sem = asyncio.Semaphore(max_concurrent)
        self._max = max_concurrent

    @property
    def max_concurrent(self) -> int:
        return self._max

    def enqueue(self, job_id: int) -> None:
        """Fire-and-forget. Returns immediately; the worker runs in background."""
        if self._sem is None:
            # Not configured yet — bootstrap with defaults so we never drop a job.
            self.configure(self._max)
        # Avoid double-enqueue for the same job id
        existing = self._tasks.get(job_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._run(job_id))
        self._tasks[job_id] = task

    async def _run(self, job_id: int) -> None:
        assert self._sem is not None
        async with self._sem:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                result = await publisher.publish_job(job_id)
                outcome = result.get("outcome")
                if outcome == "success":
                    _update_campaign_progress_for_job(job_id)
                    return
                if outcome == "action_required":
                    _update_campaign_progress_for_job(job_id)
                    return
                # transient_failure: retry if we have budget
                if attempt < MAX_ATTEMPTS:
                    _requeue_for_retry(job_id, attempt)
                    await asyncio.sleep(4)
                    continue
                # Out of retries — publisher already marked status='failed'
                _update_campaign_progress_for_job(job_id)
                return


# Module singleton
queue = PublisherQueue()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _requeue_for_retry(job_id: int, attempt: int) -> None:
    db = SessionLocal()
    try:
        j = db.query(Job).filter(Job.id == job_id).first()
        if not j:
            return
        j.status = "queued"
        j.error_message = (j.error_message or "") + f" | retrying (attempt {attempt} exhausted)"
        db.commit()
        log(db, "INFO", f"Job #{job_id} requeued for retry", campaign_id=j.campaign_id, account_id=j.account_id)
    finally:
        db.close()


def _update_campaign_progress_for_job(job_id: int) -> None:
    """Recompute the parent campaign's status from its jobs."""
    db = SessionLocal()
    try:
        j = db.query(Job).filter(Job.id == job_id).first()
        if not j:
            return
        campaign = db.query(Campaign).filter(Campaign.id == j.campaign_id).first()
        if not campaign:
            return

        jobs = db.query(Job).filter(Job.campaign_id == campaign.id).all()
        total = len(jobs)
        by_status = {"queued": 0, "running": 0, "success": 0, "failed": 0, "action_required": 0}
        for row in jobs:
            by_status[row.status] = by_status.get(row.status, 0) + 1

        terminal = by_status["success"] + by_status["failed"] + by_status["action_required"]
        new_status = campaign.status
        if terminal >= total and total > 0:
            if by_status["failed"] == total or (by_status["failed"] > 0 and by_status["success"] == 0):
                new_status = "failed"
            elif by_status["failed"] > 0 or by_status["action_required"] > 0:
                new_status = "partial"
            else:
                new_status = "completed"
            if campaign.completed_at is None:
                campaign.completed_at = datetime.now(timezone.utc)
        elif by_status["running"] > 0:
            new_status = "running"
        else:
            new_status = "queued"

        if campaign.status != new_status:
            log(db, "INFO", f"Campaign #{campaign.id} status → {new_status}", campaign_id=campaign.id)
            campaign.status = new_status
        db.commit()
    finally:
        db.close()
