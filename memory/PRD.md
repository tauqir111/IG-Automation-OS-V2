# IG Automation OS — PRD

## Problem Statement
Internal agency tool for **content publishing** across a large pool of managed Instagram accounts (~1000). Eliminates opening accounts one-by-one to publish the same or multiple pieces of content. **Not** an SMM engagement tool — no fake likes/views/comments/shares.

## Tech Stack
- Backend: Python + FastAPI + SQLAlchemy + SQLite
- Frontend: Jinja2 templates + Vanilla JS + custom CSS (dark, agency-forward, Inter + JetBrains Mono, electric lime accent `#c8ff2c`)
- Automation (later phases): Playwright w/ persistent browser profiles

## Users
- Agency operators creating publishing campaigns
- Administrators managing the account pool

## Architecture
All backend + HTML routes live under `/api` (platform ingress restriction). The React shell at `/` redirects to `/api/`.

```
/app/backend/
  server.py                     FastAPI entry + router include
  app/
    database.py                 SQLite engine + init + settings seed
    models.py                   accounts, campaigns, campaign_files, jobs, settings, logs
    schemas.py                  Pydantic I/O
    services/
      logger.py                 log-to-SQLite helper
      distribution.py           estimate_jobs + plan_pairs (same / one_per_account / round_robin)
    api/
      pages.py                  Jinja2 HTML routes
      campaigns.py              REST: upload, create, list, detail, pause/resume/stop/retry
      accounts.py               REST: add/list/stats/patch/delete, open-session stub
      system.py                 REST: settings, logs
    templates/                  base.html + dashboard, campaigns, campaign_details, accounts, logs, settings
    static/                     css + per-page js
  data/ig_automation.db         SQLite
  uploads/                      uploaded content (video/image)
  profiles/                     placeholder for persistent Playwright profiles
```

## Phase 1 — Implemented (2026-07-30)
- Modular FastAPI project structure
- SQLite schema: accounts, campaigns, campaign_files, jobs, settings, logs
- Dark agency dashboard (sidebar: Dashboard / Campaigns / Accounts / Logs / Settings)
- SYSTEM ONLINE status pill (top-right)
- **Dashboard / Create Campaign**:
  - Reel vs Static content type toggle (UI adapts, file input `accept` changes)
  - Bulk drag-and-drop upload with per-file remove + Clear All
  - Presets: 100 / 200 / 300 / 500 / 1000 + custom quantity input
  - Caption textarea w/ 2200-char counter
  - Reel-only Instagram Music section (Original vs IG Music + song search field)
  - Distribution modes: Same → All, One File Per Account, Round Robin
  - Live campaign summary + estimated jobs (uses distribution logic, NOT files × accounts)
  - Confirmation modal before dispatch → creates DB record
- **Campaigns page**: filterable list with status tags + progress + click-through details
- **Campaign details**: config, progress bar, per-status counts, file list, pause/resume/stop/retry buttons
- **Accounts page**: total / available / busy / expired / disabled stats, table w/ actions (Open Session stub, Enable/Disable, Delete), Add Account allocates persistent profile directory
- **Logs page**: SQLite-backed log stream with level filters (INFO / SUCCESS / WARNING / ERROR), auto-refresh every 15s. Never logs secrets.
- **Settings page**: General (workers/delay/retries), Browser (headless/timeout), Storage (profiles/uploads/logs dirs). Defaults seeded.

## Phase 2 — Implemented (2026-07-30)
- Playwright installed + Chromium available (uses `PLAYWRIGHT_BROWSERS_PATH` from `.env`)
- New module `app/automation/browser_session.py`:
  - Per-account `asyncio.Lock` + active-task registry (never two browsers on the same profile)
  - `connect_account(id)` — launches persistent-context browser at `https://www.instagram.com/`, visible when `$DISPLAY` is set, waits for the operator to close the window (or 30-min timeout), then auto-verifies
  - `verify_account(id)` — headless verification, opens `/accounts/edit/` and checks for a non-empty `sessionid` cookie + no login redirect + no login form (reliable signal)
  - Automatic status updates + activity logging (no secrets ever logged)
  - `get_environment()` — reports `has_display`, `playwright_installed`, `chromium_installed`, `browsers_dir` and a level (ok/warn/error) with a human message
- New API endpoints on the accounts router:
  - `POST /api/v1/accounts/{id}/connect` — start manual-login flow
  - `POST /api/v1/accounts/{id}/verify` — headless session check
  - `POST /api/v1/accounts/{id}/open-session` — alias for connect
  - `GET  /api/v1/accounts/environment` — banner data
- Session state machine expanded: `unknown | connecting | verifying | connected | login_required | expired | busy`
- Profile allocation switched to `profiles/account_{id:04d}/` (per spec)
- Accounts page redesigned to spec columns: **ID · Account · Session · Status · Actions**
  - Badges: `CONNECTED` (green) / `LOGIN REQUIRED` (amber) / `EXPIRED` (amber) / `CONNECTING…` / `VERIFYING…` / `BUSY` / `UNKNOWN`
  - Actions: `Connect Instagram` (or `Open Session` when connected) · `Verify` · `Enable/Disable` · `Delete`
  - Buttons disable while a session is in progress; page auto-polls every 3s during activity, 15s otherwise
  - Environment banner at top of page (ok/warn/error) with a clear message about local-vs-cloud
- `available` stat is now `enabled AND session_status='connected'` (never merely "account row exists")
- Concurrency-safe: attempting a second Connect while one is active returns HTTP 409

## Phase 2 — Not Implemented (deferred)
- Cross-process locking (only single-process asyncio locks). Fine while everything runs in one uvicorn worker; needs a filesystem lock or Redis lock once we scale workers.
- Distributed session worker (a remote agent that runs the browser on an operator's machine and streams status back). The current architecture is agent-ready — endpoints, DB and UI are unchanged either way.

## Phase 3 — Deferred (Queue + Workers)
- Materialize jobs from campaign + selected available accounts using `plan_pairs`
- Async worker pool (concurrency from settings)
- Live progress polling, pause/resume/stop enforcement, retry-failed
- Paginated job rows on campaign detail

## Phase 4-8 — Deferred
- Test publishing with one account (P4)
- Static post automation (P5)
- Reel upload automation (P6)
- Instagram Music search + selection (P7) — no volume adjustment
- Controlled multi-account rollout (P8)

## Explicitly Out of Scope (Product Guardrails)
- No password storage
- No SMM engagement (likes/views/comments/shares/reposts)
- No custom audio volume control (keep original as-is)
- No account groups
