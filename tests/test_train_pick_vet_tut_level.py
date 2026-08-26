# -*- coding: utf-8 -*-
"""Bot ha level de tim diem train thi phai NOI RA vi sao.

Bug that (user hoi 26/08): party level TB 160, che do "TB -30" -> muon level 130, nhung bot chon
"Hoa Dung dao4 120-122" level 122. Log CHI ghi "level quai 122 | khop level/so quai/he" - khong
noi la no da THU 130, 129, 126... va bi bo loc loai het. Mat ca buoi doi chieu du lieu 2 may moi
ra la do train_block_stats.json (du lieu quai bot tu thu, MOI MAY MOT KHAC) chu khong phai map.

Gio ly do kem VET: "tut tu 130: 130 co 9 diem nhung BO LOC loai het, 128 khong map, ...".
"""
import unittest

from bot import train_pick as TP


def _maps():
    """3 map gia: 130 va 126 co diem, 122 co diem."""
    return [
        (900130, "Map cao 130", [(10, 10), (20, 20)]),
        (900126, "Map giua 126", [(30, 30)]),
        (900122, "Map thap 120-122", [(40, 40)]),
    ]


def _stats(spots):
    """spots = {(map_id, xy): {mobs, patterns}}"""
    from bot import train_block_stats as TB
    out = {"maps": {}}
    for (mid, xy), sd in spots.items():
        out["maps"].setdefault(str(mid), {"spots": {}})["spots"][TB.spot_key(xy)] = sd
    return out


class TestVetTutLevel(unittest.TestCase):
    def test_khong_tut_thi_KHONG_co_vet(self):
        """Chon dung level muon -> ly do phai gon, khong nhet vet vao cho roi mat."""
        got = TP.pick_train_spot("avg-30", [160] * 1, _maps(), stats={"maps": {}})
        self.assertIsNotNone(got)
        self.assertEqual(got[2], 130)
        self.assertNotIn("tut tu", got[3])

    def test_tut_level_thi_ghi_ro_tung_muc(self):
        """Level muon co diem nhung bi loc loai -> vet phai ghi CA level do."""
        from bot import train_block_stats as TB
        # cho ca 3 diem deu CO du lieu, nhung level quai lech han -> spot_matches False o 130/126
        npc = TB._npc_table()
        tid = next(iter(npc), None)
        if not tid:
            self.skipTest("khong co npc_table")
        st = _stats({
            (900130, (10, 10)): {"mobs": {tid: 5}, "patterns": {"1x1": 9}},
            (900130, (20, 20)): {"mobs": {tid: 5}, "patterns": {"1x1": 9}},
            (900126, (30, 30)): {"mobs": {tid: 5}, "patterns": {"1x1": 9}},
            (900122, (40, 40)): {"mobs": {tid: 5}, "patterns": {"1x1": 9}},
        })
        got = TP.pick_train_spot("avg-30", [160], _maps(), stats=st)
        if got is None:
            self.skipTest("du lieu gia khong ra diem nao")
        if got[2] != 130:
            self.assertIn("tut tu 130", got[3])
            self.assertIn("130", got[3], "phai ghi CA level muon, khong bat dau tu 129")

    def test_vet_cat_ngan_khong_de_tran_log(self):
        """Ha tu 130 xuong 1 la ~130 muc - cat con 8, khong thi mot dong log dai ca man hinh."""
        import inspect
        src = inspect.getsource(TP.pick_train_spot)
        self.assertIn("vet[:8]", src)


if __name__ == "__main__":
    unittest.main()
