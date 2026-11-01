"""Regression tests for local-only HTTP server access controls."""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler, check

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        hdr = {'Host': '127.0.0.1:8765'}
        hdr.update(headers or {})
        conn.request(method, path, body=body, headers=hdr)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_public_and_private_paths(self):
        for path in ('/dashboard.html', '/ui/sudoku_threads.html'):
            self.assertEqual(self.request('GET', path)[0], 200, path)
        for path in ('/server.py', '/.git/config', '/sudoku_validator.c', '/README.md'):
            self.assertEqual(self.request('GET', path)[0], 404, path)

    def test_host_and_origin(self):
        self.assertEqual(self.request('GET', '/dashboard.html', headers={'Host': 'evil.test'})[0], 403)
        self.assertEqual(self.request('POST', '/api/validate', '{}',
                         {'Content-Type': 'application/json', 'Origin': 'http://evil.test'})[0], 403)

    def test_bad_payload_and_content_type(self):
        for payload in ('[]', 'null', '123', '{}', '{'):
            status, _ = self.request('POST', '/api/validate', payload, {'Content-Type': 'application/json'})
            self.assertEqual(status, 400, payload)
        self.assertEqual(self.request('POST', '/api/validate', '{}',
                         {'Content-Type': 'text/plain'})[0], 415)

    def test_valid_request(self):
        good = [int(x) for x in '534678912672195348198342567859761423426853791713924856961537284287419635345286179']
        status, data = self.request('POST', '/api/validate',
                         json.dumps({'board': good, 'mode': 11}), {'Content-Type': 'application/json'})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)['valid'])

if __name__ == '__main__':
    unittest.main()
