# -*- coding: utf-8 -*-
"""Tui do cua bot: THE DOI phai hoi chon muc, KHONG duoc gui goi dung item thuong.

Item co specialAbility 219 (EItemUseKind.Exchange) dung goi RIENG:
    C:090-001 <兌換> = 0x5a sub01 + [itemId u16][so muc chon][index...]
Bam "Sử dụng" (0x17 sub0f) len no la SAI LENH - server khong hieu, user tuong bot hong.

Bai test doc thang gui.py (giong cac bai neo Kotlin): sua nhanh hanh vi ma quen cho nay thi do.
"""
import io
import os
import unittest

GUI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui.py")


def _src():
    with io.open(GUI, encoding="utf-8") as fh:
        return fh.read()


class TestTuiDoTheDoi(unittest.TestCase):
    def test_co_nhanh_rieng_cho_the_doi(self):
        s = _src()
        self.assertIn("_exchange_rows(tid)", s, "phai nhan dien the doi truoc khi hien nut")
        self.assertIn("_chon_qua_doi", s, "phai co hop thoai chon muc")

    def test_the_doi_KHONG_dung_nut_su_dung_thuong(self):
        """Nhanh `elif _doi:` phai dung TRUOC `elif _BAG.can_use(...)`.

        Neu dat sau thi item nao co btnState>0 se roi vao nut "Sử dụng" -> gui 0x17 sub0f.
        """
        s = _src()
        i_doi = s.find("elif _doi:")
        i_use = s.find('acts.append(("Sử dụng"')
        self.assertGreater(i_doi, 0, "khong tim thay nhanh the doi")
        self.assertGreater(i_use, 0)
        self.assertLess(i_doi, i_use, "nhanh the doi phai dung TRUOC nut Sử dụng")

    def test_goi_dung_ham_open_exchange_card(self):
        s = _src()
        self.assertIn("self.c.open_exchange_card(tid, i, cho_xac_nhan=False)", s)

    def test_tui_do_KHONG_cho_xac_nhan(self):
        """Tui do phai dung cho_xac_nhan=False.

        Cac lenh khac (use_slot/equip_item) tra True NGAY khi gui xong; _run tu doi chieu trang
        thai truoc/sau de bao ket qua. De cho_xac_nhan=True thi het 3s cho la tra False -> _run
        bao nham "Khong gui duoc lenh (o trong / acc mat ket noi)" du goi DA gui va o van co the.
        """
        s = _src()
        self.assertIn("cho_xac_nhan=False", s)

    def test_nut_mo_hop_thoai_KHONG_boc_trong_run(self):
        """Nut "Mở / chọn quà..." chi MO BANG CHON, chua gui goi nao.

        Bug that (anh chup cua user): nut bi boc trong _run -> _run thay ham tra None -> bao
        "Khong gui duoc lenh (o trong / acc mat ket noi)", hien de len chinh bang chon vua mo.
        Goi that gui o buoc sau (trong _chon_qua_doi), cho do co _run rieng.
        """
        s = _src()
        self.assertIn('lambda: self._chon_qua_doi(tid, _doi), True)', s,
                      "phai co co True = khong boc _run")
        self.assertIn("_mo_hop_thoai", s, "vong dung nut phai biet bo qua _run")

    def test_khong_bao_nham_khong_dung_duoc(self):
        """The doi co btnState=0 -> truoc day se hien '(không dùng trực tiếp được)' gay hieu nham."""
        s = _src()
        self.assertIn("if not _equip and not _doi and not _BAG.can_use", s)


class TestBangExchangeCoThat(unittest.TestCase):
    def test_bang_nap_duoc_va_co_ve_boi_duong_toa_ky(self):
        from bot import config
        rows = (getattr(config, "EXCHANGE", {}) or {}).get(0x7de7) or []
        self.assertTrue(rows, "exchange.json thieu 0x7de7 -> chay tools/crack_exchange.py")
        self.assertEqual(rows[0]["id"], 0x7d65, "muc 1 phai la Tang Cap Ky Don")
        self.assertEqual(rows[0]["n"], 5)


if __name__ == "__main__":
    unittest.main()
