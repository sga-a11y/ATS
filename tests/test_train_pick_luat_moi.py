# -*- coding: utf-8 -*-
"""5 luat chon diem train (user chot 26/08) + luat khop theo TI LE thay vi "dang dong nhat".

Vi sao doi cach khop: game spawn moi diem theo DUNG HAI muc, gan nhu 50/50. Do that tren
train_block_stats.json: diem 4 'Rung Doi Phuong2' co 4x1:9386 vs 2x1:9295 - chenh 0.5%. Lay dang
dong nhat lam "so quai cua diem" thi con so do la TUNG DONG XU: may nay ghi 4, may kia ghi 2 ->
cung mot cau hinh ma hai may chon hai map khac nhau (user gap 26/08).
Them nua: cai user NHIN tren dropdown la khoang min-max cua CA CAC DANG, nen loc theo mot dang
don la loc theo con so user khong he thay.

5 luat:
  1. khop = >=40% so tran roi vao [mob_min, mob_max]
  2. level dang xet co diem CHUA CO DATA -> lay diem do truoc (de fill train_block_stats.json)
  3. tat ca da co data, nhieu diem khop -> lay diem IT TRAN NHAT
  4. tat ca da co data, khong diem nao khop -> ha level, TOI DA -5, CHI GIAM khong tang
  5. ca khoang [L-5, L] khong diem nao hop -> lay diem IT TRAN NHAT trong ca khoang
Va 2 nhanh chan duoi:
  - khoang [L-5, L] KHONG CO MAP NAO -> ha tiep den map gan nhat, diem it tran nhat
  - level muon THAP HON map thap nhat cua game -> lay luon map thap nhat
"""
import unittest

from bot import train_pick as TP


def _mp(mid, ten, so_diem):
    return (mid, ten, [(mid * 10 + i, 0) for i in range(so_diem)])


def _st(rows):
    """rows = [(map_id, spot_xy, patterns_dict, tid_quai)] -> stats gia."""
    from bot import train_block_stats as TB
    out = {"maps": {}}
    for mid, xy, pat, tid in rows:
        sd = {"patterns": dict(pat)}
        if tid:
            sd["mobs"] = {tid: 1}
        out["maps"].setdefault(str(mid), {"spots": {}})["spots"][TB.spot_key(xy)] = sd
    return out


def _tid_lv(level):
    """1 tid quai co dung level do trong npc_table (de spot co 'levels')."""
    from bot import train_block_stats as TB
    for tid, info in TB._npc_table().items():
        if info.get("level") == level:
            return tid
    return None


class TestKhopTheoTiLe(unittest.TestCase):
    def test_nguong_40_phan_tram(self):
        self.assertAlmostEqual(TP.MATCH_SHARE, 0.40)

    def test_tinh_dung_ti_le(self):
        # 4x1 nua so tran, 2x1 nua con lai -> ti le trong [4,6] la ~50%
        pat = {"4x1": 9386, "2x1": 9295, "3x1": 63}
        r = TP.mob_share_in_range(pat, 4, 6)
        self.assertGreater(r, 0.49)
        self.assertLess(r, 0.51)

    def test_chenh_nua_phan_tram_KHONG_con_lat_ket_qua(self):
        """Cot loi: 4x1 nhinh hon hay 2x1 nhinh hon deu cho CUNG ket qua khop."""
        a = TP.mob_share_in_range({"4x1": 9386, "2x1": 9295}, 4, 6) >= TP.MATCH_SHARE
        b = TP.mob_share_in_range({"4x1": 9295, "2x1": 9386}, 4, 6) >= TP.MATCH_SHARE
        self.assertTrue(a)
        self.assertEqual(a, b, "doi cho 2 dang gan bang nhau ma ket qua lat = lai la tung dong xu")

    def test_dang_hiem_khong_lam_diem_thanh_hop(self):
        """1-2 lan tren 5500 tran -> khong duoc tinh la diem 'co 3 quai'."""
        self.assertLess(TP.mob_share_in_range({"2x1": 2791, "1x1": 2744, "3x1": 2}, 3, 6),
                        TP.MATCH_SHARE)

    def test_chua_co_du_lieu_thi_ti_le_0(self):
        self.assertEqual(TP.mob_share_in_range({}, 4, 6), 0.0)
        self.assertEqual(TP.mob_share_in_range(None, 4, 6), 0.0)


class TestNamLuat(unittest.TestCase):
    def setUp(self):
        self.tid = _tid_lv(100)
        if not self.tid:
            self.skipTest("npc_table khong co quai level 100")

    def test_uu_tien_diem_CHUA_co_data(self):
        maps = [_mp(9001, "Map thu 100", 3)]
        st = _st([(9001, (90010, 0), {"4x1": 999}, self.tid)])   # chi diem 1 co data
        got = TP.pick_train_spot("avg-30", [130], maps, mob_min=4, mob_max=6, stats=st)
        self.assertIsNotNone(got)
        self.assertIn(got[1], (1, 2), "phai lay diem CHUA co data")
        self.assertIn("chua co du lieu", got[3])

    def test_nhieu_diem_hop_thi_lay_IT_TRAN_NHAT(self):
        maps = [_mp(9002, "Map thu 100", 3)]
        st = _st([(9002, (90020, 0), {"4x1": 900}, self.tid),
                  (9002, (90021, 0), {"4x1": 100}, self.tid),     # it tran nhat
                  (9002, (90022, 0), {"4x1": 500}, self.tid)])
        got = TP.pick_train_spot("avg-30", [130], maps, mob_min=4, mob_max=6, stats=st)
        self.assertEqual(got[1], 1, "phai lay diem it tran nhat de fill thong ke")

    def test_ha_toi_da_5_level(self):
        """Map o level 100 (want) va 94 (want-6). Khong diem nao hop -> KHONG duoc lay map 94."""
        maps = [_mp(9003, "Map thu 100", 1), _mp(9004, "Map xa 94", 1)]
        st = _st([(9003, (90030, 0), {"1x1": 999}, self.tid),
                  (9004, (90040, 0), {"4x1": 999}, _tid_lv(94) or self.tid)])
        got = TP.pick_train_spot("avg-30", [130], maps, mob_min=4, mob_max=6, stats=st)
        self.assertIsNotNone(got)
        self.assertNotEqual(got[0], 9004, "94 = want-6, ngoai tam -5 -> khong duoc lay")

    def test_KHONG_BAO_GIO_tim_len(self):
        """Co map o DUOI want -> tuyet doi khong duoc chon map o TREN want.

        (Map cao hon van co the duoc chon trong DUNG mot truong hop: no la map THAP NHAT cua game,
        tuc want con thap hon ca no - do la luat rieng, test o bai duoi.)
        """
        maps = [_mp(9005, "Map cao 140", 1), _mp(9007, "Map thap 96", 1)]
        st = _st([(9005, (90050, 0), {"4x1": 999}, _tid_lv(140) or self.tid),
                  (9007, (90070, 0), {"4x1": 999}, _tid_lv(96) or self.tid)])
        got = TP.pick_train_spot("avg-30", [130], maps, mob_min=4, mob_max=6, stats=st)
        self.assertIsNotNone(got)
        self.assertEqual(got[0], 9007, "phai ha xuong map 96, KHONG duoc len map 140")
        self.assertLessEqual(got[2], 100, "level chon khong duoc vuot level muon")

    def test_muon_thap_hon_map_thap_nhat_thi_lay_map_thap_nhat(self):
        maps = [_mp(9006, "Map thap 28-30", 2)]
        st = _st([(9006, (90060, 0), {"4x1": 900}, _tid_lv(28) or self.tid),
                  (9006, (90061, 0), {"4x1": 100}, _tid_lv(28) or self.tid)])
        got = TP.pick_train_spot("avg-30", [39], maps, mob_min=4, mob_max=6, stats=st)
        self.assertIsNotNone(got, "muon lv9 ma map thap nhat lv28 -> phai lay map thap nhat")
        self.assertEqual(got[0], 9006)
        self.assertIn("THAP HON map thap nhat", got[3])


class TestLoaiBlockCham(unittest.TestCase):
    """Loai diem co block 1x2 / 1x3 / 1x4 - danh qua lau (user chot 26/08)."""

    def test_1x2_KHAC_2x1(self):
        """User nhac rieng cho nay. 1x2 = HAI khoi moi khoi 1 quai -> loai.
        2x1 = MOT khoi 2 quai -> danh mot lan -> GIU."""
        self.assertTrue(TP._la_block_cham("1x2"))
        self.assertFalse(TP._la_block_cham("2x1"))

    def test_1x1_KHONG_bi_chan(self):
        """User dan: 'dung co tien tay chan luon 1x1 day nhe'."""
        self.assertFalse(TP._la_block_cham("1x1"))
        self.assertFalse(TP._la_block_cham("3x1 + 1x1"))
        self.assertFalse(TP.has_slow_block({"1x1": 999, "3x1": 5}))

    def test_1x3_1x4_bi_chan(self):
        self.assertTrue(TP._la_block_cham("1x3"))
        self.assertTrue(TP._la_block_cham("1x4"))

    def test_block_cham_nam_o_ve_sau_cung_bi_chan(self):
        self.assertTrue(TP._la_block_cham("3x1 + 1x2"))

    def test_khong_dung_nguong_ti_le(self):
        """User: 'khong can nguong dau, khi nao can t se bao loc luon file block train'.
        Dinh 1 lan cung loai."""
        self.assertTrue(TP.has_slow_block({"2x1": 99999, "1x3": 1}))

    def test_diem_co_block_cham_thi_khong_duoc_chon(self):
        tid = _tid_lv(100)
        if not tid:
            self.skipTest("npc_table khong co quai level 100")
        maps = [_mp(9010, "Map thu 100", 2)]
        st = _st([(9010, (90100, 0), {"4x1": 500, "1x2": 500}, tid),   # co block cham
                  (9010, (90101, 0), {"4x1": 900}, tid)])              # sach, nhung NHIEU tran hon
        got = TP.pick_train_spot("avg-30", [130], maps, mob_min=4, mob_max=6, stats=st)
        self.assertEqual(got[1], 1, "phai bo diem co 1x2 du no it tran hon")


if __name__ == "__main__":
    unittest.main()
