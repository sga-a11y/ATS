"""Ra lenh doi kenh thi PHAI lap lai party - va khong duoc len tang mot minh.

Party 5 (06/09) - user: "p5 leader di 1 minh":

    16:34:04  4 member: Doi kenh 2 THAT BAI: khong co khu do de doi (result=2)
    16:34:14  4 member: Doi kenh 2 THAT BAI: DANG TO DOI thi khong doi khu duoc (result=3)
    16:34:14  4 member: -> roi party roi thu lai
    16:34:14  4 member: Roi/giai tan party cu (gui ID doi truong=6860d8f8)
    16:34:15  4 member: Doi kenh OK -> 2          <- doi duoc, nhung DA RA KHOI DOI
    16:34:23  leader:   Chuyen kenh -> 2
    16:34:26  leader:   Doi kenh OK -> 2
    16:34:53  leader:   qua cong idx=2 -> map 12929   <- DOI DA TAN, khong ai bi keo theo
    16:35:38  leader:   tang 6 chi danh duoc 0/3 tran <- di mot minh, danh khong noi
    16:36:01  DIEU PHOI: gom - party dang o 2 MAP khac nhau [12928, 12929]  <- ra lenh vao hu khong

Server CAM doi kenh khi dang trong doi (`result=3`) -> muon doi kenh la PHAI roi doi truoc. Do la
luat cua game, member lam dung. SAI la o NGUOI RA LENH: dieu phoi bao doi kenh roi bo mac hau qua.

Hai cho phai vao:
  1. Dieu phoi chot `kenh_dich` -> mac no `kenh_no_lap_party`. Khi ca party ve chung kenh ma doi
     khong con du -> RA LENH LAP LAI PARTY.
  2. Vong leo thap: TRUOC khi len tang phai DU PARTY. Chua du thi moi lai tai cho; het han van
     chua du thi THOI leo (de dieu phoi xu ly) - tuyet doi khong len tang mot minh.
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


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _C:
    def __init__(self, channel=1, map_id=12928):
        self.running = True
        self.current_map = map_id
        self.current_channel = channel
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0
        # ROSTER SERVER (`0x0d`) - dieu phoi dem doi bang day (L2d), khong bang so nho cua bot
        self.party_members = [b"x" * 8] * 2


class TestDieuPhoiNoLapLaiParty(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self._jmc = R.joined_member_count
        # CO LAP config: party 0 tren may user la mode event 40NPC, va ngoai gio event thi dieu
        # phoi KHONG con viec gi (`_party_40npc_ngoai_gio`) -> test do/xanh theo dong ho that.
        self._pcfg = dict(getattr(R.config, "PARTY_CONFIG", {}))
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}

    def tearDown(self):
        R.party_accounts = self._pa
        R.joined_member_count = self._jmc
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        R.config.PARTY_CONFIG = self._pcfg

    def _song(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c
        return [(u, R.account_clients[u]) for u in self.ACCS if u in R.account_clients]

    def test_chung_kenh_ma_doi_TAN_thi_ra_lenh_lap_lai(self):
        """Doc THANG roster SERVER (`c.party_members`), khong dung co "no" nao ca."""
        song = self._song(a1=_C(1), a2=_C(1), a3=_C(1))
        for _u, c in song:
            c.party_members = []                        # doi da tan (de doi kenh)
        gen = self.st["reform_gen"]
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertGreater(self.st["reform_gen"], gen, "chung kenh ma doi tan van khong lap lai")

    def test_doi_con_DU_thi_khong_lam_gi_them(self):
        song = self._song(a1=_C(1), a2=_C(1), a3=_C(1))
        for _u, c in song:
            c.party_members = [b"x" * 8] * 2            # van du (3 acc -> roster 2)
        gen = self.st["reform_gen"]
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertEqual(self.st["reform_gen"], gen)

    def test_KHONG_dung_co_no_ma_DOC_THANG_roster(self):
        src = _doc("run_party_digioi.py")
        self.assertNotIn("kenh_no_lap_party", src, "co 'no' = suy dien; roster doc thang duoc")
        i = src.find('"-> LAP LAI PARTY", pidx + 1')
        self.assertGreater(i, 0, "khong con cho ra lenh lap lai party")
        self.assertIn("_thieu_doi(pidx, song)", src[i - 700:i + 300],
                      "phai dem doi bang ROSTER SERVER, khong bang so nho cua bot (L2d)")


class TestKhongLenTangMotMinh(unittest.TestCase):
    def setUp(self):
        self.fc = _doc("bot", "floor_crawl.py")

    def test_kiem_du_party_TRUOC_khi_qua_cong(self):
        i = self.fc.find("client._enter_gate(center[0]")
        self.assertGreater(i, 0)
        truoc = self.fc[:i]
        j = truoc.rfind("du_party()")
        self.assertGreater(j, 0, "khong kiem party truoc khi len tang")
        self.assertGreater(j, truoc.rfind("for idx in _battle_idx"),
                           "phai kiem SAU khi danh, ngay truoc cong")

    def test_chua_du_thi_KHONG_di(self):
        i = self.fc.find("chua du party -> KHONG len tang mot minh")
        self.assertGreater(i, 0)
        self.assertIn("break", self.fc[i:i + 200])

    def test_callback_la_tuy_chon(self):
        """Cac cho goi khac (test, event khac) khong truyen thi van chay."""
        self.assertIn("du_party=None", self.fc)
        self.assertIn("if du_party is not None", self.fc)


class TestMoiLaiNgayTaiCho(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_co_ham_du_party_2k(self):
        i = self.src.find("def _du_party_2k(")
        self.assertGreater(i, 0)
        than = self.src[i:i + 2200]
        self.assertIn("_invite_party_participants(", than, "chua du ma khong moi lai")
        self.assertIn("DU_PARTY_TRUOC_CONG_SEC", than, "cho vo han la treo ca vong leo")

    def test_truyen_vao_start_floor_crawl(self):
        i = self.src.find("start_floor_crawl(")
        self.assertIn("_du_party_2k", self.src[i:i + 500])

    def test_han_cho_du_dai(self):
        self.assertGreaterEqual(R.DU_PARTY_TRUOC_CONG_SEC, 30)


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_giong(self):
        for f, key in (("floor_crawl.py", "KHONG len tang mot minh"),
                       ("client.py", "_chan_switch_luc"),
                       ("run_party_digioi.py", "_doc_ket_qua_doi_kenh")):
            self.assertIn(key, _doc("android", "app", "src", "main", "python", "train_bot", f))


if __name__ == "__main__":
    unittest.main()
