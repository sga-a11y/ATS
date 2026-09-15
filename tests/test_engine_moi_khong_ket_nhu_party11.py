"""DIEN TAP: dung ca that da giet party 11 (15/09) cho chay tren ENGINE MOI.

Ca that, party 11 ket 22 phut (`luumuoi` im 64 phut):
    11:24:17 [luumuoi] Dungeon: con 1 luot FREE (flag 0x3030) -> vao FREE   <- PB don, phai leave_party
    11:25:22 [luumuoi] (member) ca party xong dungeon                        <- IM TU DAY, 0 dong/64'
    12:07..12:27 [party 11] REFORM gen -> 24,25,26,27,28,29,30               <- lenh gom, 3 phut/lan
    12:27:51 [luusau] (LEADER) -> REFORM party (gen 30)                      <- leader lam dung
    12:27:51 [luusau] reform: dieu phoi bao GOM -> thoi moi                  <- khong moi vi lech map
Party o 2 map: 23011 (Cua thanh Linh Lang - thanh gom) va 23851 (Rung Ich Duong - map train).

GOC: `do_daily_dungeon()` phai `leave_party()` -> party vo -> `luumuoi` roi vao vong
`while not st["invited"].is_set()`. Vong do nghe lenh KENH va `rally_gen` nhung KHONG nghe
`reform_gen` - ma lenh gom map lai di bang `reform_gen`. Ba ben deu "dung luat" nen ket vinh vien.

Engine moi khong co vong cho nao, nen cung KHONG CO CHO de ket. Bai nay ep no chung minh dieu do.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E

THANH = 23011      # Cua thanh Linh Lang
BAI = 23851        # Rung Ich Duong (map train)


class _CliGia:
    """Client gia co mot dac tinh QUAN TRONG: `di_lau` = di duong mat nhieu giay.

    Day chinh la cho engine cu chet: acc dang ket trong mot viec dai thi khong nghe thay lenh.
    """

    def __init__(self, map_id=BAI, kenh=1, members=0, di_lau=0.0):
        self.running = True
        self.current_map = map_id
        self.current_channel = kenh
        self.party_members = list(range(members))
        self.flee_mode = True
        self._pe_xong_chore = True
        self._di_lau = di_lau
        self.da_di = []

    def in_combat(self, *a, **k):
        return False

    def dang_lam_viec_vat(self):
        return False

    def in_di_gioi(self):
        return self.current_map == 49942

    def digioi_minutes_live(self):
        return 120                      # het gio DG -> pha train

    def follow_smart_route(self, dest_map, safe, abort=None, flee=True):
        t0 = time.time()
        while time.time() - t0 < self._di_lau:      # di duong lau
            if abort is not None and abort():
                return False                        # co lenh moi -> NHA RA
            time.sleep(0.01)
        self.current_map = int(dest_map)
        self.da_di.append(int(dest_map))
        return True

    def navigate_to(self, x, y, flee=True, abort=None, **k):
        return True

    def switch_channel(self, ch, *a, **k):
        self.current_channel = int(ch)
        return True

    def invite_train_party_participants(self, gap=1.0):
        return True

    def set_party_invite_ready(self, ready=True):
        pass

    def combat_ready(self):
        pass


def _engine(clients, can=3, spot=(100, 100)):
    def _doc():
        return [(u, c, u == "luusau") for u, c in clients]
    return E.PartyEngine(10, _doc, can_bao_nhieu=can, doc_spot=lambda: spot)


def _cho(dieu_kien, giay=6.0):
    het = time.time() + giay
    while time.time() < het:
        if dieu_kien():
            return True
        time.sleep(0.02)
    return False


class TestKhongLapLaiCaParty11(unittest.TestCase):
    def test_acc_lac_o_map_khac_DUOC_GOM_VE(self):
        """Ca that: `luumuoi` o 23851, leader + `luutam` o 23011, ket 22 phut. Engine moi phai
        don ve MOT map trong vai nhip."""
        luusau = _CliGia(map_id=THANH, members=2)     # leader
        luutam = _CliGia(map_id=THANH)
        luumuoi = _CliGia(map_id=BAI)                 # dua lac
        eng = _engine([("luusau", luusau), ("luutam", luutam), ("luumuoi", luumuoi)])
        eng.start()
        try:
            self.assertTrue(
                _cho(lambda: luumuoi.current_map == THANH),
                "engine moi cung de acc lac ngoi mai nhu party 11")
        finally:
            eng.stop()

    def test_acc_DANG_DI_DUONG_van_nhan_duoc_lenh_moi(self):
        """Day la dung cho engine cu chet. `luumuoi` dang ket trong mot viec dai; lenh moi (doi
        dich) phai CAT NGANG viec do, khong cho no "nghe thay"."""
        luusau = _CliGia(map_id=THANH, members=2)
        luumuoi = _CliGia(map_id=BAI, di_lau=30.0)     # di duong 30 giay
        eng = _engine([("luusau", luusau), ("luumuoi", luumuoi)], can=1)
        eng.start()
        try:
            w = eng._workers["luumuoi"]
            self.assertTrue(_cho(lambda: w.viec_hien_tai() == E.VIEC_VE_MAP),
                            "engine khong giao viec gom")
            t0 = time.time()
            w.giao(E.VIEC_DOI_KENH)                    # lenh moi toi giua chung
            self.assertTrue(_cho(lambda: w.viec_hien_tai() == E.VIEC_DOI_KENH, giay=5.0),
                            "viec dai KHONG nha ra -> y het benh da giet party 11")
            self.assertLess(time.time() - t0, 5.0, "lenh moi phai toi trong vai giay, khong 22 phut")
        finally:
            eng.stop()

    def test_acc_VUA_XONG_PB_DON_khong_bi_bo_roi(self):
        """`do_daily_dungeon` phai `leave_party()` -> roster ve 0. Engine phai lap lai party chu
        khong de acc do ngoi cho loi moi khong bao gio toi."""
        luusau = _CliGia(map_id=BAI, members=0)        # leader: party vua vo
        luumuoi = _CliGia(map_id=BAI, members=0)
        eng = _engine([("luusau", luusau), ("luumuoi", luumuoi)], can=2)
        eng.start()
        try:
            self.assertTrue(
                _cho(lambda: eng.viec_hien_tai.get("luumuoi") == E.VIEC_LAP_PARTY),
                "party vo ma engine khong lap lai -> acc ngoi cho vinh vien")
        finally:
            eng.stop()

    def test_lenh_KHONG_BAO_GIO_bi_nuot_qua_nhieu_nhip(self):
        """Engine cu: lenh di qua `reform_gen`, vong cho nao khong doc con so do thi DIEC vinh vien.
        Engine moi: moi nhip deu quyet dinh lai tu anh chup, khong co cho de nuot lenh."""
        luusau = _CliGia(map_id=THANH, members=2)
        luumuoi = _CliGia(map_id=BAI)
        eng = _engine([("luusau", luusau), ("luumuoi", luumuoi)], can=1)
        for _ in range(5):
            v = eng.nhip()
            self.assertEqual(v["luumuoi"], E.VIEC_VE_MAP,
                             "nhip nao cung phai ra lai lenh, khong duoc nuot")

    def test_khong_acc_nao_IM_qua_lau(self):
        """`luumuoi` im 64 phut la dau hieu ro nhat cua benh. Engine phai giao viec cho MOI acc
        song o MOI nhip - khong ai duoc roi ra ngoai danh sach."""
        cl = [("luusau", _CliGia(map_id=THANH, members=2)),
              ("luutam", _CliGia(map_id=THANH)),
              ("luumuoi", _CliGia(map_id=BAI))]
        eng = _engine(cl, can=2)
        v = eng.nhip()
        self.assertEqual(set(v), {"luusau", "luutam", "luumuoi"},
                         "co acc khong duoc giao viec -> no se im nhu luumuoi")


class TestKhongKetOPhaDiGioi(unittest.TestCase):
    """HET GIO DI GIOI -> phai doi pha TRAIN. Engine moi la nguoi DUY NHAT lam duoc viec nay.

    Hai cho doi pha cua engine cu deu khong chay voi party engine moi:
        `run_account`      - engine moi khong chay kich ban nay   (cua chan so 2)
        `_dieu_phoi_quyet` - bi cam dung vao party engine moi     (cua chan so 1)
    Thieu doan doi pha thi party ket o pha DG VINH VIEN: moi acc `con_gio_dg=False` -> VIEC_NGHI
    -> dung im mai mai. Dung cai L0 cam.
    """

    def _eng(self, het_gio=True, trong_dg=False):
        class _C(_CliGia):
            def digioi_minutes_live(self):
                return 120 if het_gio else 0

            def in_di_gioi(self):
                return trong_dg

        cl = [("luusau", _C(map_id=THANH, members=2)), ("luumuoi", _C(map_id=BAI))]
        ghi = []
        eng = _engine(cl, can=1)
        eng.pha = E.PHA_DG
        eng._ghi_pha = ghi.append
        return eng, ghi

    def test_het_gio_thi_DOI_PHA_ngay_trong_nhip_do(self):
        eng, ghi = self._eng(het_gio=True)
        v = eng.nhip()
        self.assertEqual(eng.pha, E.PHA_TRAIN, "ket o pha DG vinh vien")
        self.assertEqual(ghi, [E.PHA_TRAIN], "khong ghi nguoc ra state -> nhip sau bi doc lai la DG")
        # Doi pha roi thi phai quay ve chuoi gom NGAY trong nhip do, khong cho them mot giay.
        # (`nghi` cua leader la dung: no dang dung o map dich, cho dua kia ve.)
        self.assertEqual(v["luumuoi"], E.VIEC_VE_MAP, "doi pha roi ma ca party van dung im")

    def test_CON_GIO_thi_KHONG_doi_pha(self):
        """Mot acc con gio ma ca party bo di train la no mat gio DG."""
        eng, ghi = self._eng(het_gio=False)
        eng.nhip()
        self.assertEqual(eng.pha, E.PHA_DG)
        self.assertEqual(ghi, [])

    def test_DANG_TRONG_DG_thi_KHONG_doi_pha(self):
        """Dong ho co the da bao het gio trong khi acc VAN dang danh not trong instance."""
        eng, ghi = self._eng(het_gio=True, trong_dg=True)
        eng.nhip()
        self.assertEqual(eng.pha, E.PHA_DG, "keo acc ra giua luc con dang danh trong DG")

    def test_sau_khi_doi_pha_thi_quay_ve_chuoi_gom(self):
        eng, _g = self._eng(het_gio=True)
        eng.nhip()
        v = eng.nhip()
        self.assertEqual(v["luumuoi"], E.VIEC_VE_MAP)


class TestAccRotRoiRelogin(unittest.TestCase):
    """Acc rot -> supervisor relogin -> `GameClient` MOI HOAN TOAN.

    Worker cu van tro vao client CU DA CHET thi no goi ham tren mot socket dong, va acc do VINH
    VIEN khong nhan duoc lenh nua - mot kieu "im lang" y het `luumuoi` ngay 15/09. Engine phai
    gan client moi cho worker da co.
    """

    def test_client_moi_duoc_gan_lai_cho_worker(self):
        cl = [("luusau", _CliGia(map_id=THANH, members=2)), ("luumuoi", _CliGia(map_id=BAI))]
        eng = _engine(cl, can=1)
        eng.start()
        try:
            w = eng._workers["luumuoi"]
            cu = w.client
            moi = _CliGia(map_id=BAI)              # relogin -> client hoan toan khac
            cl[1] = ("luumuoi", moi)
            eng.start()                            # dang ky lai (supervisor goi lai sau relogin)
            self.assertIs(w.client, moi, "worker con om client CU DA CHET -> acc im vinh vien")
            self.assertIsNot(w.client, cu)
        finally:
            eng.stop()

    def test_khong_tao_worker_TRUNG_cho_cung_mot_acc(self):
        """Hai worker cho mot acc = hai luong cung dieu khien mot client."""
        cl = [("luusau", _CliGia(members=2)), ("luumuoi", _CliGia())]
        eng = _engine(cl, can=1)
        eng.start()
        try:
            eng.start()
            eng.start()
            self.assertEqual(len(eng._workers), 2)
        finally:
            eng.stop()

    def test_gan_client_moi_thi_BO_viec_dang_lam(self):
        """Viec dang chay la viec tren client cu - giu lai la thi hanh tren socket da dong."""
        cl = [("luusau", _CliGia(map_id=THANH, members=2)), ("luumuoi", _CliGia(map_id=BAI))]
        eng = _engine(cl, can=1)
        eng.start()
        try:
            w = eng._workers["luumuoi"]
            w.giao(E.VIEC_VE_MAP)
            _cho(lambda: w.viec_hien_tai() == E.VIEC_VE_MAP)
            cl[1] = ("luumuoi", _CliGia(map_id=BAI))
            eng.start()
            self.assertTrue(_cho(lambda: w.viec_hien_tai() == E.VIEC_NGHI, giay=3.0),
                            "van chay tiep viec cua client da chet")
        finally:
            eng.stop()


class TestPhaDiGioiTrenEngine(unittest.TestCase):
    def test_con_gio_DG_thi_ca_party_vao_DG_khong_gom_map(self):
        class _ConGio(_CliGia):
            def digioi_minutes_live(self):
                return 0                  # con nguyen 120 phut

        cl = [("luusau", _ConGio(map_id=THANH, members=2)),
              ("luumuoi", _ConGio(map_id=BAI))]
        eng = _engine(cl, can=1)
        eng.pha = E.PHA_DG
        v = eng.nhip()
        self.assertEqual(v["luumuoi"], E.VIEC_DI_GIOI)
        self.assertNotIn(E.VIEC_VE_MAP, v.values(),
                         "gom map truoc khi vao DG = mat phut EXP vo ich")

    def test_het_gio_DG_thi_quay_ve_chuoi_gom_binh_thuong(self):
        cl = [("luusau", _CliGia(map_id=THANH, members=2)), ("luumuoi", _CliGia(map_id=BAI))]
        eng = _engine(cl, can=1)
        eng.pha = E.PHA_TRAIN
        self.assertEqual(eng.nhip()["luumuoi"], E.VIEC_VE_MAP)


if __name__ == "__main__":
    unittest.main()
