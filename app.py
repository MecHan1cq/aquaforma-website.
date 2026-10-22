import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import create_engine, String, Text, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aquaforma.db")
# Render commonly provides postgres:// or postgresql:// URLs. Use psycopg 3,
# which is installed by requirements.txt, instead of SQLAlchemy's psycopg2 default.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
app = FastAPI(title="AquaForma API", version="1.1.0")
origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=["*"] if "*" in origins else origins, allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])

class Base(DeclarativeBase):
    pass

class Enquiry(Base):
    __tablename__ = "enquiries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    project_type: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)

class Contact(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    country: str = Field(default="", max_length=160)
    project_type: str = Field(min_length=2, max_length=80)
    message: str = Field(min_length=10, max_length=5000)
    language: str = Field(default="en", pattern="^(ru|pl|en|de|lt)$")

    @field_validator("name", "country", "project_type", "message", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

def notify_telegram(item: Contact, enquiry_id: int) -> None:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    body = (f"New website enquiry #{enquiry_id}\nName: {item.name}\nEmail: {item.email}\nLocation: {item.country or 'Not provided'}\nType: {item.project_type}\nLanguage: {item.language}\nMessage: {item.message}")
    try:
        response = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": body}, timeout=8.0)
        response.raise_for_status()
    except Exception as exc:
        print(f"Telegram notification failed for enquiry #{enquiry_id}: {type(exc).__name__}")

def notify_email(item: Contact, enquiry_id: int) -> None:
    host, user, password, recipient = (os.getenv(k, "").strip() for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"))
    if not all((host, user, password, recipient)):
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Website enquiry #{enquiry_id}"
        msg["From"] = os.getenv("MAIL_FROM", user).strip() or user
        msg["To"] = recipient
        msg.set_content(f"Name: {item.name}\nEmail: {item.email}\nLocation: {item.country or 'Not provided'}\nProject type: {item.project_type}\nLanguage: {item.language}\n\n{item.message}")
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
    except Exception as exc:
        print(f"Email notification failed for enquiry #{enquiry_id}: {type(exc).__name__}")

@app.get("/")
def root():
    return {"service": "AquaForma API", "status": "ok", "docs": "/docs"}

@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

@app.post("/api/contact", status_code=201)
def contact(payload: Contact):
    db = Session()
    try:
        row = Enquiry(name=payload.name, email=str(payload.email), country=payload.country, project_type=payload.project_type, message=payload.message, language=payload.language)
        db.add(row)
        db.commit()
        db.refresh(row)
        enquiry_id = row.id
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save enquiry")
    finally:
        db.close()
    # Notifications are best-effort: failure must not lose a saved enquiry.
    notify_telegram(payload, enquiry_id)
    notify_email(payload, enquiry_id)
    return {"ok": True, "id": enquiry_id, "message": "Enquiry received"}
