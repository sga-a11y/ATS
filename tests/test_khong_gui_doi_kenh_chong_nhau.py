"""MOT ACC CHI CO MOT LENH DOI KENH DANG BAY, va TIMEOUT khong phai bang chung "kenh day".

User 10/09: "p2, dieu phoi ngu lon, sao lai chot kenh 8 bi full trong khi rat nhieu kenh khac
trong".

CHUOI NHAN QUA (do tren party.log 10/09, party 2):

  1. Truoc khi hop nhat controller, hai duong gui lenh doi kenh cho mot acc
     khong khoa -> hai lenh chong nhau:
        00:09:05 [gamo] Doi kenh 3 TIMEOUT sau 4.0s      <- duong dieu phoi
        00:09:06 [gamo] Doi kenh 3 TIMEOUT sau 6.0s      <- duong acc tu nghe
     Server tra MOT ket qua, luong con lai TIMEOUT.

  2. TIMEOUT ghi `_chan_switch_result = -1`, ma `_doc_ket_qua_doi_kenh` doi xu `-1` y het ma 4
     (kenh day) -> kenh TRONG bi vao so den OAN.

  3. So den day dan -> nhanh (a) "kenh IT NGUOI NHAT ma du cho ca team" khong con ung vien ->
     roi xuong nhanh (b) va chot bua vao mot trong ba kenh party dang dung, ca ba deu DAY:
        00:09:27 party lech kenh {4:1, 6:1, 8:1, 14:1, 21:1} -> CHOT kenh dich = 8
     Bang kenh luc do co 57 kenh.

Hai sua, hai tang khac nhau:
  - `switch_channel` co khoa: lenh thu hai bi BO, va KHONG ghi ket qua gi (khong tao `-1` gia).
  - (27/09) BO HAN so den: timeout khong con tac dung gi len viec chon kenh, ma 4 chi bat hoi lai
    danh sach kenh. Xem `tests/test_doi_kenh_cho_ket_qua_khong_so_den.py`.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _C:
    def __init__(self, kq=None, target=None, luc=None):
        self.running = True
        self._chan_switch_result = kq
        self._chan_switch_target = target
        self._chan_switch_luc = time.time() if luc is None else luc


class TestKetQuaDoiKenhKhongConSoDen(unittest.TestCase):
    """BO SO DEN 27/09 (user: "ko can so den, moi lan chon kenh luon chon kenh it nguoi nhat").
    Chi con: ma 4 toi SAU danh sach kenh moi nhat = danh sach CU -> phai hoi lai."""

    def test_ma_4_moi_hon_danh_sach(self):
        day, _m3, _m2 = R._doc_ket_qua_doi_kenh([("u", _C(kq=4, target=8))])
        self.assertEqual(day, {8})

    def test_ma_4_cu_hon_danh_sach_thi_tin_danh_sach(self):
        c = _C(kq=4, target=8, luc=time.time() - 5)
        c._ds_kenh_nhan_luc = time.time()
        day, _m3, _m2 = R._doc_ket_qua_doi_kenh([("u", c)])
        self.assertEqual(day, set())

    def test_ma_2_chi_bat_co(self):
        day, _m3, m2 = R._doc_ket_qua_doi_kenh([("u", _C(kq=2, target=27))])
        self.assertEqual((day, m2), (set(), True))

    def test_TIMEOUT_khong_phai_bang_chung_gi(self):
        day, _m3, _m2 = R._doc_ket_qua_doi_kenh([("u", _C(kq=-1, target=3))])
        self.assertEqual(day, set(), "timeout KHONG phai bang chung kenh day")


class TestNhanhA_KhongLocSoDen(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self._src = fh.read()

    def tearDown(self):
        R.party_accounts = self._pa

    def test_nhanh_a_chi_xet_con_cho(self):
        i = self._src.find("_ung = [(dang, ch) for ch, (dang, con) in _bang.items()")
        self.assertGreater(i, 0)
        self.assertNotRegex(self._src[i:i + 200], r"\bhong\b")

    def test_van_NOI_RO_vi_sao_khong_co_ung_vien(self):
        """Nhin log cu khong the phan biet: 57 kenh deu day that / so den nuot / doc sai suc chua."""
        i = self._src.find("khong kenh nao du %d cho - bang %d kenh")
        self.assertGreater(i, 0, "roi xuong nhanh cuoi ma khong noi vi sao")


class TestMotLenhMotLuc(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.cli = fh.read()

    def test_co_khoa(self):
        self.assertIn("self._chan_switch_lock = threading.Lock()", self.cli)

    def test_khoa_KHONG_XEP_HANG(self):
        """Xep hang cung la gui thua - lenh dang bay se tra ket qua that cho ca hai."""
        i = self.cli.find("if not self._chan_switch_lock.acquire(blocking=False):")
        self.assertGreater(i, 0)
        self.assertIn("return False", self.cli[i:i + 400])

    def test_lenh_bi_BO_thi_KHONG_ghi_ket_qua(self):
        """Ghi `-1` cho lenh minh tu bo = tu tao bang chung gia -> kenh vao so den oan."""
        i = self.cli.find("if not self._chan_switch_lock.acquire(blocking=False):")
        khoi = self.cli[i:i + 400]
        self.assertNotIn("_chan_switch_result", khoi)

    def test_nha_khoa_trong_finally(self):
        i = self.cli.find("return self._switch_channel_locked(channel, wait, retries")
        self.assertGreater(i, 0)
        self.assertIn("finally:", self.cli[i:i + 200])
        self.assertIn("self._chan_switch_lock.release()", self.cli[i:i + 200])


class TestKhoaChayThat(unittest.TestCase):
    """Chay that hai luong, khong chi doc chu."""

    def test_luong_thu_hai_bi_bo(self):
        class _Cli:
            def __init__(self):
                self._chan_switch_lock = threading.Lock()
                self._label = "acc"
                self.so_lan = 0

            def switch_channel(self, ch):
                if not self._chan_switch_lock.acquire(blocking=False):
                    return False
                try:
                    self.so_lan += 1
                    time.sleep(0.2)
                    return True
                finally:
                    self._chan_switch_lock.release()

        c = _Cli()
        ra = []
        ts = [threading.Thread(target=lambda: ra.append(c.switch_channel(3))) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(c.so_lan, 1, "hai lenh cung bay -> server tra mot ket qua, cai kia TIMEOUT")
        self.assertEqual(sorted(ra), [False, True])


if __name__ == "__main__":
    unittest.main()
