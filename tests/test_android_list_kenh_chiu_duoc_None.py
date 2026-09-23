# -*- coding: utf-8 -*-
"""APK - danh sach kenh: MOT kenh khong ro so nguoi KHONG duoc lam mat ca bang.

`_on_channel_list` (bot/client.py) TU THEM kenh dang o vao bang khi server khong liet ke no:

    _ch_now = getattr(self, "current_channel", None)
    if _ch_now and int(_ch_now) not in chans:
        chans[int(_ch_now)] = (None, None)

Y HET client that: server khong liet ke kenh minh dang dung (thuong vi no DAY), va
`UIServerArea.instances` cua client cung tu them mot muc KHONG kem current/maxPlayers. Tuc bang
GAN NHU LUON co mot cap (None, None).

Ban PC xu dung - `gui.py::_show_channel_popup`:
    "cur/cap co the la None: kenh acc DANG DUNG ma server khong liet ke (client that cung tu them
     vao danh sach) -> khong biet so nguoi. Xep xuong cuoi va hien '?' chu dung so sanh None voi
     int (TypeError lam vo ca popup)."

Ban APK thi goi thang `pair[0].toInt()` -> None nem -> roi vao `catch` -> `emptyList()` -> UI bao
"Khong lay duoc danh sach kenh". MOT kenh None la MAT SACH CA BANG.

User 23/09: *"ban apk -> click doi kenh thi thay bao ko lay duoc danh sach kenh, du dang co rat
nhieu kenh"*.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AND = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _doc(ten):
    with io.open(os.path.join(AND, ten), encoding="utf-8") as fh:
        return fh.read()


def _than_getChannels(chi_code=False):
    s = _doc("BotForegroundService.kt")
    i = s.find("fun getChannels(")
    assert i > 0, "mat getChannels"
    than = s[i:s.find("\n    /**", i + 10)]
    if not chi_code:
        return than
    # CHI DONG CODE: chu thich co nhac dang CU de giai thich vi sao da bo - do la tai lieu,
    # khong phai code. Grep ca comment thi test do oan.
    return "\n".join(l for l in than.splitlines() if not l.strip().startswith("//"))


class TestServiceChiuDuocNone(unittest.TestCase):
    def setUp(self):
        self.than = _than_getChannels()

    def test_kieu_tra_ve_cho_phep_None(self):
        self.assertIn("List<Triple<Int, Int?, Int?>>", self.than,
                      "kieu khong cho None -> phai .toInt() tren None -> mat ca bang")

    def test_KHONG_goi_toInt_thang_tren_phan_tu(self):
        _code = _than_getChannels(chi_code=True)
        self.assertNotIn("pair[0].toInt()", _code, "None.toInt() nem -> emptyList()")
        self.assertNotIn("pair[1].toInt()", _code)

    def test_doc_an_toan_bang_getOrNull(self):
        self.assertIn("pair.getOrNull(0)?.toInt()", self.than)
        self.assertIn("pair.getOrNull(1)?.toInt()", self.than)

    def test_kenh_KHONG_RO_xep_xuong_CUOI(self):
        """Giong ban PC: `key=lambda kv: (kv[1][0] is None, kv[1][0] or 0)`."""
        self.assertIn("it.second == null", self.than, "khong xep kenh chua ro xuong cuoi")


class TestUIHienDauHoi(unittest.TestCase):
    def setUp(self):
        s = _doc("MainActivity.kt")
        i = s.find("fun ChannelDialog(")
        assert i > 0, "mat ChannelDialog"
        self.than = s[i:s.find("\n@Composable", i + 10)]
        self.src = s

    def test_dialog_nhan_kieu_cho_phep_None(self):
        self.assertIn("List<Triple<Int, Int?, Int?>>", self.than)

    def test_hien_dau_hoi_khi_chua_ro(self):
        self.assertIn('"?/?"', self.than, "khong ro so nguoi ma van in ra so -> in 'null/null'")

    def test_KHONG_con_cho_nao_khai_kieu_CU(self):
        """Sot mot cho la Kotlin khong bien dich, hoac te hon: ep kieu ngam roi nem luc chay."""
        self.assertNotIn("Triple<Int, Int, Int>", self.src,
                         "con cho khai kieu cu -> lech kieu voi getChannels")


class TestNguonNoneVanCon(unittest.TestCase):
    """Ve con lai cua cap: neu sau nay ai do bo duong tu them kenh dang o ben Python thi test tren
    thanh thua ma khong ai biet. Giu lai day de doc duoc quan he."""

    def test_python_van_tu_them_kenh_dang_o(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def _on_channel_list(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("chans[int(_ch_now)] = (None, None)", than,
                      "bo duong tu them kenh dang o -> lech han voi client that")


if __name__ == "__main__":
    unittest.main()
