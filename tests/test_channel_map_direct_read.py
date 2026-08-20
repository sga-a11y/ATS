"""Leader DOC THANG map cua tung acc, khong bat member "bao cao".

Bug that (party.log 20/08, party 18):
  23:36:11 .. 23:36:57 [quanmot] (LEADER) cho acc bao cao map sau sync kenh (1/5, map yeu cau=14001)
  23:37:12 [quanmot] (LEADER) sync kenh/map TIMEOUT 60s (1/5) -> thoat, moi/reform lai
  23:37:12 [quanmot] -> BUMP reform_gen, ca party ve thanh regroup      ... lap lai moi 60s
trong khi CUNG LUC:
  23:37:10 [quanhai] (member) pos=(1360, 830) map=14823 combat=False    (va 3 acc con lai)
Leader dot ~6' (23:36 -> 23:43) de cho mot bao cao khong bao gio toi, trong khi map cua ca 4 acc
la thu no DOC DUOC NGAY: ca party chay chung MOT tien trinh, account_clients[u].current_map.

Test KHONG viet lai logic: RUT DUNG doan ma tu run_party_digioi.py roi exec voi du lieu gia.
"""
import textwrap
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")

_START = "                    _live = {}"
_END = "                    if fail:"
_i = SRC.index(_START)
BLOCK = textwrap.dedent(SRC[_i:SRC.index(_END, _i)])
FUNC = "def _step():\n" + textwrap.indent(BLOCK, "    ") + "    return ('CHO TIEP', reports, done)\n"


class Client:
    def __init__(self, current_map, running=True):
        self.current_map = current_map
        self.running = running


def run_step(maps, expected_map=14001, expected=5, elapsed=30.0, reports=None):
    """maps = {acc: map}. Tra ve ('CHO TIEP'|False, reports, done)."""
    st = {"lock": threading.Lock(), "reconnecting": set()}
    logs = []
    ns = {
        "reports": dict(reports or {}),
        "done": False,
        "st": st,
        "pidx": 18,
        "expected": expected,
        "expected_map": expected_map,
        "_t0": time.time() - elapsed,
        "time": time,
        "label": "quanmot",
        "role": "LEADER",
        "party_accounts": lambda _p: [(u, "pw", False, False) for u in maps],
        "account_clients": {u: Client(m) for u, m in maps.items()},
        "log": type("L", (), {
            "warning": staticmethod(lambda f, *a: logs.append(f % a if a else f)),
            "info": staticmethod(lambda f, *a: logs.append(f % a if a else f)),
        }),
    }
    exec(FUNC, ns)
    out = ns["_step"]()
    if out is False:            # khoi ma `return False` -> khong phai tuple
        out = (False, ns["reports"], ns["done"])
    return out, logs


DUNG = 14001      # thanh leader muon tu
TRAIN = 14823     # map train


class TestChannelMapDirectRead(unittest.TestCase):
    def test_ca_party_da_dung_map_thi_XONG_NGAY_khong_cho_bao_cao(self):
        (kq, reports, done), _ = run_step({("acc%d" % i): DUNG for i in range(5)})
        self.assertEqual(kq, "CHO TIEP")     # khong bi return False
        self.assertEqual(len(reports), 5)    # dem du 5 du KHONG acc nao "bao cao"
        self.assertTrue(done)

    def test_acc_o_map_khac_thi_KHONG_dot_het_60s(self):
        maps = {"quanmot": DUNG, "quanhai": TRAIN, "quanba": TRAIN,
                "quanbon": TRAIN, "quannam": TRAIN}
        out, logs = run_step(maps, elapsed=30.0)
        self.assertIs(out[0], False)                       # regroup luon
        self.assertTrue(any("MAP KHAC" in x for x in logs), logs)
        self.assertTrue(any("14823" in x for x in logs), logs)   # noi RO acc dang o dau

    def test_10s_dau_van_cho_vi_teleport_lam_map_cu_con_sot(self):
        maps = {"quanmot": DUNG, "quanhai": TRAIN}
        out, logs = run_step(maps, expected=2, elapsed=5.0)
        self.assertEqual(out[0], "CHO TIEP")
        self.assertFalse(any("MAP KHAC" in x for x in logs), logs)

    def test_acc_dang_relogin_khong_co_client_thi_bo_qua(self):
        st_maps = {"quanmot": DUNG, "quanhai": DUNG}
        (kq, reports, _done), _ = run_step(st_maps, expected=2, elapsed=30.0)
        self.assertEqual(kq, "CHO TIEP")
        self.assertEqual(len(reports), 2)


if __name__ == "__main__":
    unittest.main()
