"""MainThread cua GUI khong duoc xep hang tren `_PARTY_LOCK`.

User 10/09: "sao bot chay hay bi no responding the" -> sau lan sua log van "van not responding".

Lan dau toi doan la log (do dung: 52% log la mot dong trace battle) va sua log. User restart, VAN
treo. Lan nay do thang bang py-spy tren chinh tien trinh dang chay (pid 26244, 256 acc, ~520
thread) - 15/15 mau, MainThread deu o day:

    is_joined (bot/client.py)      | account_status (run_party_digioi.py) | _refresh (gui.py)
    is_strategist (bot/client.py)  | account_status (run_party_digioi.py) | party_agi_report(...)

Hai ham do KHONG TINH GI CA - chung `with _PARTY_LOCK`. Cung dump do: thread `dieu-phoi` ket o
`dat_party_dang_gom`, thread acc ket o `name_for_entity` - ca he xep hang tren MOT khoa toan cuc,
va GUI thi gianh no 256 lan moi giay (`_refresh` goi `account_status` cho tung acc cua TUNG party,
ke ca party nam trong tab khong ai mo).

Bon sua, tu goc ra ngoai:
  1. `is_joined` doc BAN CHUP bat bien (`_PARTY_JOINED_RO`, frozenset) - khong khoa.
  2. `is_strategist` / `joined_member_count` doc thang dict - khong khoa.
  3. `_refresh` chi dung bang cho party DANG XEM; party khac chi dem acc chay de to cham nhom.
  4. `party_agi_report` cua party khong hien thi duoc cache.
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestDuongDocKhongKhoa(unittest.TestCase):
    def setUp(self):
        self.src = _doc("bot", "client.py")

    def _than(self, ten):
        """Than ham, DA BO docstring va comment - test phai bat MA chay, khong bat chu ghi chu.

        (Chinh cac ghi chu o day co nhac `_PARTY_LOCK` de giai thich vi sao BO no.)
        """
        i = self.src.find("def %s(" % ten)
        self.assertGreater(i, 0, ten)
        kh = self.src[i:self.src.find("\ndef ", i + 10)]
        kh = re.sub(r'"""[\s\S]*?"""', "", kh)
        kh = re.sub(r"#.*", "", kh)
        return kh

    def test_is_joined_khong_giu_PARTY_LOCK(self):
        self.assertNotIn("_PARTY_LOCK", self._than("is_joined"),
                         "MainThread ket o day 15/15 mau py-spy")

    def test_is_strategist_khong_giu_PARTY_LOCK(self):
        self.assertNotIn("_PARTY_LOCK", self._than("is_strategist"))

    def test_joined_member_count_khong_giu_PARTY_LOCK(self):
        self.assertNotIn("_PARTY_LOCK", self._than("joined_member_count"))

    def test_is_joined_doc_ban_chup_BAT_BIEN(self):
        """Doc thang `_PARTY_JOINED` (set dang bi sua) co the no giua chung."""
        self.assertIn("_PARTY_JOINED_RO", self._than("is_joined"))

    def test_MOI_duong_ghi_deu_dong_bo_ban_chup(self):
        """Sot mot duong ghi = ban chup lech that -> bot ket luan sai so nguoi da join."""
        so_ghi = (self.src.count("_PARTY_JOINED[party_idx] =")
                  + self.src.count("_PARTY_JOINED.setdefault(party_idx, set()).add")
                  + self.src.count("_PARTY_JOINED.pop(party_idx, None)")
                  + self.src.count("_PARTY_JOINED.get(party_idx, set()).discard"))
        so_dong_bo = self.src.count("_dong_bo_joined_ro(party_idx)")
        self.assertGreaterEqual(so_dong_bo, so_ghi,
                                "co duong ghi `_PARTY_JOINED` ma khong cap nhat ban chup")


class TestBanChupChayThat(unittest.TestCase):
    """Chay that tren API that, khong chi doc chu."""

    PIDX = 9911

    def setUp(self):
        self.e1, self.e2 = b"\x01" * 8, b"\x02" * 8
        C.reset_party_joined(self.PIDX)

    def tearDown(self):
        C.reset_party_joined(self.PIDX)

    def test_mark_roi_doc_lai_dung(self):
        self.assertFalse(C.is_joined(self.PIDX, self.e1))
        C.mark_joined(self.PIDX, self.e1)
        self.assertTrue(C.is_joined(self.PIDX, self.e1))
        self.assertEqual(C.joined_member_count(self.PIDX), 1)

    def test_unmark_thi_mat(self):
        C.mark_joined(self.PIDX, self.e1)
        C.unmark_joined(self.PIDX, self.e1)
        self.assertFalse(C.is_joined(self.PIDX, self.e1))
        self.assertEqual(C.joined_member_count(self.PIDX), 0)

    def test_reset_thi_sach(self):
        C.mark_joined(self.PIDX, self.e1)
        C.mark_joined(self.PIDX, self.e2)
        self.assertEqual(C.joined_member_count(self.PIDX), 2)
        C.reset_party_joined(self.PIDX)
        self.assertEqual(C.joined_member_count(self.PIDX), 0)

    def test_doc_song_song_voi_ghi_khong_no(self):
        """Duong doc khong khoa -> phai chiu duoc viec ghi lien tuc ben canh."""
        dung = threading.Event()
        loi = []

        def _ghi():
            i = 0
            while not dung.is_set():
                i += 1
                e = bytes([i % 251]) * 8
                try:
                    C.mark_joined(self.PIDX, e)
                    C.unmark_joined(self.PIDX, e)
                except Exception as ex:      # pragma: no cover
                    loi.append(ex)
                    return

        def _doc():
            for _ in range(4000):
                try:
                    C.is_joined(self.PIDX, self.e1)
                    C.joined_member_count(self.PIDX)
                except Exception as ex:      # pragma: no cover
                    loi.append(ex)
                    return

        t = threading.Thread(target=_ghi, daemon=True)
        t.start()
        try:
            _doc()
        finally:
            dung.set()
            t.join(timeout=5)
        self.assertEqual(loi, [])


class TestRefreshChiDungBangDangXem(unittest.TestCase):
    def setUp(self):
        self.gui = _doc("gui.py")
        i = self.gui.find("    def _refresh(self):")
        self.assertGreater(i, 0)
        self.than = self.gui[i:self.gui.find("    def _drain_log(self):", i)]

    def test_co_ham_biet_party_nao_dang_xem(self):
        self.assertIn("def _party_dang_xem(self):", self.gui)

    def test_account_status_chi_goi_cho_party_dang_xem(self):
        i = self.than.find("ctrl.account_status(u)")
        self.assertGreater(i, 0)
        self.assertIn("if _hien else ()", self.than,
                      "van goi account_status cho ca 256 acc moi giay")

    def test_party_khong_hien_van_dem_duoc_acc_chay(self):
        """Cham mau nhom phai dung - chi la dem bang duong RE hon."""
        self.assertIn("ctrl.is_account_running(u)", self.than)

    def test_agi_report_co_cache_cho_party_khong_xem(self):
        self.assertIn("_AGI_CACHE_SEC", self.than)
        self.assertIn("self._agi_cache", self.than)

    def test_doi_tab_thi_dung_bang_NGAY(self):
        i = self.gui.find("def _on_tab_changed(self")
        khoi = self.gui[i:i + 1500]
        self.assertIn("self._refresh()", khoi)

    def test_MOT_chuoi_timer_duy_nhat(self):
        """Goi thang `_refresh()` ma khong huy timer dang cho = them mot chuoi chay song song."""
        i = self.gui.find("def _on_tab_changed(self")
        khoi = self.gui[i:i + 1500]
        self.assertIn("after_cancel", khoi)
        self.assertIn("self._refresh_after", self.than)


if __name__ == "__main__":
    unittest.main()
