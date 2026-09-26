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
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        client = mock.Mock(current_map=100)
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"do_daily": True, "auto_world_boss": False}}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100):
            R._nhiem_vu_ngay_engine_moi(client, 0)
        client.claim_daily_quests.assert_called_once_with(heavy=False)
        client.do_world_boss_all.assert_not_called()

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




if __name__ == "__main__":
    unittest.main()
