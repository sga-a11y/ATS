"""Chay vong trong Di Gioi: KHONG duoc di ra ngoai vung di duoc; ra khoi DG thi phai FLEE.

1. ANCHOR SAU RELOGIN
`_di_gioi_anchor` (tam co dinh = diem tele vao) CHI duoc dat trong `enter_di_gioi()`. Acc RELOGIN
khi DA o trong DG thi khong ai dat -> roi ve `self.pos`, ma pos sau relogin lay tu `0x03`
self-spawn CO THE nam ngoai vung di duoc. Do tren Ground.mmg map 49942: co diem lech toi 970 don
vi so voi o di duoc gan nhat. Anchor sai -> ca 8 diem chay vong sai theo.
User 01/09: "log in vao game, thay acc o DG va dung o ngoai vung co the di".

2. RA KHOI DG PHAI FLEE
`exit_di_gioi` truoc day khong he dat `flee_mode`, chi `_wait_combat_clear` (= dung yen DANH cho
xong). Dang tren duong THOAT ma danh tung bay quai la vo nghia.
User 01/09: "di chuyen ra ngoai thi no phai o che do flee chu, sao no van danh".
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as CL, config     # noqa: E402
from bot.client import GameClient        # noqa: E402


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


class TestBamODiDuoc(unittest.TestCase):
    _MAC_DINH = object()

    def _bot(self, map_id=_MAC_DINH):
        c = GameClient.__new__(GameClient)
        c._label = "t"
        c.current_map = config.DIGIOI_MAP_ID if map_id is self._MAC_DINH else map_id
        return c

    def test_diem_ngoai_vung_bi_KEO_VE_o_di_duoc(self):
        if CL._ground_store() is None:
            self.skipTest("khong co Ground.mmg tren may nay")
        c = self._bot()
        ra = c._bam_o_di_duoc((2400, 1900), (870, 740))
        self.assertIsNotNone(ra, "khong bam duoc -> van gui move ra ngoai map")
        self.assertNotEqual(tuple(ra), (2400, 1900))

    def test_diem_DA_di_duoc_thi_gan_nhu_giu_nguyen(self):
        """Chi lam tron ve o luoi (~10 don vi), khong duoc keo di dau khac."""
        if CL._ground_store() is None:
            self.skipTest("khong co Ground.mmg tren may nay")
        c = self._bot()
        ra = c._bam_o_di_duoc((870, 740), (870, 740))
        self.assertIsNotNone(ra)
        self.assertLessEqual(max(abs(ra[0] - 870), abs(ra[1] - 740)), 20)

    def test_chua_biet_map_thi_tra_None(self):
        c = self._bot(map_id=None)
        self.assertIsNone(c._bam_o_di_duoc((1, 1), (2, 2)))

    def test_loi_khong_lam_sap(self):
        c = self._bot(map_id=999999)     # map khong co trong Ground.mmg
        c._bam_o_di_duoc((1, 1), (2, 2))   # khong duoc nem


class TestVongChayDungHam(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _run_around_loop(")
        self.assertGreater(i, 0)
        self.than = s[i:s.find("\n    def ", i + 10)]

    def test_BAM_ANCHOR(self):
        self.assertIn("anchor = self._bam_o_di_duoc(anchor, anchor) or anchor", self.than,
                      "anchor sau relogin co the nam ngoai map -> ca 8 diem sai theo")

    def test_BAM_TUNG_DIEM_truoc_khi_move(self):
        i_bam = self.than.find("_dich = self._bam_o_di_duoc(")
        i_move = self.than.find("self.move_to(*_dich)")
        self.assertGreater(i_bam, 0, "khong bam tung diem -> bai sat tuong la di xuyen ra ngoai")
        self.assertGreater(i_move, i_bam)

    def test_khong_co_dia_hinh_thi_GIU_NGUYEN_hanh_vi_cu(self):
        self.assertIn("or (ax + dx, ay + dy)", self.than,
                      "khong co Ground.mmg ma bo luon buoc di = te hon truoc")


class TestRaKhoiDGPhaiFlee(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def exit_di_gioi(")
        self.assertGreater(i, 0)
        self.than = s[i:s.find("\n    def _di_bo_chuoi_buoc_ra_cong", i)]

    def test_BAT_FLEE_truoc_khi_di(self):
        i_flee = self.than.find("self.flee_mode = True")
        i_vong = self.than.find("while self.running:")
        self.assertGreater(i_flee, 0, "khong bat flee -> vua di ra vua danh tung bay quai")
        self.assertLess(i_flee, i_vong, "bat flee SAU vong lap thi may vong dau van danh")

    def test_navigate_cung_di_bang_flee(self):
        self.assertIn("flee=True", self.than)


if __name__ == "__main__":
    unittest.main()
