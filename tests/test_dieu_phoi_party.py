"""DIEU PHOI PARTY: BOT quyet dinh party lam gi, KHONG phai luong cua acc leader.

Rule user chot 05/09: "bo me cai leader quyet dinh party lam gi di, bot la nguoi quyet dinh".

BUG GOC (party 19, 05/09, ket 2 GIO 42 PHUT - do tren party.log that):
    14:05:29  4 member xong DG -> "DUNG YEN cho party (4/5) | CON THIEU: quan801"
    14:38:48  [quanmot] "Di Gioi con lai: 0h20m"   <- nhip dem gio, dong CUOI CUNG
    14:39:45  leader roi vao vong moi party TRAN -> in "lech map live 12001!=12003" 488 LAN
    ~14:59    het gio DG cua leader - KHONG AI KIEM -> khong bao gio bao "xong DG"
    16:47:07  van nguyen trang thai do
Vong do chi co 2 loi ra: mat ket noi hoac Stop. Khong doc gio DG, khong doc reform_gen, khong
goi _resync_ck -> EP DONG BO CUNG KHONG PHA DUOC.

Va luoi an toan cuoi cung (`luat watcher "party thieu nguoi qua lau"`) thi CHET TU LUC VIET RA:
`st["training_started"]` chi duoc DOC dung mot cho, khong ai GHI -> luat do chua tung chay
(dem tren log ca ngay: THIEU NGUOI 0 lan, DEADLOCK 2227 lan).
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class _C:
    """Client gia: dieu phoi CHI duoc doc nhung truong nay."""

    def __init__(self, map_id=None, channel=None, dg_phut=0.0, running=True, roster=None):
        self.current_map = map_id
        self.current_channel = channel
        self._dg = dg_phut
        self.running = running
        # ROSTER SERVER (`0x0d`). Tu 07/09 dieu phoi dem doi bang day - `joined_member_count` la bo
        # dem trong cua bot va no om STALE (party 1: bot tuong du doi trong khi leader lap lai
        # "KHONG o party nao (roster server + local deu rong)" suot 44 phut).
        self.party_members = [b"x" * 8] * (2 if roster is None else roster)

    def digioi_minutes_live(self):
        return self._dg


class _Nen(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._jmc = R.joined_member_count
        R.joined_member_count = lambda pidx: self._joined
        self._joined = len(self.ACCS) - 1        # mac dinh: da du party
        self._clients = dict(R.account_clients)
        self._stops = dict(R.account_stops)
        R.account_clients.clear()
        R.account_stops.clear()
        R._party_state.pop(self.PARTY, None)
        self._pcfg = dict(getattr(config, "PARTY_CONFIG", {}))
        config.PARTY_CONFIG = {self.PARTY: {"mode": "digioi_train"}}

    def tearDown(self):
        R.party_accounts = self._accounts
        R.joined_member_count = self._jmc
        R.account_clients.clear(); R.account_clients.update(self._clients)
        R.account_stops.clear(); R.account_stops.update(self._stops)
        R._party_state.pop(self.PARTY, None)
        config.PARTY_CONFIG = self._pcfg

    def _dat(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c

    def _quyet(self, lech_tu=None):
        st = R._pstate(self.PARTY)
        return R._dieu_phoi_quyet(self.PARTY, st, R._acc_song(self.PARTY), lech_tu)


DG = None      # gan trong setUpModule


def setUpModule():
    global DG
    DG = config.DIGIOI_MAP_ID


class TestHetGioDGDieuPhoiTuKetLuan(_Nen):
    """Diem mau chot party 19: `dt_done` do CHINH LUONG ACC ghi, luong do ket thi khong bao gio
    ghi. Dieu phoi phai doc THANG dong ho, khong doi acc tu bao."""

    def test_con_gio_thi_chua_het(self):
        self.assertFalse(R._het_gio_dg(_C(map_id=DG, dg_phut=20)))

    def test_het_gio_theo_dong_ho(self):
        self.assertTrue(R._het_gio_dg(_C(map_id=DG, dg_phut=R.DIGIOI_LIMIT)))

    def test_bi_da_ra_ngoai_DG_va_gan_het_gio(self):
        """Dong ho noi bo DUNG YEN khi ra ngoai DG -> khong bao gio tu ve 0. Day dung la trang
        thai quanmot luc 15:00: bi da ve thanh 12003, con ~1 phut."""
        self.assertTrue(R._het_gio_dg(_C(map_id=12003, dg_phut=R.DIGIOI_LIMIT - 1)))

    def test_ra_ngoai_nhung_CON_NHIEU_gio_thi_KHONG_tinh_la_het(self):
        """Ra ngoai ma con nhieu gio = bi van/di cho khac, khong phai het gio - ep tinh la het
        thi acc bi khai tu oan (loi cu da tung mac)."""
        self.assertFalse(R._het_gio_dg(_C(map_id=12003, dg_phut=30)))


class TestDoiPhaKhongCanLeader(_Nen):
    def test_ca_party_het_gio_thi_dieu_phoi_doi_sang_train(self):
        self._dat(a1=_C(DG, 1, R.DIGIOI_LIMIT), a2=_C(DG, 1, R.DIGIOI_LIMIT),
                  a3=_C(DG, 1, R.DIGIOI_LIMIT))
        kh, ly_do, _ = self._quyet()
        self.assertEqual(kh["pha"], "train")
        self.assertEqual(R._pstate(self.PARTY)["dt_phase"], "train")
        self.assertIn("het gio", ly_do)

    def test_con_mot_acc_con_gio_thi_GIU_pha_DG(self):
        self._dat(a1=_C(DG, 1, R.DIGIOI_LIMIT), a2=_C(DG, 1, R.DIGIOI_LIMIT),
                  a3=_C(DG, 1, 10))
        kh, _l, _ = self._quyet()
        self.assertEqual(kh["pha"], "digioi")

    def test_LEADER_KET_van_doi_duoc_pha(self):
        """TAI HIEN party 19: leader het gio DG nhung luong cua no dang ket trong vong moi party
        nen khong bao gio ghi `dt_done`. Dieu phoi phai van doi pha duoc.
        Truoc khi sua, barrier doi `users <= st["dt_done"]` -> ket vinh vien."""
        st = R._pstate(self.PARTY)
        self._dat(a1=_C(12003, 1, R.DIGIOI_LIMIT),      # leader: het gio, bi da ve thanh
                  a2=_C(12001, 1, R.DIGIOI_LIMIT),
                  a3=_C(12001, 1, R.DIGIOI_LIMIT))
        with st["lock"]:
            st["dt_done"] = {"a2", "a3"}               # leader KHONG he tu bao
        kh, _l, _ = self._quyet()
        self.assertEqual(kh["pha"], "train", "leader ket la ca party ket lai lan nua")
        self.assertEqual(st["dt_phase"], "train")

    def test_member_duoc_tha_khi_dieu_phoi_doi_pha(self):
        """Barrier cua member phai nhin `dt_phase` - do la cua ra ma dieu phoi mo."""
        than = _src()
        i = than.find("def _dt_wait_all_digioi_done(")
        khoi = than[i:than.find("\ndef ", i + 10)]
        self.assertIn('st.get("dt_phase") == "train"', khoi)


class TestDuPartyThiKHONG_the_lech_kenh(_Nen):
    """DU PARTY = DA CUNG INSTANCE. Server khong cho o chung doi ma khac phan khu (`S:007-002`
    ma 3 <組隊不可換分區> la mat kia cua cung mot luat). Nen roster DU la bang chung manh hon
    `current_channel` - so BOT TU NHO, va no sai duoc (sot lai qua reconnect, ack cu; user kiem
    chung 30/08: bot hien ca 5 nick kenh 12, vao game xem la 12/12/12/2/1).

    User 07/09: "vi sao du pt roi ma van co lenh doi kenh de pt lai"."""

    def test_roster_DU_thi_bo_qua_lech_kenh(self):
        self._dat(a1=_C(12001, 1, 5, roster=2), a2=_C(12001, 2, 5, roster=2),
                  a3=_C(12001, 2, 5, roster=2))
        kh, _ly, _ = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertNotEqual(kh["viec"], R.VIEC_DONG_BO, "van ra lenh doi kenh khi party da du")
        self.assertNotEqual(kh["viec"], R.VIEC_GOM)

    def test_roster_THIEU_thi_van_xu_ly_lech_kenh(self):
        self._dat(a1=_C(12001, 1, 5, roster=0), a2=_C(12001, 2, 5, roster=0),
                  a3=_C(12001, 2, 5, roster=0))
        kh, _ly, _ = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertIn(kh["viec"], (R.VIEC_DONG_BO, R.VIEC_GOM))

    def test_lech_MAP_thi_VAN_xu_ly_du_party_du(self):
        """Lech MAP la su that DOC THANG duoc (`current_map` do server gui moi lan doi scene),
        khong phai suy tu so nho -> du party du van phai xu ly."""
        self._dat(a1=_C(12001, 1, 5, roster=2), a2=_C(12001, 1, 5, roster=2),
                  a3=_C(21836, 1, 5, roster=2))
        kh, _ly, _ = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertIn(kh["viec"], (R.VIEC_GOM, R.VIEC_DONG_BO),
                      "lech map ma bo qua -> party nam hai noi mai")


class TestPhatHienLechVaRaLENH(_Nen):
    """Chay o PHA TRAIN - do moi la cho viec gom co nghia. Pha DG cam gom han
    (xem TestPhaDIGIOI_KHONG_DUOC_GOM: acc nam rai trong/ngoai instance la binh thuong)."""

    def setUp(self):
        super().setUp()
        st = R._pstate(self.PARTY)
        with st["lock"]:
            st["dt_phase"] = "train"

    def test_lech_map_chua_du_lau_thi_chua_gom(self):
        self._dat(a1=_C(12003, 1, 5), a2=_C(12001, 1, 5), a3=_C(12001, 1, 5))
        kh, _l, lech_tu = self._quyet(lech_tu=None)
        self.assertIsNotNone(lech_tu, "phai bat dau tinh gio lech")
        self.assertNotEqual(kh["viec"], R.VIEC_GOM)

    def test_lech_map_qua_lau_thi_RA_LENH_GOM(self):
        self._dat(a1=_C(12003, 1, 5), a2=_C(12001, 1, 5), a3=_C(12001, 1, 5))
        kh, ly_do, _ = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertEqual(kh["viec"], R.VIEC_GOM)
        self.assertIn("MAP khac nhau", ly_do)

    def test_lech_kenh_CUNG_phai_co_an_han(self):
        """Ban dieu phoi dau tien cho lech kenh mot nhanh RIENG, khong an han giay nao:
            elif len(kenhs) > 1: viec = VIEC_GOM
        Ma trong luc gom thi acc dang teleport chuyen tiep - lech kenh/map la BINH THUONG.
        Ket qua party 17 (05/09 18:49-18:51): ra lenh gom moi vai giay, moi lenh abort moi acc
        dang di duong -> leader ket o thanh, member dung giua bai cho quai danh."""
        # roster 0: party CHUA lap -> luc do lech kenh moi la that (du party = da cung instance)
        self._dat(a1=_C(12001, 1, 5, roster=0), a2=_C(12001, 2, 5, roster=0),
                  a3=_C(12001, 2, 5, roster=0))
        kh, _l, lech_tu = self._quyet(lech_tu=None)
        self.assertNotEqual(kh["viec"], R.VIEC_GOM, "lech kenh ma gom NGAY = thrash")
        self.assertIsNotNone(lech_tu, "phai bat dau tinh gio lech kenh")

    def test_lech_kenh_qua_han_thi_DONG_BO_TAI_CHO_chu_khong_gom(self):
        """CUNG map ma lech kenh -> doi kenh la xong; keo ca party ve thanh chi ton mot vong di
        duong, va o cho khong co route (trong thap 2K) thi lenh gom KHONG AI THI HANH DUOC.

        Party 5 (06/09): ca 5 acc o map 12922, kenh [1,5] -> ra lenh GOM -> `_do_reform` in
        "khong co smart/legacy route -> bo qua" roi tra ve ngay -> leader quay 201.495 vong.
        """
        self._dat(a1=_C(12001, 1, 5, roster=0), a2=_C(12001, 2, 5, roster=0),
                  a3=_C(12001, 2, 5, roster=0))
        kh, ly_do, _ = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO)
        self.assertIn("kenh", ly_do)

    def test_lech_MAP_qua_han_thi_moi_GOM(self):
        """Gom ve cung cho chi dung khi lech MAP."""
        self._dat(a1=_C(12001, 1, 5), a2=_C(12061, 1, 5), a3=_C(12061, 1, 5))
        kh, ly_do, _ = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertEqual(kh["viec"], R.VIEC_GOM)
        self.assertIn("MAP khac nhau", ly_do)

    def test_an_han_du_dai_cho_mot_chuyen_teleport_gom(self):
        """Gom = ve thanh trung gian roi ve thanh tap ket, tung acc lech nhip vai chuc giay."""
        self.assertGreaterEqual(R.KE_HOACH_LECH_MAP_SEC, 45,
                                "an han qua ngan -> ra lenh gom giua luc dang gom")

    def test_cung_cho_nhung_thieu_nguoi_thi_MOI(self):
        """Thieu = ROSTER SERVER cua acc nao do chua du, khong phai bo dem trong cua bot."""
        self._dat(a1=_C(12001, 1, 5, roster=0), a2=_C(12001, 1, 5, roster=0),
                  a3=_C(12001, 1, 5, roster=0))
        self._joined = 0
        kh, _l, _ = self._quyet()
        self.assertEqual(kh["viec"], R.VIEC_MOI)

    def test_bo_dem_TRONG_noi_du_ma_roster_RONG_thi_van_MOI(self):
        """Ca that party 1 (07/09): `_PARTY_JOINED` con stale -> bot tuong du doi -> VIEC_LAM ->
        dieu phoi im 44 phut, trong khi server noi khong ai o trong doi ca."""
        self._dat(a1=_C(12001, 1, 5, roster=0), a2=_C(12001, 1, 5, roster=0),
                  a3=_C(12001, 1, 5, roster=0))
        self._joined = len(self.ACCS) - 1        # bo dem trong: "da du"
        kh, ly_do, _ = self._quyet()
        self.assertEqual(kh["viec"], R.VIEC_MOI, "van tin bo dem trong cua bot")
        self.assertIn("DOI chua du", ly_do)

    def test_du_ca_party_thi_LAM(self):
        self._dat(a1=_C(12001, 1, 5), a2=_C(12001, 1, 5), a3=_C(12001, 1, 5))
        kh, _l, _ = self._quyet()
        self.assertEqual(kh["viec"], R.VIEC_LAM)

    def test_het_lech_thi_XOA_dong_ho_lech(self):
        """Het lech phai GIU duoc `HET_LECH_CHAC_SEC` thi dong ho moi duoc go.

        Truoc day chi can MOT nhip thay cung map la reset ve 0 -> party lech NGAT QUANG khong bao
        gio chay du han, tuc khong bao gio duoc gom (party 1, 09/09: ba phut cho mot viec dieu phoi
        da biet tu giay dau). Nhung dong ho treo lai KHONG duoc bien thanh lenh - xem
        `test_het_lech_thi_KHONG_ra_lenh_du_dong_ho_con_treo`.
        """
        self._dat(a1=_C(12001, 1, 5), a2=_C(12001, 1, 5), a3=_C(12001, 1, 5))
        _kh, _l, lech_tu = self._quyet(lech_tu=time.time() - 100)
        self.assertIsNotNone(lech_tu, "moi het lech mot nhip da xoa -> lech ngat quang mat tuoi")
        _st = R._pstate(self.PARTY)
        _st["het_lech_tu"] = time.time() - R.HET_LECH_CHAC_SEC - 1   # da het lech DU LAU
        _kh, _l, lech_tu = self._quyet(lech_tu=lech_tu)
        self.assertIsNone(lech_tu)

    def test_het_lech_thi_KHONG_ra_lenh_du_dong_ho_con_treo(self):
        """Dong ho con treo (chua go) ma party da lanh -> tuyet doi khong duoc ra lenh dong bo."""
        self._dat(a1=_C(12001, 1, 5), a2=_C(12001, 1, 5), a3=_C(12001, 1, 5))
        kh, _l, _ = self._quyet(lech_tu=time.time() - 100)
        self.assertNotEqual(kh["viec"], R.VIEC_DONG_BO)
        self.assertNotEqual(kh["viec"], R.VIEC_GOM)


class TestBienQuyetDinhThanhHanhDONG(_Nen):
    """Party 19 chet vi leader BIET member lech map (in 488 lan) ma khong ai bien cai biet do
    thanh hanh dong. Ke hoach ma khong thi hanh thi vo nghia."""

    def test_lenh_GOM_thi_bump_reform_gen(self):
        st = R._pstate(self.PARTY)
        g0 = st["reform_gen"]
        R._dieu_phoi_thi_hanh(self.PARTY, st, {"viec": R.VIEC_GOM, "ly_do": "test"}, True)
        self.assertGreater(st["reform_gen"], g0, "ra lenh gom ma khong bump = khong ai dung day")

    def test_khong_doi_ke_hoach_thi_KHONG_bump_lien_tuc(self):
        """Bump moi nhip 2s la ca party bi giat lai mai, khong bao gio lam xong viec gi."""
        st = R._pstate(self.PARTY)
        g0 = st["reform_gen"]
        R._dieu_phoi_thi_hanh(self.PARTY, st, {"viec": R.VIEC_GOM, "ly_do": "test"}, False)
        self.assertEqual(st["reform_gen"], g0)

    def test_KHONG_ra_lenh_gom_don_dap(self):
        """Moi lenh gom ABORT moi acc dang di duong. Ra don dap = huy chinh viec vua ra lenh.
        Party 17 (05/09): gom luc 18:49:32, 18:49:36, 18:50:50, 18:50:56 -> leader bi
        'ABORT di duong reform' 4 lan trong 90 giay, ca party khong di xong buoc nao."""
        st = R._pstate(self.PARTY)
        kh = {"viec": R.VIEC_GOM, "ly_do": "test"}
        R._dieu_phoi_thi_hanh(self.PARTY, st, kh, True)
        g1 = st["reform_gen"]
        self.assertGreater(g1, 0, "lan dau phai bump")
        for _ in range(5):
            R._dieu_phoi_thi_hanh(self.PARTY, st, kh, True)
        self.assertEqual(st["reform_gen"], g1, "bump don dap -> ca party bi giat lai lien tuc")

    def test_het_cooldown_thi_duoc_gom_lai(self):
        st = R._pstate(self.PARTY)
        kh = {"viec": R.VIEC_GOM, "ly_do": "test"}
        R._dieu_phoi_thi_hanh(self.PARTY, st, kh, True)
        g1 = st["reform_gen"]
        with st["lock"]:
            st["dieu_phoi_gom_luc"] = time.time() - R.KE_HOACH_GOM_COOLDOWN - 1
        R._dieu_phoi_thi_hanh(self.PARTY, st, kh, True)
        self.assertGreater(st["reform_gen"], g1, "lech mai ma khong bao gio gom lai cung hong")

    def test_cooldown_du_dai_cho_mot_dot_gom_chay_xong(self):
        self.assertGreaterEqual(R.KE_HOACH_GOM_COOLDOWN, 120)


class TestGhiKeHoach(_Nen):
    def test_lan_dau_luon_tinh_la_doi(self):
        st = R._pstate(self.PARTY)
        self.assertTrue(R._ghi_ke_hoach(st, self.PARTY,
                                        {"pha": "digioi", "map": 1, "kenh": 1,
                                         "thanh": None, "viec": R.VIEC_LAM}))
        self.assertEqual(R._ke_hoach_gen(st), 1)

    def test_noi_dung_y_nguyen_thi_KHONG_tang_gen(self):
        st = R._pstate(self.PARTY)
        kh = {"pha": "digioi", "map": 1, "kenh": 1, "thanh": None, "viec": R.VIEC_LAM}
        R._ghi_ke_hoach(st, self.PARTY, kh)
        self.assertFalse(R._ghi_ke_hoach(st, self.PARTY, dict(kh)))
        self.assertEqual(R._ke_hoach_gen(st), 1)

    def test_doi_viec_thi_tang_gen(self):
        st = R._pstate(self.PARTY)
        kh = {"pha": "digioi", "map": 1, "kenh": 1, "thanh": None, "viec": R.VIEC_LAM}
        R._ghi_ke_hoach(st, self.PARTY, kh)
        R._ghi_ke_hoach(st, self.PARTY, dict(kh, viec=R.VIEC_GOM))
        self.assertEqual(R._ke_hoach_gen(st), 2)


class TestAccDaTatKhongKeoCaPartyChet(_Nen):
    def test_acc_bi_Stop_khong_tinh_vao_dieu_phoi(self):
        ev = threading.Event(); ev.set()
        R.account_stops["a3"] = ev
        self._dat(a1=_C(DG, 1, R.DIGIOI_LIMIT), a2=_C(DG, 1, R.DIGIOI_LIMIT), a3=_C(DG, 1, 5))
        self.assertEqual([u for u, _c in R._acc_song(self.PARTY)], ["a1", "a2"])
        kh, _l, _ = self._quyet()
        self.assertEqual(kh["pha"], "train", "acc da tat van keo ca party ket lai o pha DG")

    def test_acc_khong_running_bi_bo_qua(self):
        self._dat(a1=_C(DG, 1, 5), a2=_C(DG, 1, 5, running=False))
        self.assertEqual([u for u, _c in R._acc_song(self.PARTY)], ["a1"])


class TestKhongConVongMoiTRAN(unittest.TestCase):
    """Neo cau truc: vong nao cho 'du party' ma khong co duong ra la mot party 19 dang cho."""

    # Duong ra hop le o CAP PARTY (khong tinh `_stopped()` / `c.running`: hai cai do chi la
    # "bot tat" chu khong pha duoc the ket).
    LOI_RA = ("_resync_ck",              # ep dong bo (GUI/watchdog)
              "_ab()",                   # abort theo reform_gen
              "reform_gen",              # tu gom lai
              "_finish_digioi_train_if_time_over",   # het gio DG -> bao ca party
              "_dg_gather_giveup",       # acc khac het gio DG
              "_should_resync_incomplete_digioi_party")

    def _than_vong(self, src, sau):
        """Than vong lap = tu sau dong `while` toi khi thut le tro ve <= muc cua `while`."""
        dong = src[sau:].split("\n")
        thut0 = None
        ra = []
        for d in dong:
            if not d.strip():
                ra.append(d)
                continue
            t = len(d) - len(d.lstrip())
            if thut0 is None:
                thut0 = t
            elif t < thut0:
                break
            ra.append(d)
        return "\n".join(ra)

    def test_moi_vong_cho_du_party_deu_co_loi_ra(self):
        src = _src()
        thieu = []
        for m in re.finditer(r"while [^\n]*joined_member_count\([^\n]*:\n", src):
            than = self._than_vong(src, m.end())
            if not any(k in than for k in self.LOI_RA):
                thieu.append(src[:m.start()].count("\n") + 1)
        self.assertEqual(thieu, [],
                         "vong cho du party o dong %s khong co loi ra nao ngoai Stop/mat ket noi "
                         "-> dung the ket da giet party 19 trong 2h42" % thieu)

    def test_vong_moi_cua_leader_hoi_lai_dieu_phoi(self):
        src = _src()
        i = src.find("def _moi_theo_dieu_phoi(")
        self.assertGreater(i, 0, "chua co ham moi party theo dieu phoi")
        than = src[i:src.find("\n        def ", i + 10)]
        for can in ("_resync_ck", "VIEC_GOM", "_finish_digioi_train_if_time_over",
                    "_dg_gather_giveup", "reform_gen"):
            self.assertIn(can, than, "vong moi thieu kiem tra: %s" % can)

    def test_khong_con_vong_moi_tran_cu(self):
        self.assertNotIn("CHO VO HAN: du party moi danh", _src(),
                         "van con vong moi tran kieu cu")


class TestLenhGOMKhongDuocTATACC(unittest.TestCase):
    """BUG THAT 05/09 18:09 (party 10) - do chinh lan sua nay gay ra:

        18:09:06 [luumot] (LEADER) DU 4/4 member san sang -> MOI (theo entity)
        18:09:06 [luumot] (LEADER) dieu phoi bao GOM (party lech kenh [1, 2]) -> thoi moi party DG
        (het log - leader tat han, ca party dung)

    Nhanh moi party DG nam THANG trong than `run_account`, nen `return` o do = KET THUC
    run_account = TAT LUON ACC. Cac dong `return` ngay canh no deu di kem `c.close()` (Stop /
    mat ket noi) hoac co nhanh relogin rieng (`_finish_digioi_train_if_time_over` dat
    `_dt["relogin_train"]`). Nhanh dieu phoi thi khong co gi nhu the -> luong chet luon.

    Lenh GOM la lenh LAM VIEC KHAC, khong phai lenh tat acc.
    """

    def _khoi_gom_trong_vong_moi_DG(self):
        src = _src()
        i = src.find("MOI (theo entity)")
        self.assertGreater(i, 0, "khong tim thay vong moi party DG")
        j = src.find("dieu phoi bao GOM", i)
        self.assertGreater(j, 0, "vong moi party DG khong hoi dieu phoi")
        return src[j:j + 900]

    def test_lenh_GOM_o_vong_moi_DG_phai_continue_chu_khong_return(self):
        khoi = self._khoi_gom_trong_vong_moi_DG()
        truoc_continue = khoi[:khoi.find("continue")] if "continue" in khoi else khoi
        self.assertIn("continue", khoi, "nhanh GOM khong `continue` -> roi khoi vong")
        self.assertNotIn("\n                        return", truoc_continue,
                         "nhanh GOM `return` = ket thuc run_account = TAT ACC (bug party 10)")

    def test_lenh_GOM_phai_that_su_di_gom(self):
        """Thoi moi ma khong gom thi chi la doi cho ket, khong sua duoc gi."""
        self.assertIn("_do_reform()", self._khoi_gom_trong_vong_moi_DG())

    def test_cac_nhanh_GOM_khac_nam_trong_closure_nen_return_vo_hai(self):
        """Hai cho con lai (`_do_reform`, `_moi_theo_dieu_phoi`) la ham long - `return` chi thoat
        ham do. Neo lai de ai do bung chung ra than run_account thi test do."""
        src = _src()
        for ten in ("def _do_reform(", "def _moi_theo_dieu_phoi("):
            i = src.find(ten)
            self.assertGreater(i, 0, ten)
            self.assertTrue(src[max(0, i - 9):i].endswith(" " * 8),
                            "%s khong con la ham long -> `return` ben trong se tat acc" % ten)


class TestKhongDeVIET_LUAT_CHET(unittest.TestCase):
    """`st["training_started"]` tung duoc DOC ma khong ai GHI -> luat watcher chet am tham,
    khong ai biet. Neo lai de khong tai dien."""

    def test_training_started_co_nguoi_ghi(self):
        src = _src()
        self.assertIn('st["training_started"] = True', src,
                      "khoa nay lai chi co nguoi doc, luat watcher se chet am tham")

    def test_moi_khoa_watcher_doc_deu_co_cho_ghi(self):
        src = _src()
        i = src.find("def _party_watcher(")
        than = src[i:src.find("\ndef ", i + 10)]
        doc = set(re.findall(r'st\.get\("([a-z_]+)"', than)) | \
            set(re.findall(r'st\["([a-z_]+)"\]', than))
        # `lock` la doi tuong dung truc tiep, khong phai co trang thai
        doc.discard("lock")
        chet = []
        for k in sorted(doc):
            if not re.search(r'(st\["%s"\]\s*=|"%s":)' % (k, k), src):
                chet.append(k)
        self.assertEqual(chet, [],
                         "watcher doc khoa %s ma KHONG CHO NAO ghi -> luat dung khoa do khong bao "
                         "gio chay" % chet)


class TestPhaDIGIOI_KHONG_DUOC_GOM(_Nen):
    """BUG THAT 06/09 00:52 (party 1 va 2): "leader dang trong DG tu nhien di ra ngoai".

        DIEU PHOI gen 3: pha=digioi ... viec=gom - party dang o 2 MAP khac nhau [21836, 49942]
        REFORM gen -> 1 (dieu phoi: ... -> gom ve cung map/kenh)

    49942 = map Di Gioi. DG la INSTANCE: acc nam rai trong/ngoai la CHUYEN BINH THUONG (dua
    dang vao, dua het gio bi day ra). Coi do la lech map roi gom = keo ca party VE THANH, tuc
    LOI LEADER RA KHOI DG giua chung. Luong DG da co cach gom rieng.
    """

    def test_lech_map_trong_pha_DG_thi_DONG_BO_chu_khong_gom(self):
        self._dat(a1=_C(DG, 1, 30), a2=_C(21836, 1, 30), a3=_C(21836, 1, 30))
        kh, _l, _ = self._quyet(lech_tu=time.time() - 9999)
        self.assertEqual(kh["pha"], "digioi")
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO, "gom trong DG = loi leader ra khoi DG")

    def test_lech_kenh_trong_pha_DG_cung_DONG_BO(self):
        """Bon dua o cung DG ma khac kenh thi khong thay nhau, khong lap party duoc - PHAI xu ly,
        khong duoc de nguyen (user chot 06/09: 'the bon no lam tro gi trong DG a')."""
        self._dat(a1=_C(DG, 1, 30, roster=0), a2=_C(DG, 5, 30, roster=0),
                  a3=_C(DG, 9, 30, roster=0))
        kh, ly_do, _ = self._quyet(lech_tu=time.time() - 9999)
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO)
        self.assertIn("kenh", ly_do)

    def test_DONG_BO_bam_resync_gen_KHONG_bam_reform_gen(self):
        """`reform_gen` = gom ve THANH; tu DG ra thanh la phai di bo ra cong -> loi ca party ra.
        `resync_gen` = giai tan + sync kenh + moi lai NGAY TAI CHO."""
        st = R._pstate(self.PARTY)
        g_reform, g_resync = st["reform_gen"], st["resync_gen"]
        R._dieu_phoi_thi_hanh(self.PARTY, st,
                              {"viec": R.VIEC_DONG_BO, "ly_do": "test"}, True)
        self.assertEqual(st["reform_gen"], g_reform, "bam reform_gen = keo ca party ra khoi DG")
        self.assertGreater(st["resync_gen"], g_resync, "khong bam gi -> party dung ngay trong DG")

    def test_chua_lech_du_lau_trong_DG_thi_de_yen(self):
        self._dat(a1=_C(DG, 1, 30), a2=_C(DG, 5, 30), a3=_C(DG, 9, 30))
        kh, _l, _ = self._quyet(lech_tu=None)
        self.assertEqual(kh["viec"], R.VIEC_LAM)

    def test_pha_TRAIN_thi_VAN_gom_binh_thuong(self):
        """Chi cam trong DG - sang train thi lech map van phai gom."""
        st = R._pstate(self.PARTY)
        with st["lock"]:
            st["dt_phase"] = "train"
        self._dat(a1=_C(12003, 1, 5), a2=_C(12001, 1, 5), a3=_C(12001, 1, 5))
        kh, _l, _ = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertEqual(kh["pha"], "train")
        self.assertEqual(kh["viec"], R.VIEC_GOM)

    def test_VAN_doi_pha_duoc_trong_DG(self):
        """Cam gom KHONG duoc lam mat viec chinh cua dieu phoi o pha nay: doi pha khi het gio."""
        self._dat(a1=_C(DG, 1, R.DIGIOI_LIMIT), a2=_C(12003, 1, R.DIGIOI_LIMIT),
                  a3=_C(12001, 1, R.DIGIOI_LIMIT))
        kh, ly_do, _ = self._quyet(lech_tu=time.time() - 9999)
        self.assertEqual(kh["pha"], "train")
        self.assertIn("het gio", ly_do)


class TestMotLuongChoCaBOT(unittest.TestCase):
    """BUG THAT 06/09 (party 53): party chay 16 phut MA KHONG CO AI DIEU PHOI.

        01:53:44 [party 53] DIEU PHOI gen 6: ...        <- dong cuoi cung
        01:54:54 -> 01:56:46 [vumhai] chua moi 4 member ... 'lech kenh live 1!=4' (64 lan)
        (khong mot nhip DIEU PHOI nao trong khi acc van chay binh thuong)

    Goc: dieu phoi nam trong `_party_watcher` - MOI PARTY MOT LUONG. Watcher TU THOAT khi party
    khong con acc chay, ma `start_party` chi dung watcher moi o nhanh PHIEN MOI (`_fresh`);
    nhanh `not _fresh` THOAT SOM truoc do. Watcher chet mot lan + user start lai luc con acc
    chay = party do vinh vien khong co dieu phoi.

    Nay: MOT luong cho ca bot, quet moi party, khong bao gio thoat, va tu hoi sinh.
    """

    def _src(self):
        import io as _io
        return _io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()

    def test_dieu_phoi_KHONG_con_nam_trong_party_watcher(self):
        s = self._src()
        i = s.find("def _party_watcher(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertNotIn("_dieu_phoi_quyet", than,
                         "dieu phoi van gan vao watcher/party -> watcher chet la mat dieu phoi")

    def test_vong_dieu_phoi_KHONG_BAO_GIO_thoat(self):
        s = self._src()
        i = s.find("def _dieu_phoi_loop(")
        self.assertGreater(i, 0, "khong co vong dieu phoi chung")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("while True:", than)
        for dong in than.splitlines():
            self.assertNotEqual(dong.strip(), "return", "vong dieu phoi co duong thoat")

    def test_loi_mot_party_khong_giet_ca_vong(self):
        s = self._src()
        i = s.find("def _dieu_phoi_loop(")
        than = s[i:s.find("\ndef ", i + 10)]
        j = than.find("for pidx in range(")
        self.assertGreater(j, 0)
        self.assertIn("except Exception", than[j:], "loi 1 party lam chet dieu phoi ca bot")

    def test_start_party_LUON_bao_dam_dieu_phoi(self):
        """Phai goi TRUOC nhanh `not _fresh` - do la nhanh thoat som da gay ra bug."""
        s = self._src()
        i = s.find("def start_party(")
        than = s[i:s.find("\ndef ", i + 10)]
        j, k = than.find("bao_dam_dieu_phoi()"), than.find("if not _fresh:")
        self.assertGreater(j, 0, "start_party khong bao dam dieu phoi")
        self.assertLess(j, k, "goi SAU nhanh thoat som -> van co party khong co dieu phoi")

    def test_start_account_le_cung_bao_dam(self):
        s = self._src()
        i = s.find("def start_account(")
        self.assertIn("bao_dam_dieu_phoi()", s[i:i + 1200])

    def test_goi_nhieu_lan_chi_co_MOT_luong(self):
        R.bao_dam_dieu_phoi()
        t1 = R._DIEU_PHOI_THREAD
        R.bao_dam_dieu_phoi()
        self.assertIs(R._DIEU_PHOI_THREAD, t1, "moi lan goi lai de mot luong -> ngap luong")
        self.assertTrue(t1.is_alive())
        self.assertTrue(t1.daemon, "khong daemon -> tat bot khong thoat duoc")


if __name__ == "__main__":
    unittest.main()


class TestMemberKhongChoLeaderLapDuong(unittest.TestCase):
    """Member KHONG CAN biet duong di - vao party la bi leader keo theo.

    Bang chung ngay trong code cu: sau khi cho leader lap route xong, member lam
        smart_route2 = plan.get("route") if is_leader else None
    tuc NEM LUON cai route vua cho. Thu duy nhat no can la `city`/`flag` (ca party phai gom cung
    mot thanh thi leader moi moi duoc - server chan invite khac map).

    Vay ma truoc 05/09 chi leader duoc chot, member cho VO HAN. Log party 10 (05/09 18:22-18:23):
    leader bi `ABORT di duong reform: reform_gen 1 -> 5` roi di lam dungeon + sync kenh, khong he
    cong bo cho gen moi -> 3 member spam "cho leader lap duong toi map 21812" khong dut.
    """

    def _than_reform(self):
        src = _src()
        i = src.find("def _chot_thanh_tap_ket(")
        self.assertGreater(i, 0, "chua tach viec chot thanh tap ket ra khoi dac quyen leader")
        return src, src[i:i + 5000]

    def test_member_KHONG_cho_vo_han(self):
        src, _ = self._than_reform()
        i = src.find("cho leader lap duong toi map")
        self.assertGreater(i, 0)
        khoi = src[max(0, i - 900):i]
        self.assertIn("ROUTE_PLAN_TIEP_QUAN_SEC", khoi,
                      "member van cho leader vo han -> party 10 lap lai")

    def test_member_tu_chot_duoc_thanh_tap_ket(self):
        src, _ = self._than_reform()
        self.assertIn("_chot_thanh_tap_ket(False)", src,
                      "member khong co duong tu chot -> van phu thuoc leader")

    def test_member_cong_bo_thi_KHONG_kem_route(self):
        """Duong di phu thuoc thanh DA MO cua tung acc - duong cua member leader di khong duoc."""
        _src_, than = self._than_reform()
        self.assertIn('"route": _sr if vi_la_leader else None', than)

    def test_van_chi_co_MOT_ban_chot_cho_ca_party(self):
        """Moi acc tu tinh -> party toe ra hai thanh, leader dung A member dung B, moi mai khong
        ai vao doi. Phai khoa theo gen: ai cong bo truoc thi thang."""
        _src_, than = self._than_reform()
        self.assertIn('_cu.get("gen") == _g0', than)
        self.assertIn('st["lock"]', than)

    def test_leader_khong_di_duong_dan_toi_thanh_KHAC(self):
        """Neu acc khac chot thanh X ma leader lai di route toi Y thi leader mot noi party mot noi."""
        _src_, than = self._than_reform()
        self.assertIn('int(_sr.get("city", 0)) == int(_cu.get("city", 0))', than)

    def test_nguong_tiep_quan_du_cho_leader_lam_truoc(self):
        self.assertGreaterEqual(R.ROUTE_PLAN_TIEP_QUAN_SEC, 10,
                                "qua ngan -> member cuop quyen chot cua leader lien tuc")
        self.assertLessEqual(R.ROUTE_PLAN_TIEP_QUAN_SEC, 60,
                             "qua dai -> ca party dung cho nhu party 10")
