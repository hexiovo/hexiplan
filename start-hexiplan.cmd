@echo off
setlocal
chcp 65001 >nul
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0tools\launch.py" %*
) else (
  python "%~dp0tools\launch.py" %*
)
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo HexiPlan did not complete. No installation or global configuration change was attempted.
  pause
)
exit /b %RC%
