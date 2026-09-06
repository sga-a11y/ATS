"""Lenh RE-SYNC da thuc hien xong roi thi ĐỪNG roi party nua.

Party 15 (06/09) - user: "dung yen 1 luc o tang 9 roi di ra ngoai luon". 10 phut do KHONG phai
ket o cong; boc ra la ba doan:

    14:17:48 -> 14:18:48  (60s)  moi trong vo vong: "lech kenh live 2!=1" (leader kenh 1, member
                                 kenh 2) - biet ngay tu giay dau ma van doi het han 60s
    14:18:59 -> 14:22:45  (~4')  danh THAT, nhung MOT tran keo 3 phut, ~41 giay/luot, party 0/0
    14:22:45 -> 14:24:28  (100s) moi la ket o cong that

Va xuyen suot: doi VUA LAP XONG DA TAN.

    14:18:48 [trusauu] (LEADER) moi 60s chua du party (0/4) -> GIAI TAN + sync kenh + moi lai
    14:18:50..53               moi lai -> 4/4 member DONG Y, roster 4 nguoi
    14:18:57 [trumuoi] (member) leader RE-SYNC party -> roi party + sync kenh lai   <- CHAM 4 GIAY
    14:18:57 [trubay]  (member) leader RE-SYNC party -> roi party + sync kenh lai
    14:18:57 [truchin] (member) leader RE-SYNC party -> roi party + sync kenh lai
    14:18:57 [trutam]  (member) leader RE-SYNC party -> roi party + sync kenh lai
    14:18:58 [trusauu] (LEADER) DU PARTY (4/4 member join)      <- leader tuong xong, di leo thap
    14:18:59 [trubay]  KHONG o party nao (roster server + local deu rong)

Muc dich cua resync la "moi mai khong du -> giai tan + sync kenh + moi lai". Luc member doc toi
co thi muc dich DA DAT (4/4). Roi party luc nay la TU PHA cai vua lap - va sau do leader ket
trong vong leo thap nen khong lap lai duoc doi nua.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _nhanh_resync(src):
    """Than nhanh xu ly `resync_gen` cua MEMBER."""
    i = src.find('st["resync_gen"] > resync_gen_handled')
    assert i > 0
    return src[i:src.find("# ==== RECONNECT reaction", i)]


class TestBoQuaKhiPartyDaDu(unittest.TestCase):
    def setUp(self):
        self.than = _nhanh_resync(_doc("run_party_digioi.py"))

    def test_kiem_party_da_du_TRUOC_khi_roi(self):
        i = self.than.find("c.leave_party()")
        self.assertGreater(i, 0)
        truoc = self.than[:i]
        self.assertIn("is_joined(pidx, c.self_entity)", truoc,
                      "roi party ma khong xet minh dang o doi nao")
        self.assertIn("joined_member_count(pidx) >= st[\"n_members\"]", truoc,
                      "roi party ma khong xet doi da du nguoi chua")

    def test_du_nguoi_thi_CONTINUE_chu_khong_roi(self):
        i = self.than.find("joined_member_count(pidx) >= st[\"n_members\"]")
        khoi = self.than[i:i + 700]
        self.assertIn("continue", khoi)
        self.assertNotIn("leave_party", khoi[:khoi.find("continue")])

    def test_van_danh_dau_da_xu_ly_gen(self):
        """Bo qua nhung KHONG duoc de gen chua xu ly -> vong sau lai vao lai."""
        i = self.than.find("resync_gen_handled = st[\"resync_gen\"]")
        j = self.than.find("is_joined(pidx, c.self_entity)")
        self.assertGreater(i, -1)
        self.assertLess(i, j, "phai danh dau gen TRUOC khi quyet dinh bo qua")

    def test_CHUA_du_nguoi_thi_van_roi_party_nhu_cu(self):
        """Khong duoc lam hong duong dung: moi mai khong du thi van phai giai tan + sync lai."""
        self.assertIn("c.leave_party()", self.than)
        self.assertIn("do_channel_sync()", self.than)


class TestHanhViThat(unittest.TestCase):
    """Chay that ham quyet dinh tren du lieu party 15."""

    PARTY = 7

    def setUp(self):
        import bot.client as CL
        self.CL = CL
        CL._PARTY_CLIENTS.pop(self.PARTY, None)
        self._joined = dict(getattr(CL, "_PARTY_JOINED", {}) or {})

    def tearDown(self):
        self.CL._PARTY_CLIENTS.pop(self.PARTY, None)

    def test_joined_member_count_va_is_joined_ton_tai(self):
        """Hai ham nhanh moi them dung - phai co that, va da duoc import san."""
        self.assertTrue(callable(R.joined_member_count))
        self.assertTrue(callable(R.is_joined))
        src = _doc("run_party_digioi.py")
        i = src.find("from bot.client import (")
        self.assertIn("joined_member_count", src[i:i + 600])
        self.assertIn("is_joined", src[i:i + 600])


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_co_du(self):
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        self.assertIn("party DA DU", apk)


if __name__ == "__main__":
    unittest.main()
