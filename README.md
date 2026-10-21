# AquaForma — full-stack website

Responsive multilingual website with a flat project root, FastAPI backend, PostgreSQL persistence and optional Telegram/email notifications. Existing brand text remains AquaForma until the client confirms a final name.

## Project structure

- `index.html`, `styles.css`, `script.js` — static website files in the repository root
- `app.py`, `requirements.txt` — Python API in the repository root
- `assets/` — local image assets referenced directly from HTML
- `scripts/build_static.py` — builds the static publish directory and injects the API URL
- `render.yaml` — Render Blueprint for Static Site, API Web Service and PostgreSQL

## Deploy on Render

1. Upload the contents of this project to the root of a GitHub repository (do not upload the outer ZIP folder).
2. In Render, choose **New + → Blueprint** and select the repository containing `render.yaml`.
3. Confirm the API service URL and set the Static Site `API_BASE_URL` to that exact URL with `https://`.
4. Set the API service `ALLOWED_ORIGINS` to the exact Static Site URL (including `https://`, no trailing slash) after the static site has been created. Do not leave `*` for production.
5. Add optional notification environment variables to the API service:
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
   - `SMTP_HOST`, `SMTP_PORT` (usually `587`), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO`; optional `MAIL_FROM`
6. Wait for redeploy, test `/health`, then submit a test enquiry. Verify the enquiry is stored in PostgreSQL and notification arrives.
7. Connect the client's purchased domain in the Static Site settings and follow the DNS instructions shown by Render.

## Notes

- No real Telegram token or mail credentials are included in source code.
- Enquiries are saved before notifications are attempted; notification failures do not delete a saved enquiry. Check API logs for notification failures.
- Current photos were not included in the source archive, so `assets/` contains local SVG illustration assets rather than remote photo URLs. Replace them with licensed client photos when available.
- Before production, confirm company name/contact details, add privacy/legal pages, anti-spam/rate limiting, monitoring and database backups.
- The provided API has no admin dashboard yet; this source project did not include one.
