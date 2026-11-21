import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
SOLVED = [int(c) for c in '534678912672195348198342567859761423426853791713924856961537284287419635345286179']
class Diagnostics(unittest.TestCase):
    def test_modes_and_diagnostics(self):
        for mode in (1,11,27):
            with self.subTest(mode=mode):
                result = server.check({'board':SOLVED,'mode':mode})
                self.assertTrue(result['valid']);self.assertEqual(result['badCells'],[])
                self.assertEqual(result['issues'],[]);self.assertEqual(len(result['workers']),mode)
    def test_duplicate(self):
        board=SOLVED.copy();board[0]=board[1]
        result=server.check({'board':board,'mode':11})
        self.assertFalse(result['valid']);self.assertIn(0,result['badCells']);self.assertIn(1,result['badCells'])
        self.assertTrue(any('давхардсан' in x for x in result['issues']))
        self.assertTrue(any('дутуу' in x for x in result['issues']))
    def test_empty(self):
        board=SOLVED.copy();board[0]=0
        result=server.check({'board':board,'mode':27})
        self.assertFalse(result['valid']);self.assertIn(0,result['badCells'])
        self.assertTrue(any('хоосон' in x for x in result['issues']))
    def test_bad_payload(self):
        with self.assertRaises(ValueError):server.check({'board':[0]*80,'mode':11})
if __name__=='__main__':unittest.main()
