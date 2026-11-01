#!/usr/bin/env python3
"""Local-only bridge between an editable browser board and the actual C/Pthreads binary."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, re, subprocess, sys, threading
from urllib.parse import urlsplit
from http import HTTPStatus

MAX_ACTIVE = threading.BoundedSemaphore(4)
PUBLIC_FILES = {'/dashboard.html': 'dashboard.html', '/ui/sudoku_threads.html': 'ui/sudoku_threads.html'}

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / ('sudoku_validator.exe' if sys.platform == 'win32' else 'sudoku_validator')
VALID = re.compile(r'valid\[\] = \[([01 ]+)\]')
TIME = re.compile(r'Хугацаа: ([\d.]+) мкс')

def check(payload):
    if not isinstance(payload, dict):
        raise ValueError('JSON object шаардлагатай.')
    board, mode = payload.get('board'), payload.get('mode')
    if not isinstance(board, list) or len(board) != 81 or any(type(x) is not int or x < 0 or x > 9 for x in board):
        raise ValueError('81 нүдтэй, 0–9 бүхэл тоон хүснэгт оруулна уу.')
    if type(mode) is not int or mode not in (1, 11, 27):
        raise ValueError('Горим 1, 11, эсвэл 27 байх ёстой.')
    if not BINARY.is_file():
        raise FileNotFoundError('C engine not built. Run make (macOS/Linux) or build_windows.bat (Windows).')
    grid_text = '\n'.join(''.join(str(x) for x in board[r*9:(r+1)*9]) for r in range(9)) + '\n'
    run = subprocess.run([str(BINARY), '-f', '-', '-t', str(mode)], input=grid_text,
                         encoding='utf-8', errors='replace', capture_output=True,
                         timeout=8, cwd=ROOT)
    output = run.stdout or ''
    error_output = run.stderr or ''
    if run.returncode not in (0, 1):
        raise RuntimeError(error_output.strip() or output.strip() or f'C engine exited with code {run.returncode}')
    match = VALID.search(output)
    if not match:
        raise RuntimeError('C engine produced no valid[] output. ' + (error_output.strip() or output[-400:] or 'No output received.'))
    flags = [int(v) for v in match.group(1).split()]
    if len(flags) != mode:
        raise RuntimeError('Worker-ийн үр дүнгийн тоо зөрлөө.')
    elapsed = TIME.search(output)
    # Cell-level errors are derived separately for UI highlighting; the verdict is from C.
    bad = set()
    for kind in ('row', 'col', 'box'):
        for region in range(9):
            coords = ([(region, c) for c in range(9)] if kind == 'row' else
                      [(r, region) for r in range(9)] if kind == 'col' else
                      [(region//3*3+r, region%3*3+c) for r in range(3) for c in range(3)])
            values = {}
            for r, c in coords:
                v = board[r*9+c]
                if v == 0:
                    bad.add(r*9+c)
                elif v in values:
                    bad.add(r*9+c)
                    bad.add(values[v])
                else:
                    values[v] = r*9+c
    labels = (['Бүх 27 бүс'] if mode == 1 else
              ['Бүх мөр', 'Бүх багана'] + [f'3×3 хэсэг {i+1}' for i in range(9)] if mode == 11 else
              [f'Мөр {i+1}' for i in range(9)] + [f'Багана {i+1}' for i in range(9)] + [f'3×3 хэсэг {i+1}' for i in range(9)])
    return {'valid': run.returncode == 0, 'mode': mode, 'workers': [{'label': name, 'ok': bool(ok)} for name, ok in zip(labels, flags)],
            'badCells': sorted(bad), 'microseconds': float(elapsed.group(1)) if elapsed else None,
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
        return host in ('127.0.0.1:8765', 'localhost:8765')

    def _allowed_origin(self):
        origin = self.headers.get('Origin')
        return not origin or origin.lower() in ('http://127.0.0.1:8765', 'http://localhost:8765')

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
            self.send_error(403)
            return
        if self._route() != '/api/validate':
            self.send_error(404)
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            self._json(415, {'error': 'Content-Type must be application/json'})
            return
        if not MAX_ACTIVE.acquire(blocking=False):
            self._json(503, {'error': 'Too many concurrent validations'})
            return
        try:
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 8192:
                    raise ValueError('Хүсэлтийн хэмжээ буруу.')
                data = json.loads(self.rfile.read(length))
                result, status = check(data), 200
            except (ValueError, json.JSONDecodeError) as exc:
                result, status = {'error': str(exc)}, 400
            except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError) as exc:
                result, status = {'error': str(exc)}, 503
            except Exception:
                result, status = {'error': 'Серверийн алдаа.'}, 500
            self._json(status, result)
        finally:
            MAX_ACTIVE.release()

if __name__ == '__main__':
    host, port = '127.0.0.1', 8765
    print(f'Бодит Pthreads интерфэйс: http://{host}:{port}/dashboard.html', flush=True)
    try:
        ThreadingHTTPServer((host, port), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nСервер зогслоо.')
