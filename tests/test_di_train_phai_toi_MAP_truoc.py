"""LENH `di_train` = DI TOI MAP TRAIN, khong phai navigate toi toa do diem quai.

User 14/09: "vay la dang o thanh, thay vi chay ra map train may lai tinh la dang o map train va
chay ra spot a".

`st["mob_spot"]` la toa do TREN MAP TRAIN. `_start_training()` lay no roi `navigate_to` thang ma
KHONG kiem minh dang o map nao -> dung o thanh thi acc chay toi mot cho bat ky cua thanh, roi cua
kiem ben duoi moi phat hien "SAI MAP" va bo cuoc. Lap lai moi phut, khong bao gio qua duoc cong.

CA THAT party 13 (tonba = leader, thanh 21001 = Cua Thanh T.Duong, bai train 21841):
    17:02:08 [party 13] gen 11: viec=di_train - du doi, cung map/kenh -> DI TRAIN map 21841
                                (con o [21001])
    17:02:12 [tonba] khong co smart path map 21001: (770, 610) -> (1810,1360) -> chia 13 buoc
    17:04:37 [tonba] da toi diem (1820,1370) sau 4 lenh move
    17:04:37 [tonba] (LEADER) toi diem quai NHUNG dang o SAI MAP (21001 != 21841) -> de DIEU PHOI
                     ra lenh gom
    17:05:32 [tonba] (LEADER) lenh 'di_train' -> SET QS + ra train
    17:05:38 ... y het, lap lai
(1810,1360) la toa do diem quai CUA MAP 21841, bi ap len map 21001.

Bon member dung im o (770,610) suot la DUNG: server chi keo ca party khi leader QUA CONG, ma
leader thi chua bao gio toi cong.

Cua kiem map VAN CON - chi la no dat SAU khi da di. Phai co cua TRUOC.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _than_start_training():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        src = fh.read()
    i = src.find("            def _start_training(ep_ra_spot=False):")
    assert i > 0, "mat _start_training"
    j = src.find("\n            def ", i + 20)
    return src[i:j if j > 0 else i + 20000]


class TestDiToiMapTruocKhiRaSpot(unittest.TestCase):
    def setUp(self):
        self.than = _than_start_training()

    def test_co_cua_kiem_map_TRUOC_khi_lay_spot(self):
        _cua = self.than.find("CHUA O MAP TRAIN -> DI TOI MAP DA")
        self.assertGreater(_cua, 0, "khong kiem map truoc khi keo ra diem quai")
        _spot = self.than.find('spot = st.get("mob_spot")')
        self.assertGreater(_spot, 0, "mat cho lay mob_spot")
        self.assertLess(_cua, _spot, "cua kiem map dat SAU khi lay spot -> van chay bua")

    def test_sai_map_thi_dung_DUONG_SAN_CO(self):
        """`_do_reform` la duong chuan keo ca party toi map train - khong viet duong moi."""
        i = self.than.find("CHUA O MAP TRAIN -> DI TOI MAP DA")
        khoi = self.than[i:i + 2400]
        self.assertIn("_do_reform(to_spot=False)", khoi,
                      "khong dung duong san co -> khong bao gio toi duoc map train")
        self.assertIn("if c.current_map != sc:", khoi)

    def test_chua_toi_duoc_thi_TRA_VE_cho_dieu_phoi(self):
        """Khong duoc chay tiep xuong doan keo ra spot bang toa do cua map khac."""
        i = self.than.find("CHUA O MAP TRAIN -> DI TOI MAP DA")
        khoi = self.than[i:i + 2400]
        self.assertIn("chua toi duoc map train", khoi)
        self.assertIn("return False", khoi)

    def test_VAN_giu_cua_kiem_map_SAU_khi_toi_noi(self):
        """Cua cu (bat truong hop bi tran chien xen giua duong) khong duoc bo."""
        self.assertIn("toi diem quai NHUNG dang o SAI MAP", self.than)

    def test_khong_de_ra_duong_di_moi(self):
        """Bot DA co duong toi map train (`_do_reform`). Them duong thu hai la lai lech nhau."""
        i = self.than.find("CHUA O MAP TRAIN -> DI TOI MAP DA")
        khoi = self.than[i:i + 2400]
        self.assertNotIn("_travel_to_train_map(", khoi,
                         "goi ham khac de di train -> hai duong, sua mot cai quen cai kia")
        self.assertNotIn("follow_smart_route(", khoi)


if __name__ == "__main__":
    unittest.main()
