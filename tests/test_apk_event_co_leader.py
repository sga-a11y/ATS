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

        # Y ENGINE CU: khong leader bot -> VAO map event roi DUNG YEN, mo cua nhan loi moi
        # (`lap_party` voi acc khong phai leader = chi `set_party_invite_ready`). Truoc day ra
        # `nghi` -> party 7 (27/09) dung o 12003 khong vao event.
        self.assertEqual(R.party_modes.decide_mode("event", {"a": "vao_event"}, [account()],
                         event_kind="npc_repeat", has_leader=False), {"a": "vao_event"})
        self.assertEqual(R.party_modes.decide_mode("event", {"a": "nghi"},
                         [account(trong_event=True, so_member=0)], event_kind="floor_crawl",
                         has_leader=False), {"a": "lap_party"})
        # DA VAO DOI nguoi that -> dung yen theo ho, khong `lap_party` nua (27/09 party 7).
        self.assertEqual(R.party_modes.decide_mode("event", {"a": "nghi"},
                         [account(trong_event=True, so_member=4)], event_kind="floor_crawl",
                         has_leader=False), {"a": "nghi"})
        # Viec uu tien va event XONG van giu nguyen
        self.assertEqual(R.party_modes.decide_mode("event", {"a": "daily", "b": "doi_thuong"},
                         [account(), account("b", trong_event=True)], event_kind="floor_crawl",
                         has_leader=False), {"a": "daily", "b": "doi_thuong"})

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
                mock.patch.object(R.log, "info") as info:
            for _ in range(2):
                self.assertEqual(R._engine_mode_decisions(0, snapshot(), {"a": "vao_event"}),
                                 {"a": "vao_event"})
        _dong = [c for c in info.call_args_list if "KHONG CO LEADER" in str(c.args[0])]
        self.assertEqual(len(_dong), 1)



class TestDoiTruongWhitelistKhongPhaiPartyLa(unittest.TestCase):
    """27/09 party 7: 4 acc vao doi cua nguoi trong WHITELIST, len tang 12923 -> roster ve ->
    engine giao `roi_party_la` ca 4 vi doi truong "khong phai leader bot"."""

    def _cli(self, **kw):
        from types import SimpleNamespace as NS
        base = dict(self_entity=b"\x01" * 8, party_idx=0, entity_names={},
                    _nguoi_moi_da_nhan=None)
        base.update(kw)
        return NS(**base)

    def _hop_le(self, c, cap, leader=None):
        from bot.client import GameClient
        return GameClient.doi_truong_hop_le(c, cap, leader)

    def test_doi_truong_trong_whitelist_hop_le(self):
        from unittest import mock
        from bot import config
        nguoi = b"\xe3\xf4\xe4\x4c" + b"\x00" * 4
        c = self._cli(entity_names={nguoi: {"NguoiThat"}})
        with mock.patch.object(config, "leaders_for", lambda p: ["nguoithat"], create=True):
            self.assertTrue(self._hop_le(c, nguoi))

    def test_nguoi_minh_da_nhan_loi_moi_hop_le_ke_ca_chua_biet_ten(self):
        from unittest import mock
        from bot import config
        nguoi = b"	" * 8
        c = self._cli(_nguoi_moi_da_nhan=nguoi)
        with mock.patch.object(config, "leaders_for", lambda p: [], create=True):
            self.assertTrue(self._hop_le(c, nguoi))

    def test_nguoi_ngoai_whitelist_van_la_party_la(self):
        from unittest import mock
        from bot import config
        la = b"\x07" * 8
        c = self._cli(entity_names={la: {"ThangLa"}})
        with mock.patch.object(config, "leaders_for", lambda p: ["nguoithat"], create=True):
            self.assertFalse(self._hop_le(c, la))
            self.assertTrue(self._hop_le(c, la, la))      # la leader bot -> hop le

    def test_engine_hoi_whitelist_truoc_khi_roi_party(self):
        for p in ("run_party_digioi.py",
                  os.path.join("android", "app", "src", "main", "python", "train_bot",
                               "run_party_digioi.py")):
            with io.open(os.path.join(ROOT, p), encoding="utf-8") as fh:
                src = fh.read()
            i = src.find("def _engine_routine_decisions(")
            khoi = src[i:src.find("\ndef ", i + 10)]
            self.assertIn("doi_truong_hop_le(captain", khoi, p)
            self.assertNotIn("captain not in (own, leader_entity)", khoi, p)


if __name__ == "__main__":
    unittest.main()
