"""LOAN DAU phai DU BA NGAY: thu 3, thu 5, thu 7 - o CA HAI nguon lich.

User 10/09: "mien sao du loan dau thu 3 thu 5 thu 7 la dc roi".

HAI NGUON, ca hai deu phai du:
  1. `events.json` -> `loan_dau.lich`  (nguon chinh, ca ban PC lan asset APK)
  2. `bot/loandau.py: LICH_MAC_DINH`   (du phong khi khong doc duoc events.json)

Truoc 10/09, `LICH_MAC_DINH` chi co MOT ngay (thu 3). `events.json` hong/asset APK loi mot lan la
mat han loan dau thu 5 va thu 7 - va mat AM THAM, khong dong log nao. Dung bai hoc "Servers.kt
FALLBACK thieu server" trong CLAUDE.md: PC 17 server, APK 16, khong ai biet cho toi khi user hoi.

BAY DE NHAM: `thu` la `datetime.weekday()` - 0=T2, 1=T3, 2=T4, 3=T5, 4=T6, 5=T7, 6=CN.
Nhin `lich=[1, 3, 5]` rat de tuong la "thu 1, thu 3, thu 5" trong khi that ra la THU 3, THU 5,
THU 7. Chinh vi vay `documents/LOAN_DAU.md` (muc "Khai bao lich") tung BO SOT han entry thu 5 du
code da co - doc lac hau lam nguoi doc tuong tinh nang chua lam.
"""
from __future__ import annotations

import datetime
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import loandau

# weekday() cua ba ngay co loan dau
T3, T5, T7 = 1, 3, 5
TEN = {T3: "thu 3", T5: "thu 5", T7: "thu 7"}


def _lich_events(duong):
    with io.open(os.path.join(ROOT, *duong), encoding="utf-8") as fh:
        d = json.load(fh)
    return (d.get("events") or {}).get("loan_dau", {}).get("lich") or []


class TestEventsJsonDuBaNgay(unittest.TestCase):
    NGUON = (
        ("events.json",),
        ("android", "app", "src", "main", "assets", "train_bot_data", "events.json"),
    )

    def test_ca_PC_lan_APK_deu_du_ba_ngay(self):
        for duong in self.NGUON:
            lich = _lich_events(duong)
            thu = sorted(int(b.get("thu")) for b in lich if b.get("thu") is not None)
            self.assertEqual(thu, [T3, T5, T7],
                             "%s thieu ngay: co %s" % ("/".join(duong), thu))

    def test_PC_va_APK_KHOP_NHAU(self):
        """Lech mot ben la dien thoai chay lich khac may tinh, khong ai biet."""
        self.assertEqual(_lich_events(self.NGUON[0]), _lich_events(self.NGUON[1]))

    def test_moi_ngay_deu_co_khung_gio(self):
        for b in _lich_events(self.NGUON[0]):
            self.assertIn("tu", b, b)
            self.assertIn("den", b, b)


class TestLichMacDinhDuBaNgay(unittest.TestCase):
    """Du phong khong duoc thieu ngay - thieu la mat am tham."""

    def test_du_ba_ngay(self):
        thu = sorted(int(b["thu"]) for b in loandau.LICH_MAC_DINH)
        self.assertEqual(thu, [T3, T5, T7], "LICH_MAC_DINH thieu ngay: %s" % thu)

    def test_khung_gio_khop_events_json(self):
        goc = {int(b["thu"]): (b.get("tu"), b.get("den")) for b in _lich_events(("events.json",))}
        for b in loandau.LICH_MAC_DINH:
            _t = int(b["thu"])
            self.assertEqual((b.get("tu"), b.get("den")), goc[_t],
                             "du phong lech gio voi events.json o %s" % TEN[_t])


class TestNhanDungNgay(unittest.TestCase):
    """Chay that qua `_buoi_hom_nay` / `in_event_window` voi ngay gia."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "events.json"), encoding="utf-8") as fh:
            self.ev = (json.load(fh).get("events") or {}).get("loan_dau")

    @staticmethod
    def _ngay(weekday, gio, phut=0):
        """Mot ngay THAT co `weekday()` nhu yeu cau (07/09/2026 = thu 2)."""
        return datetime.datetime(2026, 9, 7 + weekday, gio, phut)

    def test_ba_ngay_deu_nhan_ra(self):
        for _t in (T3, T5, T7):
            buoi = loandau._buoi_hom_nay(self.ev, self._ngay(_t, 21))
            self.assertIsNotNone(buoi, "khong nhan ra %s" % TEN[_t])
            self.assertEqual(int(buoi["thu"]), _t)

    def test_ngay_KHONG_co_loan_dau_thi_None(self):
        for _t in (0, 2, 4, 6):      # T2, T4, T6, CN
            self.assertIsNone(loandau._buoi_hom_nay(self.ev, self._ngay(_t, 21)))
            self.assertFalse(loandau.in_event_window(self._ngay(_t, 21), ev=self.ev))

    def test_trong_gio_va_ngoai_gio(self):
        self.assertTrue(loandau.in_event_window(self._ngay(T5, 21), ev=self.ev))
        self.assertFalse(loandau.in_event_window(self._ngay(T5, 19, 59), ev=self.ev))
        self.assertFalse(loandau.in_event_window(self._ngay(T5, 22), ev=self.ev))

    def test_THU_7_lech_nua_tieng(self):
        """T7 la 20:30-22:30 - `20 <= hour < 22` khong bieu dien duoc, phai so ca PHUT."""
        self.assertFalse(loandau.in_event_window(self._ngay(T7, 20, 15), ev=self.ev))
        self.assertTrue(loandau.in_event_window(self._ngay(T7, 20, 30), ev=self.ev))
        self.assertTrue(loandau.in_event_window(self._ngay(T7, 22, 15), ev=self.ev))
        self.assertFalse(loandau.in_event_window(self._ngay(T7, 22, 30), ev=self.ev))

    def test_THU_5_dung_tham_so_cua_capture(self):
        """Doi chieu `captures/loandau_doi_20260903.pcap` (03/09/2026 = thu 5)."""
        bt = loandau.bien_the_hom_nay(self.ev, self._ngay(T5, 21))
        self.assertEqual(bt.get("select"), "03000200")
        self.assertEqual((bt.get("party_battle") or {}).get("npc_option"), "01000400")
        # Thu 5 dung CHUNG map/NPC voi thu 3 - khong khai lai trong `lich`.
        self.assertEqual(int(bt.get("dest_map")), 10991)
        self.assertEqual(list((bt.get("party_battle") or {}).get("point") or ()), [910, 290])

    def test_THU_3_giu_nguyen_gia_tri_goc(self):
        bt = loandau.bien_the_hom_nay(self.ev, self._ngay(T3, 21))
        self.assertEqual(bt.get("select"), "03000300")
        self.assertEqual((bt.get("party_battle") or {}).get("npc_option"), "01000300")

    def test_THU_7_la_SANH_KHAC(self):
        bt = loandau.bien_the_hom_nay(self.ev, self._ngay(T7, 21))
        self.assertEqual(int(bt.get("dest_map")), 54901)
        self.assertEqual(bt.get("select"), "03005a00")
        self.assertEqual(list((bt.get("party_battle") or {}).get("point") or ()), [1630, 430])

    def test_du_phong_cung_nhan_ra_ba_ngay(self):
        """`ev` khong co `lich` -> roi ve LICH_MAC_DINH, van phai du ba ngay."""
        for _t in (T3, T5, T7):
            self.assertTrue(loandau.in_event_window(self._ngay(_t, 21), ev={"label": "x"}),
                            "du phong bo mat %s" % TEN[_t])


class TestDocKhongLacHau(unittest.TestCase):
    """Doc bo sot entry = nguoi doc tuong tinh nang chua lam (dung ca 10/09)."""

    def test_LOAN_DAU_md_liet_ke_du_ba_entry(self):
        with io.open(os.path.join(ROOT, "documents", "LOAN_DAU.md"), encoding="utf-8") as fh:
            d = fh.read()
        i = d.find("### Khai báo: `lich` trong `events.json`")
        self.assertGreater(i, 0)
        khoi = d[i:d.find("###", i + 10)]
        for _t in (T3, T5, T7):
            self.assertIn('"thu": %d' % _t, khoi, "doc thieu entry %s" % TEN[_t])

    def test_doc_canh_bao_thu_la_weekday(self):
        with io.open(os.path.join(ROOT, "documents", "LOAN_DAU.md"), encoding="utf-8") as fh:
            d = fh.read()
        self.assertIn("weekday()", d, "khong canh bao thi nguoi doc tuong `thu: 3` la thu 3")


if __name__ == "__main__":
    unittest.main()
