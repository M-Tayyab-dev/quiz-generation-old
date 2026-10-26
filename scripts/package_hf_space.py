"""Package Hugging Face Space deployment bundle."""
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
hf_dir = root / "hf_space"
src_agent = root / "ai_quiz_agent"
dst_agent = hf_dir / "ai_quiz_agent"

# Copy latest ai_quiz_agent to hf_space/
if dst_agent.exists():
    shutil.rmtree(dst_agent)
shutil.copytree(src_agent, dst_agent, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.sqlite3"))

# Build zip for easy 1-click upload
zip_path = root / "hf-space-deployment.zip"
with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
    for path in sorted(hf_dir.rglob("*")):
        if path.is_file() and not any(part in {"__pycache__", ".git"} for part in path.parts):
            archive.write(path, path.relative_to(hf_dir).as_posix())

print(f"Hugging Face Space packaged: {zip_path.name} ({zip_path.stat().st_size / 1024:.1f} KB)")
