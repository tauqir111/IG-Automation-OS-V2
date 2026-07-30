"""Account pool management + Instagram session onboarding (Phase 2)."""
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db, BASE_DIR
from ..models import Account
from ..schemas import AccountOut, AccountCreate, AccountUpdate
from ..services.logger import log
from ..automation import browser_session

router = APIRouter(prefix="/v1/accounts", tags=["accounts"])

PROFILES_DIR = BASE_DIR / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)


# Session statuses accepted by the API (automation module may also write
# these). Keep this list authoritative.
VALID_SESSION_STATUSES = {
    "unknown",       # never checked
    "connecting",    # visible browser open, waiting for user
    "verifying",     # headless verify in progress
    "connected",     # verified logged in
    "login_required",  # not authed / login form present
    "expired",       # was connected, now not
    "busy",          # in use by a publishing worker (future)
}


@router.get("", response_model=List[AccountOut])
async def list_accounts(db: Session = Depends(get_db)):
    return db.query(Account).order_by(Account.created_at.desc()).all()


@router.get("/stats")
async def account_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Account.id)).scalar() or 0
    available = (
        db.query(func.count(Account.id))
        .filter(
            Account.account_status == "enabled",
            Account.session_status == "connected",
        )
        .scalar()
        or 0
    )
    busy = (
        db.query(func.count(Account.id))
        .filter(Account.session_status == "busy")
        .scalar()
        or 0
    )
    expired = (
        db.query(func.count(Account.id))
        .filter(Account.session_status.in_(["expired", "login_required"]))
        .scalar()
        or 0
    )
    disabled = (
        db.query(func.count(Account.id))
        .filter(Account.account_status == "disabled")
        .scalar()
        or 0
    )
    return {
        "total": total,
        "available": available,
        "busy": busy,
        "expired": expired,
        "disabled": disabled,
    }


@router.get("/environment")
async def account_environment():
    """Returns whether this host can launch a visible browser for manual login."""
    return browser_session.get_environment()


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    name = payload.account_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="account_name is required")
    if db.query(Account).filter(Account.account_name == name).first():
        raise HTTPException(status_code=409, detail="account_name already exists")

    account = Account(
        account_name=name,
        profile_path="",  # filled in after we have an ID
        session_status="unknown",
        account_status="enabled",
    )
    db.add(account)
    db.flush()  # assign account.id

    profile_path = PROFILES_DIR / f"account_{account.id:04d}"
    profile_path.mkdir(parents=True, exist_ok=True)
    account.profile_path = str(profile_path)

    log(db, "INFO", f"Account '{name}' added — profile {profile_path.name}", account_id=account.id)
    db.commit()
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if payload.account_status is not None:
        if payload.account_status not in ("enabled", "disabled"):
            raise HTTPException(status_code=400, detail="Invalid account_status")
        account.account_status = payload.account_status
        log(db, "INFO", f"Account '{account.account_name}' → {payload.account_status}", account_id=account.id)
    if payload.session_status is not None:
        if payload.session_status not in VALID_SESSION_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid session_status")
        account.session_status = payload.session_status
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if browser_session.is_active(account.id):
        raise HTTPException(
            status_code=409,
            detail="A browser session is currently active for this account. Close it first.",
        )
    log(db, "WARNING", f"Account '{account.account_name}' deleted", account_id=account.id)
    db.delete(account)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Session onboarding endpoints (Phase 2)
# ---------------------------------------------------------------------------
@router.post("/{account_id}/connect")
async def connect_instagram(account_id: int, db: Session = Depends(get_db)):
    """Launch a persistent-profile browser so the operator can log in manually."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.account_status == "disabled":
        raise HTTPException(status_code=400, detail="Enable the account before connecting")
    result = await browser_session.connect_account(account.id)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message"))
    return result


@router.post("/{account_id}/verify")
async def verify_session(account_id: int, db: Session = Depends(get_db)):
    """Headless check of the account's persistent profile — updates session_status."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    result = await browser_session.verify_account(account.id)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("message"))
    return result


@router.post("/{account_id}/open-session")
async def open_session(account_id: int, db: Session = Depends(get_db)):
    """Alias for connect — opens the persistent-profile browser."""
    return await connect_instagram(account_id, db)
