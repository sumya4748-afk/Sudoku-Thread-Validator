"""Regression tests for the C/Pthreads bridge and repository consistency."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server

GOOD = [int(c) for c in '534678912672195348198342567859761423426853791713924856961537284287419635345286179']


class ReviewRegression(unittest.TestCase):
    def test_source_copies_are_identical(self):
        self.assertEqual((ROOT / 'sudoku_validator.c').read_bytes(),
                         (ROOT / 'src/sudoku_validator.c').read_bytes(),
                         'Root and src copies have diverged; keep them synchronized until consolidation.')

    def test_duplicate_and_empty_are_consistent_across_modes(self):
        duplicate = GOOD.copy()
        duplicate[0] = duplicate[1]
        empty = GOOD.copy()
        empty[0] = 0
        for mode in (1, 11, 27):
            for board, expected in ((GOOD, True), (duplicate, False), (empty, False)):
                with self.subTest(mode=mode, valid=expected, empty=(board is empty)):
                    result = server.check({'board': board, 'mode': mode})
                    self.assertIs(result['valid'], expected)
                    self.assertEqual(len(result['workers']), mode)
                    self.assertEqual(bool(result['badCells']), not expected)
                    self.assertEqual(bool(result['issues']), not expected)
                    self.assertEqual(all(w['ok'] for w in result['workers']), expected)
                    self.assertEqual(result['valid'], all(w['ok'] for w in result['workers']))

    def test_subprocess_error_does_not_look_like_invalid_sudoku(self):
        with patch.object(server, 'BINARY') as binary, patch.object(
            server.subprocess, 'run', return_value=SimpleNamespace(
                returncode=2, stdout='', stderr='invalid input')):
            binary.is_file.return_value = True
            with self.assertRaisesRegex(RuntimeError, 'invalid input'):
                server.check({'board': GOOD, 'mode': 11})

    def test_worker_count_mismatch_is_rejected(self):
        with patch.object(server, 'BINARY') as binary, patch.object(
            server.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='{"valid":true,"mode":11,"microseconds":1.0,"flags":[1,1],"badCells":[],"issues":[]}', stderr='')):
            binary.is_file.return_value = True
            with self.assertRaisesRegex(RuntimeError, 'тоо зөрлөө'):
                server.check({'board': GOOD, 'mode': 11})

    def test_engine_json_is_source_of_cell_diagnostics(self):
        data = '{"valid":false,"mode":1,"microseconds":1.25,"flags":[0],"badCells":[0,1],"issues":[{"region":0,"regionNo":0,"kind":0,"digit":5,"row":0,"col":1}]}'
        with patch.object(server, 'BINARY') as binary, patch.object(
            server.subprocess, 'run', return_value=SimpleNamespace(
                returncode=1, stdout=data, stderr='')):
            binary.is_file.return_value = True
            result = server.check({'board': GOOD, 'mode': 1})
            self.assertEqual(result['badCells'], [0, 1])
            self.assertIn('давхардсан', result['issues'][0])

    def test_input_validation_rejects_bool_float_and_invalid_mode(self):
        for board, mode in (([True]*81, 11), ([1.0]*81, 11), (GOOD, True),
                            (GOOD, 5), (GOOD[:-1], 11)):
            with self.subTest(mode=mode, length=len(board)):
                with self.assertRaises(ValueError):
                    server.check({'board': board, 'mode': mode})


if __name__ == '__main__':
    unittest.main()
