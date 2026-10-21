from pathlib import Path
import os, shutil
root = Path(__file__).resolve().parents[1]
dist = root / "dist"
shutil.rmtree(dist, ignore_errors=True)
dist.mkdir(parents=True)
for name in ("index.html", "styles.css", "script.js"):
    shutil.copy2(root / name, dist / name)
shutil.copytree(root / "assets", dist / "assets", dirs_exist_ok=True)
url = os.getenv("API_BASE_URL", "").strip().rstrip("/")
if not url:
    raise SystemExit("Set API_BASE_URL to the deployed API URL")
script = dist / "script.js"
script.write_text(script.read_text().replace('"__API_BASE_URL__"', repr(url)))
print("Static build ready; API:", url)
