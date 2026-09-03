"""Nhan party trong log battle phai KHOP so party tren GUI (dem tu 1).

User 03/09: "p28 tat roi ma sao van co log". Truy ra KHONG phai bug bot: `party_battle.py` in
thang `party_idx` (0-based, tu `config.ACCOUNT_PARTY = {... enumerate(PARTIES) ...}`) trong khi
GUI dem party tu 1 va cac dong log khac cua `run_party_digioi` da in `pidx + 1`.

=> CUNG mot file log co HAI kieu danh so lech nhau 1. Party 28 tren GUI tat that (nhan cu la
`[P27 ...]`, dung o 23:27:49), con `[P28 ...]` van chay la cua party 29 (`hoangt306-310`, khop
generation g=392 voi log cua chinh `hoangt306` cung giay). Doc log la dinh bay ngay.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.party_battle import PartyBattleCoordinator, _nhan_party   # noqa: E402


def _src(p):
    with io.open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


class TestNhanParty(unittest.TestCase):
    def test_party_idx_0_hien_la_1(self):
        """party_idx 0-based -> GUI 1-based."""
        self.assertEqual(_nhan_party(0), 1)
        self.assertEqual(_nhan_party(27), 28)
        self.assertEqual(_nhan_party(28), 29)

    def test_client_solo_giu_nguyen_khong_cong(self):
        """Client solo co party_idx la tuple ("solo", id(client)) -> khong cong duoc."""
        khoa = ("solo", 140234)
        self.assertEqual(_nhan_party(khoa), khoa)

    def test_None_giu_nguyen(self):
        self.assertIsNone(_nhan_party(None))

    def test_bool_KHONG_bi_coi_la_so(self):
        """`isinstance(True, int)` la True trong Python -> phai loai bool ra, khong thi
        True -> 2 (vo nghia va am tham)."""
        self.assertIs(_nhan_party(True), True)
        self.assertIs(_nhan_party(False), False)


class TestCoordinatorDungNhan(unittest.TestCase):
    def test_luu_nhan_luc_khoi_tao(self):
        c = PartyBattleCoordinator(27)
        self.assertEqual(c.party_idx, 27, "party_idx GOC phai giu nguyen (dung lam key registry)")
        self.assertEqual(c.nhan_party, 28, "nhan hien log phai khop GUI")

    def test_moi_cho_log_deu_dung_nhan_chu_khong_dung_party_idx(self):
        src = _src("bot/party_battle.py")
        i = src.find("class PartyBattleCoordinator")
        than = src[i:]
        self.assertIn("[P%s BATTLE] conflicting copies", than)
        self.assertNotIn("self.party_idx, key", than,
                         "dong 'conflicting copies' van in party_idx 0-based")
        self.assertNotIn("f\"[P{self.party_idx}", than,
                         "prefix battle log van in party_idx 0-based")
        self.assertEqual(than.count("self.nhan_party"), 4,
                         "phai co dung 4 cho: 1 gan trong __init__ + 3 cho log "
                         "(1 warning 'conflicting copies' + 2 prefix co/khong co turn)")


class TestKhopVoiRunPartyDigioi(unittest.TestCase):
    def test_run_party_digioi_cung_dem_tu_1(self):
        """Doi chieu: cac dong log party ben `run_party_digioi` dung `pidx + 1`."""
        src = _src("run_party_digioi.py")
        self.assertIn("pidx + 1", src)


if __name__ == "__main__":
    unittest.main()
