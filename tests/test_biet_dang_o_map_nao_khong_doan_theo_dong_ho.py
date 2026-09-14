""""DANG TRONG PHO BAN TO DOI" doc MAP THAT, khong doan theo dong ho.

User 14/09: "p44, lai moi dua 1 thanh, ve thanh roi ma van bao dang o PB doi, dieu phoi ngu qua,
dang o map nao ma cung ko biet" -> "thoi gian lam deo gi, dieu phoi hoan toan thay co dang o trong
PB hay ko".

Truoc day cau hoi nay tra loi bang `time.time() < self._team_dungeon_until` - moc `now + 20 phut`
dap luc vao PB. Moc thoi gian KHONG PHAI TRANG THAI (L1b). LEADER co `finally: ... = 0.0` nen
thoat duoc; MEMBER tu accept loi moi (`_on_dungeon`) chi SET moc, KHONG CO CHO NAO HA.

CA THAT party 44 (tp601 = leader, tp602..605 = member):
    10:36:51 [tp601] (LEADER) === PHO BAN TO DOI LV110: tao + moi 4 member ===
    10:38:29 [tp601] THOAT PHO BAN TO DOI (C:047-010) - khong relogin      <- PB xong sau 98 giay
    10:38:30 [tp601] khong o trong pho ban to doi (map=12001) -> KHONG gui C:047-010
    10:39:39 [tp602] go_to_town: DANG TRONG pho ban to doi (map=12001) -> khong teleport
    10:49:59 [tp604] go_to_town: DANG TRONG pho ban to doi (map=12001) -> khong teleport
12001 = Cua thanh Trac Quan. Chinh con so in trong dong log da noi no khong o PB nao.

Ca party nam moi dua mot thanh [12001, 14001], dieu phoi ra lenh gom moi 3 phut tu 10:38 den 10:54
(REFORM gen 4->9) ma khong acc nao di duoc - `go_to_town` tu choi teleport suot 18 phut con lai
cua moc 20 phut.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient, TEAM_DUNGEON_MAPS

THANH_TRAC_QUAN = 12001
MAP_PB_LV110 = 62013


def _c(map_id):
    c = GameClient.__new__(GameClient)
    c._label = "tp604"
    c.current_map = map_id
    return c


class TestDocMapThat(unittest.TestCase):
    def test_dung_trong_map_PB_thi_TRUE(self):
        for m in sorted(TEAM_DUNGEON_MAPS):
            self.assertTrue(_c(m).in_team_dungeon(), m)

    def test_dung_o_THANH_thi_FALSE(self):
        """Ca that p44: dung o 12001 ma bao 'dang trong pho ban to doi'."""
        self.assertFalse(_c(THANH_TRAC_QUAN).in_team_dungeon())

    def test_map_train_thi_FALSE(self):
        for m in (21812, 21833, 21864, 14001):
            self.assertFalse(_c(m).in_team_dungeon(), m)

    def test_instance_KHAC_khong_phai_PB_to_doi(self):
        """62001 la PB DON - thoat bang lenh khac (`C:013-004`), xem go_to_town."""
        self.assertFalse(_c(62001).in_team_dungeon())

    def test_chua_biet_map_thi_FALSE(self):
        self.assertFalse(_c(None).in_team_dungeon())
        self.assertFalse(_c(0).in_team_dungeon())


class TestKhongCongDongHoNua(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_khong_con_ai_DOC_moc_thoi_gian(self):
        for _xau in ('time.time() < getattr(self, "_team_dungeon_until"',
                     'now < getattr(self, "_team_dungeon_until"'):
            self.assertNotIn(_xau, self.src, "moc thoi gian song lai: %s" % _xau)

    def test_khong_con_ai_GHI_moc_thoi_gian(self):
        """Doc bang AST - `_team_dungeon_until` van duoc KE LAI trong docstring lich su, hop le."""
        import ast
        ghi = []
        for node in ast.walk(ast.parse(self.src)):
            if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                continue
            for tgt in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                if isinstance(tgt, ast.Attribute) and tgt.attr == "_team_dungeon_until":
                    ghi.append(node.lineno)
        self.assertEqual(ghi, [], "con cho GHI moc thoi gian (dong %s)" % ghi)

    def test_khong_con_hang_so_20_phut(self):
        self.assertNotIn("TEAM_DUNGEON_DURATION", self.src)

    def test_ham_doc_map_that_chu_khong_phai_dong_ho(self):
        """Bo docstring (ke lai lich su) roi moi soi phan CODE."""
        import ast
        for node in ast.walk(ast.parse(self.src)):
            if isinstance(node, ast.FunctionDef) and node.name == "in_team_dungeon":
                than = node.body[1:] if ast.get_docstring(node) else node.body
                ma = "\n".join(ast.dump(n) for n in than)
                self.assertIn("TEAM_DUNGEON_MAPS", ma)
                self.assertNotIn("time", ma, "van con doan theo dong ho")
                return
        self.fail("mat in_team_dungeon")


class TestMemberCungThoatDuoc(unittest.TestCase):
    """Goc benh: LEADER co duong ha co, MEMBER thi khong. Doc map that thi ca hai giong nhau."""

    def test_member_ra_khoi_PB_la_biet_ngay(self):
        c = _c(MAP_PB_LV110)
        self.assertTrue(c.in_team_dungeon())
        c.current_map = THANH_TRAC_QUAN        # server doi scene -> ve thanh
        self.assertFalse(c.in_team_dungeon(),
                         "ra khoi PB roi van tu nhan dang trong PB -> ket o thanh nhu p44")


if __name__ == "__main__":
    unittest.main()
