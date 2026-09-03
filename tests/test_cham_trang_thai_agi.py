# -*- coding: utf-8 -*-
"""Cham trang thai party/nhom chuyen CAM khi party do lech AGI.

User: "van phai duyet tung party de xem thang nao lech agi -> khi co party lech agi thi party do /
nhom do dau cham trang thai cung mau cam luon, tuc la them trang thai mau cam".

Bai test doc thang gui.py (giong cac bai neo hanh vi khac): sua nhanh ma quen cho nay thi do.
"""
import io
import os
import unittest

GUI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui.py")


def _src():
    with io.open(GUI, encoding="utf-8") as fh:
        return fh.read()


class TestChamTrangThaiAgi(unittest.TestCase):
    def test_co_cham_mau_cam_rieng(self):
        s = _src()
        self.assertIn("_dot_agi", s, "phai co cham rieng cho lech AGI")
        self.assertIn('self._dot_agi = self._make_dot("#f59e0b")', s,
                      "dung dung mau voi nut Check AGI de nhin la lien tuong")

    def test_khong_dung_lai_mau_vang_dang_co(self):
        """Vang = chay MOT PHAN. Dung lai vang cho AGI thi hai y nghia lan nhau."""
        s = _src()
        self.assertIn('self._dot_warn = self._make_dot("#f0c000")', s)
        self.assertNotEqual("#f0c000", "#f59e0b")

    def test_ap_cho_ca_party_va_nhom(self):
        # Doi ten tu `agi_warn_groups` -> `cam_groups` (04/09): set nay gio gom CA hai nguon lam
        # cham CAM (lech AGI va chu y can lam ngay), khong con rieng AGI nua.
        s = _src()
        self.assertIn("cam_groups", s, "nhom phai biet co party nao CAM khong")
        self.assertIn("gidx in cam_groups", s, "cham NHOM phai xet toi")

    def test_cam_chi_thay_cho_xanh(self):
        """CAM khong duoc de len vang/xam.

        Luc thieu acc thi so AGI KHONG day du (report chi gop acc dang chay) -> do lech doc duoc
        chua chac dung; va viec thieu acc gap hon, da co mau rieng.
        """
        s = _src()
        self.assertIn("_lech_agi = bool(agi_report.get(\"warning\")) and _du_acc", s,
                      "phai co dieu kien _du_acc")
        self.assertIn("self._dot_agi if (_g_du and gidx in cam_groups)", s,
                      "cham nhom cung phai doi _g_du")
        self.assertIn("_cam = _lech_agi or (_gap_notify and _du_acc)", s,
                      "chu y can lam ngay cung phai doi _du_acc moi duoc len CAM")

    def test_doc_agi_report_TRUOC_khi_dung_cham(self):
        """agi_report phai tinh truoc dong dung p_dot, khong thi dung bien chua co."""
        s = _src()
        i_rep = s.find("agi_report = ctrl.party_agi_report(pidx)")
        i_dot = s.find("p_dot = (self._dot_off")
        self.assertGreater(i_rep, 0)
        self.assertGreater(i_dot, 0)
        self.assertLess(i_rep, i_dot)


class TestNguongAgiKhongDoi(unittest.TestCase):
    def test_van_la_lech_lon_hon_10(self):
        """User xac nhan nguong >10 la dung - khong duoc tu doi khi lam mau cham."""
        import io as _io
        p = os.path.join(os.path.dirname(GUI), "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('"warning": spread is not None and spread > 10', s)


if __name__ == "__main__":
    unittest.main()
