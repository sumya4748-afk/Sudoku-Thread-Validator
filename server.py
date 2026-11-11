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
        raise FileNotFoundError('C хөдөлгүүр хөрвүүлэгдээгүй байна. macOS/Linux дээр make, Windows дээр build_windows.bat ажиллуулна уу.')
    grid_text = '\n'.join(''.join(str(x) for x in board[r*9:(r+1)*9]) for r in range(9)) + '\n'
    run = subprocess.run([str(BINARY), '-f', '-', '-t', str(mode), '-j'], input=grid_text,
                         encoding='utf-8', errors='replace', capture_output=True,
                         timeout=8, cwd=ROOT)
    output = run.stdout or ''
    error_output = run.stderr or ''
    if run.returncode not in (0, 1):
        raise RuntimeError(error_output.strip() or output.strip() or f'C хөдөлгүүр {run.returncode} кодтой дууслаа')
    try:
        engine = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError('C хөдөлгүүрийн JSON гаралт буруу байна.') from exc
    flags = engine.get('flags')
    if not isinstance(flags, list) or len(flags) != mode or any(v not in (0, 1) for v in flags):
        raise RuntimeError('Worker-ийн үр дүнгийн тоо зөрлөө.')
    if engine.get('valid') is not (run.returncode == 0):
        raise RuntimeError('C хөдөлгүүрийн төлөв ба гаралтын код зөрлөө.')
    bad = engine.get('badCells')
    raw_issues = engine.get('issues')
    if not isinstance(bad, list) or not isinstance(raw_issues, list):
        raise RuntimeError('C хөдөлгүүрийн оношлогоо дутуу байна.')
    region_names = ('Мөр', 'Багана', '3×3 хэсэг')
    issues = []
    for item in raw_issues:
        if not isinstance(item, dict) or item.get('region') not in (0, 1, 2) or item.get('kind') not in (0, 1, 2):
            raise RuntimeError('C хөдөлгүүрийн оношлогооны бүтэц буруу байна.')
        title = f"{region_names[item['region']]} {item['regionNo']+1}"
        if item['kind'] == 0:
            issues.append(f"{title}: {item['digit']} давхардсан (нүд [{item['row']+1},{item['col']+1}])")
        elif item['kind'] == 1:
            issues.append(f"{title}: нүд [{item['row']+1},{item['col']+1}] хоосон")
        else:
            issues.append(f"{title}: {item['digit']} цифр дутуу")
    labels = (['Бүх 27 бүс'] if mode == 1 else
              ['Бүх мөр', 'Бүх багана'] + [f'3×3 хэсэг {i+1}' for i in range(9)] if mode == 11 else
              [f'Мөр {i+1}' for i in range(9)] + [f'Багана {i+1}' for i in range(9)] + [f'3×3 хэсэг {i+1}' for i in range(9)])
    return {'valid': run.returncode == 0, 'mode': mode, 'workers': [{'label': name, 'ok': bool(ok)} for name, ok in zip(labels, flags)],
            'badCells': bad, 'issues': issues, 'microseconds': engine.get('microseconds'),
            'engine': 'C11 + POSIX pthreads', 'note': 'Хугацаа нь бодит C thread-ийн хэмжилт; сургалтын симуляцын tick биш.'}

class LocalHTTPServer(ThreadingHTTPServer):
    # Accept a burst of local connections; validation concurrency remains capped.
    request_queue_size = 128
    daemon_threads = True


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
            self._json(415, {'error': 'Content-Type нь application/json байх ёстой.'})
            return
        if not MAX_ACTIVE.acquire(blocking=False):
            self._json(503, {'error': 'Хэт олон шалгалт зэрэг ажиллаж байна. Түр хүлээгээд дахин оролдоно уу.'})
            return
        try:
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 8192:
                    raise ValueError('Хүсэлтийн хэмжээ буруу.')
                try:
                    data = json.loads(self.rfile.read(length))
                except json.JSONDecodeError as exc:
                    raise ValueError('Хүсэлтийн JSON формат буруу байна.') from exc
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
        LocalHTTPServer((host, port), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nСервер зогслоо.')
    except OSError as exc:
        print(f'Серверийг эхлүүлж чадсангүй: 127.0.0.1:{port} порт завгүй эсвэл ашиглах боломжгүй ({exc}).', file=sys.stderr)
        sys.exit(2)
