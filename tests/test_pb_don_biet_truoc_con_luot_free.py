"""PB DON: BIET TRUOC con luot free hay khong - khong thu-roi-doan.

User 15/09: "cai vu con luot free hay ko va con luot mua hay ko thi may xem crack client no xu ly
the nao". Boc `Dungeon_C.dat` (8 ban ghi x 42B = 340B, khop tuyet doi) + `UISell_C.dat` (70x16B)
keo bang adb tu may that.

CLIENT GOC BIET TRUOC (`UI/UIDungeon.lua:911-920`, `Logic/Dungeon.lua:161-167`):
    conLai = dayilyCount - MarkManager.missions[dayilyFlag].step + VIP(EVIPPermission.Dungeon)
    event_SJoin:SetActive(conLai > 0)       -- con luot moi hien nut VAO
    event_SBuyCount:SetActive(conLai == 0)  -- het luot thi chi con nut MUA
Bot thi gui dai, an loi, roi doan "chac het free" -> 24 dong `vao FREE that bai` trong 10 phut
(log 15/09). `.step` bot DA co san trong `mission_steps` (parse tu S2C 0x18 sub 0x06) - bang do
KHONG phai rieng pho ban to doi (boss the gioi cung doc no), ten cu `team_dungeon_steps` gay hieu
nham nen doi thanh `mission_steps`.

BA SO LAY TU FILE, khong doan:
    id 2/3/4/5 = 4 ban ghi PB don (kind=2, maxPlayer=1, scene 62001), khac nhau o dai level
    15~80 / 81~150 / 151~200 / 201~450  -> `_dungeon_tier()` that ra tra `dungeonId`
    dayilyFlag = 0x3030 CHUNG ca bon | dayilyCount = 1 | skipFlag = 0 (khong quet duoc)
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as C


class _F:
    """Vo mong: chi muon hai ham thuan, khong dung ket noi."""

    _label = "t"
    bag_slots = {}
    _dungeon_tier = C.GameClient._dungeon_tier
    solo_dungeon_remaining = C.GameClient.solo_dungeon_remaining

    def __init__(self, lv=100, steps=None, loaded=True):
        self.char_level = lv
        self.mission_steps = dict(steps or {})
        self.mission_steps_loaded = loaded

    def _solo(self):
        return self.solo_dungeon_remaining()


class TestDungeonIdTheoLevel(unittest.TestCase):
    """`_dungeon_tier()` tra `id` trong Dungeon_C.dat, KHONG phai "tier" tu nghi ra."""

    def test_dung_dai_level_cua_file(self):
        for lv, exp in ((1, 2), (15, 2), (80, 2), (81, 3), (150, 3), (151, 4), (200, 4)):
            self.assertEqual(_F(lv)._dungeon_tier(), exp, "lv %d" % lv)

    def test_lv201_tro_len_phai_la_id_5(self):
        """Ban ghi id 4 HET o lv 200. Code cu dung o 4 -> acc lv 201+ gui nham id.

        Chua chay vi acc cao nhat moi lv 193 (do log 15/09) - nhung dang bo toi."""
        for lv in (201, 300, 450, 999):
            self.assertEqual(_F(lv)._dungeon_tier(), 5, "lv %d" % lv)

    def test_bang_id_khop_file_dat(self):
        self.assertEqual(C.SOLO_DUNGEON_IDS, ((80, 2), (150, 3), (200, 4), (450, 5)))
        self.assertEqual(C.SOLO_DUNGEON_DAILY_FLAG, 0x3030)
        self.assertEqual(C.SOLO_DUNGEON_DAILY_COUNT, 1)


class TestBietTruocConFree(unittest.TestCase):
    def test_chua_danh_thi_con_1_luot(self):
        self.assertEqual(_F(steps={})._solo(), 1)

    def test_da_danh_roi_thi_HET(self):
        """dayilyCount = 1: PB don moi ngay CHI 1 luot free. O 1 bingo doi 2 luot nen luot thu hai
        BUOC phai mua - day la thiet ke cua game, khong phai loi."""
        self.assertEqual(_F(steps={0x3030: 1})._solo(), 0)
        self.assertEqual(_F(steps={0x3030: 9})._solo(), 0, "khong duoc ra so am")

    def test_chua_co_bang_thi_CHUA_KET_LUAN(self):
        """None chu khong phai 0: chua co mission-step thi giu duong cu (thu FREE truoc)."""
        self.assertIsNone(_F(loaded=False)._solo())

    def test_co_flag_khac_khong_lam_nhieu(self):
        self.assertEqual(_F(steps={0x302E: 1, 0x30A6: 1})._solo(), 1,
                         "doc nham flag pho ban TO DOI")


class TestDungTrongVongDoDungeon(unittest.TestCase):
    """Doc thang nguon: vong `do_daily_dungeon` phai HOI TRUOC khi lao vao."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_hoi_con_free_truoc_vong_lap(self):
        i = self.src.find("def do_daily_dungeon(")
        j = self.src.find("while self.running and done_runs < runs_target:", i)
        self.assertGreater(j, i)
        khoi = self.src[i:j]
        self.assertIn("self.solo_dungeon_remaining()", khoi,
                      "van thu-roi-doan: khong hoi con free truoc khi vao")
        self.assertIn("bought = (_free <= 0)", khoi,
                      "biet het free ma van thu vao FREE lan nua")

    def test_khong_ket_luan_khi_chua_co_bang(self):
        i = self.src.find("_free = self.solo_dungeon_remaining()")
        self.assertGreater(i, 0)
        self.assertIn("if _free is not None:", self.src[i:i + 200],
                      "chua co mission-step ma da ket luan het free")


class TestMuaLuotDocKind(unittest.TestCase):
    """`S:084-001 [sellId][kind]` noi ro tra bang gi. Truoc day bot bo qua, luon gui kieu 2."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        self.than = self.src[self.src.find("def buy_dungeon_ticket("):]
        self.than = self.than[:self.than.find("\n    def ", 10)]

    def test_doc_kind_truoc_khi_gui_lenh_mua(self):
        self.assertIn('r[0:2] == b"\\x01\\x00"', self.than, "khong doc S:084-001")
        for _n in ("UISELL_FAIL", "UISELL_FREE", "UISELL_ITEM", "UISELL_MONEY"):
            self.assertIn(_n, self.than, "thieu nhanh %s" % _n)

    def test_gia_tri_kind_dung_theo_protocol(self):
        self.assertEqual(C.GameClient.UISELL_FAIL, 0)
        self.assertEqual(C.GameClient.UISELL_FREE, 254)     # `免費使用`
        self.assertEqual(C.GameClient.UISELL_ITEM, 255)     # + itemId(2) + so luong(1)
        self.assertEqual(sorted(C.GameClient.UISELL_MONEY), [1, 2, 3])

    def test_khung_goi_084_002_giu_nguyen_khi_tra_bang_tien(self):
        """Kieu 2 (diem) phai ra DUNG goi cu `02 00 02 0d 00 <id> 00` - khong duoc doi hanh vi."""
        _kieu, _duoi, tier = 2, b"", 3
        goi = b"\x02\x00" + bytes([_kieu]) + b"\x0d\x00" + _duoi + bytes([tier]) + b"\x00"
        self.assertEqual(goi, b"\x02\x00\x02\x0d\x00\x03\x00")

    def test_tra_bang_vat_pham_thi_kem_bagIndex(self):
        """`UISell.lua:88-92`: kieu 1 = [1][sellId 2B][bagIndex 1B][args]."""
        _kieu, _duoi, tier = 1, bytes([7]), 3
        goi = b"\x02\x00" + bytes([_kieu]) + b"\x0d\x00" + _duoi + bytes([tier]) + b"\x00"
        self.assertEqual(goi, b"\x02\x00\x01\x0d\x00\x07\x03\x00")

    def test_khong_co_vat_pham_thi_DUNG_chu_khong_gui_bua(self):
        self.assertIn("KHONG CO trong tui", self.than)


class TestTenBangMissionKhongGayHieuNham(unittest.TestCase):
    """Bang `0x18 sub 0x06` la mission-step CHUNG (boss the gioi cung doc), khong rieng PB to doi."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_khong_con_ten_cu(self):
        self.assertNotIn("team_dungeon_steps", self.src)
        self.assertNotIn("team_dungeon_status_loaded", self.src)

    def test_boss_the_gioi_van_doc_cung_bang(self):
        self.assertIn("self.mission_steps.get(WORLD_BOSS_MISSION_ID", self.src)


if __name__ == "__main__":
    unittest.main()
