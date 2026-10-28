import csv
import io
import os
import secrets
import time
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import create_engine, String, DateTime, Integer, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker

load_dotenv()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./growth.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-this-before-deploying")
SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
WORKSHOP_TITLE = os.getenv("WORKSHOP_TITLE", "Build Your First AI Project in 60 Minutes")
WORKSHOP_DATE = os.getenv("WORKSHOP_DATE", "Date to be confirmed")
WORKSHOP_MODE = os.getenv("WORKSHOP_MODE", "Online workshop")

app = FastAPI(title="Workshop Growth Platform", version="1.0.0")

class Base(DeclarativeBase):
    pass

class Registration(Base):
    __tablename__ = "registrations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    college: Mapped[str] = mapped_column(String(180), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    referral_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(60), default="website", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class Ambassador(Base):
    __tablename__ = "ambassadors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    college: Mapped[str] = mapped_column(String(180), nullable=False)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

Base.metadata.create_all(bind=engine)

class RegistrationIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    college: str = Field(min_length=2, max_length=180)
    branch: str = Field(min_length=2, max_length=100)
    graduation_year: int = Field(ge=2024, le=2035)
    referral_code: Optional[str] = Field(default=None, max_length=40)
    source: str = Field(default="website", max_length=60)

class LoginIn(BaseModel):
    username: str
    password: str

class AmbassadorIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    college: str = Field(min_length=2, max_length=180)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def make_token(username: str) -> str:
    payload = f"{username}:{int(time.time()) + 8 * 60 * 60}"
    encoded = b64(payload.encode())
    signature = b64(hmac.new(SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"

def verify_token(token: str) -> bool:
    try:
        encoded, signature = token.split(".", 1)
        expected = b64(hmac.new(SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return False
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        username, expires = payload.rsplit(":", 1)
        return username == ADMIN_USERNAME and int(expires) > int(time.time())
    except Exception:
        return False

def require_admin(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in to access the dashboard.")
    token = authorization.split(" ", 1)[1]
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Your session expired. Please sign in again.")
    return True

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "workshop-growth-platform"}

@app.get("/api/public-config")
def public_config():
    return {"title": WORKSHOP_TITLE, "date": WORKSHOP_DATE, "mode": WORKSHOP_MODE}

@app.post("/api/register", status_code=201)
def register(payload: RegistrationIn, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    existing = db.scalar(select(Registration).where(Registration.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="This email is already registered.")
    referral = (payload.referral_code or "").strip().upper() or None
    source = (payload.source or "website").strip()[:60]
    if referral:
        ambassador = db.scalar(select(Ambassador).where(Ambassador.code == referral))
        if ambassador:
            source = "ambassador"
    item = Registration(
        full_name=payload.full_name.strip(),
        email=email,
        college=payload.college.strip(),
        branch=payload.branch.strip(),
        graduation_year=payload.graduation_year,
        referral_code=referral,
        source=source,
    )
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not save registration. Please try again.")
    return {"message": "Registration received successfully.", "registration_id": item.id}

@app.post("/api/admin/login")
def login(payload: LoginIn):
    username_ok = hmac.compare_digest(payload.username, ADMIN_USERNAME)
    password_ok = hmac.compare_digest(payload.password, ADMIN_PASSWORD)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    return {"access_token": make_token(ADMIN_USERNAME), "token_type": "bearer"}

@app.get("/api/admin/overview", dependencies=[Depends(require_admin)])
def overview(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Registration)) or 0
    today = datetime.now(timezone.utc).date()
    rows = db.scalars(select(Registration)).all()
    today_count = sum(1 for r in rows if r.created_at and r.created_at.date() == today)
    by_source = {}
    for r in rows:
        by_source[r.source] = by_source.get(r.source, 0) + 1
    last_7 = []
    for offset in reversed(range(7)):
        day = today.fromordinal(today.toordinal() - offset)
        count = sum(1 for r in rows if r.created_at and r.created_at.date() == day)
        last_7.append({"date": day.isoformat(), "count": count})
    return {"total_registrations": total, "today": today_count, "target": 500,
            "remaining": max(0, 500-total), "by_source": by_source, "last_7_days": last_7}

@app.get("/api/admin/registrations", dependencies=[Depends(require_admin)])
def registrations(q: str = "", db: Session = Depends(get_db)):
    stmt = select(Registration).order_by(Registration.created_at.desc())
    items = db.scalars(stmt).all()
    q = q.strip().lower()
    if q:
        items = [x for x in items if q in x.full_name.lower() or q in x.email.lower() or q in x.college.lower() or q in x.source.lower()]
    return [{"id": x.id, "full_name": x.full_name, "email": x.email, "college": x.college,
             "branch": x.branch, "graduation_year": x.graduation_year, "referral_code": x.referral_code,
             "source": x.source, "created_at": x.created_at.isoformat() if x.created_at else ""} for x in items]

@app.get("/api/admin/export.csv", dependencies=[Depends(require_admin)])
def export_csv(db: Session = Depends(get_db)):
    items = db.scalars(select(Registration).order_by(Registration.created_at.desc())).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Name","Email","College","Branch","Graduation Year","Referral Code","Source","Registered At"])
    for x in items:
        writer.writerow([x.id,x.full_name,x.email,x.college,x.branch,x.graduation_year,x.referral_code or "",x.source,x.created_at.isoformat() if x.created_at else ""])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=registrations.csv"})

@app.get("/api/admin/ambassadors", dependencies=[Depends(require_admin)])
def ambassadors(db: Session = Depends(get_db)):
    items = db.scalars(select(Ambassador).order_by(Ambassador.created_at.desc())).all()
    counts = {}
    for reg in db.scalars(select(Registration)).all():
        if reg.referral_code:
            counts[reg.referral_code] = counts.get(reg.referral_code, 0) + 1
    return [{"id": x.id, "name": x.name, "email": x.email, "college": x.college,
             "code": x.code, "referrals": counts.get(x.code, 0)} for x in items]

@app.post("/api/admin/ambassadors", status_code=201, dependencies=[Depends(require_admin)])
def create_ambassador(payload: AmbassadorIn, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(Ambassador).where(Ambassador.email == email)):
        raise HTTPException(status_code=409, detail="An ambassador with this email already exists.")
    base = "".join(ch for ch in payload.name.upper() if ch.isalnum())[:5] or "NXT"
    code = f"{base}{secrets.token_hex(2).upper()}"
    item = Ambassador(name=payload.name.strip(), email=email, college=payload.college.strip(), code=code)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "name": item.name, "email": item.email, "college": item.college, "code": item.code, "referrals": 0}

@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
