# AquaForma — client platform

AquaForma is a multilingual water-architecture website with a client portal, FastAPI backend and PostgreSQL database. The root of this folder is the deployable project. Older nested copies and ZIP archives are retained as source backups; Render uses the root files described below.

## What is included

The main landing page retains its RU / PL / EN / DE / FR language switcher. The new client-portal pages currently use English, matching the supplied Waterfall Project questionnaire.

### Public website
- Existing AquaForma landing page, services, video and visual project section.
- A new explanation section: why a waterfall can add well-being, architectural, property and commercial value.
- Portfolio page with the supplied local reference images.
- Dedicated client pages:
  - `application.html` — private owner / investor waterfall application.
  - `courses.html` — Flowerbeds and Alpine Gardens, group and private formats.
  - `products.html` — product catalogue, small online payments and invoice requests.
  - `consultation.html` — questions with an optional file attachment.

### Client records and database
- Project applications store first name, last name, email, phone / WhatsApp, street address, country / city, five project answers and optional additional information.
- Project photos, videos and PDFs are stored as binary attachments in the database and shown in the admin dashboard.
- Consultation questions and their optional attachment are saved in the database.
- Course enrolment requests, products, invoice requests and Stripe payment records are saved in the database.
- The existing general contact form and `enquiries` table are retained. A small startup migration adds the new `status` column to an existing database if needed.

### Admin dashboard
- Open `/admin.html` on the deployed website.
- Sign in with `ADMIN_USERNAME` and `ADMIN_PASSWORD` configured on the API service.
- Review project applications, attachments, consultations, course requests, products, invoice requests, payments and general enquiries.
- Update request statuses, download attachments and add / hide products.
- Admin API endpoints require HTTP Basic authentication and should only be used over HTTPS.

### Course prices
The current defaults are:
- Group course: **€2,500 per person**
- Private course: **€5,000**

These values can be changed with `GROUP_COURSE_PRICE_EUR` and `PRIVATE_COURSE_PRICE_EUR` environment variables.

### Stripe and invoices
- Stripe Checkout is prepared for products only.
- The default online payment limit is **€500 per checkout** (`STRIPE_MAX_ONLINE_AMOUNT_CENTS=50000`). This is a configurable starting threshold; change it to the business-approved limit.
- Orders above the online limit are routed to an invoice request.
- Course enrolments are requests for availability and invoice details, not automatic Stripe charges.
- Stripe stays unavailable until real `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` values are configured.
- The webhook endpoint is `/api/stripe/webhook`. Configure Stripe to send `checkout.session.completed`, `checkout.session.async_payment_failed` and `checkout.session.expired` events to that endpoint.
- A payment is marked as paid only after a valid Stripe webhook confirms it. The website does not simulate successful payments.

## Project structure

- `index.html`, `styles.css`, `script.js` — main website
- `application.html`, `courses.html`, `products.html`, `consultation.html`, `portfolio.html`, `admin.html` — portal pages
- `application.js`, `courses.js`, `products.js`, `consultation.js`, `admin.js` — page behaviour
- `assets/` — images, videos and illustrations
- `app.py` — FastAPI API, database models, upload handling, admin endpoints and Stripe integration
- `requirements.txt` — Python dependencies
- `scripts/build_static.py` — builds the static website and injects the API URL
- `render.yaml` — Render Blueprint

## Deploy with Render

1. Upload the **contents of this root folder** to the root of a GitHub repository. Do not upload the entire parent folder as an extra nested directory.
2. In Render, choose **New + → Blueprint**, connect the repository and deploy the `render.yaml` Blueprint.
3. Confirm the API and static-site URLs assigned by Render. If they differ from the example URLs in `render.yaml`, update:
   - API service `ALLOWED_ORIGINS` to the exact static-site URL (no trailing slash).
   - Static service `API_BASE_URL` to the API URL.
   - API service `FRONTEND_URL` to the static-site URL.
4. In the API service's **Environment** settings, set:
   - `ADMIN_USERNAME` — your private administrator username.
   - `ADMIN_PASSWORD` — a long, unique password. Do not put it in GitHub or frontend files.
5. When Stripe credentials are available, set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in the API service's private Environment settings. Until then, the shop can collect invoice requests but cannot take card payments.
6. Deploy both services. Test `https://YOUR-API-URL/health`; it should report `healthy` and `database: connected`.
7. Open the website and test a project application, a consultation with an attachment, a course request and an invoice request. Confirm each record appears in `/admin.html`.
8. Add products from the admin dashboard. The public Products page will show active products.

**Database retention:** Render's free PostgreSQL option is intended for testing and may expire or have limited storage/backup guarantees. Choose a persistent database plan and configure backups before collecting real client data. File attachments are stored in PostgreSQL in this initial implementation, so database capacity and backups matter.

## Local development

Python 3.11+:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Run the API:

```bash
# Windows PowerShell:
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="replace-with-a-long-password"
uvicorn app:app --reload
```

The local database defaults to SQLite (`aquaforma.db`). Open `http://127.0.0.1:8000/docs` for API documentation. For local static-site testing, set `API_BASE_URL` in the frontend JavaScript files to `http://127.0.0.1:8000`, or build with:

```bash
# macOS / Linux:
API_BASE_URL=http://127.0.0.1:8000 python scripts/build_static.py

# Windows PowerShell:
$env:API_BASE_URL="http://127.0.0.1:8000"
python scripts/build_static.py
```

## Upload limits and storage

- Up to 25 MB per file.
- Up to 50 MB total across one project application.
- Consultation attachment: one file up to 25 MB.
- Accepted formats: JPG, PNG, WEBP, GIF, HEIC, HEIF, MP4, MOV, WEBM and PDF.
- Files are stored in the database, not in the temporary web-service filesystem. For a high-volume production portfolio or large video uploads, move binary files to private object storage (for example, S3 or Cloudflare R2) and keep only file metadata in PostgreSQL.

## Before public launch

- Confirm that the supplied portfolio images may be used and label illustrative images accurately. Do not present reference images as completed client projects unless verified.
- Replace placeholder contact details and confirm the business identity.
- Publish a privacy notice and terms appropriate to the business location and target markets. The consent text in the forms is a basic starting point, not a substitute for a reviewed privacy policy.
- Set a persistent database plan, backups, monitoring and anti-spam / rate limiting.
- Set a strong unique admin password. Keep all Stripe and database credentials private.
- Confirm the group / private course prices and the €500 default online payment threshold before accepting orders.
