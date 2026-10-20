@echo off
rem One-time setup: a Python environment in %USERPROFILE%\.venvs, with the libraries.
rem Needs Python 3.11 (py launcher). An NVIDIA graphics card makes it much faster.
rem The voice and punctuation models must also be in place (README, Setting up).
set VENV=%USERPROFILE%\.venvs\transcription
if not exist "%VENV%\Scripts\python.exe" py -3.11 -m venv "%VENV%"
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" -c "%~dp0constraints.txt"
echo.
echo Done. Start the app with start.bat
pause
