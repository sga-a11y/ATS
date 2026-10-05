"""Quest integration regressions from the 04/10 review and party 28 event cancellation log.

Run with unittest; game clients and network operations are replaced with fakes.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
with mock.patch.object(sys, "argv", ["review"]):
    from tests.test_quest_mode import R, Q, PE, FakeClient, CH, _all_bits


class ReviewProbes(unittest.TestCase):
    def setUp(self):
        self.pidx = 9999
        self.cfg = {"mode": "quest", "quest_key": "cs1_cu_thu", "_quest_thu_tu": ["a", "b"]}
        self.lead = FakeClient()
        self.member = FakeClient()
        self.lead.running = self.member.running = True
        self.lead.legion_boss_available = lambda: False
        self.member.legion_boss_available = lambda: False
        self.lead._doi_truong_dang_ket = self.member._doi_truong_dang_ket = lambda: None
        self.clients = {"a": self.lead, "b": self.member}
        for patch in (
            mock.patch.dict(R.config.PARTY_LEADER_ACC, {self.pidx: "a"}),
            mock.patch.dict(R.config.PARTY_CONFIG, {self.pidx: self.cfg}),
            mock.patch.dict(R.account_clients, self.clients),
            mock.patch.object(R, "_clients_cua_party", side_effect=lambda p: list(self.clients.items())),
            mock.patch.object(R, "_pick_start_city", return_value=15001),
            mock.patch.object(R, "party_route_maps"),
            mock.patch.object(R, "_map_train_dich", return_value=None),
            mock.patch.object(R, "_safe_cua_map", return_value=[]),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        R._party_state.pop(self.pidx, None)
        self.addCleanup(R._party_state.pop, self.pidx, None)

    def acc(self, user, **kw):
        return PE.AnhAcc(user, la_leader=user == "a", map_id=13243, kenh=kw.pop("kenh", 1), **kw)

    def decide(self, accs, initial=None):
        anh = PE.AnhParty(self.pidx, accs, pha=PE.PHA_TRAIN, can_bao_nhieu=1)
        return R._engine_mode_decisions(self.pidx, anh, initial or {a.username: "nghi" for a in accs})

    def test_control_full_party_can_start_quest(self):
        got = self.decide([self.acc("a", so_member=1), self.acc("b", so_member=1)])
        self.assertEqual(got, {"a": "quest", "b": "nghi"})

    def test_startup_daily_finishes_before_any_quest_route(self):
        # 05/10 p27 00:51:13: route arrived before daily; dungeon then broke the party.
        accs = [self.acc("a"), self.acc("b", xong_daily=False)]
        for a in accs:
            a.map_id = 12001
        got = self.decide(accs,
                          {"a": "train", "b": "daily"})
        self.assertEqual(got, {"a": "nghi", "b": "daily"})
        R.party_route_maps.assert_not_called()
        accs[1].xong_daily = True
        self.decide(accs)
        R.party_route_maps.assert_called_once_with(self.pidx, 15001, 13243)

    def test_startup_waits_for_worker_even_after_done_flag(self):
        got = self.decide([self.acc("a"), self.acc("b", dang_ban=True,
                                                   viec_dang_lam="daily")])
        self.assertEqual(got, {"a": "nghi", "b": "daily"})

    def test_startup_waits_for_reconnecting_account_without_gathering(self):
        got = self.decide([self.acc("a"), self.acc("b", song=False)])
        self.assertEqual(got["a"], "nghi")
        R.party_route_maps.assert_not_called()

    def test_daily_and_login_chore_cannot_start_after_quest_gather(self):
        ready = [self.acc("a", so_member=1), self.acc("b", so_member=1)]
        self.decide(ready)
        got = self.decide([self.acc("a", so_member=1, xong_daily=False),
                           self.acc("b", so_member=1, xong_chore=False)],
                          {"a": "daily", "b": "login_chore"})
        self.assertEqual(got, {"a": "quest", "b": "nghi"})

    def test_startup_does_not_override_user_command(self):
        got = self.decide([self.acc("a"), self.acc("b", xong_daily=False)],
                          {"a": "lenh_tay", "b": "nghi"})
        self.assertEqual(got, {"a": "lenh_tay", "b": "nghi"})

    def test_server_end_waits_for_dialogue_worker_to_consume_result(self):
        # 05/10 p40 00:57:07: rotation cancels worker before it consumes qev['het'].
        finished = FakeClient(_all_bits())
        finished._qev = {"het": True}
        self.clients["a"] = finished
        with mock.patch.dict(R.account_clients, {"a": finished}), \
                mock.patch.object(R.threading, "Thread") as thread:
            got = self.decide([self.acc("a", so_member=1, dang_ban=True,
                                       viec_dang_lam="quest"), self.acc("b", so_member=1)])
        thread.assert_not_called()
        self.assertEqual(got["a"], "quest")

    def test_all_done_server_end_does_not_logout_before_worker_consumes_it(self):
        self.clients.update({u: FakeClient(_all_bits()) for u in ("a", "b")})
        self.clients["a"]._qev = {"het": True}
        with mock.patch.dict(R.account_clients, self.clients), mock.patch.object(R, "stop_account") as stop:
            self.decide([self.acc("a", so_member=1, dang_ban=True, viec_dang_lam="quest"),
                         self.acc("b", so_member=1)])
            stop.assert_not_called()
            self.clients["a"]._qev = None
            self.decide([self.acc("a", so_member=1), self.acc("b", so_member=1)])
        self.assertEqual(stop.call_count, 2)

    def test_repeated_completed_dialogue_without_progress_stops_triggering(self):
        # mhmmot 00:50:52..00:58:27: 15 successful conversations, zero quest progress.
        c = self.step_client(True)
        c.ensure_pet_role = mock.Mock()
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        with mock.patch.object(Q, "quest_tiep_theo", return_value=(q, 1)):
            for _ in range(5):
                Q.chay(c, "cs1_cu_thu", cho=0)
        self.assertEqual(c.quest_kich_hoat.call_count, 3)

    def test_server_progress_unblocks_a_previously_stalled_step(self):
        c = self.step_client(True)
        c.ensure_pet_role = mock.Mock()
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        with mock.patch.object(Q, "quest_tiep_theo", return_value=(q, 1)):
            for _ in range(3):
                Q.chay(c, "cs1_cu_thu", cho=0)
        c.current_map = 18506
        c.mission_steps[10528] = 3
        def complete(**kwargs):
            c.mission_steps[10528] = 4
            return "xong"
        c.quest_hoi_thoai.side_effect = complete
        with mock.patch.object(Q, "quest_tiep_theo", return_value=(q, 3)):
            Q.chay(c, "cs1_cu_thu", cho=0)
        self.assertEqual(c.quest_kich_hoat.call_count, 4)
        self.assertIsNone(c._quest_khong_tien)

    def test_existing_daily_is_not_cancelled_when_resuming_quest_mode(self):
        R._pstate(self.pidx)["quest_da_bat_dau"] = True
        accs = [self.acc("a"), self.acc("b", xong_daily=False,
                                       dang_ban=True, viec_dang_lam="daily")]
        for a in accs:
            a.map_id = 12001
        got = self.decide(accs,
                          {"a": "nghi", "b": "daily"})
        self.assertEqual(got["b"], "daily")
        self.assertEqual(got["a"], "nghi")
        R.party_route_maps.assert_not_called()

    def test_startup_barrier_uses_base_engine_daily_decision(self):
        accs = [self.acc("a"), self.acc("b", xong_chore=False, xong_daily=False)]
        anh = PE.AnhParty(self.pidx, accs, pha=PE.PHA_TRAIN, can_bao_nhieu=1)
        def tick():
            return R._engine_mode_decisions(self.pidx, anh, PE.quyet_dinh(anh))
        self.assertEqual(tick(), {"a": "nghi", "b": "login_chore"})
        accs[1].xong_chore = True
        self.assertEqual(tick(), {"a": "nghi", "b": "daily"})
        accs[1].xong_daily = True
        self.assertEqual(tick(), {"a": "lap_party", "b": "lap_party"})
        accs[0].so_member = accs[1].so_member = 1
        self.assertEqual(tick(), {"a": "quest", "b": "nghi"})

    def test_pending_daily_does_not_cancel_an_already_open_dialogue(self):
        self.lead._qev = {"het": True}
        got = self.decide([self.acc("a", dang_ban=True, viec_dang_lam="quest"),
                           self.acc("b", dang_ban=True, viec_dang_lam="daily", xong_daily=False)],
                          {"a": "quest", "b": "daily"})
        self.assertEqual(got, {"a": "quest", "b": "daily"})

    def test_failed_walk_does_not_consume_no_progress_attempts(self):
        c = self.step_client(False)
        c.ensure_pet_role = mock.Mock()
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        with mock.patch.object(Q, "quest_tiep_theo", return_value=(q, 1)):
            for _ in range(4):
                Q.chay(c, "cs1_cu_thu", cho=0)
            c.navigate_to.return_value = True
            Q.chay(c, "cs1_cu_thu", cho=0)
        c.quest_kich_hoat.assert_called_once()

    def test_reconnecting_member_must_block_new_quest(self):
        self.clients["b"] = None
        got = self.decide([self.acc("a"), self.acc("b", song=False)])
        self.assertNotEqual(got["a"], "quest", got)

    def test_channel_sync_decision_must_survive_quest_adapter(self):
        got = self.decide([self.acc("a", kenh=1), self.acc("b", kenh=2)],
                          {"a": "nghi", "b": "doi_kenh"})
        self.assertEqual(got["b"], "doi_kenh", got)
        self.assertEqual(got["a"], "nghi", got)

    def test_control_same_channel_can_invite(self):
        got = self.decide([self.acc("a"), self.acc("b")])
        self.assertEqual(got, {"a": "lap_party", "b": "lap_party"})

    def test_no_new_quest_battle_after_roster_break_during_walk(self):
        self.lead._qev = None  # walking, NOT draining an existing dialogue
        got = self.decide([self.acc("a", dang_ban=True, viec_dang_lam="quest"), self.acc("b")])
        self.assertNotEqual(got["a"], "quest", got)

    def test_control_full_roster_can_continue_walk(self):
        self.lead._qev = None
        got = self.decide([self.acc("a", so_member=1, dang_ban=True, viec_dang_lam="quest"),
                           self.acc("b", so_member=1)])
        self.assertEqual(got, {"a": "quest", "b": "nghi"})

    def test_rotation_must_wait_until_last_dialogue_ends(self):
        finished = FakeClient(_all_bits())
        finished._qev = {"het": False, "conduct": True}
        self.clients["a"] = finished
        with mock.patch.dict(R.account_clients, {"a": finished}), \
                mock.patch.object(R.threading, "Thread") as thread:
            got = self.decide([self.acc("a", so_member=1, dang_ban=True, viec_dang_lam="quest"),
                               self.acc("b", so_member=1)])
        self.assertFalse(thread.called, (got, thread.call_args))
        self.assertEqual(got["a"], "quest")

    def test_all_done_must_finish_dialogue_before_logout(self):
        self.clients.update({u: FakeClient(_all_bits()) for u in ("a", "b")})
        self.clients["a"]._qev = {"het": False}
        with mock.patch.dict(R.account_clients, self.clients), mock.patch.object(R, "stop_account") as stop:
            got = self.decide([self.acc("a", so_member=1, dang_ban=True, viec_dang_lam="quest"),
                               self.acc("b", so_member=1)])
        stop.assert_not_called()
        self.assertEqual(got["a"], "quest")

    def test_open_dialogue_drains_even_if_member_reconnects(self):
        self.lead._qev = {"het": False}
        self.clients["b"] = None
        got = self.decide([self.acc("a", dang_ban=True, viec_dang_lam="quest"),
                           self.acc("b", song=False)])
        self.assertEqual(got["a"], "quest")

    def test_unloaded_member_flags_must_block_new_quest(self):
        self.member._mark_flags_loaded = False
        got = self.decide([self.acc("a", so_member=1), self.acc("b", so_member=1)])
        self.assertNotEqual(got["a"], "quest")

    def test_control_completed_dialogue_can_rotate(self):
        finished = FakeClient(_all_bits())
        finished._qev = None
        self.clients["a"] = finished
        with mock.patch.dict(R.account_clients, {"a": finished}), \
                mock.patch.object(R.threading, "Thread") as thread:
            self.decide([self.acc("a", so_member=1), self.acc("b", so_member=1)])
        self.assertTrue(thread.called)

    def test_party_support_member_must_not_leave_for_legion_boss(self):
        self.member.legion_boss_available = lambda: True
        got = self.decide([self.acc("a", so_member=1, dang_ban=True, viec_dang_lam="quest"),
                           self.acc("b", so_member=1)])
        self.assertEqual(got["b"], "nghi", got)

    def test_control_disabled_legion_boss_preserves_party(self):
        self.member.legion_boss_available = lambda: True
        self.cfg["fight_legion_boss"] = False
        got = self.decide([self.acc("a", so_member=1, dang_ban=True, viec_dang_lam="quest"),
                           self.acc("b", so_member=1)])
        self.assertEqual(got, {"a": "quest", "b": "nghi"})

    def step_client(self, navigate_ok):
        c = FakeClient(steps={10528: 1})
        c.running, c.current_map = True, 18301
        c._wait_combat_clear = mock.Mock(return_value=True)
        c.navigate_to = mock.Mock(return_value=navigate_ok)
        c.quest_kich_hoat = mock.Mock()
        c.quest_hoi_thoai = mock.Mock(return_value="xong")
        return c

    def test_control_arrival_triggers_npc(self):
        c = self.step_client(True)
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        Q.lam_buoc(c, q, 1)
        c.quest_kich_hoat.assert_called_once_with("npc", 4)

    def test_failed_navigation_must_not_trigger_npc(self):
        c = self.step_client(False)
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        Q.lam_buoc(c, q, 1)
        c.quest_kich_hoat.assert_not_called()

    def test_cancelled_navigation_must_not_trigger_npc(self):
        c = self.step_client(False)
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        Q.lam_buoc(c, q, 1, abort=lambda: True)
        c.quest_kich_hoat.assert_not_called()

    def test_abort_received_at_arrival_must_not_trigger_npc(self):
        c = self.step_client(True)
        aborted = False
        def arrived(*args, **kwargs):
            nonlocal aborted
            aborted = True
            return True
        c.navigate_to.side_effect = arrived
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        Q.lam_buoc(c, q, 1, abort=lambda: aborted)
        c.quest_kich_hoat.assert_not_called()

    def test_preparatory_walk_failure_stops_before_next_trigger(self):
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        for moves, triggers in (([True, False], []), ([True, True, False], [mock.call("cua", 3)])):
            with self.subTest(moves=moves):
                c = self.step_client(True)
                c.current_map = 18506
                c.navigate_to.side_effect = moves
                Q.lam_buoc(c, q, 2)
                self.assertEqual(c.quest_kich_hoat.call_args_list, triggers)

    def test_preparatory_dialogue_failure_stops_before_npc(self):
        c = self.step_client(True)
        c.current_map = 18506
        c.quest_hoi_thoai.return_value = "im_lang"
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        self.assertFalse(Q.lam_buoc(c, q, 2))
        c.quest_kich_hoat.assert_called_once_with("cua", 3)

    def test_step_progress_does_not_hide_unfinished_dialogue(self):
        c = self.step_client(True)
        def dialogue(**kw):
            c.mission_steps[10528] = 2
            return "im_lang"
        c.quest_hoi_thoai.side_effect = dialogue
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        self.assertFalse(Q.lam_buoc(c, q, 1))

    def test_roster_loss_at_arrival_blocks_trigger_before_next_tick(self):
        c = self.step_client(True)
        full = True
        def arrived(*args, **kw):
            nonlocal full
            full = False
            return True
        c.navigate_to.side_effect = arrived
        q = next(q for q in CH["quests"] if q["id"] == 10528)
        Q.lam_buoc(c, q, 1, du_party=lambda: full)
        c.quest_kich_hoat.assert_not_called()

    def test_worker_checks_live_roster_and_reconnecting_clients(self):
        self.lead.party_members = [b"member"]
        self.lead.current_map = self.member.current_map = 13243
        self.lead._username = "a"
        observed = []
        def run_step(*args, **kw):
            ready = kw["du_party"]
            observed.append(ready())
            self.lead.party_members = []
            observed.append(ready())
            self.lead.party_members = [b"member"]
            self.clients["b"] = None
            observed.append(ready())
            return True
        with mock.patch.object(Q, "chay", side_effect=run_step):
            R._engine_mode_action(self.pidx, self.lead, "quest", lambda: True)
        self.assertEqual(observed, [True, False, False])


if __name__ == "__main__":
    unittest.main(verbosity=2)

