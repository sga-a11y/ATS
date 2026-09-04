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


def _import_gui():
    """Import gui an toan trong test.

    `gui` import `run_party_digioi`, module do doc `int(sys.argv[1])` ngay o muc module (so phut
    chay). Duoi unittest thi argv[1] la 'discover'/ten test -> ValueError ngay luc import.
    """
    _cu = sys.argv
    sys.argv = [_cu[0]]
    try:
        import gui
        return gui
    finally:
        sys.argv = _cu


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


class TestListMacDinh(unittest.TestCase):
    """User chot 04/09: "tam thoi cho 2 item nay vao list cat"."""

    def test_hai_mon_mac_dinh(self):
        self.assertEqual(set(C.GameClient.CAT_DO_MAC_DINH), {"0xb3e2", "0xb49f"})

    def test_hai_mon_that_su_cat_duoc(self):
        """Mac dinh ma trung mon `restrict & 32` thi bot se bo qua -> list vo nghia."""
        gd = C._load_gamedata_items()
        for k in C.GameClient.CAT_DO_MAC_DINH:
            rec = gd.get(int(k, 16)) or {}
            self.assertTrue(rec.get("name"), "%s khong co trong items_gamedata" % k)
            self.assertFalse(int(rec.get("restrict", 0) or 0) & C.GameClient.BANK_RESTRICT_CAM,
                             "%s (%s) bi game cam gui ngan hang" % (k, rec.get("name")))

    def test_config_nap_duoc_mac_dinh(self):
        """Bay da dinh 04/09: import GameClient o MUC MODULE trong config.py thi vong import lam
        no tra ve RONG am tham - mac dinh chet ma khong ai bao."""
        from bot import config as _cfg
        self.assertEqual(_cfg._cat_do_mac_dinh(), dict(C.GameClient.CAT_DO_MAC_DINH))

    def test_ton_trong_lua_chon_cua_user(self):
        """Co khoa roi thi giu nguyen van, KE CA RONG - bo tick het la co y."""
        gui = _import_gui()
        self.assertEqual(gui._cat_do_mac_dinh({}), dict(C.GameClient.CAT_DO_MAC_DINH))
        self.assertEqual(gui._cat_do_mac_dinh({"cat_do_items": {}}), {})
        self.assertEqual(gui._cat_do_mac_dinh({"cat_do_items": {"0x1": True}}), {"0x1": True})


class TestThemTuTuiDo(unittest.TestCase):
    """Luong user chot 04/09: THEM mon vao list tu TUI DO, BO thi vao "List cất".

    Ly do: dialog List cat chi TIM theo ten -> mon la thi go mai khong ra, bo tick nham la coi
    nhu mat ("t lo bo tick cai la gio ko co cach nao de tick lai").
    """

    def setUp(self):
        import shutil
        import tempfile
        gui = _import_gui()
        self.gui = gui
        self._cu = gui.ACCOUNTS_JSON
        self.d = tempfile.mkdtemp()
        gui.ACCOUNTS_JSON = os.path.join(self.d, "accounts.json")
        prof = {"active": "A", "profiles": {
            "A": {"parties": [{"accounts": [{"u": "u1"}]}]},
            "B": {"parties": [{"accounts": [{"u": "u1"}], "cat_do_items": {}}]},
        }}
        gui._save_profiles(prof)
        self._shutil = shutil

    def tearDown(self):
        self.gui.ACCOUNTS_JSON = self._cu
        self._shutil.rmtree(self.d, ignore_errors=True)

    def _doc(self, ten):
        return (self.gui._load_profiles()["profiles"][ten]["parties"][0].get("cat_do_items"))

    def test_them_moi_va_giu_mac_dinh(self):
        ok, ten = self.gui.them_vao_list_cat_do("u1", 0x522B)
        self.assertTrue(ok)
        self.assertEqual(ten, "A")
        ds = self._doc("A")
        self.assertTrue(ds.get("0x522b"))
        # Party chua tung co khoa -> dang chay theo MAC DINH; ghi ra phai giu lai, khong thi
        # bam mot nut la mat hai mon mac dinh.
        for k in C.GameClient.CAT_DO_MAC_DINH:
            self.assertTrue(ds.get(k), "ghi xong lam mat mon mac dinh %s" % k)

    def test_khong_them_trung(self):
        self.gui.them_vao_list_cat_do("u1", 0x522B)
        ok, tin = self.gui.them_vao_list_cat_do("u1", 0x522B)
        self.assertFalse(ok)
        self.assertIn("đã có", tin)

    def test_ghi_vao_cau_hinh_DANG_ACTIVE(self):
        """Acc nam o ca hai cau hinh -> phai ghi vao cai dang chay."""
        prof = self.gui._load_profiles()
        prof["active"] = "B"
        self.gui._save_profiles(prof)
        ok, ten = self.gui.them_vao_list_cat_do("u1", 0x522B)
        self.assertTrue(ok)
        self.assertEqual(ten, "B", "ghi vao cau hinh khong chay = bam nut khong co tac dung")
        self.assertIsNone(self._doc("A"))

    def test_acc_la_thi_bao_ro(self):
        ok, tin = self.gui.them_vao_list_cat_do("khong-co-acc-nay", 0x522B)
        self.assertFalse(ok)
        self.assertIn("không tìm thấy", tin)

    def test_ap_live_cho_acc_dang_chay(self):
        class _C:
            cat_do_items = {}
        c = _C()
        self.gui.them_vao_list_cat_do("u1", 0x522B, client=c)
        self.assertTrue(c.cat_do_items.get("0x522b"), "phai ap ngay, khong bat user restart")

    def test_tui_do_co_nut(self):
        src = _doc("gui.py")
        self.assertIn('"Tự cất vào tiền trang"', src)
        self.assertIn("_them_cat_do", src)
        # Mon game cam gui ngan hang thi KHONG duoc hien nut (them vao cung vo ich).
        m = re.search(r'acts\.append\(\("Tự cất vào tiền trang".*?\)\)', src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("_cam", src[max(0, m.start() - 400):m.start()])


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
        i_cat = src.index('text="Tự cất đồ vào Tiền trang"')
        i_rac = src.index('text="Tự vứt item rác (Ngọc Hư)"')
        self.assertLess(i_noi, i_cat)
        self.assertLess(i_cat, i_rac)


if __name__ == "__main__":
    unittest.main()
