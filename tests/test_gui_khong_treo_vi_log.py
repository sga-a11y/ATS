"""GUI khong duoc "Not Responding" vi luong log.

User 10/09: "sao bot chay hay bi no responding the".

DO DUOC tren may dang chay (256 acc, 53 party):
    pythonw pid=20708  threads=843..887  RAM=410MB  CPU=1.0s moi giay thuc
CPU bang dung MOT core = cham tran GIL cua Python. Main thread cua Tk phai xep hang voi ~880 luong
khac, nen no giat cuc.

Log la phan CHIA duoc, va no rat lech:
    tail -300000 party.log:
        156.112  STATUS (N,N) kind=N skill=N       <- 52% TOAN BO log
         16.194  SPAWN (N,N)
         12.231  ACK (N,N)
          4.644  EXIT (N,N)
    -> rieng bon dong nay ~63%. Deu la trace TRONG TRAN, khong ai doc khi may chay binh thuong.

Toc do: trung binh ~307 dong/giay, DINH 1183 dong/giay - trong khi GUI cu rut duoc 300 dong moi
300ms = 1000/giay. Dinh vuot toc rut, ma `_log_queue` khong co tran -> don lai, an RAM, va GUI thi
hien log da lac hau.

Ba sua, deu o phia "dung bat main thread lam viec thua":
  1. Trace battle -> `log.debug` thay vi `log.info`.
  2. `_log_queue` co tran, day thi BO DONG CU NHAT (khong bao gio chan luong ghi log - `emit`
     chay tren chinh luong dang danh cua acc).
  3. GUI rut 900 dong/lan va chen theo KHOI (mot `insert`), khong phai tung dong.
"""
from __future__ import annotations

import io
import logging
import os
import queue
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestTraceBattleKhongPhaiINFO(unittest.TestCase):
    def setUp(self):
        self.src = _doc("bot", "party_battle.py")

    def test_STATUS_la_debug(self):
        i = self.src.find('elif event.kind == "status":')
        self.assertGreater(i, 0)
        khoi = self.src[i:self.src.find('elif event.kind in (', i)]
        self.assertIn("log.debug(", khoi, "52% log la dong nay - de INFO la dot main thread")
        self.assertNotIn("log.info(", khoi)

    def test_spawn_ack_exit_la_debug(self):
        i = self.src.find('elif event.kind in ("spawn", "exit"')
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 400]
        self.assertIn("log.debug(", khoi)
        self.assertNotIn("log.info(", khoi)

    def test_VAN_giu_INFO_cho_moc_tran_va_don_danh(self):
        """Ha het xuong debug thi mat dau vet chan doan - chi ha phan trace day dac."""
        for _moc in ('log.info("%s START"', 'log.info("%s TURN START"', 'log.info("%s END"'):
            self.assertIn(_moc, self.src, _moc)
        i = self.src.find('elif event.kind == "action":')
        self.assertIn("log.info(", self.src[i:i + 300], "don danh van phai thay duoc")


class TestQueueLogCoTran(unittest.TestCase):
    def setUp(self):
        self.gui = _doc("gui.py")

    def test_queue_co_maxsize(self):
        self.assertIn("_log_queue = queue.Queue(maxsize=_LOG_QUEUE_TRAN)", self.gui)

    def test_day_thi_BO_DONG_CU_chu_khong_chan(self):
        """`emit` chay tren chinh luong dang danh cua acc - chan o day la do tre ca 256 acc."""
        i = self.gui.find("class _QueueHandler(logging.Handler):")
        self.assertGreater(i, 0)
        khoi = self.gui[i:self.gui.find("def _setup_log_capture", i)]
        self.assertIn("except queue.Full:", khoi)
        self.assertIn("_log_queue.get_nowait()", khoi, "phai bo dong CU roi nhet dong moi")
        self.assertNotIn("_log_queue.put(", khoi, "`put` co cho = chan luong ghi log")

    def test_bo_dong_thi_KHONG_im_lang(self):
        self.assertIn("_log_bo_qua", self.gui)
        self.assertIn("bo qua %d dong log", self.gui)


class TestQueueHandlerChayThat(unittest.TestCase):
    """Chay that logic tran, khong chi doc chu."""

    def test_day_van_nhan_duoc_dong_moi_nhat(self):
        q = queue.Queue(maxsize=3)
        roi = {"n": 0}

        def _emit(msg):
            try:
                q.put_nowait(msg)
            except queue.Full:
                q.get_nowait()
                roi["n"] += 1
                q.put_nowait(msg)

        for i in range(6):
            _emit("dong %d" % i)
        con = [q.get_nowait() for _ in range(q.qsize())]
        self.assertEqual(con, ["dong 3", "dong 4", "dong 5"], "phai giu cai VUA xay ra")
        self.assertEqual(roi["n"], 3)

    def test_handler_that_khong_nem_loi_khi_day(self):
        from unittest import mock
        with mock.patch.object(sys, "argv", ["gui.py"]):
            import gui as G

        cu, cu_bo = G._log_queue, G._log_bo_qua
        try:
            G._log_queue = queue.Queue(maxsize=2)
            G._log_bo_qua = 0
            h = G._QueueHandler()
            h.setFormatter(logging.Formatter("%(message)s"))
            for i in range(5):
                h.emit(logging.LogRecord("bot", logging.INFO, __file__, 1,
                                         "dong %d" % i, None, None))
            self.assertEqual(G._log_queue.qsize(), 2)
            self.assertGreater(G._log_bo_qua, 0)
        finally:
            G._log_queue, G._log_bo_qua = cu, cu_bo


class TestGuiRutNhanhVaChenTheoKhoi(unittest.TestCase):
    def setUp(self):
        self.gui = _doc("gui.py")
        i = self.gui.find("def _drain_log(self):")
        self.assertGreater(i, 0)
        self.than = self.gui[i:self.gui.find("# ---- config editor ----", i)]

    def test_rut_nhanh_hon_toc_do_sinh(self):
        """Dinh do duoc la 1183 dong/giay; muc cu 300/300ms = 1000/giay khong theo kip."""
        self.assertIn("while n < 900:", self.than)

    def test_chen_theo_KHOI_mot_lan(self):
        """Moi `insert` bat Tk tinh lai layout - 900 lan/giay tren main thread la ket."""
        self.assertIn('"\\n".join(khoi)', self.than)
        self.assertEqual(self.than.count("self.log_txt.insert("), 1)

    def test_rerender_cung_chen_theo_khoi(self):
        i = self.gui.find("def _rerender_log(self):")
        khoi = self.gui[i:i + 700]
        self.assertIn('"\\n".join(khoi)', khoi)
        self.assertEqual(khoi.count("self.log_txt.insert("), 1)


if __name__ == "__main__":
    unittest.main()
