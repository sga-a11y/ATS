"""DA O DIEM TAP KET ma con dinh tran -> DANH XONG TAI CHO, khong duoc di lai.

Vong lap tu tao: safe cua bai train chi cach diem quai vai tram don vi nen DUNG YEN van bi keo
tran. Neu coi "dang danh => toa do chac sai => di lai cho chac" thi moi lan di lai la mot lan bang
qua vung quai -> dinh tran moi -> lai ket luan "van dinh tran" -> lai di. Khong bao gio ra.

Log 31/08 party 8 (10:49:25-50), lenh doi kenh tay luc dang train:
    10:49:25 [lubbon] TUONG dang o diem tap ket (650, 2070) ma van dinh tran -> ... di lai
    10:49:26 [lbumot] TUONG dang o diem tap ket (650, 2070) ma van dinh tran -> ... di lai
    10:49:33 [lbumot] manual: dinh tran luc ra safe -> thu lai (lan 1)
    10:49:36 [lbumot] manual: VAN dang trong tran -> chua doi kenh 1, thu lai (lan 2, con 290s)
    10:49:49 [lbumot] ... di lai lan nua ...
    10:49:50 [lbumot] manual: DA ra safe -> giai tan party roi doi kenh 1
=> mat 24s va vai bay quai chi de dung yen tai cho da san.
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


class TestOSafeRoiThiDungDiLai(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _ra_rally_gom_lai(")
        self.assertGreater(i, 0)
        j = s.find("\n        def ", i + 10)
        self.assertGreater(j, i)
        self.khoi = s[i:j]
        self.than = re.sub(r"#.*", "", self.khoi)

    def test_KHONG_con_di_lai_khi_da_o_rally(self):
        self.assertNotIn("KHONG tin toa do dang nho, di lai", self.khoi,
                         "di lai qua vung quai = tu chuoc them tran, vong lap khong loi ra")

    def test_dinh_tran_tai_rally_thi_DANH_CHO_XONG(self):
        i = self.than.find("if _da_toi():")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 900]
        self.assertIn("c._wait_combat_clear(", khoi, "khong cho dut tran thi bao nhieu lan cung the")
        self.assertIn("DANH XONG", self.khoi)

    def test_danh_xong_ma_van_o_rally_thi_BAO_DA_RA(self):
        i = self.than.find("if _da_toi():")
        khoi = self.than[i:i + 900]
        i_cho = khoi.find("c._wait_combat_clear(")
        i_bao = khoi.find("_bao_da_ra()", i_cho)
        self.assertGreater(i_bao, i_cho, "danh xong roi ma khong bao -> leader cho mai")
        self.assertIn("return True", khoi[i_bao:i_bao + 120])

    def test_van_kiem_LAI_toa_do_sau_khi_danh_xong(self):
        """Danh xong khong dong nghia dung cho: co the bi keo lech trong tran."""
        i = self.than.find("c._wait_combat_clear(idle=2.0, cap=120.0)")
        self.assertGreater(i, 0)
        self.assertIn("if _da_toi() and not c.in_combat(", self.than[i:i + 300])

    def test_van_con_duong_di_khi_THAT_SU_o_xa(self):
        self.assertIn("c.navigate_to(", self.than, "mat han duong di = acc o xa khong bao gio ve")


if __name__ == "__main__":
    unittest.main()
