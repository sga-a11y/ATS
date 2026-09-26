"""APK: mode EVENT phai doc `noLeader` nhu cac mode khac, khong duoc hardcode "khong co leader".

User 13/09: "ban apk ko thay di danh" -> "quanmot la leader, ma ngu vay" -> "ko he tick cai do".

`BotForegroundService.kt` dung `ModeCfg(...)` de bao cho Python biet party co leader hay khong:

    RunModes.TRAIN        -> ModeCfg(..., "party", !party.noLeader, ...)
    RunModes.DIGIOI_TRAIN -> ModeCfg(..., "party", !party.noLeader, ...)
    RunModes.DIGIOI       -> ModeCfg(..., if (party.digioiSolo) false else !party.noLeader, ...)
    RunModes.EVENT        -> ModeCfg("event", 0, 0, -1, party.cityKey, "party", false)   <- HARDCODE

Rieng EVENT truyen thang `false`, nen MOI party chay event tren APK deu bi coi la khong co leader
du user khong tick "Khong co chu PT". Ben Python:

    _event_battle_kind(mode, has_leader, ev) -> None khi khong co leader
    event_stand_mode = event_mode and not event_party_mode and not event_solo_kind

-> acc vao map event roi DUNG YEN cho nguoi moi tay, khong bao gio tu lap party de danh.

CA THAT (APK, acc quanmot - LA leader cua party):

    16:30:10 [quanmot] (member) EVENT -> dung yen tai map event, cho moi tay (auto-accept)
    16:30:15 [quanmot] (member) pos=None map=12922 combat=False
    ... y het moi 5 giay ...
    16:38:21 [quanmot] (member) pos=None map=12922 combat=False

Tam phut khong danh mot tran. Ban PC KHONG dinh vi `gui.py` doc dung `no_leader_var` - dung cai
bay "chep tay o dau la o do lech" trong CLAUDE.md.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android",
                  "BotForegroundService.kt")


def _kt():
    with io.open(KT, encoding="utf-8") as fh:
        return fh.read()


def _dong_modecfg(src, mode):
    """Dong `RunModes.<mode> -> ModeCfg(...)` (co the tran nhieu dong)."""
    i = src.find("RunModes.%s -> ModeCfg(" % mode)
    if i < 0:
        return ""
    # Cat den nhanh KE TIEP (`RunModes.` hoac `else ->`), khong thi khoi lan sang nhanh khac va
    # test bat nham chuoi cua no.
    _sau = [x for x in (src.find("\n        RunModes.", i + 10),
                        src.find("\n        else ->", i + 10)) if x > 0]
    return src[i:min(_sau) if _sau else i + 400]


class TestEventDocNoLeader(unittest.TestCase):
    def setUp(self):
        self.src = _kt()

    def test_EVENT_khong_hardcode_khong_co_leader(self):
        khoi = _dong_modecfg(self.src, "EVENT")
        self.assertTrue(khoi, "mat nhanh RunModes.EVENT")
        self.assertIn("!party.noLeader", khoi,
                      "EVENT hardcode hasLeader -> moi party event tren APK mat leader")

    def test_EVENT_khong_con_chuoi_party_false(self):
        khoi = re.sub(r"//.*", "", _dong_modecfg(self.src, "EVENT"))
        self.assertNotIn('"party", false', khoi)


class TestCacModeKhacVanDung(unittest.TestCase):
    """Sua EVENT khong duoc lam hong cac mode da dung."""

    def setUp(self):
        self.src = _kt()

    def test_TRAIN_va_DIGIOI_TRAIN(self):
        for _m in ("TRAIN", "DIGIOI_TRAIN"):
            khoi = _dong_modecfg(self.src, _m)
            self.assertTrue(khoi, _m)
            self.assertIn("!party.noLeader", khoi, _m)

    def test_DIGIOI_solo_van_khong_leader(self):
        """DG SOLO: moi acc doc lap -> khong lap party (khac han 'khong co chu PT')."""
        khoi = _dong_modecfg(self.src, "DIGIOI")
        self.assertIn("if (party.digioiSolo) false else !party.noLeader", khoi)


class TestPhiaPythonDoiHasLeader(unittest.TestCase):
    """Neo ben Python de biet gia tri do dung de lam gi - sua mot ben la test do."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_event_party_mode_can_has_leader(self):
        i = self.src.find("def _event_battle_kind(")
        self.assertGreater(i, 0)
        j = self.src.find("\ndef ", i + 10)
        self.assertIn('mode == "event" and has_leader and kind in', self.src[i:j])

    def test_khong_co_leader_thi_roi_vao_dung_yen(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        self.assertEqual(R.party_modes.decide_mode("event", {"a": "vao_event"}, [account()],
                         event_kind="npc_repeat", has_leader=False), {"a": "nghi"})

    def test_dung_yen_phai_NOI_RO_ly_do(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.dict(R.config.PARTY_CONFIG, {0: {"mode": "event"}}, clear=True), \
                mock.patch.dict(R.config.PARTY_LEADER_ACC, {}, clear=True), \
                mock.patch.object(R, "_event_cua_party", return_value={"party_battle": {"kind": "npc_repeat"}}), \
                mock.patch.object(R.log, "warning") as warning:
            for _ in range(2):
                self.assertEqual(R._engine_mode_decisions(0, snapshot(), {"a": "vao_event"}), {"a": "nghi"})
        warning.assert_called_once()
        self.assertIn("KHONG CO LEADER", warning.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
