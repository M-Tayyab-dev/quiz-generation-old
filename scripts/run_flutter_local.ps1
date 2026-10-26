param([ValidateSet('web','android')] [string]$Target='web', [string]$Device='')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$config=Join-Path $projectRoot ".local\flutter-$Target.json"
if (-not (Test-Path -LiteralPath $config)) { throw 'Run scripts/start_local.ps1 first.' }
Push-Location (Join-Path $projectRoot 'flutter project')
try {
    if ($Target -eq 'web') {
        flutter run -d web-server --web-hostname 127.0.0.1 --web-port 7357 -t lib/main.dart "--dart-define-from-file=$config"
    } else {
        if (-not $Device) { throw 'Supply -Device with your Android emulator ID from flutter devices.' }
        $socketDir = Join-Path $projectRoot '.local\java-sockets'
        New-Item -ItemType Directory -Path $socketDir -Force | Out-Null
        $env:JAVA_TOOL_OPTIONS = '-Djdk.net.unixdomain.tmpdir="' + $socketDir + '"'
        flutter run -d $Device -t lib/main.dart "--dart-define-from-file=$config"
    }
} finally { Pop-Location }
