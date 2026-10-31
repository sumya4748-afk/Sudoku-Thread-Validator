@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
 py -3 launch.py
) else (
 python launch.py
)
if errorlevel 1 (
 echo.
 echo Check START_HERE.md for setup instructions.
 pause
)
