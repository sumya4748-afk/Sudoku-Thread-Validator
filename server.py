#!/usr/bin/env python3
"""Local-only bridge between an editable browser board and the actual C/Pthreads binary."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, re, subprocess, sys

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / ('sudoku_validator.exe' if sys.platform == 'win32' else 'sudoku_validator')
VALID = re.compile(r'valid\[\] = \[([01 ]+)\]')
TIME = re.compile(r'Хугацаа: ([\d.]+) мкс')

def check(payload):
    board, mode = payload.get('board'), payload.get('mode')
    if not isinstance(board, list) or len(board) != 81 or any(type(x) is not int or x < 0 or x > 9 for x in board):
        raise ValueError('81 нүдтэй, 0–9 бүхэл тоон хүснэгт оруулна уу.')
    if type(mode) is not int or mode not in (1, 11, 27):
        raise ValueError('Горим 1, 11, эсвэл 27 байх ёстой.')
    if not BINARY.is_file():
        raise FileNotFoundError('C engine not built. Run make (macOS/Linux) or build_windows.bat (Windows).')
    grid_text = '\n'.join(''.join(str(x) for x in board[r*9:(r+1)*9]) for r in range(9)) + '\n'
    run = subprocess.run([str(BINARY), '-f', '-', '-t', str(mode)], input=grid_text, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8, cwd=ROOT)
    if run.returncode not in (0, 1):
        raise RuntimeError(run.stderr.strip() or run.stdout.strip() or 'C програм алдаа буцаалаа')
    match = VALID.search(run.stdout)
    if not match:
        raise RuntimeError('C программын valid[] үр дүнг уншиж чадсангүй.')
    flags = [int(v) for v in match.group(1).split()]
    if len(flags) != mode:
        raise RuntimeError('Worker-ийн үр дүнгийн тоо зөрлөө.')
    elapsed = TIME.search(run.stdout)
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path != '/api/validate':
            self.send_error(404); return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 8192:
                raise ValueError('Хүсэлтийн хэмжээ буруу.')
            data = json.loads(self.rfile.read(length))
            result = check(data)
            status = 200
        except (ValueError, json.JSONDecodeError) as exc:
            result, status = {'error': str(exc)}, 400
        except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError) as exc:
            result, status = {'error': str(exc)}, 503
        except Exception:
            result, status = {'error': 'Серверийн алдаа.'}, 500
        body = json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    host, port = '127.0.0.1', 8765
    print(f'Бодит Pthreads интерфэйс: http://{host}:{port}/dashboard.html', flush=True)
    try:
        ThreadingHTTPServer((host, port), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nСервер зогслоо.')
