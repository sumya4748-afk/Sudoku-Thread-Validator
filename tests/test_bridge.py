import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import check

GOOD = [int(x) for x in '534678912672195348198342567859761423426853791713924856961537284287419635345286179']

class BridgeTests(unittest.TestCase):
    def test_modes(self):
        for mode in (1, 11, 27):
            with self.subTest(mode=mode):
                result = check({'board': GOOD, 'mode': mode})
                self.assertTrue(result['valid'])
                self.assertEqual(len(result['workers']), mode)
                self.assertTrue(all(w['ok'] for w in result['workers']))
    def test_invalid(self):
        board = GOOD.copy(); board[0] = board[1]
        result = check({'board': board, 'mode': 27})
        self.assertFalse(result['valid'])
        self.assertIn(0, result['badCells'])
        self.assertIn(1, result['badCells'])
    def test_empty(self):
        self.assertFalse(check({'board': [0]*81, 'mode': 11})['valid'])
    def test_bad_shape(self):
        with self.assertRaises(ValueError): check({'board': [1]*80, 'mode': 11})
    def test_bad_mode(self):
        with self.assertRaises(ValueError): check({'board': GOOD, 'mode': 5})
    def test_bad_type(self):
        with self.assertRaises(ValueError): check({'board': [True]*81, 'mode': 11})

if __name__ == '__main__': unittest.main()
