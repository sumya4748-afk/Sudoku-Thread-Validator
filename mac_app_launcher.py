"""macOS double-click application entry point (bundled with PyInstaller)."""
import os
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
import server
server.ROOT = BASE
server.BINARY = BASE / "sudoku_validator"


def main():
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", 8765), server.Handler)
    except OSError as exc:
        # A busy port does not prove that the other service is this Sudoku app.
        print(f"Cannot start Sudoku: port 8765 is unavailable ({exc}).", flush=True)
        return 2

    url = "http://127.0.0.1:8765/dashboard.html"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
