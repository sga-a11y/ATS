"""LECH KENH do bang THAY NHAU, khong bang SO KENH - va leader cung bi soi nhu moi nguoi.

User 13/09: "biet duoc nhung nguoi xung quanh minh thi biet duoc co cung kenh hay ko, co cai lon
gi ma ko chac" -> "ma thuc ra cai party 1 la leader deo phai o kenh 6, no sai chu ko phai member
sai".

So kenh la so NHO va sai duoc (KNOWLEDGE.md muc 7: game KHONG CO lenh hoi "toi dang o kenh nao").
`0x03 PlayerAppear` thi chi server gui, va chi gui cho nguoi CUNG SCENE + CUNG INSTANCE.

CA THAT (party 1, 10 phut khong lap noi party):

    14:24:40..14:32:46 [party 1] LAP LAI PARTY (chihao188=0 sga013=0 sga014=0 sga015=0 sga017=0)
    14:32:56 [thbay] (LEADER) moi 2 nguoi ma SERVER CHUA HE cho thay ho quanh minh:
                     ['7c5dd8f8:chua co 0x03', '0c1dd3f8:chua co 0x03']

Ca party cung map 21833, cung toa do (3020..3040, 1000..1020), entity leader moi ĐÚNG het voi
entity that cua tung member. Dieu phoi nhin SO KENH thay "cung kenh 6" -> ra lenh MOI mai, ma loi
moi khong the toi noi vi khac instance.

HAI CAI SAI CUA BAN CU:
  1. `_party_khong_thay_nhau` chi nhin tu MAT LEADER -> chinh leader lech thi khong ai phat hien.
  2. Dieu phoi LOAI acc co `kenh_dang_chac()==False` ra khoi phep dem -> "khong biet" bi xu nhu
     "khong sao" (L13), roi ra lenh moi.

KHONG PHAI BAO CAO (L2): phep nay chay trong luong dieu phoi va doc THANG `entity_meta` cua tung
client (ca party chung mot tien trinh). Khong goi vao luong acc, khong cho acc ghi co.
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

MAP_TRAIN = 21833


class _C:
    """Client gia: `thay` = tap entity ma server DA bao no thay."""

    def __init__(self, ent, map_id=MAP_TRAIN):
        self.self_entity = ent
        self.current_map = map_id
        self.running = True
        self.thay = set()

    def da_thay_tan_mat(self, entity):
        return "" if bytes(entity) in self.thay else "chua co 0x03"


def _lien_ket(nhom):
    """Cac acc trong `nhom` deu thay nhau (cung instance)."""
    for a in nhom:
        for b in nhom:
            if a is not b:
                a.thay.add(bytes(b.self_entity))


class _Nen(unittest.TestCase):
    PARTY = 0
    TEN = ("thbay", "thnam", "thba", "thbon", "chihao")

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "thbay", u == "thbay") for u in self.TEN]
        self.cs = {u: _C(bytes([i + 1]) * 4) for i, u in enumerate(self.TEN)}
        self.song = [(u, self.cs[u]) for u in self.TEN]

    def tearDown(self):
        R.party_accounts = self._accounts

    def _qua_grace(self):
        for c in self.cs.values():
            c._thay_nhau_tu = {"tu": time.time() - 999}

    def _lech(self):
        return R._ai_lech_instance(self.PARTY, self.song)


class TestLeaderCungBiSoi(_Nen):
    def test_LEADER_lech_thi_chi_dich_danh_LEADER(self):
        """Ca party 1: bon member thay nhau, rieng leader o instance khac."""
        _lien_ket([self.cs[u] for u in self.TEN[1:]])
        self._qua_grace()
        self.assertEqual(self._lech(), ["thbay"])

    def test_mot_member_lech(self):
        _lien_ket([self.cs[u] for u in self.TEN if u != "chihao"])
        self._qua_grace()
        self.assertEqual(self._lech(), ["chihao"])

    def test_hai_member_lech(self):
        _lien_ket([self.cs[u] for u in ("thbay", "thnam", "thba")])
        _lien_ket([self.cs["thbon"], self.cs["chihao"]])
        self._qua_grace()
        self.assertEqual(self._lech(), ["chihao", "thbon"])

    def test_ca_party_thay_nhau_thi_khong_ai_lech(self):
        _lien_ket(list(self.cs.values()))
        self._qua_grace()
        self.assertEqual(self._lech(), [])


class TestKhongKetLuanBua(_Nen):
    def test_chua_het_GRACE_thi_chua_ket_luan(self):
        """Vua toi map chua kip nhan 0x03 cua nhau la binh thuong."""
        _lien_ket([self.cs[u] for u in self.TEN[1:]])
        self.assertEqual(self._lech(), [], "ket toi ngay khi chua het an han")

    def test_chia_doi_2_2_thi_khong_ket_luan(self):
        """Khong co da so ro rang -> im, de nhanh khac lo (L13)."""
        R.party_accounts = lambda pidx: [(u, "p", u == "a", False) for u in ("a", "b", "c", "d")]
        cs = {u: _C(bytes([i + 1]) * 4) for i, u in enumerate(("a", "b", "c", "d"))}
        _lien_ket([cs["a"], cs["b"]])
        _lien_ket([cs["c"], cs["d"]])
        for c in cs.values():
            c._thay_nhau_tu = {"tu": time.time() - 999}
        self.assertEqual(R._ai_lech_instance(self.PARTY, list(cs.items())), [])

    def test_party_hai_nguoi_thi_khong_co_da_so(self):
        _hai = [(u, self.cs[u]) for u in self.TEN[:2]]
        self.assertEqual(R._ai_lech_instance(self.PARTY, _hai), [])

    def test_dang_LECH_MAP_thi_nhanh_khac_lo(self):
        """Lech map la viec cua bac gom map, khong ket luan instance o day."""
        for i, u in enumerate(self.TEN):
            self.cs[u].current_map = MAP_TRAIN if i < 2 else 12001
        self._qua_grace()
        self.assertEqual(self._lech(), [])

    def test_chua_biet_entity_thi_khong_ket_toi(self):
        for u in self.TEN[1:]:
            self.cs[u].self_entity = None
        self._qua_grace()
        self.assertEqual(self._lech(), [])


class TestMotBenThayLaDu(_Nen):
    """Thay mot chieu cung du ket luan cung instance - `0x03` chi ban khi XUAT HIEN trong tam nhin,
    nen dua den truoc co the chua nhan goi cua dua toi sau."""

    def test_thay_mot_chieu(self):
        for u in self.TEN[1:]:
            self.cs["thbay"].thay.add(bytes(self.cs[u].self_entity))
        self._qua_grace()
        self.assertEqual(self._lech(), [])


class TestDieuPhoiRaLenhDONG_BO(unittest.TestCase):
    def setUp(self):
        # LUAT cap party da chuyen vao `bot/party_engine.py` (21/09), phan thi hanh van o
        # `run_party_digioi.py` -> doc CA HAI, luat truoc.
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src += fh.read()

    def test_bac_nay_nam_TRUOC_bac_moi(self):
        i_ins = self.src.find("anh.ai_lech_instance")
        i_moi = self.src.find("elif not anh.du_doi:")
        self.assertGreater(i_ins, 0, "mat bac khac-instance")
        self.assertGreater(i_moi, 0)
        self.assertLess(i_ins, i_moi, "phai xu khac-instance TRUOC khi ra lenh moi")

    def test_ra_lenh_dong_bo_kenh(self):
        # NEO THEO THAN NHANH, khong theo cua so ky tu co dinh: them mot doan comment la cua so
        # truot ra ngoai va test do ma luat khong he bi pha (da dinh hai lan: 21/09 va 22/09).
        i = self.src.find("anh.ai_lech_instance")
        self.assertGreater(i, 0, "mat bac khong-thay-nhau")
        j = self.src.find("\n    elif ", i)
        self.assertIn("DP_DONG_BO", self.src[i:j])

    def test_KHONG_danh_dau_kenh_HONG(self):
        """User chot 22/09: instance voi kenh la MOT -> kenh khong "hong", dung danh dau."""
        i = self.src.find("anh.ai_lech_instance")
        than = self.src[i:self.src.find("\n    elif ", i)]
        self.assertNotIn("kenh_hong", than, "kenh khong hong - dung dung lai co nay")

    def test_KHONG_bat_acc_bao_cao(self):
        """Doc thang client trong luong dieu phoi (L2), khong co bang bao cao nao."""
        i = self.src.find("def _ai_lech_instance(")
        j = self.src.find("\ndef ", i + 10)
        than = self.src[i:j]
        self.assertIn("da_thay_tan_mat(", than)
        for _xau in ("st[", "report", "bao_cao"):
            self.assertNotIn(_xau, than, "dung bang cap party / bao cao: " + _xau)


if __name__ == "__main__":
    unittest.main()
