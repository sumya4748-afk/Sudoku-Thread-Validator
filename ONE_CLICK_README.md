# Sudoku Validation — One-click launcher

## Windows
Install Python 3 and MSYS2 UCRT64 GCC (C:/msys64/ucrt64/bin/gcc.exe), then double-click `START_WINDOWS.bat`.
If Windows SmartScreen prompts, only run files you trust. The first launch compiles the C engine automatically. Keep the command window open while using the dashboard.

## macOS
Install Python 3 and Xcode Command Line Tools (`xcode-select --install`). Double-click `START_MAC.command`. If macOS blocks the script or execution permission was lost after ZIP extraction, open Terminal in the project folder and run `chmod +x START_MAC.command` once. Keep the Terminal window open.

## Linux
Install Python 3 and GCC (`sudo apt install python3 gcc` on Ubuntu). Run `./START_LINUX.sh` or enable executing the script via file manager. Desktop-file launch behavior depends on the desktop environment.

## What happens
Launcher checks/builds the C/Pthreads executable, starts the local Python HTTP server, then opens `http://127.0.0.1:8765/dashboard.html`. The server runs only while the launcher window is open. Requires port 8765 free. No network deployment and no standalone EXE/APP is included.

## Troubleshooting
If port 8765 is in use, stop the previous server before starting another copy. Do not open `dashboard.html` as `file://` because validation uses `/api/validate`.
