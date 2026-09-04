# -*- coding: utf-8 -*-
"""Mo hop xong phai cho DU do roi ra, khong duoc lay moi o dau tien.

Bug that (user bao 04/09): "cai mo ruong roi phan giai/dong gop/bo, t thay no thuong xuyen
bo sot do". Ban cu cua `_cho_tui_doi` la:

    while ...:
        moi = [s for s in self.bag_slots if s not in truoc]
        if moi: return moi

Mo 21 hop mot me -> server ban 21 goi 0x17 sub08 RAI RAC. Goi dau den la ham thoat ngay voi
DUNG MOT o; 20 mon con lai khong ai phan giai/donate/vut, nam li trong tui cho den khi day.
"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import client as C


class TestChoTuiDoiKhongBoSot(unittest.TestCase):
    def _client(self):
        cl = C.GameClient.__new__(C.GameClient)
        cl.running = True
        cl.bag_slots = {}
        return cl

    def test_cho_du_do_roi_ra_rai_rac(self):
        """Do ve nho giot -> phai gom DU 8 o, khong tra ve 1 o dau tien."""
        cl = self._client()
        truoc = dict(cl.bag_slots)

        def ban_goi():
            for i in range(8):
                time.sleep(0.12)
                cl.bag_slots[100 + i] = [0x52dd, 1]

        th = threading.Thread(target=ban_goi)
        th.start()
        moi = cl._cho_tui_doi(truoc, wait=5.0, it_nhat=8)
        th.join()
        self.assertEqual(len(moi), 8, "bo sot %d mon vua mo" % (8 - len(moi)))

    def test_khong_treo_khi_server_tra_thieu(self):
        """Server tra it hon mong doi thi van phai thoat theo `wait`, khong treo mai."""
        cl = self._client()
        truoc = dict(cl.bag_slots)
        cl.bag_slots[100] = [0x52dd, 1]
        t0 = time.time()
        moi = cl._cho_tui_doi(truoc, wait=1.0, it_nhat=9)
        dt = time.time() - t0
        self.assertEqual(len(moi), 1)
        self.assertLess(dt, 2.0, "phai thoat theo wait, khong cho mai")

    def test_du_som_thi_ve_som(self):
        """Du o va da lang thi ve ngay, khong nam cho het `wait`."""
        cl = self._client()
        truoc = dict(cl.bag_slots)
        for i in range(3):
            cl.bag_slots[100 + i] = [0x52dd, 1]
        t0 = time.time()
        moi = cl._cho_tui_doi(truoc, wait=10.0, it_nhat=3)
        dt = time.time() - t0
        self.assertEqual(len(moi), 3)
        self.assertLess(dt, 2.0, "du roi thi phai ve som")


if __name__ == "__main__":
    unittest.main()
