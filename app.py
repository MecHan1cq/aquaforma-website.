import os
import re
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email_validator import validate_email, EmailNotValidError
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import httpx
from fastapi import (
    FastAPI, HTTPException, Depends, UploadFile, File, Form, Request,
    status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import (
    create_engine, String, Text, Integer, DateTime, Boolean, ForeignKey,
    LargeBinary, select, desc, inspect, text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aquaforma.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

app = FastAPI(title="AquaForma API", version="2.0.0")
origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in origins else origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Stripe-Signature"],
)

MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(25 * 1024 * 1024)))
MAX_APPLICATION_UPLOAD_BYTES = int(os.getenv("MAX_APPLICATION_UPLOAD_BYTES", str(50 * 1024 * 1024)))
ALLOWED_UPLOAD_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif",
    "video/mp4", "video/quicktime", "video/webm", "application/pdf",
}
STRIPE_MAX_ONLINE_AMOUNT_CENTS = int(os.getenv("STRIPE_MAX_ONLINE_AMOUNT_CENTS", "50000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://aquaforma-site.onrender.com").rstrip("/")
GROUP_COURSE_PRICE_CENTS = int(os.getenv("GROUP_COURSE_PRICE_EUR", "2500")) * 100
PRIVATE_COURSE_PRICE_CENTS = int(os.getenv("PRIVATE_COURSE_PRICE_EUR", "5000")) * 100

try:
    import stripe
except ImportError:  # Stripe remains optional until keys are configured.
    stripe = None

# ---------------------------------------------------------------------------
# Database models
# ---------------------------------------------------------------------------
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
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class WaterfallApplication(Base):
    __tablename__ = "waterfall_applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(60), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    country_city: Mapped[str] = mapped_column(String(180), nullable=False)
    investor_type: Mapped[str] = mapped_column(String(60), nullable=False)
    location_type: Mapped[str] = mapped_column(String(40), nullable=False)
    waterfall_type: Mapped[str] = mapped_column(String(60), nullable=False)
    budget: Mapped[str] = mapped_column(String(60), nullable=False)
    timeline: Mapped[str] = mapped_column(String(60), nullable=False)
    additional_info: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Consultation(Base):
    __tablename__ = "consultations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class StoredFile(Base):
    __tablename__ = "stored_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[Optional[int]] = mapped_column(ForeignKey("waterfall_applications.id"), nullable=True, index=True)
    consultation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("consultations.id"), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    course: Mapped[str] = mapped_column(String(80), nullable=False)
    course_format: Mapped[str] = mapped_column(String(20), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="invoice_requested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class InvoiceRequest(Base):
    __tablename__ = "invoice_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(180), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    amount_total: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    customer_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(engine)
# Backwards-compatible migration for databases created by the previous version.
with engine.begin() as connection:
    if "enquiries" in inspect(engine).get_table_names():
        enquiry_columns = {column["name"] for column in inspect(engine).get_columns("enquiries")}
        if "status" not in enquiry_columns:
            connection.execute(text("ALTER TABLE enquiries ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'new'"))

# ---------------------------------------------------------------------------
# Schemas and helpers
# ---------------------------------------------------------------------------
class Contact(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    country: str = Field(default="", max_length=160)
    project_type: str = Field(min_length=2, max_length=80)
    message: str = Field(min_length=10, max_length=5000)
    language: str = Field(default="en", pattern="^(ru|pl|en|de|fr|lt)$")

    @field_validator("name", "country", "project_type", "message", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class CourseRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(default="", max_length=60)
    course: str = Field(pattern="^(flowerbeds|alpine-gardens)$")
    course_format: str = Field(pattern="^(group|private)$")
    message: str = Field(default="", max_length=3000)


class InvoiceRequestCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str = Field(min_length=2, max_length=180)
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(default="", max_length=60)
    quantity: int = Field(default=1, ge=1, le=100)
    message: str = Field(default="", max_length=3000)


class CheckoutRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=10)
    email: EmailStr


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=4000)
    price_eur: float = Field(gt=0, le=1000000)
    active: bool = True


class ProductUpdate(BaseModel):
    active: Optional[bool] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=4000)
    price_eur: Optional[float] = Field(default=None, gt=0, le=1000000)


class StatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=30)


security = HTTPBasic(auto_error=False)


def require_admin(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> str:
    expected_user = os.getenv("ADMIN_USERNAME", "").strip()
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    if not expected_user or not expected_password:
        raise HTTPException(status_code=503, detail="Admin access is not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD.")
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin login required",
            headers={"WWW-Authenticate": "Basic"},
        )
    valid_user = secrets.compare_digest(credentials.username.encode("utf-8"), expected_user.encode("utf-8"))
    valid_password = secrets.compare_digest(credentials.password.encode("utf-8"), expected_password.encode("utf-8"))
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def clean_email(value: str) -> str:
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError:
        raise HTTPException(status_code=422, detail="Please enter a valid email address")


def safe_filename(name: str) -> str:
    base = Path(name or "upload").name
    base = re.sub(r"[^A-Za-z0-9._() -]", "_", base).strip(" .")
    return (base or "upload")[:250]


def validate_required(value: str, field: str, max_len: int = 300) -> str:
    value = (value or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail=f"{field} is required")
    if len(value) > max_len:
        raise HTTPException(status_code=422, detail=f"{field} is too long")
    return value


def serialize_file(row: StoredFile) -> dict:
    return {
        "id": row.id,
        "filename": row.original_filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "created_at": row.created_at.isoformat(),
        "download_url": f"/api/admin/files/{row.id}",
    }


def serialize_application(row: WaterfallApplication, files: list[StoredFile]) -> dict:
    return {
        "id": row.id, "first_name": row.first_name, "last_name": row.last_name,
        "email": row.email, "phone": row.phone, "address": row.address,
        "country_city": row.country_city, "investor_type": row.investor_type,
        "location_type": row.location_type, "waterfall_type": row.waterfall_type,
        "budget": row.budget, "timeline": row.timeline,
        "additional_info": row.additional_info, "status": row.status,
        "created_at": row.created_at.isoformat(),
        "files": [serialize_file(f) for f in files],
    }


def notify_telegram(item: Contact, enquiry_id: int) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    body = (
        f"New website enquiry #{enquiry_id}\nName: {item.name}\nEmail: {item.email}\n"
        f"Location: {item.country or 'Not provided'}\nType: {item.project_type}\n"
        f"Language: {item.language}\nMessage: {item.message}"
    )
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": body}, timeout=8.0,
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"Telegram notification failed for enquiry #{enquiry_id}: {type(exc).__name__}")


def notify_email(item: Contact, enquiry_id: int) -> None:
    host, user, password, recipient = (
        os.getenv(k, "").strip() for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO")
    )
    if not all((host, user, password, recipient)):
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Website enquiry #{enquiry_id}"
        msg["From"] = os.getenv("MAIL_FROM", user).strip() or user
        msg["To"] = recipient
        msg.set_content(
            f"Name: {item.name}\nEmail: {item.email}\nLocation: {item.country or 'Not provided'}\n"
            f"Project type: {item.project_type}\nLanguage: {item.language}\n\n{item.message}"
        )
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
    except Exception as exc:
        print(f"Email notification failed for enquiry #{enquiry_id}: {type(exc).__name__}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
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
        row = Enquiry(
            name=payload.name, email=str(payload.email), country=payload.country,
            project_type=payload.project_type, message=payload.message, language=payload.language,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        enquiry_id = row.id
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save enquiry")
    finally:
        db.close()
    notify_telegram(payload, enquiry_id)
    notify_email(payload, enquiry_id)
    return {"ok": True, "id": enquiry_id, "message": "Enquiry received"}


@app.post("/api/applications", status_code=201)
async def create_application(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    country_city: str = Form(...),
    investor_type: str = Form(...),
    location_type: str = Form(...),
    waterfall_type: str = Form(...),
    budget: str = Form(...),
    timeline: str = Form(...),
    additional_info: str = Form(default=""),
    files: Optional[list[UploadFile]] = File(default=None),
):
    first_name = validate_required(first_name, "First name", 100)
    last_name = validate_required(last_name, "Last name", 100)
    phone = validate_required(phone, "Phone / WhatsApp", 60)
    address = validate_required(address, "Address", 300)
    country_city = validate_required(country_city, "Country / city", 180)
    email = clean_email(email)
    allowed = {
        "investor_type": {"Property owner", "Direct investor"},
        "location_type": {"Indoor", "Outdoor", "Both"},
        "waterfall_type": {"Mobile waterfall", "Permanent waterfall", "Custom-designed waterfall", "Not sure yet"},
        "budget": {"€3,000–5,000", "€5,000–15,000", "€15,000–30,000", "€30,000–50,000", "€50,000–100,000", "€100,000–250,000", "€250,000+"},
        "timeline": {"Immediately", "Within 3–6 months", "Within 6–12 months", "Future project"},
    }
    values = {
        "investor_type": investor_type, "location_type": location_type,
        "waterfall_type": waterfall_type, "budget": budget, "timeline": timeline,
    }
    for key, value in values.items():
        if value not in allowed[key]:
            raise HTTPException(status_code=422, detail=f"Invalid value for {key}")

    prepared_files = []
    total_size = 0
    for upload in files or []:
        if not upload.filename:
            continue
        content_type = (upload.content_type or "application/octet-stream").lower()
        if content_type not in ALLOWED_UPLOAD_TYPES:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {safe_filename(upload.filename)}")
        data = await upload.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_BYTES // (1024 * 1024)} MB")
        total_size += len(data)
        if total_size > MAX_APPLICATION_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Combined upload size is too large")
        prepared_files.append((safe_filename(upload.filename), content_type, data))

    db = Session()
    try:
        row = WaterfallApplication(
            first_name=first_name, last_name=last_name, email=email, phone=phone,
            address=address, country_city=country_city, investor_type=investor_type,
            location_type=location_type, waterfall_type=waterfall_type, budget=budget,
            timeline=timeline, additional_info=(additional_info or "").strip()[:10000],
        )
        db.add(row)
        db.flush()
        for filename, content_type, data in prepared_files:
            db.add(StoredFile(
                application_id=row.id, original_filename=filename,
                content_type=content_type, size_bytes=len(data), data=data,
            ))
        db.commit()
        application_id = row.id
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save application")
    finally:
        db.close()
    return {"ok": True, "id": application_id, "message": "Application received"}


@app.get("/api/courses")
def get_courses():
    return {
        "currency": "EUR",
        "courses": [
            {"id": "flowerbeds", "name": "Flowerbeds", "description": "Planning, planting and designing expressive flowerbeds.", "group_price_cents": GROUP_COURSE_PRICE_CENTS, "private_price_cents": PRIVATE_COURSE_PRICE_CENTS},
            {"id": "alpine-gardens", "name": "Alpine Gardens", "description": "Designing alpine gardens, rock gardens and natural stone compositions.", "group_price_cents": GROUP_COURSE_PRICE_CENTS, "private_price_cents": PRIVATE_COURSE_PRICE_CENTS},
        ],
    }


@app.post("/api/courses/enroll", status_code=201)
def enroll_course(payload: CourseRequest):
    price = GROUP_COURSE_PRICE_CENTS if payload.course_format == "group" else PRIVATE_COURSE_PRICE_CENTS
    db = Session()
    try:
        row = CourseEnrollment(
            name=payload.name.strip(), email=str(payload.email), phone=payload.phone.strip(),
            course=payload.course, course_format=payload.course_format,
            price_cents=price, message=payload.message.strip(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        enrollment_id = row.id
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save course request")
    finally:
        db.close()
    return {"ok": True, "id": enrollment_id, "message": "Course request received. The team will contact you with invoice details."}


@app.get("/api/products")
def get_products():
    db = Session()
    try:
        rows = db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all()
        return {
            "stripe_enabled": bool(
                os.getenv("STRIPE_SECRET_KEY", "").strip()
                and os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
                and stripe
            ),
            "online_payment_limit_cents": STRIPE_MAX_ONLINE_AMOUNT_CENTS,
            "products": [
                {"id": p.id, "name": p.name, "description": p.description,
                 "price_cents": p.price_cents, "currency": p.currency}
                for p in rows
            ],
        }
    finally:
        db.close()


@app.post("/api/products/{product_id}/checkout")
def create_product_checkout(product_id: int, payload: CheckoutRequest):
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret_key or not webhook_secret or stripe is None:
        raise HTTPException(status_code=503, detail="Online payments are not fully configured yet")
    db = Session()
    try:
        product = db.get(Product, product_id)
        if not product or not product.active:
            raise HTTPException(status_code=404, detail="Product not found")
        amount = product.price_cents * payload.quantity
        if amount > STRIPE_MAX_ONLINE_AMOUNT_CENTS:
            raise HTTPException(status_code=409, detail={
                "code": "invoice_required",
                "message": "This order is above the online payment limit. Please request an invoice.",
            })
        payment = Payment(
            product_id=product.id, amount_total=amount, currency=product.currency,
            customer_email=str(payload.email), status="pending",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        try:
            stripe.api_key = secret_key
            session_obj = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": product.currency.lower(),
                        "product_data": {"name": product.name, "description": product.description[:500]},
                        "unit_amount": product.price_cents,
                    },
                    "quantity": payload.quantity,
                }],
                customer_email=str(payload.email),
                success_url=f"{FRONTEND_URL}/products.html?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{FRONTEND_URL}/products.html?payment=cancelled",
                metadata={"payment_id": str(payment.id), "product_id": str(product.id)},
            )
            payment.stripe_session_id = session_obj.id
            db.commit()
            return {"ok": True, "checkout_url": session_obj.url}
        except Exception as exc:
            payment.status = "checkout_error"
            db.commit()
            print(f"Stripe checkout creation failed: {type(exc).__name__}")
            raise HTTPException(status_code=502, detail="Could not start checkout. Please try again later.")
    finally:
        db.close()


@app.post("/api/invoice-requests", status_code=201)
def create_invoice_request(payload: InvoiceRequestCreate):
    db = Session()
    try:
        product_id = payload.product_id
        if product_id is not None:
            product = db.get(Product, product_id)
            if not product or not product.active:
                raise HTTPException(status_code=404, detail="Product not found")
        row = InvoiceRequest(
            product_id=product_id, product_name=payload.product_name.strip(),
            name=payload.name.strip(), email=str(payload.email), phone=payload.phone.strip(),
            quantity=payload.quantity, message=payload.message.strip(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        request_id = row.id
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save invoice request")
    finally:
        db.close()
    return {"ok": True, "id": request_id, "message": "Invoice request received"}


@app.post("/api/consultations", status_code=201)
async def create_consultation(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(default=""),
    question: str = Form(...),
    file: Optional[UploadFile] = File(default=None),
):
    name = validate_required(name, "Name", 160)
    email = clean_email(email)
    question = validate_required(question, "Question", 10000)
    phone = (phone or "").strip()[:60]
    file_data = None
    file_info = None
    if file and file.filename:
        content_type = (file.content_type or "application/octet-stream").lower()
        if content_type not in ALLOWED_UPLOAD_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported attachment type")
        file_data = await file.read(MAX_FILE_BYTES + 1)
        if len(file_data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_BYTES // (1024 * 1024)} MB")
        file_info = (safe_filename(file.filename), content_type, file_data)

    db = Session()
    try:
        row = Consultation(name=name, email=email, phone=phone, question=question)
        db.add(row)
        db.flush()
        if file_info:
            filename, content_type, data = file_info
            db.add(StoredFile(
                consultation_id=row.id, original_filename=filename,
                content_type=content_type, size_bytes=len(data), data=data,
            ))
        db.commit()
        consultation_id = row.id
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save consultation")
    finally:
        db.close()
    return {"ok": True, "id": consultation_id, "message": "Consultation request received"}


# ---------------------------------------------------------------------------
# Stripe webhook (payment status is changed only after Stripe confirms it)
# ---------------------------------------------------------------------------
@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret or stripe is None:
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured")
    body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(body, signature, webhook_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")

    event_type = event.get("type", "")
    session_obj = event.get("data", {}).get("object", {})
    session_id = session_obj.get("id")
    if session_id:
        db = Session()
        try:
            payment = db.scalar(select(Payment).where(Payment.stripe_session_id == session_id))
            if payment:
                if event_type == "checkout.session.completed" and session_obj.get("payment_status") == "paid":
                    payment.status = "paid"
                elif event_type in {"checkout.session.async_payment_failed", "checkout.session.expired"}:
                    payment.status = "failed" if event_type.endswith("failed") else "expired"
                db.commit()
        finally:
            db.close()
    return {"received": True}


# ---------------------------------------------------------------------------
# Admin API — every endpoint below requires HTTP Basic authentication.
# ---------------------------------------------------------------------------
@app.get("/api/admin/verify")
def admin_verify(admin: str = Depends(require_admin)):
    return {"ok": True, "username": admin}


@app.get("/api/admin/overview")
def admin_overview(admin: str = Depends(require_admin)):
    db = Session()
    try:
        applications = db.scalars(select(WaterfallApplication).order_by(desc(WaterfallApplication.created_at)).limit(200)).all()
        consultations = db.scalars(select(Consultation).order_by(desc(Consultation.created_at)).limit(200)).all()
        courses = db.scalars(select(CourseEnrollment).order_by(desc(CourseEnrollment.created_at)).limit(200)).all()
        products = db.scalars(select(Product).order_by(desc(Product.created_at)).limit(200)).all()
        invoices = db.scalars(select(InvoiceRequest).order_by(desc(InvoiceRequest.created_at)).limit(200)).all()
        payments = db.scalars(select(Payment).order_by(desc(Payment.created_at)).limit(200)).all()
        enquiries = db.scalars(select(Enquiry).order_by(desc(Enquiry.created_at)).limit(200)).all()
        app_files = {}
        consult_files = {}
        all_files = db.execute(select(
            StoredFile.id, StoredFile.application_id, StoredFile.consultation_id,
            StoredFile.original_filename, StoredFile.content_type, StoredFile.size_bytes,
            StoredFile.created_at
        ).order_by(StoredFile.id)).all()
        for file_row in all_files:
            file_meta = SimpleNamespace(**file_row._mapping)
            if file_meta.application_id:
                app_files.setdefault(file_meta.application_id, []).append(file_meta)
            if file_meta.consultation_id:
                consult_files.setdefault(file_meta.consultation_id, []).append(file_meta)
        return {
            "applications": [serialize_application(x, app_files.get(x.id, [])) for x in applications],
            "consultations": [{
                "id": x.id, "name": x.name, "email": x.email, "phone": x.phone,
                "question": x.question, "status": x.status, "created_at": x.created_at.isoformat(),
                "files": [serialize_file(f) for f in consult_files.get(x.id, [])],
            } for x in consultations],
            "courses": [{
                "id": x.id, "name": x.name, "email": x.email, "phone": x.phone,
                "course": x.course, "course_format": x.course_format,
                "price_cents": x.price_cents, "currency": x.currency, "message": x.message,
                "status": x.status, "created_at": x.created_at.isoformat(),
            } for x in courses],
            "products": [{
                "id": x.id, "name": x.name, "description": x.description,
                "price_cents": x.price_cents, "currency": x.currency, "active": x.active,
                "created_at": x.created_at.isoformat(),
            } for x in products],
            "invoice_requests": [{
                "id": x.id, "product_id": x.product_id, "product_name": x.product_name,
                "name": x.name, "email": x.email, "phone": x.phone, "quantity": x.quantity,
                "message": x.message, "status": x.status, "created_at": x.created_at.isoformat(),
            } for x in invoices],
            "payments": [{
                "id": x.id, "product_id": x.product_id, "amount_total": x.amount_total,
                "currency": x.currency, "customer_email": x.customer_email,
                "status": x.status, "created_at": x.created_at.isoformat(),
            } for x in payments],
            "enquiries": [{
                "id": x.id, "name": x.name, "email": x.email, "country": x.country,
                "project_type": x.project_type, "message": x.message, "language": x.language,
                "status": x.status, "created_at": x.created_at.isoformat(),
            } for x in enquiries],
        }
    finally:
        db.close()


@app.get("/api/admin/files/{file_id}")
def admin_download_file(file_id: int, admin: str = Depends(require_admin)):
    db = Session()
    try:
        row = db.get(StoredFile, file_id)
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        filename = row.original_filename.replace('"', "")
        return StreamingResponse(
            BytesIO(row.data),
            media_type=row.content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


@app.patch("/api/admin/status/{resource}/{record_id}")
def admin_update_status(
    resource: str, record_id: int, payload: StatusUpdate,
    admin: str = Depends(require_admin),
):
    models = {
        "applications": WaterfallApplication, "consultations": Consultation,
        "courses": CourseEnrollment, "invoice-requests": InvoiceRequest,
        "enquiries": Enquiry,
    }
    model = models.get(resource)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown resource")
    allowed_statuses = {"new", "in_progress", "contacted", "completed", "closed", "invoice_requested", "paid", "cancelled"}
    if payload.status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Invalid status")
    db = Session()
    try:
        row = db.get(model, record_id)
        if not row:
            raise HTTPException(status_code=404, detail="Record not found")
        row.status = payload.status
        db.commit()
        return {"ok": True, "id": record_id, "status": payload.status}
    finally:
        db.close()


@app.post("/api/admin/products", status_code=201)
def admin_create_product(payload: ProductCreate, admin: str = Depends(require_admin)):
    db = Session()
    try:
        row = Product(
            name=payload.name.strip(), description=payload.description.strip(),
            price_cents=round(payload.price_eur * 100), currency="EUR", active=payload.active,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "id": row.id}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create product")
    finally:
        db.close()


@app.patch("/api/admin/products/{product_id}")
def admin_update_product(product_id: int, payload: ProductUpdate, admin: str = Depends(require_admin)):
    db = Session()
    try:
        row = db.get(Product, product_id)
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            row.name = data["name"].strip()
        if "description" in data and data["description"] is not None:
            row.description = data["description"].strip()
        if "price_eur" in data and data["price_eur"] is not None:
            row.price_cents = round(data["price_eur"] * 100)
        if "active" in data and data["active"] is not None:
            row.active = data["active"]
        db.commit()
        return {"ok": True, "id": row.id}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
