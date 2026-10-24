
import os
import logging
import smtplib
from datetime import datetime, timezone
from typing import Optional
from email.message import EmailMessage

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Text, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logger = logging.getLogger("uvicorn.error")

URL = os.getenv("DATABASE_URL", "sqlite:///./aquaforma.db")

if URL.startswith("postgres://"):
    URL = URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False}
    if URL.startswith("sqlite") else {}
)

Session = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

app = FastAPI(title="AquaForma API", version="1.0.0")

origins = [
    x.strip()
    for x in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if x.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in origins else origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"]
)


class Base(DeclarativeBase):
    pass


class Enquiry(Base):
    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(
        String(160), nullable=True
    )
    project_type: Mapped[str] = mapped_column(
        String(80), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        String(5), nullable=False, default="en"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


Base.metadata.create_all(engine)


class Contact(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    country: str = Field(default="", max_length=160)
    project_type: str = Field(min_length=2, max_length=80)
    message: str = Field(min_length=10, max_length=5000)
    language: str = Field(
        default="en", pattern="^(ru|pl|en|de)$"
    )


def send_enquiry_email(row: Enquiry) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_to = os.getenv("EMAIL_TO")

    if not all([smtp_host, smtp_user, smtp_password, email_to]):
        raise RuntimeError("SMTP environment variables are missing")

    msg = EmailMessage()
    msg["Subject"] = f"New AquaForma enquiry #{row.id}"
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg["Reply-To"] = row.email

    msg.set_content(
        f"""New enquiry received from the AquaForma website.

Enquiry ID: #{row.id}
Name: {row.name}
Email: {row.email}
Country / city: {row.country or "Not specified"}
Project type: {row.project_type}
Language: {row.language}

Project description:
{row.message}
"""
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=25) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_password.replace(" ", ""))
        server.send_message(msg)


@app.get("/")
def root():
    return {
        "service": "AquaForma API",
        "status": "ok",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")

        return {"status": "healthy", "database": "connected"}

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        ) from exc


@app.post("/api/contact", status_code=201)
def contact(p: Contact):
    db = Session()

    try:
        try:
            row = Enquiry(
                name=p.name.strip(),
                email=str(p.email),
                country=p.country.strip(),
                project_type=p.project_type.strip(),
                message=p.message.strip(),
                language=p.language
            )

            db.add(row)
            db.commit()
            db.refresh(row)

        except Exception as exc:
            db.rollback()
            logger.exception("Could not save enquiry")
            raise HTTPException(
                status_code=500,
                detail="Could not save enquiry"
            ) from exc

        try:
            send_enquiry_email(row)
            email_sent = True

        except Exception:
            email_sent = False
            logger.exception(
                "Enquiry #%s was saved, but email notification failed",
                row.id
            )

        return {
            "ok": True,
            "id": row.id,
            "message": "Enquiry received",
            "email_sent": email_sent
        }

    finally:
        db.close()
