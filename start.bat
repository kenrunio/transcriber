@echo off
rem Opens the Transcriber in its own window (no console). Same as the desktop shortcut.
set PYW=%USERPROFILE%\.venvs\transcription\Scripts\pythonw.exe
if not exist "%PYW%" (
  echo The Python environment is missing. Run setup.bat first.
  pause
  exit /b 1
)
cd /d "%~dp0"
start "" "%PYW%" window.py %*
