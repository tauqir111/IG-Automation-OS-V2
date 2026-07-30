"""Campaign REST endpoints: create, list, detail, upload, lifecycle actions."""
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..database import get_db, BASE_DIR
from ..models import Campaign, CampaignFile, Job
from ..schemas import CampaignCreate, CampaignOut, CampaignDetail, CampaignFileOut
from ..services.logger import log
from ..services.distribution import estimate_jobs

router = APIRouter(prefix="/v1/campaigns", tags=["campaigns"])

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _valid_for(content_type: str, filename: str, mime: str) -> bool:
    ext = Path(filename).suffix.lower()
    if content_type == "reel":
        return ext in VIDEO_EXTS or mime in VIDEO_TYPES
    if content_type == "static":
        return ext in IMAGE_EXTS or mime in IMAGE_TYPES
    return False


@router.post("/upload", response_model=List[CampaignFileOut])
async def upload_files(
    content_type: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload one or many files. Files are stored on disk and a stub CampaignFile
    row is created (campaign_id=0) which is later linked when the campaign is
    finalised via POST /v1/campaigns."""
    if content_type not in ("reel", "static"):
        raise HTTPException(status_code=400, detail="Invalid content_type")

    saved: List[CampaignFile] = []
    for idx, upload in enumerate(files):
        if not _valid_for(content_type, upload.filename or "", upload.content_type or ""):
            raise HTTPException(
                status_code=400,
                detail=f"File '{upload.filename}' not allowed for {content_type} campaign",
            )
        # unique filename on disk to avoid collisions
        ext = Path(upload.filename or "").suffix.lower()
        unique = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / unique
        size = 0
        with dest.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                f.write(chunk)
                size += len(chunk)
        row = CampaignFile(
            campaign_id=0,
            filename=upload.filename or unique,
            stored_path=str(dest),
            file_type=upload.content_type or "application/octet-stream",
            size_bytes=size,
            order_index=idx,
        )
        db.add(row)
        db.flush()
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved


@router.delete("/upload/{file_id}")
async def delete_uploaded_file(file_id: int, db: Session = Depends(get_db)):
    row = db.query(CampaignFile).filter(CampaignFile.id == file_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    # Only allow deleting orphaned uploads (not yet attached to a campaign)
    if row.campaign_id != 0:
        raise HTTPException(status_code=400, detail="File already attached to a campaign")
    try:
        Path(row.stored_path).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("", response_model=CampaignDetail, status_code=201)
async def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    if payload.content_type not in ("reel", "static"):
        raise HTTPException(status_code=400, detail="content_type must be 'reel' or 'static'")
    if payload.distribution_mode not in ("same", "one_per_account", "round_robin"):
        raise HTTPException(status_code=400, detail="Invalid distribution_mode")
    if payload.audio_mode not in ("original", "ig_music"):
        raise HTTPException(status_code=400, detail="Invalid audio_mode")
    if not payload.file_ids:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if payload.content_type == "reel" and payload.audio_mode == "ig_music" and not payload.music_search.strip():
        raise HTTPException(status_code=400, detail="Song search is required when Instagram Music is enabled")

    campaign = Campaign(
        content_type=payload.content_type,
        caption=payload.caption or "",
        account_quantity=payload.account_quantity,
        distribution_mode=payload.distribution_mode,
        audio_mode=payload.audio_mode if payload.content_type == "reel" else "original",
        music_search=payload.music_search.strip() if payload.content_type == "reel" else "",
        status="draft",
    )
    db.add(campaign)
    db.flush()

    # Attach uploaded files to this campaign
    rows = (
        db.query(CampaignFile)
        .filter(CampaignFile.id.in_(payload.file_ids), CampaignFile.campaign_id == 0)
        .all()
    )
    if len(rows) != len(payload.file_ids):
        raise HTTPException(status_code=400, detail="Some file IDs are invalid or already attached")
    for i, row in enumerate(rows):
        row.campaign_id = campaign.id
        row.order_index = i

    est = estimate_jobs(campaign.distribution_mode, payload.file_ids, campaign.account_quantity)
    log(
        db,
        "INFO",
        f"Campaign #{campaign.id} created — {campaign.content_type}, {len(rows)} file(s), "
        f"{campaign.account_quantity} accounts, mode={campaign.distribution_mode}, est_jobs={est}",
        campaign_id=campaign.id,
    )
    db.commit()
    db.refresh(campaign)

    return _serialize_campaign(campaign, db)


@router.get("", response_model=List[CampaignOut])
async def list_campaigns(db: Session = Depends(get_db)):
    return db.query(Campaign).order_by(Campaign.created_at.desc()).all()


@router.get("/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _serialize_campaign(campaign, db)


def _serialize_campaign(campaign: Campaign, db: Session) -> CampaignDetail:
    files = (
        db.query(CampaignFile)
        .filter(CampaignFile.campaign_id == campaign.id)
        .order_by(CampaignFile.order_index)
        .all()
    )
    counts_rows = (
        db.query(Job.status)
        .filter(Job.campaign_id == campaign.id)
        .all()
    )
    counts = {"queued": 0, "processing": 0, "successful": 0, "failed": 0}
    for (status,) in counts_rows:
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = sum(counts.values())
    data = CampaignOut.model_validate(campaign).model_dump()
    return CampaignDetail(
        **data,
        files=[CampaignFileOut.model_validate(f) for f in files],
        job_counts=counts,
    )


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _transition(db, campaign_id, "paused", "Campaign paused")


@router.post("/{campaign_id}/resume")
async def resume_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _transition(db, campaign_id, "running", "Campaign resumed")


@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _transition(db, campaign_id, "stopped", "Campaign stopped")


@router.post("/{campaign_id}/retry")
async def retry_failed(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    updated = (
        db.query(Job)
        .filter(Job.campaign_id == campaign_id, Job.status == "failed")
        .update({"status": "queued", "error_message": ""})
    )
    log(db, "INFO", f"Retrying {updated} failed job(s)", campaign_id=campaign_id)
    db.commit()
    return {"retried": updated}


def _transition(db: Session, campaign_id: int, new_status: str, msg: str):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = new_status
    if new_status == "stopped":
        campaign.completed_at = datetime.now(timezone.utc)
    log(db, "INFO", msg, campaign_id=campaign_id)
    db.commit()
    return {"status": new_status}
