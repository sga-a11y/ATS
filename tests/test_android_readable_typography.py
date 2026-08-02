import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME = (ROOT / "android/app/src/main/java/com/tsbot/android/Theme.kt").read_text(encoding="utf-8")
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")


class TestAndroidReadableTypography(unittest.TestCase):
    def test_mobile_theme_uses_larger_readable_type_scale(self):
        self.assertIn("private val TsTypography", THEME)
        self.assertIn("bodyLarge = bodyLarge.copy(fontSize = 18.sp", THEME)
        self.assertIn("bodyMedium = bodyMedium.copy(fontSize = 16.sp", THEME)
        self.assertIn("labelLarge = labelLarge.copy(fontSize = 16.sp", THEME)
        self.assertIn("typography = TsTypography", THEME)

    def test_live_control_buttons_share_a_separate_full_width_row(self):
        self.assertIn('"Kênh hiện tại:', UI)
        self.assertGreaterEqual(UI.count("modifier = Modifier.weight(1f)"), 5)


if __name__ == "__main__":
    unittest.main()
