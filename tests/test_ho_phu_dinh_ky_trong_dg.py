# -*- coding: utf-8 -*-
"""DI GIOI HO PHU phai duoc dung DINH KY trong luc DANG O TRONG Di Gioi.

User 22/09: "engine moi hinh nhu ko tu dung Di gioi ho phu".

Engine CU goi trong vong keepalive, MOI 3 PHUT, bat ke acc dang lam gi:
    if is_digioi and pcfg["use_digioi_ho_phu"] and time.time() >= next_ho_phu:
        if not c.in_combat(): _maybe_use_di_gioi_ho_phu("3p")

Engine MOI truoc day CHI goi trong `VIEC_DI_GIOI` - tuc luc acc dang DI VAO Di Gioi. Vao roi thi
engine giao `VIEC_TRAIN` (chay long vong) nen khong con goi nua, trong khi ho phu lai dung la thu
can dung LUC DANG O TRONG DG va con < 15 phut.

Hau qua: chi dung duoc SAU KHI acc da bi day ra khoi DG - mat han tac dung keo dai gio.
Ca that 22/09:
    02:41:17 [dtbay] Kenh hien tai = 2 ... map 12003      <- da o Quang Truong, NGOAI DG
    02:41:18 [dtbay] ENGINE: Di Gioi Ho Phu - con 3 phut (<15), da gui lenh dung
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE


class _Cli:
    _label = "t"
    running = True

    def __init__(self, trong_dg=True, danh=False, bat=True):
        self._pe_pcfg = {"use_digioi_ho_phu": bat}
        self._trong_dg = trong_dg
        self._danh = danh
        self.phuc_than_pending = False

    def in_di_gioi(self):
        return self._trong_dg

    def in_combat(self, *a, **k):
        return self._danh


class TestGoiDinhKy(unittest.TestCase):
    def _chay(self, c, lan=1):
        goi = []
        for _ in range(lan):
            PE._duy_tri(c, ho_phu=lambda _cli: goi.append(1))
        return len(goi)

    def test_dang_o_TRONG_DG_thi_CO_goi(self):
        self.assertEqual(self._chay(_Cli()), 1,
                         "vao DG roi la khong goi nua -> mat duong keo dai gio")

    def test_KHONG_o_trong_DG_thi_khong_goi(self):
        self.assertEqual(self._chay(_Cli(trong_dg=False)), 0)

    def test_TAT_tick_thi_khong_goi(self):
        self.assertEqual(self._chay(_Cli(bat=False)), 0)

    def test_DANG_DANH_thi_khong_goi(self):
        """Y flow cu: `if not c.in_combat()`. Gui giua tran la goi bi nuot."""
        self.assertEqual(self._chay(_Cli(danh=True)), 0)

    def test_CHU_KY_3_PHUT_khong_spam_moi_nhip(self):
        """Engine chay 1 nhip/giay - khong co chu ky thi ban 60 lenh/phut."""
        c = _Cli()
        self.assertEqual(self._chay(c, lan=5), 1, "goi lai moi nhip -> spam lenh")

    def test_het_chu_ky_thi_goi_LAI(self):
        c = _Cli()
        self._chay(c)
        c._pe_next_ho_phu = time.time() - 1.0      # gia lap da qua 3 phut
        self.assertEqual(self._chay(c), 1)

    def test_dat_moc_TRUOC_khi_goi(self):
        """Loi giua chung cung khong duoc spam lai moi nhip."""
        c = _Cli()

        def _no(_cli):
            raise RuntimeError("hong")

        PE._duy_tri(c, ho_phu=_no)
        self.assertGreater(float(getattr(c, "_pe_next_ho_phu", 0.0)), time.time())


class TestVanGoiLucVAO_DG(unittest.TestCase):
    """Duong cu (goi trong `VIEC_DI_GIOI`) KHONG duoc bo: no lo lan dung luc moi vao."""

    def test_nhanh_VIEC_DI_GIOI_van_con(self):
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("    if viec == VIEC_DI_GIOI:")
        self.assertGreater(i, 0)
        self.assertIn("ho_phu(client)", s[i:i + 1200])

    def test_VIEC_TRAIN_truyen_ho_phu_xuong__duy_tri(self):
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("_duy_tri(client, log=log, ho_phu=ho_phu)", s,
                      "khong truyen -> `_duy_tri` khong co gi de goi")


if __name__ == "__main__":
    unittest.main()
