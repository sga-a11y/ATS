"""Vai pet "pb_don" TACH RA KHOI "boss" (2026-08-22).

PB DON cho nhieu EXP nen user muon danh rieng mot con de don exp (cung y tuong voi chon pet van
tieu). Truoc day do_daily_dungeon dung CHUNG vai "boss" voi world boss / legion boss.

LUU Y de khoi hieu nham lai: nhan UI cu la "Quest/PB/Event" -> de tuong PB don nam trong nhom
quest. THUC TE no nam trong nhom BOSS. Nen viec tach la tach khoi "boss", KHONG phai khoi "quest".

Tuong thich nguoc (user chon): vai chua gan pet -> GIU NGUYEN pet dang dung, KHONG fallback sang
pet cua vai boss.
"""
import re
import unittest
from pathlib import Path

from bot.client import GameClient

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "bot" / "client.py").read_text(encoding="utf-8")


class _State:
    def __init__(self, cfg=None):
        self.battle_config = cfg or {}


def make_client(cfg=None):
    c = GameClient.__new__(GameClient)
    c._label = "pr"
    c.state = _State(cfg)
    c.switched = []
    c.switch_pet = lambda pid, wait=4.0: (c.switched.append(pid) or True)
    return c


class TestPetRolePbDon(unittest.TestCase):
    def test_pb_don_la_mot_vai_rieng(self):
        self.assertEqual(GameClient.PET_ROLES, ("train", "boss", "quest", "pb_don"))

    def test_PB_don_khong_con_dung_vai_boss(self):
        """do_daily_dungeon = PB DON. Truoc day gan @_pet_role("boss")."""
        m = re.search(r'@_pet_role\("([a-z_]+)"\)\s*\n\s*def do_daily_dungeon', SRC)
        self.assertIsNotNone(m, "khong tim thay decorator cua do_daily_dungeon")
        self.assertEqual(m.group(1), "pb_don")

    def test_cac_vai_KHAC_giu_nguyen(self):
        """Chi PB don doi vai. World boss / legion boss van la boss; quest + PB DOI van la quest."""
        for ham, vai in (("do_world_boss", "boss"), ("do_legion_boss", "boss"),
                         ("claim_daily_quests", "quest"), ("do_team_dungeon", "quest")):
            m = re.search(r'@_pet_role\("([a-z_]+)"\)\s*\n\s*def %s' % ham, SRC)
            self.assertIsNotNone(m, "khong thay decorator cua %s" % ham)
            self.assertEqual(m.group(1), vai, "%s doi vai ngoai y muon" % ham)

    def test_gan_pet_cho_pb_don_thi_doi_sang_con_do(self):
        c = make_client({"pet_roles": {"boss": 0x1111, "pb_don": 0x2222}})
        self.assertTrue(c.ensure_pet_role("pb_don"))
        self.assertEqual(c.switched, [0x2222])

    def test_CHUA_gan_pb_don_thi_GIU_pet_dang_dung(self):
        """User chon: KHONG fallback sang pet cua vai boss. Vai trong = khong doi pet."""
        c = make_client({"pet_roles": {"boss": 0x1111}})
        self.assertFalse(c.ensure_pet_role("pb_don"))
        self.assertEqual(c.switched, [], "da tu y doi pet du vai pb_don chua duoc gan")

    def test_config_CU_khong_co_pb_don_van_chay_binh_thuong(self):
        """Config user cu chi co train/boss/quest -> khong duoc no."""
        c = make_client({"pet_roles": {"train": 0x1, "boss": 0x2, "quest": 0x3}})
        self.assertFalse(c.ensure_pet_role("pb_don"))
        self.assertTrue(c.ensure_pet_role("boss"))
        self.assertEqual(c.switched, [0x2])

    def test_khong_co_pet_roles_gi_ca(self):
        self.assertFalse(make_client({}).ensure_pet_role("pb_don"))
        self.assertFalse(make_client(None).ensure_pet_role("pb_don"))


class TestPetRoleLabelsDongBo(unittest.TestCase):
    """Nhan UI PC va APK phai phu DU 4 vai va GIONG NHAU - day la 2 ban chep tay."""

    PC = (ROOT / "gui.py").read_text(encoding="utf-8")
    APK = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(
        encoding="utf-8")

    def test_ca_hai_ban_deu_co_du_4_vai(self):
        for ten, src in (("PC", self.PC), ("APK", self.APK)):
            for role in GameClient.PET_ROLES:
                self.assertIn('"%s"' % role, src, "%s thieu vai %s" % (ten, role))

    def test_nhan_quest_ghi_ro_la_PB_DOI(self):
        """Nhan cu "Quest/PB/Event" gay hieu nham PB DON nam trong nhom nay."""
        for ten, src in (("PC", self.PC), ("APK", self.APK)):
            self.assertIn("Quest/PB đội/Event", src, "%s con nhan cu" % ten)
            self.assertNotIn("Quest/PB/Event", src, "%s van con nhan cu gay nham" % ten)


if __name__ == "__main__":
    unittest.main()
