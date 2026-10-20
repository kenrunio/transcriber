@echo off
rem Runs the Transcriber in your web browser instead of its own window
rem (http://127.0.0.1:5055). Close this window to stop it.
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
set PY=%USERPROFILE%\.venvs\transcription\Scripts\python.exe
if not exist "%PY%" (
  echo The Python environment is missing. Run setup.bat first.
  pause
  exit /b 1
)
cd /d "%~dp0"
title Transcriber
"%PY%" app.py %*
pause
