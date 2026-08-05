import unittest
from pathlib import Path

from bot import config


ROOT = Path(__file__).resolve().parents[1]
ANDROID_UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(
    encoding="utf-8"
)
ANDROID_PARTY = (ROOT / "android/app/src/main/java/com/tsbot/android/Party.kt").read_text(
    encoding="utf-8"
)
ANDROID_STORE = (ROOT / "android/app/src/main/java/com/tsbot/android/PartyStore.kt").read_text(
    encoding="utf-8"
)


class TestTeamDungeon110Config(unittest.TestCase):
    def test_pc_missing_setting_defaults_110_off(self):
        self.assertEqual(config.TEAM_DUNGEON_LEVELS, (20, 50, 80, 110))
        self.assertEqual(
            config.normalize_team_dungeons(None),
            {20: True, 50: True, 80: True, 110: False},
        )

    def test_pc_preserves_explicit_110_setting(self):
        self.assertTrue(config.normalize_team_dungeons({"110": True})[110])

    def test_android_ui_and_store_default_110_off(self):
        self.assertIn("private val TeamDungeonLevels = listOf(20, 50, 80, 110)", ANDROID_UI)
        self.assertIn("110 to (src[110] ?: false)", ANDROID_UI)
        self.assertIn("110 to false", ANDROID_PARTY)
        self.assertIn("110 to false", ANDROID_STORE)
        self.assertIn("listOf(20, 50, 80, 110)", ANDROID_STORE)


if __name__ == "__main__":
    unittest.main()
