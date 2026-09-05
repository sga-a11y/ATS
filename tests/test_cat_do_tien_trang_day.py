"""Tien trang DAY: moi mon thu DUNG MOT LAN, hong thi bo qua mon do.

User bao 06/09: "tien trang full thi bot dung cho tien trang mai". Hai lo hong:
  1. Vong cat `break` CA LO ngay o mon hong dau tien -> vut luon phan van cat duoc.
     Kho day VAN cat duoc mon DA CO STACK san (gop chung stack); chi mon MOI moi hong.
  2. Mon hong khong duoc nho lai -> no van nam trong tui -> lan tele ve Trac Quan sau lai
     thay "co mon can cat" -> lai di NPC -> lai hong. Di di lai lai khong dut.

User chot: "moi item cat 1 lan thoi, ko duoc thi bo qua item do".
"""
from __future__ import annotations

import io
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C  # noqa: E402


class _Fake:
    """Chi giu phan lien quan den vong cat. `hong_tid` = cac tid server tra loi LOI."""

    BANK_RESTRICT_CAM = C.GameClient.BANK_RESTRICT_CAM

    def __init__(self, tui, hong_tid=()):
        self.running = True
        self._label = "t"
        self.bag_slots = dict(tui)
        self.bank_fail = None
        self._cat_hong = set()
        self._hong_tid = set(hong_tid)
        self.gui = []

    def send(self, op, body):
        slot = body[2]
        tid = self.bag_slots[slot][0]
        self.gui.append(tid)
        # server tra LOI 13 (kho day) cho mon chua co stack san
        self.bank_fail = 13 if tid in self._hong_tid else None

    _cat_do_slots = C.GameClient._cat_do_slots


def _chon(*tids):
    return {"0x%04x" % t: C.CAT_DO_CAT for t in tids}


def _chay_vong_cat(fake, chon):
    """Chay DUNG doan vong cat cua `cat_do_tien_trang` (khong dung mang/NPC)."""
    hong = []
    for slot, tid, qty in fake._cat_do_slots(chon):
        fake.bank_fail = None
        fake.send(0x1E, b"\x02\x00" + bytes([slot & 0xFF]) + struct.pack("<i", int(qty)))
        if fake.bank_fail is not None:
            fake._cat_hong.add(tid)
            hong.append(tid)
            continue
    return hong


class TestKhoDay(unittest.TestCase):
    TUI = {1: (0x1111, 5), 2: (0x2222, 3), 3: (0x3333, 7)}

    def test_mon_hong_KHONG_chan_mon_sau(self):
        """Mon dau hong (mon moi), hai mon sau da co stack -> VAN phai cat duoc."""
        f = _Fake(self.TUI, hong_tid={0x1111})
        _chay_vong_cat(f, _chon(0x1111, 0x2222, 0x3333))
        self.assertEqual(f.gui, [0x1111, 0x2222, 0x3333], "dung ca lo o mon hong dau tien")

    def test_moi_mon_gui_DUNG_MOT_lan(self):
        f = _Fake(self.TUI, hong_tid={0x1111, 0x2222, 0x3333})
        _chay_vong_cat(f, _chon(0x1111, 0x2222, 0x3333))
        self.assertEqual(sorted(f.gui), [0x1111, 0x2222, 0x3333])
        self.assertEqual(len(f.gui), len(set(f.gui)), "co mon bi gui lai lan 2")

    def test_nho_mon_hong_de_LAN_SAU_khong_di_nua(self):
        f = _Fake(self.TUI, hong_tid={0x1111, 0x3333})
        _chay_vong_cat(f, _chon(0x1111, 0x2222, 0x3333))
        self.assertEqual(f._cat_hong, {0x1111, 0x3333})
        # lan sau: `_cat_do_slots` phai LOC HET mon hong -> khong con gi de cat -> khong di NPC
        con = f._cat_do_slots(_chon(0x1111, 0x3333))
        self.assertEqual(con, [], "van con mon can cat -> bot lai di tien trang, dung li o do")

    def test_mon_cat_DUOC_thi_khong_bi_nho_oan(self):
        f = _Fake(self.TUI, hong_tid={0x1111})
        _chay_vong_cat(f, _chon(0x1111, 0x2222, 0x3333))
        self.assertNotIn(0x2222, f._cat_hong)
        self.assertNotIn(0x3333, f._cat_hong)


class TestNguonCode(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def cat_do_tien_trang(")
        self.than = s[i:s.find("\n    def ", i + 10)]
        self.src = s

    def test_KHONG_con_break_o_mon_hong(self):
        i = self.than.find("self._cat_hong.add(tid)")
        self.assertGreater(i, 0, "khong nho mon hong")
        self.assertIn("continue", self.than[i:i + 400], "phai `continue`, khong duoc `break`")

    def test_xoa_co_TRUOC_moi_lan_gui(self):
        """Khong xoa thi co cua mon TRUOC lam mon sau bi do oan ngay."""
        i = self.than.find("self.bank_fail = None\n            self.send(0x1E")
        self.assertGreater(i, 0, "khong xoa bank_fail truoc khi gui tung mon")

    def test_xoa_co_TRUOC_khi_lay_do_ra(self):
        """Vong lay do cung doc `bank_fail`; con sot tu mon cat cuoi la bo luon chieu lay ra."""
        i = self.than.find("self._lay_do_tien_trang(chon, kq)")
        self.assertGreater(i, 0)
        self.assertIn("self.bank_fail = None", self.than[max(0, i - 400):i])

    def test_nho_theo_PHIEN(self):
        """Relogin phai quen - luc do kho co the da duoc don trong."""
        self.assertIn("self._cat_hong = set()", self.src)

    def test_APK_giong_PC(self):
        with io.open(os.path.join(ROOT, "android", "app", "src", "main", "python",
                                  "train_bot", "client.py"), encoding="utf-8") as fh:
            apk = fh.read()
        self.assertIn("self._cat_hong.add(tid)", apk)


class TestLayRaKhiTuiDay(unittest.TestCase):
    """Chieu LAY RA lam DOI XUNG voi chieu cat (user chot 06/09).

    Client: `S:030-007` ma 3 -> ShowCenterMessage(80359) = 物品欄已滿 = TUI DO DAY, roi THOI.
    Chu thich trong protocal.lua ghi "3 = cat that bai" la SAI - chinh handler hien "tui day".
    """

    def setUp(self):
        import io as _io
        s = _io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8").read()
        i = s.find("def _lay_do_tien_trang(")
        self.than = s[i:s.find("\n    def ", i + 10)]
        self.src = s

    def test_KHONG_con_break_o_mon_hong(self):
        i = self.than.find("self._lay_hong.add(tid)")
        self.assertGreater(i, 0, "khong nho mon lay hong")
        self.assertIn("continue", self.than[i:i + 400], "phai `continue`, khong duoc `break`")

    def test_xoa_co_TRUOC_moi_lan_gui(self):
        self.assertIn("self.bank_fail = None\n            self.send(0x1E", self.than)

    def test_loc_mon_da_hong(self):
        self.assertIn('tid in getattr(self, "_lay_hong", ())', self.than)

    def test_nho_theo_PHIEN(self):
        self.assertIn("self._lay_hong = set()", self.src)

    def test_KHONG_di_NPC_khi_tui_day_va_khong_co_gi_cat(self):
        i = self.src.find("tui DAY va khong co gi de cat")
        self.assertGreater(i, 0, "van di NPC du chuyen do chac chan vo ich")
        khoi = self.src[max(0, i - 400):i + 300]
        self.assertIn("bag_capacity() - self.bag_used_slots() <= 0", khoi)
        self.assertIn("return kq", khoi)

    def test_comment_ma_3_da_sua_dung(self):
        """Ban cu chep nguyen cai sai cua protocal.lua."""
        i = self.src.find("def _on_bank_fail(")
        than = self.src[i:self.src.find("\n    def ", i + 10)]
        self.assertIn("MA 3 = TUI DO DAY", than)
        self.assertNotIn("3 = cat that bai", than)

    def test_APK_giong_PC(self):
        import io as _io
        apk = _io.open(os.path.join(ROOT, "android", "app", "src", "main", "python",
                                    "train_bot", "client.py"), encoding="utf-8").read()
        self.assertIn("self._lay_hong.add(tid)", apk)


if __name__ == "__main__":
    unittest.main()
