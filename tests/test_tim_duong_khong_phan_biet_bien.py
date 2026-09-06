"""TIM DUONG KHONG PHAN BIET BO/BIEN - y het client.

P43/P44/P45 sang 06/09: ba leader (tonqmot, chdumot, tpmot) quay vong relogin ca tieng.
58/58 lan `SERVER NGAT KET NOI: di chuyen QUA XA (ma 14)` trong log deu dung ngay sau dong
`qua cong idx=1 -> map 18000`:

    10:48:38 BEN THUYEN idx=1 @(40,680): len thuyen (0x7c)
    10:48:39 qua cong idx=1 -> map 18000
    10:48:40.568 >>gui 0x06 0100 01 2c0b 620c    = move_to(2860, 3170)
    10:48:40.671 <<nhan 0x00 ...0e00             = ma 14

Cap ben o (2790,1070) roi ban MOT lenh move toi (2860,3170) = nhay 2100 don vi.

VI SAO: bot tu bia ra che do `boat=True` = "chi di duoc tren NUOC", va gan no cho CA chang
`18000 -> 26000` chi vi CONG DICH nam duoi nuoc. Cho cap ben lai la DAT -> `find_world_path`
bi chan ngay o o xuat phat -> tra None -> mat smart path -> nhanh di mu ban thang mot lenh.

CLIENT KHONG HE CO CHE DO DO (`_lua_dec`):
    MapManager.lua:231  IsObstacle = bit1 | bit4          <- bit2 (bien) KHONG phai chuong ngai
    FindWay.lua (377 dong, toan bo ham tim duong) chi goi IsObstacle; khong mot chu sea/boat/water
    MapManager.IsSea chi duoc goi 3 cho, khong cho nao tim duong:
        RoleController:3692 / Role.lua:318 -> SetOnTheSea() (doi hinh nhan vat sang dang thuyen)
        UIAction.lua:92 -> chan lam dong tac tren bien (`--海上不可做動作`)
Tuc dung len o bien thi TU THANH "dang tren thuyen" - he qua, khong phai dieu kien.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import pathfind as PF  # noqa: E402


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _ma_that(src):
    """Cac dong MA THUC SU chay - bo chu thich va MOI chuoi (docstring nhac lai bug cu)."""
    import io as _io, tokenize
    bo = set()
    toks = tokenize.generate_tokens(_io.StringIO(src).readline)
    for tok in toks:
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            for ln in range(tok.start[0], tok.end[0] + 1):
                bo.add(ln)
    return [d for i, d in enumerate(src.splitlines(), 1) if i not in bo]


# Luoi 5x5, cot 3 la BIEN (bit2), con lai la dat trong; o (5,5) la tuong (bit1).
def _grid():
    g = []
    for x in range(1, 6):
        for y in range(1, 6):
            g.append(2 if x == 3 else 0)
    g[(5 - 1) * 5 + (5 - 1)] = 1
    return g


class TestLuatChanGiongClient(unittest.TestCase):
    """`IsObstacle = bit.band(v,1)==1 or bit.band(v,4)==4` - khong hon khong kem."""

    def setUp(self):
        self.g = _grid()

    def test_o_BIEN_KHONG_phai_chuong_ngai(self):
        self.assertFalse(PF._blocked(self.g, 5, 5, 3, 2), "o bien bi coi la chan -> sai client")

    def test_bit1_va_bit4_moi_la_chuong_ngai(self):
        for val, chan in ((0, False), (1, True), (2, False), (3, True), (4, True), (6, True)):
            g = [val] * 25
            self.assertEqual(PF._blocked(g, 5, 5, 1, 1), chan, "val=%d" % val)

    def test_ngoai_luoi_la_chan(self):
        self.assertTrue(PF._blocked(self.g, 5, 5, 9, 9))

    def test_KHONG_con_tham_so_boat_o_bat_ky_dau(self):
        """Che do boat la bot tu bia; con lai la con duong quay lai bug cu."""
        for f, cho_phep in (("pathfind.py", ()), ("client.py", ("board_boat=", "on_boat=")),
                            ("smart_route.py", ())):
            for dong in _ma_that(_doc("bot", f)):
                if "boat=" in dong:
                    self.assertTrue(any(k in dong for k in cho_phep), "%s: %s" % (f, dong))


class TestDiXuyenBoVaBien(unittest.TestCase):
    """Chang NUA BO NUA BIEN: xuat phat tren dat, dich duoi nuoc - phai ra duong."""

    def test_tu_dat_toi_o_bien(self):
        p = PF.find_local_path(_grid(), 5, 5, (1, 1), (3, 5))
        self.assertTrue(p, "dat -> bien khong ra duong (dung bug p43/44/45)")

    def test_tu_bien_ve_dat(self):
        self.assertTrue(PF.find_local_path(_grid(), 5, 5, (3, 1), (5, 1)))

    def test_di_doc_tren_bien(self):
        self.assertTrue(PF.find_local_path(_grid(), 5, 5, (3, 1), (3, 5)))


class TestChanCuoiKhongBanLenhNhayXa(unittest.TestCase):
    """Loi tim duong chi duoc phep 'di sai', KHONG duoc phep lam ROT GAME."""

    def setUp(self):
        self.src = _doc("bot", "client.py")
        i = self.src.find("def navigate_to(")
        self.than = self.src[i:self.src.find("\n    def ", i + 10)]

    def test_khong_smart_path_ma_biet_pos_thi_VAN_chia_doan(self):
        i = self.than.find("if not using_smart_path and self.pos:")
        self.assertGreater(i, 0, "nhanh di mu van ban thang mot lenh toi dich")
        khoi = self.than[i:i + 600]
        self.assertIn("_split_segment", khoi)
        self.assertIn("SMART_PATH_SEGMENT", khoi)

    def test_chia_doan_dung_do_dai(self):
        import math
        def split(a, b, max_len):
            ax, ay = a; bx, by = b
            dist = math.hypot(bx - ax, by - ay)
            n = max(1, int(math.ceil(dist / max_len)))
            return [(round(ax + (bx - ax) * i / n), round(ay + (by - ay) * i / n))
                    for i in range(1, n + 1)]
        # dung ca P45: cap ben (2790,1070) -> cong 36 (2860,3170)
        buoc = split((2790, 1070), (2860, 3170), 100.0)
        truoc = (2790, 1070)
        for diem in buoc:
            self.assertLessEqual(math.hypot(diem[0] - truoc[0], diem[1] - truoc[1]), 101,
                                 "van con buoc nhay xa -> ma 14")
            truoc = diem
        self.assertEqual(buoc[-1], (2860, 3170))


class TestRouteThatCuaP45(unittest.TestCase):
    """Route 18021 -> 26816 (train map cua p43/44/45). Chi chay khi may co Ground.mmg."""

    def setUp(self):
        from bot.client import _ground_store, _smart_world_router
        self.gs = _ground_store()
        self.r = _smart_world_router()
        if self.gs is None or self.r is None:
            self.skipTest("khong co Ground.mmg tren may nay")

    def test_chang_cap_ben_toi_cong_bien_RA_DUONG(self):
        p = self.gs.find_world_path(18000, (2790, 1070), (2860, 3170))
        self.assertTrue(p, "chang 18000 -> cong 36 lai None = bug p45 quay lai")
        self.assertGreater(len(p), 2)

    def test_duong_do_di_qua_CA_dat_lan_bien(self):
        p = self.gs.find_world_path(18000, (2790, 1070), (2860, 3170))
        co = {self.gs.is_sea_world(18000, q) for q in p}
        self.assertEqual(co, {True, False}, "phai la chang nua bo nua bien")

    def test_route_day_du_van_build_duoc(self):
        rt = self.r.build_scene_route(18021, 26816, None, start=(270, 590))
        self.assertIsNotNone(rt)
        self.assertEqual([l["target_scene"] for l in rt["legs"]][-1], 26816)


if __name__ == "__main__":
    unittest.main()
