"""Watcher phai bat duoc "party THIEU NGUOI qua lau", khong de treo vo han.

Hai la chan cua watcher che kin dung truong hop nay:
  luat (1) DEADLOCK  doi CA PARTY cung cho -> leader luon ban (moi party 13-20s/lan) nen khong
                     bao gio du dieu kien;
  luat (3) `if waiting: continue` -> thay CO acc dang cho la bo qua ngay.
=> party ket 1/4 hang chuc phut ma khong luat nao dong toi.

Log 31/08 party 1 (13:33-13:49, 16 phut): `st["channel"] = 3` khong ton tai (result=2), 3 member
nam cho `channel_ready` khong ai set lai, leader moi lien tuc `da join=1 | roster server=1`.
Log 31/08 party 14 (09:14-09:26, 12 phut): trubon ket trong sync kenh nen `party_invite_ready`
khong mo, leader `da join=3` mai.

Luat moi doc THANG so nguoi da join (`joined_member_count`) chu khong qua bao cao pha, nen khong
bi cac la chan tren che mat.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestWatcherThieuNguoi(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _party_watcher(")
        self.assertGreater(i, 0)
        j = s.find("\ndef start_all(", i)
        self.assertGreater(j, i)
        self.khoi = s[i:j]
        self.than = re.sub(r"#.*", "", self.khoi)
        self.src = s

    def test_co_nguong_rieng(self):
        self.assertIn("WATCH_THIEU_NGUOI_SEC = ", self.src)

    def test_khoi_tao_bo_dem(self):
        self.assertIn("thieu_t0 = None", self.than)

    def test_doc_THANG_so_nguoi_join(self):
        self.assertIn("joined_member_count(pidx)", self.than,
                      "doc qua bao cao pha thi lai bi la chan 'co nguoi dang lam' che mat")
        self.assertIn('st.get("n_members")', self.than)

    def test_EP_DONG_BO_khi_qua_han(self):
        i = self.than.find("if thieu_t0 is None:")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 900]
        self.assertIn("time.time() - thieu_t0 >= WATCH_THIEU_NGUOI_SEC", khoi)
        self.assertIn("request_party_resync(pidx,", khoi, "phat hien ma khong ep = chi log cho vui")

    def test_chay_TRUOC_la_chan_co_acc_dang_cho(self):
        i_moi = self.than.find("if thieu_t0 is None:")
        i_chan = self.than.find("if waiting:\n            mismatch_t0 = None")
        self.assertGreater(i_moi, 0)
        self.assertGreater(i_chan, 0)
        self.assertLess(i_moi, i_chan, "dat SAU la chan thi khong bao gio chay toi")

    def test_chi_tinh_khi_DA_VAO_PHA_TRAIN(self):
        """Luc dang login/di duong thi thieu nguoi la binh thuong, ep dong bo la pha ngang."""
        i = self.than.find("joined_member_count(pidx)")
        self.assertIn('st.get("training_started")', self.than[max(0, i - 400):i + 400])

    def test_het_thieu_thi_XOA_bo_dem(self):
        i = self.than.find("if thieu_t0 is None:")
        sau = self.than[i:i + 1200]
        self.assertIn("thieu_t0 = None", sau.split("continue", 1)[-1],
                      "khong reset -> du party lai bi ep dong bo oan o vong sau")


if __name__ == "__main__":
    unittest.main()
