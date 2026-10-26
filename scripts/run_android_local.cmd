@echo off
setlocal
set "QUIZ_PROJECT=%~dp0.."
if not exist "%QUIZ_PROJECT%\.local\flutter-android.json" (
  echo Start the API first with powershell -File scripts\start_local.ps1
  exit /b 1
)
if not exist "%QUIZ_PROJECT%\.local\java-sockets" mkdir "%QUIZ_PROJECT%\.local\java-sockets"
set JAVA_TOOL_OPTIONS=%JAVA_TOOL_OPTIONS% -Djdk.net.unixdomain.tmpdir="%QUIZ_PROJECT%\.local\java-sockets"
set "QUIZ_DEVICE=%~1"
if not defined QUIZ_DEVICE set "QUIZ_DEVICE=emulator-5554"
pushd "%QUIZ_PROJECT%\flutter project"
call flutter run -d %QUIZ_DEVICE% -t lib/main.dart "--dart-define-from-file=%QUIZ_PROJECT%\.local\flutter-android.json"
set "QUIZ_EXIT=%ERRORLEVEL%"
popd
exit /b %QUIZ_EXIT%
