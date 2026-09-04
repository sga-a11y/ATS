"""Mo ta item (tac dung) hien trong dialog Tui do.

Nguon: Item_C.dat truong cuoi `description` (ItemData.lua --[55] 說明, <=254 ky tu). Bo ra file
RIENG `items_desc.json` chu KHONG nhap vao items_gamedata.json: 25634 item deu co mo ta (1.32
trieu ky tu) ma items_gamedata.json duoc MOI tien trinh party load het vao RAM.
"""
from __future__ import annotations

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESC = os.path.join(ROOT, "items_desc.json")


def _doc(ten):
    with open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


class TestFileMoTa(unittest.TestCase):
    def setUp(self):
        with open(DESC, encoding="utf-8") as fh:
            self.d = json.load(fh)

    def test_co_du_mo_ta(self):
        self.assertGreater(len(self.d), 20000, "items_desc.json thieu qua nhieu muc")

    def test_khoa_mo_ta_that(self):
        """Neo bang vai item da doi chieu tay voi client - bat sai lech ban ghi khi doc .dat."""
        self.assertIn("Ngộ Tính Đan", self.d["0xb22c"])          # Tui Toa Ky Dan
        self.assertIn("Thái Văn Cơ", self.d["0xb297"])           # Qua Thai Van Co
        self.assertIn("Đích Lô", self.d["0x799d"])               # Ve Dich Lo

    def test_khoa_dang_hex_va_khong_rong(self):
        for k, v in self.d.items():
            self.assertRegex(k, r"^0x[0-9a-f]{4}$")
            self.assertTrue(v.strip(), "muc %s co mo ta rong -> phai bo di cho file gon" % k)

    def test_khong_nhap_vao_items_gamedata(self):
        """items_gamedata.json phai GIU nguyen kich thuoc - do la file bot load moi party."""
        with open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            g = json.load(fh)
        co = [k for k, v in g.items() if isinstance(v, dict) and v.get("desc")]
        self.assertEqual(co, [], "mo ta bi nhet vao items_gamedata.json -> phinh RAM moi party")


class TestKhaiBaoDongGoi(unittest.TestCase):
    def test_co_trong_DATA_JSON_cua_ban_exe(self):
        """Quen khai bao = ban exe THIEU file am tham (loi da tai pham 3 lan, xem CLAUDE.md)."""
        import sys
        sys.path.insert(0, ROOT)
        from build_product import DATA_JSON
        self.assertIn("items_desc.json", DATA_JSON)

    def test_KHONG_khai_bao_cho_APK(self):
        """APK khong co dialog Tui do -> khai bao vao la doi 2MB lay khong gi."""
        src = _doc(os.path.join("tools", "sync_apk_python.py"))
        self.assertNotIn("items_desc.json", src)


class TestGuiHienMoTa(unittest.TestCase):
    """Doc thang gui.py: dialog Tui do phai doc file rieng va hien tren label rieng."""

    def setUp(self):
        self.src = _doc("gui.py")

    def test_doc_file_rieng(self):
        """Mo ta phai nap tu items_desc.json RIENG, khong gop vao items_gamedata.json.

        Neo theo Y NGHIA (co doc file do khong), khong theo TEN HAM nap: ham da tung doi tu
        _load_json -> _bag_db (them cache) va bai test cu dut du hanh vi khong he doi.
        """
        self.assertRegex(self.src, r'_(?:load_json|bag_db)\("items_desc\.json"\)')

    def test_co_label_mo_ta_rieng_khong_dinh_vao_dong_id(self):
        self.assertIn("self.lbl_desc", self.src)
        # Dong id KHONG duoc noi mo ta vao (mo ta dai toi 272 ky tu, cua so chi 690px).
        m = re.search(r'text="Ô #%d.*?\)\)', self.src, re.S)
        self.assertIsNotNone(m, "khong tim thay cho dat text dong thong tin item")
        self.assertNotIn("desc", m.group(0))

    def test_click_item_thi_cap_nhat_mo_ta(self):
        m = re.search(r"^    def _select\(self, slot\):\n(.*?)^    def ", self.src, re.S | re.M)
        self.assertIsNotNone(m)
        than = re.sub(r"#.*", "", m.group(1))       # bo chu thich, tranh bay "tim thay trong comment"
        self.assertIn("self.lbl_desc.configure", than)


if __name__ == "__main__":
    unittest.main()
