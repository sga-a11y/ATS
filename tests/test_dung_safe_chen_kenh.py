"""DUNG YEN O SAFE (chen kenh) - them 08/10/2026, xem `documents/DUNG_SAFE_CHEN_KENH.md`.

User: acc chi vao map train, dung yen o safe, ghim DUNG kenh user chon de chen full kenh cho party
chinh train. "De che do bot tu chon diem train thi dung ngu ma chon che do dung yen nay."
"""
from __future__ import annotations

import os
import re
import sys
import time
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE  # noqa: E402
from bot import train_pick as TP  # noqa: E402

_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import gui  # noqa: E402
finally:
    sys.argv = _argv


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class Client:
    def __init__(self, pos=(0, 0), channel=2):
        self.pos = pos
        self.current_channel = channel
        self.flee_mode = False
        self._label = "t"
        self._pe_pcfg = {}
        self._pe_la_leader = True
        self.state = SimpleNamespace(in_battle=False)
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0
        self.calls = []

    def navigate_to(self, x, y, flee=True, abort=None):
        self.calls.append(("navigate_to", x, y, flee))
        self.pos = (x, y)
        return True

    def follow_path(self, path, flee=True, abort=None):
        self.calls.append(("follow_path", flee))
        return True

    def combat_ready(self):
        self.calls.append(("combat_ready",))

    def start_run_around(self):
        self.calls.append(("start_run_around",))

    def stop_run_around(self):
        self.calls.append(("stop_run_around",))

    def in_di_gioi(self):
        return False

    def kenh_dang_chac(self):
        return True

    def switch_channel(self, ch, **kw):
        self.calls.append(("switch_channel", ch))
        return True


def _ten(calls):
    return [c[0] for c in calls]


class TestCoDungSafe(unittest.TestCase):
    def test_bat_o_train_va_dg_train(self):
        for mode in ("train", "digioi_train"):
            self.assertEqual(TP.dung_safe_kenh(
                {"mode": mode, "stand_safe": True, "stand_channel": 7}), 7)

    def test_tu_chon_map_khong_bao_gio_dung_yen(self):
        self.assertEqual(TP.dung_safe_kenh({"mode": "train", "train_pick": "avg-25",
                                            "stand_safe": True, "stand_channel": 7}), 0)

    def test_tat_hoac_mode_khac(self):
        self.assertEqual(TP.dung_safe_kenh({"mode": "train", "stand_channel": 7}), 0)
        self.assertEqual(TP.dung_safe_kenh({"mode": "event", "stand_safe": True,
                                            "stand_channel": 7}), 0)
        self.assertEqual(TP.dung_safe_kenh(None), 0)

    def test_kenh_hong_thi_kenh_1(self):
        self.assertEqual(TP.dung_safe_kenh({"mode": "train", "stand_safe": True,
                                            "stand_channel": "x"}), 1)
        self.assertEqual(TP.dung_safe_kenh({"mode": "train", "stand_safe": True}), 1)


class TestThiHanh(unittest.TestCase):
    def test_ra_spot_di_safe_bang_flee_khong_danh(self):
        c = Client(pos=(0, 0))
        thong_ke = []
        PE.thi_hanh(c, PE.VIEC_RA_SPOT, lambda: True, dich=(500, 600), dung_safe=True,
                    duong_ra_spot=[(1, 1)], ghi_thong_ke=lambda *a: thong_ke.append(a))
        self.assertEqual(c.calls, [("navigate_to", 500, 600, True)])
        self.assertTrue(c.flee_mode)
        self.assertEqual(thong_ke, [])

    def test_da_dung_quanh_safe_thi_khong_di_nua(self):
        c = Client(pos=(510, 590))
        PE.thi_hanh(c, PE.VIEC_RA_SPOT, lambda: True, dich=(500, 600), dung_safe=True,
                    xe_dich=lambda p: (p[0] + 9, p[1] - 9))
        self.assertEqual(c.calls, [])

    def test_train_dung_im(self):
        c = Client()
        PE.thi_hanh(c, PE.VIEC_TRAIN, lambda: True, dung_safe=True)
        self.assertNotIn("combat_ready", _ten(c.calls))
        self.assertNotIn("start_run_around", _ten(c.calls))
        self.assertTrue(c.flee_mode)

    def test_khong_bat_thi_train_nhu_cu(self):
        c = Client()
        PE.thi_hanh(c, PE.VIEC_RA_SPOT, lambda: True, dich=(500, 600))
        self.assertIn("combat_ready", _ten(c.calls))
        self.assertFalse(c.flee_mode)

    def test_kenh_ghim_day_thi_gian_cach(self):
        c = Client(channel=2)
        c._chan_switch_result, c._chan_switch_target = 4, 9
        c._chan_switch_luc = time.time()
        self.assertFalse(PE.thi_hanh(c, PE.VIEC_DOI_KENH, lambda: True, dich=9, dung_safe=True))
        self.assertEqual(c.calls, [])
        c._chan_switch_luc = time.time() - PE.DUNG_SAFE_KENH_DAY_CHO_SEC - 1
        PE.thi_hanh(c, PE.VIEC_DOI_KENH, lambda: True, dich=9, dung_safe=True)
        self.assertEqual(c.calls, [("switch_channel", 9)])


class TestEngineChiPhaTrain(unittest.TestCase):
    def test_pha_dg_van_danh(self):
        cfg = {"mode": "digioi_train", "stand_safe": True, "stand_channel": 3}
        e = PE.PartyEngine(0, lambda: [], pha=PE.PHA_DG, pcfg=cfg)
        self.assertFalse(e._dung_safe())
        e.pha = PE.PHA_TRAIN
        self.assertTrue(e._dung_safe())


class TestGuiLuu(unittest.TestCase):
    def test_train_last_giu_co_dung_safe(self):
        tl = gui._train_last_of({"mode": "train", "start_city_id": 21864, "mob_index": -1,
                                 "stand_safe": True, "stand_channel": 5})
        self.assertEqual((tl["stand_safe"], tl["stand_channel"]), (True, 5))

    def test_ap_che_do_lay_lai_dung_safe_rieng_party(self):
        p = {"mode": "event", "stand_safe": False,
             "train_last": {"pick": "", "sc": 21864, "mob_index": -1,
                            "stand_safe": True, "stand_channel": 5}}
        d = gui._doi_che_do_preset(p, {"mode": "train"})
        self.assertEqual((d["start_city_id"], d["stand_safe"], d["stand_channel"]),
                         (21864, True, 5))


class TestApkGoiTheoViTri(unittest.TestCase):
    def test_hai_tham_so_cuoi_cung(self):
        py = _read("run_party_digioi.py")
        sig = re.search(r"def setup_party_runtime\((.*?)\):", py, re.S).group(1)
        self.assertTrue(sig.rstrip().rstrip(",").endswith("stand_safe=False, stand_channel=0"))
        kt = _read("android/app/src/main/java/com/tsbot/android/BotForegroundService.kt")
        self.assertRegex(kt, r"party\.questKey, party\.questLeader,\s*(//[^\n]*\n\s*)?"
                             r"party\.trainPick\.isEmpty\(\) && party\.standSafe, "
                             r"party\.standChannel,\s*\)")

    def test_store_luu_doc_ca_hai_key(self):
        kt = _read("android/app/src/main/java/com/tsbot/android/PartyStore.kt")
        for k in ('"stand_safe"', '"stand_channel"'):
            self.assertEqual(kt.count(k), 2, k)


if __name__ == "__main__":
    unittest.main()
