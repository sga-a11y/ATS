"""P3 ket 1 tieng (06/09) vi mot acc vao kenh DAY roi DO LAI cho leader "pick lai".

Dien bien that:
    02:38:20 [nanam]  (LEADER) Kenh it nguoi MA DU CHO ca party (5): kenh 15 (11/20) -> chuyen sang
    02:38:21 [nanam]  (LEADER) chon kenh 15 cho ca party (5 acc)
    02:38:25 [laochin](member) da chuyen sang kenh chung = 15   <- 3 dua nay BREAK ra khoi vong
    02:38:30 [batbat] Doi kenh 15 THAT BAI: khu da day nguoi (result=4)
    02:38:31 [batbat] (member) khong doi duoc sang kenh chung 15 -> bao leader pick lai
    02:38:32 [nanam]  (LEADER) sync kenh/map FAIL -> BUMP reform_gen, ca party ve thanh regroup
    02:39:04 .. 03:34:32 [nanam] (LEADER) CHO du member san sang (3/4)...   (lap 1 tieng)
              [nanam] (LEADER) reform: khong co smart/legacy route -> bo qua   (reform vo dung)

Ba loi chong nhau, ca ba deu la "cho dua khac bao cao / bam nut" thay vi bot tu dieu phoi:
  1. batbat DO LAI trong vong `while st["channel_ready"].is_set()` cho leader pick kenh khac.
  2. Leader thoat vong sync ma KHONG xoa `channel_ready` -> co ket SET vinh vien -> batbat khong
     bao gio ra, va no cung diec voi reform_gen (vong do khong he kiem gen).
  3. Leader `_bump_reform` - reform khong sua duoc gi, chi lap log 28 lan.
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


class TestKhongConDoLaiChoAiPickLai(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")
        i = self.src.find("khong doi duoc sang kenh chung")
        self.assertGreater(i, 0)
        self.khoi = self.src[i - 400:i + 600]

    def test_vao_kenh_khong_duoc_thi_THOAT_ngay(self):
        self.assertIn("return False", self.khoi[self.khoi.find("khong doi duoc"):])

    def test_KHONG_do_lai_trong_while(self):
        sau = self.khoi[self.khoi.find("khong doi duoc"):]
        self.assertNotIn("while", sau, "do lai = dung nguyen bug P3")

    def test_KHONG_con_bao_cao_channel_failed(self):
        sau = self.khoi[self.khoi.find("khong doi duoc") - 300:]
        self.assertNotIn('st["channel_failed"].set()', sau,
                         "bao cao roi ngoi cho = cho dua khac bam nut")

    def test_KHONG_bao_cao_len_nua(self):
        """Dieu phoi DOC THANG `_chan_switch_result` cua client - user chot 06/09:
        "bot la nguoi dieu phoi, deo phai cho dua nao bao cao"."""
        self.assertNotIn("bao_kenh_day", self.khoi)
        self.assertIn("_chan_switch_result", self.khoi)

    def test_sang_kenh_OK_nhung_SAI_MAP_cung_thoat_ngay(self):
        i = self.src.find('log.warning("[%s] (member) sang kenh %s roi nhung SAI MAP')
        self.assertGreater(i, 0, "van con nhanh do lai khi sai map")
        self.assertIn("return False", self.src[i:i + 300])


class TestVongSyncHongPhaiDONG_CUA(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_co_ham_dong_vong_sync(self):
        i = self.src.find("def _dong_vong_sync(")
        self.assertGreater(i, 0)
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        for k in ('st["channel_ready"].clear()', 'st["channel"] = None',
                  'st["channel_failed"].clear()'):
            self.assertIn(k, than)

    def test_nhanh_FAIL_goi_dong_vong_sync_VA_bo_bump_reform(self):
        i = self.src.find("sync kenh/map FAIL %d lan")
        self.assertGreater(i, 0)
        khoi = self.src[i - 900:i + 200]
        self.assertIn("_dong_vong_sync(st)", khoi)
        self.assertNotIn("_bump_reform(st)", khoi,
                         "reform khong sua duoc gi - P3 lap 'khong co smart/legacy route' 28 lan")

    def test_dong_vong_sync_GO_acc_dang_ket(self):
        """Kiem hanh vi that: co dang SET, goi xong phai TAT."""
        st = R._pstate(97)
        try:
            st["channel_ready"].set()
            st["channel"] = 15
            st["channel_failed"].set()
            R._dong_vong_sync(st)
            self.assertFalse(st["channel_ready"].is_set())
            self.assertIsNone(st["channel"])
            self.assertFalse(st["channel_failed"].is_set())
        finally:
            R._party_state.pop(97, None)


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_co_du(self):
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        for k in ("def _dong_vong_sync(", "def _doc_ket_qua_doi_kenh("):
            self.assertIn(k, apk)


if __name__ == "__main__":
    unittest.main()
