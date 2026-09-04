# -*- coding: utf-8 -*-
"""TU CAT DO VAO TIEN TRANG (錢莊) - user chot 04/09.

Goi va so lieu deu tra tu crack client, KHONG doan:
  Common_protocal.lua : C:030-002 <錢莊存物品> <<+索引(1) +數量(4)>> -> 0x1e sub0200
                        C:030-008 <關閉錢莊>                        -> 0x1e sub0800
                        S:030-007 <錢莊操作失敗> +失敗結果(1) [3 loi, 13 DAY]
  UI_UIBank.lua       : `索引` = bagIndex cua EThings.Bag = SLOT TUI DO; mon co restrict & 32
                        bi CLIENT CHAN khong cho cat.
  Eve.emg scene 12263 : NPC id=1 (npcId 16004); surface 1 muc 2 = ma 31 "Vat pham day du".
"""
import os
import re
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import client as C


def _doc(p):
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p),
              encoding="utf-8") as fh:
        return fh.read()


class _Gia(C.GameClient):
    """Client gia: ghi lai goi gui ra thay vi mo socket."""

    def __init__(self):
        self.sent = []
        self.running = True
        self._label = "test"
        self.bag_slots = {}
        self.current_map = C.GameClient.TRAC_QUAN_CITY
        self.bank_fail = None
        self.pos = (0, 0)
        self.di_toi = []

    def send(self, op, payload=b""):
        self.sent.append((op, bytes(payload)))

    def _wait_combat_clear(self, idle=1.0, cap=60.0):
        return True

    def follow_smart_scene_route(self, src, dst, safe=None, **kw):
        self.di_toi.append((src, dst, safe))
        self.current_map = dst
        return True

    def navigate_to(self, x, y, **kw):
        self.pos = (x, y)
        return True

    def go_to_town(self, city, flag=0, **kw):
        self.current_map = city
        return True


class TestHangSo(unittest.TestCase):
    def test_dung_scene_npc_va_ma_muc(self):
        self.assertEqual(C.GameClient.TIEN_TRANG_MAP, 12263)
        self.assertEqual(C.GameClient.TIEN_TRANG_NPC, 1)      # Eve_NpcData.id, KHONG phai npcId
        self.assertEqual(C.GameClient.TIEN_TRANG_MUC, 31)     # "Vat pham day du"
        self.assertEqual(C.GameClient.BANK_RESTRICT_CAM, 32)


class TestCatDo(unittest.TestCase):
    def setUp(self):
        self.c = _Gia()
        self.c.bag_slots = {5: [0x7D2B, 40], 9: [0x6A01, 7]}

    def test_khong_tick_gi_thi_khong_lam_gi(self):
        kq = self.c.cat_do_tien_trang({})
        self.assertEqual(kq["cat"], 0)
        self.assertEqual(self.c.sent, [], "chua tick ma da gui goi")

    def test_goi_cat_dung_bo_cuc(self):
        kq = self.c.cat_do_tien_trang({"0x7d2b": True})
        self.assertEqual(kq["cat"], 1)
        self.assertEqual(kq["so_luong"], 40, "phai cat CA STACK")
        cat = [p for op, p in self.c.sent if op == 0x1E and p[:2] == b"\x02\x00"]
        self.assertEqual(len(cat), 1)
        # sub(2) + slot(1) + so luong(4 LE)
        self.assertEqual(cat[0], b"\x02\x00" + bytes([5]) + struct.pack("<i", 40))

    def test_mo_thoai_npc_roi_chon_muc_31(self):
        self.c.cat_do_tien_trang({"0x7d2b": True})
        self.assertIn((0x20, b"\x02\x00" + bytes([1])), self.c.sent)
        self.assertIn((0x14, b"\x09\x00" + bytes([31])), self.c.sent)

    def test_dong_tien_trang_sau_khi_cat(self):
        self.c.cat_do_tien_trang({"0x7d2b": True})
        self.assertEqual(self.c.sent[-1], (0x1E, b"\x08\x00"))

    def test_di_dung_map_va_toa_do(self):
        self.c.cat_do_tien_trang({"0x7d2b": True})
        self.assertEqual(self.c.di_toi, [(12001, 12263, (390, 310))])
        self.assertEqual(self.c.pos, (390, 310))

    def test_ve_lai_trac_quan(self):
        self.c.cat_do_tien_trang({"0x7d2b": True})
        self.assertEqual(self.c.current_map, C.GameClient.TRAC_QUAN_CITY,
                         "khong ve thanh thi buoc tele ke tiep xuat phat sai cho")

    def test_khong_o_trac_quan_thi_bo_qua(self):
        self.c.current_map = 12061
        kq = self.c.cat_do_tien_trang({"0x7d2b": True})
        self.assertEqual(kq["cat"], 0)
        self.assertEqual(self.c.sent, [])

    def test_tien_trang_day_thi_dung_ngay(self):
        """S:030-007 ma 13 = DAY -> khong ban tiep ca chuc mon vao kho da day."""
        self.c.bag_slots = {i: [0x7D2B, 1] for i in range(1, 6)}
        _send = self.c.send

        def send(op, payload=b""):
            _send(op, payload)
            if op == 0x1E and payload[:2] == b"\x02\x00":
                self.c.bank_fail = 13       # server bao day ngay sau mon dau
        self.c.send = send
        kq = self.c.cat_do_tien_trang({"0x7d2b": True})
        self.assertEqual(kq["cat"], 1, "phai dung ngay sau mon dau")
        self.assertEqual(kq["bo_qua"], "tien trang day")


class TestLocRestrict(unittest.TestCase):
    def test_mon_bi_cam_gui_ngan_hang_thi_bo_qua(self):
        """restrict & 32 -> client chan; bot gui la thao tac khong hop le."""
        c = _Gia()
        c.bag_slots = {3: [0x1234, 5]}
        goc = C._load_gamedata_items()
        goc[0x1234] = {"name": "mon cam", "restrict": 32}
        try:
            self.assertEqual(c._cat_do_slots({"0x1234": True}), [])
            goc[0x1234]["restrict"] = 0
            self.assertEqual(c._cat_do_slots({"0x1234": True}), [(3, 0x1234, 5)])
        finally:
            goc.pop(0x1234, None)


class TestNoiDayDu(unittest.TestCase):
    """Tinh nang chi song khi noi du CA BA chang: config -> client -> cho boc 50-50."""

    def test_config_doc_hai_khoa(self):
        src = _doc(os.path.join("bot", "config.py"))
        self.assertIn("auto_cat_do", src)
        self.assertIn("cat_do_items", src)

    def test_runner_gan_vao_client(self):
        src = _doc("run_party_digioi.py")
        self.assertRegex(src, r"c\.auto_cat_do\s*=")
        self.assertRegex(src, r"c\.cat_do_items\s*=")

    def test_moc_o_pre_route_town_hop(self):
        """Phai goi trong pre_route_town_hop, nhanh Trac Quan."""
        src = _doc(os.path.join("bot", "client.py"))
        m = re.search(r"def pre_route_town_hop\(self\):\n(.*?)\n    def ", src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("cat_do_tien_trang", m.group(1))
        self.assertIn("TRAC_QUAN_CITY", m.group(1))

    def test_gui_co_tick_va_nut_list(self):
        src = _doc("gui.py")
        self.assertIn("auto_cat_do_var", src)
        self.assertIn("_open_cat_do_list", src)
        # Tick phai nam GIUA "Tu ban Noi dat" va "Tu vut item rac" (user chot vi tri).
        i_noi = src.index('text="Tự bán Nồi đất"')
        i_cat = src.index('text="Tự cất đồ vào Tiền trang (Trác Quận)"')
        i_rac = src.index('text="Tự vứt item rác (Ngọc Hư)"')
        self.assertLess(i_noi, i_cat)
        self.assertLess(i_cat, i_rac)


if __name__ == "__main__":
    unittest.main()
