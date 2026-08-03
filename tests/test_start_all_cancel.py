import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COORDINATOR = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")


class TestStartAllCancel(unittest.TestCase):
    def test_stop_all_cancels_party_start_loops_still_in_progress(self):
        self.assertIn("_start_cancel_generation = 0", COORDINATOR)
        self.assertIn("generation = _start_cancel_generation", COORDINATOR)
        self.assertIn("if generation != _start_cancel_generation:", COORDINATOR)
        self.assertIn("_start_cancel_generation += 1", COORDINATOR)


if __name__ == "__main__":
    unittest.main()
