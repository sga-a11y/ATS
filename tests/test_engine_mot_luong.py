import threading
import time
import unittest

from bot import party_engine as E
from bot.party_route import decide_route


def _anh_cap():
    return E.AnhCapParty(can_lap_doi=False, lech_tu=None, het_lech_tu=None,
                        o_thanh_tu=None, bay_gio=1)


class _Client:
    running = True
    _pe_xong_chore = True
    _pe_xong_daily = True
    current_map = 12001
    current_channel = 1
    party_members = ()
    mission_steps_loaded = False
    bag_counts = {}

    def in_combat(self):
        return False

    def in_di_gioi(self):
        return False

    def in_team_dungeon(self):
        return False

    def digioi_minutes_live(self):
        return 0

    def kenh_dang_chac(self):
        return getattr(self, "channel_certain", True)


class _Worker:
    def __init__(self):
        self.sent = []

    def dang_ban(self):
        return False

    def giao(self, viec):
        self.sent.append(viec)
        return True


class TestMotLuongQuyetDinh(unittest.TestCase):
    def test_snapshot_khong_tu_quyet_va_tick_ap_dung_truoc_khi_chup(self):
        calls = []
        client = _Client()
        eng = E.PartyEngine(
            0, lambda: [("u", client, True)],
            doc_party=lambda: (calls.append("doc_party") or _anh_cap()),
            ap_dung_party=lambda anh, viec, ly_do, hu: calls.append(("apply", viec)),
        )
        eng.chup()
        self.assertEqual(calls, [])
        original_chup = eng.chup

        def observed_chup():
            calls.append("chup")
            return original_chup()

        eng.chup = observed_chup
        eng.nhip()
        self.assertEqual(calls[:3], ["doc_party", ("apply", E.DP_LAM), "chup"])

    def test_snapshot_loi_khong_giao_lenh_cu(self):
        client = _Client()
        eng = E.PartyEngine(0, lambda: [("u", client, True)],
                            doc_party=lambda: (_ for _ in ()).throw(ValueError("snapshot")),
                            ap_dung_party=lambda *_: None)
        sent = []
        eng.workers["u"] = type("Worker", (), {"giao": lambda self, v: sent.append(v)})()
        with self.assertRaisesRegex(ValueError, "snapshot"):
            eng.nhip()
        self.assertEqual(sent, [])

    def test_effect_loi_khong_giao_lenh_cu(self):
        client = _Client()
        eng = E.PartyEngine(0, lambda: [("u", client, True)],
                            doc_party=_anh_cap,
                            ap_dung_party=lambda *_: (_ for _ in ()).throw(ValueError("effect")))
        sent = []
        eng.workers["u"] = type("Worker", (), {"giao": lambda self, v: sent.append(v)})()
        with self.assertRaisesRegex(ValueError, "effect"):
            eng.nhip()
        self.assertEqual(sent, [])

    def test_restart_va_relogin_khong_nhan_doi_worker_chet(self):
        c1, c2 = _Client(), _Client()
        current = [c1]
        eng = E.PartyEngine(0, lambda: [("u", current[0], True)])
        eng._th = threading.current_thread()
        eng.start()
        old = eng.workers["u"]
        old.stop()
        current[0] = c2
        eng.start()
        self.assertIsNot(eng.workers["u"], old)
        self.assertIs(eng.workers["u"].client, c2)

    def test_kenh_dich_chi_giao_worker_lech_hoac_khong_chac(self):
        clients = [_Client(), _Client(), _Client()]
        clients[0].current_channel = 1
        clients[1].current_channel = 2
        clients[2].current_channel = 2
        clients[2].channel_certain = False
        names = ("left", "right", "uncertain")
        eng = E.PartyEngine(0, lambda: [(u, c, i == 0) for i, (u, c) in
                                         enumerate(zip(names, clients))],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            doc_kenh_dich=lambda: 2)
        eng.workers = {u: _Worker() for u in names}
        decisions = eng.nhip()
        self.assertEqual(decisions["left"], E.VIEC_DOI_KENH)
        self.assertEqual(decisions["right"], E.VIEC_TRAIN)
        self.assertEqual(decisions["uncertain"], E.VIEC_DOI_KENH)

    def test_lenh_tay_va_tran_khong_bi_lenh_kenh_de_len(self):
        client = _Client()
        client.current_channel = 1
        client._lenh_tay_kenh_dang_chay = True
        eng = E.PartyEngine(0, lambda: [("u", client, True)],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            doc_kenh_dich=lambda: 2)
        eng.workers["u"] = _Worker()
        self.assertNotEqual(eng.nhip()["u"], E.VIEC_DOI_KENH)
        client._lenh_tay_kenh_dang_chay = False
        client.in_combat = lambda: True
        self.assertNotEqual(eng.nhip()["u"], E.VIEC_DOI_KENH)

    def test_kenh_nho_trung_nhung_khong_chac_van_gui_switch(self):
        client = _Client()
        client.current_channel = 2
        client.channel_certain = False
        sent = []
        client.switch_channel = lambda target, **kw: (sent.append((target, kw)) or True)
        self.assertTrue(E.thi_hanh(client, E.VIEC_DOI_KENH, lambda: True, dich=2))
        self.assertEqual(sent[0][0], 2)

    def test_mode_action_chay_tren_worker_hien_co(self):
        client = _Client()
        calls = []
        eng = E.PartyEngine(0, lambda: [], mode_action_fn=lambda c, action, can:
                            (calls.append((c, action, can())) or True))
        eng._lam_viec(client, "city", lambda: True)
        eng._lam_viec(client, "route_dest", lambda: True)
        eng._lam_viec(client, "boss_quan_doan", lambda: True)
        self.assertEqual(calls, [(client, "city", True), (client, "route_dest", True),
                                 (client, "boss_quan_doan", True)])

    def test_lenh_tay_da_lam_xong_khong_chan_kenh_mai(self):
        client = _Client()
        client.current_channel = 1
        client._pe_lenh_tay_gen = 3
        eng = E.PartyEngine(0, lambda: [("u", client, True)],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            doc_kenh_dich=lambda: 2, doc_lenh_tay=lambda: 3)
        eng.workers["u"] = _Worker()
        self.assertEqual(eng.nhip()["u"], E.VIEC_DOI_KENH)

    def test_mode_khong_duoc_gui_lenh_di_chuyen_giua_tran(self):
        client = _Client()
        client.in_combat = lambda: True
        eng = E.PartyEngine(0, lambda: [("u", client, True)],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            mode_fn=lambda anh, viec: {"u": "route_dest"})
        eng.workers["u"] = _Worker()
        self.assertEqual(eng.nhip()["u"], E.VIEC_NGHI)

    def test_boss_da_chay_tiep_tuc_qua_tran_nhung_khong_khoi_dong_moi(self):
        client = _Client()
        client.in_combat = lambda: True
        eng = E.PartyEngine(0, lambda: [("u", client, True)],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            mode_fn=lambda anh, viec: {"u": "boss_quan_doan"})
        worker = _Worker()
        eng.workers["u"] = worker
        self.assertEqual(eng.nhip()["u"], E.VIEC_NGHI)
        eng.viec_hien_tai["u"] = "boss_quan_doan"
        worker.dang_ban = lambda: True
        self.assertEqual(eng.nhip()["u"], "boss_quan_doan")

    def test_route_dang_chay_khong_bi_huy_vi_member_tam_lech_map(self):
        leader, follower = _Client(), _Client()
        follower.current_map = 12002
        plan = {"users": ("leader", "follower"), "source": 12001,
                "dest": 13000, "city": 10000, "phase": "dest", "lag_since": None}

        def route_mode(anh, viec):
            result = decide_route(plan, anh.accs, "leader", joined_members=1, now=10)
            plan["phase"], plan["lag_since"] = result.phase, result.lag_since
            return result.actions

        eng = E.PartyEngine(0, lambda: [("leader", leader, True),
                                        ("follower", follower, False)],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            mode_fn=route_mode)
        worker = _Worker()
        worker.dang_ban = lambda: True
        eng.workers["leader"] = worker
        eng.viec_hien_tai["leader"] = "route_dest"
        self.assertEqual(eng.nhip()["leader"], "route_dest")
        self.assertEqual(plan["phase"], "dest")

    def test_route_busy_giu_trong_tran_nhung_khong_bat_dau_moi(self):
        client = _Client()
        client.in_combat = lambda: True
        eng = E.PartyEngine(0, lambda: [("u", client, True)],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            mode_fn=lambda anh, viec: {"u": "route_dest"})
        worker = _Worker()
        eng.workers["u"] = worker
        self.assertEqual(eng.nhip()["u"], E.VIEC_NGHI)
        eng.viec_hien_tai["u"] = "route_dest"
        worker.dang_ban = lambda: True
        self.assertEqual(eng.nhip()["u"], "route_dest")

    def test_thieu_acc_giua_pb_thoat_moi_client_con_trong_instance(self):
        inside = E.AnhAcc("inside", la_leader=True, song=True, map_id=62012,
                          kenh=1, trong_pb=True)
        outside = E.AnhAcc("outside", song=True, map_id=12001, kenh=1)
        missing = E.AnhAcc("missing", song=False)
        anh = E.AnhParty(0, [inside, outside, missing], can_bao_nhieu=2,
                         pha=E.PHA_TRAIN)
        self.assertEqual(E.quyet_dinh(anh), {"inside": E.VIEC_THOAT_PB,
                                           "outside": E.VIEC_NGHI})

    def test_thoat_pb_chay_tren_worker_va_ton_trong_huy_lenh(self):
        client = _Client()
        calls = []
        client.leave_team_dungeon = lambda: (calls.append("exit") or True)
        self.assertFalse(E.thi_hanh(client, E.VIEC_THOAT_PB, lambda: False))
        self.assertEqual(calls, [])
        self.assertTrue(E.thi_hanh(client, E.VIEC_THOAT_PB, lambda: True))
        self.assertEqual(calls, ["exit"])

    def test_mode_khong_de_len_thoat_pb_khi_thieu_acc(self):
        client = _Client()
        client.in_team_dungeon = lambda: True
        eng = E.PartyEngine(0, lambda: [("inside", client, True),
                                        ("missing", None, False)],
                            doc_party=_anh_cap, ap_dung_party=lambda *_: None,
                            mode_fn=lambda anh, viec: {"inside": E.VIEC_TRAIN})
        eng.workers["inside"] = _Worker()
        self.assertEqual(eng.nhip()["inside"], E.VIEC_THOAT_PB)

    def test_placeholder_dang_reconnect_giu_controller_song(self):
        rows = [("u", None, True)]
        eng = E.PartyEngine(0, lambda: rows)
        eng.nhip = lambda: None
        eng.start()
        try:
            time.sleep(0.05)
            self.assertTrue(eng._th.is_alive())
        finally:
            eng.stop()
            eng._th.join(timeout=2)

    def test_stop_roi_start_lai_co_controller_moi(self):
        client = _Client()
        eng = E.PartyEngine(0, lambda: [("u", client, True)])
        eng.nhip = lambda: None
        eng.start()
        eng.stop()
        eng._th.join(timeout=2)
        eng.start()
        try:
            self.assertTrue(eng._th.is_alive())
            self.assertFalse(eng._dung.is_set())
            self.assertFalse(eng.workers["u"]._dung.is_set())
        finally:
            eng.stop()
            eng._th.join(timeout=2)

    def test_start_lai_khi_controller_cu_dang_thoat(self):
        client = _Client()
        entered = threading.Event()
        release = threading.Event()
        eng = E.PartyEngine(0, lambda: [("u", client, True)])

        def slow_tick():
            entered.set()
            release.wait(timeout=2)

        eng.nhip = slow_tick
        eng.start()
        self.assertTrue(entered.wait(timeout=1))
        eng.stop()
        eng.start()
        release.set()
        try:
            deadline = time.time() + 2
            while time.time() < deadline and eng._dung.is_set():
                time.sleep(0.01)
            self.assertFalse(eng._dung.is_set())
            self.assertTrue(eng._th.is_alive())
        finally:
            eng.stop()
            eng._th.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
