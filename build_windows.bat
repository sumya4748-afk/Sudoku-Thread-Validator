@echo off
cd /d "%~dp0"
where gcc >nul 2>nul
if errorlevel 1 (
 echo GCC not found. Install MSYS2 UCRT64 GCC and add its bin directory to PATH.
 exit /b 1
)
gcc -std=c11 -Wall -Wextra -O2 -pthread sudoku_validator.c -o sudoku_validator.exe
if errorlevel 1 (
 echo Build failed.
 exit /b 1
)
echo Build OK: sudoku_validator.exe
