"""Gap tran giua duong: DUNG YEN CHO, khong an vao ngan sach buoc di - lam Y CLIENT.

Soi `_lua_dec` (31/08), client xu ly dung hai cho va deu la "dung im, giu nguyen dich":

    MoveController:Update()             -> `if ... FightField.isInBattle then return end`
                                           (khong tien mot buoc, `Role.player.position` DUNG IM)
    MoveController.SendRolePosition()   -> `if FightField.isInBattle ... then return end`
                                           (khong gui `C:006-001`)

`targetPosition` KHONG bi xoa, timer KHONG bi go (chi go khi het diem / doi scene / vao nha /
reconnect) => het tran la di tiep toi DUNG dich cu.

Bot truoc day tang `attempts` NGAY DAU vong lap, nen moi luot cho tran an mot suat trong
`max_iter`: tran dai = het ngan sach = thoat vong khi CHUA gui du buoc, dung giua duong nhung van
chay tiep phan sau nhu da toi (user 31/08: "dang chay ma gap battle thi no ko den duoc diem muon
den").
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


class TestGapTranGiuaDuong(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("    def navigate_to(")
        self.assertGreater(i, 0)
        j = s.find("\n    def follow_path(", i)
        self.assertGreater(j, i)
        self.khoi = s[i:j]
        self.than = re.sub(r"#.*", "", self.khoi)
        self.src = s

    def test_cho_tran_KHONG_an_ngan_sach_buoc(self):
        i_w = self.than.find("while attempts < max_iter and sent < waypoint_moves:")
        self.assertGreater(i_w, 0)
        i_tran = self.than.find("if self.in_combat(idle_secs=1.0):", i_w)
        i_dem = self.than.find("attempts += 1", i_w)
        self.assertGreater(i_tran, 0)
        self.assertGreater(i_dem, i_tran,
                           "attempts += 1 nam TRUOC nhanh cho tran -> tran an het ngan sach buoc")

    def test_cho_tran_co_HAN(self):
        self.assertIn("NAV_CHO_TRAN_CAP", self.src, "cho vo han = treo ca acc neu ket tran")
        self.assertIn("_cho_tran > self.NAV_CHO_TRAN_CAP", self.than)

    def test_reset_bo_dem_cho_khi_het_tran(self):
        """Han la cho MOT tran, khong phai tong thoi gian ca chang."""
        self.assertIn("_cho_tran = 0.0", self.than)
        self.assertGreaterEqual(self.than.count("_cho_tran = 0.0"), 2,
                                "khong reset sau moi tran -> chang dai nhieu tran la bi cat oan")

    def test_vong_DI_BU_cung_the(self):
        i = self.than.find("while _them < 8 and self.running:")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 800]
        self.assertIn("_cho_bu", khoi, "vong di bu cho tran vo han")
        i_tran = khoi.find("if self.in_combat(idle_secs=1.0):")
        i_dem = khoi.find("_them += 1")
        self.assertGreater(i_dem, i_tran, "cho tran an vao ngan sach di bu")

    def test_KHONG_CHO_NAO_move_giua_tran(self):
        """Client KHONG BAO GIO gui `C:006-001` trong tran. Moi cho goi `move_to` cua bot deu phai
        cho het tran truoc - `exit_di_gioi` truoc day gui thang, ma do la doan replay chuoi buoc
        THAT tu capture: goi bi nuot ma `self.pos` van nhay -> lech chuoi, di mai khong toi cong."""
        for m in re.finditer(r"^(\s*)self\.move_to\(", self.src, re.M):
            truoc = self.src[max(0, m.start() - 700):m.start()]
            self.assertTrue(
                ("in_combat(" in truoc) or ("_wait_combat_clear(" in truoc),
                "move_to o offset %d khong cho het tran truoc" % m.start())

    def test_KHONG_tu_tien_pos_trong_luc_danh(self):
        """Client dung im trong tran; bot cung chi doi `self.pos` o `move_to` (luc THAT SU gui
        goi), nen chi can KHONG gui trong tran la pos khong lech."""
        i = self.than.find("while attempts < max_iter and sent < waypoint_moves:")
        khoi = self.than[i:i + 1500]
        i_tran = khoi.find("if self.in_combat(idle_secs=1.0):")
        i_move = khoi.find("self.move_to(")
        self.assertGreater(i_move, i_tran, "gui move truoc khi kiem tran -> pos chay trong khi danh")


if __name__ == "__main__":
    unittest.main()
