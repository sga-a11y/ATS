"""Dang KEO party ra bai ma party TUT NGUOI -> DUNG KEO, gom lai.

Su co party 1 (30/08):
    15:03:50 PARTY: 38d0d2f8 vao doi -> roster 4 nguoi
    15:03:55 (LEADER) reform: 4/4 member join lai -> KEO qua cong ra train map
    15:03:57 PARTY-JOINED: 4 -> 3 (chihao roi khoi party)
    15:03:57..15:07  leader loi qua 23001 -> 23000 -> 23811 -> 23000 -> 23521 -> ... voi 3 member
    15:08:08 (LEADER) moi 20s chua du party (3/4) -> REFORM

Quyet dinh "du 4/4" duoc chup MOT LAN roi chuyen di mat 3-4 phut ma khong ai kiem tra lai:
`_ab()` chi bat `_stopped()` / client chet / `reform_gen` bi acc khac bump - KHONG bat so member.

Grace 15s: roster nhay mot nhip khi member qua cong la binh thuong, dung vi the huy ca chuyen di.
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestAbortTheoSoMember(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _keo_bi_tut_nguoi():")
        self.assertGreater(i, 0, "khong co cho nao kiem tra so member giua duong keo")
        j = s.find("plan_ready = st.setdefault", i)
        self.assertGreater(j, i)
        self.than = re.sub(r"#.*", "", s[i:j])
        self.src = s

    def test_ab_hoi_so_member(self):
        i = self.than.find("def _ab(")
        self.assertGreater(i, 0)
        self.assertIn("_keo_bi_tut_nguoi()", self.than[i:],
                      "_ab van chi bat stop/reform_gen -> keo tiep du party da tut")

    def test_so_sanh_voi_n_members(self):
        self.assertIn("joined_member_count(pidx)", self.than)
        self.assertIn('st["n_members"]', self.than)

    def test_co_grace_tranh_nhay_roster(self):
        self.assertIn("KEO_THIEU_GRACE", self.than)
        i = self.src.find("KEO_THIEU_GRACE = ")
        self.assertGreater(i, 0)
        self.assertRegex(self.src[i:i + 40], r"KEO_THIEU_GRACE = 1[0-9](\.\d+)?")

    def test_du_lai_thi_XOA_moc_thieu(self):
        """Thieu thoang qua roi day lai ma van giu moc = 15s sau tu huy chuyen di vo co."""
        i = self.than.find('if _nj >= st["n_members"]:')
        self.assertGreater(i, 0)
        self.assertIn("_keo_thieu[:] = []", self.than[i:i + 200])

    def test_bump_reform_de_con_duong_gom_lai(self):
        """Dung keo ma khong bao ai thi leader dung giua duong, khong ai gom lai."""
        self.assertIn("_bump_reform(st,", self.than)

    def test_bump_DUNG_MOT_LAN(self):
        """_ab() bi goi moi buoc di - bump moi lan = reform_gen chay loan."""
        i = self.than.find("_bump_reform(st,")
        self.assertGreater(i, 0)
        self.assertIn("len(_keo_thieu) < 2", self.than[max(0, i - 300):i])

    def test_CHI_ap_dung_khi_da_bat_dau_keo_voi_party_DU(self):
        """Vong CHO du member (truoc khi keo) cung goi _ab() - bat o do la thoat ngay lap tuc."""
        self.assertIn("if not _keo_du_party", self.than)
        s = self.src
        i = s.find("c.flee_mode = not _full")
        self.assertGreater(i, 0)
        self.assertIn("_keo_du_party.append(1)", s[i:i + 500],
                      "phai bat co NGAY TRUOC khi keo, va chi khi party DU")


if __name__ == "__main__":
    unittest.main()
