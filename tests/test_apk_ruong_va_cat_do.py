# -*- coding: utf-8 -*-
"""APK phai co DU hai tick con thieu so voi ban PC: "Tự dọn rương trang bị" va "Tự cất đồ".

Bai test doc THANG file .kt (giong cac test APK khac trong repo): `gradlew compileReleaseKotlin`
chi noi code BIEN DICH DUOC, khong noi no con noi dung day chuyen sang Python.

Chuoi noi Kotlin -> Python di qua `setup_party_runtime`, ma Kotlin goi ham do THEO VI TRI. Them
tham so vao GIUA signature la lech het cac tham so phia sau ma khong loi gi ca - nen o day neo
lai ca thu tu.
"""
import os
import re
import sys
import unittest

_GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _GOC)

_KT = os.path.join(_GOC, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _doc(p):
    with open(os.path.join(_GOC, p), encoding="utf-8") as fh:
        return fh.read()


def _kt(name):
    with open(os.path.join(_KT, name), encoding="utf-8") as fh:
        return fh.read()


class TestModelVaLuuTru(unittest.TestCase):
    def test_party_co_truong_moi(self):
        src = _kt("Party.kt")
        for f in ("autoOpenBoxes", "boxModes", "autoCatDo"):
            self.assertIn("val %s" % f, src, "Party.kt thieu %s" % f)
            # copy() thieu truong = sua party xong thi truong do bi reset ve mac dinh
            self.assertIn("%s = source.%s" % (f, f), src,
                          "Party.kt copy khong mang theo %s -> sua party la mat" % f)

    def test_partystore_doc_va_ghi(self):
        src = _kt("PartyStore.kt")
        for k in ("auto_open_boxes", "box_modes", "auto_cat_do"):
            self.assertIn('optBoolean("%s"' % k if k != "box_modes" else 'optJSONObject("%s"' % k,
                          src, "PartyStore khong DOC %s" % k)
            self.assertIn('put("%s"' % k, src, "PartyStore khong GHI %s" % k)


class TestCauNoiSangPython(unittest.TestCase):
    def test_kotlin_truyen_ba_tham_so_o_CUOI(self):
        """Kotlin goi setup_party_runtime THEO VI TRI -> ba tham so moi phai o CUOI."""
        src = _kt("BotForegroundService.kt")
        m = re.search(r'callAttr\(\s*\n?\s*"setup_party_runtime",(.*?)\n\s*\)', src, re.S)
        self.assertIsNotNone(m, "khong tim thay loi goi setup_party_runtime")
        goi = m.group(1)
        self.assertIn("party.autoOpenBoxes", goi)
        self.assertIn("party.boxModes", goi)
        self.assertIn("party.autoCatDo", goi)
        self.assertLess(goi.index("party.autoBagExpand"), goi.index("party.autoOpenBoxes"),
                        "tham so moi phai nam SAU autoBagExpand, khong duoc chen vao giua")

    def test_python_nhan_dung_thu_tu(self):
        src = _doc("run_party_digioi.py")
        m = re.search(r"def setup_party_runtime\((.*?)\):", src, re.S)
        self.assertIsNotNone(m)
        ten = [x.split("=")[0].strip() for x in re.findall(r"(\w+\s*=\s*[^,)]+)", m.group(1))]
        for k in ("auto_open_boxes", "box_modes", "auto_cat_do"):
            self.assertIn(k, ten, "setup_party_runtime thieu %s" % k)
        self.assertLess(ten.index("bag_expand_gold"), ten.index("auto_open_boxes"),
                        "thu tu tham so PHAI khop ben Kotlin (goi theo vi tri)")

    def test_python_gan_vao_party_config(self):
        src = _doc("run_party_digioi.py")
        for k in ("auto_open_boxes", "box_modes", "auto_cat_do"):
            self.assertRegex(src, r'"%s":\s' % k, "khong gan %s vao PARTY_CONFIG" % k)

    def test_ham_luu_list_cat_nhan_CHUOI(self):
        """Chaquopy khong convert dung List<String> -> phai nhan chuoi noi bang xuong dong."""
        src = _doc("run_party_digioi.py")
        self.assertIn("def save_cat_do_items_str(", src)
        kt = _kt("BotForegroundService.kt")
        # Neo theo Y NGHIA: co goi ham do va co noi chuoi. KHONG neo theo mot dong lien mach -
        # xuong dong cho vua 100 cot la bai test dut du hanh vi khong doi.
        self.assertIn('"save_cat_do_items_str"', kt)
        self.assertIn("joinToString(", kt)
        self.assertNotRegex(kt, r'callAttr\(\s*"save_cat_do_items_str",\s*items\s*\)',
                            "truyen thang List/Map se vo o ban release (R8)")

    def test_list_cat_KHONG_luu_theo_party(self):
        """List cat la MOT file chung - lo luu them vao PartyStore la hai nguon lech nhau.

        Chi cam TRUONG/KHOA, khong cam nhac ten file trong chu thich (chu thich giai thich
        chinh chuyen "list nay khong o day" thi rat nen co).
        """
        self.assertNotIn('"cat_do_items"', _kt("PartyStore.kt"))
        self.assertNotRegex(_kt("Party.kt"), r"val\s+catDoItems")


class TestGiaoDien(unittest.TestCase):
    def test_hai_tick_va_nut_list(self):
        src = _kt("MainActivity.kt")
        self.assertIn('Text("Tự cất đồ vào Tiền trang")', src)
        self.assertIn('Text("List cất")', src)
        self.assertIn('Text("Tự dọn rương trang bị và Phó bản")', src)
        self.assertIn('Text("List rương")', src)

    def test_thu_tu_giong_ban_PC(self):
        """Cat do nam GIUA ban Noi dat va vut item rac; ruong NGAY SAU donate nguyen lieu."""
        src = _kt("MainActivity.kt")
        i_noi = src.index('Text("Tự bán Nồi đất")')
        i_cat = src.index('Text("Tự cất đồ vào Tiền trang")')
        i_rac = src.index('Text("Tự vứt item rác (Ngọc Hư)")')
        i_mat = src.index('Text("Tự đóng góp nguyên liệu cho quân đoàn")')
        i_box = src.index('Text("Tự dọn rương trang bị và Phó bản")')
        i_cuon = src.index('Text("Tự phân giải cuộn võ tướng rác")')
        self.assertLess(i_noi, i_cat)
        self.assertLess(i_cat, i_rac)
        self.assertLess(i_mat, i_box)
        self.assertLess(i_box, i_cuon)

    def test_dialog_duoc_hien(self):
        src = _kt("MainActivity.kt")
        for d in ("BoxListDialog", "CatDoListDialog"):
            self.assertIn("fun %s(" % d, src, "chua dinh nghia %s" % d)
            self.assertRegex(src, r"\n\s+%s\(" % d, "%s dinh nghia roi nhung KHONG hien" % d)

    def test_doc_asset_da_khai_bao(self):
        """Asset nao APK doc thi PHAI co trong SHARED_ASSETS, khong thi APK chay ra list rong."""
        src = _kt("MainActivity.kt")
        sync = _doc(os.path.join("tools", "sync_apk_python.py"))
        for a in re.findall(r'assets\.open\("train_bot_data/([\w.]+)"\)', src):
            self.assertIn('"%s"' % a, sync, "%s chua khai bao trong SHARED_ASSETS" % a)


if __name__ == "__main__":
    unittest.main()
