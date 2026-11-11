"""Standalone Windows entry point; package with PyInstaller --onedir."""
import os
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
os.chdir(BASE)
import server
server.ROOT = BASE
server.BINARY = BASE / ('sudoku_validator.exe' if os.name == 'nt' else 'sudoku_validator')

def main():
    host, port = '127.0.0.1', 8765
    try:
        httpd = server.LocalHTTPServer((host, port), server.Handler)
    except OSError as exc:
        print('Port 8765 is busy. Close the previous Sudoku window. ' + str(exc))
        input('Press Enter to exit...')
        return 2
    url = f'http://{host}:{port}/dashboard.html'
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print('Sudoku Validation is running:', url)
    print('Keep this window open. Close it to stop the application.')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
