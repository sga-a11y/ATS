"""BARRIER login-dailies DA BI XOA HAN (13/09) - leader khong cho ca party xong daily nua.

Ca that 08/09 party 48 (user: "dm may, bon no ko lap pt, may check cai lon gi the"):

    06:52:36 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
    06:53:07 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
    06:53:37 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
    06:52:51 [party 48] ... viec=moi - DOI chua du (dt901=4 dt902=0 dt903=0 dt904=4 dt905=0)

Ca 5 acc deu dang chay binh thuong. Dieu phoi ra lenh moi party; leader dang cho mot con so cua
rieng no (`dailies_done >= min(expected, _con_cho)`) nen khong nghe.

Hai lan sua truoc deu chi VA quanh con so do - lan dau sua cach dem (bo acc da tat, bo acc khong
di qua barrier), lan sau chuyen viec dem sang cho dieu phoi. Ca hai giu nguyen cai sai goc: LEADER
VAN DUNG YEN CHO, va trong luc cho no diec voi lenh cap party.

User 13/09: "van cho acc tu quyet ma ko theo dieu phoi, m code ngu that su day".

GIO: khong cho gi ca. Member dang lam daily o map/kenh khac chinh la LECH MAP / LECH KENH - dung
thu ma dieu phoi doc moi 2 giay va ra lenh gom theo chuoi gom map -> gom kenh -> moi.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _ma(s):
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)


class TestBarrierDaXoa(unittest.TestCase):
    def setUp(self):
        self.ma = _ma(_src())

    def test_khong_con_vong_cho(self):
        self.assertNotIn("CHO ca party xong daily", self.ma)

    def test_khong_con_dieu_kien_thoat_tu_dat(self):
        self.assertNotIn("min(expected,", self.ma,
                         "leader lai tu dat nguong 'du bao nhieu nguoi thi toi di'")

    def test_khong_con_co_danh_dau_de_dem(self):
        """`_bo_qua_barrier_daily` chi ton tai de leader dem xem phai cho may nguoi."""
        self.assertNotIn("_bo_qua_barrier_daily", self.ma)


class TestVanDemSoAccXongDaily(unittest.TestCase):
    """`dailies_done` giu lai lam SO LIEU (in ra log), khong con la dieu kien cho."""

    def setUp(self):
        self.src = _src()

    def test_van_cong_khi_xong_daily(self):
        self.assertIn('st["dailies_done"] += 1', _ma(self.src))

    def test_khong_ai_CHO_theo_con_so_nay(self):
        i = self.src.find('st["dailies_done"] += 1')
        self.assertGreater(i, 0)
        khoi = _ma(self.src[i:i + 800])
        self.assertNotIn("while", khoi, "lai cho theo `dailies_done`")


if __name__ == "__main__":
    unittest.main()
