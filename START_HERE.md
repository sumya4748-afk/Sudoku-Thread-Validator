# Sudoku Validation — Cross-platform Quick Start

## macOS
Requirements: Xcode Command Line Tools (C compiler and make), Python 3.

```sh
make
python3 server.py
```

## Linux (Ubuntu/Debian)
Install dependencies once:

```sh
sudo apt update
sudo apt install build-essential python3
```

Then run `bash run_linux.sh` (or `make` followed by `python3 server.py`).

## Windows 10/11 — native, without WSL
Requirements: Python 3 and **MSYS2 UCRT64 GCC** with pthread support.

1. Install Python 3 from python.org and enable PATH (or use the Python launcher `py`).
2. Install MSYS2 from https://www.msys2.org/. Open **MSYS2 UCRT64** and install the compiler:

   `pacman -S --needed mingw-w64-ucrt-x86_64-gcc`

3. In MSYS2 UCRT64 terminal, navigate to this project directory and run:

   `gcc -std=c11 -Wall -Wextra -O2 -pthread sudoku_validator.c -o sudoku_validator.exe`

4. From Windows Explorer, double-click `run_windows.bat` (or run `python server.py` from the same folder).

Alternative: add `C:\msys64\ucrt64\bin` to Windows PATH, then `build_windows.bat` and `run_windows.bat` work from Command Prompt. Keep MSYS2 UCRT64 runtime DLLs available via PATH.

## Browser

Open **http://127.0.0.1:8765/dashboard.html**. The C engine must be compiled before validating. Stop the server with **Ctrl+C**. If port 8765 is in use, stop the previous server first.

## Tests

- macOS/Linux: `make` and `python3 -m unittest discover -s tests -v`; run `bash run_tests.sh` for CLI tests.
- Windows: `py -3 -m unittest discover -s tests -v`; check the UI and all 1/11/27 worker modes. The POSIX shell test script `run_tests.sh` requires an MSYS2 shell on Windows.

**Status:** Linux build and bridge tests can be verified in this package's build environment; Windows native build and UI must be tested on a real Windows machine before claiming full compatibility.
