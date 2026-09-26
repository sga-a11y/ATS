"""Channel targets apply only after every live account shares a known map."""

import unittest

from tests.test_dieu_phoi_tu_gui_lenh_doi_kenh import channel_decision


class TestMapGateBeforeChannelWork(unittest.TestCase):
    def test_split_maps_do_not_issue_any_channel_work(self):
        channels = {"seller": 1, "lead": 1, "member": 7}
        maps = {"seller": 12061, "lead": 21001, "member": 21001}
        actions, clients = channel_decision(channels, 2, maps=maps)
        self.assertEqual(actions, {u: "nghi" for u in channels})
        self.assertTrue(all(not c.calls for c in clients.values()))

    def test_same_map_sends_work_to_mismatched_accounts(self):
        actions, _ = channel_decision({"a": 1, "b": 7}, 2,
                                      maps={"a": 21001, "b": 21001})
        self.assertEqual(actions, {"a": "doi_kenh", "b": "doi_kenh"})

    def test_unknown_map_blocks_channel_work(self):
        actions, _ = channel_decision({"a": 1, "b": 7}, 2,
                                      maps={"a": 21001, "b": None})
        self.assertEqual(actions, {"a": "nghi", "b": "nghi"})

    def test_one_account_can_switch_on_its_known_map(self):
        actions, _ = channel_decision({"a": 1}, 2, maps={"a": 12061})
        self.assertEqual(actions, {"a": "doi_kenh"})


if __name__ == "__main__":
    unittest.main()
