# -*- coding: utf-8 -*-
"""APK - chon map train: danh sach o DIALOG RIENG, khong tha ngay tren o text.

### Goc benh

O "Map train" nam trong `Column(verticalScroll)` cua `AddPartyDialog` - `verticalScroll` do them
ngay 14/09 (commit `fd4a4a8` "dialog keo xuong duoc"). Va no la o DUY NHAT trong dialog CO BAN
PHIM: sau o dropdown con lai deu `readOnly`.

Chinh commit 14/09 da ghi trieu chung do cho dropdown "Quai":
    "khien cac field cuoi (vd dropdown 'Quai') bi che/lech vi tri popup - da xac nhan qua test
     thuc te tren emulator (chon Quai 'khong thay hien thi gi ca' vi popup tinh vi tri theo anchor
     da bi day ra ngoai)"

### BA cach tha danh sach NGAY TAI CHO - da thu, hong ca ba. DUNG LAM LAI.

| Cach | Hong the nao | User bao (23/09) |
|---|---|---|
| `Box` + `DropdownMenu(PopupProperties(focusable = false))` | popup ve DE LEN ban phim, IME gianh pointer -> tap bi CANCEL (scroll da bat dau thi van chay) | "list map vuot len vuot xuong van dc nhung click thi ko co gi xay ra, list map van con do" |
| `ExposedDropdownMenuBox` + `.menuAnchor()` | EDMB them lop bat su kien de nhan tap-ngoai; voi TextField KHONG readOnly no danh nhau voi IME va KET LAI | "tat list di thi ko tuong tac dc UI nao khac nua" |
| List render INLINE (Column co `verticalScroll` rieng, long trong Column da cuon cua dialog) | nang hon han - ca o text cung chet | "chon map van ko duoc, go text cung ko hien gi vao o text, o text ko duoc scroll len" |

### Cach dung: DIALOG RIENG

Khong co anchor de lech, khong long scroll, IME day noi dung dialog nhu moi dialog khac. Day la
khuon DA CHAY TOT san trong app: `ChannelDialog`, `CityDialog`, dialog chon he quai. Ban PC cung
the - `gui.py::_popup_channels` mo `tk.Toplevel` + `Listbox` rieng.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android",
                  "MainActivity.kt")


def _src():
    with io.open(KT, encoding="utf-8") as fh:
        return fh.read()


def _chi_code(s):
    """Bo comment Kotlin - ca `//` lan KDoc (`/**`, `*`, `*/`).

    Chu thich co nhac ten CA BA cach cu de chan lam lai; grep ca comment thi test do oan.
    """
    ra = []
    for l in s.splitlines():
        t = l.strip()
        if t.startswith("//") or t.startswith("/*") or t.startswith("*"):
            continue
        ra.append(l)
    return "\n".join(ra)


def _khoi_o_map(chi_code=False):
    """Khoi dung O "Map train" trong `AddPartyDialog` - tu `mapOptions` toi o "Quai"."""
    s = _src()
    i = s.find("val mapOptions = trainMapOptions()")
    assert i > 0, "mat khoi chon map train"
    j = s.find("if (isPickMode) {", i)
    assert j > i
    khoi = s[i:j]
    return _chi_code(khoi) if chi_code else khoi


def _than_dialog(chi_code=False):
    s = _src()
    i = s.find("fun TrainMapDialog(")
    assert i > 0, "mat TrainMapDialog"
    j = s.find("\n@Composable", i + 10)
    than = s[i:j if j > i else len(s)]
    return _chi_code(than) if chi_code else than


class TestKhongTaDanhSachTaiCho(unittest.TestCase):
    """Ba cach cu deu tha danh sach ngay tren o text. Chan ca ba."""

    def setUp(self):
        self.code = _khoi_o_map(chi_code=True)

    def test_KHONG_dung_DropdownMenu(self):
        self.assertNotIn("DropdownMenu(", self.code, "popup neo anchor trong vung cuon -> lech")

    def test_KHONG_dung_ExposedDropdownMenuBox(self):
        self.assertNotIn("ExposedDropdownMenuBox(", self.code,
                         "EDMB + TextField khong readOnly -> lop bat su kien ket lai, liet ca UI")

    def test_KHONG_dung_PopupProperties(self):
        self.assertNotIn("PopupProperties(", self.code)

    def test_KHONG_long_them_mot_verticalScroll(self):
        """Khoi nay da nam trong `Column(verticalScroll)` cua dialog - long them la ca o text chet."""
        self.assertNotIn("verticalScroll(", self.code)

    def test_o_text_CHI_DOC_va_bam_duoc(self):
        self.assertIn("readOnly = true", self.code, "o khong readOnly -> ban phim bat len lai")
        self.assertIn(".clickable {", self.code, "bam vao o khong mo duoc dialog")

    def test_mo_DIALOG_RIENG(self):
        self.assertIn("TrainMapDialog(", self.code)


class TestDialogCoDuTinhNang(unittest.TestCase):
    """Chuyen sang dialog khong duoc lam mat thu gi."""

    def setUp(self):
        self.than = _than_dialog()
        self.code = _than_dialog(chi_code=True)

    def test_co_o_TIM_map(self):
        self.assertIn("filterTrainMapOptions(", self.code, "mat duong loc map")
        self.assertIn('Text("Tìm map")', self.than)

    def test_co_nhom_GAP_MO(self):
        self.assertIn("trainMapGroupOrder(", self.code)
        self.assertIn("nhomDangGap", self.code)

    def test_dang_TIM_thi_bung_het_nhom(self):
        """Go chu ma van phai mo tung nhom la vo ly."""
        self.assertIn("!dangTim", self.code)

    def test_bao_khi_KHONG_TIM_THAY(self):
        self.assertIn("Không tìm thấy map", self.than)

    def test_danh_sach_CUON_duoc_va_co_gioi_han_chieu_cao(self):
        self.assertIn("LazyColumn(", self.code)
        self.assertIn(".height(", self.code)

    def test_bam_mot_muc_la_CHON_map(self):
        self.assertIn("onPick(key, mapName)", self.code)


class TestDongDialogThiGIU_NGUYEN(unittest.TestCase):
    """`snapToFirst` cu: dong list thi tu chon map DAU TIEN khop voi chu dang co trong o - ma chu
    do chinh la TEN MAP DANG CHON -> chon lai chinh no -> KHONG MOT DAU HIEU GI. Duong am tham nay
    lam hien tuong "bam vao list ma khong thay gi xay ra" khong the doc duoc tu ngoai."""

    def test_KHONG_con_snapToFirst(self):
        self.assertNotIn("snapToFirst", _chi_code(_src()))

    def test_dong_dialog_chi_ha_co(self):
        code = _khoi_o_map(chi_code=True)
        i = code.find("onDismiss = {")
        self.assertGreater(i, 0)
        self.assertIn("trainMapExpanded = false", code[i:i + 120])
        self.assertNotIn("pickTrainMap(", code[i:i + 120], "dong dialog ma van tu chon map")


class TestDoiMapThiBoDIEM_QUAI_cu(unittest.TestCase):
    def test_pickTrainMap_reset_diem_quai(self):
        code = _khoi_o_map(chi_code=True)
        i = code.find("fun pickTrainMap(")
        self.assertGreater(i, 0)
        than = code[i:code.find("}", i)]
        self.assertIn("trainMobIndex = -1", than, "doi map ma giu diem quai cu -> diem khong ton tai")


class TestSauODANG_CHAY_TOT_giu_nguyen(unittest.TestCase):
    """Sau o dropdown con lai deu `readOnly` nen khong co ban phim -> popup khong lech. Dung doi
    chung: bo `readOnly` o mot trong so do la no dinh dung benh nay."""

    def test_o_quai_van_dung_ExposedDropdownMenuBox_va_readOnly(self):
        s = _src()
        i = s.find("val mobOptions = trainMobOptions(trainMapKey)")
        self.assertGreater(i, 0, "mat o chon diem quai")
        than = s[i:i + 1200]
        self.assertIn("ExposedDropdownMenuBox(", than)
        self.assertIn("readOnly = true", than)

    def test_KHONG_o_nao_dung_focusable_false(self):
        _xau = [l.strip() for l in _chi_code(_src()).splitlines() if "focusable = false" in l]
        self.assertEqual(_xau, [], "con dropdown khai focusable=false: %s" % _xau)


if __name__ == "__main__":
    unittest.main()
