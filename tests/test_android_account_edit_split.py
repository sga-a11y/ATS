import re
import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "android/app/src/main/java/com/tsbot/android/MainActivity.kt"
).read_text(encoding="utf-8")


def fun_body(name):
    """Cat than 1 @Composable: tu "fun <name>(" toi @Composable KE TIEP.

    Truoc day test neo bang regex doi 2 ham phai DINH NHAU (AddAccountDialog roi NGAY sau la
    @Composable fun HealSettingsDialog) -> chi can chen bat cu thu gi vao giua la test do, du
    tinh nang khong sao. Thuc te da chen "val FURNACE_TABS" -> hong. Bam theo CHINH ham thi
    khong con gion nhu vay.
    """
    i = SOURCE.index("fun %s(" % name)
    j = SOURCE.find("\n@Composable", i)
    return SOURCE[i:j if j != -1 else len(SOURCE)]


class TestAndroidAccountEditSplit(unittest.TestCase):
    def test_account_row_exposes_credentials_heal_and_skill_actions(self):
        body = fun_body("AccountRow")
        self.assertIn("onEditHeal", body)
        self.assertIn("onEditSkill", body)
        self.assertIn('contentDescription = "Hồi HP SP"', body)
        self.assertRegex(body, r'Text\("Skill"[,)]')

    def test_credentials_dialog_does_not_include_heal_or_skill_editors(self):
        body = fun_body("AddAccountDialog")
        self.assertNotIn("hpCharText", body)
        self.assertNotIn("BattleRuleUnitEditor", body)

    def test_separate_heal_and_skill_dialogs_are_wired(self):
        self.assertIn("fun HealSettingsDialog(", SOURCE)
        self.assertIn("fun SkillSettingsDialog(", SOURCE)
        self.assertIn("editingHealAccount", SOURCE)
        self.assertIn("editingSkillAccount", SOURCE)
        # heal nay luu KEM furnace trong cung 1 copy() -> dung regex thay vi doi chuoi y nguyen
        self.assertRegex(SOURCE, r"account\.copy\(heal = editedHeal[,)]")
        self.assertIn("account.copy(battleJson = editedBattleJson)", SOURCE)


if __name__ == "__main__":
    unittest.main()
