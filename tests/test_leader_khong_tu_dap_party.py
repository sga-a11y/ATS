"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_member_already_in_party_ignores_resync(self):
        from unittest.mock import Mock
        client = Mock(party_members=[b"member"], party_leader=b"leader")
        self.assertTrue(E.thi_hanh(client, E.VIEC_RESYNC, lambda: True, dich=2))
        client.leave_party.assert_not_called()
        client.switch_channel.assert_not_called()

    def test_full_party_trains_without_new_invitation(self):
        self.assertNotIn(E.VIEC_LAP_PARTY, E.quyet_dinh(snapshot()).values())
