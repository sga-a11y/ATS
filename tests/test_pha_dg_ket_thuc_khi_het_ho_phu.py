# -*- coding: utf-8 -*-
"""PHA DI GIOI ket thuc khi HET TIME **VA** KHONG CON DI GIOI HO PHU.

User chot 22/09: "phai la pha DG ket thuc khi het time va ko con DG phu".

Truoc day chi xet HET GIO: het gio la doi pha sang train ngay, so ho phu con lai trong tui bi VUT.
Giu pha DG thi `VIEC_DI_GIOI` con duoc giao, ma chinh nhanh do goi `ho_phu(client)` -> server nap
lai gio -> vao tiep. KHONG can them duong goi ho phu nao khac.

Ca that 22/09 (user: "engine moi hinh nhu ko tu dung Di gioi ho phu" -> "p1, co Di gioi ho phu
trong tui ma ko dung kia"):
  - party 1 (`mode=digioi_train`, tick BAT, 02:00 `pha=digioi` map=49942 - dang trong DG):
    KHONG MOT DONG ho phu nao cho ca 5 acc;
  - `[dtbay]` 02:41:17 da o map 12003 (Quang Truong, NGOAI DG) roi 02:41:18 moi
    "Di Gioi Ho Phu - con 3 phut (<15), da gui lenh dung".
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE


def _doc_src():
    with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
        return fh.read()


class TestPhaDGKetThucKhiNao(unittest.TestCase):
    def _anh(self, het_gio, con_ho_phu):
        accs = [PE.AnhAcc("a%d" % i, song=True, map_id=12001, kenh=1,
                          con_gio_dg=not het_gio, con_ho_phu=con_ho_phu)
                for i in range(3)]
        return PE.AnhParty(0, accs, can_bao_nhieu=2, pha=PE.PHA_DG)

    def _doi_pha(self, het_gio, con_ho_phu, co_pha_train=True):
        eng = PE.PartyEngine.__new__(PE.PartyEngine)
        eng.pha = PE.PHA_DG
        eng.co_pha_train = co_pha_train
        eng.pidx = 0
        eng._ghi_pha = None
        eng._log = None
        eng._doi_pha_neu_het_gio_dg(self._anh(het_gio, con_ho_phu))
        return eng.pha

    def test_het_gio_VA_het_ho_phu_thi_DOI_sang_train(self):
        self.assertEqual(self._doi_pha(True, False), PE.PHA_TRAIN)

    def test_het_gio_nhung_CON_ho_phu_thi_GIU_pha_DG(self):
        self.assertEqual(self._doi_pha(True, True), PE.PHA_DG,
                         "doi sang train la vut so ho phu con lai trong tui")

    def test_con_gio_thi_giu_pha_DG(self):
        self.assertEqual(self._doi_pha(False, False), PE.PHA_DG)

    def test_mode_digioi_THUAN_khong_doi_pha(self):
        """Mode khong co pha train: het gio la het viec, khong doi pha di dau."""
        self.assertEqual(self._doi_pha(True, False, co_pha_train=False), PE.PHA_DG)


class TestDocThangTuTui(unittest.TestCase):
    def test_doc_bag_counts_khong_nho_so_rieng(self):
        s = _doc_src()
        i = s.find("con_ho_phu=bool(")
        self.assertGreater(i, 0, "mat cho chup `con_ho_phu`")
        self.assertIn("bag_counts", s[i:i + 200])
        self.assertIn("HO_PHU_TID", s[i:i + 200])

    def test_tid_dung_bang_lenh_dung_ho_phu(self):
        """Lech tid la dem nham mon khac -> pha DG khong bao gio ket thuc."""
        self.assertEqual(PE.HO_PHU_TID, 0xff8c)
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.assertIn("self.use_item(0xff8c, target=0)", fh.read())

    def test_dieu_phoi_cung_xet_ho_phu(self):
        """`ca_party_het_gio_dg` (nguon cua nhanh doi pha trong `quyet_dinh_cap_party`) phai xet
        y het - lech mot cho la hai nguon ket luan khac nhau ve cung mot party."""
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("ca_party_het_gio_dg=bool(")
        self.assertGreater(i, 0)
        self.assertIn("0xff8c", s[i:i + 400])


class TestKhongThemDuongThua(unittest.TestCase):
    """Giu pha DG la DU: nhanh `VIEC_DI_GIOI` tu goi ho phu roi vao lai. Them mot duong goi ho phu
    nua (vd trong `_duy_tri`) la lam HAI LAN cung mot viec."""

    def test__duy_tri_KHONG_goi_ho_phu(self):
        s = _doc_src()
        i = s.find("def _duy_tri(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertNotIn("ho_phu", than)

    def test_nhanh_VIEC_DI_GIOI_van_goi_ho_phu(self):
        s = _doc_src()
        i = s.find("    if viec == VIEC_DI_GIOI:")
        self.assertGreater(i, 0)
        self.assertIn("ho_phu(client)", s[i:i + 1200])


if __name__ == "__main__":
    unittest.main()
