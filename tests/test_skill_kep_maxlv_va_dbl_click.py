"""Bang tu nang skill: KEP cap dich ve maxLv, va double-click trong cay = them vao bang.

User chot 04/09:
  - "dien muc level mong muon ma cao hon max thi co sao ko" -> engine
    (`client._skill_co_the_nang`) DA cat ve `maxLv` truoc khi tinh gia va gui goi, nen KHONG hai.
  - "cat deo dau, t van dien lv 110 vao dc kia" -> nhung GUI thi khong chan gi: o van cho go 110
    va bang hien "den cap 110" trong khi bot chi nang toi 10. So hien thi noi doi -> phai kep o
    ngay tren GUI.
  - "click double vao 1 skill thi neu skill do chua max, m add no vao auto o duoi luon nhe".

Luu y: `to=` cua ttk.Spinbox CHI chan mui ten len/xuong - GO TAY van vuot qua duoc. Nen khong
duoc coi `to=` la da chan.
"""
from __future__ import annotations

import io
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _gui():
    with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
        return fh.read()


def _client():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


def _than(src, ten, tu_class="class SkillDialog"):
    """Than mot method. PHAI neo tu `class SkillDialog`: `PointDialog` (nam TRUOC trong file) co
    method TRUNG TEN (`_them_dong`, `_luu`, `_cap_nhat_done`...) -> `find` tho se bat nham ham cua
    bang Point. Da dinh bay nay nhieu lan trong repo."""
    goc = src.find(tu_class) if tu_class else 0
    assert goc >= 0, "khong tim thay %s" % tu_class
    i = src.find("def %s(" % ten, goc)
    assert i > 0, "khong tim thay %s trong %s" % (ten, tu_class)
    return src[i:src.find("\n    def ", i + 10)]


class TestDuLieuMaxLv(unittest.TestCase):
    def test_moi_skill_co_cay_deu_co_maxLv(self):
        """Thieu maxLv thi nhanh kep bi bo qua (`if not _mx: return`) -> lot so bua."""
        with io.open(os.path.join(ROOT, "skills_data.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        skills = d.get("skills") if isinstance(d, dict) and "skills" in d else d
        thieu = [k for k, v in skills.items()
                 if isinstance(v, dict) and v.get("tree") and not int(v.get("maxLv") or 0)]
        self.assertEqual(thieu, [], "co skill khong khai bao maxLv")


class TestEngineVanCat(unittest.TestCase):
    """Lop chan cuoi cung - GUI co bi qua mat thi engine van khong gui cap qua tran."""

    def test_skill_co_the_nang_cat_ve_maxLv(self):
        t = _than(_client(), "_skill_co_the_nang", tu_class=None)
        self.assertIn('max_lv = int(info.get("maxLv") or 0)', t)
        self.assertIn("if max_lv and den_cap > max_lv:", t)
        self.assertIn("den_cap = max_lv", t)

    def test_goi_gui_di_dung_cap_DA_CAT(self):
        """`nang_skill_char` phai dong goi bang `cap_that` (tra ve tu ham cat), khong phai
        `den_cap` goc cua rule."""
        t = _than(_client(), "nang_skill_char", tu_class=None)
        self.assertIn("gia, cap_that = ket_qua", t)
        self.assertIn('goi = b"".join(struct.pack("<HB", sid, cap) for sid, cap, _g in chon)', t)
        self.assertIn("chon.append((sid, cap_that, gia))", t)


class TestGuiKepCap(unittest.TestCase):
    def setUp(self):
        self.src = _gui()

    def test_o_nhap_kep_theo_maxLv_cua_skill_dang_chon(self):
        t = _than(self.src, "_them_dong")
        self.assertIn("def _kep_cap(", t)
        self.assertIn('.get("maxLv") or 0)', t)
        self.assertIn("var_cap.set(str(_mx))", t, "go qua tran ma khong keo ve maxLv")

    def test_kep_chay_khi_DOI_SKILL_va_khi_GO_SO(self):
        """Doi skill sang cai co maxLv thap hon ma khong kep lai -> so cu treo lai qua tran."""
        t = _than(self.src, "_them_dong")
        i = t.find("def _kiem_done(")
        self.assertGreater(i, 0)
        self.assertIn("_kep_cap()", t[i:i + 200], "trace write khong goi _kep_cap")
        self.assertIn('var.trace_add("write", _kiem_done)', t)
        self.assertIn('var_cap.trace_add("write", _kiem_done)', t)

    def test_kep_ca_luc_TAO_DONG(self):
        """Rule cu luu tu truoc (hoac sua tay accounts.json) co the mang so qua tran."""
        t = _than(self.src, "_them_dong")
        i = t.rfind("_kep_cap()")
        self.assertGreater(i, 0)
        self.assertIn("self.rules.append(rec)", t[:i], "phai kep sau khi dong da vao self.rules")

    def test_hien_tran_cho_user_thay(self):
        t = _than(self.src, "_them_dong")
        self.assertIn('_lbl_max.configure(text="/%d" % _mx)', t,
                      "khong hien maxLv thi user khong biet tran la bao nhieu")

    def test_luu_van_kep_lan_cuoi(self):
        i = self.src.find('settings["skill"] = cfg')
        self.assertGreater(i, 0)
        khoi = self.src[max(0, i - 900):i]
        self.assertIn("if _mx and cap > _mx:", khoi, "luu ma khong kep -> ghi so noi doi vao file")

    def test_nut_hoc_nang_ngay_cung_kep(self):
        t = _than(self.src, "_nang_tay")
        self.assertIn("if _mx and cap > _mx:", t)
        self.assertIn("self.var_cap_tay.set(str(cap))", t, "kep xong phai hien lai so that")


class TestDoubleClickThemVaoBang(unittest.TestCase):
    def setUp(self):
        self.src = _gui()

    def test_co_bind_double_click_tren_cay(self):
        self.assertIn('_tv.bind("<Double-1>", self._them_tu_cay_dbl, add="+")', self.src)

    def test_skill_DA_MAX_thi_khong_them(self):
        t = _than(self.src, "_them_tu_cay_dbl")
        self.assertIn("self._da_max(sid)", t)

    def test_da_co_trong_bang_thi_khong_them_trung(self):
        """Double-click cung la thao tac mo/dong node cay -> rat de bam nhieu lan."""
        t = _than(self.src, "_them_tu_cay_dbl")
        self.assertIn("self._sid_trong_bang()", t)

    def test_double_click_KHONG_bat_popup(self):
        """Cham vao skill da max la chuyen binh thuong khi duyet cay - bat popup moi lan la phien.
        Nut 'Them vao bang duoi' thi VAN bao (thao tac co chu dich)."""
        t = _than(self.src, "_them_tu_cay_dbl")
        self.assertNotIn("showinfo", t)
        self.assertIn("im_lang=True", t, "chua chon gi ma popup 'Chon mot skill' la sai")
        self.assertIn("showinfo", _than(self.src, "_them_tu_cay"))

    def test_them_dung_maxLv_lam_cap_dich(self):
        for ten in ("_them_tu_cay", "_them_tu_cay_dbl"):
            t = _than(self.src, ten)
            self.assertIn('self._them_dong(sid, int(info.get("maxLv") or 1))', t)

    def test_ham_da_max_doc_cap_hien_tai(self):
        t = _than(self.src, "_da_max")
        self.assertIn('.get("maxLv") or 0)', t)
        self.assertIn("self.cap.get(int(sid), 0)", t)


if __name__ == "__main__":
    unittest.main()
