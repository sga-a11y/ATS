"""Engine sends channel work to the existing account worker."""

import unittest
from types import SimpleNamespace

from bot import party_engine as PE


class Client:
    def __init__(self, channel=2):
        self.running = True
        self.current_channel = channel
        self._label = "test"
        self._lenh_tay_kenh_dang_chay = False
        self._dp_gui_kenh_dang_chay = False
        self.state = SimpleNamespace(in_battle=False)
        self.calls = []

    def kenh_dang_chac(self):
        return True

    def switch_channel(self, target, **kwargs):
        self.calls.append((target, kwargs))
        self.current_channel = target
        return True


def channel_decision(channels, target, *, maps=None, base=None, certain=None,
                     fighting=(), stopped=(), manual=(), active=(), allow=None,
                     manual_generation=0):
    """Run the real channel overlay on a controlled party snapshot."""
    maps = maps or {}
    base = base or {}
    certain = certain or {}
    clients = {u: Client(ch) for u, ch in channels.items()}
    accounts = []
    for u, channel in channels.items():
        if u in manual:
            clients[u]._lenh_tay_kenh_dang_chay = True
        if u in active:
            clients[u]._dp_gui_kenh_dang_chay = True
        accounts.append(PE.AnhAcc(u, song=u not in stopped, map_id=maps.get(u, 100),
                                  kenh=channel, kenh_chac=certain.get(u, True),
                                  dang_danh=u in fighting,
                                  lenh_tay_da_lam=0))
    snapshot = PE.AnhParty(0, accounts, lenh_tay_gen=manual_generation)
    engine = PE.PartyEngine(0, lambda: [(u, c, False) for u, c in clients.items()],
                            doc_kenh_dich=lambda: target,
                            kenh_doi_duoc=allow or (lambda _c: True))
    actions = engine._giao_kenh_dich(snapshot,
                                    {u: base.get(u, "nghi") for u in channels})
    return actions, clients


class TestChannelWorkerHandoff(unittest.TestCase):
    def test_mismatched_accounts_get_worker_action(self):
        actions, clients = channel_decision({"a": 2, "b": 10}, 16)
        self.assertEqual(actions, {"a": "doi_kenh", "b": "doi_kenh"})
        self.assertEqual(clients["a"].calls, [])
        PE.thi_hanh(clients["a"], actions["a"], lambda: True, dich=16,
                    kenh_doi_duoc=lambda _c: True)
        self.assertEqual(clients["a"].calls[0][0], 16)
        self.assertTrue(clients["a"].calls[0][1]["theo_lenh"])

    def test_matching_certain_channel_and_unknown_target_do_not_switch(self):
        self.assertEqual(channel_decision({"a": 16}, 16)[0], {"a": "nghi"})
        self.assertEqual(channel_decision({"a": 2}, None)[0], {"a": "nghi"})

    def test_uncertain_channel_is_not_treated_as_arrived(self):
        self.assertEqual(channel_decision({"a": 16}, 16, certain={"a": False})[0],
                         {"a": "doi_kenh"})

    def test_login_chore_is_not_interrupted(self):
        self.assertEqual(channel_decision({"a": 2}, 16,
                                          base={"a": "login_chore"})[0],
                         {"a": "login_chore"})

    def test_manual_command_and_inflight_switch_have_one_owner(self):
        self.assertEqual(channel_decision({"a": 2}, 16, manual={"a"})[0],
                         {"a": "nghi"})
        self.assertEqual(channel_decision({"a": 2}, 16, active={"a"})[0],
                         {"a": "nghi"})
        self.assertEqual(channel_decision({"a": 2}, 16,
                                          manual_generation=1)[0], {"a": "nghi"})

    def test_battle_safety_and_stopped_account(self):
        self.assertEqual(channel_decision({"a": 2}, 16, fighting={"a"})[0],
                         {"a": "nghi"})
        self.assertEqual(channel_decision({"a": 2}, 16, stopped={"a"})[0],
                         {"a": "nghi"})
        self.assertEqual(channel_decision({"a": 2}, 16,
                                          allow=lambda _c: False)[0], {"a": "nghi"})


if __name__ == "__main__":
    unittest.main()
