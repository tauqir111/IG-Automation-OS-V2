"""IG Automation OS — FastAPI entrypoint.

All routes (pages + REST) are mounted under `/api` because the platform
ingress only forwards paths beginning with `/api` to this backend.
"""
import logging
import os
import sys
import asyncio
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env before importing any app modules that read env at import time
# (e.g. automation.browser_session reads PLAYWRIGHT_BROWSERS_PATH).
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from app.database import init_db, SessionLocal  # noqa: E402
from app.models import Setting  # noqa: E402
from app.api.pages import router as pages_router  # noqa: E402
from app.api.campaigns import router as campaigns_router  # noqa: E402
from app.api.accounts import router as accounts_router  # noqa: E402
from app.api.system import router as system_router  # noqa: E402
from app.services.crash_recovery import recover_on_startup  # noqa: E402
from app.automation.publisher_queue import queue as publisher_queue  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ig_automation_os")

init_db()

app = FastAPI(title="IG Automation OS", version="0.2.0")

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
    return {
        "status": "ok",
        "service": "IG Automation OS",
        "phase": 2,
        "publisher_max_concurrent": publisher_queue.max_concurrent,
    }


app.include_router(api_router)

STATIC_DIR = ROOT_DIR / "app" / "static"
app.mount("/api/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _read_max_concurrent() -> int:
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "concurrent_workers").first()
        return int(row.value) if row and row.value.isdigit() else 3
    except Exception:
        return 3
    finally:
        db.close()


@app.on_event("startup")
async def on_startup():
    # 1) Crash recovery: mark stale RUNNING jobs as ACTION_REQUIRED, release BUSY accounts.
    stats = recover_on_startup()
    if stats["jobs_marked_action_required"] or stats["accounts_released"]:
        logger.warning(
            "Recovered from prior crash — jobs→ACTION_REQUIRED: %d, accounts released: %d",
            stats["jobs_marked_action_required"], stats["accounts_released"],
        )

    # 2) Configure the publisher queue from Settings (concurrent_workers).
    publisher_queue.configure(_read_max_concurrent())
    logger.info(
        "IG Automation OS ready — SQLite initialised, publisher concurrency=%d",
        publisher_queue.max_concurrent,
    )


