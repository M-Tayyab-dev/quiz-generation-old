"""Create a source-only upload bundle; never include secrets or model weights."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
files = []
for folder in ("ai_quiz_agent", "tests", "training", "scripts", "examples", "docs"):
    files.extend(p for p in (root/folder).rglob("*") if p.is_file()
                 and not any(x in {"__pycache__", ".ipynb_checkpoints", ".dart_tool", "build"} for x in p.parts)
                 and p.name != ".env" and p.suffix in {".py", ".txt", ".md", ".jsonl", ".example", ".mmd", ".dart", ".yaml", ".lock", ".ps1", ".cmd", ".pdf", ".docx"})
files.extend(root.glob("*.md"))
files.extend(root.glob("requirements*.txt"))
files.append(root/".gitignore")
with ZipFile(root/"quiz-project-current.zip", "w", ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        archive.write(path, path.relative_to(root).as_posix())
print(f"Packaged {len(set(files))} files")
