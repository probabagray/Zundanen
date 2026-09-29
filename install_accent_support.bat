@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_accent_support.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Accent component repair/setup finished.
) else (
  echo Accent component repair/setup did not finish. Run setup.bat again or retry this helper.
)
echo.
pause
exit /b %RC%
