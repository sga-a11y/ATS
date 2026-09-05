"""Loan dau loi dai (亂鬥擂台) - solo, thu 3 20-22h.

Goi neo theo capture THAT `captures/loandau_20260825.pcap`; xem documents/LOAN_DAU.md.
"""
from __future__ import annotations

import datetime
import os
import re
import sys
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import loandau  # noqa: E402


def _goi(opcode, than_hex):
    """Dung goi that: header 7 byte `c0 91 [len 2B] 00 00 [opcode]` roi den than."""
    than = bytes.fromhex(than_hex)
    n = len(than) + 7
    return bytes([0xC0, 0x91, n & 0xFF, n >> 8, 0, 0, opcode]) + than


# --- Byte LAY THANG TU CAPTURE (khong tu che) ---
DK_XONG = (0x14, "08002a")           # t=19.31 - dang ky xong
KET_TRAN = (0x14, "080026")          # t=477.75 - tran ket thuc
PAGE1 = (0x14, "0100000000010103030000000000003930")      # t=13.59 - chua phai buoc chon
PAGE_CHON = (0x14, "0100000000020603030000000000000200")  # t=15.89 - da la buoc chon
TAO_TRAN = (0x0b, "fa007b000005025910fdf4878d0300000000000000000000")  # t=355.68
TA = bytes.fromhex("5910fdf4878d0300")
WIN_CUA_TA = (0x25, "01005910fdf4878d03000100")
WIN_NGUOI_KHAC = (0x25, "0100571cf8f4878d03000500")


class TestNhanDangGoi(unittest.TestCase):
    def test_dang_ky_xong(self):
        self.assertTrue(loandau.is_registered(*[DK_XONG[0], _goi(*DK_XONG)]))
        self.assertFalse(loandau.is_registered(KET_TRAN[0], _goi(*KET_TRAN)))

    def test_ket_tran(self):
        self.assertTrue(loandau.is_battle_over(KET_TRAN[0], _goi(*KET_TRAN)))
        self.assertFalse(loandau.is_battle_over(DK_XONG[0], _goi(*DK_XONG)))

    def test_hai_moc_KHONG_lan_nhau(self):
        """`08 2a` va `08 26` chi khac 1 byte - lan nhau la vong lap chay loan."""
        self.assertNotEqual(loandau.END_REGISTERED, loandau.END_BATTLE)

    def test_page_dialog_va_buoc_chon(self):
        self.assertFalse(loandau.is_choice_page(loandau.dialog_page(PAGE1[0], _goi(*PAGE1))))
        self.assertTrue(loandau.is_choice_page(
            loandau.dialog_page(PAGE_CHON[0], _goi(*PAGE_CHON))))
        self.assertIsNone(loandau.dialog_page(DK_XONG[0], _goi(*DK_XONG)))

    def test_tao_tran(self):
        self.assertTrue(loandau.is_battle_create(TAO_TRAN[0], _goi(*TAO_TRAN)))
        # `0x0b` sub khac (vd sub 4 = nguoi khac vao tran) KHONG duoc tinh la tao tran.
        self.assertFalse(loandau.is_battle_create(0x0b, _goi(0x0b, "0400025910fdf4878d0300000005")))

    def test_so_tran_thang_chi_lay_cua_minh(self):
        self.assertEqual(loandau.parse_vs_win(0x25, _goi(*WIN_CUA_TA), TA), 1)
        self.assertIsNone(loandau.parse_vs_win(0x25, _goi(*WIN_NGUOI_KHAC), TA))
        self.assertIsNone(loandau.parse_vs_win(0x25, _goi(*WIN_CUA_TA), None))


def _ev():
    """Entry loan_dau THAT tu events.json - test phai bat duoc loi sai trong chinh file du lieu."""
    from bot import config
    ev = (getattr(config, "EVENTS", {}) or {}).get("loan_dau")
    assert ev, "events.json khong con entry loan_dau"
    return ev


class TestKhungGio(unittest.TestCase):
    """Thang 8/2026: 24=T2, 25=T3, 26=T4, 27=T5, 28=T6, 29=T7, 30=CN."""

    def test_thu_3_20h_den_22h(self):
        for h, m in ((20, 0), (21, 59)):
            self.assertTrue(loandau.in_event_window(datetime.datetime(2026, 8, 25, h, m), _ev()))
        for h, m in ((19, 59), (22, 0)):
            self.assertFalse(loandau.in_event_window(datetime.datetime(2026, 8, 25, h, m), _ev()))

    def test_thu_7_20h30_den_22h30(self):
        """User chot 05/09: T7 LECH NUA TIENG so voi T3 -> phai so ca PHUT, `now.hour` khong du."""
        for h, m in ((20, 30), (22, 29)):
            self.assertTrue(loandau.in_event_window(datetime.datetime(2026, 8, 29, h, m), _ev()),
                            "T7 %02d:%02d phai mo" % (h, m))
        for h, m in ((20, 0), (20, 29), (22, 30), (23, 0)):
            self.assertFalse(loandau.in_event_window(datetime.datetime(2026, 8, 29, h, m), _ev()),
                             "T7 %02d:%02d phai dong" % (h, m))

    def test_thu_5_20h_den_22h(self):
        """Loan dau DOI (團P). Cung map/NPC voi T3, chi khac select + option NPC."""
        for h, m in ((20, 0), (21, 59)):
            self.assertTrue(loandau.in_event_window(datetime.datetime(2026, 8, 27, h, m), _ev()))
        for h, m in ((19, 59), (22, 0)):
            self.assertFalse(loandau.in_event_window(datetime.datetime(2026, 8, 27, h, m), _ev()))

    def test_ngay_khac_thi_dong(self):
        for ngay in (24, 26, 28, 30):    # thu 2, 4, 6, CN (T3=25, T5=27, T7=29 deu mo)
            self.assertFalse(loandau.in_event_window(datetime.datetime(2026, 8, ngay, 21, 0), _ev()),
                             "ngay %d khong phai T3/T5/T7 ma van mo" % ngay)

    def test_khong_co_lich_thi_giu_hanh_vi_cu(self):
        """ev=None / event khong khai `lich` -> chi THU 3, y nhu truoc 05/09."""
        self.assertTrue(loandau.in_event_window(datetime.datetime(2026, 8, 25, 21, 0)))
        self.assertFalse(loandau.in_event_window(datetime.datetime(2026, 8, 29, 21, 0)))

    def test_KHONG_trung_khung_40NPC(self):
        """40NPC la thu 2/4/6 - hai event khong duoc dam nhau."""
        from bot import npc40
        for ngay in range(24, 31):
            for h, m in ((20, 15), (21, 0), (22, 15)):
                t = datetime.datetime(2026, 8, ngay, h, m)
                self.assertFalse(loandau.in_event_window(t, _ev()) and npc40.in_event_window(t))


class TestBienTheTheoThu(unittest.TestCase):
    """T3 va T7 la HAI SANH KHAC NHAU, khong phai cung mot sanh doi gio.

    Do tren `captures/loandau_t7_20260905.pcap` (ghep luong TCP theo seq, 0 byte sot):
        chon event 0x4d : T3 `03000300` (id 3)   | T7 `03005a00` (id 90)
        map             : T3 10991               | T7 54901
        diem NPC        : T3 (910, 290)          | T7 (1630, 430)
        option NPC      : T3 `0x14 0100 03 00`   | T7 `0x14 0100 01 00`
    """

    T3 = datetime.datetime(2026, 8, 25, 21, 0)
    T7 = datetime.datetime(2026, 8, 29, 21, 0)

    def test_thu_3_giu_nguyen_gia_tri_goc(self):
        b = loandau.bien_the_hom_nay(_ev(), self.T3)
        self.assertEqual(b["select"], "03000300")
        self.assertEqual(b["dest_map"], 10991)
        self.assertEqual(list(b["party_battle"]["point"]), [910, 290])
        self.assertEqual(loandau.npc_option(b), b"\x01\x00\x03\x00")

    T5 = datetime.datetime(2026, 8, 27, 21, 0)

    def test_thu_5_chi_doi_select_va_option(self):
        """Do tren `captures/loandau_doi_20260903.pcap` (03/09/2026 = THU 5, 1 luong TCP -> CUNG
        server, khong phai vo gioi):
            C2S 0x4d 03000200          <- id 2 (T3 la 3)
            S2C 0x4d 030000ef2a7201a802 -> map 10991, spawn (370,680)  = Y HET T3
            di bo toi (910,290) roi C2S 0x14 01000400   <- option 04 = 團P (T3 la 03)
        """
        b = loandau.bien_the_hom_nay(_ev(), self.T5)
        self.assertEqual(b["select"], "03000200")
        self.assertEqual(loandau.npc_option(b), b"\x01\x00\x04\x00")
        # map va diem NPC GIU NGUYEN cua T3 - khong duoc khai lai trong `lich`
        self.assertEqual(b["dest_map"], 10991)
        self.assertEqual(list(b["party_battle"]["point"]), [910, 290])

    def test_thu_5_KHONG_phai_lien_server(self):
        """Capture chi co 1 IP -> khong co buoc chuyen may. Khai nham la bot cho vo ich."""
        b = loandau.bien_the_hom_nay(_ev(), self.T5)
        self.assertNotIn("vo_gioi", str(b))

    def test_ba_ngay_KHAC_NHAU_tung_doi_mot(self):
        """Trung select hay trung option = vao nham event."""
        bs = [loandau.bien_the_hom_nay(_ev(), t) for t in (self.T3, self.T5, self.T7)]
        self.assertEqual(len({b["select"] for b in bs}), 3, "trung `select` giua cac ngay")
        self.assertEqual(len({loandau.npc_option(b) for b in bs}), 3, "trung option NPC")

    def test_thu_7_doi_du_bon_tham_so(self):
        b = loandau.bien_the_hom_nay(_ev(), self.T7)
        self.assertEqual(b["select"], "03005a00")
        self.assertEqual(b["dest_map"], 54901)
        self.assertEqual(list(b["party_battle"]["point"]), [1630, 430])
        self.assertEqual(loandau.npc_option(b), b"\x01\x00\x01\x00")

    def test_van_la_CUNG_MOT_MODE(self):
        """User chot: 'ko lam them mode moi'. Kind phai giu nguyen o CA BA ngay.
        Rieng T5 la 團P ('loan dau doi') nhung user chot 05/09: VAN dang ky SOLO, khong lap party."""
        for t in (self.T3, self.T5, self.T7):
            b = loandau.bien_the_hom_nay(_ev(), t)
            self.assertEqual(b["party_battle"]["kind"], "chaos_vs")
            self.assertEqual(b["exit"]["out_map"], 12003)

    def test_khong_de_be_ev_goc(self):
        """Tra ban SAO - de lo ghi de len EVENTS thi acc sau doc nham tham so ngay khac."""
        goc = _ev()
        loandau.bien_the_hom_nay(goc, self.T7)["dest_map"] = 999
        self.assertEqual(_ev()["dest_map"], 10991)
        self.assertEqual(list(_ev()["party_battle"]["point"]), [910, 290])

    def test_ngay_khong_co_loan_dau_thi_tra_ban_sao_nguyen(self):
        b = loandau.bien_the_hom_nay(_ev(), datetime.datetime(2026, 8, 26, 21, 0))
        self.assertEqual(b["dest_map"], 10991)

    def test_config_event_hom_nay_ap_dung_bien_the(self):
        """Duong THAT ma run_party_digioi dung."""
        from bot import config
        self.assertEqual(config.event_hom_nay("loan_dau", self.T7)["dest_map"], 54901)
        self.assertEqual(config.event_hom_nay("loan_dau", self.T3)["dest_map"], 10991)

    def test_event_khong_co_lich_thi_khong_dung_toi(self):
        from bot import config
        for k, v in (getattr(config, "EVENTS", {}) or {}).items():
            if not v.get("lich"):
                self.assertIs(config.event_hom_nay(k, self.T7), v,
                              "event '%s' khong co lich ma van bi thay doi" % k)


class _FakeClient:
    """Client gia: ghi lai goi da gui, va tu tang seq theo kich ban."""

    def __init__(self, dang_ky_sau=1):
        self.running = True
        self._label = "test"
        self.gui = []
        self._loandau_registered_seq = 0
        self._loandau_create_seq = 0
        self._loandau_end_seq = 0
        self._loandau_dialog = ""
        self._loandau_wins = 0
        self._dang_ky_sau = dang_ky_sau      # so lan ADVANCE truoc khi server bao da dang ky

    def send(self, op, body):
        self.gui.append((op, body.hex()))
        if op == loandau.OP_DIALOG and body == loandau.ADVANCE:
            n = sum(1 for o, b in self.gui
                    if o == loandau.OP_DIALOG and b == loandau.ADVANCE.hex())
            if n >= self._dang_ky_sau:
                self._loandau_registered_seq += 1


class TestDangKy(unittest.TestCase):
    def _chay(self, c):
        return loandau.dang_ky(c, threading.Event(), lambda _s: None, poll_interval=0.0)

    def test_gui_dung_option_03(self):
        c = _FakeClient()
        self.assertTrue(self._chay(c))
        self.assertIn((loandau.OP_EVENT, "020008"), c.gui)
        self.assertIn((loandau.OP_DIALOG, "01000300"), c.gui)

    def test_option_KHAC_40NPC(self):
        """Nham sang `...0500` la vao event 40NPC chu khong phai loan dau."""
        from bot import npc40
        self.assertNotEqual(loandau.OPEN_NPC, npc40.OPEN_NPC)
        self.assertEqual(loandau.OPEN_NPC, b"\x01\x00\x03\x00")

    def test_page_chua_phai_buoc_chon_thi_advance_truoc_khi_chon(self):
        c = _FakeClient()
        self._chay(c)
        thu_tu = [b for o, b in c.gui if o == loandau.OP_DIALOG]
        self.assertEqual(thu_tu[0], "01000300")
        self.assertEqual(thu_tu[1], loandau.ADVANCE.hex(), "phai advance khi chua toi buoc chon")
        self.assertEqual(thu_tu[2], loandau.CHOOSE_YES.hex())

    def test_page_DA_la_buoc_chon_thi_KHONG_advance_thua(self):
        """Advance thua lam lech state -> server kick (bai hoc 40NPC 2026-07-29)."""
        c = _FakeClient()
        _goc = c.send

        def send(op, body):
            _goc(op, body)
            if op == loandau.OP_DIALOG and body == loandau.OPEN_NPC:
                c._loandau_dialog = "0100000000020603030000000000000200"
        c.send = send
        self._chay(c)
        thu_tu = [b for o, b in c.gui if o == loandau.OP_DIALOG]
        self.assertEqual(thu_tu[0], "01000300")
        self.assertEqual(thu_tu[1], loandau.CHOOSE_YES.hex(),
                         "da o buoc chon ma van advance -> se bi kick")

    def test_dung_advance_NGAY_khi_da_dang_ky(self):
        """Capture can 3 advance. Sau khi nhan `08 2a` thi KHONG duoc gui them cai nao."""
        c = _FakeClient(dang_ky_sau=3)
        self.assertTrue(self._chay(c))
        n = sum(1 for o, b in c.gui
                if o == loandau.OP_DIALOG and b == loandau.ADVANCE.hex())
        self.assertEqual(n, 3, "gui thua advance sau khi da dang ky")

    def test_dang_ky_that_bai_thi_tra_False(self):
        c = _FakeClient(dang_ky_sau=999)
        self.assertFalse(self._chay(c))


class TestNoiVaoBot(unittest.TestCase):
    """Doc thang ma nguon - giu cac moc noi khong bi thao ra."""

    def setUp(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.rp = fh.read()
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.cl = fh.read()

    def _than(self, src, ten):
        m = re.search(r"^([ \t]*)def %s\(.*?\n(.*?)(?=\n\1def |\n\S)" % ten, src, re.S | re.M)
        self.assertIsNotNone(m, "khong thay ham %s" % ten)
        return re.sub(r"#.*", "", m.group(2))    # bo chu thich, tranh bay "khop trong comment"

    def test_event_solo_KHONG_bi_coi_la_dung_yen(self):
        than = self._than(self.rp, "_event_solo_battle_kind")
        self.assertIn("chaos_vs", than)
        self.assertIn("event_solo_kind", self.rp)
        self.assertRegex(self.rp, r"event_stand_mode\s*=.*not event_solo_kind")

    def test_chaos_vs_KHONG_lot_vao_duong_lap_party(self):
        """Nhet chaos_vs vao _event_battle_kind se keo theo sync kenh + barrier cua 40NPC/2K."""
        than = self._than(self.rp, "_event_battle_kind")
        self.assertNotIn("chaos_vs", than)

    def test_KHONG_sync_kenh_cho_event_solo(self):
        """`do_channel_sync` la BARRIER: leader doi du ca party, member cho `channel_ready`.

        Loan dau danh solo nen cho nhau khong duoc gi - acc xong truoc van phai dung im cho acc
        dang login, mat luot dang ky (user bao 25/08: 5 acc login xong 21:33:03 ma toi 21:33:14
        moi di duoc).
        """
        import re
        m = re.search(r"\n(\s*)if not _is_party_event\(mode, has_leader, ev\)(.*?)\n\s*do_channel_sync\(\)",
                      self.rp, re.S)
        self.assertIsNotNone(m, "khong tim thay cho goi do_channel_sync cho event")
        self.assertIn("_event_solo_battle_kind", m.group(2),
                      "event solo van bi keo vao sync kenh -> cho nhau vo ich")

    def test_het_gio_thi_RA_KHOI_MAP_roi_moi_tat(self):
        """Server tu trao thuong nen khong co buoc doi thuong, nhung PHAI ra khoi map event:
        de nguyen trong 10991 thi lan login sau bot khoi dong tu map event chu khong tu thanh."""
        self.assertIn("def _loandau_ra_khoi_map", self.rp)
        than = self._than(self.rp, "_loandau_ra_khoi_map")
        self.assertIn("exit_event", than)
        self.assertIn("dest_map", than, "phai kiem dang o map event moi thoat, khong lam bua")
        # Dem CHO GOI, bo dong `def` (dong do cung chua y het chuoi nay).
        goi = [ln for ln in self.rp.splitlines()
               if "_loandau_ra_khoi_map(c, ev, label)" in ln and not ln.lstrip().startswith("def ")]
        self.assertEqual(len(goi), 2,
                         "phai goi ca o nhanh HET GIO lan nhanh NGOAI GIO, dang co %d" % len(goi))

    def test_KHONG_con_nhac_doi_thuong(self):
        self.assertNotIn("LOAN DAU: buoc DOI THUONG chua lam", self.rp)

    def test_co_khoi_dong_vong_loan_dau(self):
        self.assertIn("start_loandau_loop", self.rp)
        self.assertIn("def start_loandau_loop", self.cl)

    def test_close_phai_dung_vong(self):
        """Thieu -> thread con gui 0x14 06 len socket dang dong."""
        than = self._than(self.cl, "close")
        self.assertIn("stop_loandau_loop", than)

    def test_observer_duoc_goi_trong_dispatch(self):
        than = self._than(self.cl, "_dispatch")
        self.assertIn("_observe_loandau_packet", than)

    def test_hoi_mau_chi_goi_khi_KHONG_trong_tran(self):
        m = re.search(r"def _before_loandau_repeat\(\):(.*?)\n\n", self.rp, re.S)
        self.assertIsNotNone(m)
        than = re.sub(r"#.*", "", m.group(1))
        self.assertIn("not c.state.in_battle", than)


class TestDuLieuEvent(unittest.TestCase):
    def setUp(self):
        import json
        with open(os.path.join(ROOT, "events.json"), encoding="utf-8") as fh:
            self.ev = json.load(fh)["events"]

    def test_entry_loan_dau(self):
        d = self.ev["loan_dau"]
        self.assertEqual(d["select"], "03000300")
        self.assertEqual(d["dest_map"], 10991)
        self.assertEqual(d["party_battle"]["kind"], "chaos_vs")
        self.assertEqual(list(d["party_battle"]["point"]), [910, 290])

    def test_KHONG_trung_select_voi_event_khac(self):
        sel = [v["select"] for v in self.ev.values()]
        self.assertEqual(len(sel), len(set(sel)), "hai event dung chung payload chon -> vao nham")

    def test_cung_map_NPC_voi_40npc(self):
        """Capture xac nhan trung map + trung diem; lech la di sai cho."""
        self.assertEqual(self.ev["loan_dau"]["dest_map"], self.ev["npc_40"]["dest_map"])
        self.assertEqual(list(self.ev["loan_dau"]["party_battle"]["point"]),
                         list(self.ev["npc_40"]["party_battle"]["point"]))


class TestKhaiBaoAPK(unittest.TestCase):
    def test_co_trong_SHARED(self):
        """Quen khai bao = ban APK chay thieu file (build se DUNG, xem CLAUDE.md)."""
        with open(os.path.join(ROOT, "tools", "sync_apk_python.py"), encoding="utf-8") as fh:
            self.assertIn('"loandau.py"', fh.read())

    def test_co_future_annotations(self):
        """Chaquopy chay Python 3.8 - thieu dong nay la crash khi dung type hint moi."""
        with open(os.path.join(ROOT, "bot", "loandau.py"), encoding="utf-8") as fh:
            self.assertIn("from __future__ import annotations", fh.read())


if __name__ == "__main__":
    unittest.main()


class TestOptionNPCTheoNgay(unittest.TestCase):
    """`dang_ky` phai gui option cua HOM NAY, khong duoc hard-code 03 nhu ban cu."""

    def _gui_khi_dang_ky(self, ev):
        c = _FakeClient()
        loandau.dang_ky(c, threading.Event(), lambda _s: None, poll_interval=0.0, ev=ev)
        return list(c.gui)

    def test_thu_7_gui_option_01(self):
        b = loandau.bien_the_hom_nay(_ev(), datetime.datetime(2026, 8, 29, 21, 0))
        self.assertIn((loandau.OP_DIALOG, "01000100"), self._gui_khi_dang_ky(b))

    def test_thu_3_gui_option_03(self):
        b = loandau.bien_the_hom_nay(_ev(), datetime.datetime(2026, 8, 25, 21, 0))
        self.assertIn((loandau.OP_DIALOG, "01000300"), self._gui_khi_dang_ky(b))

    def test_khong_truyen_ev_thi_dung_mac_dinh_03(self):
        self.assertIn((loandau.OP_DIALOG, "01000300"), self._gui_khi_dang_ky(None))

    def test_option_hong_thi_lui_ve_mac_dinh_chu_khong_no(self):
        self.assertEqual(loandau.npc_option({"party_battle": {"npc_option": "zzz"}}),
                         loandau.OPEN_NPC)

    def test_chuoi_dang_ky_GIONG_NHAU_o_ca_hai_ngay(self):
        """Capture t7 xac nhan: sau option, chuoi con lai y het t3 (advance -> 09001e -> ...)."""
        t3 = [x for x in self._gui_khi_dang_ky(
            loandau.bien_the_hom_nay(_ev(), datetime.datetime(2026, 8, 25, 21, 0)))]
        t7 = [x for x in self._gui_khi_dang_ky(
            loandau.bien_the_hom_nay(_ev(), datetime.datetime(2026, 8, 29, 21, 0)))]
        bo_option = lambda ds: [x for x in ds if x[1] not in ("01000300", "01000100")]
        self.assertEqual(bo_option(t3), bo_option(t7))


class TestKhongMoNPCKhiSaiMap(unittest.TestCase):
    """SỰ CỐ 05/09 21:15 - MAT 4 ACC party 11 trong 3 giay.

        21:14:56 go_to_event 'Loan dau' xong: map=23882 (dich 54901) -> CHUA TOI
        21:14:58 (LEADER) LOAN DAU: toi (1630, 430) va bat dau vong dang ky/danh
        21:15:19 >>gui  0x20 020008          <- mo NPC su kien TREN MAP TRAIN
        21:15:19 >>gui  0x14 01000100
        21:15:21 <<nhan 0x00 ...0500         <- S:000-000 ma 5 "su kien vi pham" = DA
        21:15:21 SERVER NGAT KET NOI: su kien vi pham (ma 5)

    Hai lo hong cong lai: `go_to_event` khong CHO server tele xong (chi ngu 1.0s, ma capture do
    2.36s) nen luon bao CHUA TOI; va ket qua do bi VUT DI, khong ai doc.

    Bo mot buoi event con hon mat acc.
    """

    class _C:
        def __init__(self, map_id):
            self.running = True
            self._label = "test"
            self.current_map = map_id
            self.da_navigate = False

        def navigate_to(self, *a, **k):
            self.da_navigate = True
            return True

    def test_sai_map_thi_KHONG_navigate_KHONG_mo_NPC(self):
        c = self._C(23882)                       # map train, khong phai map event
        ev = loandau.bien_the_hom_nay(_ev(), datetime.datetime(2026, 8, 29, 21, 0))
        self.assertFalse(loandau.run_loop(c, (1630, 430), threading.Event(), ev=ev,
                                          sleep_fn=lambda _s: None))
        self.assertFalse(c.da_navigate, "da di toi diem NPC tren map thuong -> se bi da ma 5")

    def test_dung_map_thi_van_chay(self):
        c = self._C(54901)
        ev = loandau.bien_the_hom_nay(_ev(), datetime.datetime(2026, 8, 29, 21, 0))
        c.running = False                        # dung ngay sau navigate, chi can kiem da di
        loandau.run_loop(c, (1630, 430), threading.Event(), ev=ev, sleep_fn=lambda _s: None)
        self.assertTrue(c.da_navigate)

    def test_go_to_event_CO_cho_khi_khong_co_staging(self):
        """`staging_map: 0` = tele THANG toi map event -> phai cho, khong ket luan sau 1 giay."""
        import io as _io, os as _os
        src = _io.open(_os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()
        i = src.find("def go_to_event(")
        than = src[i:src.find("\n    def ", i + 10)]
        self.assertIn("if not staging and dest:", than,
                      "khong co staging thi KHONG cho gi -> luon bao CHUA TOI")
        self.assertIn("while self.current_map != dest", than)

    def test_caller_PHAI_doc_ket_qua_go_to_event(self):
        import io as _io, os as _os
        src = _io.open(_os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()
        self.assertIn("if not c.go_to_event(ev):", src,
                      "vut ket qua go_to_event -> tele hong van mo NPC -> bi da ma 5")
