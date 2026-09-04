# -*- coding: utf-8 -*-
"""APK phai co man CAY SKILL nhan vat (truoc do chi co nut "Battle" = bang chien dau).

Doc THANG file .kt: `gradlew compileReleaseKotlin` chi noi code BIEN DICH DUOC, khong noi no
con noi dung sang Python (bai hoc da ghi trong CLAUDE.md).
"""
import os
import re
import sys
import unittest

_GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _GOC)

_KTDIR = os.path.join(_GOC, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _doc(p):
    with open(os.path.join(_GOC, p), encoding="utf-8") as fh:
        return fh.read()


def _kt(name):
    with open(os.path.join(_KTDIR, name), encoding="utf-8") as fh:
        return fh.read()


class TestGiaoDien(unittest.TestCase):
    def test_co_dialog_va_duoc_hien(self):
        src = _kt("MainActivity.kt")
        self.assertIn("fun SkillTreeDialog(", src)
        self.assertRegex(src, r"\n\s+SkillTreeDialog\(", "dinh nghia roi nhung KHONG hien")

    def test_co_nut_skill_rieng_khac_nut_battle(self):
        """Nut "Battle" san co la bang CHIEN DAU - khong phai cay skill. Phai co nut rieng."""
        src = _kt("MainActivity.kt")
        self.assertIn('Text("Skill", maxLines = 1)', src)
        self.assertIn('Text("Battle", maxLines = 1)', src)
        self.assertIn("onEditSkillTree", src)

    def test_tab_khop_ban_PC(self):
        """Tab va quy uoc phai khop gui.py::SkillDialog - lech la user thay cay khac nhau."""
        src = _kt("MainActivity.kt")
        for k in ("Earth", "Water", "Fire", "Wind", "Mind", "Turn1"):
            self.assertIn('"%s"' % k, src)
        # Game CHUA MO cay LightDark -> khong duoc hien tab do
        self.assertNotRegex(src, r'Triple\("LightDark"')
        # Tab Tam chi hien skill DA HOC (104 skill sinh hoat, hien het thi khong tim noi)
        self.assertIn("SkillTabsChiHienDaHoc", src)

    def test_gia_hoc_gap_doi_khi_khac_he(self):
        """Luat cua client: hoc skill KHAC HE cua char thi learnPt GAP DOI."""
        src = _kt("MainActivity.kt")
        m = re.search(r"val giaHoc = .*?sk\.learnPt \* 2", src, re.S)
        self.assertIsNotNone(m, "khong thay cho nhan doi gia hoc khi khac he")

    def test_acc_tat_thi_khong_nang_duoc(self):
        """Acc TAT doc so tu cache - bam Nang cung khong gui duoc goi nao."""
        src = _kt("MainActivity.kt")
        self.assertIn("enabled = !tuCache && c < sk.maxLv", src)


class TestCauNoiSangPython(unittest.TestCase):
    def test_service_co_ba_cau_noi(self):
        src = _kt("BotForegroundService.kt")
        for f, py in (("skillCharInfoJson", "skill_char_info"),
                      ("upgradeSkill", "nang_skill_ngay"),
                      ("applySkillConfig", "apply_skill_config_json")):
            self.assertIn("fun %s(" % f, src, "thieu cau noi %s" % f)
            self.assertIn('"%s"' % py, src, "%s khong goi dung ham python" % f)

    def test_python_co_wrapper_nhan_chuoi(self):
        """Kotlin chi truyen duoc CHUOI; apply_skill_config ban PC nhan dict."""
        src = _doc("run_party_digioi.py")
        self.assertIn("def apply_skill_config_json(", src)
        self.assertIn("def apply_skill_config(", src)
        m = re.search(r"def apply_skill_config\(username, cfg\):", src)
        self.assertIsNotNone(m, "khong duoc doi chu ky apply_skill_config (dung chung voi PC)")

    def test_bang_tu_nang_duoc_bom_luc_khoi_dong(self):
        """Thieu doan nay thi bang co luu nhung bot KHONG BAO GIO nang, va khong co log nao bao."""
        src = _kt("BotForegroundService.kt")
        self.assertIn("apply_skill_config_json", src)
        self.assertIn("acc.skillJson", src)

    def test_rules_luu_dang_MANG_giong_PC(self):
        """PC luu rules = [[skill_id, cap], ...]. Luu thanh object la ban PC doc khong ra."""
        src = _kt("MainActivity.kt")
        m = re.search(r"fun skillRulesJson\(.*?\n\}\.toString\(\)", src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("put(JSONArray()", m.group(0))


class TestLuuTru(unittest.TestCase):
    def test_account_co_skill_json(self):
        self.assertRegex(_kt("Account.kt"), r"val skillJson: String")

    def test_partystore_doc_va_ghi(self):
        src = _kt("PartyStore.kt")
        self.assertIn('optString("skill", "")', src)
        self.assertIn('put("skill", a.skillJson)', src)

    def test_asset_skill_da_khai_bao(self):
        """APK doc skills_data.json tu assets -> phai co trong SHARED_ASSETS."""
        self.assertIn("skills_data.json", _kt("MainActivity.kt"))
        self.assertIn('"skills_data.json"', _doc(os.path.join("tools", "sync_apk_python.py")))


if __name__ == "__main__":
    unittest.main()
