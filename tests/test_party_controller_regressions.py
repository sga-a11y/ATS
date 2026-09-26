"""Behavior retained when the old account scripts and watcher were removed.

The former tests searched for closures, wait loops and comments in run_account.
These scenarios exercise the controller and its existing worker operations.
"""
import ast
import inspect
import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R
from bot import party_engine as E


class ControllerRegressions(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(R._party_state, {}, clear=True))
        self.enterContext(mock.patch.dict(R.account_clients, {}, clear=True))
        self.enterContext(mock.patch.dict(R.config.PARTY_LEADER_ACC, {0: "a"}, clear=True))
        self.enterContext(mock.patch.dict(R.config.PARTY_CONFIG,
                                         {0: {"mode": "train", "fight_legion_boss": False}}, clear=True))

    def account(self, name, **changes):
        values = dict(map_id=100, song=True, kenh=1, xong_chore=True, xong_daily=True,
                      so_member=1, la_leader=name == "a")
        values.update(changes)
        return E.AnhAcc(name, **values)

    def test_single_controller_owns_all_party_planning(self):
        functions = {n.name for n in ast.parse(inspect.getsource(R)).body
                     if isinstance(n, ast.FunctionDef)}
        self.assertTrue(functions.isdisjoint({"_dieu_phoi_loop", "_dieu_phoi_quyet",
                                            "_party_watcher", "_engine_gui_lenh_kenh"}))
        nested = {n.name for n in ast.walk(ast.parse(inspect.getsource(R.run_account)))
                  if isinstance(n, ast.FunctionDef)}
        self.assertTrue(nested.isdisjoint({"_do_reform", "do_channel_sync", "_nghe_lenh_kenh"}))

    def test_rally_waits_for_every_live_position_before_inviting(self):
        a, b = self.account("a"), self.account("b")
        snapshot = E.AnhParty(0, [a, b], can_bao_nhieu=1)
        R.account_clients.update(a=NS(pos=(650, 2070)), b=NS(pos=(760, 1980)))
        with mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(650, 2070)]):
            requested = {"a": "lap_party", "b": "lap_party"}
            self.assertEqual(R._engine_rally_decisions(0, snapshot, requested),
                             {"a": "nghi", "b": "ve_safe"})
            R.account_clients["b"].pos = (650, 2070)
            self.assertEqual(R._engine_rally_decisions(0, snapshot, requested), requested)

    def test_unknown_safe_position_does_not_release_channel_switch(self):
        snapshot = E.AnhParty(0, [self.account("a")])
        R.account_clients["a"] = NS(pos=None)
        with mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertEqual(R._engine_rally_decisions(0, snapshot, {"a": "doi_kenh"}),
                             {"a": "ve_safe"})

    def test_rally_uses_corrected_follower_position(self):
        client = NS(pos=(20, 30))
        client._theo_leader_sua_pos = lambda: setattr(client, "pos", (1000, 1000))
        R.account_clients["a"] = client
        with mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertEqual(R._engine_rally_decisions(
                0, E.AnhParty(0, [self.account("a")]), {"a": "lap_party"}), {"a": "ve_safe"})

    def test_manual_channel_pin_survives_automatic_selection_and_failure(self):
        from tests.test_chon_kenh_it_nguoi_du_cho import _C
        st = R._pstate(0)
        st["kenh_ghim"] = 3
        for channels in ((1, 2), (1, 1), (3, 3)):
            song = [(name, _C(ch, {2: (0, 20), 3: (20, 20)}))
                    for name, ch in zip(("a", "b"), channels)]
            song[0][1]._chan_switch_result = 4
            song[0][1]._chan_switch_target = 3
            with mock.patch.object(R, "_mode_can_lap_doi", return_value=True), \
                    mock.patch.object(R, "_party_40npc_ngoai_gio", return_value=False):
                self.assertEqual(R._engine_chot_kenh(0, st, song), 3)
            self.assertEqual(st["kenh_ghim"], 3)

    def test_already_at_safe_does_not_walk_again(self):
        client = mock.Mock(current_map=100, pos=(20, 30), party_members=[])
        client._wait_combat_clear.return_value = True
        with mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertTrue(R._ra_safe_engine_moi(client, 0))
        client.navigate_to.assert_not_called()

    def test_safe_work_can_be_cancelled_before_movement(self):
        client = mock.Mock(current_map=100, pos=(1000, 1000), party_members=[])
        with mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertFalse(R._ra_safe_engine_moi(client, 0, con_lam=lambda: False))
        client.navigate_to.assert_not_called()

    def test_foreign_party_is_left_only_by_a_selected_worker(self):
        client = mock.Mock(self_entity=b"member", party_members=[])
        client._doi_truong_dang_ket.return_value = b"stranger"
        R.account_clients.update(a=NS(self_entity=b"leader"), b=client)
        snapshot = E.AnhParty(0, [self.account("b")])
        with mock.patch.object(R, "_map_train_dich", return_value=None):
            result = R._engine_routine_decisions(0, snapshot, {"b": "lap_party"},
                                                  {"fight_legion_boss": False})
        self.assertEqual(result, {"b": "roi_party_la"})
        client.leave_party.assert_not_called()
        R._engine_mode_action(0, client, result["b"], lambda: True)
        client.leave_party.assert_called_once()

    def test_member_keeps_party_of_its_own_leader(self):
        client = mock.Mock(self_entity=b"member")
        client._doi_truong_dang_ket.return_value = b"leader"
        R.account_clients.update(a=NS(self_entity=b"leader"), b=client)
        snapshot = E.AnhParty(0, [self.account("b")])
        with mock.patch.object(R, "_map_train_dich", return_value=None):
            result = R._engine_routine_decisions(0, snapshot, {"b": "lap_party"},
                                                  {"fight_legion_boss": False})
        self.assertEqual(result, {"b": "lap_party"})

    def test_legion_boss_does_not_override_regroup_or_daily(self):
        client = mock.Mock(self_entity=b"leader")
        client.legion_boss_available.return_value = True
        client._doi_truong_dang_ket.return_value = None
        R.account_clients["a"] = client
        snapshot = E.AnhParty(0, [self.account("a")], dp_viec=E.DP_GOM)
        for action in ("daily", "ve_map", "lap_party", "nghi"):
            with self.subTest(action=action), mock.patch.object(R, "_map_train_dich", return_value=None):
                self.assertEqual(R._engine_routine_decisions(0, snapshot, {"a": action},
                                                             {"mode": "train"}), {"a": action})
        snapshot.dp_viec = E.DP_LAM
        self.assertEqual(R._engine_routine_decisions(0, snapshot, {"a": "train"},
                                                     {"mode": "train"}), {"a": "boss_quan_doan"})
        client.do_legion_boss.assert_not_called()

    def test_legion_boss_worker_fights_in_place(self):
        client = mock.Mock(_pe_la_leader=True)
        with mock.patch.object(R, "reset_party_joined"):
            R._engine_mode_action(0, client, "boss_quan_doan", lambda: True)
        client.do_legion_boss.assert_called_once()
        client.go_to_town.assert_not_called()
        self.assertFalse(client.flee_mode)

    def test_failed_login_safety_does_not_mark_chores_done(self):
        client = NS(_pe_xong_chore=False)
        self.assertFalse(E.lam_viec_vat(client, chore_fn=lambda c: False))
        self.assertFalse(client._pe_xong_chore)

    def test_client_receives_enabled_and_disabled_account_options(self):
        client = NS()
        R._cap_nhat_tuy_chon_client(client, {"mode": "train", "auto_bag_clean": False,
                                            "auto_cat_do": True, "auto_bank_expand": True,
                                            "bank_expand_gold": 250,
                                            "scroll_modes": {"0xc946": "keep"}})
        self.assertFalse(client.auto_bag_clean)
        self.assertTrue(client.auto_cat_do)
        self.assertEqual(client.bank_expand_gold, 250)
        self.assertEqual(client.scroll_modes, {0xc946: "keep"})
        R._cap_nhat_tuy_chon_client(client, {"mode": "event", "auto_cat_do": True})
        self.assertFalse(client.auto_cat_do)
        self.assertFalse(client.auto_sell_noi_dat)
        self.assertEqual(client.bank_expand_gold, 0)

    def test_safe_battle_warning_counts_only_new_trusted_battles(self):
        client = mock.Mock(_username="a", current_map=100, _pos_valid_for_map=100,
                           pos=(20, 30), _pe_battle_before=False, state=NS(in_battle=False))
        R._pstate(0)["rally_point"] = (20, 30)
        with mock.patch.object(R, "_ghi_nhan_tran_tai_safe") as record:
            R._nhip_acc_engine_moi(client, 0)
            record.assert_not_called()
            client.state.in_battle = True
            for _ in range(3):
                R._nhip_acc_engine_moi(client, 0)
            record.assert_called_once_with("a", 100, (20, 30), (20, 30), pos_dang_tin=True)
            client.state.in_battle = False
            R._nhip_acc_engine_moi(client, 0)
            client.state.in_battle = True
            client._pos_valid_for_map = None
            R._nhip_acc_engine_moi(client, 0)
            self.assertFalse(record.call_args.kwargs["pos_dang_tin"])

    def test_40npc_early_loss_skips_reward_and_still_stops(self):
        client = mock.Mock(_npc40_bo_thuong=True, _username="a")
        with mock.patch.object(R, "_event_cua_party", return_value={"party_battle": {"kind": "npc_repeat"}}), \
                mock.patch.object(R, "stop_account") as stop:
            R._doi_thuong_engine_moi(client, 0)
        client.claim_40npc_reward.assert_not_called()
        stop.assert_called_once()

    def test_40npc_normal_exit_claims_reward_before_stopping(self):
        client = mock.Mock(_npc40_bo_thuong=False, _username="a")
        events = []
        client.claim_40npc_reward.side_effect = lambda ev: events.append("reward")
        with mock.patch.object(R, "_event_cua_party", return_value={"party_battle": {}}), \
                mock.patch.object(R, "stop_account", side_effect=lambda *a: events.append("stop")):
            R._doi_thuong_engine_moi(client, 0)
        self.assertEqual(events, ["reward", "stop"])
