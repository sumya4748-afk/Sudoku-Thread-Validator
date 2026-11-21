#!/usr/bin/env python3
"""One-click local launcher: compile if necessary, start server, open browser."""
import os, sys, shutil, subprocess, time, webbrowser, socket
from pathlib import Path
ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8765/dashboard.html'
EXE = ROOT / ('sudoku_validator.exe' if os.name == 'nt' else 'sudoku_validator')
SRC = ROOT / 'sudoku_validator.c'

def main():
    if not EXE.exists() or EXE.stat().st_mtime < SRC.stat().st_mtime:
        gcc = shutil.which('gcc') or shutil.which('clang')
        if not gcc and os.name == 'nt':
            for base in ('C:/msys64/ucrt64/bin/gcc.exe','C:/msys64/mingw64/bin/gcc.exe'):
                if Path(base).exists(): gcc=base;break
        if not gcc:
            print('C compiler not found. Install GCC (Windows: MSYS2 UCRT64) or Clang (macOS).')
            return 1
        cmd = [gcc, '-std=c11', '-O2', '-Wall', '-Wextra', '-pthread', str(SRC), '-o', str(EXE)]
        print('Building C/Pthreads engine...', flush=True)
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode: return result.returncode
    try:
        with socket.create_connection(('127.0.0.1',8765),timeout=0.4):
            print('Port 8765 is already in use. Close the old server before launching.')
            return 2
    except OSError: pass
    server = subprocess.Popen([sys.executable, str(ROOT/'server.py')], cwd=ROOT)
    try:
        for _ in range(40):
            if server.poll() is not None:
                print('Server exited unexpectedly.')
                return 3
            try:
                with socket.create_connection(('127.0.0.1',8765),timeout=0.25):
                    webbrowser.open(URL)
                    print('Dashboard:', URL)
                    print('Keep this launcher open while using the dashboard.')
                    print('Press Ctrl+C to stop.')
                    return server.wait()
            except OSError: time.sleep(0.15)
        print('Server did not start in time.')
        return 4
    except KeyboardInterrupt:
        print('\nStopping server...')
        return 0
    finally:
        if server.poll() is None:
            server.terminate()
            try: server.wait(timeout=3)
            except subprocess.TimeoutExpired: server.kill()

if __name__ == '__main__':
    sys.exit(main())
