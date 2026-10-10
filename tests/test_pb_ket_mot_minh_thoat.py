"""Acc KET MOT MINH trong map PB (party da ra ngoai) -> engine giao `thoat_pb`, khong ra thi relogin.

Ca that 11/10 party 1 (user: "sao co dua trong PB doi 1 minh"):
    00:53:05 [baybay] Party roster: 4 member, minh LA LEADER       <- leader cu rot
    00:53:07 [party 1] ENGINE: sga005 da relogin -> tao worker MOI <- het thieu_acc_song
    00:53:17 [baybay] PARTY: f4d0d7f8 ROI doi -> roster con 0 nguoi
    00:55:49 [baybay] KHONG o party nao ... -> KHONG gui 013-004 [map=62012]
    00:55:45 (LEADER) lv80 SERVER moi cong nhan 3/4 ... -> HUY      <- lap 13 lan toi khi Stop
`thoat_pb` cu chi giao khi `thieu_acc_song`; leader login lai xong la thoi giao. `047-010` gui 14
lan khong ra. User chot 11/10: dang trong PB ma relogin la ra map thuong (CORE_FLOW Buoc 7).
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C           # noqa: E402
from bot import party_engine as E     # noqa: E402

MAP_PB = 62012
MAP_THANH = 24001


def _anh_cap():
    return E.AnhCapParty(can_lap_doi=False, lech_tu=None, het_lech_tu=None,
                         o_thanh_tu=None, bay_gio=1)


class _Fake:
    running = True
    _pe_xong_chore = True
    _pe_xong_daily = True
    current_channel = 1
    party_members = ()
    mission_steps_loaded = False
    bag_counts = {}

    def __init__(self, map_id):
        self.current_map = map_id

    def in_combat(self):
        return False

    def in_di_gioi(self):
        return False

    def in_team_dungeon(self):
        return C.in_instance_map(self.current_map)

    def digioi_minutes_live(self):
        return 0

    def kenh_dang_chac(self):
        return True


class _Worker:
    def __init__(self, client):
        self.client = client
        self.sent = []

    def dang_ban(self):
        return False

    def giao(self, viec):
        self.sent.append(viec)
        return True


def _engine(rows):
    eng = E.PartyEngine(0, lambda: rows, doc_party=_anh_cap, ap_dung_party=lambda *_: None)
    for u, c, _l in rows:
        if c is not None:
            eng.workers[u] = _Worker(c)
    return eng


def _p1():
    ket = _Fake(MAP_PB)
    rows = [("sga005", _Fake(MAP_THANH), True), ("sga006", _Fake(MAP_THANH), False),
            ("sga007", ket, False), ("sga008", _Fake(MAP_THANH), False)]
    return rows, ket


class TestPhatHienKetPB(unittest.TestCase):
    def test_chua_du_30s_thi_CHUA_keo(self):
        """Luc START / luc danh xong ca doi vao-ra lech nhau vai giay la binh thuong."""
        rows, _k = _p1()
        eng = _engine(rows)
        eng.nhip()
        self.assertNotIn(E.VIEC_THOAT_PB, eng.workers["sga007"].sent)

    def test_qua_30s_thi_giao_thoat_pb_cho_dua_ket_con_lai_NGHI(self):
        rows, ket = _p1()
        eng = _engine(rows)
        eng.nhip()
        eng._ket_pb_tu["sga007"] -= E.KET_PB_GRACE_SEC + 1
        eng.nhip()
        self.assertEqual(eng.workers["sga007"].sent[-1], E.VIEC_THOAT_PB)
        for u in ("sga005", "sga006", "sga008"):
            self.assertEqual(eng.workers[u].sent[-1], E.VIEC_NGHI)
        self.assertTrue(getattr(ket, "_pb_bo_chay", False))

    def test_ca_doi_cung_trong_PB_thi_khong_keo(self):
        rows = [("a", _Fake(MAP_PB), True), ("b", _Fake(MAP_PB), False)]
        eng = _engine(rows)
        eng.nhip()
        eng._ket_pb_tu.clear()
        self.assertEqual(eng._tim_ket_pb(eng.chup().accs), ())
        self.assertNotIn(E.VIEC_THOAT_PB, eng.workers["a"].sent + eng.workers["b"].sent)

    def test_ra_khoi_PB_thi_xoa_moc_gio(self):
        rows, ket = _p1()
        eng = _engine(rows)
        eng.nhip()
        self.assertIn("sga007", eng._ket_pb_tu)
        ket.current_map = MAP_THANH
        eng.nhip()
        self.assertEqual(eng._ket_pb_tu, {})


class TestThiHanhThoatPB(unittest.TestCase):
    def test_co_thoat_pb_fn_thi_dung_no(self):
        goi = []
        ok = E.thi_hanh(object(), E.VIEC_THOAT_PB, lambda: True,
                        thoat_pb_fn=lambda c: goi.append(c) or True)
        self.assertTrue(ok)
        self.assertEqual(len(goi), 1)

    def test_engine_truyen_thoat_pb_fn_xuong_thi_hanh(self):
        eng = E.PartyEngine(0, lambda: [], thoat_pb_fn="X")
        self.assertEqual(eng._thoat_pb_fn, "X")


class TestNoiDayEngineCu(unittest.TestCase):
    def test_run_party_noi_exit_pb_or_reconnect(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("thoat_pb_fn=_thoat_pb_engine_moi", src)
        i = src.index("def _thoat_pb_engine_moi")
        self.assertIn("_exit_pb_or_reconnect(", src[i:i + 1200])


if __name__ == "__main__":
    unittest.main()
