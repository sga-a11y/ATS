"""One party engine owns planning; login and startup never create another controller."""
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class TestPartyControllerRunner(unittest.TestCase):
    def test_invite_worker_does_not_make_its_own_channel_decision(self):
        client = mock.Mock()
        R._invite_party_participants(client, False, gap=0)
        client.switch_channel.assert_not_called()
        client.invite_members.assert_called_once_with(gap=0)

    def test_route_channel_selection_overrides_solo_mode_policy(self):
        clients = [("a", SimpleNamespace(current_map=100, current_channel=1, party_members=[])),
                   ("b", SimpleNamespace(current_map=100, current_channel=2, party_members=[]))]
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_mode_can_lap_doi", return_value=False), \
                mock.patch.object(R, "_dang_doi_kenh", return_value=False), \
                mock.patch.object(R, "_lam_moi_ds_kenh"), \
                mock.patch.object(R, "_bang_kenh", return_value={1: (2, 10), 2: (5, 10)}):
            state = R._pstate(0)
            self.assertEqual(R._engine_chot_kenh(0, state, clients,
                                               {"viec": "dong_bo"}, manual_route=True), 1)

    def test_failed_safe_arrival_defers_login_chores(self):
        client = SimpleNamespace(_username="a", _label="a", _pe_la_leader=False)
        with mock.patch.object(R, "_ra_safe_engine_moi", return_value=False), \
                mock.patch.object(R, "lam_login_chores") as chores:
            self.assertFalse(R._login_chores_engine_moi(client, 0))
        chores.assert_not_called()

    def test_unknown_position_cannot_confirm_safe_arrival(self):
        client = SimpleNamespace(current_map=100, pos=None, party_members=[],
                                 _theo_leader_sua_pos=lambda: False,
                                 _wait_combat_clear=lambda **_: True, navigate_to=lambda *a, **k: None)
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertFalse(R._ra_safe_engine_moi(client, 0))

    def test_account_keepalive_never_decides_to_leave_or_fight(self):
        client = mock.Mock()
        client._doi_truong_dang_ket.return_value = b"stranger"
        client.self_entity = b"self"
        client.in_combat.return_value = False
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"mode": "train"}}, clear=True):
            R._nhip_acc_engine_moi(client, 0)
        client.leave_party.assert_not_called()
        client.do_legion_boss.assert_not_called()

    def test_controller_spot_refresh_never_runs_blocking_scan(self):
        client = SimpleNamespace(current_map=100)
        state = {"lock": R.threading.Lock()}
        with mock.patch.object(R, "_engine_chot_map"), \
                mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.dict(R.config.TRAIN_MAPS, {100: {"mobs": []}}, clear=True), \
                mock.patch.object(R, "_resolve_train_mob_centers", return_value=[]) as scan:
            R._chuan_bi_bai_train(client, state, 0, "a")
        scan.assert_not_called()

    def test_scan_action_observes_cancellation_on_existing_worker(self):
        client = SimpleNamespace(current_map=100)
        with mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.dict(R.config.TRAIN_MAPS, {100: {"mobs": []}}, clear=True), \
                mock.patch.object(R, "_resolve_train_mob_centers", return_value=[(10, 20)]) as scan:
            R._engine_mode_action(0, client, "quet_bai_train", lambda: True)
        self.assertEqual(client._pe_mob_scan, (100, [(10, 20)]))
        self.assertFalse(scan.call_args.kwargs["stop"]())

    def test_manual_route_is_not_marked_done_by_account_executor(self):
        client = SimpleNamespace(_pe_lenh_tay_gen=0)
        with mock.patch.dict(R._party_state, {}, clear=True):
            state = R._pstate(0)
            state.update(cmd=("route", 100, 200), cmd_gen=2)
            self.assertFalse(R._lenh_tay_engine_moi(client, 0))
        self.assertEqual(client._pe_lenh_tay_gen, 0)

    def test_manual_route_completes_only_from_whole_party_arrival(self):
        a = SimpleNamespace(username="a", song=True, dang_danh=False, map_id=12061,
                            kenh=1, lenh_tay_da_lam=0, so_member=1, la_leader=True)
        b = SimpleNamespace(username="b", song=True, dang_danh=False, map_id=12061,
                            kenh=1, lenh_tay_da_lam=0, so_member=0, la_leader=False)
        ca, cb = SimpleNamespace(_pe_lenh_tay_gen=0), SimpleNamespace(_pe_lenh_tay_gen=0)
        snapshot = SimpleNamespace(accs=[a, b], lenh_tay_gen=2)
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.dict(R.config.PARTY_CONFIG, {0: {"mode": "stand"}}, clear=True), \
                mock.patch.dict(R.config.PARTY_LEADER_ACC, {0: "a"}, clear=True), \
                mock.patch.dict(R.account_clients, {"a": ca, "b": cb}, clear=True):
            state = R._pstate(0)
            state.update(cmd=("route", 12001, 12061), cmd_gen=2, manual_route_gen=2,
                         manual_route_plan={"source": 12001, "dest": 12061, "city": 12001,
                                            "flag": 0, "users": ["a", "b"],
                                            "leader": "a", "phase": "dest"})
            decisions = R._engine_mode_decisions(0, snapshot, {"a": "lenh_tay", "b": "lenh_tay"})
            self.assertEqual(decisions, {"a": "nghi", "b": "nghi"})
            self.assertEqual((ca._pe_lenh_tay_gen, cb._pe_lenh_tay_gen), (2, 2))
            self.assertTrue(state["manual_route_done"].is_set())

    def test_city_mode_stays_in_town_instead_of_starting_train(self):
        decide = getattr(R, "_engine_mode_decisions", None)
        self.assertIsNotNone(decide)
        account = SimpleNamespace(username="a", song=True, dang_danh=False,
                                  map_id=12001, lenh_tay_da_lam=0)
        snapshot = SimpleNamespace(accs=[account], lenh_tay_gen=0)
        with mock.patch.dict(R.config.PARTY_CONFIG,
                             {0: {"mode": "city", "start_city_id": 12001}}, clear=True):
            self.assertEqual(decide(0, snapshot, {"a": "train"}), {"a": "nghi"})

    def test_mode_refresh_reads_current_event_maps(self):
        engine = SimpleNamespace()
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"mode": "event"}}, clear=True), \
                mock.patch.dict(R.config.PARTY_LEADER_ACC, {}, clear=True), \
                mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "party_accounts", return_value=[]), \
                mock.patch.object(R, "_map_event_engine_moi", return_value=(10991,)):
            R._cap_nhat_engine(engine, 0)
        self.assertEqual(getattr(engine, "map_event", None), (10991,))

    def test_start_party_does_not_start_global_or_watcher_thread(self):
        with mock.patch.object(R, "party_accounts", return_value=[]), \
                mock.patch.object(R, "_tim_server_moi_nen"), \
                mock.patch.object(R, "_start_party_accounts", return_value=1), \
                mock.patch.object(R, "reset_party_joined"), \
                mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R.threading, "Thread") as thread:
            self.assertEqual(R.start_party(0), 1)
        self.assertEqual(thread.call_count, 0,
                         "startup must not launch a second source of party commands")

    def test_stand_login_hands_client_to_party_engine(self):
        client = SimpleNamespace(
            char_name="test", current_map=12001, self_entity=b"entity01",
            running=True, server_closed=False, char_level=1, pet_level=1,
            pet_name_out=lambda: "", close=lambda: None)
        handed = []
        with mock.patch.dict(R.config.PARTY_CONFIG, {0: {"mode": "stand"}}, clear=True), \
                mock.patch.dict(R.config.PARTY_LEADER_ACC, {}, clear=True), \
                mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.dict(R.account_clients, {}, clear=True), \
                mock.patch.object(R, "_party_exit_summary"), \
                mock.patch.object(R, "_dang_ky_engine_moi",
                                  side_effect=lambda *a, **k: handed.append(a[1])):
            R.run_account("test", "", 0, False, reuse_client=client)
        self.assertEqual(handed, [client])

    def test_party_effect_adapter_does_not_decide_or_launch_channel_threads(self):
        adapter = getattr(R, "_engine_ap_dung_party", None)
        self.assertIsNotNone(adapter, "engine needs an effects-only runner adapter")
        snap = SimpleNamespace(pha="train", maps={12001: ["a"]},
                               kenhs={1}, thanh_cu=12001)
        effect = SimpleNamespace(lech_tu=None, doi_pha_train=False,
                                 chot_tang_gom=False, chot_2k_xong=False)
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_acc_song", return_value=[]), \
                mock.patch.object(R, "_thi_hanh_hieu_ung"), \
                mock.patch.object(R, "_ghi_ke_hoach"), \
                mock.patch.object(R, "_engine_chot_kenh", return_value=1), \
                mock.patch.object(R, "_engine_chot_map"), \
                mock.patch.object(R.party_engine, "quyet_dinh_cap_party") as decide, \
                mock.patch.object(R.threading, "Thread") as thread:
            adapter(0, snap, "dong_bo", "different channels", effect)
        self.assertEqual(decide.call_count, 0)
        self.assertEqual(thread.call_count, 0)


if __name__ == "__main__":
    unittest.main()
