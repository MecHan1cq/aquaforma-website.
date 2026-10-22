# AquaForma — full-stack website

Responsive multilingual website with a static frontend, FastAPI backend and PostgreSQL storage. The contact form sends enquiries to the API; the API validates and saves them to the database. Optional Telegram/email notifications can be enabled through environment variables.

## Project structure

- `index.html` — website markup
- `styles.css` — layout and responsive styling
- `script.js` — language switcher, mobile navigation and contact form API call
- `assets/` — local SVG illustrations used by the website
- `app.py` — FastAPI API and database model
- `requirements.txt` — Python dependencies
- `scripts/build_static.py` — creates the static `dist/` directory and injects `API_BASE_URL`
- `render.yaml` — Render Blueprint for the API, static site and PostgreSQL database

## Deploy with Render Blueprint

1. Upload the **contents of this folder** to the root of a GitHub repository. Do not upload a nested copy of the project or another ZIP inside the repository.
2. In Render, select **New + → Blueprint**, connect GitHub and select this repository. Render will read `render.yaml` and propose the API, static site and database.
3. **Database note:** the free PostgreSQL option is intended for testing and may have a limited lifetime. If enquiries must be retained long-term, select a persistent paid database plan in Render and check the current plan limits before confirming deployment.
4. The Blueprint assumes these service URLs: `https://aquaforma-api.onrender.com` and `https://aquaforma-site.onrender.com`. If Render assigns different URLs, update `API_BASE_URL` on the static site to the actual API URL, and `ALLOWED_ORIGINS` on the API to the actual static-site URL (no trailing slash), then redeploy both services.
5. Wait for deployment to finish. Open `https://YOUR-API-URL/health`; it should return JSON with `status: healthy` and `database: connected`.
6. Open the static-site URL and submit a test enquiry. Check the API logs and confirm the record is saved in the PostgreSQL database. Do not put database credentials in frontend files or GitHub.

## Optional notifications

Set these only in the API Web Service's environment settings (never commit secrets):

- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Email: `SMTP_HOST`, `SMTP_PORT` (usually `587`), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO`; optional `MAIL_FROM`

An enquiry is saved before optional notifications are attempted, so a notification failure does not remove the saved enquiry.

## Before production

- Replace the placeholder email/contact details in `index.html` with real business details.
- Replace illustration SVGs with licensed photographs of real projects if available.
- Add a privacy notice and consent text appropriate to the business and the countries where it operates.
- Configure backups and review anti-spam/rate limiting before advertising the site.
- The project currently has no admin dashboard for reading enquiries; use the database/provider tools or add an authenticated admin feature if needed.
