"""Regression contract after removing legacy per-account planning loops."""
import unittest
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class TestControllerContract(unittest.TestCase):

    def test_member_in_party_does_not_leave_on_late_resync(self):
        from unittest.mock import Mock
        for members, captain in (([b"m"], None), ([], b"leader")):
            client = Mock(party_members=members, party_leader=captain)
            E.thi_hanh(client, E.VIEC_RESYNC, lambda: True, dich=3)
            client.leave_party.assert_not_called()
            client.switch_channel.assert_not_called()
