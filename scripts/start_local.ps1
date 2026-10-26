$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localRoot = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Path $localRoot -Force | Out-Null
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$modelPath = Join-Path $localRoot 'qwen2.5-3b-instruct-q4_k_m.gguf'
$server = Get-ChildItem -LiteralPath (Join-Path $localRoot 'llama') -Filter 'llama-server.exe' -Recurse | Select-Object -First 1
if (-not $server -or -not (Test-Path -LiteralPath $modelPath)) {
    throw 'Run .\.venv\Scripts\python.exe scripts/setup_local_model.py first.'
}
$configPath = Join-Path $localRoot 'flutter-web.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    $tokenBytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($tokenBytes)
    $token = ([BitConverter]::ToString($tokenBytes)).Replace('-', '')
    @{QUIZ_API_URL='http://127.0.0.1:8000'; QUIZ_API_TOKEN=$token} | ConvertTo-Json | Set-Content -LiteralPath $configPath
    @{QUIZ_API_URL='http://10.0.2.2:8000'; QUIZ_API_TOKEN=$token} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $localRoot 'flutter-android.json')
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$env:AI_PROVIDER = 'local'
$env:QUIZ_API_TOKEN = $config.QUIZ_API_TOKEN
$env:QUIZ_DB = Join-Path $localRoot 'quiz-data.sqlite3'
$env:LOCAL_MODEL_URL = 'http://127.0.0.1:8081/v1/chat/completions'
$env:QUIZ_CORS_ORIGINS = 'http://localhost:7357,http://127.0.0.1:7357'

function Test-LocalService($url) {
    try { $null = Invoke-RestMethod -Uri $url -TimeoutSec 2; return $true } catch { return $false }
}
if (-not (Test-LocalService 'http://127.0.0.1:8081/health')) {
    # Override malformed escaped newlines in the downloaded GGUF chat metadata.
    $modelProcess = Start-Process -FilePath $server.FullName -ArgumentList @('-m', "`"$modelPath`"", '--host', '127.0.0.1', '--port', '8081', '-c', '4096', '-np', '1', '-t', '4', '-ngl', '0', '--chat-template', 'chatml') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localRoot 'model.log') -RedirectStandardError (Join-Path $localRoot 'model-error.log')
    $modelProcess.Id | Set-Content -LiteralPath (Join-Path $localRoot 'model.pid')
}
if (-not (Test-LocalService 'http://127.0.0.1:8000/health')) {
    $apiProcess = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','ai_quiz_agent.api.app:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localRoot 'api.log') -RedirectStandardError (Join-Path $localRoot 'api-error.log')
    $apiProcess.Id | Set-Content -LiteralPath (Join-Path $localRoot 'api.pid')
}
Write-Output 'Local model and API starting. API: http://127.0.0.1:8000/docs'
Write-Output 'For browser testing, run scripts/run_flutter_local.ps1. Model loading may take a minute.'
