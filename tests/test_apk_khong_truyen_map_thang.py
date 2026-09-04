"""APK: KHONG duoc truyen thang Map/List qua Chaquopy - phai NOI CHUOI truoc.

Ban release bi R8 rut gon ten lop, nen Python nhan mot OBJECT JAVA chu khong phai dict/list.
Hai kieu hong, ca hai deu da xay ra THAT:

  - `dict(raw)`             -> `TypeError: 'w' object is not iterable` -> MOI acc bao "Loi" ngay
                               luc bam Chay (APK 1.1.202609040107, user bao 04/09). Truoc do la
                               `'t' object is not iterable` (APK 1.1.202608181827) voi
                               `eventExchangeItems`.
  - `isinstance(raw, dict)` -> False -> tra {} IM LANG. `scrollModes`/`materialModes` dinh cai
                               nay: tick "giu/bo" cuon + nguyen lieu cua user tren APK bi bo qua
                               HANG THANG ma khong he bao loi.

Cung ho ly do voi cac bay khac trong CLAUDE.md: hong am tham vi khong ai bao.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import run_party_digioi as rpd        # noqa: E402
finally:
    sys.argv = _argv

KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _kt(ten):
    with io.open(os.path.join(KT, ten), encoding="utf-8") as fh:
        return fh.read()


def _py():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _goi_setup(src):
    """Doan tham so cua loi goi `setup_party_runtime` trong BotForegroundService.kt."""
    m = re.search(r'callAttr\(\s*\n?\s*"setup_party_runtime",(.*?)\n            \)', src, re.S)
    assert m, "khong tim thay loi goi setup_party_runtime"
    return m.group(1)


class TestKhongTruyenMapThang(unittest.TestCase):
    """Moi truong Map/List cua `Party` khi di qua Chaquopy deu phai duoc NOI CHUOI / JSON."""

    def test_moi_truong_tap_hop_deu_duoc_chuyen_doi(self):
        party = _kt("Party.kt")
        truong = re.findall(r"val ([a-zA-Z]+): (?:Map|List|Set)<", party)
        self.assertTrue(truong, "khong doc duoc truong tap hop nao trong Party.kt")
        than = _goi_setup(_kt("BotForegroundService.kt"))
        for ten in truong:
            for m in re.finditer(r"([A-Za-z]*\()?party\.%s\b([^,\n]*)" % re.escape(ten), than):
                boc, duoi = m.group(1) or "", m.group(2)
                # Hop le: `.joinToString(...)` ngay sau, HOAC duoc boc trong ham tra ve String
                # (vd `teamDungeonsJson(party.teamDungeons)`).
                self.assertTrue(
                    "joinToString" in duoi or boc.endswith("Json("),
                    "party.%s truyen THANG Map/List qua Chaquopy -> Python nhan object Java "
                    "(xem docstring file nay)" % ten)

    def test_teamDungeons_di_bang_JSON(self):
        than = _goi_setup(_kt("BotForegroundService.kt"))
        self.assertIn("teamDungeonsJson(party.teamDungeons)", than)

    def test_accounts_di_bang_chuoi_phang(self):
        src = _kt("BotForegroundService.kt")
        self.assertIn("val accountsFlat = activeAccounts.joinToString(SEP)", src)

    def test_boxModes_gia_tri_bool_ra_1_hoac_0(self):
        """De nguyen "true"/"false" thi ben Python "false" cung la chuoi TRUTHY -> mo ca ruong
        user KHONG tick."""
        than = _goi_setup(_kt("BotForegroundService.kt"))
        self.assertIn('if (it.value) 1 else 0', than)


class TestPythonNhanCaHaiKieu(unittest.TestCase):
    def test_chuoi_k_bang_v(self):
        self.assertEqual(rpd._map_cau_hinh("0xc946=drop\n0xc947=keep"),
                         {"0xc946": "drop", "0xc947": "keep"})

    def test_dict_van_chay(self):
        """Ban PC / test goi thang bang dict - khong duoc pha."""
        self.assertEqual(rpd._map_cau_hinh({"0xc946": "drop"}), {"0xc946": "drop"})

    def test_rong_va_rac(self):
        self.assertEqual(rpd._map_cau_hinh(None), {})
        self.assertEqual(rpd._map_cau_hinh(""), {})
        self.assertEqual(rpd._map_cau_hinh("dong khong co dau bang\n\n  "), {})

    def test_object_la_thi_tra_RONG_chu_khong_no(self):
        """Object Java (hoac gi do khong ro) -> {} chu KHONG duoc raise: mot cai tick hong khong
        duoc lam chet ca luot chay acc."""
        class _La:
            pass
        self.assertEqual(rpd._map_cau_hinh(_La()), {})

    def test_gia_tri_bool(self):
        ra = rpd._map_cau_hinh("0x1=1\n0x2=0\n0x3=true\n0x4=false", gia_tri_bool=True)
        self.assertEqual(ra, {"0x1": True, "0x2": False, "0x3": True, "0x4": False})

    def test_bool_that_giu_nguyen(self):
        ra = rpd._map_cau_hinh({"0x1": True, "0x2": False}, gia_tri_bool=True)
        self.assertEqual(ra, {"0x1": True, "0x2": False})


class TestNoiVaoSetupPartyRuntime(unittest.TestCase):
    def setUp(self):
        self.src = _py()

    def test_ba_map_deu_qua_ham_kiem(self):
        self.assertIn('"box_modes": _map_cau_hinh(box_modes, gia_tri_bool=True)', self.src)
        self.assertIn('"scroll_modes": _map_cau_hinh(scroll_modes)', self.src)
        self.assertIn('"material_modes": _map_cau_hinh(material_modes)', self.src)

    def test_KHONG_con_dict_thang(self):
        """`dict(box_modes or {})` chinh la dong lam APK chet."""
        self.assertNotIn("dict(box_modes or {})", self.src)


if __name__ == "__main__":
    unittest.main()
