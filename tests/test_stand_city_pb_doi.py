# -*- coding: utf-8 -*-
"""Mode `stand` / `city` PHAI di PHO BAN TO DOI nhu engine cu.

Bao loi BL-1007-8C5F (07/10, party 1, mode stand, user: "che do login tai cho k di pho ban doi"):
    13:35:43 [CaoManHoa] ENGINE: XONG nhiem vu ngay      <- dua cuoi cung xong daily, o5 chua lam
    13:35:43 ... 13:36:51 khong mot dong `ENGINE: ... ->` nao
Engine ra `pb_doi` / `pb_doi_theo`, nhung `party_modes.decide_mode` cua mode stand ep moi viec
ngoai `lap_party`/`doi_kenh` thanh `nghi` (city cung the). Engine cu truoc 26/09 (`90bfb10`)
van chay PB doi luc login cho ca stand lan city (`_do_startup_team` khong loai mode nao).

Stand/city danh PB TAI CHO: buoc "ve thanh tap ket truoc" cua nhanh PB la cho party dang o bai
train; o stand/city thanh tap ket co the la thanh con sot tu phien truoc (phien 1 cua bao loi
chon Tu Chau) -> `ve_thanh` bi ep `nghi` -> ket vinh vien.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E
from bot import party_modes


def _anh(pb_tai_cho, thanh_dich=None, xong_daily_97=True):
    def a(u, **kw):
        kw.setdefault("map_id", 12001)
        kw.setdefault("kenh", 4)
        return E.AnhAcc(u, song=True, xong_chore=True, **kw)
    accs = [a("goldhaise98", la_leader=True, xong_daily=True, viec_dang_lam="lap_party"),
            a("goldhaise99", xong_daily=True, viec_dang_lam="lap_party"),
            a("goldhaise200", xong_daily=True, viec_dang_lam="lap_party"),
            a("goldhaise97", kenh=2, xong_daily=xong_daily_97, viec_dang_lam="daily")]
    anh = E.AnhParty(0, accs, can_bao_nhieu=3, pha=E.PHA_TRAIN, pb_doi_level=20,
                     pb_tai_cho=pb_tai_cho)
    anh.dp_viec = E.DP_DONG_BO
    anh.thanh_dich = thanh_dich
    return anh


def _chuoi(mode, thanh_dich=None):
    anh = _anh(pb_tai_cho=mode in ("stand", "city"), thanh_dich=thanh_dich)
    return party_modes.decide_mode(mode, E.quyet_dinh(anh), anh.accs, target_map=12001)


PB = {"goldhaise98": "pb_doi", "goldhaise99": "pb_doi_theo",
      "goldhaise200": "pb_doi_theo", "goldhaise97": "pb_doi_theo"}


class TestStandCityDiPbDoi(unittest.TestCase):
    def test_stand_di_pb_doi(self):
        self.assertEqual(_chuoi("stand"), PB)

    def test_city_di_pb_doi(self):
        self.assertEqual(_chuoi("city"), PB)

    def test_stand_city_khong_ve_thanh_tap_ket_truoc(self):
        # Thanh tap ket con sot tu phien train truoc (Tu Chau 15001) -> van danh PB tai cho.
        for mode in ("stand", "city"):
            self.assertEqual(_chuoi(mode, thanh_dich=15001), PB, mode)

    def test_mode_train_van_ve_thanh_truoc(self):
        # Hanh vi cu cua train (user chot 21/09) KHONG doi.
        anh = _anh(pb_tai_cho=False, thanh_dich=15001)
        self.assertEqual(set(E.quyet_dinh(anh).values()), {E.VIEC_VE_THANH})

    def test_chua_xong_daily_thi_chua_di_pb(self):
        anh = _anh(pb_tai_cho=True, xong_daily_97=False)
        v = party_modes.decide_mode("stand", E.quyet_dinh(anh), anh.accs)
        self.assertEqual(v["goldhaise97"], "daily")
        self.assertNotIn("pb_doi", v.values())

    def test_dang_danh_member_giu_pb_doi_theo_nhu_mode_train(self):
        acc = E.AnhAcc("m", song=True, dang_danh=True)
        self.assertEqual(party_modes.decide_mode("stand", {"m": "pb_doi_theo"}, [acc]),
                         {"m": "pb_doi_theo"})

    def test_event_chaos_vs_khong_doi(self):
        acc = E.AnhAcc("m", song=True, map_id=1)
        v = party_modes.decide_mode("event", {"m": "pb_doi_theo"}, [acc], event_kind="chaos_vs",
                                    event_map=1)
        self.assertEqual(v, {"m": "solo_event_run"})


class TestCapNhatDatCoPbTaiCho(unittest.TestCase):
    def test_cap_nhat_engine_dat_co_theo_mode(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('eng.pb_tai_cho = eng.pcfg.get("mode") in ("stand", "city")', s)


if __name__ == "__main__":
    unittest.main()
