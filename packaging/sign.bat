@echo off
rem Signs one file with signtool, for build.bat and the Inno Setup installer.
rem   packaging\sign.bat "path\to\file.exe"
rem The certificate settings are in %LOCALAPPDATA%\Transcriber-build\signing.bat,
rem outside the source folder and git (it may hold a password). With no such file,
rem files are left unsigned. That file sets SIGN_ARGS, the signtool arguments
rem for the route in use (README, Signing). For example:
rem   a .pfx file:     set SIGN_ARGS=/f "C:\certs\code.pfx" /p PASSWORD /fd SHA256 /tr http://timestamp.digicert.com /td SHA256
rem   a certificate in the Windows store or on a USB token:
rem                    set SIGN_ARGS=/n "Kenny Green Ltd" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256
rem   Azure Trusted Signing:
rem                    set SIGN_ARGS=/fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 /dlib "C:\tools\Azure.CodeSigning.Dlib.dll" /dmdf "C:\tools\metadata.json"
setlocal
set CONFIG=%LOCALAPPDATA%\Transcriber-build\signing.bat
if not exist "%CONFIG%" (
  echo Not signing %~nx1: no %CONFIG%
  exit /b 0
)
call "%CONFIG%"
set SIGNTOOL=signtool.exe
for /f "delims=" %%s in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*signtool.exe" 2^>nul ^| findstr /i "\\x64\\"') do set SIGNTOOL=%%s
"%SIGNTOOL%" sign %SIGN_ARGS% "%~1" || exit /b 1
