import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(encoding="utf-8")
STORE = (ROOT / "android/app/src/main/java/com/tsbot/android/PartyStore.kt").read_text(encoding="utf-8")


class TestAndroidHealAllAndSkillSections(unittest.TestCase):
    def test_skill_editor_has_distinct_character_and_pet_section_labels(self):
        self.assertIn('"NHÂN VẬT (CHAR)"', UI)
        self.assertIn('"PET ĐANG DÙNG"', UI)
        self.assertIn("primaryContainer", UI)
        self.assertIn("tertiaryContainer", UI)
        self.assertIn("color = sectionColor.copy(alpha = 0.14f)", UI)

    def test_heal_dialog_can_apply_current_values_to_every_account(self):
        self.assertIn("fun applyHealToAllAccounts(heal: HealSettings): Int", STORE)
        self.assertIn("it.copy(heal = heal)", STORE)
        self.assertIn('Text("Áp dụng cho tất cả acc")', UI)
        self.assertIn("onApplyToAll(currentHeal())", UI)
        self.assertIn("partyStore.applyHealToAllAccounts(heal)", UI)


if __name__ == "__main__":
    unittest.main()
