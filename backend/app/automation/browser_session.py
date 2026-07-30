"""Playwright session worker for Instagram accounts.

Each managed account has its own persistent Playwright profile directory. Two
workers must never open the same profile at the same time — enforced with
per-account asyncio locks.

Passwords, cookies and session IDs are never displayed or logged. The operator
performs manual login inside the browser Playwright launches; Playwright's
persistent context retains the resulting session on disk.

Environment:
  * If a display (`$DISPLAY`) is available, the browser opens visibly for
    manual login.
  * If no display (typical cloud/preview environment), the browser is launched
    headless — which means an operator cannot complete manual login there.
    In that case, the flow must be executed on the machine hosting the app.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..database import SessionLocal
from ..models import Account
from ..services.logger import log


# Playwright import is deferred so a missing chromium install only breaks the
# actual worker call, not import of the whole app.
try:
    from playwright.async_api import async_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover
    PLAYWRIGHT_AVAILABLE = False


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY"))


def _browsers_dir() -> Path:
    return Path(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        or os.path.expanduser("~/.cache/ms-playwright")
    )


# ---------------------------------------------------------------------------
# Concurrency: per-account lock + active-task registry
# ---------------------------------------------------------------------------
_locks: dict[int, asyncio.Lock] = {}
_tasks: dict[int, asyncio.Task] = {}


def _lock_for(account_id: int) -> asyncio.Lock:
    if account_id not in _locks:
        _locks[account_id] = asyncio.Lock()
    return _locks[account_id]


def is_active(account_id: int) -> bool:
    task = _tasks.get(account_id)
    return task is not None and not task.done()


# ---------------------------------------------------------------------------
# Small helpers that use their own DB session (they run in background tasks)
# ---------------------------------------------------------------------------
def _update_account(account_id: int, **fields) -> None:
    db = SessionLocal()
    try:
        acc = db.query(Account).filter(Account.id == account_id).first()
        if not acc:
            return
        for k, v in fields.items():
            setattr(acc, k, v)
        db.commit()
    finally:
        db.close()


def _write_log(account_id: Optional[int], level: str, message: str) -> None:
    db = SessionLocal()
    try:
        log(db, level, message, account_id=account_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Verification: given an existing persistent profile, is the session logged in?
# ---------------------------------------------------------------------------
async def _verify_persistent_profile(profile_path: Path) -> str:
    """Return 'connected' or 'login_required'.

    The most reliable signal that an Instagram session is authenticated is the
    presence of a non-empty ``sessionid`` cookie on the ``.instagram.com``
    domain. We visit a protected route (``/accounts/edit/``) so Instagram sets
    or refreshes cookies, then inspect them.
    """
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-first-run", "--no-default-browser-check"],
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                await page.goto(
                    "https://www.instagram.com/accounts/edit/",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
            except Exception:
                # network hiccup — fall through to cookie check anyway
                pass
            await asyncio.sleep(2)  # let redirects settle

            # 1) Cookie signal — the sessionid cookie is the auth token.
            has_session_cookie = False
            try:
                cookies = await context.cookies("https://www.instagram.com/")
                has_session_cookie = any(
                    c.get("name") == "sessionid" and c.get("value")
                    for c in cookies
                )
            except Exception:
                pass

            # 2) URL / DOM signal — if Instagram redirected to /accounts/login/
            #    OR a login form is present, the user is not authed regardless.
            current = (page.url or "").split("?")[0]
            redirected_to_login = "/accounts/login" in current
            login_form_present = False
            try:
                login_form_present = bool(
                    await page.query_selector('input[name="username"]')
                )
            except Exception:
                pass

            if has_session_cookie and not redirected_to_login and not login_form_present:
                return "connected"
            return "login_required"
        finally:
            try:
                await context.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Connect: launch a browser for manual login, then verify after close
# ---------------------------------------------------------------------------
async def connect_account(account_id: int, timeout_minutes: int = 30) -> dict:
    """Kick off the manual-login flow in a background task."""
    if not PLAYWRIGHT_AVAILABLE:
        return {"ok": False, "message": "Playwright is not installed on this server."}

    lock = _lock_for(account_id)
    if lock.locked() or is_active(account_id):
        return {"ok": False, "message": "A session is already in progress for this account."}

    async def _worker():
        async with lock:
            # 1) Load account + set status
            db = SessionLocal()
            try:
                acc = db.query(Account).filter(Account.id == account_id).first()
                if not acc:
                    return
                profile_path = Path(acc.profile_path)
                profile_path.mkdir(parents=True, exist_ok=True)
                acc.session_status = "connecting"
                db.commit()
                account_name = acc.account_name
                log(
                    db,
                    "INFO",
                    f"Launching browser for '{account_name}' — waiting for manual login",
                    account_id=account_id,
                )
            finally:
                db.close()

            # 2) Open browser and wait for user to close it (or hit timeout)
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    has_display = _has_display()
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir=str(profile_path),
                        headless=not has_display,
                        viewport={"width": 1280, "height": 800},
                        args=["--no-first-run", "--no-default-browser-check"],
                    )
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.goto(
                        "https://www.instagram.com/",
                        wait_until="domcontentloaded",
                        timeout=45000,
                    )

                    if not has_display:
                        # No display: cannot complete manual login here. Close
                        # the browser immediately and report the situation.
                        try:
                            await context.close()
                        except Exception:
                            pass
                        _update_account(account_id, session_status="login_required")
                        _write_log(
                            account_id,
                            "WARNING",
                            "This host has no display — visible manual login requires running the app locally.",
                        )
                        return

                    # Visible mode: wait until user closes the last page/window
                    close_evt = asyncio.Event()

                    def _on_close(_ctx):
                        close_evt.set()

                    context.on("close", _on_close)
                    try:
                        await asyncio.wait_for(
                            close_evt.wait(),
                            timeout=timeout_minutes * 60,
                        )
                    except asyncio.TimeoutError:
                        try:
                            await context.close()
                        except Exception:
                            pass

                # 3) After manual login, verify session by relaunching headless
                await asyncio.sleep(1)
                status = await _verify_persistent_profile(profile_path)
                _update_account(
                    account_id,
                    session_status=status,
                    last_used_at=datetime.now(timezone.utc),
                )
                _write_log(
                    account_id,
                    "SUCCESS" if status == "connected" else "WARNING",
                    f"Session verification for '{account_name}': {status}",
                )
            except Exception as e:
                _update_account(account_id, session_status="unknown")
                _write_log(
                    account_id,
                    "ERROR",
                    f"Connect session error: {type(e).__name__}: {str(e)[:200]}",
                )

    task = asyncio.create_task(_worker())
    _tasks[account_id] = task
    return {"ok": True, "message": "Connect flow started. The browser window will open on the host machine."}


# ---------------------------------------------------------------------------
# Verify only: no window, just check current session validity
# ---------------------------------------------------------------------------
async def verify_account(account_id: int) -> dict:
    if not PLAYWRIGHT_AVAILABLE:
        return {"ok": False, "message": "Playwright is not installed on this server."}

    lock = _lock_for(account_id)
    if lock.locked() or is_active(account_id):
        return {"ok": False, "message": "A session is already in progress for this account."}

    async def _worker():
        async with lock:
            db = SessionLocal()
            profile_path: Optional[Path] = None
            account_name = ""
            try:
                acc = db.query(Account).filter(Account.id == account_id).first()
                if not acc:
                    return
                profile_path = Path(acc.profile_path)
                account_name = acc.account_name
                acc.session_status = "verifying"
                db.commit()
                log(db, "INFO", f"Verifying session for '{account_name}'", account_id=account_id)
            finally:
                db.close()

            try:
                if not profile_path or not profile_path.exists() or not any(profile_path.iterdir()):
                    _update_account(account_id, session_status="login_required")
                    _write_log(
                        account_id,
                        "WARNING",
                        "No persistent profile yet — Connect Instagram first",
                    )
                    return
                status = await _verify_persistent_profile(profile_path)
                _update_account(
                    account_id,
                    session_status=status,
                    last_used_at=datetime.now(timezone.utc),
                )
                _write_log(
                    account_id,
                    "SUCCESS" if status == "connected" else "WARNING",
                    f"Session verification for '{account_name}': {status}",
                )
            except Exception as e:
                _update_account(account_id, session_status="unknown")
                _write_log(
                    account_id,
                    "ERROR",
                    f"Verify error: {type(e).__name__}: {str(e)[:200]}",
                )

    task = asyncio.create_task(_worker())
    _tasks[account_id] = task
    return {"ok": True, "message": "Verification started."}


# ---------------------------------------------------------------------------
# Environment probe — used by the UI to show a helpful banner
# ---------------------------------------------------------------------------
def get_environment() -> dict:
    browsers_dir = _browsers_dir()
    has_display = _has_display()
    chromium_installed = False
    if browsers_dir.exists():
        try:
            chromium_installed = any(
                p.name.startswith("chromium") for p in browsers_dir.iterdir()
            )
        except OSError:
            chromium_installed = False
    if not PLAYWRIGHT_AVAILABLE:
        msg = "Playwright is not installed on this server. Install `playwright` and run `playwright install chromium`."
        level = "error"
    elif not chromium_installed:
        msg = f"Playwright is installed, but the Chromium browser has not been downloaded yet. Run `playwright install chromium` (looking in {browsers_dir})."
        level = "warn"
    elif not has_display:
        msg = (
            "This host is headless (no display server). Session verification (headless) works here, "
            "but visible manual login must be performed on the machine where this app is running. "
            "To connect an Instagram account, run the app locally and click Connect Instagram — "
            "the browser will open on your desktop."
        )
        level = "warn"
    else:
        msg = "Ready — clicking Connect Instagram will open a browser window on this machine for manual login."
        level = "ok"
    return {
        "has_display": has_display,
        "playwright_installed": PLAYWRIGHT_AVAILABLE,
        "chromium_installed": chromium_installed,
        "browsers_dir": str(browsers_dir),
        "level": level,
        "message": msg,
    }
