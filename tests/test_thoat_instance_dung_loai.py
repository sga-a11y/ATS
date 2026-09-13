"""HAI LOAI INSTANCE, HAI LENH THOAT - bot BIET minh dang o loai nao, khong duoc thu mo.

User 13/09: "P9, bi ket o map khieu chien Dau dau, cai nay la danh PB don, t nghi la danh xong no
ko chiu nhan thuong nen ko ra khoi map dc" -> "thu cai lon, dang lam PB don hay doi ma bot deo
biet a".

    PB TO DOI (`TEAM_DUNGEON_MAPS` = {62002, 62011, 62012, 62013}) -> `C:047-010`
    PB DON / instance khac (vd 62001)                              -> `C:013-004` + ID CUA MINH
                                                                      (`Dungeon.LeaveSinglePlayDungeon`)

Gui sai loai thi server im lang - acc o lai instance mai mai.

CA THAT (party 9):

    14:09:06 [lbo007] go_to_town: DANG TRONG instance (map=62001) -> THOAT PHO BAN roi ve thanh
    14:09:06 [lbo007] THOAT PHO BAN TO DOI (C:047-010) - khong relogin
    14:09:12 [lbo007] -> gui C:047-010 roi ma 6s chua ra khoi map 62001
    ... lap lien tuc; BA acc cung ket, ca party dung cho o 21001 ...

62001 khong nam trong `TEAM_DUNGEON_MAPS` -> la PB DON.

KHONG PHAI LOI CUA PB DON: duong dungeon binh thuong van goi dung `leave_single_dungeon` va van
chay dung (party 48 cung ngay: "Thoat pho ban SOLO (013-004 voi ID cua chinh minh)" -> ra binh
thuong). Sai nam o `go_to_town` - duong DIEU PHOI KEO VE GOM, them 10/09 (commit f7e7fab), tu dau
chi biet moi lenh to doi. No chi no khi acc DANG O TRONG PB don VA co lenh gom keo ve.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import TEAM_DUNGEON_MAPS, in_instance_map


def _than_go_to_town():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        src = fh.read()
    i = src.find("    def go_to_town(")
    assert i > 0, "mat go_to_town"
    j = src.find("\n    def ", i + 10)
    return src[i:j]


class TestBietMinhODAU(unittest.TestCase):
    def test_62001_KHONG_phai_pho_ban_to_doi(self):
        self.assertNotIn(62001, TEAM_DUNGEON_MAPS)

    def test_62001_van_la_instance(self):
        self.assertTrue(in_instance_map(62001), "khong nhan ra la instance -> khong ai thoat ho")

    def test_bon_map_PB_to_doi(self):
        self.assertEqual(set(TEAM_DUNGEON_MAPS), {62002, 62011, 62012, 62013})


class TestChonLenhTheoLoai(unittest.TestCase):
    def setUp(self):
        # Neo tren CA THAN HAM, khong cat theo cua so ky tu: chu thich dai (ca that party 9) day
        # phan ma ra ngoai khung -> test dut du ma van dung.
        self.than = _than_go_to_town()
        self.khoi = self.than

    def test_co_phan_loai_theo_map(self):
        self.assertIn("TEAM_DUNGEON_MAPS", self.khoi,
                      "khong phan loai -> gui mo mot lenh cho ca hai loai")

    def test_co_ca_hai_duong_ra(self):
        self.assertIn("leave_team_dungeon()", self.khoi)
        self.assertIn("leave_single_dungeon()", self.khoi)

    def test_KHONG_thu_lan_luot(self):
        """Thu lan luot = doan. Gui lenh to doi cho PB don la mot goi rac gui len server."""
        _ma = re.sub(r"#.*", "", self.khoi)
        self.assertIn("if _la_to_doi:", _ma, "khong re nhanh theo loai instance")
        self.assertIn("elif self.leave_single_dungeon():", _ma,
                      "hai duong phai loai tru nhau (if/elif), khong phai thu roi fallback")

    def test_log_noi_ro_loai_nao(self):
        self.assertIn("PB TO DOI", self.khoi)
        self.assertIn("PB DON", self.khoi)


class TestChayThatPhepChon(unittest.TestCase):
    @staticmethod
    def _lenh(map_id):
        return "047-010" if int(map_id) in TEAM_DUNGEON_MAPS else "013-004"

    def test_khieu_chien_dau_dau_dung_lenh_PB_don(self):
        self.assertEqual(self._lenh(62001), "013-004")

    def test_PB_to_doi_lv20(self):
        self.assertEqual(self._lenh(62002), "047-010")

    def test_PB_to_doi_lv50_80_110(self):
        for m in (62011, 62012, 62013):
            self.assertEqual(self._lenh(m), "047-010", m)

    def test_instance_la_khac_cung_dung_lenh_don(self):
        """Instance 62xxx khac (San Kho Bau, Bach Chien...) -> khong phai PB to doi cua bot."""
        for m in (62003, 62050, 62999):
            self.assertEqual(self._lenh(m), "013-004", m)


class TestDuongDungeonBinhThuongKhongBiDungVao(unittest.TestCase):
    """PB don khong he bi sua - chi `go_to_town` duoc bo sung."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_luong_dungeon_van_goi_leave_single_dungeon(self):
        self.assertGreaterEqual(self.src.count("leave_single_dungeon()"), 3,
                                "duong dungeon binh thuong mat loi thoat")

    def test_ham_thoat_don_van_gui_ID_cua_chinh_minh(self):
        i = self.src.find("def leave_single_dungeon(")
        self.assertGreater(i, 0)
        j = self.src.find("\n    def ", i + 10)
        self.assertIn("bytes(self.self_entity)", self.src[i:j],
                      "phai mang ID CUA CHINH MINH, khong phai ID doi truong")


if __name__ == "__main__":
    unittest.main()
