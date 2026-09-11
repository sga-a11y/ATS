"""KHONG CO LENH THI ACC KHONG QUYET GI CA.

User 11/09: "chan chan cai lon, dieu phoi dieu khien bot chu ai cho acc quyet dinh" -> "deo phai
chan gi het, theo lenh dieu phoi cho tao, dieu phoi ko ra lenh thi acc ko quyet gi ca".

CHIEU CU (sai): acc cu di, ai muon can thi phai dung ra CHAN. Moi cho quen chan la mot cho acc tu
quyet - va da quen that ba lan lien tiep:
    `_cho_leader_keo`              xoa 10/09 (member het han cho -> tu di -> party tan)
    `_chot_thanh_tap_ket(False)`   xoa 11/09 (member het han cho -> tu lap duong -> ve thanh)
    ca duong route ra bai          xoa 11/09 (ca nay)

CHIEU DUNG: acc CHI di khi dieu phoi giao viec cho chinh no. Khong lenh -> dung yen.

CA THAT (party 6, 11/09 - user: "dang di ra map train thi member lai tele ve thanh"):

    09:48:49 [party 6] gen 11: viec=lam                        <- dieu phoi KHONG ra lenh gi
    09:49:05 [ttmot]   qua cong idx=2 -> map 23000             <- leader dang KEO ca doi
    09:49:05 [party 6] gen 12: viec=lam                        <- van khong lenh gi
    09:49:08 [ttbon]   pre-route: tele trung gian ve thanh 12061 truoc
    09:49:08 [ttbon]   Teleport: dang o to doi (4 member) -> ROI DOI truoc
    09:49:08 [ttmot]   PARTY: 9ce7e44c ROI doi -> roster con 3 nguoi
    09:49:11 [party 6] gen 13: con lech map [12001, 12061, 23000]   <- biet SAU khi doi da tan

Dieu phoi chi bao `viec=lam` (party lanh, cu lam). Bon member TU khoi dong chuyen di ra bai cua
rieng chung. Ma moi duong ra bai deu bat dau bang teleport, va client chan teleport khi con trong
doi -> phai ROI DOI truoc. Bon dua tu roi, roster 4 -> 3 -> 2 -> 0, leader di tiep mot minh.

GIO: dieu phoi chot `nguoi_keo(pidx)` moi nhip. Acc doc lenh do y het cach no doc `party_dang_gom`.
"*" = khong ai phai cho ai (party khong co bot-leader). Nguoi duoc giao ma tat/rot thi dieu phoi
chuyen sang "*" - khong de ca party dung cho mot acc khong con chay (L0).
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


def _doc(ten):
    with io.open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


def _ma(s):
    s = re.sub(r'"""[\s\S]*?"""', "", s)
    return re.sub(r"#.*", "", s)


class _Gia:
    """Client toi thieu - chi nhung truong phep kiem duoc doc."""

    def __init__(self, pidx, user):
        self.party_idx = pidx
        self._username = user
        self._label = user

    _chan_tu_di_route = C.GameClient._chan_tu_di_route


class TestAccChiDiKhiDuocGiao(unittest.TestCase):
    def setUp(self):
        C.dat_nguoi_keo(7, None)

    def tearDown(self):
        C.dat_nguoi_keo(7, None)

    def test_CHUA_RA_LENH_thi_acc_KHONG_di(self):
        """Diem mau chot: mac dinh la KHONG di, khong phai 'di tru khi bi chan'."""
        self.assertTrue(_Gia(7, "a1")._chan_tu_di_route(23831))

    def test_duoc_giao_thi_di(self):
        C.dat_nguoi_keo(7, "a1")
        self.assertFalse(_Gia(7, "a1")._chan_tu_di_route(23831))

    def test_nguoi_khac_duoc_giao_thi_minh_KHONG_di(self):
        C.dat_nguoi_keo(7, "a1")
        self.assertTrue(_Gia(7, "a2")._chan_tu_di_route(23831))

    def test_giao_cho_TAT_CA_thi_ai_cung_di(self):
        C.dat_nguoi_keo(7, "*")
        self.assertFalse(_Gia(7, "a2")._chan_tu_di_route(23831))

    def test_acc_ngoai_party_khong_bi_rang_buoc(self):
        """Khong thuoc party nao thi khong co dieu phoi -> khong cho lenh cua ai."""
        self.assertFalse(_Gia(None, "a9")._chan_tu_di_route(23831))


class TestDieuPhoiLaNoiRaLENH(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_dieu_phoi_chot_nguoi_keo_moi_nhip(self):
        i = self.src.find("dat_nguoi_keo(pidx,")
        self.assertGreater(i, 0, "dieu phoi khong chot ai keo -> acc dung yen mai")

    def test_chot_ngay_canh_cac_lenh_cap_party_khac(self):
        """Cung mot cho quyet, cung mot nhip - khong de mot lenh chay o noi khac (L1)."""
        i_gom = self.src.find("dat_party_dang_gom(pidx, viec in")
        i_keo = self.src.find("dat_nguoi_keo(pidx,")
        self.assertGreater(i_gom, 0)
        self.assertLess(abs(i_keo - i_gom), 1500)

    def test_nguoi_keo_tat_thi_giao_lai(self):
        """L0: khong de ca party dung cho mot acc khong con chay."""
        i = self.src.find("dat_nguoi_keo(pidx,")
        khoi = self.src[max(0, i - 900):i]
        self.assertIn("khong con chay", khoi)


class TestAccKhongTuChanTuSuy(unittest.TestCase):
    """Acc KHONG duoc tu suy ra ai la leader - no chi doc lenh."""

    def setUp(self):
        src = _doc(os.path.join("bot", "client.py"))
        i = src.find("def _chan_tu_di_route(")
        self.than = _ma(src[i:src.find("\n    def ", i + 10)])

    def test_chi_doc_lenh_khong_doc_config(self):
        self.assertIn("nguoi_keo(self.party_idx)", self.than)
        self.assertNotIn("PARTY_LEADER_ACC", self.than,
                         "acc tu suy ra leader = acc tu quyet, du ket qua co dung")

    def test_khong_doc_roster_de_tu_ket_luan(self):
        self.assertNotIn("party_members", self.than)


class TestMemberSaiMapKhongTuReform(unittest.TestCase):
    """Member sai map giua luc leader keo qua tung cong la chuyen BINH THUONG - khong duoc tu goi
    `_do_reform` (ham do mo dau bang VE THANH = teleport = phai ROI DOI truoc).

    Party 6, 11/09:
        10:09:47 [tthai] (member) SAI MAP (o 23001, can 23831) -> retry reform
        10:10:10 [ttmot] qua cong idx=2 -> map 23000        <- leader DANG keo no toi
        10:10:12 [tthai] Teleport: dang o to doi (4 member) -> ROI DOI truoc
        10:10:12 [party 6] gen 9: viec=lam                  <- dieu phoi KHONG ra lenh gi
    """

    def setUp(self):
        src = _doc("run_party_digioi.py")
        i = src.find("KHONG THOAT, cho leader keo")
        self.assertGreater(i, 0, "mat nhanh member sai map")
        j = src.find("# --- MAP-TRAIN", i)
        self.than = _ma(src[i:j if j > i else i + 4000])

    def test_KHONG_con_tu_goi_do_reform(self):
        self.assertNotIn("_do_reform(to_spot=False)", self.than,
                         "member lai tu goi reform -> tu ve thanh -> roi doi giua luc leader keo")

    def test_van_co_loi_ra_khi_leader_chet_han(self):
        """Bo tu-quyet KHONG duoc bien thanh cho vo han (L9)."""
        self.assertIn("leader_gone", self.than)
        self.assertIn("_quit()", self.than)

    def test_van_thoat_khi_toi_noi(self):
        self.assertIn("c.current_map == sc", self.than)


class TestLenhKeoTheoViec(unittest.TestCase):
    """Dang GOM thi ca party deu phai tu di ve diem hen - do la ca duy nhat moi acc deu teleport."""

    def test_gom_thi_giao_cho_tat_ca(self):
        src = _doc("run_party_digioi.py")
        i = src.find("dat_nguoi_keo(pidx,")
        khoi = src[max(0, i - 1200):i]
        self.assertIn("viec in (VIEC_GOM, VIEC_DONG_BO)", khoi)


if __name__ == "__main__":
    unittest.main()
