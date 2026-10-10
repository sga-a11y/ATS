"""Ngoc Phuc Than: viec NGOC (vut Ngoc Hu / deo / mo tui ra ngoc) chi lam o KHE TIEP TE.

Bug BL-1009-FF31 (user: "relog thi tu deo ngoc, dang train ngoc hu thi khong tu thay"). Do tren
party.log 09/10:
  * ngoc chi mon trong tran -> luc hong la DANG DANH; bot deo ngay luc do. Gui deo khi tran moi da
    bat dau hong 50% (173/344), gui 0-2s sau S:065-010 hong 5% (3/60). Thu lai 3 lan cung roi vao
    tran -> "THOI (cho login lai)" 25 lan / 22 acc.
  * client goc CHI thay ngoc trong MachineBox.Supply() = luc nhan S:065-010 (MachineBox.lua:880).
  * mo Tui Dai Phuc Than: 145/145 lan KHONG co S:023-008 -> bot khong biet ngoc ve, khong deo.
  * tui ra ngoc bi tinh chung cap 10 cai voi item tieu hao -> dung du 10 Dai Phuc Than la khong mo.
"""
import threading
import time
import types
import unittest
from unittest.mock import patch

from bot import client as C
from bot import config
from bot import party_engine as PE

GREAT_GEM = 0x5A2D
GREAT_BAG = 0xB5F4
GREAT_BLESSING = 0xB3D6
BROKEN_GEM = 0x59F0


def _game(bag, equipped=None, in_battle=False, khe=None):
    g = C.GameClient.__new__(C.GameClient)
    g.bag_slots = {s: [t, n] for s, (t, n) in bag.items()}
    g.equipped_items = list(equipped or [])
    g.running = True
    g._label = "test"
    g.sock = None
    g.send = lambda *a, **k: None
    g.state = types.SimpleNamespace(in_battle=in_battle)
    g.phuc_than_deo_lai = False
    g._khe_tiep_te = 0.0 if khe is None else time.time() - khe
    g.equip_calls, g.use_calls = [], []
    g.equip_item = lambda s: g.equip_calls.append(s) or True
    g.use_slot = lambda s, qty=1, target=0: g.use_calls.append((s, qty)) or True
    g._kiem_deo_ngoc = lambda tid, slot: None
    return g


def _cfg():
    return {t: v for t, v in config.USE_LOGIN_ITEMS.items() if v.get("phuc_than")}


def _run(g):
    with patch.object(C, "_load_gamedata_items", return_value={}), \
            patch.object(C.time, "sleep", return_value=None):
        g._use_items_from_cfg(_cfg(), "test")


HONG = [{"id": BROKEN_GEM, "damage": 250, "damaged_item_id": GREAT_GEM}]


class TestKheTiepTe(unittest.TestCase):
    def test_trong_tran_KHONG_deo_ma_giu_co(self):
        g = _game({5: (GREAT_GEM, 1)}, HONG, in_battle=True, khe=1)
        _run(g)
        self.assertEqual(g.equip_calls, [])
        self.assertTrue(g.phuc_than_deo_lai, "khong giu co -> khe sau khong ai deo")

    def test_ngay_sau_S065_010_thi_deo(self):
        g = _game({5: (GREAT_GEM, 1)}, HONG, khe=1)
        _run(g)
        self.assertEqual(g.equip_calls, [5])

    def test_ngoai_tran_nhung_qua_khe_thi_cho_khe_sau(self):
        """Giua hai tran (5-10s) tran moi sap bat dau -> server nuot lenh deo."""
        g = _game({5: (GREAT_GEM, 1)}, HONG, khe=10)
        _run(g)
        self.assertEqual(g.equip_calls, [])
        self.assertTrue(g.phuc_than_deo_lai)

    def test_server_khong_gui_S065_010_thi_lam_khi_ngoai_tran(self):
        for khe in (None, 200):
            g = _game({5: (GREAT_GEM, 1)}, HONG, khe=khe)
            _run(g)
            self.assertEqual(g.equip_calls, [5], khe)

    def test_khong_co_viec_ngoc_thi_khong_bat_co(self):
        """Dang deo ngoc tot -> khong duoc bat co (bat co = moi tran goi mot lan vo ich)."""
        g = _game({5: (GREAT_BAG, 3)}, [{"id": GREAT_GEM, "damage": 10, "damaged_item_id": 0}],
                  in_battle=True)
        _run(g)
        self.assertFalse(g.phuc_than_deo_lai)

    def test_S065_010_ghi_moc_khe(self):
        s = open("bot/client.py", encoding="utf-8").read()
        i = s.find('opcode == 0x41 and len(pkt) >= 9 and pkt[7:9] == b"\\x0a\\x00":')
        self.assertGreater(i, 0)
        self.assertIn("self._khe_tiep_te = time.time()", s[i:i + 300])


class TestTuiRaNgoc(unittest.TestCase):
    def test_mo_tui_xong_giu_co_de_khe_sau_deo(self):
        g = _game({4: (GREAT_BAG, 2)}, khe=1)
        _run(g)
        self.assertEqual(g.use_calls, [(4, 1)])
        self.assertTrue(g.phuc_than_deo_lai)
        self.assertGreater(g._tui_ngoc_mo_luc, 0)

    def test_vua_mo_tui_chua_thay_ngoc_thi_KHONG_mo_them(self):
        g = _game({4: (GREAT_BAG, 2)}, khe=1)
        g._tui_ngoc_mo_luc = time.time() - 30
        _run(g)
        self.assertEqual(g.use_calls, [])
        self.assertTrue(g.phuc_than_deo_lai)

    def test_ngoc_ve_tui_thi_deo_ngay(self):
        g = _game({4: (GREAT_BAG, 1), 9: (GREAT_GEM, 1)}, khe=1)
        g._tui_ngoc_mo_luc = time.time() - 30
        _run(g)
        self.assertEqual(g.equip_calls, [9])
        self.assertEqual(g._tui_ngoc_mo_luc, 0.0)

    def test_goi_023_005_co_ngoc_thi_bat_co(self):
        # Handler nam giua vong doc goi (khong tach ham) -> kiem bang nguon.
        s = open("bot/client.py", encoding="utf-8").read()
        i = s.find('pkt[7:9] == b"\\x05\\x00":')
        j = s.find('pkt[7:9] == b"\\x08\\x00":', i)
        self.assertIn("self.phuc_than_deo_lai = True", s[i:j])

    def test_tui_KHONG_tinh_vao_cap_10_cai(self):
        """AnhXanh BL-1009-FF31: 10 Dai Phuc Than an het cap -> tui bi loai, khong mo."""
        g = C.GameClient.__new__(C.GameClient)
        g.god_mission = 2
        g.phuc_than_tat = False
        g._label = "test"
        g.bag_slots = {1: [GREAT_BLESSING, 20], 40: [GREAT_BAG, 1]}
        seen = {}
        g._use_items_from_cfg = lambda cfg, lbl: seen.update(cfg)
        g.discard_junk_items = lambda: None
        g.use_phuc_than_items()
        self.assertEqual(seen[GREAT_BLESSING]["qty"], 10)
        self.assertIn(GREAT_BAG, seen)


class _ChayLuon:
    def __init__(self, target=None, daemon=None):
        self.target = target

    def start(self):
        self.target()


class TestKhongBoCuoc(unittest.TestCase):
    def test_that_bai_lien_tiep_van_thu_lai(self):
        g = _game({5: (GREAT_GEM, 1)})
        g._kiem_deo_ngoc = C.GameClient._kiem_deo_ngoc.__get__(g)
        with patch.object(C.threading, "Thread", _ChayLuon), \
                patch.object(C.time, "sleep", return_value=None):
            for _ in range(C.GameClient.PHUC_THAN_DEO_THU_LAI):
                g.phuc_than_deo_lai = False
                g._kiem_deo_ngoc(GREAT_GEM, 5, cho=0.0)
                self.assertTrue(g.phuc_than_deo_lai, "bo co = cho login lai")
        # Qua so lan -> gian ra, khong bo
        self.assertGreater(g._ngoc_thu_lai_sau, time.time())
        self.assertFalse(g.khe_thay_ngoc())
        self.assertNotIn("cho login lai", open("bot/client.py", encoding="utf-8").read()
                         .split("def _kiem_deo_ngoc(")[1].split("\n    def ")[0])


class _FakeClient:
    def __init__(self, khe):
        self._pe_pcfg = {"use_phuc_than": True}
        self.phuc_than_pending = False
        self.phuc_than_deo_lai = True
        self._khe = khe
        self.goi = 0

    def khe_thay_ngoc(self):
        return self._khe

    def use_phuc_than_items(self):
        self.goi += 1


class TestDuyTri(unittest.TestCase):
    def test_co_deo_lai_chi_goi_o_khe(self):
        c = _FakeClient(False)
        PE._duy_tri(c)
        self.assertEqual(c.goi, 0, "goi moi nhip 1s giua tran")
        c._khe = True
        PE._duy_tri(c)
        self.assertEqual(c.goi, 1)

    def test_su_kien_moi_van_goi_ngay(self):
        """Buff < 5 / ngoc hong: item tieu hao van dung ngay nhu cu (viec ngoc tu hoan)."""
        c = _FakeClient(False)
        c.phuc_than_deo_lai = False
        c.phuc_than_pending = True
        PE._duy_tri(c)
        self.assertEqual(c.goi, 1)


if __name__ == "__main__":
    unittest.main()
