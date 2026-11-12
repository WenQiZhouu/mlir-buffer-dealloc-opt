import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PatchStructuralTest(unittest.TestCase):
    def test_patch_contains_fast_path_and_fallback(self):
        patch = (ROOT / "patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch").read_text(encoding="utf-8")
        self.assertIn("+    bool allRootsKnown = true;", patch)
        self.assertIn("+    llvm::DenseMap<Value, int64_t> rootUseCount;", patch)
        self.assertIn("+        mayAlias = potentiallyAliasesMemref(analysis, otherMemrefs, memref);", patch)

    def test_reference_and_modified_have_same_rewrite_tail(self):
        rel = "mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp"
        baseline = (ROOT / "reference-tree" / rel).read_text(encoding="utf-8")
        modified = (ROOT / "modified-source" / rel).read_text(encoding="utf-8")
        text = "    // Create bufferization.dealloc op for all remaining memrefs."
        self.assertEqual(baseline[baseline.index(text):], modified[modified.index(text):])

    def test_regression_mlir_covers_fast_path_and_fallback(self):
        test = (ROOT / "tests/llvm/buffer-deallocation-simplification-wide.mlir").read_text(encoding="utf-8")
        self.assertIn("@split_distinct_alloc_roots", test)
        self.assertIn("@do_not_split_same_allocation_root", test)
        self.assertIn("@unknown_origins_keep_conservative_fallback", test)

if __name__ == "__main__":
    unittest.main()
