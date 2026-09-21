# -*- coding: utf-8 -*-
"""PHO BAN TO DOI: DU MEMBER THEO CONFIG PARTY moi duoc START.

User 21/09 (party 17): "chua du pt sao da start PB, start roi thi moi nguoi khac the deo nao dc
nua", roi chi ro: "client hoan toan biet ro member nao da vao room, member nao da ready, du de
biet du member chua truoc khi start, m tra lai crack client di".

Log (lap lai suot tu 06:04 den 00:03 hom sau):
    00:03:43 (LEADER) member ready 4/4 sau 2.0s -> START
    00:03:56 (LEADER) roster phong pho ban chi 2/4 member -> THIEU nguoi, HUY danh de gom lai

`ready 4/4` la BOT TU BAO: member accept xong bat `Timer(2.5s)` roi tu danh dau ready, KHONG doi
server xac nhan da vao phong. Accept fail am tham (member lech kenh) thi van bao ready.

CRACK CLIENT (`_lua_dec/Logic/Dungeon.lua` + `Common/protocal.lua`): client giu
`dungeonNowRoomPlayers`, cap nhat bang BA goi - day la so THAT cua server:
    S:047-003 (0x2f/03) <加入房間結果>   +ket qua(1) +phong(4) +SO NGUOI(1) + danh sach
    S:047-013 (0x2f/0d) <通知某人加入房間> +RoleID(8) + ten...
    S:047-010 (0x2f/0a) <通知某人離開房間> +RoleID(8)
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestCuaStart(unittest.TestCase):
    """`needed` = so MEMBER (khong ke leader) -> phong phai co `needed + 1` nguoi."""

    def test_du_ready_nhung_phong_THIEU_thi_KHONG_start(self):
        self.assertFalse(C._team_dungeon_can_start(4, 4, 99.0, 0, room_count=3),
                         "dung ca that p17: ready 4/4 ma server chi cong nhan 2-3 -> khong duoc start")

    def test_du_ready_VA_du_phong_thi_start(self):
        self.assertTrue(C._team_dungeon_can_start(4, 4, 99.0, 0, room_count=5))

    def test_CHUA_BIET_so_phong_thi_giu_hanh_vi_CU(self):
        """None = ban cu / chua doc duoc goi -> khong duoc ket cung, van cho start nhu truoc."""
        self.assertTrue(C._team_dungeon_can_start(4, 4, 99.0, 0, room_count=None))

    def test_thieu_ready_thi_van_KHONG_start(self):
        self.assertFalse(C._team_dungeon_can_start(3, 4, 99.0, 0, room_count=5))

    def test_grace_whitelist_van_giu(self):
        self.assertFalse(C._team_dungeon_can_start(4, 4, 1.0, 2, room_count=5),
                         "co whitelist thi van phai doi grace")


class TestDemNguoiThat(unittest.TestCase):
    def setUp(self):
        C._DUNGEON_ROOM.clear()

    def test_tao_phong_thi_LEADER_tu_tinh_la_mot(self):
        C.reset_dungeon_room(7, b"\x01" * 8)
        self.assertEqual(C.dungeon_room_count(7), 1, "leader la chu phong, phai dem chinh no")

    def test_chua_biet_thi_ZERO(self):
        self.assertEqual(C.dungeon_room_count(99), 0)

    def test_moi_nguoi_VAO_thi_tang(self):
        C.reset_dungeon_room(7, b"\x01" * 8)
        with C._PARTY_LOCK:
            C._DUNGEON_ROOM[7].add(b"\x02" * 8)
        self.assertEqual(C.dungeon_room_count(7), 2)

    def test_cung_mot_nguoi_vao_HAI_LAN_khong_dem_doi(self):
        C.reset_dungeon_room(7, b"\x01" * 8)
        with C._PARTY_LOCK:
            C._DUNGEON_ROOM[7].add(b"\x02" * 8)
            C._DUNGEON_ROOM[7].add(b"\x02" * 8)
        self.assertEqual(C.dungeon_room_count(7), 2, "dem theo RoleID nen goi lap lai khong sai so")


class TestDocGoiCuaServer(unittest.TestCase):
    """Neo theo SUB-OPCODE lay tu crack client - boc nham sub la dem nham nguoi."""

    def setUp(self):
        s = _doc("bot", "client.py")
        i = s.find("    def _on_dungeon(self")
        self.than = s[i:s.find("\n    def ", i + 10)]

    def test_doc_047_013_nguoi_VAO(self):
        self.assertIn("sub == 0x0d", self.than)
        self.assertIn("S:047-013", self.than)

    def test_doc_047_010_nguoi_RA(self):
        self.assertIn("sub == 0x0a", self.than)
        self.assertIn("S:047-010", self.than)

    def test_doc_047_003_ket_qua_vao_phong(self):
        self.assertIn("sub == 0x03", self.than)
        self.assertIn("S:047-003", self.than)

    def test_RoleID_lay_dung_8_BYTE_sau_sub(self):
        """`+RoleID(8)` ngay sau 2 byte sub -> body[2:10]."""
        self.assertIn("body[2:10]", self.than)


class TestKhongStartKhiHetGio(unittest.TestCase):
    """Het gio cho ma server chua cong nhan du -> HUY, khong START. Start roi thi khong moi
    them duoc ai nua."""

    def setUp(self):
        self.src = _doc("bot", "client.py")

    def test_ca_hai_duong_deu_co_cua(self):
        self.assertEqual(self.src.count("SERVER moi cong nhan %d/%d nguoi trong phong"), 2,
                         "lv20 va lv50/80/110 la hai ham rieng - thieu mot cai la thung")

    def test_cua_dat_TRUOC_lenh_START(self):
        i = self.src.find("SERVER moi cong nhan %d/%d nguoi trong phong")
        j = self.src.find('self.send(0x2f, b"\\x0c\\x00")', i)
        self.assertGreater(j, i, "cua dat SAU khi da start thi vo nghia")

    def test_dem_lai_tu_dau_moi_lan_tao_phong(self):
        self.assertEqual(self.src.count("reset_dungeon_room(self.party_idx, self.self_entity)"), 2,
                         "khong reset -> nguoi cua lan tao phong TRUOC van con trong so dem")


if __name__ == "__main__":
    unittest.main()
