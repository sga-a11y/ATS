# -*- coding: utf-8 -*-
"""DANG TRONG TRAN thi KHONG giao viec DI CHUYEN - de acc danh xong da.

Teleport / doi kenh bi TRAN CHAN (client game chan thang), nen lenh do that bai NGAY va nhip sau
engine giao lai - thanh vong quay khong lam duoc gi, vua ton lenh vua nhin nhu bot dang doi acc
bo tran chay ve thanh. Engine cu luon `_wait_combat_clear` / `_ra_safe_truoc_khi_doi_kenh` truoc
nhung buoc nay.

Ca that 17/09 party 56 (user: "sao vua danh vua doi tele ve thanh la sao"):
    19:44:49 ENGINE: 've_map' giao lai 220 lan lien tiep cho tik906 - viec chay xong ngay
    19:45:29 ENGINE: 've_map' giao lai 260 lan lien tiep cho tik906
    19:45:50 [tksau] BATTLE SEND g=4 t=1 source=(2, 2) skill=10000   <- chinh no dang danh
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E


def _a(u, **kw):
    kw.setdefault("map_id", 11532)
    kw.setdefault("kenh", 1)
    return E.AnhAcc(u, **kw)


def _anh(accs, viec=E.DP_DI_TRAIN, thanh=11011, keo="l"):
    a = E.AnhParty(55, accs, can_bao_nhieu=len(accs) - 1, co_spot=True)
    a.dp_viec = viec
    a.nguoi_keo = keo
    a.thanh_dich = thanh
    return a


class TestDangDanhThiKhongDiChuyen(unittest.TestCase):
    def test_nguoi_keo_dang_danh_thi_KHONG_giao_ve_map(self):
        accs = [_a("l", la_leader=True, so_member=4, dang_danh=True), _a("m1"), _a("m2")]
        v = E.quyet_dinh(_anh(accs))
        self.assertEqual(v["l"], E.VIEC_NGHI, "tele bi tran chan -> lenh quay vong vo nghia")

    def test_khong_danh_thi_VAN_di_binh_thuong(self):
        accs = [_a("l", la_leader=True, so_member=4), _a("m1"), _a("m2")]
        self.assertEqual(E.quyet_dinh(_anh(accs))["l"], E.VIEC_VE_MAP)

    def test_chan_du_cac_viec_DI_CHUYEN(self):
        """Tele / doi kenh / ra spot deu bi tran chan nhu nhau."""
        for _viec, _dp in ((E.VIEC_VE_THANH, None), (E.VIEC_RA_SPOT, E.DP_RA_QUAI)):
            accs = [_a("l", la_leader=True, so_member=4, dang_danh=True), _a("m1")]
            anh = _anh(accs, viec=_dp or E.DP_GOM)
            if _dp is None:
                anh.reform_moi = True          # `gom` di bang reform_gen
            self.assertEqual(E.quyet_dinh(anh)["l"], E.VIEC_NGHI, _viec)

    def test_DANH_thi_van_duoc_giao(self):
        """`train` khong phai viec di chuyen - dang danh la dung dang train."""
        accs = [_a("l", la_leader=True, so_member=4, dang_danh=True,
                   viec_dang_lam=E.VIEC_TRAIN), _a("m1", dang_danh=True)]
        anh = _anh(accs, viec=E.DP_LAM)
        self.assertEqual(E.quyet_dinh(anh)["l"], E.VIEC_TRAIN)

    def test_acc_KHAC_khong_bi_anh_huong(self):
        accs = [_a("l", la_leader=True, so_member=0, dang_danh=True, map_id=11011),
                _a("m1", map_id=11532)]
        v = E.quyet_dinh(_anh(accs, keo="*"))
        self.assertEqual(v["l"], E.VIEC_NGHI)
        # m1 chua ve toi diem gom va party chua du -> `ve_thanh` (khong phai `ve_map`), cai can
        # kiem la no VAN duoc giao viec chu khong bi cua "dang danh" cua dua khac lam cam.
        self.assertEqual(v["m1"], E.VIEC_VE_THANH, "dua khong danh van phai di")


if __name__ == "__main__":
    unittest.main()
