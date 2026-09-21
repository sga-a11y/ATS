"""DANG TRONG TRAN: chi viec trong ALLOWLIST moi duoc giao, moi viec khac phai hoan.

Cho nay truoc la BLOCKLIST ("nhung viec KHONG duoc giao khi dang danh"), nen them viec moi la
phai nho khai bao vao do. Da quen HAI LAN, cung mot kieu hong:

    17/09 p56: 've_map' giao lai 260 lan lien tiep trong luc `BATTLE SEND`
               (user: "sao vua danh vua doi tele ve thanh la sao")
    21/09 p21: 'pb_doi' giao lai 3760 lan lien tiep trong luc `BATTLE SEND` -> leader ket trong
               tran khong vao duoc phong PB, 4 member vao roi ngoi cho -> "roster phong chi 0/4"
               -> HUY + relogin ca party, lap vo tan
               (user: "sao 4 dua trong PB, con 1 dua o ngoai" / "tao chan canh va ngu cua may")

Lan hai da co san ba viec moi (`2k_danh`, `2k_len_tang`, `fc_gom`) chua ai xet -> lan ba chi la
chuyen som muon. Bai test nay ep giu dang ALLOWLIST: viec them sau nay MAC DINH bi hoan, tuc quen
la quen theo huong an toan.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE


def _anh_mot_acc(viec_muon, dang_danh=True):
    """Dung anh sao cho `_quyet_dinh_goc` chac chan tra ve `viec_muon` cho acc dang danh."""
    a = PE.AnhAcc("a1", la_leader=True, song=True, map_id=12001, kenh=1, dang_danh=dang_danh)
    anh = PE.AnhParty(0, [a], can_bao_nhieu=0)
    goc = PE._quyet_dinh_goc
    PE._quyet_dinh_goc = lambda _x: {"a1": viec_muon}
    try:
        return PE.quyet_dinh(anh).get("a1")
    finally:
        PE._quyet_dinh_goc = goc


class TestMoiVIECDeuBiHoanTruKhiDuocPhep(unittest.TestCase):
    def test_tung_viec_mot(self):
        for viec in PE.THU_TU:
            got = _anh_mot_acc(viec, dang_danh=True)
            if viec in PE.VIEC_LAM_DUOC_GIUA_TRAN:
                self.assertEqual(got, viec, "'%s' nam trong allowlist ma van bi hoan" % viec)
            else:
                self.assertEqual(got, PE.VIEC_NGHI,
                                 "'%s' duoc giao giua tran -> gui goi giua tran" % viec)

    def test_khong_danh_thi_giao_binh_thuong(self):
        for viec in PE.THU_TU:
            self.assertEqual(_anh_mot_acc(viec, dang_danh=False), viec,
                             "'%s' bi hoan du acc KHONG danh" % viec)


class TestAllowlistGiuDungPhamVi(unittest.TestCase):
    def test_bon_viec_duoc_phep(self):
        """Moi lan noi rong allowlist deu phai co ly do - neo lai de khong ai them bua."""
        self.assertEqual(PE.VIEC_LAM_DUOC_GIUA_TRAN,
                         frozenset({PE.VIEC_NGHI, PE.VIEC_TRAIN,
                                    PE.VIEC_PB_DOI_THEO, PE.VIEC_THOAT}))

    def test_hai_ca_hong_that_deu_bi_chan(self):
        for viec in (PE.VIEC_VE_MAP, PE.VIEC_PB_DOI):
            self.assertNotIn(viec, PE.VIEC_LAM_DUOC_GIUA_TRAN)

    def test_ba_viec_2K_moi_cung_bi_chan(self):
        """Chung duoc them vao 20/09 ma chua ai xet - allowlist lo giup."""
        for viec in (PE.VIEC_2K_DANH, PE.VIEC_2K_LEN_TANG, PE.VIEC_FC_GOM):
            self.assertNotIn(viec, PE.VIEC_LAM_DUOC_GIUA_TRAN)


class TestCuaChanPhaiLaALLOWLIST(unittest.TestCase):
    """Neo DANG code: quay lai blocklist la mat toan bo tac dung phong ngua."""

    def test_quyet_dinh_dung_not_in_allowlist(self):
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def quyet_dinh(")
        than = src[i:src.find("\ndef ", i + 10)]
        # CHI xet khoi `_dang_danh`. `VIEC_DI_CHUYEN` van dung hop le o cua khac trong cung ham
        # (trong thap 2K khong teleport duoc) - do la muc dich KHAC, dung nham hai cai.
        j = than.find("_dang_danh = {")
        self.assertGreater(j, 0)
        khoi = than[j:than.find("# DANG TRONG THAP", j)]
        self.assertIn("not in VIEC_LAM_DUOC_GIUA_TRAN", khoi)
        self.assertNotIn("VIEC_DI_CHUYEN", khoi,
                         "quay lai blocklist -> viec moi lai lot giua tran")


class TestChoThiHanhTuBaoVe(unittest.TestCase):
    """Mot ham GUI GOI phai tu cho het tran, khong tin nguoi goi: engine cu goi
    `_handle_auto_team_dungeon` tu cho khac, va code sau nay cung vay."""

    def test_mo_phong_PB_tu_cho_het_tran(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _handle_auto_team_dungeon(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertLess(than.find("in_combat()"), than.find("wait_mission_steps"),
                        "phai cho het tran TRUOC khi bat dau mo phong")
        self.assertIn("_wait_combat_clear", than)


if __name__ == "__main__":
    unittest.main()
