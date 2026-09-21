# -*- coding: utf-8 -*-
"""CHI doi di PHO BAN TO DOI moi duoc moi member o MAP KHAC.

User 21/09 (party 20), kem anh cot "Trong PT": 4 acc tick xanh, acc o Trac Quan gach ngang.
"day la pt PB, no ko moi dua khac map la may code ngu".

Log khop tung dong:

    17:11:44 (LEADER) moi 3 member theo entity (live dung map/kenh): [...]      <- chi 3
    17:11:55 TRANG THAI: dieumot@21001(L) dieuhai@21001 dieuba@12001 dieubon@21001 dieunam@21001
    17:12:41 (LEADER) member ready 0/4 sau 40.2s -> HUY phong, relogin ca party

PHAM VI - user chot ngay sau do: "chi moi PB la duoc moi member o map khac, dung ngu toi muc cac
cai khac cung bo check cung map". Party THUONG van PHAI cung map (phai tap trung roi moi keo nhau
di train), chi rieng doi lap de di pho ban to doi la bo.

KENH thi khong bao gio bo: khac kenh la thuc su khong thay nhau (user xac nhan 30/08 - party 3
nam o kenh 12/12/12/2/1, moi mai khong ai vao doi).
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than_ham(src, dau):
    i = src.find(dau)
    return "" if i < 0 else src[i:src.find("\n    def ", i + 10)]


class _Peer:
    running = True

    def __init__(self, map_id, kenh=1):
        self.current_map = map_id
        self._kenh = kenh

    def kenh_that(self, *a, **k):
        return self._kenh


class TestCungMapChiBoChoPB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bot import client as C
        cls.C = C
        cls.ham = staticmethod(C.GameClient._bot_member_is_on_current_scene)

    def _cli(self, my_map=21001):
        from bot import client as C
        c = C.GameClient.__new__(C.GameClient)
        c.party_idx = 77
        c.current_map = my_map
        c._label = "t"
        c.kenh_that = lambda *a, **k: 1      # cung kenh -> phep kenh khong xen vao phep map
        return c

    def _hoi(self, peer_map, bo_qua_map):
        c = self._cli()
        ent = b"\x01" * 8
        with self.C._PARTY_LOCK:
            self.C._PARTY_CLIENTS.setdefault(77, {})[ent] = _Peer(peer_map)
        try:
            return type(self).ham(c, ent, bo_qua_map=bo_qua_map)
        finally:
            with self.C._PARTY_LOCK:
                self.C._PARTY_CLIENTS.get(77, {}).pop(ent, None)

    def test_party_THUONG_van_loai_dua_khac_map(self):
        ok, ly_do = self._hoi(12001, bo_qua_map=False)
        self.assertFalse(ok)
        self.assertIn("lech map", ly_do)

    def test_doi_di_PB_thi_KHONG_loai(self):
        ok, ly_do = self._hoi(12001, bo_qua_map=True)
        self.assertTrue(ok, "van loai -> dua o map khac khong bao gio vao duoc doi (%s)" % ly_do)

    def test_cung_map_thi_luon_duoc(self):
        self.assertTrue(self._hoi(21001, bo_qua_map=False)[0])


class TestNguonCoPB(unittest.TestCase):
    """Phai phu CA HAI engine: engine cu bat `dat_pha_pho_ban`, engine moi thi khong."""

    def setUp(self):
        self.than = _than_ham(_doc("bot", "client.py"),
                              "    def _lap_doi_de_di_pho_ban(self) -> bool:")
        self.assertTrue(self.than, "mat `_lap_doi_de_di_pho_ban`")

    def test_doc_ca_hai_nguon(self):
        self.assertIn("dang_pha_pho_ban(", self.than, "thieu nguon cua ENGINE CU")
        self.assertIn("_pe_pb_doi_level", self.than, "thieu nguon cua ENGINE MOI")

    def test_invite_members_dung_ham_nay(self):
        than = _than_ham(_doc("bot", "client.py"), "    def invite_members(self, gap: float = 1.0):")
        self.assertIn("_lap_doi_de_di_pho_ban()", than)
        self.assertIn("bo_qua_map=", than)

    def test_engine_moi_co_GAN_co(self):
        """Engine moi khong goi `dat_pha_pho_ban`, nen phai tu dat `_pe_pb_doi_level` moi nhip."""
        s = _doc("bot", "party_engine.py")
        self.assertIn("_pe_pb_doi_level = _pb_lv", s)

    def test_het_luot_PB_thi_co_ve_None(self):
        """Con luot moi duoc noi long; het luot la ve luat cu."""
        s = _doc("bot", "party_engine.py")
        i = s.find("_pb_lv = self._pb_doi_level()")
        self.assertGreater(i, 0)
        self.assertIn("_pe_pb_doi_level = _pb_lv", s[i:i + 700],
                      "gan mot gia tri khac thay vi chinh level -> het luot van con noi long")


class TestNhanhPB_KhongTuBia(unittest.TestCase):
    """Hai cach da thu o `quyet_dinh` va deu SAI - neo lai de khong ai lam lai."""

    @classmethod
    def setUpClass(cls):
        s = _doc("bot", "party_engine.py")
        i = s.find("    if anh.pb_doi_level is not None")
        assert i > 0
        khoi = s[i:i + 400]
        cls.lenh = "\n".join(d for d in khoi.split("\n") if not d.strip().startswith("#"))

    def test_KHONG_giu_phien_bang_viec_dang_lam(self):
        """Co suy tu chinh viec minh vua giao = tu nuoi chinh no -> khoa cung party vao PB (L1b)."""
        self.assertNotIn("viec_dang_lam", self.lenh)

    def test_KHONG_hoan_PB_vi_lech_map(self):
        """"Di PB doi thi co can gom map deo dau"."""
        for tu in ("DP_GOM", "DP_DONG_BO", "map_id", "reform_moi"):
            self.assertNotIn(tu, self.lenh,
                             "lay '%s' lam dieu kien PB -> mat luot PB moi lan party lech" % tu)


if __name__ == "__main__":
    unittest.main()
