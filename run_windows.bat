@echo off
cd /d "%~dp0"
if not exist sudoku_validator.exe (
 call build_windows.bat
 if errorlevel 1 exit /b 1
)
where py >nul 2>nul
if not errorlevel 1 (
 py -3 server.py
) else (
 python server.py
)
