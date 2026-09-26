"""The party controller reads live maps and channels without account reports."""
import unittest
from bot import party_engine as E
from tests.test_party_engine_vong import _Cli


class TestChannelMapDirectRead(unittest.TestCase):
    def test_snapshot_changes_immediately_with_server_state(self):
        a, b = _Cli(map_id=100), _Cli(map_id=200, kenh=2)
        engine = E.PartyEngine(0, lambda: [("a", a, True), ("b", b, False)], can_bao_nhieu=1)
        self.assertEqual([(x.map_id, x.kenh) for x in engine.chup().accs], [(100, 1), (200, 2)])
        b.current_map, b.current_channel = 100, 1
        self.assertEqual([(x.map_id, x.kenh) for x in engine.chup().accs], [(100, 1), (100, 1)])

    def test_missing_client_remains_in_expected_party(self):
        engine = E.PartyEngine(0, lambda: [("a", _Cli(), True), ("b", None, False)], can_bao_nhieu=1)
        snapshot = engine.chup()
        self.assertTrue(snapshot.thieu_acc_song)
        self.assertEqual(len(snapshot.accs), 2)

    def test_unknown_map_does_not_count_as_arrival(self):
        engine = E.PartyEngine(0, lambda: [("a", _Cli(map_id=None), True)], map_dich=100)
        self.assertIsNone(engine.chup().accs[0].map_id)
        self.assertNotIn(E.VIEC_RA_SPOT, engine.nhip().values())
