from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ASSETS = ROOT / "assets"
API_URL = os.getenv("API_BASE_URL", "").strip().rstrip("/")

if not API_URL.startswith(("https://", "http://localhost", "http://127.0.0.1")):
    raise SystemExit("Set API_BASE_URL to the deployed API URL (https://...) before building.")

shutil.rmtree(DIST, ignore_errors=True)
DIST.mkdir(parents=True)
for filename in ("index.html", "styles.css", "script.js"):
    shutil.copy2(ROOT / filename, DIST / filename)
shutil.copytree(ASSETS, DIST / "assets", dirs_exist_ok=True)

script_path = DIST / "script.js"
script = script_path.read_text(encoding="utf-8")
script = script.replace('"__API_BASE_URL__"', repr(API_URL))
if '"__API_BASE_URL__"' in script:
    raise SystemExit("API_BASE_URL injection failed; placeholder remains in script.js")
script_path.write_text(script, encoding="utf-8")
print(f"Static build ready. API endpoint: {API_URL}")
