import re
import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "android/app/src/main/java/com/tsbot/android/MainActivity.kt"
).read_text(encoding="utf-8")


class TestAndroidAccountEditSplit(unittest.TestCase):
    def test_account_row_exposes_credentials_heal_and_skill_actions(self):
        row = re.search(
            r"fun AccountRow\((.*?)\n}\n\n@Composable",
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(row)
        body = row.group(1)
        self.assertIn("onEditHeal", body)
        self.assertIn("onEditSkill", body)
        self.assertIn('contentDescription = "Hồi HP SP"', body)
        self.assertRegex(body, r'Text\("Skill"[,)]')

    def test_credentials_dialog_does_not_include_heal_or_skill_editors(self):
        credentials = re.search(
            r"fun AddAccountDialog\((.*?)\n}\n\n@Composable\nfun HealSettingsDialog",
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(credentials)
        body = credentials.group(1)
        self.assertNotIn("hpCharText", body)
        self.assertNotIn("BattleRuleUnitEditor", body)

    def test_separate_heal_and_skill_dialogs_are_wired(self):
        self.assertIn("fun HealSettingsDialog(", SOURCE)
        self.assertIn("fun SkillSettingsDialog(", SOURCE)
        self.assertIn("editingHealAccount", SOURCE)
        self.assertIn("editingSkillAccount", SOURCE)
        self.assertIn("account.copy(heal = editedHeal)", SOURCE)
        self.assertIn("account.copy(battleJson = editedBattleJson)", SOURCE)


if __name__ == "__main__":
    unittest.main()
