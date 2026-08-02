import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")


class TestAndroidPartyStatusColor(unittest.TestCase):
    def test_party_dot_distinguishes_stopped_partial_and_fully_running(self):
        self.assertIn("fun partyStatusColor(", UI)
        self.assertIn("running == enabledAccounts.size -> StatusRunning", UI)
        self.assertIn("running > 0 || connecting -> StatusConnecting", UI)
        self.assertIn("else -> StatusStopped", UI)

    def test_party_tab_and_card_use_the_same_status_color(self):
        self.assertGreaterEqual(UI.count("partyStatusColor("), 3)


if __name__ == "__main__":
    unittest.main()
