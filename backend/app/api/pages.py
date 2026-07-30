"""HTML page routes — Jinja2 templates served under /api/ so the ingress routes them to FastAPI."""
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Campaign

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(tags=["pages"])


def _page(request: Request, template: str, active: str, **ctx):
    return templates.TemplateResponse(
        template,
        {"request": request, "active": active, **ctx},
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return _page(request, "dashboard.html", active="dashboard")


@router.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(request: Request):
    return _page(request, "campaigns.html", active="campaigns")


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_details_page(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _page(request, "campaign_details.html", active="campaigns", campaign=campaign)


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    return _page(request, "accounts.html", active="accounts")


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    return _page(request, "logs.html", active="logs")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return _page(request, "settings.html", active="settings")
