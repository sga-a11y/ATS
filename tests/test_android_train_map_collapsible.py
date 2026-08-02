import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")


class TestAndroidTrainMapCollapsible(unittest.TestCase):
    def test_train_map_groups_can_be_collapsed_without_closing_menu(self):
        self.assertIn("collapsedTrainMapGroups", UI)
        self.assertIn("toggleTrainMapGroup", UI)
        self.assertIn("if (g !in collapsedTrainMapGroups)", UI)
        self.assertNotIn("DropdownMenuItem(enabled = false, onClick = {},\n                                        text = { Text(\"📁 $g\") })", UI)


if __name__ == "__main__":
    unittest.main()
