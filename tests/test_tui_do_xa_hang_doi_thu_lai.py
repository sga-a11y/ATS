"""Lenh tui do bi XEP HANG giua tran: gui xong phai KIEM, bi nuot thi thu lai.

Su co 26/08 22:09-22:10: user bam "Trang bi cho Quan Vu" 6 lan lien, log deu ghi
`het tran -> gui lenh da xep hang` ma do KHONG he doi. Dung yen (khong train) thi bam phat an
ngay -> gui DUNG goi, chi SAI THOI DIEM.

Nguyen nhan: moc xa hang doi la `0x14 sub0700`, ma goi do KHONG phai ket tran that
(`S:020-007 <事件換場景>`; ket tran that la `S:011-000` = `0x0b sub 0`). Dang train thi tran ke
tiep bat dau chi ~2 giay sau nen server nuot lenh doi do.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


class _C:
    """Chi muon phan xa hang doi - dung ham that cua GameClient tren object toi gian."""

    BAG_FLUSH_TRIES = GameClient.BAG_FLUSH_TRIES
    BAG_FLUSH_VERIFY = 0.2          # rut ngan cho test chay nhanh
    _flush_bag_queue = GameClient._flush_bag_queue
    _bag_flush_worker = GameClient._bag_flush_worker
    # Phai boc lai staticmethod: lay tu class ra la ham THUONG, gan vao class body se thanh
    # method co `self`.
    _la_lenh_do = staticmethod(GameClient._la_lenh_do)

    def __init__(self):
        self._label = "test"
        self._username = "test"
        self._bag_queue = []
        self._bag_flush_running = False
        self._equip_seq = 0
        self.goi = []

    def _cho_xong(self, han=5.0):
        het = time.time() + han
        while time.time() < het:
            if not self._bag_flush_running:
                return True
            time.sleep(0.02)
        return False


class TestThuLai(unittest.TestCase):
    def test_lenh_an_ngay_thi_KHONG_thu_lai(self):
        c = _C()

        def fn():
            c.goi.append("gui")
            c._equip_seq += 1        # server phan hoi = _equip_seq tang
        c._bag_queue.append(("Trang bị cho Quan Vũ", fn))
        c._flush_bag_queue()
        self.assertTrue(c._cho_xong())
        self.assertEqual(len(c.goi), 1)
        self.assertEqual(c._bag_queue, [], "an roi ma van xep lai")

    def test_bi_nuot_thi_xep_lai(self):
        c = _C()
        c._bag_queue.append(("Trang bị cho Quan Vũ", lambda: c.goi.append("gui")))
        c._flush_bag_queue()
        self.assertTrue(c._cho_xong())
        self.assertEqual(len(c.goi), 1)
        self.assertEqual(len(c._bag_queue), 1, "bi nuot ma khong xep lai -> mat lenh")
        self.assertEqual(c._bag_queue[0][2], 2, "phai dem so lan da thu")

    def test_dung_sau_dung_so_lan(self):
        c = _C()
        c._bag_queue.append(("Trang bị cho Quan Vũ", lambda: c.goi.append("gui")))
        for _ in range(10):
            c._flush_bag_queue()
            self.assertTrue(c._cho_xong())
            if not c._bag_queue:
                break
        self.assertEqual(len(c.goi), GameClient.BAG_FLUSH_TRIES,
                         "so lan thu khong khop BAG_FLUSH_TRIES")
        self.assertEqual(c._bag_queue, [], "thu du so lan roi ma con giu -> lap vo han")

    def test_lenh_KHONG_lien_quan_do_thi_khong_thu_lai(self):
        """'Bo' / 'Phan giai' khong lam doi `_equip_seq` -> thu lai la gui lap, rat nguy hiem."""
        for ten in ("Bỏ", "Phân giải", "Sử dụng"):
            c = _C()
            c._bag_queue.append((ten, lambda: c.goi.append("gui")))
            c._flush_bag_queue()
            self.assertTrue(c._cho_xong())
            self.assertEqual(len(c.goi), 1, "%s: gui lap" % ten)
            self.assertEqual(c._bag_queue, [], "%s: khong duoc xep lai" % ten)

    def test_lenh_loi_thi_bo_qua_khong_treo(self):
        c = _C()

        def hong():
            raise RuntimeError("hong")
        c._bag_queue.append(("Trang bị cho Quan Vũ", hong))
        c._bag_queue.append(("Cởi ra", lambda: c.goi.append("sau")))
        c._flush_bag_queue()
        self.assertTrue(c._cho_xong())
        self.assertIn("sau", c.goi, "lenh loi lam chet ca hang doi")

    def test_KHONG_xa_chong_len_nhau(self):
        c = _C()
        c._bag_queue.append(("Trang bị cho Quan Vũ", lambda: c.goi.append("gui")))
        c._flush_bag_queue()
        c._flush_bag_queue()      # goi lien tay lan 2 (heartbeat + goi ket tran cung luc)
        self.assertTrue(c._cho_xong())
        self.assertEqual(len(c.goi), 1, "gui lenh HAI lan vi xa chong len nhau")


class TestKhongChanThreadDocGoi(unittest.TestCase):
    def test_xa_hang_doi_chay_o_thread_rieng(self):
        """_flush_bag_queue duoc goi TU thread doc goi; ngu trong do la chan doc socket."""
        c = _C()
        cai_dat = threading.current_thread()
        thay = []
        c._bag_queue.append(("Trang bị cho Quan Vũ",
                             lambda: thay.append(threading.current_thread())))
        c._flush_bag_queue()
        self.assertTrue(c._cho_xong())
        self.assertNotEqual(thay[0], cai_dat, "van chay tren chinh thread goi -> chan doc goi")


if __name__ == "__main__":
    unittest.main()
