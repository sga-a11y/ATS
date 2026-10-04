# -*- coding: utf-8 -*-
"""Bo chay hoi thoai quest phai gui `0x14 06` / `0x14 09` KHOP TUNG GOI voi client that.

Gui thua `0x14 06` luc server khong cho = "su kien vi pham" ma 5 -> ngat ket noi; gui luc dang
giai tran = ma 47. Nen test phat lai DUNG chuoi goi server trong capture user lam tay
(KNOWLEDGE.md muc capture quest 10384 / 10528) va so chuoi bot gui voi chuoi client that gui.
"""
from __future__ import annotations

import os
import struct
import sys
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient

CAP = os.path.join(ROOT, "captures")


def _frames(fn):
    """[(chieu 'C'/'S', opcode, body)] theo thu tu thoi gian (khung TS c0 91, XOR 0xAD)."""
    with open(fn, "rb") as fh:
        d = fh.read()
    L = 16 if struct.unpack("<I", d[20:24])[0] == 113 else 14
    off, bufs, out = 24, {"C": b"", "S": b""}, []
    while off + 16 <= len(d):
        incl = struct.unpack("<I", d[off + 8:off + 12])[0]
        p = d[off + 16:off + 16 + incl]
        off += 16 + incl
        if len(p) < L + 20 or p[L + 9] != 6:
            continue
        t = L + (p[L] & 15) * 4
        pay = p[t + (p[t + 12] >> 4) * 4:]
        sp, dp = struct.unpack(">HH", p[t:t + 4])
        k = "C" if dp == 6614 else ("S" if sp == 6614 else None)
        if not k or not pay:
            continue
        bufs[k] += bytes(x ^ 0xAD for x in pay)
        s, i = bufs[k], 0
        while i + 7 <= len(s):
            if s[i] == 0xC0 and s[i + 1] == 0x91:
                ln = struct.unpack("<H", s[i + 2:i + 4])[0]
                if ln < 7:
                    i += 1
                    continue
                if i + ln > len(s):
                    break
                out.append((k, s[i + 6], s[i + 7:i + ln]))
                i += ln
                continue
            i += 1
        bufs[k] = s[i:]
    return out


def _doan(fn, trigger_body):
    """Doan su kien: tu goi C2S kich hoat `trigger_body` toi S2C `S:020-008`.

    Tra (c2s_0x14, nhom): c2s_0x14 = cac body 0x14 client gui SAU kich hoat; nhom[i] = cac goi S2C
    0x14 server tra sau lan gui thu i (nhom[0] = sau kich hoat).
    """
    fr = _frames(fn)
    i = next(n for n, (k, op, b) in enumerate(fr) if k == "C" and op == 0x14 and b == trigger_body)
    c2s, nhom = [], [[]]
    for k, op, b in fr[i + 1:]:
        if op != 0x14:
            continue
        if k == "C":
            if b[:2] == b"\x08\x00":
                break          # cham cua (di bo) - het doan
            c2s.append(b)
            nhom.append([])
        else:
            nhom[-1].append(b)
            if b[:2] == b"\x08\x00":
                break
    return c2s, nhom


def _pkt(body):
    return b"\xc0\x91" + struct.pack("<H", 7 + len(body)) + b"\x00\x00\x14" + body


class _ServerGia:
    """Client gia: moi lan bot gui 0x14 -> day nhom goi server KE TIEP vao `_observe_quest_event`.
    Goi sau `S:020-009` (vao tran) chi duoc day khi tran KET (lan dau bot hoi `in_combat`)."""

    def __init__(self, nhom):
        self.c = GameClient.__new__(GameClient)
        self.c.running = True
        self.c._label = "test"
        self.c.state = SimpleNamespace(in_battle=False)
        self.c._qev = None
        self.c.QEV_TALK_DELAY = 0.0
        self.c.QEV_MOVIE_WAIT = 0.0
        self.c.QEV_SCENE_WAIT = 0.0
        self.c.send = self.send
        self.c.in_combat = self.in_combat
        self.c._in_battle_end_grace = lambda: False
        self.nhom = [list(g) for g in nhom]
        self.sau_tran = []
        self.gui = []

    def _day(self, goi):
        for n, b in enumerate(goi):
            self.c._observe_quest_event(0x14, _pkt(b))
            if b[:2] == b"\x09\x00":
                self.sau_tran = goi[n + 1:]
                return

    def send(self, op, body):
        if op != 0x14:
            return
        if body[:2] in (b"\x01\x00", b"\x08\x00") and not self.gui and self.nhom:
            self._day(self.nhom.pop(0))      # kich hoat
            return
        self.gui.append(bytes(body))
        if self.nhom:
            self._day(self.nhom.pop(0))

    def in_combat(self, idle_secs=1.0):
        if self.sau_tran:
            goi, self.sau_tran = self.sau_tran, []
            self._day(goi)
        return False


class TestPhatLaiCapture(unittest.TestCase):
    def _chay(self, fn, trigger, kieu, idx, chon=()):
        c2s, nhom = _doan(os.path.join(CAP, fn), trigger)
        sv = _ServerGia(nhom)
        sv.c.quest_kich_hoat(kieu, idx)
        kq = sv.c.quest_hoi_thoai(chon=chon, im_lang=2.0, toi_da=20.0)
        return kq, sv.gui, c2s

    def test_tuyet_dong_nhan_quest(self):
        kq, gui, that = self._chay("cs1_10384_tuyetdong_20261003.pcap", b"\x01\x00\x01\x00",
                                   "npc", 1)
        self.assertEqual(kq, "xong")
        self.assertEqual(gui, that)

    def test_tuyet_dong_buoc2_movie_va_danh_boss(self):
        # NPC 2 o 19506: movie -> vao tran boss -> server TU gui thoai tiep sau tran
        kq, gui, that = self._chay("cs1_10384_tuyetdong_20261003.pcap", b"\x01\x00\x02\x00",
                                   "npc", 2)
        self.assertEqual(kq, "xong")
        self.assertEqual(gui, that)
        self.assertEqual(len(that), 18)       # 7 truoc tran + 11 sau tran (dem tay tu capture)

    def test_thai_ho_nhan_quest(self):
        kq, gui, that = self._chay("cs1_10528_thaiho_20261003.pcap", b"\x01\x00\x04\x00",
                                   "npc", 4)
        self.assertEqual((kq, gui), ("xong", that))

    def test_thai_ho_buoc1_chon_muc_1(self):
        c2s, nhom = _doan(os.path.join(CAP, "cs1_10528_thaiho_20261003.pcap"),
                          b"\x01\x00\x04\x00")
        # lan NPC 4 thu HAI trong capture = buoc 1 o Quan Phu (co chon)
        fr = _frames(os.path.join(CAP, "cs1_10528_thaiho_20261003.pcap"))
        idx = [n for n, (k, op, b) in enumerate(fr)
               if k == "C" and op == 0x14 and b == b"\x01\x00\x04\x00"]
        self.assertGreaterEqual(len(idx), 2)
        kq, gui, that = self._chay_tu(fr, idx[1], "npc", 4, chon=[30])
        self.assertEqual(kq, "xong")
        self.assertEqual(gui, that)
        self.assertIn(b"\x09\x00\x1e", gui)

    def test_thai_ho_buoc2_chon_va_danh_boss(self):
        fr = _frames(os.path.join(CAP, "cs1_10528_thaiho_20261003.pcap"))
        i = next(n for n, (k, op, b) in enumerate(fr)
                 if k == "C" and op == 0x14 and b == b"\x01\x00\x01\x00")
        kq, gui, that = self._chay_tu(fr, i, "npc", 1, chon=[30])
        self.assertEqual((kq, gui), ("xong", that))

    def test_thieu_ma_chon_thi_dung_khong_doan(self):
        fr = _frames(os.path.join(CAP, "cs1_10528_thaiho_20261003.pcap"))
        i = next(n for n, (k, op, b) in enumerate(fr)
                 if k == "C" and op == 0x14 and b == b"\x01\x00\x01\x00")
        kq, gui, _that = self._chay_tu(fr, i, "npc", 1, chon=[])
        self.assertEqual(kq, "can_chon")
        self.assertFalse(any(b[:2] == b"\x09\x00" for b in gui))

    def _chay_tu(self, fr, i, kieu, idx, chon=()):
        c2s, nhom = [], [[]]
        for k, op, b in fr[i + 1:]:
            if op != 0x14:
                continue
            if k == "C":
                if b[:2] == b"\x08\x00":
                    break
                c2s.append(b)
                nhom.append([])
            else:
                nhom[-1].append(b)
                if b[:2] == b"\x08\x00":
                    break
        sv = _ServerGia(nhom)
        sv.c.quest_kich_hoat(kieu, idx)
        kq = sv.c.quest_hoi_thoai(chon=chon, im_lang=2.0, toi_da=20.0)
        return kq, sv.gui, c2s


if __name__ == "__main__":
    unittest.main()


class TestPhatLaiThienDoc(unittest.TestCase):
    """captures/cs1_10324_thiendoc_20261003.pcap: buoc 'chi co toa do' = CUA SU KIEN AN."""
    FN = os.path.join(CAP, "cs1_10324_thiendoc_20261003.pcap")

    def _chay(self, trigger, kieu, idx, chon=(), lan=0):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == trigger][lan]
        return TestPhatLaiCapture._chay_tu(None, fr, i, kieu, idx, chon=chon)

    def test_nhan_quest_quan_tro(self):
        kq, gui, that = self._chay(b"\x01\x00\x01\x00", "npc", 1)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc1_npc2_dai_lo(self):
        kq, gui, that = self._chay(b"\x01\x00\x02\x00", "npc", 2)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc2_cua5_co_doi_scene_giua_su_kien(self):
        kq, gui, that = self._chay(b"\x08\x00\x05\x00", "cua", 5, lan=1)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc3_cua2_chon_muc_1(self):
        fr = _frames(self.FN)
        # cua 2 cuoi cung trong capture = buoc 3 o 13519
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == b"\x08\x00\x02\x00"][-1]
        kq, gui, that = TestPhatLaiCapture._chay_tu(None, fr, i, "cua", 2, chon=[30])
        self.assertEqual((kq, gui), ("xong", that))
        self.assertIn(b"\x09\x00\x1e", gui)

    def test_buoc4_cua3_movie_danh_boss_xong_quest(self):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == b"\x08\x00\x03\x00"][-1]
        kq, gui, that = TestPhatLaiCapture._chay_tu(None, fr, i, "cua", 3)
        self.assertEqual((kq, gui), ("xong", that))


class TestPhatLaiPhanNoBien(unittest.TestCase):
    """captures/cs1_10326_phannobien_20261003.pcap."""
    FN = os.path.join(CAP, "cs1_10326_phannobien_20261003.pcap")

    def _chay(self, trigger, kieu, idx, chon=()):
        fr = _frames(self.FN)
        i = next(n for n, (k, op, b) in enumerate(fr)
                 if k == "C" and op == 0x14 and b == trigger)
        return TestPhatLaiCapture._chay_tu(None, fr, i, kieu, idx, chon=chon)

    def test_nhan_quest_co_chon_muc_1(self):
        kq, gui, that = self._chay(b"\x01\x00\x04\x00", "npc", 4, chon=[30])
        self.assertEqual((kq, gui), ("xong", that))
        self.assertIn(b"\x09\x00\x1e", gui)

    def test_buoc1_cua2_danh_boss_xong_ca_quest(self):
        kq, gui, that = self._chay(b"\x08\x00\x02\x00", "cua", 2)
        self.assertEqual((kq, gui), ("xong", that))


class TestPhatLaiThuToChayThoat(unittest.TestCase):
    """captures/cs1_10328_thutochaythoat_20261003.pcap - nhan quest bang CUA AN."""
    FN = os.path.join(CAP, "cs1_10328_thutochaythoat_20261003.pcap")

    def _chay(self, trigger, idx, chon=()):
        fr = _frames(self.FN)
        i = next(n for n, (k, op, b) in enumerate(fr)
                 if k == "C" and op == 0x14 and b == trigger)
        return TestPhatLaiCapture._chay_tu(None, fr, i, "cua", idx, chon=chon)

    def test_nhan_quest_cua4_chon_muc_1(self):
        kq, gui, that = self._chay(b"\x08\x00\x04\x00", 4, chon=[30])
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc1_cua2_movie_danh_boss(self):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == b"\x08\x00\x02\x00"][2]   # lan 3 = o 56517
        kq, gui, that = TestPhatLaiCapture._chay_tu(None, fr, i, "cua", 2)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc3_cua5_danh_boss_xong_quest(self):
        kq, gui, that = self._chay(b"\x08\x00\x05\x00", 5)
        self.assertEqual((kq, gui), ("xong", that))


class TestPhatLaiHoaDiem(unittest.TestCase):
    """captures/cs1_10360_hoadiem_20261003.pcap - B3 chon MUC 2 (31) -> nhay 3 buoc."""
    FN = os.path.join(CAP, "cs1_10360_hoadiem_20261003.pcap")

    def _chay(self, trigger, kieu, idx, chon=(), lan=0):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == trigger][lan]
        return TestPhatLaiCapture._chay_tu(None, fr, i, kieu, idx, chon=chon)

    def test_nhan_quest_chon_muc_1(self):
        kq, gui, that = self._chay(b"\x01\x00\x02\x00", "npc", 2, chon=[30])
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc1_cua6(self):
        kq, gui, that = self._chay(b"\x08\x00\x06\x00", "cua", 6)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc2_cua2_danh_boss(self):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == b"\x08\x00\x02\x00"][2]   # 57511 (610,950)
        kq, gui, that = TestPhatLaiCapture._chay_tu(None, fr, i, "cua", 2)
        self.assertEqual((kq, gui), ("xong", that))
        self.assertGreater(len(that), 5)

    def test_buoc3_cua3_chon_muc_2_danh_boss(self):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == b"\x08\x00\x03\x00"][3]   # 57511 (370,230)
        kq, gui, that = TestPhatLaiCapture._chay_tu(None, fr, i, "cua", 3, chon=[31])
        self.assertEqual((kq, gui), ("xong", that))
        self.assertIn(b"\x09\x00\x1f", gui)

    def test_buoc6_tra_quest(self):
        # Capture BI CAT ngay sau cum thuong (S:020-013/100), truoc `0x14 06` cuoi cua client ->
        # bot gui them DUNG MOT `0x14 06` (S:020-013 bat conduct, nhu 4 quest kia) roi cho server.
        kq, gui, that = self._chay(b"\x01\x00\x02\x00", "npc", 2, lan=1)
        self.assertEqual(kq, "im_lang")
        self.assertEqual(gui, that + [b"\x06\x00"])


class TestPhatLaiLeTe(unittest.TestCase):
    """captures/cs1_10564_letethannuoc_20261003.pcap - 3 lan NPC 1: nhan / B1 (boss) / B4."""
    FN = os.path.join(CAP, "cs1_10564_letethannuoc_20261003.pcap")
    NPC1 = bytes([1, 0, 1, 0])

    def _chay(self, lan, chon=()):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == self.NPC1][lan]
        return TestPhatLaiCapture._chay_tu(None, fr, i, "npc", 1, chon=chon)

    def test_nhan_quest_chon_muc_1(self):
        kq, gui, that = self._chay(0, chon=[30])
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc1_movie_danh_boss_nhay_2_buoc(self):
        kq, gui, that = self._chay(1)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc4_tra_quest(self):
        kq, gui, that = self._chay(2)
        self.assertEqual((kq, gui), ("xong", that))


class TestPhatLaiKhungThuong(unittest.TestCase):
    """captures/cs1_10806_khungthuong_20261003.pcap - 4 lan NPC 1: nhan / B1 / B2 (boss) / B3."""
    FN = os.path.join(CAP, "cs1_10806_khungthuong_20261003.pcap")
    NPC1 = bytes([1, 0, 1, 0])

    def _chay(self, lan, chon=()):
        fr = _frames(self.FN)
        i = [n for n, (k, op, b) in enumerate(fr)
             if k == "C" and op == 0x14 and b == self.NPC1][lan]
        return TestPhatLaiCapture._chay_tu(None, fr, i, "npc", 1, chon=chon)

    def test_nhan_quest(self):
        kq, gui, that = self._chay(0)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc1_chon_muc_1(self):
        kq, gui, that = self._chay(1, chon=[30])
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc2_movie_danh_boss(self):
        kq, gui, that = self._chay(2)
        self.assertEqual((kq, gui), ("xong", that))

    def test_buoc3_tra_quest(self):
        kq, gui, that = self._chay(3)
        self.assertEqual((kq, gui), ("xong", that))
