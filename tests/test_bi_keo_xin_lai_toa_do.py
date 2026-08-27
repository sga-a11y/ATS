# -*- coding: utf-8 -*-
"""BI KEO SANG MAP MOI -> phai XIN LAI TOA DO THAT truoc khi gui lenh move.

Log that 27/08 12:24:11 (party ton_quyen, map train 12831): leader keo party qua cong, 4 member
deu in "bi keo sang map 12831 -> chay scene_resume truoc khi di" roi tinh duong tu (1310,2410)
va RA DI CUNG MOT GIAY:
    SERVER NGAT KET NOI: di chuyen QUA XA (ma 14)

Vi sao: scene_resume() chi bao server "toi vao scene xong", KHONG tra ve vi tri. self.pos luc do
la dead-reckoning (diem cuoi minh tu gui o map CU / cho leader dung luc keo). Server dat member
canh leader O THOI DIEM KEO, ma leader da di tiep (luc do o (1180,480)) -> lenh move dau tien
nhay ca nghin don vi -> server coi la speedhack va dong ket noi.

refresh_server_position() von CHI chay khi self.pos is None (canh vua tu qua cong). Bi keo thi
pos KHONG None - no chi SAI - nen nhanh do khong bao gio chay.
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


class TestXinLaiToaDoSauKhiBiKeo(unittest.TestCase):
    def test_scene_resume_xong_phai_xin_lai_toa_do(self):
        s = _src()
        i = s.find("bi keo sang map %s (khong tu qua cong)")
        self.assertGreater(i, 0)
        doan = s[i:i + 1400]
        j = doan.find("self.scene_resume()")
        self.assertGreater(j, 0)
        self.assertIn("self.refresh_server_position(self.current_map)", doan[j:],
                      "phai xin lai toa do NGAY SAU scene_resume")

    def test_khong_de_loi_xin_toa_do_lam_chet_luong_di(self):
        """Xin toa do that bai (server im) thi van phai di tiep - khong duoc nem ra ngoai."""
        s = _src()
        i = s.find("bi keo sang map %s (khong tu qua cong)")
        doan = s[i:i + 1400]
        j = doan.find("self.refresh_server_position(self.current_map)")
        self.assertIn("except Exception", doan[j:j + 300])

    def test_nhanh_cu_pos_None_van_con(self):
        """Canh 'vua tu qua cong' (pos=None) van phai xin toa do - khong duoc thay the nhanh do."""
        s = _src()
        self.assertIn("if self.pos is None and self.current_map is not None:", s)


if __name__ == "__main__":
    unittest.main()
