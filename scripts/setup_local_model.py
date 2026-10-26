"""Download official CPU runtime and quantized Qwen weights into local-only storage."""
import hashlib
import json
from pathlib import Path
import urllib.request
from zipfile import ZipFile

root = Path(__file__).resolve().parent.parent
local = root / '.local'
local.mkdir(exist_ok=True)
runtime_url = 'https://github.com/ggml-org/llama.cpp/releases/download/b11849/llama-b11849-bin-win-cpu-x64.zip'
model_url = 'https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/7dabda4d13d513e3e842b20f0d435c732f172cbe/qwen2.5-3b-instruct-q4_k_m.gguf'

def download(url, target):
    if target.exists():
        print('Already present:', target.name, flush=True)
        return
    partial = target.with_suffix(target.suffix + '.partial')
    with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as out:
        length = int(response.headers.get('Content-Length', 0))
        received, milestone = 0, 0
        while chunk := response.read(4 * 1024 * 1024):
            out.write(chunk)
            received += len(chunk)
            if received // (128 * 1024 * 1024) > milestone:
                milestone = received // (128 * 1024 * 1024)
                print(f'{target.name}: {received // 1048576} MB downloaded', flush=True)
        if length and received != length:
            raise RuntimeError('Download size mismatch')
    partial.rename(target)
    print('Downloaded:', target.name, flush=True)

archive_path = local / 'llama-cpu.zip'
download(runtime_url, archive_path)
with urllib.request.urlopen('https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11849', timeout=60) as response:
    release = json.load(response)
asset = next(a for a in release['assets'] if a['browser_download_url'] == runtime_url)
digest = asset.get('digest')
if digest and digest.startswith('sha256:'):
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == digest.split(':')[1], 'Runtime checksum mismatch'
with ZipFile(archive_path) as archive:
    target = (local/'llama').resolve()
    assert archive.testzip() is None
    assert all((target/name).resolve().is_relative_to(target) for name in archive.namelist())
    archive.extractall(target)
model = local/'qwen2.5-3b-instruct-q4_k_m.gguf'
download(model_url, model)
with model.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == '626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d', 'Model checksum mismatch'
with model.open('rb') as stream:
    assert stream.read(4) == b'GGUF', 'Unexpected model format'
(local/'model-sources.json').write_text(json.dumps({'runtime':runtime_url, 'runtime_digest':digest,
    'model':model_url, 'model_bytes':model.stat().st_size}, indent=2))
print('Local CPU model ready. Training still runs separately in Colab.', flush=True)
