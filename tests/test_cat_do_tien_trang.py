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

    # Gia lap server: co mo thoai NPC / co mo kho khong (de test ca hai nhanh hong).
    tu_mo_su_kien = True
    tu_mo_kho = True

    def __init__(self):
        self.sent = []
        self.running = True
        self._label = "test"
        self.bag_slots = {}
        self.current_map = C.GameClient.TRAC_QUAN_CITY
        self.bank_fail = None
        self.event_dang_mo = False
        self.bank_open = False
        self.bank_slots = {}
        self.role_counts = {}       # bag_capacity() that doc bang nay
        self.pos = (0, 0)
        self.di_toi = []

    def send(self, op, payload=b""):
        self.sent.append((op, bytes(payload)))
        # Server that (theo capture): ClickNpc -> S:020-001 (su kien mo);
        # <事件下一步> -> S:030-001 (kho mo).
        if op == 0x14 and payload[:2] == b"\x01\x00" and self.tu_mo_su_kien:
            self.event_dang_mo = True
        elif op == 0x14 and payload[:2] == b"\x06\x00" and self.tu_mo_kho:
            self.bank_open = True

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
        # Ghi mot MOC vao chinh chuoi goi de test kiem duoc THU TU: dong su kien phai xay ra
        # TRUOC khi tele (tele luc dang ban la chet).
        self.sent.append(("TELE", city))
        self.current_map = city
        return True


class TestHangSo(unittest.TestCase):
    def test_dung_scene_npc_va_ma_muc(self):
        self.assertEqual(C.GameClient.TIEN_TRANG_MAP, 12263)
        self.assertEqual(C.GameClient.TIEN_TRANG_NPC, 1)      # Eve_NpcData.id, KHONG phai npcId
        # KHONG con hang so "ma chon muc": capture that cho thay NPC nay chi mot nhanh, client
        # gui `0x14 sub0600` (<事件下一步>) chu khong he gui lenh chon muc nao.
        self.assertFalse(hasattr(C.GameClient, "TIEN_TRANG_MUC"))
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
        kq = self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertEqual(kq["cat"], 1)
        self.assertEqual(kq["so_luong"], 40, "phai cat CA STACK")
        cat = [p for op, p in self.c.sent if op == 0x1E and p[:2] == b"\x02\x00"]
        self.assertEqual(len(cat), 1)
        # sub(2) + slot(1) + so luong(4 LE)
        self.assertEqual(cat[0], b"\x02\x00" + bytes([5]) + struct.pack("<i", 40))

    def test_mo_thoai_npc_bang_ClickNpc(self):
        """`C:020 <事件觸發>` voi triggerKind = EEventTrigger.ClickNpc = 1.

        mainKind 20 la 0x14 -> `0x14 sub0100 + [id u16]`. Ban dau em tuong 0x20 la lenh mo NPC
        va gui `0x20 02 00 01` (id NPC vao day) - sai: capture cho thay payload luon la 08, y
        het sell_noi_dat, con id NPC di trong goi 0x14.
        """
        self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertIn((0x14, b"\x01\x00" + struct.pack("<H", 1)), self.c.sent)
        self.assertIn((0x20, b"\x02\x00\x08"), self.c.sent)

    def test_chuoi_mo_dung_capture_that(self):
        """captures/tien_trang_cat_do_20260904.pcap:
        0x20 sub0200 08 -> 0x14 sub0100 [id u16] -> (su kien mo) -> 0x14 sub0600 -> kho mo.
        """
        self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertIn((0x20, b"\x02\x00\x08"), self.c.sent)
        self.assertIn((0x14, b"\x01\x00" + struct.pack("<H", 1)), self.c.sent)
        self.assertIn((0x14, b"\x06\x00"), self.c.sent)

    def test_KHONG_BAO_GIO_gui_lenh_chon_muc(self):
        """Chinh goi nay lam ROT ACC tp605 (server: "su kien vi pham" ma 5).

        NPC tien trang khong co menu -> gui `C:020-009 <事件選擇>` la thao tac khong ton tai.
        """
        self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        subs = [p[:2] for op, p in self.c.sent if op == 0x14]
        self.assertNotIn(b"\x09\x00", subs)

    def test_NPC_khong_mo_thoai_thi_DUNG_LAI(self):
        self.c.tu_mo_su_kien = False
        kq = self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertEqual(kq["bo_qua"], "NPC khong mo thoai")
        self.assertEqual(kq["cat"], 0)
        self.assertNotIn(0x1E, [op for op, _p in self.c.sent], "chua mo kho ma da ban lenh cat")

    def test_kho_khong_mo_thi_DUNG_LAI(self):
        """Thoai chay nhung `S:030-001` khong ve -> cat luc nay la ban vao khoang khong."""
        self.c.tu_mo_kho = False
        kq = self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertEqual(kq["bo_qua"], "tien trang khong mo")
        self.assertEqual(kq["cat"], 0)

    def test_nhanh_HONG_cung_phai_dong_su_kien_TRUOC_khi_tele(self):
        """User chot 04/09: "dang ban ma cho tele luon thi cung chet".

        Nhanh hong giua chung (su kien mo nhung kho khong mo) van dang BAN -> phai gui
        `0x14 sub0600` dong su kien TRUOC khi go_to_town.
        """
        self.c.tu_mo_kho = False
        self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        _ops = self.c.sent
        self.assertIn((0x14, b"\x06\x00"), _ops, "khong dong su kien truoc khi roi di")
        _i_dong = _ops.index((0x14, b"\x06\x00"))
        _i_tele = next(i for i, x in enumerate(_ops) if x[0] == "TELE")
        self.assertLess(_i_dong, _i_tele, "TELE khi con dang ban (chua dong su kien) = chet")

    def test_dong_kho_ROI_dong_ca_SU_KIEN(self):
        """Ca hai capture 04/09: `0x1e sub0800` roi NGAY `0x14 sub0600`.

        Dang mo tien trang thi SERVER coi la DANG BAN: khong moi party duoc, khong nhan loi moi.
        Bot chay party ma quen buoc nay thi acc do ket ngoai party mai, ca party dung cho.
        """
        self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        goi = [x for x in self.c.sent if x[0] != "TELE"]      # bo moc tele cua client gia
        self.assertEqual(goi[-2:], [(0x1E, b"\x08\x00"), (0x14, b"\x06\x00")])

    def test_di_dung_map_va_toa_do(self):
        self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertEqual(self.c.di_toi, [(12001, 12263, (390, 310))])
        self.assertEqual(self.c.pos, (390, 310))

    def test_ve_lai_trac_quan(self):
        self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertEqual(self.c.current_map, C.GameClient.TRAC_QUAN_CITY,
                         "khong ve thanh thi buoc tele ke tiep xuat phat sai cho")

    def test_khong_o_trac_quan_thi_bo_qua(self):
        self.c.current_map = 12061
        kq = self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
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
        kq = self.c.cat_do_tien_trang({"0x7d2b": C.CAT_DO_CAT})
        self.assertEqual(kq["cat"], 1, "phai dung ngay sau mon dau")
        self.assertEqual(kq["bo_qua"], "tien trang day")


class TestLayDoRa(unittest.TestCase):
    """Bo tick = LAY RA khoi tien trang (user chot 04/09). Cung mot chuyen di voi cat."""

    def setUp(self):
        self.c = _Gia()
        self.c.bag_slots = {5: [0x7D2B, 40]}
        # Kho: doc that tu captures/tien_trang_lay_do_20260904.pcap
        self.c.bank_slots = {3: (0xB3E2, 1), 4: (0xB49F, 7), 5: (0xB4A1, 6)}

    def test_goi_lay_dung_bo_cuc(self):
        """`C:030-001 <錢莊領物品>` = 0x1e sub0100 + [idx trong KHO][so luong u32]."""
        kq = self.c.cat_do_tien_trang({"0xb49f": C.CAT_DO_LAY})
        lay = [p for op, p in self.c.sent if op == 0x1E and p[:2] == b"\x01\x00"]
        self.assertEqual(len(lay), 1)
        self.assertEqual(lay[0], b"\x01\x00" + bytes([4]) + struct.pack("<I", 7))
        self.assertEqual((kq["lay"], kq["lay_so_luong"]), (1, 7))

    def test_an_INDEX_KHO_khong_phai_slot_tui(self):
        """Nham cai nay la rut NHAM mon: idx 4 la vi tri trong kho, khong lien quan slot tui."""
        self.c.cat_do_tien_trang({"0xb4a1": C.CAT_DO_LAY})
        lay = [p for op, p in self.c.sent if op == 0x1E and p[:2] == b"\x01\x00"]
        self.assertEqual(lay[0][2], 5, "phai la idx trong kho cua 0xb4a1")

    def test_mon_khong_trong_list_thi_KHONG_dung_toi(self):
        """Xoa dong = bot thoi dung toi. Kho co 3 mon nhung list chi ke mot."""
        self.c.cat_do_tien_trang({"0xb49f": C.CAT_DO_LAY})
        lay = [p for op, p in self.c.sent if op == 0x1E and p[:2] == b"\x01\x00"]
        self.assertEqual(len(lay), 1, "rut ca mon khong co trong list")

    def test_mon_danh_dau_CAT_thi_khong_bi_rut_ra(self):
        self.c.cat_do_tien_trang({"0xb49f": C.CAT_DO_CAT})
        lay = [p for op, p in self.c.sent if op == 0x1E and p[:2] == b"\x01\x00"]
        self.assertEqual(lay, [])

    def test_tui_day_thi_khong_rut_them(self):
        self.c.bag_slots = {i: [0x1000 + i, 1] for i in range(200)}   # cap = 200 -> day
        kq = self.c.cat_do_tien_trang({"0xb49f": C.CAT_DO_LAY})
        self.assertEqual(kq["lay"], 0)

    def test_doc_kho_tu_capture_that(self):
        c = _Gia()
        import binascii
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "captures", "tien_trang_lay_do_20260904.pcap"), "rb"):
            pass    # chi de chac file capture con trong repo
        # 2 ban ghi dau cua S:030-001 that (36B/ban ghi: idx + tid u16 + count u32 + 29B)
        d = binascii.unhexlify(
            "01" + "c57e" + "01000000" + "00" * 29 +
            "02" + "efb5" + "01000000" + "00" * 29)
        c.bank_slots = {}
        c._doc_kho_tien_trang(d)
        self.assertEqual(c.bank_slots, {1: (0x7EC5, 1), 2: (0xB5EF, 1)})


class TestLocRestrict(unittest.TestCase):
    def test_mon_bi_cam_gui_ngan_hang_thi_bo_qua(self):
        """restrict & 32 -> client chan; bot gui la thao tac khong hop le."""
        c = _Gia()
        c.bag_slots = {3: [0x1234, 5]}
        goc = C._load_gamedata_items()
        goc[0x1234] = {"name": "mon cam", "restrict": 32}
        try:
            self.assertEqual(c._cat_do_slots({"0x1234": C.CAT_DO_CAT}), [])
            goc[0x1234]["restrict"] = 0
            self.assertEqual(c._cat_do_slots({"0x1234": C.CAT_DO_CAT}), [(3, 0x1234, 5)])
        finally:
            goc.pop(0x1234, None)


class TestListChung(unittest.TestCase):
    """User chot 04/09: "lam 1 list chung cho tat ca cac bot thoi, the cho nhe bot".

    List nam o MOT file `cat_do_items.json` (bot tu sinh, nhu checkin_state.json), KHONG con
    nhan ban trong tung party cua accounts.json.
    """

    def setUp(self):
        import shutil
        import tempfile
        self.d = tempfile.mkdtemp()
        self._cu = C._cat_do_path
        C._cat_do_path = lambda: os.path.join(self.d, "cat_do_items.json")
        self._shutil = shutil

    def tearDown(self):
        C._cat_do_path = self._cu
        self._shutil.rmtree(self.d, ignore_errors=True)

    def test_chua_co_file_thi_dung_mac_dinh(self):
        self.assertEqual(C.load_cat_do_items(), dict(C.CAT_DO_MAC_DINH))

    def test_hai_mon_mac_dinh_that_su_cat_duoc(self):
        """Mac dinh ma trung mon `restrict & 32` thi bot se bo qua -> list vo nghia."""
        self.assertEqual(set(C.CAT_DO_MAC_DINH), {"0xb3e2", "0xb49f"})
        gd = C._load_gamedata_items()
        for k in C.CAT_DO_MAC_DINH:
            rec = gd.get(int(k, 16)) or {}
            self.assertTrue(rec.get("name"), "%s khong co trong items_gamedata" % k)
            self.assertFalse(int(rec.get("restrict", 0) or 0) & C.GameClient.BANK_RESTRICT_CAM,
                             "%s (%s) bi game cam gui ngan hang" % (k, rec.get("name")))

    def test_ghi_roi_doc_lai(self):
        self.assertTrue(C.save_cat_do_items({"0x522b": C.CAT_DO_LAY}))
        self.assertEqual(C.load_cat_do_items(), {"0x522b": C.CAT_DO_LAY})

    def test_doc_duoc_FILE_DANG_CU(self):
        """File da luu truoc do dung {tid: true}. Doc phai ra "cat", khong duoc mat mon."""
        with open(C._cat_do_path(), "w", encoding="utf-8") as fh:
            fh.write('{"items": {"0xb3e2": true, "0x522b": false}}')
        self.assertEqual(C.load_cat_do_items(),
                         {"0xb3e2": C.CAT_DO_CAT, "0x522b": C.CAT_DO_LAY})

    def test_file_rong_thi_ton_trong(self):
        """Bo tick het la CO Y - khong duoc nhoi lai mac dinh."""
        C.save_cat_do_items({})
        self.assertEqual(C.load_cat_do_items(), {})

    def test_khong_con_luu_trong_party(self):
        """Khoa cu `cat_do_items` phai bien khoi config/runner/gui - khong thi hai nguon lech nhau."""
        for f in (os.path.join("bot", "config.py"), "run_party_digioi.py"):
            self.assertNotIn('"cat_do_items"', _doc(f), "%s van luu list theo party" % f)

    def test_bot_doc_thang_file_chung(self):
        """cat_do_tien_trang khong truyen `chon` thi phai tu doc file chung."""
        C.save_cat_do_items({"0x7d2b": C.CAT_DO_CAT})
        c = _Gia()
        c.bag_slots = {5: [0x7D2B, 3]}
        kq = c.cat_do_tien_trang()
        self.assertEqual(kq["cat"], 1)


class TestThemTuTuiDo(unittest.TestCase):
    """THEM mon vao list tu TUI DO, BO thi vao "List cất" (user chot 04/09).

    Ly do: dialog List cat chi TIM theo ten -> mon la thi go mai khong ra, bo tick nham la coi
    nhu mat ("t lo bo tick cai la gio ko co cach nao de tick lai").
    """

    def setUp(self):
        import shutil
        import tempfile
        self.gui = _import_gui()
        self.d = tempfile.mkdtemp()
        self._cu = C._cat_do_path
        C._cat_do_path = lambda: os.path.join(self.d, "cat_do_items.json")
        self._shutil = shutil

    def tearDown(self):
        C._cat_do_path = self._cu
        self._shutil.rmtree(self.d, ignore_errors=True)

    def test_them_moi_va_giu_mac_dinh(self):
        ok, tin = self.gui.them_vao_list_cat_do(0x522B)
        self.assertTrue(ok, tin)
        ds = C.load_cat_do_items()
        self.assertTrue(ds.get("0x522b"))
        for k in C.CAT_DO_MAC_DINH:
            self.assertTrue(ds.get(k), "them mot mon lam mat mon mac dinh %s" % k)

    def test_khong_them_trung(self):
        self.gui.them_vao_list_cat_do(0x522B)
        ok, tin = self.gui.them_vao_list_cat_do(0x522B)
        self.assertFalse(ok)
        self.assertIn("đã có", tin)

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

    def test_runner_gan_vao_client(self):
        src = _doc("run_party_digioi.py")
        self.assertRegex(src, r"c\.auto_cat_do\s*=")

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
