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
from tests.party_controller_helpers import quyet_party

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
        return quyet_party(R, self.PARTY, st, R._acc_song(self.PARTY), lech_tu)


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


class TestQuyetDinhDuocApDung(_Nen):
    """Decision effects are applied by the party engine adapter."""

    def test_doi_pha_duoc_ghi_vao_state_party(self):
        self._dat(a1=_C(DG, 1, R.DIGIOI_LIMIT), a2=_C(DG, 1, R.DIGIOI_LIMIT),
                  a3=_C(DG, 1, R.DIGIOI_LIMIT))
        kh, _ly, _lech = self._quyet()
        self.assertEqual(kh["pha"], "train")
        self.assertEqual(R._pstate(self.PARTY)["dt_phase"], "train")

    def test_lenh_gom_khong_bam_reform_gen_cho_account_script_cu(self):
        st = R._pstate(self.PARTY)
        st["dt_phase"] = "train"
        self._dat(a1=_C(12003, 1, 5), a2=_C(12001, 1, 5), a3=_C(12001, 1, 5))
        before = st["reform_gen"]
        kh, _ly, _lech = self._quyet(lech_tu=time.time() - R.KE_HOACH_LECH_MAP_SEC - 1)
        self.assertEqual(kh["viec"], R.VIEC_GOM)
        self.assertEqual(st["reform_gen"], before)



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


class TestKhongConVongChoPartyTran(unittest.TestCase):
    """The controller tick decides again after every completed worker action."""

    def test_nhip_engine_khong_cho_roster_trong_vong_lap(self):
        import ast
        from bot import party_engine as PE
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PartyEngine")
        tick = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "nhip")
        self.assertFalse(any(isinstance(n, ast.While) for n in ast.walk(tick)))
        self.assertTrue(hasattr(PE.PartyEngine, "nhip"))



class TestLenhGOMKhongTatAcc(unittest.TestCase):
    """A regroup action is a worker task, not an account exit."""

    def test_gom_giao_viec_ve_thanh_cho_acc_lech(self):
        from bot import party_engine as PE
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12001, kenh=1, so_member=1),
                PE.AnhAcc("member", map_id=21001, kenh=1, so_member=1)]
        anh = PE.AnhParty(0, accs, can_bao_nhieu=1, thanh_dich=12001,
                          dp_viec=PE.DP_GOM)
        jobs = PE.quyet_dinh(anh)
        self.assertEqual(jobs["member"], PE.VIEC_VE_THANH)
        self.assertNotEqual(jobs.get("leader"), PE.VIEC_THOAT)



class TestKhongDeLuatChoChet(unittest.TestCase):
    """Party decisions use client snapshots without a waiting-report watchdog."""

    def test_khong_con_party_watcher(self):
        self.assertFalse("def _party_watcher(" in _src())



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

    def test_DONG_BO_khong_bam_co_cho_account_script_cu(self):
        """The engine owns synchronization; old account-script flags must stay untouched."""
        st = R._pstate(self.PARTY)
        g_reform, g_resync = st["reform_gen"], st["resync_gen"]
        self._dat(a1=_C(DG, 1, 30, roster=0), a2=_C(DG, 5, 30, roster=0),
                  a3=_C(DG, 9, 30, roster=0))
        kh, _ly, _ = self._quyet(lech_tu=time.time() - 9999)
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO)
        self.assertEqual(st["reform_gen"], g_reform)
        self.assertEqual(st["resync_gen"], g_resync)

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


class TestMotLuongChoMoiParty(unittest.TestCase):
    """Runner registers the party engine after login and starts no global coordinator."""

    def test_khong_con_vong_dieu_phoi_chung(self):
        src = _src()
        self.assertFalse("def _dieu_phoi_loop(" in src)
        self.assertFalse("bao_dam_dieu_phoi(" in src)

    def test_runner_dang_ky_engine_sau_login(self):
        src = _src()
        self.assertIn("_dang_ky_engine_moi(username, c, pidx", src)
        self.assertIn("doc_party=lambda _p=pidx: _engine_doc_party(_p)", src)
        self.assertIn("ap_dung_party=lambda _anh, _v, _ly, _hu", src)



if __name__ == "__main__":
    unittest.main()


class TestMemberKhongTuLapDuong(unittest.TestCase):
    """When a full party travels, one leader pulls and members wait for new ticks."""

    def test_chi_nguoi_keo_nhan_lenh_di_map(self):
        from bot import party_engine as PE
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12001, kenh=1, so_member=1),
                PE.AnhAcc("member", map_id=12001, kenh=1, so_member=1)]
        anh = PE.AnhParty(0, accs, can_bao_nhieu=1, map_dich=21001,
                          dp_viec=PE.DP_DI_TRAIN, nguoi_keo="leader")
        jobs = PE.quyet_dinh(anh)
        self.assertEqual(jobs["leader"], PE.VIEC_VE_MAP)
        self.assertEqual(jobs["member"], PE.VIEC_NGHI)

    def test_member_khong_tu_chot_thanh_khi_cho(self):
        from bot import party_engine as PE
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12001, kenh=1, so_member=1),
                PE.AnhAcc("member", map_id=12001, kenh=1, so_member=1)]
        anh = PE.AnhParty(0, accs, can_bao_nhieu=1, map_dich=21001,
                          dp_viec=PE.DP_DI_TRAIN, nguoi_keo="leader")
        for _ in range(3):
            self.assertEqual(PE.quyet_dinh(anh)["member"], PE.VIEC_NGHI)
