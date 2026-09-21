"""LENH TAY cua GUI (teleport ve thanh / di map) phai toi duoc party chay ENGINE MOI.

Ca that 21/09 (user: "P21 dang train -> chon map -> chon thanh thi ko co gi xay ra ca"):
`party_teleport_city` chi dat `st["cmd"]` roi tang `st["cmd_gen"]`, va NOI DUY NHAT doc gen do la
vong keepalive cua `run_account` (engine cu). P21 la party DAU TIEN chay engine moi
(`PARTY_ENGINE_MOI_TU = 21`) nen lenh roi vao hu khong - bam xong khong co gi nhuc nhich.

Luat o day:
  1. Lenh tay CAT TRUOC MOI THU - ke ca cua "chua nen ra lenh". User bam la lenh ro rang, de no
     xep hang sau chuoi gom/train thi co khi khong bao gio toi luot.
  2. Moi acc tu nho gen DA LAM (`_pe_lenh_tay_gen`) - lam xong thi thoi, khong lap lai moi nhip.
  3. Thi hanh giu DUNG THU TU cua engine cu: cho het tran -> LEADER roi party -> teleport.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE


def _acc(u, leader=False, da_lam=0):
    return PE.AnhAcc(u, la_leader=leader, song=True, map_id=21001, kenh=1,
                     lenh_tay_da_lam=da_lam)


def _anh(accs, gen=0, **kw):
    kw.setdefault("can_bao_nhieu", len(accs) - 1)
    return PE.AnhParty(0, accs, lenh_tay_gen=gen, **kw)


class TestLenhTayCatTruocMoiThu(unittest.TestCase):
    def test_co_lenh_moi_thi_ca_party_lam_ngay(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", leader=True), _acc("a2")], gen=3))
        self.assertEqual(ket["a1"], PE.VIEC_LENH_TAY)
        self.assertEqual(ket["a2"], PE.VIEC_LENH_TAY)

    def test_cat_truoc_ca_cua_CHO(self):
        """"Chua nen ra lenh" khong duoc nuot lenh cua user."""
        ket = PE.quyet_dinh(_anh([_acc("a1", leader=True)], gen=1, cho_ly_do="leader dang rot"))
        self.assertEqual(ket["a1"], PE.VIEC_LENH_TAY)

    def test_cat_truoc_ca_lenh_GOM_cua_dieu_phoi(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", leader=True), _acc("a2")], gen=1,
                                 dp_viec="gom", reform_moi=True, thanh_dich=12001))
        self.assertEqual(set(ket.values()), {PE.VIEC_LENH_TAY})


class TestKhongLamLaiKhiDaXong(unittest.TestCase):
    def test_acc_da_lam_gen_do_thi_thoi(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", leader=True, da_lam=3), _acc("a2", da_lam=3)], gen=3))
        self.assertNotIn(PE.VIEC_LENH_TAY, ket.values(),
                         "lam xong roi ma van giao lai -> teleport lien tuc")

    def test_nguoi_xong_CHO_nguoi_chua_xong(self):
        """Mot dua da teleport, dua kia chua -> dua xong phai DUNG YEN, khong di train truoc."""
        ket = PE.quyet_dinh(_anh([_acc("a1", leader=True, da_lam=3), _acc("a2", da_lam=0)], gen=3))
        self.assertEqual(ket["a2"], PE.VIEC_LENH_TAY)
        self.assertEqual(ket["a1"], PE.VIEC_NGHI)

    def test_lenh_MOI_HON_thi_lam_lai(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", leader=True, da_lam=3)], gen=4))
        self.assertEqual(ket["a1"], PE.VIEC_LENH_TAY)

    def test_chua_co_lenh_nao_thi_khong_dinh_toi(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", leader=True), _acc("a2")], gen=0))
        self.assertNotIn(PE.VIEC_LENH_TAY, ket.values())


class TestNoiDayDayDu(unittest.TestCase):
    def test_engine_doc_cmd_gen(self):
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            pe = fh.read()
        self.assertIn("def _lenh_tay_gen(self)", pe)
        i = pe.find("def chup(self)")
        than = pe[i:pe.find("\n    def ", i + 10)]
        self.assertIn("lenh_tay_gen=", than, "chup anh khong doc gen -> khong bao gio thay lenh")

    def test_run_party_noi_ca_HAI_callback(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("doc_lenh_tay=", src, "khong noi -> engine khong doc duoc cmd_gen")
        self.assertIn("lenh_tay_fn=", src, "khong noi -> engine khong thi hanh duoc")
        self.assertIn('int(_pstate(_p).get("cmd_gen", 0) or 0)', src)

    def test_thi_hanh_giu_dung_thu_tu_cua_engine_cu(self):
        """cho het tran -> LEADER roi party -> teleport. Teleport bat buoc ROI DOI truoc."""
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _lenh_tay_engine_moi(")
        self.assertGreater(i, 0)
        than = src[i:src.find("\ndef ", i + 10)]
        _cho = than.find("in_combat(")
        _roi = than.find("leave_party()")
        _tele = than.find("go_to_town(")
        self.assertGreater(_cho, 0, "teleport giua tran -> server nuot lenh")
        self.assertLess(_cho, _roi, "phai cho het tran TRUOC khi huy party")
        self.assertLess(_roi, _tele, "teleport ma con trong doi -> client chan")

    def test_ghi_lai_gen_DA_LAM(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _lenh_tay_engine_moi(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("_pe_lenh_tay_gen", than, "khong ghi lai -> lam di lam lai moi nhip")


if __name__ == "__main__":
    unittest.main()
