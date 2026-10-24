
import os
import logging
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Text, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL = os.getenv("DATABASE_URL", "sqlite:///./aquaforma.db")

if URL.startswith("postgres://"):
    URL = URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False}
    if URL.startswith("sqlite")
    else {},
)

Session = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
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
    allow_headers=["Content-Type"],
)


class Base(DeclarativeBase):
    pass


class Enquiry(Base):
    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(254), nullable=False
    )
    country: Mapped[Optional[str]] = mapped_column(
        String(160), nullable=True
    )
    project_type: Mapped[str] = mapped_column(
        String(80), nullable=False
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    language: Mapped[str] = mapped_column(
        String(5), nullable=False, default="en"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
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


def send_enquiry_email(data: dict) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_to = os.getenv("EMAIL_TO")

    if not all([smtp_user, smtp_password, email_to]):
        logger.warning(
            "Email notification skipped: SMTP credentials are not configured."
        )
        return

    message = EmailMessage()
    message["Subject"] = (
        f"Новая заявка AquaForma №{data['id']}"
    )
    message["From"] = smtp_user
    message["To"] = email_to
    message["Reply-To"] = data["email"]

    message.set_content(
        f"""Новая заявка с сайта AquaForma

Номер заявки: {data['id']}
Имя: {data['name']}
Email клиента: {data['email']}
Страна / город: {data['country']}
Тип объекта: {data['project_type']}
Язык сайта: {data['language']}
Дата: {data['created_at']}

Описание проекта:
{data['message']}
"""
    )

    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))

        with smtplib.SMTP(
            smtp_host, smtp_port, timeout=15
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(message)

        logger.info(
            "Email notification sent for enquiry %s",
            data["id"],
        )

    except Exception:
        logger.exception(
            "Failed to send email for enquiry %s",
            data["id"],
        )


@app.get("/")
def root():
    return {
        "service": "AquaForma API",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")

        return {
            "status": "healthy",
            "database": "connected",
        }

    except Exception:
        raise HTTPException(
            503, "Database unavailable"
        )


@app.post("/api/contact", status_code=201)
def contact(
    p: Contact,
    background_tasks: BackgroundTasks,
):
    db = Session()

    try:
        row = Enquiry(
            name=p.name.strip(),
            email=str(p.email),
            country=p.country.strip(),
            project_type=p.project_type.strip(),
            message=p.message.strip(),
            language=p.language,
        )

        db.add(row)
        db.commit()
        db.refresh(row)

        email_data = {
            "id": row.id,
            "name": row.name,
            "email": row.email,
            "country": row.country or "Не указано",
            "project_type": row.project_type,
            "message": row.message,
            "language": row.language,
            "created_at": (
                row.created_at.isoformat()
                if row.created_at
                else "Не указано"
            ),
        }

        background_tasks.add_task(
            send_enquiry_email, email_data
        )

        return {
            "ok": True,
            "id": row.id,
            "message": "Enquiry received",
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            500, "Could not save enquiry"
        )

    finally:
        db.close()
