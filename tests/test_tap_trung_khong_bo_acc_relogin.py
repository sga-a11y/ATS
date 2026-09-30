"""Mode tap trung ve thanh: acc dang relogin luc tao plan KHONG duoc bi bo lai.

Ca that 29/09 party 57 (map 11011 -> 55002):
    23:40:58 [party 57] ENGINE: di map 11011 -> 55002, tap ket 11011   <- plan chup 4 nguoi
    23:41:02 [party 57] ENGINE: stsm05 da relogin -> tao worker MOI
    23:42:16 [stmot] PARTY: ... -> roster 3 nguoi
    23:42:16 [party 57] ENGINE: stsm01 -> route_dest                    <- bo lai stsm05
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _acc(u, so_member=0):
    return SimpleNamespace(username=u, song=True, map_id=11011, kenh=1, kenh_chac=True,
                           so_member=so_member)


class TapTrungKhongBoAccRelogin(unittest.TestCase):
    def test_acc_relogin_sau_khi_tao_plan_duoc_them_va_chan_di(self):
        users5 = ["stsm01", "stsm02", "stsm03", "stsm04", "stsm05"]
        st = R._pstate(56)
        plan = {"source": 11011, "dest": 55002, "city": 11011, "flag": 1,
                "users": users5[:4], "leader": "stsm01", "phase": "sync_city",
                "temporary_party": False}
        anh = SimpleNamespace(accs=[_acc("stsm01", so_member=3)] + [_acc(u) for u in users5[1:]],
                              lenh_tay_gen=0)
        with mock.patch.dict(st, {"manual_route_plan": plan, "kenh_dich": 1}), \
                mock.patch.object(R, "_clients_cua_party",
                                  return_value=[(u, object()) for u in users5]), \
                mock.patch.object(R, "_engine_chot_kenh"), \
                mock.patch.object(R, "dat_nguoi_keo"):
            actions = R._engine_route_decisions(56, anh, ("route", 11011, 55002))
        self.assertEqual(plan["users"], users5)
        self.assertNotIn("route_dest", actions.values())
        self.assertEqual(actions.get("stsm01"), "lap_party")

    def test_acc_tat_han_bi_bo_khoi_plan(self):
        st = R._pstate(56)
        plan = {"source": 11011, "dest": 55002, "city": 11011, "flag": 1,
                "users": ["a", "b", "c"], "leader": "a", "phase": "sync_city",
                "temporary_party": False}
        anh = SimpleNamespace(accs=[_acc("a", so_member=1), _acc("b")], lenh_tay_gen=0)
        with mock.patch.dict(st, {"manual_route_plan": plan, "kenh_dich": 1}), \
                mock.patch.object(R, "_clients_cua_party",
                                  return_value=[("a", object()), ("b", object())]), \
                mock.patch.object(R, "_engine_chot_kenh"), \
                mock.patch.object(R, "dat_nguoi_keo"):
            R._engine_route_decisions(56, anh, ("route", 11011, 55002))
        self.assertEqual(plan["users"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
