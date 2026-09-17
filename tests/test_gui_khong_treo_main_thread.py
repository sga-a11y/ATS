"""GUI khong duoc lam viec NANG tren main thread Tk moi nhip.

Do bang py-spy tren tien trinh that (15/09, PID 9148, 799 thread): 6/6 mau MainThread deu ket o
    _recent_battle_end -> in_combat -> account_status -> party_agi_report -> _refresh -> mainloop
Voi 798 thread ngoi tranh GIL thi `account_status` bo, GUI "not responding".

`gui.py` da tung bi va da tung sua dung kieu nay mot lan (10/09, ghi trong chinh `_refresh`:
"Do bang py-spy tren tien trinh that: 15/15 mau MainThread deu ket trong `account_status` goi tu
`_refresh`") - lan do ho cho party KHONG hien thi dung cache, nhung party DANG XEM van tinh moi
nhip. Bai nay giu cho ca hai duong deu co cache.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
        return fh.read()


class TestAgiReportCoCache(unittest.TestCase):
    def test_MAIN_THREAD_khong_goi_party_agi_report(self):
        """Cache theo thoi gian van KHONG DU: ban than ham do qua cham khi 700 thread tranh GIL,
        nen chi can chay MOT LAN tren main thread la GUI khung lai.

        Do py-spy (PID 9472, 698 thread): 3/5 mau MainThread ket o `account_status` <-
        `party_agi_report` <- `_refresh`, DU DA CO cache 5 giay."""
        s = _src()
        i = s.find("def _refresh(self)")
        j = s.find(chr(10) + "    def ", i + 10)
        self.assertNotIn("ctrl.party_agi_report(", s[i:j],
                         "van tinh tren main thread -> GUI treo")

    def test_co_THREAD_NEN_tinh_thay(self):
        s = _src()
        self.assertIn("def _agi_worker(self)", s, "khong co thread nen -> ai tinh?")
        i = s.find("def _agi_worker(self)")
        j = s.find(chr(10) + "    def ", i + 10)
        self.assertIn("ctrl.party_agi_report(", s[i:j])

    def test_thread_nen_LOI_khong_chet(self):
        s = _src()
        i = s.find("def _agi_worker(self)")
        j = s.find(chr(10) + "    def ", i + 10)
        self.assertIn("except Exception", s[i:j], "loi cham canh bao ma giet ca thread")

    def test_han_cache_du_dai_de_bot_tai(self):
        s = _src()
        m = re.search(r"_AGI_XEM_SEC\s*=\s*([\d.]+)", s)
        self.assertIsNotNone(m, "mat hang _AGI_XEM_SEC")
        self.assertGreaterEqual(float(m.group(1)), 3.0,
                                "cache ngan qua -> van goi account_status gan nhu moi nhip")

    def test_van_lam_moi_du_nhanh_de_user_thay_doi(self):
        s = _src()
        m = re.search(r"_AGI_XEM_SEC\s*=\s*([\d.]+)", s)
        self.assertLessEqual(float(m.group(1)), 10.0, "cache qua lau -> cham canh bao dung im")

    def test_party_KHONG_xem_van_cache_lau_hon(self):
        s = _src()
        m1 = re.search(r"_AGI_XEM_SEC\s*=\s*([\d.]+)", s)
        m2 = re.search(r"_AGI_CACHE_SEC\s*=\s*([\d.]+)", s)
        self.assertLess(float(m1.group(1)), float(m2.group(1)),
                        "party khong hien thi phai cache LAU hon party dang xem")


class TestKhongVE_LAI_KHI_KHONG_DOI(unittest.TestCase):
    """`_refresh` chay moi giay cho CA 54 party; moi `configure` la mot lenh Tk tren main thread.

    Do py-spy (PID 9472, 698 thread): 2/5 mau MainThread ket o `pack_configure` / `_configure`
    trong `_refresh`. Gan nhu moi nhip khong co gi doi, nen phan lon so lenh do la vo ich.
    """

    def test_co_helper_chi_ve_khi_doi(self):
        s = _src()
        self.assertIn("def _cfg(self, w, **kw)", s, "khong co helper -> ve lai moi giay")

    def test_helper_bo_qua_gia_tri_KHONG_DOI(self):
        s = _src()
        i = s.find("def _cfg(self, w, **kw)")
        j = s.find(chr(10) + "    def ", i + 10)
        than = s[i:j]
        self.assertIn("if not _moi:", than, "van goi configure du khong doi gi")
        self.assertIn("return", than)

    def test_cac_nut_trong_refresh_dung_helper(self):
        s = _src()
        i = s.find("def _refresh(self)")
        j = s.find(chr(10) + "    def ", i + 10)
        than = s[i:j]
        self.assertNotIn("nbtn.configure(", than, "nut Chu y van ve lai moi giay")
        self.assertNotIn("agi_btn.configure(", than, "nut AGI van ve lai moi giay")
        self.assertIn("self._cfg(", than)

    def test_widget_khong_luu_duoc_cache_thi_VAN_VE(self):
        """Khong duoc vi toi uu ma bo qua viec ve - thieu mau canh bao la user khong thay."""
        s = _src()
        i = s.find("def _cfg(self, w, **kw)")
        j = s.find(chr(10) + "    def ", i + 10)
        self.assertIn("w.configure(**kw)", s[i:j])


if __name__ == "__main__":
    unittest.main()
