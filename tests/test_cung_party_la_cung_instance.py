"""CUNG PARTY = CUNG INSTANCE. Bang chung nay CHAC HON `0x03` va khong bi xoa.

User 14/09: "cung kenh va thay nhau roi ma van ket luan la khac kenh, dieu phoi ngu vay a".

`da_thay_tan_mat` (tu `0x03 PlayerAppear`) la bang chung tot, nhung no BI HUY moi lan doi scene /
roi tam nhin (`S:001-001`, `S:012-000`) - dung theo thiet ke. Ma lenh `dong_bo` lai BAT DOI KENH,
tuc no TU XOA dung cai bang chung ma lan sau no can:

    doi kenh -> xoa "da thay" -> ket luan khac instance -> lenh dong_bo -> doi kenh -> ...

CA THAT party 3, 14/09 (minh = minhminhmq):
    17:15:32 [minh] thay acc whitelist 'nanam' entity=94d0d7f8808d (0x03)
    17:18:00 [minh] thay acc whitelist 'laochin' entity=8255d8f8808d (0x03)
    17:18:00 [minh] Kenh hien tai = 2
    17:18:25 [minh] PARTY: 94d0d7f8 vao doi (leader=4ef7d7f8) -> roster 4 nguoi     <- DU
    17:18:33 [party 3] gen 13: viec=dong_bo - cung map nhung ['minhminhmq'] KHONG THAY duoc
                               dong doi (khac instance du cung so kenh)
    17:18:31 [minh] PARTY: 94d0d7f8 ROI doi (S:013-004) -> roster con 3
    17:18:31 [minh] PARTY: DOI TRUONG 4ef7d7f8 roi -> doi giai tan
Kenh cua `minh` trong ba phut: 7 -> 4 -> 1 -> 4 -> 2. Do la vong tu nuoi.

SERVER KHONG CHO LAP PARTY XUYEN INSTANCE: loi moi khong toi noi, accept khong an. Nen hai acc co
ten trong roster cua nhau la CHAC CHAN cung instance - khong can doi goi `0x03`, va bang chung nay
khong bi xoa khi doi kenh.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _C:
    """Client toi thieu: entity, map, roster, va bang 'da thay' (co the RONG)."""

    def __init__(self, ent, map_id=21001, roster=(), thay=()):
        self.self_entity = ent
        self.current_map = map_id
        self.running = True
        self.party_members = [bytes(x) for x in roster]
        self._thay = {bytes(x) for x in thay}

    def da_thay_tan_mat(self, ent):
        """Tra LY DO chua thay; rong ("") = DA thay - giong client that."""
        return "" if bytes(ent) in self._thay else "chua co 0x03"


E = {k: bytes([i]) * 8 for i, k in enumerate("abcde", start=1)}


def _song(*cs):
    return [(u, c) for u, c in cs]


class TestCungPartyThiKhongLechInstance(unittest.TestCase):
    def test_ca_that_p3_vua_vao_doi_thi_KHONG_bi_ket_lech(self):
        """`minh` vua vao party voi leader nhung chua kip nhan `0x03` cua ai."""
        ros = [E["a"], E["b"], E["c"], E["d"]]
        leader = _C(E["a"], roster=ros, thay=[E["b"], E["c"]])
        b = _C(E["b"], roster=ros, thay=[E["a"], E["c"]])
        c = _C(E["c"], roster=ros, thay=[E["a"], E["b"]])
        minh = _C(E["d"], roster=ros, thay=[])        # bang "da thay" bi xoa sach
        _lech = R._ai_lech_instance(
            0, _song(("a", leader), ("b", b), ("c", c), ("d", minh)), grace=0)
        self.assertEqual(_lech, [],
                         "cung roster ma van bao lech -> lenh dong_bo pha party vua lap")

    def test_KHONG_cung_party_va_KHONG_thay_nhau_thi_VAN_bao_lech(self):
        """Bo sung bang chung khong duoc lam mat kha nang bat lech that."""
        ros = [E["a"], E["b"], E["c"]]
        leader = _C(E["a"], roster=ros, thay=[E["b"], E["c"]])
        b = _C(E["b"], roster=ros, thay=[E["a"], E["c"]])
        c = _C(E["c"], roster=ros, thay=[E["a"], E["b"]])
        ngoai = _C(E["d"], roster=[], thay=[])        # khong trong doi, khong thay ai
        # `grace=0`: bo cua "lech lien tuc 30s" de test dung mot lan goi.
        _lech = R._ai_lech_instance(
            0, _song(("a", leader), ("b", b), ("c", c), ("d", ngoai)), grace=0)
        self.assertEqual(_lech, ["d"], "mat kha nang bat acc lech that")

    def test_chi_mot_ben_co_ten_trong_roster_cung_du(self):
        """Roster hai ben den khong cung luc - mot ben thay la du."""
        ros = [E["a"], E["b"], E["c"], E["d"]]
        leader = _C(E["a"], roster=ros, thay=[E["b"], E["c"]])
        b = _C(E["b"], roster=ros, thay=[E["a"], E["c"]])
        c = _C(E["c"], roster=ros, thay=[E["a"], E["b"]])
        minh = _C(E["d"], roster=[], thay=[])         # roster cua MINH chua ve
        _lech = R._ai_lech_instance(
            0, _song(("a", leader), ("b", b), ("c", c), ("d", minh)), grace=0)
        self.assertEqual(_lech, [], "leader da co ten no trong roster -> du de ket luan cung cho")


class TestNeoTrenNguon(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _ai_lech_instance(")
        self.than = src[i:src.find("\ndef ", i + 10)]

    def test_co_phep_hoi_cung_party(self):
        self.assertIn("def _cung_party(", self.than)

    def test_duoc_hoi_TRUOC_khi_hoi_0x03(self):
        i = self.than.find("def _thay(a, b):")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 700]
        _cp = khoi.find("_cung_party(a, b)")
        _03 = khoi.find("da_thay_tan_mat(")
        self.assertGreater(_cp, 0, "khong hoi 'cung party' -> van dua het vao 0x03")
        self.assertLess(_cp, _03, "hoi 0x03 truoc -> bang chung chac hon bi bo qua")


if __name__ == "__main__":
    unittest.main()
