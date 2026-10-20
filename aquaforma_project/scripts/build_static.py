from pathlib import Path
import os,shutil
r=Path(__file__).resolve().parents[1];src=r/"frontend";dst=src/"dist"
shutil.rmtree(dst,ignore_errors=True);dst.mkdir(parents=True)
for n in ("index.html","styles.css","script.js"):shutil.copy2(src/n,dst/n)
shutil.copytree(src/"images",dst/"images",dirs_exist_ok=True)
url=os.getenv("API_BASE_URL","").strip().rstrip("/")
if not url:raise SystemExit("Set API_BASE_URL to the deployed API URL")
p=dst/"script.js";p.write_text(p.read_text().replace(chr(34)+"__API_BASE_URL__"+chr(34),repr(url)))
print("Static build ready; API:",url)
