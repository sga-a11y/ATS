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
        self.assertIn("service?.startAll(parties)", UI)
        self.assertIn("fun startAll(parties: List<Party>)", SERVICE)
        self.assertIn('name = "aTSBot-start-all"', SERVICE)
        self.assertIn('py.callAttr("start_party", pidx)', SERVICE)

    def test_stop_all_runs_off_the_compose_thread(self):
        self.assertIn("scope.launch(Dispatchers.IO) { service?.stopAll() }", UI)

    def test_stop_all_reuses_the_working_stop_party_path(self):
        body = SERVICE.split("fun stopAll()", 1)[1].split("// --- lenh LIVE", 1)[0]
        self.assertIn("val partiesToStop", body)
        self.assertIn("partiesToStop.forEach { stopParty(it) }", body)
        self.assertNotIn('callAttr("stop_all")', body)

    def test_buttons_wait_for_service_and_stop_is_available_while_connecting(self):
        self.assertIn("enabled = service != null && totalAccounts > 0", UI)
        self.assertIn("enabled = service != null", UI)

    def test_running_party_cannot_be_started_twice(self):
        self.assertIn("pidx in runningPidx", SERVICE)


if __name__ == "__main__":
    unittest.main()
