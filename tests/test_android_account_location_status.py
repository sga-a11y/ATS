import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS = (ROOT / "android/app/src/main/java/com/tsbot/android/AccountStatus.kt").read_text(encoding="utf-8")
SERVICE = (ROOT / "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt").read_text(encoding="utf-8")
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")


class TestAndroidAccountLocationStatus(unittest.TestCase):
    def test_runtime_map_and_channel_are_carried_to_each_account_row(self):
        self.assertIn("val mapId: Int? = null", STATUS)
        self.assertIn("val channel: Int? = null", STATUS)
        self.assertIn('mapId = gInt("map")', SERVICE)
        self.assertIn('channel = gInt("channel")', SERVICE)
        self.assertIn('"Map: $mapLabel  •  Kênh: $channelLabel"', UI)

    def test_map_names_are_loaded_directly_from_bundled_data(self):
        self.assertIn("fun loadStatusMapNames(context: Context)", UI)
        self.assertIn('readMapAsset("train_maps.json")', UI)
        self.assertIn('readMapAsset("events.json")', UI)
        self.assertIn("remember(context) { loadStatusMapNames(context) }", UI)


if __name__ == "__main__":
    unittest.main()
