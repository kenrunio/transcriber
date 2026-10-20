@echo off
rem Builds dist\Transcriber-Setup-<version>.exe:
rem   1. the program folder, with PyInstaller (packaging\transcriber.spec)
rem   2. Transcriber.exe signed, if a certificate is set up (packaging\sign.bat)
rem   3. the installer around it, with Inno Setup (packaging\installer.iss), which
rem      signs the installer and the uninstaller the same way
rem Needs the build environment: a venv with requirements.txt minus the nvidia-*
rem lines, plus pyinstaller (see README, Building the installer).
rem Work files go to %LOCALAPPDATA%\Transcriber-build, out of the source folder;
rem the finished installer goes to the installer folder here (not in git).
setlocal
for %%i in ("%~dp0..") do set ROOT=%%~fi
set PY=%USERPROFILE%\.venvs\transcription-build\Scripts\python.exe
set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
set BUILD=%LOCALAPPDATA%\Transcriber-build
set OUT=%ROOT%\installer

rem the version is the one line of transcriber\__init__.py: __version__ = "x.y.z"
for /f "tokens=2 delims==" %%v in ('findstr /b "__version__" "%ROOT%\transcriber\__init__.py"') do set VERSION=%%v
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%
echo Building Transcriber %VERSION%

"%PY%" -m PyInstaller --noconfirm --clean --distpath "%BUILD%\dist" --workpath "%BUILD%\work" "%~dp0transcriber.spec" || exit /b 1

set SIGNED=
if exist "%BUILD%\signing.bat" set SIGNED=/DSign
call "%~dp0sign.bat" "%BUILD%\dist\Transcriber\Transcriber.exe" || exit /b 1
"%ISCC%" /Q /DAppVersion=%VERSION% /DSourceDir="%BUILD%\dist\Transcriber" /DOutDir="%OUT%" %SIGNED% "/Ssigntool=$q%~dp0sign.bat$q $f" "%~dp0installer.iss" || exit /b 1

echo.
echo Installer: %OUT%\Transcriber-Setup-%VERSION%.exe
if defined SIGNED (echo Signed with the certificate in %BUILD%\signing.bat) else (echo Not signed: no %BUILD%\signing.bat)
