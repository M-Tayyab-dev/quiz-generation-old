"""Save and verify a local source snapshot, including the supplied Flutter app."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
destination = root / 'backups'
destination.mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive_path = destination / f'quiz-ai-and-flutter-{stamp}.zip'
excluded_dirs = {'.git', '.venv', '.dart_tool', '.idea', '__pycache__',
                 '.ipynb_checkpoints', 'build', 'backups', 'node_modules',
                 '.gradle', 'ephemeral', 'Pods', '.symlinks', '.local', 'handwritten'}
excluded_names = {'.env', 'local.properties', 'key.properties',
                  '.flutter-plugins-dependencies', 'Quiz_AI_Module_before_cleanup.ipynb',
                  'colab-status.png', 'colab-upload.png'}
files = []
for path in root.rglob('*'):
    relative = path.relative_to(root)
    if not path.is_file() or path.is_symlink():
        continue
    if any(part in excluded_dirs for part in relative.parts):
        continue
    if path.name in excluded_names or path.name.startswith('.env.') and path.name != '.env.example':
        continue
    if path.suffix.lower() in {'.zip', '.pyc', '.jks', '.keystore', '.lnk'}:
        continue
    files.append(path)
git_status = subprocess.run(['git', '-C', str(root/'flutter project'), 'status', '--short', '--branch'],
                            capture_output=True, text=True, check=True).stdout
manifest = {'created_utc': stamp, 'archive': archive_path.name,
            'flutter_git_status': git_status, 'scope': 'Local source snapshot; excludes Git history and caches.',
            'files': {}}
with ZipFile(archive_path, 'x', ZIP_DEFLATED) as archive:
    for path in sorted(files):
        name = path.relative_to(root).as_posix()
        data = path.read_bytes()
        archive.writestr(name, data)
        manifest['files'][name] = hashlib.sha256(data).hexdigest()
    archive.writestr('SNAPSHOT_MANIFEST.json', json.dumps(manifest, indent=2))
with ZipFile(archive_path) as archive:
    assert archive.testzip() is None, 'Archive integrity failed'
    for name, digest in manifest['files'].items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest, name
    assert 'flutter project/pubspec.yaml' in archive.namelist()
    assert 'ai_quiz_agent/api/app.py' in archive.namelist()
manifest_path = archive_path.with_suffix('.json')
manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'archive': str(archive_path), 'files_verified': len(files),
                  'bytes': archive_path.stat().st_size, 'manifest': str(manifest_path)}, indent=2))
