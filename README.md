# IG Automation OS

Internal agency dashboard for **bulk content publishing** across a large pool of managed Instagram accounts. Not an SMM engagement tool.

## Stack
- FastAPI + SQLAlchemy + SQLite
- Jinja2 templates + Vanilla JS + custom CSS
- Playwright (later phases) with persistent per-account browser profiles

## Run locally
```bash
cd /app/backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Open **http://localhost:8001/api/**.

In the Emergent preview, the app is served at `/api/` (the platform ingress only routes `/api*` to FastAPI). The React shell at `/` redirects to `/api/` automatically.

## Layout
```
backend/
  server.py                  FastAPI entry
  app/
    database.py              SQLite engine + init + default settings
    models.py                accounts, campaigns, campaign_files, jobs, settings, logs
    schemas.py               Pydantic
    services/                logger, distribution logic
    api/                     pages (HTML) + campaigns/accounts/system (REST)
    templates/               Jinja2
    static/                  CSS + per-page JS
  data/                      ig_automation.db (SQLite)
  uploads/                   uploaded content
  profiles/                  persistent Playwright profiles (Phase 2)
```

## API surface
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/campaigns/upload` | Multipart bulk upload (content_type + files) |
| DELETE | `/api/v1/campaigns/upload/{file_id}` | Remove orphaned upload |
| POST | `/api/v1/campaigns` | Create a campaign, attaches previously-uploaded files |
| GET | `/api/v1/campaigns` | List campaigns |
| GET | `/api/v1/campaigns/{id}` | Campaign details + files + job counts |
| POST | `/api/v1/campaigns/{id}/pause|resume|stop|retry` | Lifecycle actions |
| GET | `/api/v1/accounts` · `POST /api/v1/accounts` | Account pool |
| GET | `/api/v1/accounts/stats` | Totals |
| PATCH `/api/v1/accounts/{id}` · DELETE | | Enable/disable/delete |
| POST | `/api/v1/accounts/{id}/open-session` | Phase 2 stub |
| GET/PUT | `/api/v1/settings` | System settings |
| GET | `/api/v1/logs` | Filtered activity log |

## What Phase 1 covers
Everything listed in section 25 of the spec — dashboard UX, DB models, campaign creation, campaigns/accounts/logs/settings pages. **No** Playwright automation, **no** mass posting, **no** SMM features, **no** password storage.

## What's next (Phase 2)
- Manual account onboarding with Playwright + persistent profile
- Session status detection
- Account locking

See `/app/memory/PRD.md` for the full roadmap.
