"""IG Automation OS — FastAPI entrypoint.

All routes (pages + REST) are mounted under `/api` because the platform
ingress only forwards paths beginning with `/api` to this backend.
"""
import logging
import os
from pathlib import Path

from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env before importing any app modules that read env at import time
# (e.g. automation.browser_session reads PLAYWRIGHT_BROWSERS_PATH).
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from app.database import init_db  # noqa: E402
from app.api.pages import router as pages_router  # noqa: E402
from app.api.campaigns import router as campaigns_router  # noqa: E402
from app.api.accounts import router as accounts_router  # noqa: E402
from app.api.system import router as system_router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ig_automation_os")

init_db()

app = FastAPI(title="IG Automation OS", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(pages_router)
api_router.include_router(campaigns_router)
api_router.include_router(accounts_router)
api_router.include_router(system_router)


@api_router.get("/health")
async def health():
    return {"status": "ok", "service": "IG Automation OS", "phase": 1}


app.include_router(api_router)

STATIC_DIR = ROOT_DIR / "app" / "static"
app.mount("/api/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def on_startup():
    logger.info("IG Automation OS ready — SQLite initialised")
