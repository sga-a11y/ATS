"""Rule toi thuong: PHAI DU PARTY. Member rung DOC DUONG thi khong duoc train thieu.

Bug that (party 2, party.log 21/08):
  18:17:20 [sga002] RECONNECT: ép đồng bộ theo leader -> login lai sau 1s   (ca party cung 1s)
  18:18:08 [sga002] SERVER NGAT KET NOI: DANG NHAP QUA THUONG XUYEN (ma 90)
  18:18:16 [gamo] (LEADER) reform: 4/4 member join lai -> KEO qua cong ra train map
  18:18:23 [gamo] Party roster: 3 member          <- rung 1
  18:18:59 [gamo] Party roster: 2 member          <- rung tiep
  18:20:00 [gamo] (LEADER) toi train map theo party (da partied) -> bo qua moi lai
  ... roi train voi 3 acc, bo 2 acc lai.
Hai loi noi tiep nhau:
  1. ep dong bo -> CA PARTY relogin cach nhau 1s -> server chan toc do (ma 90) -> acc khong vao lai
  2. leader thay `via_route` la tin "da partied", KHONG dem lai member -> keo di thieu nguoi
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")


class TestPartyMustBeFull(unittest.TestCase):
    def test_via_route_van_phai_DEM_LAI_member(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        anh = snapshot([account(so_member=1), account("b", so_member=1)])
        self.assertEqual(E.quyet_dinh(anh)["a"], E.VIEC_RA_SPOT)

    def test_thieu_member_thi_DI_MOI_LAI_chu_khong_bo_qua(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        anh = snapshot([account(so_member=0), account("b", so_member=0)])
        self.assertEqual(E.quyet_dinh(anh)["a"], E.VIEC_LAP_PARTY)

    def test_thieu_nguoi_KHONG_con_vong_tu_cho(self):
        self.assertNotIn('while _dem_san_sang(pidx) < st["n_members"]:', SRC)

    def test_relogin_hang_loat_duoc_GIAN_CACH(self):
        """5 acc cung wait=1 -> server chan toc do. Phai xep hang theo vi tri trong party."""
        self.assertIn("_them = _gian_buoc * _order.index(username)", SRC)
        self.assertIn("_gian_buoc = 3 if forced else", SRC, "mat buoc gian cua nhanh forced")

    def test_gian_cach_cho_ra_moc_tang_dan(self):
        """Mo phong dung cong thuc trong file: 1s, 4s, 7s, 10s, 13s cho 5 acc (nhanh forced)."""
        m = re.search(r"_gian_buoc = (\d+) if forced else", SRC)
        buoc = int(m.group(1))
        moc = [1 + buoc * i for i in range(5)]
        self.assertEqual(moc, [1, 4, 7, 10, 13])
        self.assertGreaterEqual(moc[-1] - moc[0], 10, "gian cach qua hep, van co the bi chan")


if __name__ == "__main__":
    unittest.main()
