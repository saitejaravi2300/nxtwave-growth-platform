# Deployment link
https://nxtwave-growth-platform.onrender.com
# NxtWave Workshop Growth Platform

A full-stack workshop registration and campaign management website built as a real project, not a seeded demo.

## Features
- Public workshop landing page and registration form
- Server-side validation and duplicate-email prevention
- Persistent SQLite database (created automatically on first run)
- Referral code capture from `?ref=CODE`
- Admin login backed by a server-side password and signed session token
- Admin dashboard with live database counts (no fake seed metrics)
- Registrations table, search, CSV export
- Ambassador code creation and campaign overview
- Responsive UI

## Stack
- Frontend: HTML, CSS, vanilla JavaScript (no build step required)
- Backend: FastAPI, SQLAlchemy, SQLite, Pydantic
- Auth: signed JWT-style bearer token (HMAC SHA-256)

## Requirements
- Python 3.10+
- pip

## Run locally
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

The FastAPI server serves the website and API from the same origin. SQLite database is created at `backend/growth.db`.

## Configure admin login
Edit `backend/.env`:
- `ADMIN_USERNAME` (default: admin)
- `ADMIN_PASSWORD` (change this before deploying)
- `SECRET_KEY` (set a long random value)
- `DATABASE_URL` (optional; defaults to SQLite)

Never deploy with the example password or secret key.

## API endpoints
- `GET /api/health`
- `POST /api/register`
- `POST /api/admin/login`
- `GET /api/admin/overview` (auth required)
- `GET /api/admin/registrations` (auth required)
- `GET /api/admin/export.csv` (auth required)
- `POST /api/admin/ambassadors` (auth required)
- `GET /api/admin/ambassadors` (auth required)

## Before production launch
1. Replace workshop date/platform details with confirmed information.
2. Add HTTPS and configure a production database (PostgreSQL recommended).
3. Set strong `ADMIN_PASSWORD` and `SECRET_KEY`.
4. Add privacy notice/consent language approved by the organizer.
5. Configure backups, logging, rate limiting, and email confirmation delivery.
6. Deploy the backend and frontend together or configure a reverse proxy.
7. This project does not send confirmation emails or connect to NxtWave systems unless you configure those integrations.
