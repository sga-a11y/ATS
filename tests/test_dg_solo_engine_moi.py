"""DI GIOI SOLO tren ENGINE MOI phai chay y ENGINE CU: moi acc tu vao DG, tu chay long vong danh.

Ca that BL-1008-C452 (08/10, APK, party 1 tick Di Gioi Solo): ca 5 acc deu `(member) vao world`
(solo -> khong co leader), engine van dem `n_members` = 5 va giao `lap_party` 511 lan trong 1.5
phut, khong ai moi ai, khong ai chay - dung im trong map DG 49942 toi khi user bam Stop.

Engine cu (truoc 90bfb10, 26/09), nhanh `elif digioi_solo`:
  - khong `do_channel_sync`, khong mo cua nhan moi party
  - du thuoc HP+SP -> `combat_ready` + `start_run_around`; thieu -> flee, DUNG YEN
  - khong thoat theo leader / khong reform / khong cho dong doi rot
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config
from bot import party_engine as E


def _a(u, **kw):
    kw.setdefault("map_id", 49942)
    kw.setdefault("kenh", 1)
    kw.setdefault("con_gio_dg", True)
    return E.AnhAcc(u, **kw)


def _anh_solo(accs):
    # DG solo: `_mode_can_lap_doi` False -> `n_members` = 0 -> engine `can_bao_nhieu` = 0.
    return E.AnhParty(0, accs, can_bao_nhieu=0, co_spot=True, pha=E.PHA_DG)


class TestModeKhongCanLapDoi(unittest.TestCase):
    def setUp(self):
        self._cu = config.PARTY_CONFIG
        self.addCleanup(setattr, config, "PARTY_CONFIG", self._cu)

    def test_DG_SOLO_khong_can_lap_doi(self):
        config.PARTY_CONFIG = {0: {"mode": "digioi", "digioi_mode": "solo"}}
        self.assertFalse(R._mode_can_lap_doi(0))

    def test_DG_PARTY_van_can_lap_doi(self):
        config.PARTY_CONFIG = {0: {"mode": "digioi", "digioi_mode": "party"}}
        self.assertTrue(R._mode_can_lap_doi(0))

    def test_digioi_train_khong_doc_co_solo(self):
        """`digioi_mode` chi la sub-option cua mode `digioi` - mode khac con sot gia tri cu thi
        khong duoc tat nham duong lap doi."""
        config.PARTY_CONFIG = {0: {"mode": "digioi_train", "digioi_mode": "solo"}}
        self.assertTrue(R._mode_can_lap_doi(0))


class TestQuyetDinhDGSolo(unittest.TestCase):
    def test_ca_5_acc_trong_DG_KHONG_lap_party_ma_TU_DANH(self):
        v = E.quyet_dinh(_anh_solo([_a("u%d" % i, trong_dg=True) for i in range(5)]))
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values(), v)
        self.assertTrue(all(x == E.VIEC_TRAIN for x in v.values()), v)

    def test_acc_CHUA_VAO_DG_khong_giu_chan_acc_da_vao(self):
        v = E.quyet_dinh(_anh_solo([_a("u1", trong_dg=True), _a("u2", map_id=12001)]))
        self.assertEqual(v["u1"], E.VIEC_TRAIN, "solo: acc vao roi thi tu danh, khong cho ai")
        self.assertEqual(v["u2"], E.VIEC_DI_GIOI)

    def test_acc_KHAC_HET_GIO_khong_bat_acc_con_gio_dung_yen(self):
        v = E.quyet_dinh(_anh_solo([_a("u1", trong_dg=True),
                                    _a("u2", trong_dg=True, con_gio_dg=False)]))
        self.assertEqual(v["u1"], E.VIEC_TRAIN)

    def test_DG_PARTY_van_giu_luat_du_doi(self):
        """Khong lan sang party that: thieu doi van lap party nhu cu."""
        accs = [_a("l", la_leader=True, so_member=0, trong_dg=True), _a("m1", trong_dg=True)]
        v = E.quyet_dinh(E.AnhParty(0, accs, can_bao_nhieu=1, co_spot=True, pha=E.PHA_DG))
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)


class _C:
    def __init__(self, thuoc=True, solo=True, la_leader=False):
        self._pe_pcfg = {"mode": "digioi", "digioi_mode": "solo" if solo else "party"}
        self._pe_la_leader = la_leader
        self._label = "c"
        self.flee_mode = None
        self.thuoc = thuoc
        self.chay = False

    def in_di_gioi(self):
        return True

    def has_hp_and_sp_items(self):
        return self.thuoc

    def combat_ready(self):
        pass

    def start_run_around(self):
        self.chay = True

    def stop_run_around(self):
        self.chay = False


class TestThiHanhTrainDGSolo(unittest.TestCase):
    def test_member_solo_TU_chay_long_vong(self):
        c = _C()
        self.assertTrue(E.thi_hanh(c, E.VIEC_TRAIN, lambda: True))
        self.assertTrue(c.chay, "solo khong co leader keo - acc phai tu chay long vong")
        self.assertFalse(c.flee_mode)

    def test_thieu_thuoc_thi_DUNG_YEN_co_lai_thi_CHAY_TIEP(self):
        c = _C(thuoc=False)
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertFalse(c.chay)
        self.assertTrue(c.flee_mode)
        c.thuoc = True
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertTrue(c.chay)
        self.assertFalse(c.flee_mode)

    def test_member_party_van_KHONG_tu_chay(self):
        """Party that: chi leader chay long vong (do that 27/09) - khong doi."""
        c = _C(solo=False)
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertFalse(c.chay)


if __name__ == "__main__":
    unittest.main()
