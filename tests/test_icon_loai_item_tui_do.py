"""ICON LOAI ITEM trong tui do (gui.py).

User 21/09: "mo tui do thay tat ca cac item chi co ten lam tim item muon tim cung kho qua, t muon
them 1 icon the hien loai item vao do o goc cho de phan biet ... muon tim loai nao thi t tim khu
nao co nhieu icon loai do roi t moi nhin ten, se tim nhanh hon".

Chot: thuoc HP+SP CHUNG mot icon · cuon goi pet · item HOI TRUNG THANH (con ngua) · 6 icon cho 6
vi tri mac. Bo do ngua va nguyen lieu ("game rat it do nay" / "ko can").

File nay ep hai thu:
  1. NHAN DANG bang DU LIEU GAME, khong doan theo ten (ten trong .dat co ca ky tu rac).
  2. KHONG DUNG EMOJI - font mac dinh cua Tk tren Windows khong co, hien O VUONG (user bao 25/08,
     chinh vi vay `_bag_icon` cu cung phai ve tay tung pixel).
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than_ham(src, dau):
    """Than cua ham/method `dau`: cat tai DONG DAU TIEN o cot 0 hoac cung muc thut `def`.

    Cat theo `\\ndef ` thoi la chua du - sau ham co the la BIEN cap module (vd `_PICK_GROUP`), luc
    do than bi keo dai sang ca cai do va phep kiem "khong co emoji" bat nham dau sao trong bien.
    """
    i = src.find(dau)
    if i < 0:
        return ""
    thut = len(dau) - len(dau.lstrip())
    dong = src[i:].split("\n")
    ra = [dong[0]]
    for d in dong[1:]:
        if d.strip() and (len(d) - len(d.lstrip())) <= thut:
            break
        ra.append(d)
    return "\n".join(ra)


class TestNguonPhanLoai(unittest.TestCase):
    """Moi loai phai suy tu mot truong CU THE cua game."""

    @classmethod
    def setUpClass(cls):
        cls.db = json.load(io.open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8"))

    def test_item_hoi_trung_thanh_khop_TRON_VEN_voi_kd_49(self):
        """`kd == 49` duoc chon lam dau hieu vi no trung KHIT voi thuoc tinh 64 (= 忠誠, tra o
        `_lua_dec/Data/ItemData.lua:479`). Lech mot mon la icon gan sai."""
        k49 = [v for v in self.db.values()
               if isinstance(v, dict) and int(v.get("kd") or 0) == 49]
        co64 = [v for v in self.db.values()
                if isinstance(v, dict) and 64 in (v.get("a1k"), v.get("a2k"))]
        self.assertTrue(k49, "mat nhom item hoi trung thanh")
        self.assertEqual(len(k49), len(co64),
                         "kd=49 khong con trung khit voi thuoc tinh trung thanh -> doi dau hieu")
        self.assertTrue(all(64 in (v.get("a1k"), v.get("a2k")) for v in k49))

    def test_sau_vi_tri_mac_deu_co_item(self):
        """ft 1..6 = Mu/Ao/Vu khi/Ho uyen/Giay/Dac biet (`EItemFitType` cua client)."""
        for ft in range(1, 7):
            n = sum(1 for v in self.db.values()
                    if isinstance(v, dict) and int(v.get("ft") or 0) == ft)
            self.assertGreater(n, 0, "vi tri mac %d khong co item nao -> icon thua" % ft)

    def test_cuon_goi_pet_doc_tu_file_rieng(self):
        d = json.load(io.open(os.path.join(ROOT, "pet_scrolls.json"), encoding="utf-8"))
        tid = [k for k in d if isinstance(k, str) and k.startswith("0x")]
        self.assertGreater(len(tid), 100, "pet_scrolls.json rong -> cuon khong co icon")


class TestLuatNhanDang(unittest.TestCase):
    def setUp(self):
        self.than = _than_ham(_doc("gui.py"), "    def _loai_item(self, tid, d):")
        self.assertTrue(self.than, "mat ham `_loai_item`")

    def test_dung_du_lieu_chu_khong_doan_ten(self):
        for truong in ('d.get("ft")', 'd.get("kd")', 'd.get("hp")', 'd.get("sp")'):
            self.assertIn(truong, self.than)
        self.assertNotIn('"name"', self.than, "doan loai theo TEN -> sai som muon")

    def test_TRANG_BI_xet_TRUOC_thuoc(self):
        """Mot mon trang bi co the cong HP/SP (vd ao cong HP) - luc do no van la TRANG BI."""
        self.assertLess(self.than.find('d.get("ft")'), self.than.find('d.get("hp")'),
                        "xet thuoc truoc -> ao cong HP bi gan icon lo thuoc")

    def test_HP_va_SP_CHUNG_mot_icon(self):
        """User chot: "thuoc HP va SP chi can lam chung 1 icon thuoc"."""
        i = self.than.find('d.get("hp")')
        self.assertIn('"thuoc"', self.than[i:i + 200])
        self.assertNotIn('"thuoc_sp"', self.than)

    def test_khong_gan_icon_cho_loai_da_bo(self):
        """User: do ngua (kd=81) va nguyen lieu -> "ko can"."""
        self.assertNotIn("81", self.than)


class TestVeIconKhongDungEmoji(unittest.TestCase):
    def setUp(self):
        self.src = _doc("gui.py")
        self.than = _than_ham(self.src, "def _icon_loai(widget, loai):")
        self.assertTrue(self.than, "mat ham `_icon_loai`")

    def test_ve_bang_PhotoImage_pixel(self):
        self.assertIn("tk.PhotoImage", self.than)
        self.assertIn("transparency_set", self.than, "khong co nen trong suot -> icon co khoi vuong")

    def test_KHONG_co_emoji_trong_ma_icon(self):
        """Font mac dinh Tk tren Windows khong co emoji -> O VUONG (user bao 25/08)."""
        for ch in self.than:
            self.assertLess(ord(ch), 0x2500,
                            "co ky tu ve/emoji U+%04X - font Windows khong ve duoc" % ord(ch))

    def test_du_CHIN_loai(self):
        for loai in ("thuoc", "cuon", "ngua", "eq1", "eq2", "eq3", "eq4", "eq5", "eq6"):
            self.assertIn('== "%s"' % loai, self.than, "thieu hinh cho loai %r" % loai)

    def test_moi_loai_mot_TONG_MAU_rieng(self):
        """12x12 pixel thi HINH kho ta chi tiet - mau moi la thu nhin loang qua da tach duoc."""
        i = self.src.find("_LOAI_MAU = {")
        bang = self.src[i:self.src.find("}", i)]
        mau = re.findall(r'"(#[0-9a-fA-F]{6})"', bang)
        vien = mau[0::3]
        self.assertEqual(len(vien), len(set(vien)), "hai loai dung chung mau vien -> nhin lan")

    def test_GIU_THAM_CHIEU_anh(self):
        """Tk khong giu ho PhotoImage - bi thu gom rac la o thanh TRONG TRON (bai hoc cua
        `_bag_icon` ngay tren)."""
        self.assertIn("_LOAI_ICON[key] = img", self.than)


class TestNoiVaoO(unittest.TestCase):
    def setUp(self):
        self.than = _than_ham(_doc("gui.py"), "    def _cell(self, i, slot, tid, cnt, d):")
        self.assertTrue(self.than, "mat ham `_cell`")

    def test_o_co_label_icon(self):
        self.assertIn("l_icon", self.than)
        self.assertIn("_icon_loai(", self.than)

    def test_XOA_anh_cu_khi_o_doi_item(self):
        """O duoc dung lai cho item khac moi lan refresh - giu anh cu la icon SAI cho mon moi."""
        i = self.than.find("l_icon.configure(image=")
        self.assertGreater(i, 0)
        self.assertIn('""', self.than[i:i + 120],
                      "phai gan image=\"\" de xoa; image=None khong xoa duoc")

    def test_ten_thut_vao_cho_icon(self):
        """Icon de len chu thi doc khong ra ten - phai lay cho that su."""
        self.assertIn("_IC", self.than)
        i = self.than.find("l_ten.place(")
        self.assertIn("_IC", self.than[i:i + 120], "ten khong thut vao -> icon de len chu")

    def test_click_vao_icon_van_chon_duoc_o(self):
        i = self.than.find("w.bind(")
        khoi = self.than[max(0, i - 200):i]
        self.assertIn("l_icon", khoi, "bam trung icon thi khong chon duoc o")


class TestIconODangMac(unittest.TestCase):
    """User 21/09: "may trang bi o cac slot dang mac cung can icon tuong ung de de nhan biet item
    cung loai" - tuc icon o hang DANG MAC phai la CUNG hinh voi icon trong luoi tui."""

    def setUp(self):
        self.src = _doc("gui.py")
        i = self.src.find("for _c, (_fit, _ten) in enumerate(self._EQUIP_SLOTS)")
        self.assertGreater(i, 0, "mat vong dung 6 o dang mac")
        self.khoi = self.src[i:i + 1400]

    def test_o_dang_mac_co_icon(self):
        self.assertIn("_icon_loai(", self.khoi)

    def test_DUNG_CHUNG_ham_voi_luoi_tui(self):
        """Hai noi ve rieng = som muon lech hinh, luc do doi chieu bang mat lai sai."""
        self.assertEqual(self.src.count("def _icon_loai(widget, loai):"), 1)
        self.assertIn('"eq%d" % int(_fit)', self.khoi,
                      "phai suy icon tu chinh fitType cua o, khong map tay")

    def test_icon_gan_theo_O_chu_khong_theo_mon_dang_mac(self):
        """O TRONG van phai co icon - do la luc can nhin nhat."""
        i = self.khoi.find("_icon_loai(")
        self.assertNotIn("self.equip_cells", self.khoi[max(0, i - 300):i],
                         "ve icon theo mon dang mac -> o trong mat icon")

    def test_bam_trung_icon_van_chon_duoc_o(self):
        i = self.khoi.find("_l_ic.bind(")
        self.assertGreater(i, 0, "bam trung icon thi khong chon duoc o dang mac")
        self.assertIn("_select_equip", self.khoi[i:i + 120])


if __name__ == "__main__":
    unittest.main()
