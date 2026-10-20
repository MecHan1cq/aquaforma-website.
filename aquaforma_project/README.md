# AquaForma full-stack website
Responsive multilingual site (RU/PL/EN/DE), FastAPI backend, PostgreSQL and Render Blueprint.

## Structure
- `frontend/index.html` — page structure
- `frontend/styles.css` — responsive styles
- `frontend/script.js` — language switcher, hamburger menu and API form
- `frontend/images/` — add licensed client photos here
- `backend/app.py` — API and PostgreSQL/SQLite data model
- `backend/requirements.txt` — dependencies
- `scripts/build_static.py` — static build and API URL injection
- `render.yaml` — Render resources

## Deploy
1. Create a GitHub account and an empty repository. Extract this ZIP and upload all project files (including `render.yaml`) to the repository.
2. In Render Dashboard select New + → Blueprint, connect the GitHub repository and deploy `render.yaml`.
3. Render creates API, static site and PostgreSQL. Confirm the actual API public URL; if it differs from `https://aquaforma-api.onrender.com`, update the static service `API_BASE_URL` and redeploy.
4. Set API `ALLOWED_ORIGINS` to the exact published static-site URL (instead of `*`) and redeploy.
5. Test API `/health`, submit a test enquiry on the site, then verify it is in the database table `enquiries`.

## Local API test
Python 3.11+: `cd backend`, `python -m venv .venv`, activate it, `pip install -r requirements.txt`, then `uvicorn app:app --reload`. Local default database is SQLite. API docs at `http://127.0.0.1:8000/docs`. For frontend local testing, set `API_BASE_URL` in `frontend/script.js` to `http://127.0.0.1:8000` or use the build script with `API_BASE_URL=http://127.0.0.1:8000`.

## Before launch
Replace demo business name, email, placeholder contact details and illustrative stock images. Form submissions are saved to PostgreSQL, but email notifications are not configured yet. Add a notification provider if the client wants email alerts. Add legal/privacy pages, spam protection, rate limiting, monitoring and backups before production. Check current Render Blueprint syntax/pricing in the dashboard before provisioning resources.
