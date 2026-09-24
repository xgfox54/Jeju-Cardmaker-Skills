@echo off
setlocal
pushd "%~dp0"
echo This updates Jeju_Cardmaker and replaces an earlier ReleasePick install after backing up the existing skill.
powershell -NoProfile -File "%~dp0install.ps1" -Replace -WithRuntime
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo Update failed or runtime setup incomplete. See messages above.
popd
pause
exit /b %RESULT%
