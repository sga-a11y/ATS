"""Trong MAP EVENT thi teleport ve thanh bi CHAN - phai DI BO ra truoc.

Su co party 2 (27/08 11:40): het 2K, chuyen pha train, ca 5 acc con dung o map 12932 (tang thap
Nhi Kieu) -> "PARTY co acc sai map -> ve thanh don nhau" -> `Teleport -> city 12001` lap lai
MOI 2 GIAY cho toi het deadline, khong bao gio ra duoc.

`go_to_town` von DA co chot y het cho Di Gioi ("di bo ra cong thoat truoc") va cho pho ban to doi
("server chan teleport -> tra False"), chi thieu map event.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


def _bot(map_id, dang_leo=False):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.current_map = map_id
    c._floor_crawl_started = dang_leo
    c.da_di_ra = []
    c.exit_event = lambda ev: (c.da_di_ra.append(ev.get("label")), True)[1]
    return c


class TestNhanBietMapEvent(unittest.TestCase):
    def test_tang_thap_2K(self):
        self.assertEqual((_bot(12932).event_dang_dung_trong() or {}).get("label"), "Nhị Kiều")

    def test_map_cho_va_tang_dau(self):
        for m in (12921, 12922):
            self.assertIsNotNone(_bot(m).event_dang_dung_trong(), "map %s" % m)

    def test_map_event_mot_tang(self):
        self.assertIsNotNone(_bot(10991).event_dang_dung_trong(), "map 40NPC / loan dau")

    def test_map_train_KHONG_bi_coi_la_event(self):
        """Nham cai nay la bot tu di bo ra khoi bai train - hong han."""
        for m in (21811, 23822, 12001, 0, None):
            self.assertIsNone(_bot(m).event_dang_dung_trong(), "map %s" % m)


class TestDiBoRaTruoc(unittest.TestCase):
    def test_dang_o_map_event_thi_di_bo_ra(self):
        c = _bot(12932)
        self.assertTrue(c._di_bo_ra_khoi_map_event())
        self.assertEqual(c.da_di_ra, ["Nhị Kiều"])

    def test_o_ngoai_thi_khong_lam_gi(self):
        c = _bot(21811)
        self.assertTrue(c._di_bo_ra_khoi_map_event())
        self.assertEqual(c.da_di_ra, [])

    def test_DANG_LEO_THAP_thi_KHONG_duoc_di_ra(self):
        """Di ra giua chung la mat het tang da leo."""
        c = _bot(12932, dang_leo=True)
        self.assertFalse(c._di_bo_ra_khoi_map_event())
        self.assertEqual(c.da_di_ra, [], "tu bo giua chung -> mat het tang")

    def test_loi_khi_di_ra_khong_lam_sap(self):
        c = _bot(12932)

        def _no(_ev):
            raise RuntimeError("hong")
        c.exit_event = _no
        self.assertFalse(c._di_bo_ra_khoi_map_event())


class TestNoiVaoGoToTown(unittest.TestCase):
    def test_go_to_town_goi_truoc_khi_teleport(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        m = re.search(r"def go_to_town\(.*?\n(.*?)\n    def ", src, re.S)
        self.assertIsNotNone(m)
        than = re.sub(r"#.*", "", m.group(1))
        i_ra = than.find("_di_bo_ra_khoi_map_event()")
        i_tele = than.find("while time.time() < deadline")
        self.assertGreater(i_ra, 0, "khong di bo ra -> spam teleport trong map event")
        self.assertLess(i_ra, i_tele, "phai di bo ra TRUOC vong teleport")


class TestDiBoRaHongThiKhongTeleport(unittest.TestCase):
    """Log APK 27/09 17:03 (map 12922, sau go_to_event Nhi Kieu): exit_event hong vi mat pos ->
    `go_to_town` van vao vong teleport -> "Teleport -> city 12001" MOI 2 GIAY suot 150s."""

    def _client(self, map_id):
        c = GameClient("user", "token")
        c.running = True
        c.current_map = map_id
        c._floor_crawl_started = False
        c.goi_da_gui = []
        c.send = lambda op, body=b"": c.goi_da_gui.append(op)
        c.in_di_gioi = lambda: False
        c.city_unlocked = lambda _cid: True
        return c

    def test_di_bo_ra_hong_thi_KHONG_gui_teleport(self):
        c = self._client(12922)
        c.exit_event = lambda ev: False
        with mock.patch("time.sleep"):
            self.assertFalse(c.go_to_town(12001, 0, tries=2, wait=0.01, battle_grace=0.0))
        self.assertEqual(c.goi_da_gui, [], "trong map event teleport bi chan -> gui la spam")

    def test_di_bo_ra_duoc_thi_teleport_binh_thuong(self):
        c = self._client(12922)

        def _ra(_ev):
            c.current_map = 12003
            return True
        c.exit_event = _ra
        with mock.patch("time.sleep"):
            c.go_to_town(12001, 0, tries=1, wait=0.01, battle_grace=0.0)
        self.assertTrue(c.goi_da_gui, "da ra ngoai event -> phai teleport")


class TestCongEventGiuToaDo(unittest.TestCase):
    """Goi doi map (0x0c) mang toa do moi. `_event_gate` xoa khong dieu kien -> vao map event xong
    pos=None -> exit_event khong co pos de tim duong ra."""

    def _qua_cong(self, co_toa_do):
        c = GameClient("user", "token")
        c.running = True
        c.current_map = 12921
        c.pos = (350, 330)
        c._wait_combat_clear = lambda idle=3.0: True
        c.move_to = lambda x, y: None

        def _send(op, body=b""):
            if op == 0x14 and body[:2] == b"\x08\x00":
                c.current_map = 12922
                if co_toa_do:
                    c.pos = (811, 431)
                    c._pos_valid_for_map = 12922
        c.send = _send
        with mock.patch("time.sleep"):
            self.assertTrue(c._event_gate(350, 330, 2, 12922))
        return c.pos

    def test_goi_doi_map_co_toa_do_thi_GIU(self):
        self.assertEqual(self._qua_cong(True), (811, 431))

    def test_khong_co_toa_do_moi_thi_xoa_toa_do_map_cu(self):
        self.assertIsNone(self._qua_cong(False))


if __name__ == "__main__":
    unittest.main()
