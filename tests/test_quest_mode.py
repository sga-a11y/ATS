# -*- coding: utf-8 -*-
"""MODE "LAM QUEST" - khung (user chot 03/10/2026, documents/QUEST_CHUYEN_SINH.md).

  - luon chay theo party, user CHI DINH chu party (khong mac dinh acc dau danh sach)
  - chu party lam quest, member chi dung trong doi ho tro
  - chu xong het -> chi dinh acc DAU TIEN (thu tu danh sach) chua xong lam chu
  - ca party xong het -> thoat game
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R
from bot import config, party_engine as PE, party_modes, quest_runner as Q
from bot.client import GameClient

CH = Q.chuoi("cs1_cu_thu")


class FakeClient:
    """Co nhiem vu y het GameClient (mark_flag_get 1-based cua client that)."""
    mark_flag_get = GameClient.mark_flag_get

    def __init__(self, xong_bits=(), loaded=True, steps=None):
        self._mark_flags_loaded = loaded
        self.mark_flags = {}
        for b in xong_bits:
            i = int(b) - 1
            self.mark_flags[i // 8 + 1] = self.mark_flags.get(i // 8 + 1, 0) | (1 << (i % 8))
        if loaded and not self.mark_flags:
            self.mark_flags = {999: 0}     # da nhan bang co nhung chua xong gi
        self.mission_steps = dict(steps or {})
        self._label = "fake"


def _all_bits():
    return [q["bit"] for q in CH["quests"]]


class TestDataQuest(unittest.TestCase):
    def test_du_8_quest_bat_dai_cu_thu(self):
        self.assertIsNotNone(CH)
        ids = [q["id"] for q in CH["quests"]]
        # User chot theo ten trong game 03/10 (KNOWLEDGE.md muc NHIEM VU)
        self.assertEqual(ids, [10324, 10326, 10328, 10360, 10384, 10528, 10564, 10806])
        self.assertEqual(_all_bits(), [174, 175, 176, 192, 204, 280, 298, 428])

    def test_quests_json_dong_goi_ca_exe_lan_apk(self):
        import build_product
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import sync_apk_python
        self.assertIn("quests.json", build_product.DATA_JSON)
        self.assertIn("quests.json", sync_apk_python.SHARED_ASSETS)
        self.assertIn("quest_runner.py", sync_apk_python.SHARED)


class TestTrangThai(unittest.TestCase):
    def test_chua_nhan_co_la_chua_biet(self):
        self.assertIsNone(Q.xong_het(FakeClient(loaded=False), CH))
        self.assertIsNone(Q.xong_het(None, CH))

    def test_xong_het_va_con_quest(self):
        self.assertTrue(Q.xong_het(FakeClient(_all_bits()), CH))
        self.assertFalse(Q.xong_het(FakeClient(_all_bits()[:-1]), CH))

    def test_quest_dang_lam_duoc_uu_tien(self):
        # xong quest 1, dang lam quest 5 buoc 2 -> lam tiep quest 5 chu khong quay ve quest 2
        c = FakeClient([174], steps={10384: 2})
        q, step = Q.quest_tiep_theo(c, CH)
        self.assertEqual((q["id"], step), (10384, 2))

    def test_chua_nhan_quest_nao_thi_lay_quest_dau_DA_CO_KICH_BAN(self):
        # xong 10324/10326/10328/10360/10384 -> quest tiep theo co kich ban la 10528 (Thai Ho)
        q, step = Q.quest_tiep_theo(FakeClient([174, 175, 176, 192, 204]), CH)
        self.assertEqual((q["id"], step), (10528, None))

    def test_du_8_quest_deu_co_kich_ban(self):
        self.assertTrue(all(q["kich_ban"] for q in CH["quests"]))
        q, step = Q.quest_tiep_theo(FakeClient([174, 175, 176, 192, 204, 280, 298]), CH)
        self.assertEqual((q["id"], step), (10806, None))

    def test_het_quest_co_kich_ban_thi_khong_lam_gi(self):
        c = FakeClient(_all_bits())
        self.assertEqual(Q.quest_tiep_theo(c, CH), (None, None))
        self.assertEqual(Q.con_thieu_kich_ban(c, CH), [])

    def test_diem_nhan_va_buoc_lay_dung_kich_ban(self):
        q = next(x for x in CH["quests"] if x["id"] == 10528)
        n = Q._diem(q, None)
        self.assertEqual((n["scene"], n["x"], n["y"], n["kieu"], n["idx"]),
                         (18001, 1310, 250, "npc", 4))
        b2 = Q._diem(q, 2)
        self.assertEqual((b2["scene"], b2["kieu"], b2["idx"], b2["chon"]), (18506, "npc", 1, [30]))
        self.assertEqual(b2["truoc"], [{"cua": 3, "x": 3651, "y": 365}])

    def test_buoc_chi_co_toa_do_chua_capture_thi_chua_lam(self):
        q = next(x for x in CH["quests"] if x["id"] == 10328)   # B2 chua capture (ev_kind 0)
        self.assertIsNone(Q._diem(q, 2))

    def test_nhan_quest_bang_cua_an(self):
        q = next(x for x in CH["quests"] if x["id"] == 10328)
        n = Q._diem(q, None)
        self.assertEqual((n["scene"], n["kieu"], n["idx"], n["chon"]), (56501, "cua", 4, [30]))

    def test_buoc_chi_co_toa_do_la_cua_an_theo_capture(self):
        q = next(x for x in CH["quests"] if x["id"] == 10324)
        b3 = Q._diem(q, 3)
        self.assertEqual((b3["scene"], b3["x"], b3["y"], b3["kieu"], b3["idx"], b3["chon"]),
                         (13519, 1760, 1000, "cua", 2, [30]))


class TestChonChuParty(unittest.TestCase):
    TT = ["a", "b", "c", "d"]

    def test_chu_con_quest_thi_giu(self):
        self.assertEqual(Q.chon_chu_party(self.TT, {"a": True, "b": False}, "b"), ("giu", "b"))

    def test_chu_xong_chi_dinh_acc_dau_tien_con_quest_theo_thu_tu(self):
        tt = {"a": True, "b": True, "c": False, "d": False}
        self.assertEqual(Q.chon_chu_party(self.TT, tt, "b"), ("doi", "c"))

    def test_ca_party_xong_thi_thoat(self):
        tt = {u: True for u in self.TT}
        self.assertEqual(Q.chon_chu_party(self.TT, tt, "a"), ("thoat", None))

    def test_chua_biet_thi_cho_khong_doan(self):
        # acc d dang login (chua nhan co) -> KHONG duoc ket luan ca party xong
        tt = {"a": True, "b": True, "c": True, "d": None}
        self.assertEqual(Q.chon_chu_party(self.TT, tt, "a"), ("cho", None))
        # chu chua biet -> cho, du da co acc chac chan con quest
        self.assertEqual(Q.chon_chu_party(self.TT, {"a": None, "b": False}, "a"), ("cho", None))


def _acc(u, la_leader=False, map_id=12061, so_member=0, song=True, dang_danh=False):
    return PE.AnhAcc(u, la_leader=la_leader, song=song, map_id=map_id, so_member=so_member,
                     dang_danh=dang_danh)


class TestDecideModeQuest(unittest.TestCase):
    def _run(self, accs, base=None):
        base = base or {a.username: "nghi" for a in accs}
        return party_modes.decide_mode("quest", base, accs, target_map=12061)

    def test_du_doi_chu_lam_quest_member_dung_trong_doi(self):
        accs = [_acc("b", True, map_id=56517, so_member=2), _acc("a", so_member=2),
                _acc("c", so_member=2)]
        self.assertEqual(self._run(accs), {"b": "quest", "a": "nghi", "c": "nghi"})

    def test_chua_du_doi_tai_thanh_tap_ket_thi_lap_party(self):
        accs = [_acc("b", True), _acc("a"), _acc("c")]
        self.assertEqual(set(self._run(accs).values()), {"lap_party"})

    def test_chua_du_doi_lech_map_thi_ve_thanh_tap_ket(self):
        accs = [_acc("b", True), _acc("a", map_id=12001), _acc("c")]
        self.assertEqual(self._run(accs)["a"], "city")

    def test_chu_trong_doi_thieu_nguoi_van_phai_gom(self):
        # mode city cho "trong doi" = nghi (dang theo nguoi khac keo); mode quest chu party thieu
        # nguoi thi van phai moi/gom - L0
        accs = [_acc("b", True, map_id=56517, so_member=1), _acc("a", so_member=1),
                _acc("c", map_id=12001)]
        r = self._run(accs)
        self.assertEqual(r["b"], "city")
        self.assertEqual(r["a"], "nghi")

    def test_dang_danh_thi_nghi(self):
        accs = [_acc("b", True, so_member=1, dang_danh=True), _acc("a", so_member=1)]
        self.assertEqual(self._run(accs)["b"], "nghi")

    def test_quest_la_viec_ban_thi_cho(self):
        self.assertIn("quest", PE.BAN_THI_CHO)


class TestChiDinhChuParty(unittest.TestCase):
    PIDX = 991

    def setUp(self):
        while len(config.PARTIES) <= self.PIDX:
            config.PARTIES.append([])
        self._old = (config.PARTIES[self.PIDX], dict(config.PARTY_CONFIG),
                     dict(config.PARTY_LEADER_ACC))
        config.PARTIES[self.PIDX] = [("a", "pa"), ("b", "pb"), ("c", "pc")]
        config.PARTY_CONFIG[self.PIDX] = {"mode": "quest", "quest_key": "cs1_cu_thu",
                                          "quest_leader": "b"}
        config.PARTY_LEADER_ACC[self.PIDX] = "a"

    def tearDown(self):
        config.PARTIES[self.PIDX] = self._old[0]
        config.PARTY_CONFIG.clear(); config.PARTY_CONFIG.update(self._old[1])
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._old[2])

    def test_acc_chi_dinh_len_slot_0_khong_phai_acc_dau(self):
        R._ap_chu_party_quest(self.PIDX)
        self.assertEqual(config.PARTY_LEADER_ACC[self.PIDX], "b")
        self.assertEqual([u for u, _ in config.PARTIES[self.PIDX]], ["b", "a", "c"])
        lead = [u for u, _p, la, _pk in R.party_accounts(self.PIDX) if la]
        self.assertEqual(lead, ["b"])
        # mat khau di theo dung acc
        self.assertEqual(dict(config.PARTIES[self.PIDX])["b"], "pb")

    def test_xoay_vong_giu_thu_tu_goc(self):
        R._ap_chu_party_quest(self.PIDX)
        R._ap_chu_party_quest(self.PIDX, "c")
        self.assertEqual(config.PARTY_LEADER_ACC[self.PIDX], "c")
        self.assertEqual(config.PARTY_CONFIG[self.PIDX]["_quest_thu_tu"], ["a", "b", "c"])

    def test_chu_khong_co_trong_party_thi_lay_acc_dau(self):
        config.PARTY_CONFIG[self.PIDX]["quest_leader"] = "zz"
        R._ap_chu_party_quest(self.PIDX)
        self.assertEqual(config.PARTY_LEADER_ACC[self.PIDX], "a")

    def test_mode_khac_khong_dung_vao(self):
        config.PARTY_CONFIG[self.PIDX]["mode"] = "train"
        R._ap_chu_party_quest(self.PIDX)
        self.assertEqual(config.PARTY_LEADER_ACC[self.PIDX], "a")
        self.assertEqual([u for u, _ in config.PARTIES[self.PIDX]], ["a", "b", "c"])


class TestDieuPhoiQuest(unittest.TestCase):
    PIDX = 992

    def setUp(self):
        R._party_state.pop(self.PIDX, None)
        self.cfg = {"mode": "quest", "quest_key": "cs1_cu_thu", "_quest_thu_tu": ["a", "b", "c"]}
        self._lead = dict(config.PARTY_LEADER_ACC)
        config.PARTY_LEADER_ACC[self.PIDX] = "a"

    def tearDown(self):
        R._party_state.pop(self.PIDX, None)
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._lead)

    def _chay(self, clients):
        with mock.patch.object(R, "_clients_cua_party", return_value=list(clients.items())), \
                mock.patch.object(R.threading, "Thread") as th, \
                mock.patch.object(R, "stop_account") as stop:
            ket = R._quest_dieu_phoi(self.PIDX, self.cfg)
        return ket, th, stop

    def test_chu_xong_thi_chi_dinh_acc_ke_tiep(self):
        ket, th, stop = self._chay({"a": FakeClient(_all_bits()), "b": FakeClient([174]),
                                    "c": FakeClient()})
        self.assertTrue(ket)
        self.assertEqual(th.call_args.kwargs["args"], (self.PIDX, "b"))
        stop.assert_not_called()

    def test_ca_party_xong_thi_thoat_game(self):
        ket, th, stop = self._chay({u: FakeClient(_all_bits()) for u in "abc"})
        self.assertTrue(ket)
        th.assert_not_called()
        self.assertEqual(sorted(c.args[0] for c in stop.call_args_list), ["a", "b", "c"])

    def test_chu_con_quest_thi_lam_tiep(self):
        ket, th, stop = self._chay({"a": FakeClient([174]), "b": FakeClient(_all_bits()),
                                    "c": FakeClient()})
        self.assertFalse(ket)
        th.assert_not_called()
        stop.assert_not_called()

    def test_acc_dang_login_thi_cho(self):
        ket, th, stop = self._chay({"a": FakeClient(_all_bits()), "b": FakeClient(_all_bits()),
                                    "c": None})
        self.assertFalse(ket)
        stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class _ClientBuoc(FakeClient):
    """Client gia cho lam_buoc: ghi lai thu tu thao tac; su kien NPC xong -> mission +1."""

    def __init__(self, map_id, steps=None, len_buoc=True):
        super().__init__([], steps=steps)
        self.current_map = map_id
        self.running = True
        self.len_buoc = len_buoc
        self.goi = []

    def _wait_combat_clear(self, idle=1.0, cap=90.0):
        return True

    def follow_smart_route(self, dest, safe, abort=None, flee=True):
        self.goi.append(("tele+route", dest, safe))
        self.current_map = dest
        return True

    def navigate_to(self, x, y, abort=None, flee=True):
        self.goi.append(("di", x, y))

    def quest_kich_hoat(self, kieu, idx):
        self.goi.append((kieu, idx))
        self._kieu = kieu

    def quest_hoi_thoai(self, chon=(), abort=None, im_lang=60.0, toi_da=600.0):
        self.goi.append(("thoai", list(chon)))
        if self._kieu == "npc" and self.len_buoc:
            self.mission_steps[10528] = self.mission_steps.get(10528, 0) + 1
        return "xong"


class TestLamBuoc(unittest.TestCase):
    Q = staticmethod(lambda: next(x for x in CH["quests"] if x["id"] == 10528))

    def test_khac_map_thi_tele_route_roi_cham_cua_truoc_npc(self):
        c = _ClientBuoc(12001, steps={10528: 2})
        self.assertTrue(Q.lam_buoc(c, self.Q(), 2))
        self.assertEqual(c.goi, [("tele+route", 18506, (3660, 360)),
                                 ("di", 3651, 365), ("cua", 3), ("thoai", []),
                                 ("di", 3660, 360), ("npc", 1), ("thoai", [30])])

    def test_cung_map_thi_di_bo_thang(self):
        c = _ClientBuoc(18001)
        self.assertTrue(Q.lam_buoc(c, self.Q(), None))
        self.assertEqual(c.goi[0], ("di", 1310, 250))
        self.assertEqual(c.mission_steps[10528], 1)

    def test_server_khong_len_buoc_thi_bao_hong(self):
        c = _ClientBuoc(18301, steps={10528: 1}, len_buoc=False)
        self.assertFalse(Q.lam_buoc(c, self.Q(), 1))


class TestThanhTapKet(unittest.TestCase):
    """User 03/10: KHONG co o chon thanh - gom ve thanh gan buoc ke tiep cua chu party."""
    PIDX = 994

    def setUp(self):
        R._party_state.pop(self.PIDX, None)
        self._lead = dict(config.PARTY_LEADER_ACC)
        config.PARTY_LEADER_ACC[self.PIDX] = "a"
        self.cfg = {"mode": "quest", "quest_key": "cs1_cu_thu"}

    def tearDown(self):
        R._party_state.pop(self.PIDX, None)
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._lead)

    def _thanh(self, client, router_city=13001):
        router = mock.Mock()
        router.build_route.return_value = {"city": router_city, "flag": 2}
        with mock.patch.dict(R.account_clients, {"a": client}), \
                mock.patch("bot.client._smart_world_router", return_value=router):
            return R._quest_thanh_tap_ket(self.PIDX, self.cfg), router

    def test_theo_diem_nhan_quest_dau_tien(self):
        th, router = self._thanh(FakeClient())
        self.assertEqual(th, (13001, 2))
        # chua nhan quest nao -> Thien Doc, nhan o Quan tro Uyen Thanh 13243
        self.assertEqual(router.build_route.call_args.args, (13243, (190, 470)))

    def test_theo_buoc_dang_lam(self):
        th, router = self._thanh(FakeClient([174], steps={10326: 1}), router_city=11011)
        self.assertEqual(th, (11011, 2))
        self.assertEqual(router.build_route.call_args.args[0], 58000)   # Phan No Cua Bien B1

    def test_chu_chua_nhan_co_thi_chua_co_thanh(self):
        th, router = self._thanh(FakeClient(loaded=False))
        self.assertIsNone(th)
        router.build_route.assert_not_called()

    def test_quest_mode_khong_dung_start_city_id(self):
        # decide_mode nhan dich gom tu _quest_thanh_tap_ket, khong phai start_city_id cu
        src = open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()
        self.assertIn("_th = _quest_thanh_tap_ket(pidx, pcfg)", src)


class TestKhongTanDoiGiuaDuong(unittest.TestCase):
    """Log party 7, 04/10 (lap 4/4 vong):
        03:12:43 [party 7] ENGINE: taot006 -> nghi          <- dinh tran quai o 15402 giua duong
        03:12:43 [ttsau] navigate_to: abort (reform moi/stop) -> dung
        03:12:59 [ttsau] Teleport: dang o to doi (4 member) -> ROI DOI truoc
    """

    def test_chu_dang_lam_quest_dinh_tran_thi_giu_quest(self):
        lead = PE.AnhAcc("b", la_leader=True, map_id=15402, so_member=1, dang_danh=True,
                         dang_ban=True, viec_dang_lam="quest")
        r = party_modes.decide_mode("quest", {"b": "nghi", "a": "nghi"},
                                    [lead, _acc("a", map_id=15402, so_member=1)],
                                    target_map=15001)
        self.assertEqual(r["b"], "quest")

    def test_dinh_tran_ma_khong_dang_lam_quest_thi_van_nghi(self):
        lead = PE.AnhAcc("b", la_leader=True, so_member=1, dang_danh=True, dang_ban=False,
                         viec_dang_lam="quest")
        r = party_modes.decide_mode("quest", {"b": "nghi"}, [lead], target_map=12061)
        self.assertEqual(r["b"], "nghi")

    def test_engine_mien_tru_quest_dang_lam_do(self):
        src = open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8").read()
        self.assertIn('("route_source", "route_dest", "quest")', src)

    def _client(self, cur, walk_legs):
        c = mock.Mock()
        c.current_map = cur
        c.build_smart_scene_route.return_value = (None if walk_legs is None
                                                  else {"legs": [0] * walk_legs})
        return c

    def _di_bo(self, c, tele_city, tele_legs):
        router = mock.Mock()
        router.build_route.return_value = {"city": tele_city, "legs": [0] * tele_legs}
        with mock.patch("bot.client._smart_world_router", return_value=router):
            return Q._di_bo_tiep(c, 13243, 190, 470)

    def test_giua_duong_di_bo_tiep_khong_tele(self):
        # o 15402: con 3 cong toi dich; tele ve 15001 phai di 7 cong -> di bo
        self.assertTrue(self._di_bo(self._client(15402, 3), 15001, 7))

    def test_di_bo_xa_hon_thi_tele(self):
        self.assertFalse(self._di_bo(self._client(19000, 12), 15001, 7))

    def test_dang_o_thanh_xuat_phat_thi_de_follow_smart_route(self):
        self.assertFalse(self._di_bo(self._client(15001, 7), 15001, 7))

    def test_khong_co_duong_di_bo_thi_tele(self):
        self.assertFalse(self._di_bo(self._client(15402, None), 15001, 7))
