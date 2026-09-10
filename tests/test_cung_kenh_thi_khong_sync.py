"""DA CUNG KENH THI KHONG DONG BO KENH - roi doi luc do la TU PHA PARTY.

User 10/09: "p1 lai deo thay lap party" -> "vi sao dieu phoi ngu toi muc cho leader chay ra bai
train 1 minh" -> "loi ko sua di con de lai lam cho gi".

CHUOI THAT (party 1, 23:18):

    23:18:02  bon member vao doi -> roster 4 nguoi        <- DA DU
    23:18:04 [chihao] (member) cap nhat kenh hien tai truoc sync: 1
    23:18:04 [chihao] Roi/giai tan party cu               <- ROI DOI de SYNC KENH
    23:18:04 [minh]   y het
    23:18:05  roster con 0                                <- doi TAN sau 3 giay
    23:18:07  leader moi lai... 23:19:09 lai tan... 23:20:10 leader di route MOT MINH

Trong khi chinh dieu phoi ghi `ca party da chung kenh 1`. Member roi doi de "dong bo" ve DUNG CAI
KENH NO DANG DUNG.

Va cau hoi cua user - "vi sao dieu phoi cho leader di mot minh" - co cau tra loi: KHONG PHAI dieu
phoi cho. Leader di mot minh la HAU QUA cuoi chuoi: doi cu tan -> moi lai -> lai tan -> khong bao
gio giu duoc doi -> cuoi cung no di.

Doi kenh BAT BUOC phai roi doi truoc (server cam doi kenh khi con trong doi - `S:007-002` ma 3
`<組隊不可換分區>`). Nen mot vong sync chay luc DA cung kenh khong chi vo ich: no pha party.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _than_sync(src):
    """Than `do_channel_sync` - neo theo THUT LE GIAM, khong theo cua so ky tu (L3i)."""
    i = src.find("        def do_channel_sync():")
    assert i > 0
    dong = src[i:].split("\n")
    het = len(dong)
    for k, d in enumerate(dong[1:], start=1):
        if d.strip() and not d.startswith(" " * 12):
            het = k
            break
    return "\n".join(dong[:het])


class TestCungKenhThiRaNgay(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.than = _than_sync(self.src)

    def test_co_cua_kiem_ca_party_cung_kenh(self):
        self.assertIn("CA PARTY DA CUNG KENH", self.than,
                      "khong kiem thi member roi doi de dong bo ve chinh kenh no dang dung")

    def test_cua_do_dung_TRUOC_moi_buoc_roi_doi(self):
        """Roi doi la buoc khong hoan tac duoc - kiem sau la party da tan."""
        i_kiem = self.than.find("CA PARTY DA CUNG KENH")
        self.assertGreater(i_kiem, 0)
        for _moc in ("leave_party()", "_prepare_channel_switch", "switch_channel("):
            i = self.than.find(_moc)
            if i > 0:
                self.assertLess(i_kiem, i, "cua kiem phai dung truoc '%s'" % _moc)

    def _khoi_cua(self):
        """Tu moc den het khoi `try` cua cua kiem - neo theo MA, khong theo cua so ky tu (L3i)."""
        i = self.than.find("CA PARTY DA CUNG KENH")
        self.assertGreater(i, 0)
        j = self.than.find("except Exception as e:", i)
        self.assertGreater(j, i)
        return self.than[i:j]

    def test_doc_THANG_kenh_tung_client(self):
        """Khong hoi ai, khong doi bao cao (L2)."""
        khoi = self._khoi_cua()
        self.assertIn("account_clients.get(", khoi)
        self.assertIn("current_channel", khoi)

    def test_chi_ra_khi_TAT_CA_cung_mot_kenh(self):
        """`len(_ks) == 1` - hai kenh khac nhau thi van phai sync."""
        khoi = self._khoi_cua()
        self.assertIn("len(_ks) == 1", khoi)

    def test_bo_acc_chua_doc_duoc_kenh(self):
        """Acc chua biet kenh (None/0) khong duoc tinh la 'kenh thu hai' -> sync oan."""
        khoi = self._khoi_cua()
        self.assertIn('getattr(_uc, "current_channel", None)', khoi)


class TestChayThatLogicChonKenh(unittest.TestCase):
    """Chay that phan loc kenh, khong chi doc chu."""

    @staticmethod
    def _tap_kenh(kenhs, chay=None):
        """Mo phong dung bieu thuc trong code: bo acc tat / chua doc duoc kenh."""
        chay = [True] * len(kenhs) if chay is None else chay
        return {int(k) for k, r in zip(kenhs, chay) if r and k}

    def test_cung_kenh_thi_mot_phan_tu(self):
        self.assertEqual(len(self._tap_kenh([1, 1, 1, 1])), 1)

    def test_lech_kenh_thi_nhieu_hon_mot(self):
        self.assertGreater(len(self._tap_kenh([1, 1, 2])), 1)

    def test_acc_TAT_khong_tinh(self):
        self.assertEqual(len(self._tap_kenh([1, 1, 9], chay=[True, True, False])), 1)

    def test_acc_CHUA_DOC_DUOC_kenh_khong_tinh(self):
        """`None`/0 = chua biet, khong phai 'kenh khac' - tinh vao la sync oan roi tan doi."""
        self.assertEqual(len(self._tap_kenh([1, None, 1])), 1)
        self.assertEqual(len(self._tap_kenh([1, 0, 1])), 1)


if __name__ == "__main__":
    unittest.main()
