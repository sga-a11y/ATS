"""Ban kinh "da toi diem tap ket" phai DU CHAT de DIEM QUAI khong lot vao.

Log 31/08 party 8, lenh doi kenh tay luc dang train:
    16:11:36 [lbumot] (LEADER) pos=(760, 1980) map=21812 combat=True     <- dang o DIEM QUAI
    16:11:51 [lbumot] lenh doi kenh tay: ra diem an toan (650, 2070) truoc khi doi kenh
    16:11:51 [lbumot] ... da o diem tap ket (650, 2070) ... -> DANH XONG TAI CHO
    16:11:51 [lbumot] manual: DA ra safe -> giai tan party roi doi kenh 2
Khoang cach (760,1980) -> (650,2070) la 142, LOT vao ban kinh cu 200 -> bot bao "da ra safe" ma
KHONG HE DI MOT BUOC (user: "an lenh doi kenh no van ko chiu di ve diem safe").

Can duoi: `navigate_to` coi la toi khi con cach <= NAV_TOI_NOI (60), cong bien do `_jitter`
(+-10, cheo ~14) -> 80 la du rong de khong tu choi acc that su da toi.
"""
from __future__ import annotations

import io
import math
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestBanKinhRally(unittest.TestCase):
    def setUp(self):
        m = re.search(r"^\s*RALLY_BAN_KINH = (\d+)", _src(), re.M)
        self.assertIsNotNone(m, "mat hang RALLY_BAN_KINH")
        self.r = int(m.group(1))

    def test_KHONG_lot_diem_quai_cua_map_21812(self):
        d = math.dist((760, 1980), (650, 2070))
        self.assertLess(self.r, d,
                        "ban kinh %d >= khoang cach safe-diem quai %.0f -> dung o bai quai van bi "
                        "coi la 'da ra safe'" % (self.r, d))

    def test_van_du_rong_cho_sai_so_di_duong(self):
        from bot.client import GameClient
        toi_thieu = GameClient.NAV_TOI_NOI + 15    # jitter +-10 -> cheo ~14
        self.assertGreaterEqual(self.r, toi_thieu,
                                "chat hon %d thi acc DA toi that cung bi coi la chua toi -> cho mai"
                                % toi_thieu)

    def test_ghi_ro_ly_do_hai_can(self):
        s = _src()
        i = s.find("RALLY_BAN_KINH = ")
        khoi = s[max(0, i - 900):i]
        self.assertIn("NAV_TOI_NOI", khoi, "phai ghi can duoi lay tu dau")
        self.assertIn("diem quai", khoi.lower().replace("Đ", "d"), "phai ghi can tren vi sao")


if __name__ == "__main__":
    unittest.main()
