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
        # Thu To B2 (ev_kind 0, chua capture rieng) cung toa do cua 2 cua B1 -> dung lai cua 2
        q = next(x for x in CH["quests"] if x["id"] == 10328)
        self.assertEqual(Q._diem(q, 2)["idx"], 2)
        # buoc khong co toa do trung cua nao -> van chua lam
        fake = {"id": 1, "steps": {"1": {"scene": 1, "x": 1, "y": 1, "ev_kind": 0, "ev_id": 0}}}
        self.assertIsNone(Q._diem(fake, 1))

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
        return True

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

    def test_khac_map_thi_KHONG_tu_di_cho_lenh_di_map(self):
        c = _ClientBuoc(12001, steps={10528: 2})
        self.assertFalse(Q.lam_buoc(c, self.Q(), 2))
        self.assertEqual(c.goi, [])

    def test_dung_map_thi_cham_cua_truoc_roi_npc(self):
        c = _ClientBuoc(18506, steps={10528: 2})
        self.assertTrue(Q.lam_buoc(c, self.Q(), 2))
        self.assertEqual(c.goi, [("di", 3660, 360),
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




def _acc(u, la_leader=False, map_id=12061, so_member=0, song=True, dang_danh=False, **kw):
    return PE.AnhAcc(u, la_leader=la_leader, song=song, map_id=map_id, so_member=so_member,
                     dang_danh=dang_danh, **kw)


class TestDecideQuest(unittest.TestCase):
    """Viec tung acc khi khong co lenh DI MAP dang chay (di chuyen do lenh DI MAP co san lo)."""

    def _r(self, accs, trang_thai):
        return party_modes.decide_quest({a.username: "nghi" for a in accs}, accs,
                                        trang_thai=trang_thai)

    def test_toi_noi_du_doi_chu_lam_member_dung(self):
        accs = [_acc("b", True, so_member=1), _acc("a", so_member=1)]
        self.assertEqual(self._r(accs, "lam"), {"b": "quest", "a": "nghi"})

    def test_toi_noi_chua_du_doi_thi_lap_party(self):
        accs = [_acc("b", True), _acc("a")]
        self.assertEqual(set(self._r(accs, "moi").values()), {"lap_party"})

    def test_dang_cho_lenh_di_map_thi_nghi(self):
        accs = [_acc("b", True), _acc("a")]
        self.assertEqual(set(self._r(accs, "cho").values()), {"nghi"})

    def test_chu_dang_lam_quest_dinh_tran_thi_giu_quest(self):
        # log party 7, 04/10: doi sang `nghi` = huy giua chung
        lead = _acc("b", True, so_member=1, dang_danh=True, dang_ban=True, viec_dang_lam="quest")
        self.assertEqual(self._r([lead, _acc("a", so_member=1)], "lam")["b"], "quest")

    def test_dinh_tran_khong_dang_lam_quest_thi_nghi(self):
        lead = _acc("b", True, so_member=1, dang_danh=True)
        self.assertEqual(self._r([lead], "lam")["b"], "nghi")

    def test_viec_uu_tien_giu_nguyen(self):
        accs = [_acc("b", True), _acc("a")]
        r = party_modes.decide_quest({"b": "daily", "a": "login_chore"}, accs, trang_thai="lam")
        self.assertEqual(r, {"b": "daily", "a": "login_chore"})

    def test_decide_mode_khong_con_nhanh_quest(self):
        accs = [_acc("b", True)]
        self.assertEqual(party_modes.decide_mode("quest", {"b": "train"}, accs), {"b": "train"})

    def test_engine_mien_tru_quest_dang_lam_do(self):
        src = open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8").read()
        self.assertIn('("route_source", "route_dest", "quest")', src)
        self.assertIn("quest", PE.BAN_THI_CHO)


class TestDenDichBangLenhDiMap(unittest.TestCase):
    """User 04/10: "moi co che deu co san ... m dung lai hay code moi". Mode quest dua doi toi map
    buoc quest bang lenh DI MAP co san: party_route_maps(thanh CA PARTY da mo gan nhat, map)."""
    PIDX = 996

    def setUp(self):
        R._party_state.pop(self.PIDX, None)
        self._lead = dict(config.PARTY_LEADER_ACC)
        config.PARTY_LEADER_ACC[self.PIDX] = "a"
        self.cfg = {"mode": "quest", "quest_key": "cs1_cu_thu"}

    def tearDown(self):
        R._party_state.pop(self.PIDX, None)
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._lead)

    def _goi(self, accs, clients, city=15001):
        anh = SimpleNamespace(accs=accs)
        with mock.patch.dict(R.account_clients, {"a": clients["a"]}), \
                mock.patch.object(R, "_clients_cua_party", return_value=list(clients.items())), \
                mock.patch.object(R, "_pick_start_city", return_value=city) as pick, \
                mock.patch.object(R, "party_route_maps") as route:
            return R._quest_den_dich(self.PIDX, anh, self.cfg), pick, route

    def test_chua_o_map_thi_ra_lenh_di_map_tu_thanh_da_mo(self):
        # chua nhan quest nao -> Thien Doc, nhan o Quan tro Uyen Thanh 13243
        accs = [_acc("a", True, map_id=12061), _acc("b", map_id=12061)]
        kq, pick, route = self._goi(accs, {"a": FakeClient(), "b": FakeClient()})
        self.assertEqual(kq, "cho")
        self.assertEqual(pick.call_args.args, (self.PIDX, 13243))
        route.assert_called_once_with(self.PIDX, 15001, 13243)

    def test_khong_ra_lenh_lien_tuc(self):
        accs = [_acc("a", True, map_id=12061), _acc("b", map_id=12061)]
        cl = {"a": FakeClient(), "b": FakeClient()}
        self._goi(accs, cl)
        _kq, _pick, route = self._goi(accs, cl)
        route.assert_not_called()

    def test_member_chua_vao_world_thi_chua_ra_lenh(self):
        # party 27, 04/10: chot thanh khi moi 1/5 acc vao -> member chua mo thanh do
        accs = [_acc("a", True, map_id=12061), _acc("b", map_id=None, song=False)]
        kq, pick, route = self._goi(accs, {"a": FakeClient(), "b": None})
        self.assertEqual(kq, "cho")
        pick.assert_not_called()
        route.assert_not_called()

    def test_ca_doi_o_map_du_doi_thi_lam(self):
        accs = [_acc("a", True, map_id=13243, so_member=1), _acc("b", map_id=13243, so_member=1)]
        kq, _pick, route = self._goi(accs, {"a": FakeClient(), "b": FakeClient()})
        self.assertEqual(kq, "lam")
        route.assert_not_called()

    def test_ca_doi_o_map_chua_du_doi_thi_moi(self):
        accs = [_acc("a", True, map_id=13243), _acc("b", map_id=13243)]
        kq, _pick, route = self._goi(accs, {"a": FakeClient(), "b": FakeClient()})
        self.assertEqual(kq, "moi")
        route.assert_not_called()

    def test_party_route_maps_cho_phep_mode_quest(self):
        src = open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()
        self.assertIn('if mode not in ("city", "stand", "quest"):', src)
        self.assertNotIn("_quest_thanh_tap_ket", src)
        self.assertNotIn("_di_bo_tiep", open(os.path.join(ROOT, "bot", "quest_runner.py"),
                                              encoding="utf-8").read())


class TestDoiChuTaiCho(unittest.TestCase):
    """User 04/10: "thang nao xong roi van online de ho tro", chi thoat khi CA party xong.
    Log party 3/4/5 04/10: doi chu = STOP ca 5 acc + start lai; dung hut thi party tat han:
        17:21:21 [sga017..chihao188] STOP: Quest: doi chu party -> sga018
        17:03:25 [party 3] QUEST: 120s van con acc chua dung [...] -> KHONG start lai
    """
    PIDX = 997

    def setUp(self):
        while len(config.PARTIES) <= self.PIDX:
            config.PARTIES.append([])
        self._old = (config.PARTIES[self.PIDX], dict(config.PARTY_CONFIG),
                     dict(config.PARTY_LEADER_ACC))
        config.PARTIES[self.PIDX] = [("a", "pa"), ("b", "pb"), ("c", "pc")]
        config.PARTY_CONFIG[self.PIDX] = {"mode": "quest", "quest_key": "cs1_cu_thu",
                                          "quest_leader": "a"}
        config.PARTY_LEADER_ACC[self.PIDX] = "a"
        R._party_state.pop(self.PIDX, None)

    def tearDown(self):
        config.PARTIES[self.PIDX] = self._old[0]
        config.PARTY_CONFIG.clear(); config.PARTY_CONFIG.update(self._old[1])
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._old[2])
        R._party_state.pop(self.PIDX, None)

    def test_doi_chu_khong_stop_acc_nao(self):
        cl = {u: mock.Mock(_pe_la_leader=(u == "a")) for u in "abc"}
        R._pstate(self.PIDX)["quest_ket_thuc"] = True
        with mock.patch.object(R, "_clients_cua_party", return_value=list(cl.items())), \
                mock.patch.dict(R.account_clients, cl), \
                mock.patch.object(R, "stop_account") as stop, \
                mock.patch.object(R, "start_party") as start:
            R._quest_doi_chu(self.PIDX, "b")
        stop.assert_not_called()
        start.assert_not_called()
        self.assertEqual(config.PARTY_LEADER_ACC[self.PIDX], "b")
        self.assertEqual({u: c._pe_la_leader for u, c in cl.items()},
                         {"a": False, "b": True, "c": False})
        cl["a"].leave_party.assert_called_once()        # chu cu roi doi -> doi cu tan
        cl["b"].leave_party.assert_not_called()
        self.assertFalse(R._pstate(self.PIDX)["quest_ket_thuc"])   # dieu phoi chay tiep

    def test_engine_doc_vai_leader_tu_config_moi_nhip(self):
        src = open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()
        self.assertIn("lambda _p=pidx: [(u, cl, u == config.PARTY_LEADER_ACC.get(_p))", src)


class TestKhongDiMapKhiDangSuKien(unittest.TestCase):
    """Log party 11, 04/10: len buoc (0x18 sub01) toi TRUOC khi su kien het -> ra lenh DI MAP ngay
    -> huy hoi thoai giua chung -> chu ket trong su kien, tele bi nuot:
        17:35:49 [luusau] QUEST: Sâm Lan Thái Hồ buoc 1 -> su kien dung, buoc 1 -> 2
        17:35:50.. [luusau] Teleport -> city 12001   (moi 2s, ket o Quan Phu 18301)
    """
    PIDX = 998

    def setUp(self):
        R._party_state.pop(self.PIDX, None)
        self._lead = dict(config.PARTY_LEADER_ACC)
        config.PARTY_LEADER_ACC[self.PIDX] = "a"

    def tearDown(self):
        R._party_state.pop(self.PIDX, None)
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._lead)

    def test_chu_dang_lam_quest_thi_khong_ra_lenh_di_map(self):
        accs = [_acc("a", True, map_id=18301, so_member=1, dang_ban=True, viec_dang_lam="quest"),
                _acc("b", map_id=18301, so_member=1)]
        c = FakeClient([174, 175, 176, 192, 204], steps={10528: 2})   # buoc 2 o 18506
        with mock.patch.dict(R.account_clients, {"a": c}), \
                mock.patch.object(R, "_clients_cua_party", return_value=[("a", c), ("b", c)]), \
                mock.patch.object(R, "party_route_maps") as route:
            kq = R._quest_den_dich(self.PIDX, SimpleNamespace(accs=accs),
                                   {"mode": "quest", "quest_key": "cs1_cu_thu"})
        self.assertEqual(kq, "lam")
        route.assert_not_called()


class TestParty13BotHai(unittest.TestCase):
    """Log party 13, 04/10:
        17:25:44 [tonba] QUEST: Phẫn Nộ Của Biển buoc 1 -> su kien dung, buoc 1 -> 2
        -> ket buoc 2 (chua kich ban), ca party `nghi` o Bot Hai ~30 phut, roster 0/4.
    """
    PIDX = 999

    def setUp(self):
        R._party_state.pop(self.PIDX, None)
        self._lead = dict(config.PARTY_LEADER_ACC)
        config.PARTY_LEADER_ACC[self.PIDX] = "a"
        self.cfg = {"mode": "quest", "quest_key": "cs1_cu_thu"}

    def tearDown(self):
        R._party_state.pop(self.PIDX, None)
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._lead)

    def _goi(self, accs, c):
        with mock.patch.dict(R.account_clients, {"a": c}), \
                mock.patch.object(R, "_clients_cua_party", return_value=[("a", c), ("b", c)]), \
                mock.patch.object(R, "party_route_maps") as route:
            return R._quest_den_dich(self.PIDX, SimpleNamespace(accs=accs), self.cfg), route

    def test_buoc_gop_ket_dung_lai_cua_cung_toa_do(self):
        q = next(x for x in CH["quests"] if x["id"] == 10326)
        d = Q._diem(q, 2)                         # B2 data ev_kind 0 tai (2207,282) = cua 2 cua B1
        self.assertEqual((d["scene"], d["kieu"], d["idx"]), (58000, "cua", 2))
        q2 = next(x for x in CH["quests"] if x["id"] == 10328)
        self.assertEqual(Q._diem(q2, 4)["idx"], 5)   # Thu To B4 = cua 5 cua B3

    def test_ket_buoc_2_o_bot_hai_thi_lap_doi_roi_lam(self):
        c = FakeClient([174], steps={10326: 2})
        accs = [_acc("a", True, map_id=58000), _acc("b", map_id=58000)]
        kq, route = self._goi(accs, c)
        self.assertEqual(kq, "moi")               # truoc day "cho" -> ca party nghi
        route.assert_not_called()

    def test_chu_dang_lam_quest_kiem_truoc_moi_nhanh(self):
        c = FakeClient([174, 175, 176, 192, 204, 280, 298], steps={})   # khong con gi lam
        accs = [_acc("a", True, map_id=58000, dang_ban=True, viec_dang_lam="quest")]
        kq, _route = self._goi(accs, c)
        self.assertEqual(kq, "lam")

    def test_cho_ma_cung_map_chua_du_doi_van_lap_doi(self):
        c2 = FakeClient(loaded=False)             # chu chua nhan co -> chua biet buoc -> d None
        accs = [_acc("a", True, map_id=58000), _acc("b", map_id=58000)]
        kq, _route = self._goi(accs, c2)
        self.assertEqual(kq, "moi")


class TestLuatToiThuongL0(unittest.TestCase):
    """RULE_DIEU_PHOI L0: "du party roi lam gi thi lam; party hong thi phai gom lai BANG DUOC".
    Mode quest KHONG duoc co nhanh de party le dung im (party 13, 04/10: 0/4 suot ~30 phut)."""
    PIDX = 993

    def setUp(self):
        R._party_state.pop(self.PIDX, None)
        self._lead = dict(config.PARTY_LEADER_ACC)
        config.PARTY_LEADER_ACC[self.PIDX] = "a"
        self.cfg = {"mode": "quest", "quest_key": "cs1_cu_thu"}

    def tearDown(self):
        R._party_state.pop(self.PIDX, None)
        config.PARTY_LEADER_ACC.clear(); config.PARTY_LEADER_ACC.update(self._lead)

    def _goi(self, accs, c):
        with mock.patch.dict(R.account_clients, {"a": c}), \
                mock.patch.object(R, "_clients_cua_party", return_value=[("a", c), ("b", c)]), \
                mock.patch.object(R, "_pick_start_city", return_value=11011), \
                mock.patch.object(R, "party_route_maps") as route:
            return R._quest_den_dich(self.PIDX, SimpleNamespace(accs=accs), self.cfg), route

    def test_khong_co_buoc_lam_duoc_khac_map_thi_gom_ve_cho_chu(self):
        c = FakeClient(_all_bits())                       # chu xong het -> khong co buoc
        accs = [_acc("a", True, map_id=58000), _acc("b", map_id=12001)]
        kq, route = self._goi(accs, c)
        self.assertEqual(kq, "cho")
        route.assert_called_once_with(self.PIDX, 11011, 58000)

    def test_khong_co_buoc_lam_duoc_du_doi_thi_giu_doi_dung_cho(self):
        c = FakeClient(_all_bits())
        accs = [_acc("a", True, map_id=58000, so_member=1), _acc("b", map_id=12001, so_member=1)]
        kq, route = self._goi(accs, c)
        self.assertEqual(kq, "cho")
        route.assert_not_called()

    def test_moi_nhanh_chua_du_doi_deu_gom_hoac_moi(self):
        c = FakeClient([174], steps={10326: 2})
        for accs in ([_acc("a", True, map_id=58000), _acc("b", map_id=58000)],
                     [_acc("a", True, map_id=12001), _acc("b", map_id=18001)]):
            R._party_state.pop(self.PIDX, None)
            kq, route = self._goi(accs, c)
            self.assertTrue(kq == "moi" or route.called, (kq, accs))
