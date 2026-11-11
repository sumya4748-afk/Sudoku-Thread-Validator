"""macOS double-click application entry point (bundled with PyInstaller)."""
import sys
import threading
import webbrowser
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
import server
server.ROOT = BASE
server.BINARY = BASE / "sudoku_validator"


def main():
    try:
        port = server.configured_port()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    try:
        httpd = server.LocalHTTPServer((server.HOST, port), server.Handler)
    except OSError:
        print(f'{port} порт завгүй эсвэл ашиглах боломжгүй. SUDOKU_PORT тохируулна уу.', file=sys.stderr)
        return 2
    url = server.dashboard_url(port)
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
