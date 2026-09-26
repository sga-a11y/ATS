import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R
from bot import party_engine as E
from tests.party_engine_scenarios import account, snapshot


class UnseenMemberTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(R._party_state, {}, clear=True))
        self.leader = NS(current_map=49942, current_channel=19,
                         party_members=[b"b", b"c", b"d"], kenh_dang_nghi_ngo=False)
        self.member = mock.Mock(current_map=49942, current_channel=19,
                                party_members=[], kenh_dang_nghi_ngo=False,
                                _lenh_tay_kenh_dang_chay=False,
                                _dp_gui_kenh_dang_chay=False)
        self.member.kenh_dang_chac.side_effect = lambda: not self.member.kenh_dang_nghi_ngo
        self.rows = [("a", self.leader), ("e", self.member)]
        self.cap = NS(pha=E.PHA_DG, du_doi=False, ai_lech_instance=["e"])

    def test_unseen_member_rechecks_same_channel_without_breaking_joined_party(self):
        self.cap.maps, self.cap.kenhs, self.cap.thanh_cu = {49942: ["a", "e"]}, {19}, None
        effects = NS(lech_tu=None, doi_pha_train=False, chot_tang_gom=False, chot_2k_xong=False)
        with mock.patch.object(R.time, "time", return_value=100), \
                mock.patch.object(R, "_acc_song", return_value=self.rows), \
                mock.patch.object(R, "_thi_hanh_hieu_ung"), \
                mock.patch.object(R, "_ghi_ke_hoach"), \
                mock.patch.object(R, "_engine_chot_map"), \
                mock.patch.object(R, "_engine_chot_kenh"):
            R._engine_ap_dung_party(0, self.cap, E.DP_LAM, "", effects)
        self.assertFalse(self.leader.kenh_dang_nghi_ngo)
        self.assertTrue(self.member.kenh_dang_nghi_ngo)
        anh = snapshot([account(map_id=49942, kenh=19, so_member=3),
                        account("e", map_id=49942, kenh=19, so_member=0, kenh_chac=False)],
                       can_bao_nhieu=4, pha=E.PHA_DG)
        eng = E.PartyEngine(0, lambda: [(u, c, u == "a") for u, c in self.rows],
                            doc_kenh_dich=lambda: None)
        result = eng._giao_kenh_dich(anh, {"a": E.VIEC_LAP_PARTY, "e": E.VIEC_LAP_PARTY})
        self.assertEqual(result, {"a": E.VIEC_LAP_PARTY, "e": E.VIEC_DOI_KENH})
        self.assertTrue(E.thi_hanh(self.member, result["e"], lambda: True,
                                   dich=19, kenh_doi_duoc=lambda c: True))
        self.member.switch_channel.assert_called_once_with(19, wait=4.0, retries=1, theo_lenh=True)

    def test_fresh_visibility_full_roster_and_joined_member_are_not_rechecked(self):
        for full, unseen, members in ((False, [], []), (True, ["e"], []),
                                      (False, ["e"], [b"a"])):
            self.cap.du_doi, self.cap.ai_lech_instance = full, unseen
            self.member.party_members = members
            R._engine_recheck_unseen_channels(0, self.cap, self.rows)
            self.assertFalse(self.member.kenh_dang_nghi_ngo)

    def test_rechecks_are_spaced_and_do_not_replace_map_sync(self):
        with mock.patch.object(R.time, "time", return_value=100):
            R._engine_recheck_unseen_channels(0, self.cap, self.rows)
        self.member.kenh_dang_nghi_ngo = False
        with mock.patch.object(R.time, "time", return_value=101):
            R._engine_recheck_unseen_channels(0, self.cap, self.rows)
        self.assertFalse(self.member.kenh_dang_nghi_ngo)
        self.member.current_map = 12001
        with mock.patch.object(R.time, "time", return_value=140):
            R._engine_recheck_unseen_channels(0, self.cap, self.rows)
        self.assertFalse(self.member.kenh_dang_nghi_ngo)
