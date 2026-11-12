import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from make_wide_dealloc import render, render_observable

class GeneratorTest(unittest.TestCase):
    def test_generates_expected_count(self):
        for n in [2, 8, 32]:
            ir = render(n)
            self.assertEqual(ir.count(" = memref.alloc()"), n)
            self.assertEqual(ir.count("bufferization.dealloc"), 1)
            self.assertIn("%a0", ir)
            self.assertIn(f"%a{n-1}", ir)

    def test_observable_copies_per_allocation(self):
        for n in [2, 8, 32]:
            ir = render_observable(n)
            self.assertEqual(ir.count(" = memref.alloc()"), n)
            self.assertEqual(ir.count("memref.copy %src"), n)
            self.assertEqual(ir.count("bufferization.dealloc"), 1)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            render(1)

if __name__ == "__main__":
    unittest.main()
