import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")


class TestAndroidTrainMapCollapsible(unittest.TestCase):
    def test_train_map_groups_can_be_collapsed_without_closing_menu(self):
        self.assertIn("collapsedTrainMapGroups", UI)
        self.assertIn("toggleTrainMapGroup", UI)
        # Truoc day neo y nguyen dong "if (g !in collapsedTrainMapGroups)". Nay da refactor thanh
        # bien `collapsed` (co them mien tru khi dang TIM MAP: dang search thi bung het nhom).
        # Tinh nang van con -> neo theo Y NGHIA: co quyet dinh collapsed tu tap, va noi dung nhom
        # chi ve khi KHONG collapsed.
        self.assertRegex(UI, r"val collapsed = .*g in collapsedTrainMapGroups")
        self.assertIn("if (!collapsed) {", UI)
        # bam vao nhom phai TOGGLE chu khong dong menu
        self.assertRegex(UI, r"onClick = \{ toggleTrainMapGroup\(g\) \}")
        self.assertNotIn("DropdownMenuItem(enabled = false, onClick = {},\n                                        text = { Text(\"📁 $g\") })", UI)


if __name__ == "__main__":
    unittest.main()
