import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = (ROOT / "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt").read_text(encoding="utf-8")


class TestAndroidPartyStartAsync(unittest.TestCase):
    def test_python_party_start_does_not_block_compose_main_thread(self):
        self.assertIn("startingPidx", SERVICE)
        self.assertIn("AccountStatus(RunState.CONNECTING)", SERVICE)
        self.assertIn('Thread({', SERVICE)
        self.assertIn('name = "aTSBot-start-party-$pidx"', SERVICE)
        self.assertIn("startingPidx.remove(pidx)", SERVICE)


if __name__ == "__main__":
    unittest.main()
