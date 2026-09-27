"""`fc_gom` (2K lech tang -> di bo ve tang gom) PHAI huy duoc khi engine doi viec.

Ca that party 5, 27/09 (party.log):
    11:10:34 [party 5] ENGINE: sga018 -> fc_gom          (anh chup luc chihao con o 12922)
    11:10:34 [thtam]   gom doi: di bo 12923 -> 12922
    11:10:35 [party 5] DIEU PHOI gen 22: pha=event map=12923 kenh=1 viec=lam
    11:10:36 [party 5] ENGINE: sga018 -> nghi
    11:11:47 [thtam]   cong idx=1 ra map 12924 (khac du kien 12922) -> plan lai duong con lai toi 12922
    11:12:37 [thtam]   SERVER NGAT KET NOI: di chuyen QUA XA (ma 14)
Engine da doi sang `nghi` nhung `fc_gom(client)` khong nhan duong huy -> ba member di tiep 2 phut
roi bi kick, party vo va ket `lap_party` tu do.

Kem theo: engine chay tiep nhip khi party da bi bo khoi cau hinh -> `party_accounts(pidx)` no
`IndexError` moi nhip (26/09 18:41:12, party 21, 20 traceback luc STOP).
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C
from bot import party_engine as PE

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


EV_2K = {"label": "Nhi Kieu", "staging_map": 12921, "dest_map": 12922,
         "party_battle": {"kind": "floor_crawl", "top_map": 12934}}


class TestEngineTruyenDuongHuyChoFcGom(unittest.TestCase):
    def test_thi_hanh_truyen_con_lam_xuong_fc_gom(self):
        nhan = []
        con_lam = lambda: True
        PE.thi_hanh(object(), PE.VIEC_FC_GOM, con_lam,
                    fc_gom=lambda cli, cl: nhan.append(cl) or True)
        self.assertEqual(nhan, [con_lam])

    def test_callback_doi_con_lam_thanh_abort(self):
        class _Cli:
            current_map = 12923
            abort = None

            def regroup_to_event_start(self, ev, dest=None, abort=None):
                self.abort = abort
                return False

        cli = _Cli()
        dang_lam = [True]
        with mock.patch.object(R, "_event_cua_party", return_value=EV_2K), \
                mock.patch.object(R, "_tang_gom_engine_moi", return_value=12922):
            R._fc_gom_engine_moi(cli, 4, lambda: dang_lam[0])
        self.assertIsNotNone(cli.abort)
        self.assertFalse(cli.abort())
        dang_lam[0] = False                  # engine doi viec (`nghi`) -> phai nha ra
        self.assertTrue(cli.abort())


class TestRegroupNhaRaKhiAbort(unittest.TestCase):
    def _cli(self):
        cli = mock.Mock()
        cli.current_map = 12923
        cli._label = "thtam"
        cli.refresh_server_position.return_value = True
        cli.follow_smart_scene_route.return_value = False
        return cli

    def test_abort_duoc_chuyen_xuong_duong_di(self):
        cli = self._cli()
        ab = lambda: False
        C.GameClient.regroup_to_event_start(cli, EV_2K, dest=12922, abort=ab)
        self.assertIs(cli.follow_smart_scene_route.call_args.kwargs.get("abort"), ab)

    def test_da_huy_thi_khong_di(self):
        cli = self._cli()
        ok = C.GameClient.regroup_to_event_start(cli, EV_2K, dest=12922, abort=lambda: True)
        self.assertFalse(ok)
        cli.follow_smart_scene_route.assert_not_called()


class TestExecuteRouteHuyKhiDangPlanLai(unittest.TestCase):
    """Dung duong di cua ca party 5: cong ra 12924 thay vi 12922 -> plan lai. Neu lenh da bi huy
    thi phai dung, khong di tiep chang moi."""

    def test_dung_sau_khi_plan_lai_neu_da_huy(self):
        cli = mock.Mock()
        cli.running = True
        cli._label = "thtam"
        cli.current_map = 12923
        cli.pos = (1020, 680)
        huy = [False]

        def _enter_gate(*_a, **_k):
            cli.current_map = 12924          # bi keo len tang tren, khong phai 12922
            huy[0] = True                    # dung luc do engine giao `nghi`
            return True

        cli._enter_gate.side_effect = _enter_gate
        cli.build_smart_scene_route.return_value = {
            "dest_map": 12922, "legs": [{"scene": 12924, "gate": 1, "gate_center": (90, 1640),
                                         "target_scene": 12923}]}
        route = {"dest_map": 12922, "legs": [{"scene": 12923, "gate": 1,
                                              "gate_center": (1020, 680), "target_scene": 12922}]}
        ok = C.execute_smart_route(cli, route, abort=lambda: huy[0])
        self.assertFalse(ok)
        self.assertEqual(cli._enter_gate.call_count, 1)


class TestPartyBiBoKhoiCauHinhThiDungEngine(unittest.TestCase):
    def test_cap_nhat_dung_engine_khong_no_index_error(self):
        eng = mock.Mock()
        with mock.patch.object(R.config, "PARTIES", [], create=True):
            R._cap_nhat_engine(eng, 20)
        eng.stop.assert_called_once_with()

    def test_nhip_khong_chay_tiep_sau_khi_cap_nhat_dung_engine(self):
        doc = mock.Mock(return_value=None)
        eng = PE.PartyEngine(20, lambda: [], cap_nhat=lambda e: e.stop(), doc_party=doc)
        eng.nhip()
        doc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
