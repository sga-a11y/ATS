"""BARRIER daily: chi cho nhung acc THUC SU phai di qua no, va con SONG.

`dailies_done` la so acc TU KHAI (moi acc qua barrier thi +1). Hai loai acc khong bao gio khai:
  - acc BO QUA barrier: `is_digioi` / `is_reconnect` / mode event (xem dieu kien `if` bao quanh),
  - acc DA TAT.
Ma `expected = len(party_accounts(pidx))` van dem ca hai -> leader cho mot con so KHONG BAO GIO
DAT DUOC, va no cho VO HAN (vong `while True`).

Ca that 08/09 party 48 (user: "dm may, bon no ko lap pt, may check cai lon gi the"):

    06:52:36 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
    06:53:07 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
    06:53:37 [dtmot] (LEADER) CHO ca party xong daily (2/5, reconnecting=0)...
    06:52:51 [party 48] ... viec=moi - DOI chua du (dt901=4 dt902=0 dt903=0 dt904=4 dt905=0)

Ca 5 acc deu dang chay binh thuong, con so dung im o 2/5 suot 4 phut trong khi dieu phoi lien tuc
keu thieu doi. Cung dem do co 92 acc bi TAT nham (xem `test_khong_doan_het_gio_dg.py`), cang lam
`expected` khong the dat.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestDieuKienThoatBarrier(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find('st["dailies_done"] += 1')
        self.assertGreater(i, 0)
        # moc ket thuc phai la DONG LOG that, khong phai chu trong comment (comment o giua khoi
        # cung chua chuoi nay -> cat nham, khoi con lai khong co phan dieu kien)
        j = s.find('log.info("[%s] (%s) CHO ca party xong daily', i)
        self.assertGreater(j, i)
        self.khoi = s[i:j]

    def test_KHONG_cho_acc_da_TAT(self):
        self.assertIn('getattr(_c3, "running", False)', self.khoi,
                      "dem ca acc da tat -> cho mot con so khong the dat")

    def test_KHONG_cho_acc_bo_qua_barrier(self):
        """Acc `is_digioi`/`is_reconnect`/event khong di qua barrier nen khong bao gio +1."""
        self.assertIn('_bo_qua_barrier_daily', self.khoi,
                      "dem ca acc khong di qua barrier -> cho vinh vien")

    def test_van_khong_vuot_qua_so_acc_cau_hinh(self):
        """`min(expected, ...)` - khong duoc noi long thanh 'ai toi truoc thi di' (L0)."""
        self.assertIn("min(expected,", self.khoi)

    def test_van_cong_reconnecting(self):
        """Acc dang reconnect se catch up qua reform - dem vao de khoi deadlock (hanh vi cu)."""
        self.assertIn('len(st["reconnecting"])', self.khoi)


class TestDanhDauBoQua(unittest.TestCase):
    def test_co_danh_dau_trên_client(self):
        s = _src()
        i = s.find("c._bo_qua_barrier_daily = ")
        self.assertGreater(i, 0, "khong danh dau -> leader khong biet phai cho may nguoi")
        khoi = s[i:i + 200]
        for m in ("is_digioi", "is_reconnect", 'mode == "event"'):
            self.assertIn(m, khoi, m)

    def test_danh_dau_TRUOC_khi_vao_barrier(self):
        s = _src()
        i = s.find("c._bo_qua_barrier_daily = ")
        j = s.find('st["dailies_done"] += 1', i)
        self.assertGreater(j, i, "danh dau sau khi vao barrier -> vong dau tien van dem sai")

    def test_dung_CUNG_dieu_kien_voi_nhanh_bo_qua(self):
        """Danh dau lech voi dieu kien that = leader cho nham nguoi."""
        s = _src()
        i = s.find("c._bo_qua_barrier_daily = ")
        j = s.find("if not is_digioi and not is_reconnect and mode != \"event\":", i)
        self.assertGreater(j, i, "nhanh bo qua khong nam ngay sau cho danh dau")
        self.assertLess(j - i, 400)


if __name__ == "__main__":
    unittest.main()
