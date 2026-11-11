#!/usr/bin/env python3
"""Local-only bridge between an editable browser board and the actual C/Pthreads binary."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, os, subprocess, sys, threading
from urllib.parse import urlsplit
from http import HTTPStatus

MAX_ACTIVE = threading.BoundedSemaphore(4)
PUBLIC_FILES = {'/dashboard.html': 'dashboard.html', '/ui/sudoku_threads.html': 'ui/sudoku_threads.html'}

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / ('sudoku_validator.exe' if sys.platform == 'win32' else 'sudoku_validator')
HOST = '127.0.0.1'
DEFAULT_PORT = 8765


def configured_port():
    value = os.environ.get('SUDOKU_PORT', str(DEFAULT_PORT))
    if not value.isascii() or not value.isdecimal() or len(value) > 5 or not 1 <= int(value) <= 65535:
        raise ValueError('SUDOKU_PORT нь 1–65535 хоорондох бүхэл тоо байх ёстой.')
    return int(value)


def dashboard_url(port):
    return f'http://{HOST}:{port}/dashboard.html'


def format_issue(item):
    region, number, kind, digit, row, col = item
    title = ('Мөр', 'Багана', '3×3 хэсэг')[region]
    prefix = f'{title} {number + 1}: '
    cell = f'нүд [{row + 1},{col + 1}]'
    if kind == 0:
        return f'{prefix}{digit} давхардсан ({cell})'
    if kind == 1:
        return f'{prefix}{cell} хоосон'
    return f'{prefix}{digit} цифр дутуу'


def check(payload):
    if not isinstance(payload, dict):
        raise ValueError('JSON object шаардлагатай.')
    board, mode = payload.get('board'), payload.get('mode')
    if not isinstance(board, list) or len(board) != 81 or any(type(x) is not int or x < 0 or x > 9 for x in board):
        raise ValueError('81 нүдтэй, 0–9 бүхэл тоон хүснэгт оруулна уу.')
    if type(mode) is not int or mode not in (1, 11, 27):
        raise ValueError('Горим 1, 11, эсвэл 27 байх ёстой.')
    if not BINARY.is_file():
        raise FileNotFoundError('C хөдөлгүүр хөрвүүлэгдээгүй байна. macOS/Linux дээр make, Windows дээр build_windows.bat ажиллуулна уу.')
    grid_text = '\n'.join(''.join(str(x) for x in board[r*9:(r+1)*9]) for r in range(9)) + '\n'
    run = subprocess.run([str(BINARY), '-j', '-f', '-', '-t', str(mode)], input=grid_text,
                         encoding='utf-8', errors='replace', capture_output=True,
                         timeout=8, cwd=ROOT)
    if run.returncode not in (0, 1):
        raise RuntimeError(f'C хөдөлгүүрийн шалгалт амжилтгүй (код {run.returncode}).')
    try:
        result = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('C хөдөлгүүрээс JSON үр дүн уншиж чадсангүй.') from exc
    flags = result['workers']
    if len(flags) != mode:
        raise RuntimeError('Урсгалын үр дүнгийн тоо зөрлөө.')
    if result['valid'] != (run.returncode == 0) or result['valid'] != all(flags):
        raise RuntimeError('C хөдөлгүүрийн үр дүн зөрлөө.')
    # Keep the API display order consistent across all worker configurations.
    issues = sorted(result['issues'], key=lambda item: (item[0], item[1], item[4] < 0, item[4], item[5], item[3]))
    labels = (['Бүх 27 бүс'] if mode == 1 else
              ['Бүх мөр', 'Бүх багана'] + [f'3×3 хэсэг {i+1}' for i in range(9)] if mode == 11 else
              [f'Мөр {i+1}' for i in range(9)] + [f'Багана {i+1}' for i in range(9)] + [f'3×3 хэсэг {i+1}' for i in range(9)])
    return {'valid': run.returncode == 0, 'mode': mode, 'workers': [{'label': name, 'ok': bool(ok)} for name, ok in zip(labels, flags)],
            'badCells': result['badCells'], 'issues': [format_issue(item) for item in issues],
            'microseconds': result['microseconds'],
            'engine': 'C11 + POSIX pthreads', 'note': 'Хугацаа нь бодит C thread-ийн хэмжилт; сургалтын симуляцын tick биш.'}

class Handler(SimpleHTTPRequestHandler):
    # Explicit UTF-8 for browser HTML pages containing Mongolian text.
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.html': 'text/html; charset=utf-8'}

    # Only explicitly published HTML is readable; no repository directory listing.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def _allowed_host(self):
        host = self.headers.get('Host', '').lower()
        return host in (f'{HOST}:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def _allowed_origin(self):
        origin = self.headers.get('Origin')
        return not origin or origin.lower() in (f'http://{HOST}:{self.server.server_port}', f'http://localhost:{self.server.server_port}')

    def _route(self):
        return urlsplit(self.path).path

    def do_GET(self):
        if not self._allowed_host():
            self.send_error(403)
            return
        path = self._route()
        if path == '/':
            self.send_response(302)
            self.send_header('Location', '/dashboard.html')
            self.end_headers()
            return
        if path not in PUBLIC_FILES:
            self.send_error(404)
            return
        self.path = '/' + PUBLIC_FILES[path]
        super().do_GET()

    def do_HEAD(self):
        if not self._allowed_host():
            self.send_error(403)
            return
        path = self._route()
        if path not in PUBLIC_FILES:
            self.send_error(404)
            return
        self.path = '/' + PUBLIC_FILES[path]
        super().do_HEAD()

    def _json(self, status, result):
        body = json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self._allowed_host() or not self._allowed_origin():
            self._json(403, {'error': 'Хүсэлтийн хаяг зөвшөөрөгдөөгүй.'})
            return
        if self._route() != '/api/validate':
            self._json(404, {'error': 'Хүсэлтийн зам олдсонгүй.'})
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            self._json(415, {'error': 'Content-Type нь application/json байх ёстой.'})
            return
        if not MAX_ACTIVE.acquire(blocking=False):
            self._json(503, {'error': 'Хэт олон шалгалт зэрэг ажиллаж байна. Түр хүлээгээд дахин оролдоно уу.'})
            return
        try:
            try:
                size = self.headers.get('Content-Length', '')
                if not size.isascii() or not size.isdecimal() or len(size) > 4 or not 1 <= int(size) <= 8192:
                    raise ValueError('Хүсэлтийн хэмжээ буруу.')
                length = int(size)
                try:
                    data = json.loads(self.rfile.read(length))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ValueError('Хүсэлтийн JSON формат буруу байна.') from exc
                result, status = check(data), 200
            except ValueError as exc:
                result, status = {'error': str(exc)}, 400
            except subprocess.TimeoutExpired:
                result, status = {'error': 'C хөдөлгүүрийн шалгалтын хугацаа хэтэрлээ.'}, 503
            except (FileNotFoundError, RuntimeError) as exc:
                result, status = {'error': str(exc)}, 503
            except Exception:
                result, status = {'error': 'Серверийн алдаа.'}, 500
            self._json(status, result)
        finally:
            MAX_ACTIVE.release()

class LocalHTTPServer(ThreadingHTTPServer):
    # Accept queued connections under short bursts; active C validations remain bounded.
    request_queue_size = 128
    daemon_threads = True


if __name__ == '__main__':
    try:
        port = configured_port()
        with LocalHTTPServer((HOST, port), Handler) as httpd:
            print(f'Бодит Pthreads интерфэйс: {dashboard_url(port)}', flush=True)
            httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nСервер зогслоо.')
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
    except OSError:
        print(f'Серверийг эхлүүлж чадсангүй: {HOST}:{port} порт завгүй эсвэл ашиглах боломжгүй.', file=sys.stderr)
        sys.exit(2)
