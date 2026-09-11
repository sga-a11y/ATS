"""MOT ACC CHI CO MOT LENH DOI KENH DANG BAY, va TIMEOUT khong phai bang chung "kenh day".

User 10/09: "p2, dieu phoi ngu lon, sao lai chot kenh 8 bi full trong khi rat nhieu kenh khac
trong".

CHUOI NHAN QUA (do tren party.log 10/09, party 2):

  1. Tu 09/09 co HAI duong cung ra lenh doi kenh cho mot acc: dieu phoi tu gui
     (`_dieu_phoi_thi_hanh_kenh`, them de sua ca party 3 bi diec) va duong acc tu nghe
     (`_nghe_lenh_kenh`). Khong khoa -> hai lenh chong nhau:
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
  - So den phan biet CHAC (server noi: ma 2/4) voi DOAN (chi timeout). Het ung vien thi bo phan
    doan ra roi tim lai.
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


class TestSoDenPhanBietChacVaDoan(unittest.TestCase):
    def test_ma_4_la_CHAC(self):
        hong, _m3, _m2 = R._doc_ket_qua_doi_kenh([("u", _C(kq=4, target=8))])
        self.assertEqual(set(hong), {8})
        self.assertEqual(hong.chac(), {8}, "server noi ro kenh day -> chac")
        self.assertEqual(hong.doan, set())

    def test_ma_2_la_CHAC(self):
        hong, _m3, _m2 = R._doc_ket_qua_doi_kenh([("u", _C(kq=2, target=27))])
        self.assertEqual(hong.chac(), {27})

    def test_TIMEOUT_chi_la_DOAN(self):
        hong, _m3, _m2 = R._doc_ket_qua_doi_kenh([("u", _C(kq=-1, target=3))])
        self.assertEqual(set(hong), {3}, "van vao so den - khong vao thi lai dam dau mai")
        self.assertEqual(hong.doan, {3})
        self.assertEqual(hong.chac(), set(), "timeout KHONG phai bang chung kenh day")

    def test_cung_kenh_vua_timeout_vua_ma_4_thi_la_CHAC(self):
        """Mot acc timeout, acc khac nhan ma 4 -> co bang chung that."""
        hong, _m3, _m2 = R._doc_ket_qua_doi_kenh(
            [("a", _C(kq=-1, target=8)), ("b", _C(kq=4, target=8))])
        self.assertEqual(hong.chac(), {8})


class TestBoQuaPhanDOAN_KhiHetUngVien(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._src = io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()

    def tearDown(self):
        R.party_accounts = self._pa

    def test_nhanh_a_thu_lai_khi_so_den_chi_toan_DOAN(self):
        i = self._src.find("_ung = [(dang, ch) for ch, (dang, con) in _bang.items()")
        self.assertGreater(i, 0)
        khoi = self._src[i:i + 1200]
        self.assertIn('getattr(hong, "doan", None)', khoi,
                      "het ung vien ma khong xet lai phan doan -> chot bua vao kenh dang DAY")
        self.assertIn("hong.chac()", khoi)

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
