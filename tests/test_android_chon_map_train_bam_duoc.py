# -*- coding: utf-8 -*-
"""APK - o "Map train": danh sach map phai BAM DUOC khi ban phim dang mo.

### Goc benh

O nay nam trong `Column(verticalScroll)` cua AlertDialog - `verticalScroll` do them ngay 14/09
(commit `fd4a4a8` "dialog keo xuong duoc"). Va no la o DUY NHAT trong dialog CO BAN PHIM (sau o
dropdown con lai deu `readOnly`).

Ban phim mo -> dialog co lai -> Column cuon -> ANCHOR DICH, ma popup thi da dat xong -> nguoi dung
nhin thay list mot cho con vung cham o cho khac.

Chinh commit 14/09 da ghi lai trieu chung do cho dropdown "Quai":
    "khien cac field cuoi (vd dropdown 'Quai') bi che/lech vi tri popup - da xac nhan qua test
     thuc te tren emulator (chon Quai 'khong thay hien thi gi ca' vi popup tinh vi tri theo anchor
     da bi day ra ngoai)"

### Hai cach DA THU va DEU HONG - dung lam lai

| Cach | Hong the nao | User bao |
|---|---|---|
| `Box` + `PopupProperties(focusable = false)` | popup ve DE LEN ban phim, IME gianh pointer -> tap bi CANCEL (scroll da bat dau thi van chay) | "list map vuot len vuot xuong van dc nhung click thi ko co gi xay ra, list map van con do" |
| `ExposedDropdownMenuBox` + `.menuAnchor()` | EDMB them lop bat su kien de nhan tap-ngoai; voi TextField KHONG readOnly no danh nhau voi IME va KET LAI | "tat list di thi ko tuong tac dc UI nao khac nua" |

CON POPUP LA CON LECH -> bo han popup cho RIENG o nay, render list INLINE trong than dialog.
Sau o `readOnly` khac GIU NGUYEN `ExposedDropdownMenuBox` (chung khong co ban phim, dang chay tot).

### Bo cuc (user chot 23/09)

"them cai tu scroll len de cai o text sat phia tren man hinh de go text thi van du thay dang go gi
ma list map cung nhin duoc nhieu hon" -> `bringIntoViewRequester` dat tren CA KHOI (o text + list),
keo vao view la ca khoi vao -> o text len gan dinh, phan con lai danh cho list.

KHONG cho ban phim de len list: phan bi de la phan BAM KHONG DUOC - dung cai benh dang chua.
`imePadding()` cho list dung ngay TREN ban phim, list tu cuon nen dai bao nhieu cung voi toi duoc.
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


def _khoi_map_train(s, chi_code=False):
    """Khoi dung o "Map train" - tu cho tinh `mapOptions` toi truoc o "Quai"."""
    i = s.find("val mapOptions = trainMapOptions()")
    assert i > 0, "mat khoi chon map train"
    j = s.find("if (isPickMode) {", i)
    assert j > i
    khoi = s[i:j]
    if not chi_code:
        return khoi
    # CHI DONG CODE: chu thich co nhac hai cach CU de chan lam lai - do la tai lieu.
    return "\n".join(l for l in khoi.splitlines() if not l.strip().startswith("//"))


class TestKhongConPopup(unittest.TestCase):
    def setUp(self):
        self.code = _khoi_map_train(_src(), chi_code=True)

    def test_KHONG_dung_ExposedDropdownMenuBox(self):
        self.assertNotIn("ExposedDropdownMenuBox(", self.code,
                         "EDMB + TextField khong readOnly -> lop bat su kien ket lai, liet ca UI")

    def test_KHONG_dung_DropdownMenu(self):
        self.assertNotIn("DropdownMenu(", self.code, "con popup la con lech anchor")

    def test_KHONG_dung_PopupProperties(self):
        self.assertNotIn("PopupProperties(", self.code)

    def test_list_render_INLINE(self):
        self.assertIn("if (trainMapExpanded) {", self.code, "list khong con ve trong than dialog")
        self.assertIn("MucChonMap(", self.code, "muc chon map phai la Row bam duoc, khong phai menu item")


class TestBoCucTheoUser(unittest.TestCase):
    def setUp(self):
        self.code = _khoi_map_train(_src(), chi_code=True)

    def test_keo_o_text_len_sat_tren(self):
        self.assertIn("BringIntoViewRequester()", self.code)
        self.assertIn("bringIntoView()", self.code)

    def test_keo_CA_KHOI_chu_khong_chi_o_text(self):
        """Neo tren ca khoi (o text + list) thi keo vao view moi day o text len gan dinh."""
        i_neo = self.code.find(".bringIntoViewRequester(")
        i_field = self.code.find("value = trainMapText,")
        self.assertGreater(i_neo, 0)
        self.assertGreater(i_field, 0)
        self.assertLess(i_neo, i_field, "neo dat sau o text -> chi keo vua du thay o text")

    def test_ban_phim_KHONG_de_len_list(self):
        """Phan bi ban phim de la phan BAM KHONG DUOC - dung cai benh dang chua."""
        self.assertIn(".imePadding()", self.code, "list khong tranh ban phim")

    def test_list_co_gioi_han_chieu_cao_va_TU_CUON(self):
        """Nam trong Column(verticalScroll) nen phai chan chieu cao, va phai cuon rieng de khong
        mat map nao."""
        self.assertIn("heightIn(max =", self.code)
        self.assertIn("verticalScroll(rememberScrollState())", self.code)


class TestDongListThiGIU_NGUYEN(unittest.TestCase):
    """`snapToFirst` cu: dong list thi tu chon map DAU TIEN khop voi chu dang co trong o. Ma chu do
    chinh la TEN MAP DANG CHON -> loc ra chinh no -> chon lai chinh no -> KHONG MOT DAU HIEU GI.
    Duong am tham nay lam hien tuong "bam vao list ma khong thay gi xay ra" khong the doc duoc."""

    def setUp(self):
        self.code = _khoi_map_train(_src(), chi_code=True)

    def test_KHONG_con_snapToFirst(self):
        self.assertNotIn("snapToFirst", self.code, "van con duong tu chon ho map dau danh sach")

    def test_dong_list_chi_tra_ve_map_dang_chon(self):
        i = self.code.find("fun closeTrainMapDropdown(")
        self.assertGreater(i, 0)
        than = self.code[i:i + 400]
        self.assertIn("selectedTrainMapTextValue()", than)
        self.assertNotIn("pickTrainMap(", than, "dong list ma van tu chon map")


class TestVANGIU_tinh_nang_cu(unittest.TestCase):
    """Bo popup khong duoc lam mat thu gi."""

    def setUp(self):
        self.code = _khoi_map_train(_src(), chi_code=True)

    def test_van_go_tim_map_duoc(self):
        self.assertIn("filterTrainMapOptions(", self.code)
        self.assertIn("trainMapExpanded = true", self.code, "go chu ma khong mo list")

    def test_van_co_nhom_gap_mo(self):
        self.assertIn("toggleTrainMapGroup(", self.code)
        self.assertIn("collapsedTrainMapGroups", self.code)

    def test_van_bao_khi_khong_tim_thay(self):
        self.assertIn("Không tìm thấy map", self.code)


class TestSauODANG_CHAY_TOT_giu_nguyen(unittest.TestCase):
    """Sau o dropdown con lai deu `readOnly` nen khong co ban phim -> popup khong lech. Dung doi
    chung: neu sau nay ai do bo `readOnly` o mot trong so do, no se dinh dung benh nay."""

    def setUp(self):
        self.src = _src()

    def test_o_quai_van_dung_ExposedDropdownMenuBox_va_readOnly(self):
        i = self.src.find("val mobOptions = trainMobOptions(trainMapKey)")
        self.assertGreater(i, 0, "mat o chon diem quai")
        than = self.src[i:i + 1200]
        self.assertIn("ExposedDropdownMenuBox(", than)
        self.assertIn("readOnly = true", than, "bo readOnly la o nay dinh benh cua o Map train")

    def test_KHONG_o_nao_dung_focusable_false(self):
        _that = [l for l in self.src.splitlines() if not l.strip().startswith("//")]
        _xau = [l.strip() for l in _that if "focusable = false" in l]
        self.assertEqual(_xau, [], "con dropdown khai focusable=false: %s" % _xau)


if __name__ == "__main__":
    unittest.main()
