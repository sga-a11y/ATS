# -*- coding: utf-8 -*-
"""LO HOANG KIM (game mo 03/09) DUNG CHUNG config tab voi lo thuong.

Crack client 03/09:
  - `gamedata/Data/FurnaceSlot_C.dat` (1905 ban ghi x 15 byte) = POOL item cua lo, chia dung
    3 nhom: kind1 Vo Tuong 415 | kind2 Trang Bi 713 | kind3 Chuyen Sinh 777 - khop chan chan
    voi furnace_pool.json. KHONG co pool rieng cho hoang kim -> tab gold lay tu chinh 3 nhom do.
  - `gamedata/Data/FurnaceSelect_C.dat` (42 dong x 11 byte): lo thuong (kind 1/2/5) moi tab 6 muc
    sample 4050..50; hoang kim (3/4/6) 8 muc, sample xuong toi 10, awardPro don ve pham cao.
  - `UI_UIFurnace.lua`: tab gold nhan them goldStoreRate (x2 gia).

=> Khac biet nam o XAC SUAT PHAM va GIA, KHONG phai danh sach item. User chot 03/09: "neu chung
list thi co khi ko can lam 3 tab moi, moi tab cho ca 2 lo luon cung dc" -> moi tab config phu
CA HAI lo.
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than():
    s = _doc("bot", "client.py")
    i = s.find("def process_furnace(")
    return s[i:s.find("def decompose_slot(", i)]


class TestChungConfigChoCaHaiLo(unittest.TestCase):
    def test_co_bang_map_tab_sang_kind_gold(self):
        s = _doc("bot", "client.py")
        self.assertIn('FURNACE_TAB_KIND_GOLD = {"vo_tuong": 3, "trang_bi": 4, "chuyen_sinh": 6}', s)

    def test_duyet_ca_hai_lo_trong_mot_tab(self):
        t = _than()
        self.assertIn('_cap.append((_t, _k, _k))', t, "phai co lo thuong")
        self.assertIn('_cap.append((_t, _k, _kg))', t, "phai co lo hoang kim")
        # config lay theo TEN TAB (chung), khong phai theo kind
        self.assertIn('tcfg = (cfg or {}).get(tab_name) or {}', t)

    def test_luat_mua_bam_theo_NHOM_khong_phai_kind_goi(self):
        """kind cua goi o lo gold la 3/4/6 -> neu luat mua van so kind == 2 / == 5 thi trang bi va
        chuyen sinh ben hoang kim se mat het gioi han "da co trong tui thi thoi"."""
        t = _than()
        self.assertIn("if nhom == 2 and _bag >= 1:", t)
        self.assertIn("elif nhom == 5:", t)
        self.assertIn('if nhom == 5 else None', t)
        self.assertNotIn("if kind == 2 ", t)
        self.assertNotIn("elif kind == 5:", t)

    def test_gui_lenh_mua_va_co_da_mua_dung_KIND_THAT(self):
        """Mua/flag phai dung kind cua goi (3/4/6), khong duoc thay bang nhom."""
        t = _than()
        self.assertIn("self.buy_furnace_item(kind, it[\"index\"], it[\"id\"])", t)
        self.assertIn('for it in tabs.get(kind, [])', t)

    def test_co_co_gold_de_UI_phan_biet(self):
        t = _than()
        self.assertIn('"gold": _gold', t)
        self.assertIn('_ten_tab = tab_name + " HOANG KIM" if _gold else tab_name', t)

    def test_flag_da_mua_co_du_6_kind(self):
        s = _doc("bot", "client.py")
        self.assertIn("FURNACE_BOUGHT_FLAG_BASE = {1: 1518, 2: 1526, 5: 7257, 3: 7067, 4: 7075, 6: 7265}", s)


class TestPoolChungThatSu(unittest.TestCase):
    def test_furnace_pool_json_dung_3_nhom_va_dung_so_luong(self):
        """Neu game doi pool (them nhom thu 4) thi luat "dung chung list" khong con dung."""
        import json
        with io.open(os.path.join(ROOT, "furnace_pool.json"), encoding="utf-8") as fh:
            pool = json.load(fh)
        self.assertEqual(sorted(pool), ["Chuyen Sinh", "Trang Bi", "Vo Tuong"])
        self.assertEqual(len(pool["Vo Tuong"]), 415)
        self.assertEqual(len(pool["Trang Bi"]), 713)
        self.assertEqual(len(pool["Chuyen Sinh"]), 777)


class TestNhanTabBoChuThuong(unittest.TestCase):
    """User chot 03/09: "the bo chu thuong di nhi, dung cho ca thuong va Hoang kim ma"."""

    def test_pc_bo_chu_thuong(self):
        s = _doc("gui.py")
        self.assertIn('("vo_tuong", "Vo Tuong", "Võ Tướng")', s)
        self.assertIn('("trang_bi", "Trang Bi", "Trang Bị")', s)
        self.assertIn('("chuyen_sinh", "Chuyen Sinh", "Chuyển Sinh")', s)
        self.assertNotIn("Võ Tướng thường", s)
        self.assertNotIn("Trang Bị thường", s)
        self.assertNotIn("Chuyển Sinh thường", s)

    def test_apk_bo_chu_thuong(self):
        s = _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                 "MainActivity.kt")
        self.assertIn('Triple("vo_tuong", "Vo Tuong", "Võ Tướng")', s)
        self.assertNotIn("Võ Tướng thường", s)
        self.assertNotIn("Chuyển Sinh thường", s)

    def test_thong_bao_van_noi_ro_lo_nao(self):
        """Bo chu 'thuong' nhung phai biet item o lo nao - gia hoang kim GAP DOI."""
        s = _doc("gui.py")
        # User chot 03/09: "cho thong bao thi van ghi ro la lo thuong hay lo hoang kim co item"
        # -> lo thuong KHONG duoc de trong (gia hoang kim gap doi, phai phan biet duoc ngay).
        self.assertIn('_lo = " HOÀNG KIM" if it.get("gold") else " thường"', s)
        self.assertIn('soi lò võ tướng{_lo} có', s)
        k = _doc("android", "app", "src", "main", "java", "com", "tsbot", "android",
                 "MainActivity.kt")
        self.assertIn('in listOf("true", "1")) " HOÀNG KIM" else " thường"', k)
        self.assertIn('soi lò võ tướng$lo có', k)


class TestKhongMuaTRUNGO2Lo(unittest.TestCase):
    """User hoi 03/09: "1 Kim toa co ca o lo thuong va lo hoang kim, thi lan do co bi tu mua o
    ca 2 ko, vi truoc do la chua co".

    CO - va do la loi: buy_furnace_item() chi cho ack S:089-002, KHONG cho goi cap nhat tui
    (0x17 sub08). Sang tab hoang kim ngay sau do thi bag_counts VAN 0 -> luat "da co >=1 thi thoi"
    khong chan duoc -> mua lai dung mon vua mua, gia hoang kim GAP DOI.
    """

    def test_co_set_nho_da_mua_trong_luot(self):
        t = _than()
        self.assertIn("_mua_luot = set()", t)

    def test_chan_TRUOC_khi_mua(self):
        t = _than()
        i = t.find('if it["id"] in _mua_luot:')
        self.assertGreater(i, 0)
        self.assertIn("KHONG mua lai", t[i:i + 400])
        self.assertLess(i, t.find("self.buy_furnace_item("), "phai chan TRUOC khi gui lenh mua")

    def test_chi_ghi_nho_khi_mua_THANH_CONG(self):
        t = _than()
        i = t.find("ok = self.buy_furnace_item(")
        doan = t[i:i + 300]
        self.assertIn("if ok:", doan)
        self.assertIn('_mua_luot.add(it["id"])', doan)

    def test_khong_bao_TRUNG_ben_notify(self):
        """Vua tu mua o lo kia roi thi bao tiep chi lam user tuong con thieu."""
        t = _than()
        i = t.find("else:   # notify")
        self.assertIn('if it["id"] in _mua_luot:', t[i:i + 500])


class TestChoTuiCapNhatTruocKhiSangLoKia(unittest.TestCase):
    """User chot 03/09: "mua lo thuong truoc, sang ben hoang kim la phai cap nhat trang thai moi
    cua tui do dung ko" - DUNG.

    `_mua_luot` chi chan mua trung DUNG MON do. Cac luat khac van doc `bag_counts`:
      - trang bi: "da co >=1 trong tui thi thoi"
      - chuyen sinh: K.Toa / Me gioi han 1
    Khong cho tui len thi cac luat do doc SO CU -> quyet dinh sai cho mon KHAC cung tab.
    """

    def test_co_ham_cho_tui(self):
        s = _doc("bot", "client.py")
        self.assertIn("def _cho_tui_cap_nhat(", s)
        i = s.find("def _cho_tui_cap_nhat(")
        than = s[i:i + 900]
        self.assertIn("self.bag_counts.get(int(tid), 0) > int(cu)", than)
        self.assertIn("return False", than, "het gio thi van phai di tiep, khong treo")

    def test_goi_ngay_sau_khi_mua_thanh_cong(self):
        t = _than()
        i = t.find("ok = self.buy_furnace_item(")
        doan = t[i:i + 700]
        self.assertIn("self._cho_tui_cap_nhat(", doan)
        self.assertIn("_bag_truoc", doan)

    def test_doc_so_luong_TRUOC_khi_gui_lenh_mua(self):
        """Doc sau khi mua thi co the da la so MOI -> cho vo nghia."""
        t = _than()
        i_truoc = t.find("_bag_truoc = self.bag_counts.get(")
        i_mua = t.find("ok = self.buy_furnace_item(")
        self.assertGreater(i_truoc, 0)
        self.assertLess(i_truoc, i_mua)


if __name__ == "__main__":
    unittest.main()
