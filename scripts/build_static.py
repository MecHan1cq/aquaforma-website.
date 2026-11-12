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

for source in ROOT.glob("*.html"):
    shutil.copy2(source, DIST / source.name)
for source in ROOT.glob("*.css"):
    shutil.copy2(source, DIST / source.name)
for source in ROOT.glob("*.js"):
    target = DIST / source.name
    script = source.read_text(encoding="utf-8").replace('"__API_BASE_URL__"', repr(API_URL))
    if '"__API_BASE_URL__"' in script:
        raise SystemExit(f"API_BASE_URL injection failed in {source.name}")
    target.write_text(script, encoding="utf-8")
shutil.copytree(ASSETS, DIST / "assets", dirs_exist_ok=True)

print(f"Static build ready. API endpoint: {API_URL}")
