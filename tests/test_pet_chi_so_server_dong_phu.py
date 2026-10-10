"""Chi so pet phai lay PHAN TRANG BI tu server (S:008-002), khong tu tinh tu ban mau Item.dat.

User bao 08/10: "agi cua pet bi hien thieu so voi game". Client KHONG tu tinh EquipX cua pet
(`Status.GetAgi` doc thang `EAttribute.EquipAgi`, server day qua S:008-002 humanKind=4). So do da
gom dong phu 洗鍊/升階/專武/天官 ma `pet_stats.json` khong co. Doi chieu 10 pcap: ban VTC do thuong
khop het; `tsm_quangam_20261001` slot3 (專武 64573 + 天官 23376) tu tinh Agi 0, server 12.
Kem theo: Int/Atk/Def/Hpx/Spx cua pet chua cong suu tap (client cong ca CollectStyle + CollectCard).
"""
from __future__ import annotations

import json
import os
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from analyze_pcap import load_frames  # noqa: E402
from bot import client as client_module, pet_login_stats  # noqa: E402
from bot.state import BattleState  # noqa: E402

PCAP = os.path.join(ROOT, "captures", "tsm_quangam_20261001.pcap")


def _pkt(body: bytes) -> bytes:
    return b"\x00" * 7 + body


def _goi_0802(human, slot, kind, value):
    sign = 2 if value < 0 else 1
    return _pkt(b"\x02\x00" + bytes([human]) + slot.to_bytes(2, "little") + bytes([kind, sign])
                + struct.pack("<i", abs(value)) + b"\x00" * 4)


def _game():
    g = client_module.GameClient.__new__(client_module.GameClient)
    g.state = BattleState()
    g._label = "test"
    g.pet_login_records = {}
    g.pet_equip_server = {}
    g._collect_style_flags = {}
    g._collect_card_equipped = []
    g._collect_card_levels = {}
    g.char_attrs = {}
    return g


def _nap_pcap(g):
    """Nap ban ghi pet (0x0f sub08) + S:008-002 cua pcap TSM, dung thu tu server gui."""
    frames, _ = load_frames(PCAP)
    for f in frames:
        b = f["body"]
        if f["dir"] != "S2C":
            continue
        if f["op"] == 0x0f and b[:2] == b"\x08\x00":
            start = 3
            for _ in range(b[2]):
                r = pet_login_stats.parse_record(b, start)
                if r:
                    g.pet_login_records[b[start]] = r
                start += 254 + b[start + 31]
        elif f["op"] == 0x08 and b[:2] == b"\x02\x00" and len(b) >= 11:
            g._on_pet_equip_attr(_pkt(b))


@unittest.skipUnless(os.path.exists(PCAP), "thieu pcap TSM")
class TestPcapTSM(unittest.TestCase):
    def test_pet_deo_chuyen_vo_thien_quan_lay_dung_agi_server(self):
        g = _game()
        _nap_pcap(g)
        self.assertEqual(g.pet_equip_server[3][214], 12)
        # base 104 + equip 12 (server). Tu tinh ra 104 -> thieu 12.
        self.assertEqual(g.pet_stats(3)["agi"], 116)

    def test_cac_chi_so_khac_cung_lay_so_server(self):
        g = _game()
        _nap_pcap(g)
        rec = g.pet_login_records[3]
        ps = g.pet_stats(3)
        self.assertEqual(ps["atk"], rec["atk"] + 67)
        self.assertEqual(ps["def"], rec["def"] + 6)
        self.assertEqual(ps["int"], rec["int"] + 3)
        self.assertEqual(ps["hpx"], rec["hpx"] + 3)
        self.assertEqual(ps["spx"], rec["spx"] + 2)

    def test_pet_khong_co_goi_server_van_tu_tinh(self):
        """Slot 2/4 khong mac gi -> server khong gui; so tu tinh van giu nguyen."""
        g = _game()
        _nap_pcap(g)
        self.assertNotIn(2, g.pet_equip_server)
        self.assertEqual(g.pet_stats(2)["agi"], g.pet_login_records[2]["agi"])


class TestGoi0802(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "pet_stats.json"), encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_so_am_theo_byte_dau(self):
        g = _game()
        g._on_pet_equip_attr(_goi_0802(4, 1, 214, -10))
        self.assertEqual(g.pet_equip_server[1][214], -10)

    def test_bo_qua_khong_phai_pet(self):
        g = _game()
        g._on_pet_equip_attr(_goi_0802(1, 1, 214, 9))
        g._on_pet_equip_attr(_goi_0802(4, 1, 25, 900))   # HP hien tai, khong phai EquipX
        self.assertEqual(g.pet_equip_server, {})

    def test_server_ghi_de_so_tu_tinh(self):
        rec = {"id": 41050, "agi": 70, "equipment": [
            {"id": 15098, "element": 0, "element_value": 0, "stone_attr": 0, "stone_lv": 0}]}
        self.assertEqual(pet_login_stats.calculate_agi(rec, self.data), 74)       # tu tinh +4
        self.assertEqual(pet_login_stats.calculate_agi(rec, self.data, server_equip={214: 16}), 86)

    def test_pet_xuat_chien_cap_nhat_agi_nhung_KHONG_nap_lai_hp(self):
        """Giua phien server day lai EquipAgi -> pet_agi doi; HP/SP dang chay giu nguyen."""
        g = _game()
        g._active_pet_login = {
            "marker": 1, "id": 41050, "level": 117, "hp": 1054, "sp": 82, "agi": 70,
            "hpx": 94, "spx": 26, "hp_pill": 0, "sp_pill": 0,
            "equipment": [{"id": 0, "element": 0, "element_value": 0, "stone_attr": 0,
                           "stone_lv": 0} for _ in range(6)]}
        g._refresh_active_pet_login_stats()
        self.assertEqual(g.pet_agi, 70)
        g.state.pet.hp = 500
        g._on_pet_equip_attr(_goi_0802(4, 1, 214, 12))
        self.assertEqual(g.pet_agi, 82)
        self.assertEqual(g.state.pet.hp, 500)

    def test_int_atk_def_hpx_spx_pet_cong_suu_tap(self):
        g = _game()
        g.pet_login_records[1] = {
            "id": 41050, "level": 117, "hp": 1, "sp": 1, "int": 44, "atk": 175, "def": 85,
            "agi": 70, "hpx": 94, "spx": 26, "hp_pill": 0, "sp_pill": 0,
            "equipment": [{"id": 0, "element": 0, "element_value": 0, "stone_attr": 0,
                           "stone_lv": 0} for _ in range(6)]}
        bonus = {27: 2, 28: 2, 29: 2, 30: 1, 31: 1, 32: 1}   # moc 22 diem thoi trang
        with patch.object(pet_login_stats, "style_attribute",
                          side_effect=lambda d, f, k: bonus.get(k, 0)):
            ps = g.pet_stats(1)
        self.assertEqual((ps["int"], ps["atk"], ps["def"], ps["agi"], ps["hpx"], ps["spx"]),
                         (46, 177, 87, 71, 95, 27))


PCAP_LOGIN = os.path.join(ROOT, "captures", "pet_login_stats_20260804.pcap")


def _replay_char(path):
    """Cho TOAN BO goi S2C cua pcap di qua _dispatch that (0x05, 0x4f, 0x5f, 0x51...)."""
    g = client_module.GameClient("user", "token")
    g.send = lambda *a, **k: None
    frames, _ = load_frames(path)
    for f in frames:
        if f["dir"] != "S2C":
            continue
        body = f["body"]
        pkt = b"\xc0\x91" + struct.pack("<H", len(body) + 7) + b"\x00\x00" + bytes([f["op"]]) + body
        g._dispatch(f["op"], pkt)
    return g


@unittest.skipUnless(os.path.exists(PCAP_LOGIN), "thieu pcap login")
class TestChiSoCharDayDu(unittest.TestCase):
    """Char Atk/Def/Hpx/Spx truoc 08/10 = goc + do (thieu thoi trang/the/thu cuoi/chuyen sinh 3).

    So UI game ghi trong KNOWLEDGE (char lv148): INT/ATK/DEF/AGI/HPX/SPX = 311/3/13/76/1/1.
    Ban cu ra ATK 0, DEF 10: thieu thoi trang ATK+2/DEF+2 (pet_stats.json loc mat kind 28/29) va
    thu cuoi `floor((base 1 + EquipX) * 1.01)` (ATK 1, DEF 1+8=9).
    """

    def test_khop_dung_bang_chi_so_trong_game(self):
        full = _replay_char(PCAP_LOGIN).char_stat_full()
        self.assertEqual([full[k] for k in (27, 28, 29, 30, 31, 32)], [311, 3, 13, 76, 1, 1])

    def test_tach_thanh_phan(self):
        g = _replay_char(PCAP_LOGIN)
        self.assertEqual(g._char_cong_ngoai_do(28), {"turn3": 0, "style": 2, "card": 0, "horse": 1})
        self.assertEqual(g._char_cong_ngoai_do(29), {"turn3": 0, "style": 2, "card": 0, "horse": 9})
        # Status.GetHpx/GetSpx khong co dong Mounts.
        self.assertEqual(g._char_cong_ngoai_do(31)["horse"], 0)


@unittest.skipUnless(os.path.exists(PCAP), "thieu pcap tsm_quangam")
class TestThuTuGoiLogin(unittest.TestCase):
    """BL-1008-0B07 "van ko dung agi voi ingame": login that ra `PL -> S:008-002 -> 0x13`; 0x13 doc
    lai goi pet-list cache, ma reset pet_equip_server nam trong _on_pet_list -> xoa sach so server.
    Test cu goi thang _on_pet_equip_attr nen khong bat duoc - test nay di qua _dispatch that."""

    def test_so_server_con_sau_0x13(self):
        g = _replay_char(PCAP)
        self.assertEqual(g._active_pet_login["marker"], 3)
        self.assertEqual(g.pet_equip_server.get(3, {}).get(214), 12)
        self.assertEqual(g.pet_agi, 119)   # tu tinh 107 = thieu 12 cua 專武/天官


class TestDuLieu(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "pet_stats.json"), encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_thoi_trang_va_the_co_du_atk_def(self):
        kinds = {k for _s, attrs in self.data["style_values"] for k, _v in attrs}
        self.assertTrue({28, 29} <= kinds, "pet_stats.json loc mat Atk/Def thoi trang")
        kinds = {a[0] for attrs in self.data["cards"].values() for a in attrs}
        self.assertTrue({28, 29} <= kinds, "pet_stats.json loc mat Atk/Def the")

    def test_linh_thach_atk_def(self):
        """Item.StoneAttrKind = {212, 210, 211, 218, 219, 214}: loai 2/3 la Atk/Def."""
        rec = {"equipment": [{"id": 0, "element": 0, "element_value": 0,
                              "stone_attr": 2, "stone_lv": 7}]}
        self.data["items"]["0"] = {"a": [], "e": 0, "ev": 0, "k": 0, "s": 0}
        self.assertEqual(pet_login_stats.equipment_bonus(rec, self.data, 0)[210], 9)

    def test_tu_tinh_atk_def_tu_do(self):
        """Truoc: bang do khong co 210/211 -> Atk/Def tu do luon 0. pcap ts_lglogin slot1 server
        gui Atk 16 / Def 34; do 20006,19006,12006,21206,22017,23006."""
        rec = {"equipment": [{"id": i, "element": 0, "element_value": 0, "stone_attr": 0,
                              "stone_lv": 0} for i in (20006, 19006, 12006, 21206, 22017, 23006)]}
        b = pet_login_stats.equipment_bonus(rec, self.data, 4)
        self.assertEqual((b[210], b[211], b[214]), (16, 34, -7))


if __name__ == "__main__":
    unittest.main()
