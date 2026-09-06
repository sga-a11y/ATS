"""CACHE TUI DO + TIEN TRANG (user 06/09).

Tui do: "de xem lai khi offline". Tien trang: "de xem va nho lai trong do dang co gi" - de sau
nay mo rong soi lo check ca do trong kho.

HAI RANG BUOC KHONG DUOC PHA:
  1. Ban cache la CHI XEM. Truoc day `bag_info` tu choi cache han voi ly do dung: "doc file ra thi
     vua sai vua nguy hiem (bam phan giai theo so cu la mat nham do)". Gio cache nhung phai tra
     `live=False` va UI chi duoc de lai MOT nut "Tu cat vao tien trang" (nut do ghi accounts.json,
     khong gui goi nao len server).
  2. Server KHONG BAO GIO tu gui tien trang. Bot chi thay kho dung luc di NPC Trac Quan mo kho
     (S:030-001 ca kho, S:030-004 tung o). Nen cache kho = anh chup LAN MO KHO GAN NHAT, va acc
     chua tung mo kho thi COI NHU KHONG CO GI (user chot: khong lam nut "doc lai kho").
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as CL  # noqa: E402

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R  # noqa: E402


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._goc = CL._skill_cache_path
        CL._skill_cache_path = lambda: os.path.join(self.d, "c.json")
        CL._skill_cache_sig.clear()

    def tearDown(self):
        CL._skill_cache_path = self._goc
        CL._skill_cache_sig.clear()
        R.account_clients.pop("zz", None)


class TestGhiVaDoc(_Base):
    def test_tui_di_ve_nguyen_ven(self):
        CL.save_bag_cache("zz", {"slots": {"3": [0x1234, 7]}, "cap": 160, "used": 1})
        tui, ts = CL.load_bag_cache("zz")
        self.assertEqual(tui["slots"]["3"], [0x1234, 7])
        self.assertEqual(tui["cap"], 160)
        self.assertGreater(ts, 0)

    def test_KHONG_ghi_de_khoa_khac_cua_acc(self):
        """Cung file voi cache skill/point/inn - ghi tui khong duoc lam mat chung."""
        CL.save_point_cache("zz", {"left": 5, "stats": []})
        CL.save_bag_cache("zz", {"slots": {"1": [1, 1]}})
        CL.save_bank_cache("zz", {"slots": {"0": [2, 2]}})
        self.assertIsNotNone(CL.load_point_cache("zz")[0])
        self.assertIsNotNone(CL.load_bag_cache("zz")[0])
        self.assertIsNotNone(CL.load_bank_cache("zz")[0])

    def test_noi_dung_KHONG_doi_thi_KHONG_ghi_lai(self):
        self.assertTrue(CL.save_bag_cache("zz", {"slots": {"1": [1, 1]}}))
        self.assertFalse(CL.save_bag_cache("zz", {"slots": {"1": [1, 1]}}))

    def test_chua_co_gi_thi_tra_None(self):
        self.assertEqual(CL.load_bag_cache("zz"), (None, 0))
        self.assertEqual(CL.load_bank_cache("zz"), (None, 0))


class TestBankCountsChoSoiLo(_Base):
    def test_cong_tong_theo_tid(self):
        CL.save_bank_cache("zz", {"slots": {"0": [0x3ac6, 99], "1": [0x3ac6, 1], "2": [0x4e43, 3]}})
        self.assertEqual(CL.bank_counts_cache("zz"), {0x3ac6: 100, 0x4e43: 3})

    def test_cung_hinh_dang_voi_bag_counts(self):
        """Soi lo dang doc `c.bag_counts` = {tid:int} - nguon thu hai phai ghep vao duoc ngay."""
        CL.save_bank_cache("zz", {"slots": {"0": [7, 2]}})
        dem = CL.bank_counts_cache("zz")
        self.assertTrue(all(isinstance(k, int) and isinstance(v, int) for k, v in dem.items()))

    def test_chua_mo_kho_lan_nao_thi_COI_NHU_KHONG_CO_GI(self):
        self.assertEqual(CL.bank_counts_cache("zz"), {})


class TestBagInfoTraCacheKhiAccTat(_Base):
    def test_acc_tat_co_cache_thi_tra_kem_live_False(self):
        CL.save_bag_cache("zz", {"slots": {"1": [0x3ac6, 5]}, "cap": 160, "used": 1})
        info = R.bag_info("zz")
        self.assertFalse(info["live"])
        self.assertEqual(info["cap"], 160)
        self.assertEqual([s["id"] for s in info["slots"]], [0x3ac6])

    def test_acc_tat_KHONG_co_cache_thi_van_tra_rong(self):
        self.assertEqual(R.bag_info("zz"), {})

    def test_ban_cache_KHONG_bam_duoc_nut(self):
        """Rang buoc so 1: acc tat thi moi lenh tui do deu bi tu choi."""
        CL.save_bag_cache("zz", {"slots": {"1": [0x3ac6, 5]}})
        for act in ("use", "equip", "decompose", "discard", "fashion"):
            self.assertTrue(R.bag_cmd("zz", act, 1).startswith("False:"), act)

    def test_co_bank_van_tinh_duoc_khi_khong_co_client(self):
        """Nut "Tu cat vao tien trang" la nut DUY NHAT con lai -> co `bank` phai dung."""
        CL.save_bag_cache("zz", {"slots": {"1": [0x3ac6, 5]}})
        self.assertIn("bank", R.bag_info("zz")["slots"][0])


class TestBankInfo(_Base):
    def test_tra_do_trong_kho(self):
        CL.save_bank_cache("zz", {"slots": {"0": [0x3ac6, 99]}})
        info = R.bank_info("zz")
        self.assertEqual([(s["id"], s["cnt"]) for s in info["slots"]], [(0x3ac6, 99)])
        self.assertFalse(info["live"], "kho luon la anh chup, khong bao gio 'live'")

    def test_chua_mo_kho_thi_rong(self):
        self.assertEqual(R.bank_info("zz"), {})


class TestGhiNguyenTu(_Base):
    """Ghi de nguyen file JSON kieu `open(path,"w")` = CAT TRANG truoc, ghi sau.

    Do bang tay 06/09 luc bot dang chay 90 acc: `account_skills_cache.json` nhay
    8KB -> 80KB -> 56KB trong vai giay. Ai doc trung khe do thi `json.load` nem loi -> coi nhu
    "chua co cache"; sap nguon dung luc do thi mat sach ca file. Them cache tui do (to hon nhieu,
    90 acc) lam khe do rong ra.
    """

    def test_khong_con_ghi_de_thang_vao_file(self):
        src = _doc("bot", "client.py")
        i = src.find("def _skill_cache_path(")
        self.assertNotIn('with open(path, "w"', src[i:],
                         "van con ghi de thang -> doc gia co the trung ban do dang")

    def test_ghi_qua_file_tam_roi_os_replace(self):
        src = _doc("bot", "client.py")
        i = src.find("def _ghi_json_an_toan(")
        self.assertGreater(i, 0)
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        self.assertIn("os.replace", than)

    def test_file_cu_con_nguyen_khi_ghi_hong(self):
        import json
        CL.save_bag_cache("zz", {"slots": {"1": [1, 1]}})
        p = CL._skill_cache_path()
        cu = io.open(p, encoding="utf-8").read()
        with mock.patch("json.dump", side_effect=OSError("het cho")):
            with self.assertRaises(Exception):
                CL._ghi_json_an_toan(p, {"hong": True})
        self.assertEqual(io.open(p, encoding="utf-8").read(), cu, "file cu bi pha khi ghi hong")
        self.assertIsNotNone(json.loads(cu))

    def test_khong_de_lai_rac_file_tam(self):
        import os as _os
        p = CL._skill_cache_path()
        CL._ghi_json_an_toan(p, {"a": 1})
        self.assertEqual([f for f in _os.listdir(self.d) if ".tam" in f], [])


class TestNhipGhi(unittest.TestCase):
    def test_tui_do_CHI_ghi_o_LOGIN_va_luc_DONG_acc(self):
        """User chot 06/09: "trong luc chay thi chi dung cache tien trang, cache tui do ghi lien
        tuc cung thua". Ban cache chi de XEM khi acc DA TAT -> chi ban ghi CUOI CUNG co nguoi doc.

        Do 06/09: cache tui chiem 91.5% file (596/651 KB); du da tiet che 120s thi 246 acc van
        thanh ~20 luot ghi/phut, ma MOI luot ghi LAI CA FILE -> 6/12 lan doc trung luc dang ghi.
        """
        src = _doc("bot", "client.py")
        # MOC 1: snapshot day 0x17 sub05 (login)
        i = src.find('INVENTORY (TUI THAT): S2C 0x17 sub=0500')
        self.assertGreater(i, 0)
        self.assertIn("self._ghi_cache_tui()", src[i:i + 2000], "login khong ghi cache")
        # MOC 2: dong acc
        j = src.find("    def close(self):")
        self.assertGreater(j, 0)
        self.assertIn("self._ghi_cache_tui()", src[j:j + 1500], "dong acc khong chot cache")
        # KHONG ghi khi nhat/dung tung mon (0x17 sub08)
        k = src.find('NHAN/DROP ITEM 1 SLOT: S2C 0x17 sub=0800')
        self.assertGreater(k, 0)
        self.assertNotIn("_ghi_cache_tui", src[k:k + 1200],
                         "van ghi cache moi lan nhat do -> ghi lai ca file lien tuc")
        self.assertNotIn("BAG_CACHE_NHIP_SEC", src, "khong con tiet che -> hang so phai bo")

    def test_moi_lan_KHO_doi_deu_ghi(self):
        """Kho chi mo luc di cat do - hiem, khong can tiet che, va bo lo mot lan la mat ca lan mo."""
        src = _doc("bot", "client.py")
        i = src.find("def _doc_kho_tien_trang(")
        than = src[i:src.find("\n    def ", i + 10)]
        self.assertIn("self._ghi_cache_kho()", than)


class TestGiaoDienChiXem(unittest.TestCase):
    def setUp(self):
        self.gui = _doc("gui.py")

    def test_co_tab_tien_trang_va_KHONG_nhet_vao_TAB_NAMES(self):
        """TAB_NAMES la luat PHAN LOAI ITEM cua client (matches_tab) - nhet kho vao la sai luat."""
        self.assertIn("TAB_TIEN_TRANG = 5", self.gui)
        self.assertIn('[(TAB_TIEN_TRANG, "Tiền trang")]', self.gui)
        self.assertNotIn("TIEN_TRANG", _doc("bot", "bag_tabs.py"))

    def test_acc_tat_chi_con_nut_tu_cat(self):
        i = self.gui.find("if not self._live:", self.gui.find("def _show_actions("))
        khoi = self.gui[i:i + 1200]
        self.assertIn("Tự cất vào tiền trang", khoi)
        self.assertIn("return", khoi)
        for nut in ("Phân giải", "Trang bị", "Sử dụng"):
            self.assertNotIn(nut, khoi, "nut '%s' con song o ban cache" % nut)

    def test_tab_kho_khong_co_nut_nao(self):
        i = self.gui.find("if self._tab == TAB_TIEN_TRANG:", self.gui.find("def _show_actions("))
        self.assertGreater(i, 0)
        self.assertIn("chỉ xem", self.gui[i:i + 400])


class TestHangNutTrenKhongCatMatNutMuaSlot(_Base):
    """Them tab thu 5 lam hang tren dai ra -> nut "Mua slot" bi day ra ngoai va CUT MAT
    (user bao 06/09: chi con thay "Mua :"). Nut do la thu DUY NHAT khong doan duoc bang mat."""

    def setUp(self):
        super().setUp()
        try:
            import tkinter as tk
        except Exception:
            self.skipTest("khong co Tk")
        CL.save_bag_cache("zz", {"slots": {"1": [0x4e43, 1]}, "cap": 180, "used": 138})
        CL.save_bank_cache("zz", {"slots": {"0": [0x3ac6, 99]}})
        import gui
        self.gui = gui
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest("khong mo duoc man hinh")
        self.root.geometry("100x100+0+0")
        self.dlg = gui.BagDialog(self.root, "zz", None)

    def tearDown(self):
        try:
            self.dlg._alive = False      # dung vong _watch truoc khi go cua so
            self.dlg.destroy()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        super().tearDown()

    def test_acc_tat_thi_KHONG_lap_thread_hoi_gia_slot(self):
        """Shim `_TuiCache` khong co `query_bag_slot_price` - lap thread la nem loi trong thread
        phu va dam vao Tk tu ngoai main thread."""
        self.assertIsNone(self.dlg._price_async())

    def test_nut_mua_slot_nam_TRON_trong_cua_so(self):
        # Chu dai nhat co the co tren nut do (gia 4 chu so).
        self.dlg.btn_buy.configure(text="Mua slot (1200 vàng)")
        self.dlg.update()
        self.dlg.update_idletasks()
        phai = self.dlg.btn_buy.winfo_x() + self.dlg.btn_buy.winfo_width()
        self.assertLessEqual(phai, self.dlg.winfo_width(),
                             "nut Mua slot tran ra ngoai cua so")
        self.assertGreater(self.dlg.btn_buy.winfo_width(), 20, "nut Mua slot bi bop mat")

    def test_du_cho_cho_CA_5_tab(self):
        self.dlg.update()
        self.dlg.update_idletasks()
        for tab, b in self.dlg._tab_btns.items():
            self.assertLessEqual(b.winfo_x() + b.winfo_width(), self.dlg.winfo_width(),
                                 "tab %s tran ra ngoai" % tab)

    def test_moc_anh_chup_o_TIEU_DE_chu_khong_chen_hang_nut(self):
        self.assertIn("chỉ xem", self.dlg.title())
        self.assertIn("ảnh chụp", self.dlg.title())


class TestAPKGiongPC(unittest.TestCase):
    def setUp(self):
        self.kt = _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                       "MainActivity.kt")

    def test_co_tab_tien_trang(self):
        self.assertIn("TAB_TIEN_TRANG = 5", self.kt)
        self.assertIn('TAB_TIEN_TRANG to "Tiền trang"', self.kt)

    def test_doc_co_live_va_ts(self):
        self.assertIn('optBoolean("live"', self.kt)
        self.assertIn('optLong("ts"', self.kt)

    def test_khong_live_thi_chi_con_nut_cat(self):
        i = self.kt.find("if (!live) {")
        self.assertGreater(i, 0, "APK khong khoa nut khi xem ban cache")
        khoi = self.kt[i:i + 700]
        khoi = khoi[:khoi.find("return@Row")]   # het nhanh !live la thoi, duoi la nhanh live
        self.assertIn("onBank", khoi)
        for nut in ("onDismantle", "onDiscard", "onEquip"):
            self.assertNotIn(nut, khoi)

    def test_service_co_cau_noi_kho(self):
        self.assertIn("fun bankInfoJson(",
                      _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                           "BotForegroundService.kt"))

    def test_python_apk_giong_PC(self):
        for f in ("client.py", "run_party_digioi.py"):
            apk = _doc("android", "app", "src", "main", "python", "train_bot", f)
            self.assertIn("bank_counts_cache" if f == "client.py" else "def bank_info(", apk)


if __name__ == "__main__":
    unittest.main()
