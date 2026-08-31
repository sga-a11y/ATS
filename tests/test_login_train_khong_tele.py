# -*- coding: utf-8 -*-
"""LOGIN DUNG MAP TRAIN -> khong duoc teleport di lam viec vat.

User 27/08: "luc login vao va dung map train roi, t thay no van tele ve thanh, chac de lam may
viec lat vat. M chi can tele neu can danh world bos thoi, con nhung cai khac thi chi can chay ra
diem an toan dung la duoc roi".

Thu pham: `claim_daily_quests(heavy=True)` (mac dinh) lam O SO 2 = BOSS THE GIOI ->
`do_world_boss()` TELEPORT di roi tra ve Trac Quan. No chay KE CA khi user TAT auto world boss,
vi day la "nhiem vu hang ngay" chu khong phai tinh nang world boss. Sau do acc dung o Trac Quan
(khac map train) -> phai reform di route len lai bai.

Cac viec vat con lai (gacha pet/card o4/o6, hop vat pham o7, claim line, mail, diem danh, phan
giai/ban do...) deu KHONG roi cho - da kiem trong bot/client.py.
"""
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestDailyKhongKeoRaKhoiBai(unittest.TestCase):
    def test_heavy_bam_theo_auto_world_boss(self):
        s = _doc("run_party_digioi.py")
        self.assertIn("_heavy = bool(auto_world_boss) or not train_on_map", s)
        self.assertIn("c.claim_daily_quests(heavy=_heavy)", s)
        self.assertNotIn("c.claim_daily_quests()\n", s,
                         "khong duoc con cho nao goi heavy mac dinh o luong login train")

    def test_o_so_2_dung_la_world_boss(self):
        """Neu client doi (o2 khong con la boss the gioi) thi luat tren vo nghia -> phai biet."""
        s = _doc("bot", "client.py")
        i = s.find("def claim_daily_quests(")
        doan = s[i:i + 2500]
        self.assertIn("if heavy and 2 not in done:", doan)
        self.assertIn("self.do_world_boss()", doan)

    def test_viec_NHE_van_lam(self):
        """Tat world boss KHONG duoc lam mat gacha/hop vat pham - chung khong roi cho."""
        s = _doc("bot", "client.py")
        i = s.find("def claim_daily_quests(")
        doan = s[i:i + 2500]
        for nhe in ("self.claim_gacha_pet()", "self.claim_gacha_card()", "self.do_combine_item()"):
            j = doan.find(nhe)
            self.assertGreater(j, 0)
            self.assertNotIn("if heavy", doan[max(0, j - 120):j],
                             "%s la viec NHE, khong duoc phu thuoc heavy" % nhe)


class TestXongDGKhongVeThanh(unittest.TestCase):
    """DG+Train: het gio DG ma dang DUNG SAN o bai train -> khong duoc tele ve thanh.

    Log that 27/08 13:49:54 (party 42, luu_bi): ca 5 acc login o (1170,470) map 12831 - dung
    safe cua bai train - DG da het gio (120/120) nen khong vao DG, vay ma:
        [luubmot] Ve thanh 12001 ... Teleport -> city 12001 (flag 0)
    roi pha train ngay sau do: "RECONNECT o map 12001, train map 12831 di bang ROUTE -> de reform
    keo" -> 12001 -> 12011 -> bo cong len lai DUNG CHO vua dung.
    """

    def test_co_nhanh_ra_safe_thay_vi_ve_thanh(self):
        s = _doc("run_party_digioi.py")
        self.assertIn("def _ve_cho_cho_pha_train(", s)
        i = s.find("def _ve_cho_cho_pha_train(")
        than = s[i:s.find("def _finish_digioi_train_after_dg", i)]
        self.assertIn("if c.current_map == sc and _ds:", than)
        self.assertIn("c.navigate_to(*_s0, flee=True)", than)
        self.assertIn("return", than)

    def test_dung_DANH_SACH_SAFE_DAY_DU_va_dung_yen_neu_da_o_safe(self):
        """train_safes luc do CHI CO 1 diem (cache/gan pos luc login); danh sach day du chi co
        sang pha train (`train_safes[:] = learned_safes`).

        Log 27/08 15:11: ca party dung san o safe (310,2090) -> bi bat chay 10 buoc toi (450,1210),
        22s sau pha train lai keo 11 buoc NGUOC ve (310,2090). Di lai qua vung quai 2 luot -> dinh
        tran lien tuc ("BO CHAY", "party-battle lech phien...").
        """
        s = _doc("run_party_digioi.py")
        i = s.find("def _ve_cho_cho_pha_train(")
        than = s[s.find('"""', s.find('"""', i) + 3) + 3:i + 4200]
        self.assertIn('(tm or {}).get("safe")', than, "phai lay safe DAY DU tu config map")
        self.assertIn("<= 60 ** 2", than, "da dung san o safe thi DUNG YEN")
        self.assertIn("DUNG YEN", than)

    def test_khong_o_bai_train_thi_VAN_ve_thanh(self):
        """Het gio DG luc dang o map DG / map la -> van phai ve thanh nhu cu."""
        s = _doc("run_party_digioi.py")
        i = s.find("def _ve_cho_cho_pha_train(")
        than = s[i:s.find("def _finish_digioi_train_after_dg", i)]
        self.assertIn("_go_town_safe(c, label)", than, "nhanh du phong phai con")

    def test_finish_dg_dung_nhanh_moi(self):
        s = _doc("run_party_digioi.py")
        i = s.find("def _finish_digioi_train_after_dg():")
        doan = s[i:i + 200]
        self.assertIn("_ve_cho_cho_pha_train(", doan)
        self.assertNotIn("_go_town_safe(c, label)", doan)


if __name__ == "__main__":
    unittest.main()
