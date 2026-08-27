"""Thay do cho PET xong thi chi so pet phai doi ngay.

User bao 26/08: "thay cho char thi thay update luon, thay cho pet thi khong". Nguyen nhan:
`_on_equip_done` chi goi `_recalc_char_equip_stats()` trong nhanh `if not follow` (= nhan vat).
Ma chi so pet lai tinh tu `pet_login_records[follow]["equipment"]` - ban ghi cua goi pet-list
LUC LOGIN - va KHONG co lenh nao xin lai goi do (tra het C:015-*: chi them/duoi/doi ten/gui xe).
Nen khong sua ban ghi = chi so pet dung yen toi tan lan login sau.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


def _o_trong():
    return {"id": 0, "element": 0, "element_value": 0, "stone_attr": 0, "stone_lv": 0}


class _C:
    _cap_nhat_do_trong_ban_ghi_pet = GameClient._cap_nhat_do_trong_ban_ghi_pet

    def __init__(self):
        self._label = "test"
        self.pet_login_records = {1: {"equipment": [_o_trong() for _ in range(6)]}}
        # ThingData cua mon trong tui - CO linh da, phai duoc giu nguyen khi chep sang
        self.bag_items = {18: {"id": 0x5613, "element": 3, "element_value": 120,
                               "stone_attr": 7, "stone_lv": 4, "reinforced": 9}}

    def mac(self, follow, fit, tid, slot=18):
        """Mac mon o o `slot` - lay ThingData Y NHU luong that (doc TRUOC khi o tui bi ghi de)."""
        self._cap_nhat_do_trong_ban_ghi_pet(follow, fit, tid=tid, td=self.bag_items.get(slot))


class TestCapNhatBanGhi(unittest.TestCase):
    def test_mac_do_thi_ban_ghi_pet_doi_theo(self):
        c = _C()
        c.mac(1, 5, 0x5613)                             # fitType 5 = giay
        o = c.pet_login_records[1]["equipment"][4]       # fit 5 -> chi so 4
        self.assertEqual(o["id"], 0x5613)

    def test_GIU_NGUYEN_linh_da_chu_khong_uoc_tinh(self):
        """Chep du 5 khoa; mat linh da la chi so ra THIEU, con te hon khong cap nhat."""
        c = _C()
        c.mac(1, 5, 0x5613)
        o = c.pet_login_records[1]["equipment"][4]
        self.assertEqual((o["stone_attr"], o["stone_lv"]), (7, 4))
        self.assertEqual((o["element"], o["element_value"]), (3, 120))

    def test_khoa_dung_khuon_cua_pet_login_stats(self):
        """`equipment_bonus` doc dung 5 khoa nay - thieu mot cai la KeyError giua tran."""
        c = _C()
        c.mac(1, 5, 0x5613)
        o = c.pet_login_records[1]["equipment"][4]
        for k in ("id", "element", "element_value", "stone_attr", "stone_lv"):
            self.assertIn(k, o)

    def test_coi_do_thi_o_do_thanh_trong(self):
        c = _C()
        c.mac(1, 5, 0x5613)
        c._cap_nhat_do_trong_ban_ghi_pet(1, 5, tid=None)
        self.assertEqual(c.pet_login_records[1]["equipment"][4], _o_trong())

    def test_MAT_ThingData_van_phai_ghi_id(self):
        """Bug 26/08 cua chinh ban va nay: ham tu tra ThingData theo O TUI, nhung luc no chay thi
        o tui DA bi ghi de bang mon CU (thay do) -> tra ra rong -> ghi thanh O TRONG.

        Hieu ung dung nhu user do duoc: pet AGI 85, thay giay -4 bang giay -2, ra **89** (=85+4,
        chi go giay cu) thay vi 87. Mat linh da con chap nhan duoc; mat CA MON thi khong.
        """
        c = _C()
        c._cap_nhat_do_trong_ban_ghi_pet(1, 5, tid=0x5613, td=None)
        o = c.pet_login_records[1]["equipment"][4]
        self.assertEqual(o["id"], 0x5613, "mat ThingData thi thanh o TRONG -> tinh thieu ca mon")

    def test_ThingData_cua_mon_KHAC_thi_khong_dung(self):
        """O tui da bi mon CU chiem -> ThingData do khong phai cua mon vua mac, dung la sai so."""
        c = _C()
        cu = {"id": 0x9999, "element": 1, "element_value": 200, "stone_attr": 9, "stone_lv": 9}
        c._cap_nhat_do_trong_ban_ghi_pet(1, 5, tid=0x5613, td=cu)
        o = c.pet_login_records[1]["equipment"][4]
        self.assertEqual(o["id"], 0x5613)
        self.assertEqual((o["stone_attr"], o["stone_lv"]), (0, 0), "lay nham linh da cua mon cu")

    def test_khong_lam_sap_khi_thieu_du_lieu(self):
        c = _C()
        for a in ((9, 5), (1, 0), (1, 7)):
            c.mac(a[0], a[1], 0x5613)   # pet la, fit 0 / qua 6
        self.assertEqual(len(c.pet_login_records[1]["equipment"]), 6)


class TestCaHaiBanGhi(unittest.TestCase):
    """Pet DANG XUAT CHIEN co HAI ban ghi rieng, moi cai nuoi mot cho hien thi:

        pet_login_records[follow] -> pet_stats()                       -> chi so trong TUI DO
        _active_pet_login         -> _refresh_active_pet_login_stats() -> `pet_agi` = nut Check AGI

    User bao 26/08: "chi so trong tui do update roi, nhung cho check agi chua" - dung la sua moi
    ban ghi thu nhat.
    """

    def _c(self):
        c = _C()
        c._active_pet_login = {"marker": 1, "equipment": [_o_trong() for _ in range(6)]}
        c.da_tinh_lai = 0
        c._refresh_active_pet_login_stats = lambda: setattr(c, "da_tinh_lai", c.da_tinh_lai + 1)
        return c

    def test_sua_CA_HAI_ban_ghi(self):
        c = self._c()
        c.mac(1, 5, 0x5613)
        self.assertEqual(c.pet_login_records[1]["equipment"][4]["id"], 0x5613)
        self.assertEqual(c._active_pet_login["equipment"][4]["id"], 0x5613,
                         "ban ghi cua con dang xuat chien khong duoc sua -> Check AGI dung so cu")

    def test_co_tinh_lai_pet_agi(self):
        c = self._c()
        c.mac(1, 5, 0x5613)
        self.assertEqual(c.da_tinh_lai, 1, "sua xong khong tinh lai thi `pet_agi` van la so cu")

    def test_pet_KHAC_thi_khong_dung_vao_ban_ghi_active(self):
        c = self._c()
        c.pet_login_records[2] = {"equipment": [_o_trong() for _ in range(6)]}
        c.mac(2, 5, 0x5613)          # con so 2, khong phai con dang xuat chien (marker 1)
        self.assertEqual(c._active_pet_login["equipment"][4]["id"], 0, "sua nham con khac")
        self.assertEqual(c.da_tinh_lai, 0)

    def test_coi_do_cung_cap_nhat_ca_hai(self):
        c = self._c()
        c.mac(1, 5, 0x5613)
        c._cap_nhat_do_trong_ban_ghi_pet(1, 5, tid=None)
        self.assertEqual(c._active_pet_login["equipment"][4], _o_trong())
        self.assertEqual(c.da_tinh_lai, 2)

    def test_moi_ban_ghi_mot_dict_RIENG(self):
        """Dung chung mot dict thi sua ban ghi nay se am tham doi ban ghi kia."""
        c = self._c()
        c.mac(1, 5, 0x5613)
        a = c.pet_login_records[1]["equipment"][4]
        b = c._active_pet_login["equipment"][4]
        self.assertEqual(a, b)
        self.assertIsNot(a, b)


class TestNoiVaoLuong(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_mac_va_coi_do_pet_deu_goi(self):
        import re
        than = re.sub(r"#.*", "", self.src)
        self.assertEqual(than.count("_cap_nhat_do_trong_ban_ghi_pet("), 3,
                         "phai co 1 def + 2 cho goi (mac do / coi do)")

    def test_nhanh_pet_KHONG_bi_bo_quen_nhu_truoc(self):
        """Bug cu: `if not follow: _recalc_char_equip_stats()` - nhanh pet khong lam gi ca."""
        import re
        m = re.search(r"if not follow:\s*\n\s*self\._recalc_char_equip_stats\(\)\s*\n(\s*)else:",
                      self.src)
        self.assertIsNotNone(m, "nhanh coi do cho PET lai khong lam gi")


if __name__ == "__main__":
    unittest.main()
