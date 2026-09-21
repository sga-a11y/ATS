"""Engine moi mua HP/SP - phai goi DUNG chu ky va DUNG nhip cua flow cu.

Loi that (phat hien 21/09 khi user hoi "khong tick tu mua HP SP nhung bot van di mua"):
`_duy_tri` goi `client.buy_hp_sp()` KHONG THAM SO, trong khi ham can 6 tham so bat buoc:

    def buy_hp_sp(self, buy_hp, hp_qty, hp_thresh, buy_sp, sp_qty, sp_thresh)

-> TypeError, bi nuot vao `except` va chi ghi "mua thuoc loi (bo qua)". Party chay engine moi ma
bat tick mua HP/SP thi KHONG BAO GIO mua duoc, con loi thi nam im trong log warning. Chua lo ra
vi hien khong party nao bat co do.

Va cua cu `has_hp_and_sp_items()` sai loai cau hoi: no hoi "con item HP/SP nao khong", con flow cu
hoi "DU TRU co tut duoi nguong user dien khong" - `buy_hp_sp` TU kiem nguong do.
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


class _C:
    _label = "acc"
    running = True

    def __init__(self, tra=False, danh=False):
        self.goi = []
        self._tra = tra
        self._danh = danh
        self._pe_pcfg = {"buy_hp": True, "hp_qty": 500, "hp_thresh": 400000,
                         "buy_sp": True, "sp_qty": 600, "sp_thresh": 300000}

    def in_combat(self):
        return self._danh

    def buy_hp_sp(self, buy_hp, hp_qty, hp_thresh, buy_sp, sp_qty, sp_thresh):
        self.goi.append((buy_hp, hp_qty, hp_thresh, buy_sp, sp_qty, sp_thresh))
        return self._tra

    # `_duy_tri` con dung hai thu nay
    phuc_than_pending = False

    def use_phuc_than_items(self):
        raise AssertionError("khong duoc goi khi khong bat phuc than")


class TestGoiDUNG_CHU_KY(unittest.TestCase):
    def test_truyen_DU_6_tham_so_tu_config(self):
        c = _C()
        PE._duy_tri(c)
        self.assertEqual(c.goi, [(True, 500, 400000, True, 600, 300000)],
                         "goi thieu/sai tham so -> TypeError, khong bao gio mua duoc")

    def test_KHONG_bat_tick_thi_KHONG_goi(self):
        c = _C()
        c._pe_pcfg = {"buy_hp": False, "buy_sp": False}
        PE._duy_tri(c)
        self.assertEqual(c.goi, [], "user khong tick ma van di mua")

    def test_chi_bat_SP_thi_van_goi(self):
        """Hai tick doc lap - bat mot cai la phai di (ham tu loc ben trong)."""
        c = _C()
        c._pe_pcfg = {"buy_hp": False, "buy_sp": True, "sp_qty": 10, "sp_thresh": 1}
        PE._duy_tri(c)
        self.assertEqual(len(c.goi), 1)
        self.assertFalse(c.goi[0][0])
        self.assertTrue(c.goi[0][3])


class TestNhipVaCuaChan(unittest.TestCase):
    def test_DANG_TRAN_thi_khong_di_mua(self):
        """Chuyen mua DOI MAP - di giua tran la bo tran."""
        c = _C(danh=True)
        PE._duy_tri(c)
        self.assertEqual(c.goi, [])

    def test_moi_2_TIENG_mot_lan(self):
        """Ban cu goi MOI NHIP (1 giay) -> keo acc ra khoi bai train lien tuc."""
        c = _C()
        PE._duy_tri(c)
        PE._duy_tri(c)
        PE._duy_tri(c)
        self.assertEqual(len(c.goi), 1, "goi lai truoc han -> acc khong con o bai train")
        self.assertGreater(getattr(c, "_pe_next_buy_hpsp", 0), time.time() + 7000)

    def test_qua_han_thi_di_lai(self):
        c = _C()
        PE._duy_tri(c)
        c._pe_next_buy_hpsp = time.time() - 1
        PE._duy_tri(c)
        self.assertEqual(len(c.goi), 2)

    def test_dat_moc_TRUOC_khi_goi(self):
        """Dat sau khi goi thi ham nem loi la moc khong duoc dat -> spam lai moi nhip."""
        class _No(_C):
            def buy_hp_sp(self, *a):
                raise RuntimeError("server loi")
        c = _No()
        PE._duy_tri(c)   # khong duoc nem ra ngoai
        self.assertGreater(getattr(c, "_pe_next_buy_hpsp", 0), time.time() + 7000,
                           "loi mot lan ma moc khong dat -> thu lai moi giay")


class TestKhongDungNhamPhepThu(unittest.TestCase):
    def test_KHONG_dua_vao_has_hp_and_sp_items(self):
        """`has_hp_and_sp_items()` hoi "con item nao khong"; flow cu hoi "du tru duoi nguong
        chua" - va `buy_hp_sp` da tu kiem nguong do."""
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _duy_tri(")
        than = src[i:src.find("\ndef ", i + 10)]
        ma = "\n".join(l for l in than.split("\n") if not l.strip().startswith("#"))
        self.assertNotIn("has_hp_and_sp_items", ma)
        self.assertIn("hp_thresh", ma, "khong truyen nguong -> ham khong biet luc nao can mua")


if __name__ == "__main__":
    unittest.main()
