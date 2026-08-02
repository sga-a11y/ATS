import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")
SERVICE = (ROOT / "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt").read_text(encoding="utf-8")


class TestAndroidAllPartyControls(unittest.TestCase):
    def test_main_screen_has_start_and_stop_all_party_buttons(self):
        self.assertIn('Text("Chạy tất cả",', UI)
        self.assertIn('Text("Dừng tất cả",', UI)

    def test_start_all_only_starts_parties_with_enabled_accounts(self):
        self.assertIn("parties.filter { party -> party.accounts.any { it.enabled } }", UI)
        self.assertIn("forEach(::startPartyIn)", UI)

    def test_stop_all_runs_off_the_compose_thread(self):
        self.assertIn("scope.launch(Dispatchers.IO) { service?.stopAll() }", UI)

    def test_running_party_cannot_be_started_twice(self):
        self.assertIn("pidx in runningPidx", SERVICE)


if __name__ == "__main__":
    unittest.main()
