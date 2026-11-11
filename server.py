#!/usr/bin/env python3
"""Local-only bridge between an editable browser board and the actual C/Pthreads binary."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import json
import subprocess
import sys
import threading
from urllib.parse import urlsplit

MAX_ACTIVE = threading.BoundedSemaphore(4)
PUBLIC_FILES = {'/dashboard.html': 'dashboard.html', '/ui/sudoku_threads.html': 'ui/sudoku_threads.html'}

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / ('sudoku_validator.exe' if sys.platform == 'win32' else 'sudoku_validator')
def describe_issue(issue):
    title = {'row': 'Мөр', 'col': 'Багана', 'box': '3×3 хэсэг'}[issue['region']]
    region = f"{title} {issue['number']}"
    cell = f"[{issue['row']},{issue['column']}]"
    digit = issue['digit']
    if issue['kind'] == 'duplicate':
        return f'{region}: {digit} давхардсан (нүд {cell})'
    if issue['kind'] == 'range':
        return f'{region}: нүд {cell} хоосон'
    return f'{region}: {digit} цифр дутуу'


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
    output = run.stdout or ''
    error_output = run.stderr or ''
    if run.returncode not in (0, 1):
        raise RuntimeError(error_output.strip() or output.strip() or f'C engine exited with code {run.returncode}')
    try:
        report = json.loads(output)
        flags = report['flags']
        bad_cells = report['badCells']
        issues = [describe_issue(issue) for issue in report['issues']]
        elapsed = report['microseconds']
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError('C хөдөлгүүрийн JSON үр дүнг уншиж чадсангүй.') from exc
    if not isinstance(flags, list) or len(flags) != mode:
        raise RuntimeError('Урсгалын үр дүнгийн тоо зөрлөө.')
    if all(flags) != (run.returncode == 0):
        raise RuntimeError('C хөдөлгүүрийн эцсийн дүн ба урсгалуудын үр дүн зөрлөө.')
    labels = (['Бүх 27 бүс'] if mode == 1 else
              ['Бүх мөр', 'Бүх багана'] + [f'3×3 хэсэг {i+1}' for i in range(9)] if mode == 11 else
              [f'Мөр {i+1}' for i in range(9)] + [f'Багана {i+1}' for i in range(9)] + [f'3×3 хэсэг {i+1}' for i in range(9)])
    return {'valid': run.returncode == 0, 'mode': mode, 'workers': [{'label': name, 'ok': bool(ok)} for name, ok in zip(labels, flags)],
            'badCells': bad_cells, 'issues': issues, 'microseconds': elapsed,
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
        return host in self._local_hosts()

    def _allowed_origin(self):
        origin = self.headers.get('Origin')
        return not origin or origin.lower() in {f'http://{host}' for host in self._local_hosts()}

    def _local_hosts(self):
        port = self.server.server_port
        return (f'127.0.0.1:{port}', f'localhost:{port}')

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
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ValueError('Хүсэлтийн JSON формат буруу байна.') from exc
                result, status = check(data), 200
            except ValueError as exc:
                result, status = {'error': str(exc)}, 400
            except subprocess.TimeoutExpired:
                result, status = {'error': 'C хөдөлгүүр хугацаандаа хариу өгсөнгүй.'}, 503
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
    parser = argparse.ArgumentParser(description='Судокугийн локал сервер')
    parser.add_argument('--port', type=int, default=8765, help='Локал порт (анхдагч: 8765)')
    port = parser.parse_args().port
    if not 1 <= port <= 65535:
        parser.error('--port нь 1–65535 хооронд байна.')
    host = '127.0.0.1'
    try:
        with LocalHTTPServer((host, port), Handler) as httpd:
            print(f'Бодит Pthreads интерфэйс: http://{host}:{port}/dashboard.html', flush=True)
            httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nСервер зогслоо.')
    except OSError:
        print(f'{host}:{port} порт завгүй эсвэл ашиглах боломжгүй байна. --port сонголтоор өөр порт өгнө үү.', file=sys.stderr)
        sys.exit(2)
