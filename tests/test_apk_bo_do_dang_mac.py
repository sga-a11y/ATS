"""Tui do APK: do dang mac + bo do + dong chi so (mirror gui.py::BagDialog)."""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

sys.argv = [sys.argv[0]]        # run_party_digioi doc int(sys.argv[1]) o muc module
import run_party_digioi as R  # noqa: E402
from bot import outfit_stats as OS  # noqa: E402


class _St:
    carried_pets = [(111, "Heo"), (222, "Cho")]
    in_battle = False
    char = None


class _C:
    OUTFIT_FITS = (1, 2, 3, 4, 5, 6)

    def __init__(self):
        self.state = _St()
        self.active_pet_slot = 2
        self.equip_by_fit = {3: 0x5854, 1: 0}
        self.pet_equip_by_fit = {1: {2: 0x52dd}}
        self.equipped_items = []
        self.bag_slots = {}
        self.char_level = 50
        self.char_attrs = {}
        self.goi = []

    def char_stat_full(self):
        return {27: 10, 28: 20, 29: 30, 31: 5, 32: 5, 30: 7}

    def pet_stats(self, i):
        return {"level": 9, "int": 1, "atk": 2}

    def _bag_slot_best(self, tid):
        return None

    def queue_bag_cmd(self, ten, fn):
        return False

    def unequip_item(self, fit, follow=0):
        self.goi.append(("unequip", fit, follow))
        return True

    def apply_outfit(self, bo):
        self.goi.append(("wear", bo))
        return 1, []


class TestBagEquip(unittest.TestCase):
    def setUp(self):
        self.c = _C()
        R.account_clients["u9"] = self.c
        self.luu = {}
        p1 = mock.patch.object(R, "load_outfits",
                               lambda u=None, d=None: dict(self.luu.get(d) or {}))
        p2 = mock.patch.object(R, "save_outfit", self._save)
        p1.start(); p2.start()
        self.addCleanup(p1.stop); self.addCleanup(p2.stop)
        self.addCleanup(lambda: R.account_clients.pop("u9", None))

    def _save(self, u, d, ten, bo):
        if bo is None:
            self.luu.get(d, {}).pop(ten, None)
        else:
            self.luu.setdefault(d, {})[ten] = dict(bo)

    def test_info_char_va_pet(self):
        i = R.bag_equip_info("u9", 0)
        self.assertTrue(i["live"])
        self.assertEqual([t[0] for t in i["targets"]], [0, 1, 2])
        self.assertTrue(i["targets"][2][1].endswith("★"))
        self.assertEqual(list(i["equip"]), ["3"])          # o trong (tid 0) khong hien
        self.assertIn("INT 10", i["stats"])
        self.assertEqual(list(R.bag_equip_info("u9", 1)["equip"]), ["2"])

    def test_acc_tat_van_xem_bo(self):
        self.luu["char"] = {"A": {"3": 0x5854}}
        i = R.bag_equip_info("khong-chay", 0)
        self.assertFalse(i["live"])
        self.assertEqual(i["equip"], {})
        self.assertIn("A", i["outfits"])

    def test_luu_moi_mac_xoa(self):
        self.assertEqual(R.bag_outfit_cmd("u9", 0, "save_new", "A"), "True")
        self.assertEqual(self.luu["char"]["A"], {3: 0x5854})
        self.assertEqual(R.bag_outfit_cmd("u9", 1, "save", "P", bo_json='{"2": 21}'), "True")
        self.assertIn("P", self.luu["pet1"])
        self.assertEqual(R.bag_outfit_cmd("u9", 1, "wear", "P"), "True")
        self.assertEqual(self.c.goi[-1], ("wear", {"pets": {1: {2: 21}}}))
        self.assertEqual(R.bag_outfit_cmd("u9", 0, "unequip", fit=3), "True")
        self.assertEqual(self.c.goi[-1], ("unequip", 3, 0))
        R.bag_outfit_cmd("u9", 0, "delete", "A")
        self.assertNotIn("A", self.luu["char"])

    def test_lenh_la(self):
        self.assertTrue(R.bag_outfit_cmd("u9", 0, "hack").startswith("False"))

    def test_delta(self):
        s = R.bag_outfit_delta("u9", 0, "{}")
        self.assertTrue(s.startswith("Nếu mặc bộ này"))
        self.assertEqual(R.bag_outfit_delta("khong-chay", 0, "{}"), "")

    def test_cong_mon_ban_mau(self):
        # a1v lech 100 -> cong (v - 100)
        with mock.patch.object(OS, "_load_gamedata_items",
                               return_value={7: {"a1k": 210, "a1v": 115}}):
            self.assertEqual(OS.cong_cua_mon(7, None), {210: 15})


class TestKotlin(unittest.TestCase):
    def test_ui_co_do_dang_mac_va_bo(self):
        s = open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                              "android", "MainActivity.kt"), encoding="utf-8").read()
        for x in ("Trang bị đang mặc", "Mặc bộ này", "Lưu thành bộ mới", "Cởi ra",
                  "Đặt vào bộ", "onOutfitDelta", 'chay("equip", who)'):
            self.assertIn(x, s)


if __name__ == "__main__":
    unittest.main()
