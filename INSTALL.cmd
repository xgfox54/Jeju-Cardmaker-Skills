@echo off
setlocal
pushd "%~dp0"
powershell -NoProfile -File "%~dp0install.ps1" -WithRuntime
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo Installation failed. See messages above. Do not change organization security policy.
popd
pause
exit /b %RESULT%
