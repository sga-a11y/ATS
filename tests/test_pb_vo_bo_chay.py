"""PB TO DOI VO (co acc van giua PB) -> CA PARTY bo chay khoi tran dang danh roi THOAT PB.

User chot 07/10: *"truong hop co dua vang vi bat ky ly do gi thi cho thoat het PB, nho la neu dang
danh do tran thi chuyen qua bo chay de thoat tran da"*.

Ca that 07/10 party 4 (thba leader, thbon/thnam/thsau/minh):
    15:00:34 [minh] SERVER NGAT KET NOI: DANG NHAP TRUNG LAP (ma 19)
    15:01:35 [party 4] ENGINE: sga014 -> thoat_pb          <- 1 phut sau, het tran 3 moi giao
    15:01:35 [thba] (LEADER) PB110 tran 4: bat dau          <- leader KHONG nghe, danh tiep
    15:02:11 [thba] (LEADER) PB110: VAO TRAN 4/5            <- mot minh, toi 15:12
Ket qua: thba + minh (relogin roi vao lai instance) trong PB, 3 member ngoai thanh 11 phut.

Goc: engine moi goi `do_team_dungeon` KHONG cam `_td_party_broken` -> `_td_party_gone` luon False
("DONG DOI ROT giua pho ban" 0 lan trong ca party.log ngay 07/10). Va acc dang danh thi engine doi
`thoat_pb` thanh `nghi` -> ngoi danh het tran moi thoat.

Sua: engine bat `_pb_bo_chay` thang len client (L1 mot cho quyet, L2 doc/ghi thang):
  * luot danh -> BO CHAY, ke ca dang trong party (flee_mode thuong thi KHONG bo chay trong party)
  * kich ban PB cua leader -> `_td_party_gone` tra True -> dung ngay
  * ra khoi PB / phien moi -> ha co, lan vao PB sau phai DANH
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C           # noqa: E402
from bot import config                # noqa: E402
from bot import party_engine as E     # noqa: E402
from bot.state import BattleState     # noqa: E402

MAP_PB = 62013
MAP_THANH = 23001


def _anh_cap():
    return E.AnhCapParty(can_lap_doi=False, lech_tu=None, het_lech_tu=None,
                         o_thanh_tu=None, bay_gio=1)


class _Fake:
    running = True
    _pe_xong_chore = True
    _pe_xong_daily = True
    current_channel = 1
    party_members = ()
    mission_steps_loaded = False
    bag_counts = {}

    def __init__(self, map_id, dang_danh=False):
        self.current_map = map_id
        self._dang_danh = dang_danh

    def in_combat(self):
        return self._dang_danh

    def in_di_gioi(self):
        return False

    def in_team_dungeon(self):
        return C.in_instance_map(self.current_map)

    def digioi_minutes_live(self):
        return 0

    def kenh_dang_chac(self):
        return True


class _Worker:
    def __init__(self, client):
        self.client = client
        self.sent = []

    def dang_ban(self):
        return False

    def giao(self, viec):
        self.sent.append(viec)
        return True


def _engine(rows):
    eng = E.PartyEngine(0, lambda: rows, doc_party=_anh_cap, ap_dung_party=lambda *_: None)
    for u, c, _l in rows:
        if c is not None:
            eng.workers[u] = _Worker(c)
    return eng


class TestEngineBatCoBoChay(unittest.TestCase):
    def test_acc_van_giua_PB_thi_MOI_acc_trong_PB_bat_co_ke_ca_dang_danh(self):
        leader = _Fake(MAP_PB, dang_danh=True)
        m1 = _Fake(MAP_PB, dang_danh=True)
        m2 = _Fake(MAP_PB)
        eng = _engine([("thba", leader, True), ("thbon", m1, False), ("thnam", m2, False),
                       ("minh", None, False)])
        eng.nhip()
        for c in (leader, m1, m2):
            self.assertTrue(getattr(c, "_pb_bo_chay", False))

    def test_acc_da_o_NGOAI_PB_khong_bat_co(self):
        trong = _Fake(MAP_PB)
        ngoai = _Fake(MAP_THANH)
        eng = _engine([("thba", trong, True), ("thbon", ngoai, False), ("minh", None, False)])
        eng.nhip()
        self.assertTrue(getattr(trong, "_pb_bo_chay", False))
        self.assertFalse(getattr(ngoai, "_pb_bo_chay", False))

    def test_DU_party_thi_khong_bat_co(self):
        """Khong ai van -> PB dang chay binh thuong, cam bo chay oan."""
        a = _Fake(MAP_PB)
        b = _Fake(MAP_PB)
        eng = _engine([("thba", a, True), ("thbon", b, False)])
        eng.nhip()
        self.assertFalse(getattr(a, "_pb_bo_chay", False))
        self.assertFalse(getattr(b, "_pb_bo_chay", False))


def _client(map_id=MAP_PB, party=("x",)):
    c = C.GameClient.__new__(C.GameClient)
    c._label = "t"
    c.current_map = map_id
    c.party_members = list(party)
    c.flee_mode = False
    c._pb_bo_chay = False
    c._td_party_broken = None
    return c


class TestLeaderDungKichBan(unittest.TestCase):
    def test_co_bo_chay_thi_party_gone(self):
        c = _client()
        self.assertFalse(c._td_party_gone("thu"))
        c._pb_bo_chay = True
        self.assertTrue(c._td_party_gone("thu"))

    def test_callback_duong_cu_van_chay(self):
        c = _client()
        c._td_party_broken = lambda: True
        self.assertTrue(c._td_party_gone("thu"))


class TestLuotDanhBoChay(unittest.TestCase):
    def _turn(self, map_id, bo_chay, flee_mode=False, party=("x",)):
        c = _client(map_id, party)
        c._pb_bo_chay = bo_chay
        c.flee_mode = flee_mode
        c._acted_turn = False
        c._gate_transit = False
        c.party_idx = 0
        c.in_team_dungeon = lambda: C.in_instance_map(map_id)
        c._in_battle_end_grace = lambda: False
        c._log_battle_verbose = lambda: False
        st = BattleState()
        st.char.hp_max = st.char.hp = 100
        st.pet.hp_max = st.pet.hp = 100
        st.my_atype = 2
        c.state = st
        c.available = {config.UNIT_CHAR: [(2, 2)], config.UNIT_PET: [(2, 2)]}
        c._first_turn = False
        sent = []
        c._send_combat = sent.append
        try:
            c._make_decisions()
        except Exception:
            pass      # nhanh DANH can them state - chi can biet co gui lenh bo chay hay khong
        return [d.skill for d in sent]

    def test_PB_vo_TRONG_PARTY_van_bo_chay(self):
        self.assertEqual(self._turn(MAP_PB, bo_chay=True),
                         [config.SKILL_FLEE, config.SKILL_FLEE])

    def test_khong_co_co_thi_trong_party_KHONG_bo_chay(self):
        """flee_mode cu giu nguyen: trong party thi danh (bo chay tran party bi day khoi party)."""
        self.assertNotIn(config.SKILL_FLEE,
                         self._turn(MAP_PB, bo_chay=False, flee_mode=True))

    def test_co_sot_lai_NGOAI_PB_thi_khong_bo_chay(self):
        self.assertNotIn(config.SKILL_FLEE, self._turn(MAP_THANH, bo_chay=True))


class TestHaCoKhiRaKhoiPB(unittest.TestCase):
    def test_da_o_ngoai_thi_ha_co(self):
        c = _client(MAP_THANH)
        c._pb_trong_phong = False
        c._pb_bo_chay = True
        self.assertTrue(c.leave_team_dungeon())
        self.assertFalse(c._pb_bo_chay)

    def test_ra_khoi_map_PB_thi_ha_co(self):
        c = _client(MAP_PB)
        c._pb_trong_phong = False
        c._pb_bo_chay = True
        c.running = True

        def _send(op, data):
            c.current_map = MAP_THANH        # server day ra thanh
        c.send = _send
        self.assertTrue(c.leave_team_dungeon(wait=2.0))
        self.assertFalse(c._pb_bo_chay)


if __name__ == "__main__":
    unittest.main()
