"""40NPC NGOAI GIO event: khong gom, khong dong bo kenh. TRONG GIO thi GIU NGUYEN het.

User 09/09: "mode 40npc, ngoai gio event thi chi log vao va di doi thuong roi out, m con phai dong
bo kenh lam lon gi" -> va ngay sau do: "dung co tien tay xoa luon cai dong bo kenh lap pt khi
trong thoi gian event do".

Hai ve, ve nao cung phai dung - nen file nay khoa CA HAI:

  NGOAI GIO -> viec duy nhat cua moi acc la di NPC map 12003 doi 'qua chien dau 40NPC' roi thoat
               game. SOLO. Khong danh, khong lap doi, khong dung chung kenh.
  TRONG GIO -> nguyen ven duong cu: gom map, dong bo kenh, lap party roi danh.

Ca that 09/09 sau 22h - dieu phoi van chay day du cho party da het viec:
    22:00:31 [party 49] gen 26: pha=event map=12003 viec=lam - con lech map [10991, 12003]
    22:00:37 [party 49] gen 27: viec=gom - party dang o 2 MAP khac nhau [10991, 12003]
    22:00:30 [dakbon]   DIEU PHOI GUI doi kenh 2 (dang o 1) -> ket qua 4
    22:00:33 [quanmot]  (LEADER) DIEU PHOI chot kenh 14, minh dang o 1 -> tu chuyen
`12003` CHINH LA map doi thuong, tuc "lech map" luc do la dung y do. Con lenh doi kenh thi keo acc
ra khoi viec no dang lam, va dinh ma 4 (kenh day) nen lap lai mai.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config


class _C:
    def __init__(self, map_id=12003, channel=1, roster=0):
        self.current_map = map_id
        self.current_channel = channel
        self.running = True
        self.party_members = [b"x" * 8] * roster

    def digioi_minutes_live(self):
        return 0.0


class _Nen(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._jmc = R.joined_member_count
        R.joined_member_count = lambda pidx: 0          # doi rong -> co co de "lap lai party"
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self._pcfg = dict(getattr(config, "PARTY_CONFIG", {}))
        self._leader = dict(getattr(config, "PARTY_LEADER_ACC", {}))
        config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "40npc"}}
        config.PARTY_LEADER_ACC = {self.PARTY: "a1"}
        self._evs = dict(getattr(config, "EVENTS", {}) or {})
        config.EVENTS = {"40npc": {"label": "40 NPC",
                                   "party_battle": {"kind": "npc_repeat"}}}
        self._eht = config.event_hom_nay
        config.event_hom_nay = lambda k: config.EVENTS.get("40npc")

    def tearDown(self):
        R.party_accounts = self._pa
        R.joined_member_count = self._jmc
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        config.PARTY_CONFIG = self._pcfg
        config.PARTY_LEADER_ACC = self._leader
        config.EVENTS = self._evs
        config.event_hom_nay = self._eht

    def _song(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c
        return [(u, R.account_clients[u]) for u in self.ACCS if u in R.account_clients]


class TestNgoaiGioThiThoiDieuPhoi(_Nen):
    def setUp(self):
        super().setUp()
        self._win = R.npc40.in_event_window
        R.npc40.in_event_window = lambda *a, **k: False

    def tearDown(self):
        R.npc40.in_event_window = self._win
        super().tearDown()

    def test_nhan_ra_la_ngoai_gio(self):
        self.assertTrue(R._party_40npc_ngoai_gio(self.PARTY, config.PARTY_CONFIG[self.PARTY]))

    def test_lech_map_KHONG_ra_lenh_gom(self):
        """10991 = map event, 12003 = map doi thuong. Lech giua hai cai do la DUNG y do."""
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(10991), a2=_C(12003), a3=_C(12003))
        kh, ly_do, _ = R._dieu_phoi_quyet(self.PARTY, st, song,
                                          lech_tu=1.0)     # lech tu rat lau
        self.assertEqual(kh["viec"], R.VIEC_LAM, ly_do)
        self.assertIn("doi thuong", ly_do)

    def test_lech_kenh_KHONG_chot_kenh_dich(self):
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(12003, 1), a2=_C(12003, 3), a3=_C(12003, 4))
        self.assertIsNone(R._dieu_phoi_chot_kenh(self.PARTY, st, song))
        self.assertIsNone(st.get("kenh_dich"))

    def test_BO_kenh_dich_con_treo_tu_trong_gio(self):
        """22h vua qua: kenh dich chot luc con trong gio phai duoc go, khong keo acc di nua."""
        st = R._pstate(self.PARTY)
        with st["lock"]:
            st["kenh_dich"] = 14
        song = self._song(a1=_C(12003, 1), a2=_C(12003, 3), a3=_C(12003, 4))
        R._dieu_phoi_chot_kenh(self.PARTY, st, song)
        self.assertIsNone(st.get("kenh_dich"))

    def test_doi_rong_cung_KHONG_ra_lenh_lap_lai(self):
        """Acc di doi thuong solo - lap lai party luc nay la keo nhau ve vo nghia."""
        st = R._pstate(self.PARTY)
        gen = st["reform_gen"]
        song = self._song(a1=_C(12003, 1), a2=_C(12003, 1), a3=_C(12003, 1))
        R._dieu_phoi_chot_kenh(self.PARTY, st, song)
        self.assertEqual(st["reform_gen"], gen)


class TestTRONG_GIO_thi_GIU_NGUYEN(_Nen):
    """User chot ro: dung tien tay xoa luon duong trong gio event."""

    def setUp(self):
        super().setUp()
        self._win = R.npc40.in_event_window
        R.npc40.in_event_window = lambda *a, **k: True

    def tearDown(self):
        R.npc40.in_event_window = self._win
        super().tearDown()

    def test_trong_gio_KHONG_bi_coi_la_ngoai_gio(self):
        self.assertFalse(R._party_40npc_ngoai_gio(self.PARTY, config.PARTY_CONFIG[self.PARTY]))

    def test_trong_gio_VAN_chot_kenh_dich(self):
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(10991, 1), a2=_C(10991, 3), a3=_C(10991, 3))
        self.assertIsNotNone(R._dieu_phoi_chot_kenh(self.PARTY, st, song),
                             "xoa mat duong dong bo kenh trong gio event")

    def test_trong_gio_VAN_ra_lenh_gom_khi_lech_map(self):
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(10991), a2=_C(12003), a3=_C(12003))
        kh, ly_do, _ = R._dieu_phoi_quyet(self.PARTY, st, song, lech_tu=1.0)
        self.assertEqual(kh["viec"], R.VIEC_GOM, ly_do)

    def test_trong_gio_VAN_lap_lai_party_khi_doi_tan(self):
        st = R._pstate(self.PARTY)
        gen = st["reform_gen"]
        song = self._song(a1=_C(10991, 1), a2=_C(10991, 1), a3=_C(10991, 1))
        R._dieu_phoi_chot_kenh(self.PARTY, st, song)
        self.assertGreater(st["reform_gen"], gen, "xoa mat duong lap lai party trong gio event")


class TestChiApChoDUNG_MODE(_Nen):
    def setUp(self):
        super().setUp()
        self._win = R.npc40.in_event_window
        R.npc40.in_event_window = lambda *a, **k: False

    def tearDown(self):
        R.npc40.in_event_window = self._win
        super().tearDown()

    def test_party_train_khong_dinh_gi(self):
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}
        self.assertFalse(R._party_40npc_ngoai_gio(self.PARTY, config.PARTY_CONFIG[self.PARTY]))

    def test_event_KHAC_khong_dinh_gi(self):
        """Loan dau (`chaos_vs`) co duong ngoai gio RIENG - khong dung cua nay."""
        config.EVENTS = {"loandau": {"party_battle": {"kind": "chaos_vs"}}}
        config.event_hom_nay = lambda k: config.EVENTS.get("loandau")
        config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "loandau"}}
        self.assertFalse(R._party_40npc_ngoai_gio(self.PARTY, config.PARTY_CONFIG[self.PARTY]))

    def test_2K_khong_dinh_gi(self):
        config.EVENTS = {"2k": {"party_battle": {"kind": "floor_crawl"}}}
        config.event_hom_nay = lambda k: config.EVENTS.get("2k")
        config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "2k"}}
        self.assertFalse(R._party_40npc_ngoai_gio(self.PARTY, config.PARTY_CONFIG[self.PARTY]))


if __name__ == "__main__":
    unittest.main()
