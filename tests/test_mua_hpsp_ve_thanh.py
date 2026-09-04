# -*- coding: utf-8 -*-
"""MUA HP/SP xong phai VE THANH, va luong goi phai biet map da doi.

User bao 28/08: acc "dung ket o Loi dai Huong dung" (cho NPC ban HP/SP).

Hai loi cong lai:
  1. `buy_hp_sp()` di: go_to_town(12001) -> chay TRAC_HPSP_ROUTE qua 2 CONG -> toi NPC -> mua ->
     dong dialog -> RETURN NGAY. Khong co buoc quay ra: acc nam lai o map "Loi Dai Huong Dung",
     khong phai 12001.
  2. Luong train phia sau bam `login_map` (doc MOT LAN luc login, van la map train) chu khong phai
     `c.current_map` -> tuong acc dang dung o bai train, khong nhanh nao keo no ve.

Nen acc dung im tai cho NPC den khi user tu tat.
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestVeThanhSauKhiMua(unittest.TestCase):
    def test_co_ham_ve_thanh(self):
        s = _doc("bot", "client.py")
        self.assertIn("def _ve_thanh_sau_mua_hpsp(", s)
        i = s.find("def _ve_thanh_sau_mua_hpsp(")
        than = s[i:i + 900]
        self.assertIn("self.go_to_town(self.TRAC_QUAN_CITY, 0)", than)
        self.assertIn("_wait_combat_clear(", than, "teleport giua tran -> server KICK")

    def test_da_o_thanh_thi_khong_tele_lai(self):
        s = _doc("bot", "client.py")
        i = s.find("def _ve_thanh_sau_mua_hpsp(")
        than = s[i:i + 900]
        self.assertIn("if self.current_map == self.TRAC_QUAN_CITY:", than)

    def test_goi_trong_FINALLY(self):
        """Loi giua chung (route dut, shop khong mo) cung phai ve - khong thi van ket o map NPC.

        Neo theo KHOI `finally` THAT (tu `finally:` toi het than ham) chu khong cat cung 1200 ky
        tu: them vai dong chu thich vao khoi do la bai test dut du hanh vi khong doi.
        """
        s = _doc("bot", "client.py")
        i = s.find("def buy_hp_sp(")
        than = s[i:s.find("\n    def ", i + 10)]
        j = than.find("finally:")
        self.assertGreater(j, 0, "phai co finally")
        self.assertIn("self._ve_thanh_sau_mua_hpsp()", than[j:])

    def test_route_di_qua_CONG_nen_ket_o_map_khac(self):
        """Neu route sau nay khong con qua cong nua thi luat tren thua - test giu cho biet."""
        s = _doc("bot", "client.py")
        i = s.find("TRAC_HPSP_ROUTE = [")
        than = s[i:i + 1800]
        self.assertIn('("gate", "08000100")', than)
        self.assertIn('("gate", "08000500")', than)


class TestCapNhatLoginMap(unittest.TestCase):
    def test_sau_mua_phai_cap_nhat_login_map(self):
        s = _doc("run_party_digioi.py")
        i = s.find("loi mua HP/SP")
        self.assertGreater(i, 0)
        doan = s[i:i + 900]
        self.assertIn("login_map = c.current_map", doan)
        self.assertIn("c.current_map != login_map", doan)


if __name__ == "__main__":
    unittest.main()
