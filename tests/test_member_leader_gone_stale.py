"""A reconnecting leader leaves members under the same party controller."""
import unittest
from bot import party_engine as E
from tests.test_party_engine_vong import _Cli


class TestMemberLeaderGoneStale(unittest.TestCase):
    def test_reconnecting_leader_does_not_kill_member(self):
        member = _Cli()
        clients = [("l", None, True), ("m", member, False)]
        engine = E.PartyEngine(0, lambda: clients, can_bao_nhieu=1,
                               hoi_cho=lambda: "leader dang login")
        self.assertEqual(engine.nhip(), {"m": E.VIEC_NGHI})
        self.assertTrue(member.running)
        clients[0] = ("l", _Cli(members=1), True)
        engine._hoi_cho = lambda: ""
        self.assertFalse(engine.chup().thieu_acc_song)
        self.assertNotIn(E.VIEC_THOAT, engine.nhip().values())

    def test_explicit_stop_stops_all_attached_workers(self):
        clients = [("l", _Cli(), True), ("m", _Cli(), False)]
        engine = E.PartyEngine(0, lambda: clients)
        engine.start()
        engine.stop()
        self.assertTrue(all(w._dung.is_set() for w in engine.workers.values()))
