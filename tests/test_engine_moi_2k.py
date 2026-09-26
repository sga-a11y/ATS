"""ENGINE MOI lam event 2K (Nhi Kieu, `floor_crawl`).

Ngay 20/09 KHONG PARTY NAO vao duoc Nhi Kieu. Log thuc, ca loat acc cua moi party cung giay
14:15:33:
    [tkbon]   DIEU PHOI chot tang gom Thong Dao (12922), minh dang o 12001 -> di bo xuong
    [tkbon]   gom doi: di bo 12001 -> 12922 (map event khong teleport duoc)
    [dieutam] scene route: khong tim thay duong 12061 -> 12922
    [dieutam] gom doi: KHONG di bo duoc 12061 -> 12922
Khong co duong BO tu thanh vao map event, ma trong thap thi khong teleport duoc -> engine cu ra
lenh gi cung sai. User: "event 2k thi tat ca deu chay engine moi, engine cu loi the thi chay lam
deo gi".

Hai cai bay da tra gia de biet, giu bang test o day:
  * `go_to_event` co `leave_party()` ngay dong dau -> goi no de "gom" la DAP TAN PARTY vua lap
    (user 20/09: "sao party xong leader bi vang the").
  * Trong thap KHONG teleport duoc -> `ve_thanh`/`resync` la lenh RONG. Engine cu quay 201.495
    vong vi dieu nay (party 5, 06/09).
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import floor_crawl as FC
from bot import party_engine as PE

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


EV_2K = {"label": "Nhi Kieu", "staging_map": 12921, "dest_map": 12922,
         "party_battle": {"kind": "floor_crawl", "top_map": 12934}}


def _anh(accs, **kw):
    kw.setdefault("can_bao_nhieu", len(accs) - 1)
    return PE.AnhParty(0, accs, pha=PE.PHA_EVENT, **kw)


def _acc(u, map_id, leader=False, trong=True):
    return PE.AnhAcc(u, la_leader=leader, song=True, map_id=map_id, kenh=1,
                     so_member=len(("a", "b")), trong_event=trong)


class TestMoiPartyDeuDungEngineMoi(unittest.TestCase):
    """2K and 40NPC use the same per-party controller at every party index."""

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        self._evs = getattr(R.config, "EVENTS", {})
        R.config.EVENTS = {"2k": EV_2K, "npc40": {"party_battle": {"kind": "npc_repeat"}}}

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.EVENTS = self._evs

    def test_party_so_NHO_van_dung_engine_moi(self):
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        self.assertTrue(R.dung_engine_moi(0), "party 1 mode 2K phai dung engine moi")

    def test_khong_con_cong_tac_quay_ve_engine_cu(self):
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        with mock.patch.object(R.config, "PARTY_ENGINE_MOI_TU", 0, create=True):
            self.assertTrue(R.dung_engine_moi(0))

    def test_event_40npc_cung_dung_engine(self):
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "npc40"}}
        self.assertTrue(R.dung_engine_moi(0))

    def test_floor_crawl_nam_trong_danh_sach_kind(self):
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        self.assertTrue(R.dung_engine_moi(0))
        self.assertTrue(hasattr(PE, "VIEC_FC_GOM"))


class TestMapEventLaCA_DAI_TANG(unittest.TestCase):
    """Leo len tang 2 la DOI MAP. Chi ke `dest_map` thi engine tuong acc "ra khoi event" ngay sau
    tran dau -> giao `vao_event` -> `go_to_event` -> `leave_party()` + keo ca doi ve 12921 = mat
    sach tang da leo."""

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        self._evs = getattr(R.config, "EVENTS", {})
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        R.config.EVENTS = {"2k": EV_2K}

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.EVENTS = self._evs

    def test_phu_het_cac_tang(self):
        maps = R._map_event_engine_moi(0)
        for m in (12922, 12928, 12934):
            self.assertIn(m, maps, "tang %s phai duoc tinh la DANG TRONG event" % m)

    def test_KHONG_ke_san_cho_12921(self):
        """Acc con o san cho phai duoc `go_to_event` di tiep vao 12922 - luc do party chua lap
        nen `leave_party()` trong do vo hai."""
        self.assertNotIn(12921, R._map_event_engine_moi(0))


class TestLechTangThiDIBO(unittest.TestCase):
    def test_lech_tang_thi_giao_FC_GOM(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", 12925, leader=True), _acc("a2", 12924)],
                                 tang_gom=12924))
        self.assertEqual(ket["a1"], PE.VIEC_FC_GOM, "dua o tang cao phai DI BO xuong tang gom")

    def test_dua_DA_O_tang_gom_thi_khong_bi_dieu_di(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", 12925, leader=True), _acc("a2", 12924)],
                                 tang_gom=12924))
        self.assertNotEqual(ket.get("a2"), PE.VIEC_FC_GOM)

    def test_CUNG_TANG_thi_KHONG_gom_nua(self):
        ket = PE.quyet_dinh(_anh([_acc("a1", 12924, leader=True), _acc("a2", 12924)],
                                 tang_gom=12924))
        self.assertNotIn(PE.VIEC_FC_GOM, ket.values())

    def test_trong_thap_thi_KHONG_ra_lenh_TELEPORT(self):
        """`ve_thanh`/`resync`/`ve_map` deu di bang teleport - trong map event khong teleport
        duoc nen do la lenh RONG. Engine cu quay 201.495 vong vi dieu nay (party 5, 06/09)."""
        anh = _anh([_acc("a1", 12925, leader=True), _acc("a2", 12924)],
                   tang_gom=12924, dp_viec=R.VIEC_GOM, reform_moi=True, thanh_dich=12001)
        for viec in PE.quyet_dinh(anh).values():
            self.assertNotIn(viec, PE.VIEC_DI_CHUYEN,
                             "trong thap ma van ra lenh di chuyen bang teleport")


class TestEngineGiaoTungBuocChoLeader(unittest.TestCase):
    """Trong thap chi LEADER di chuyen, member dinh party tu theo -> engine chi giao viec cho
    leader, member `nghi`."""

    def _ket(self, buoc, **kw):
        accs = [_acc("a1", 12924, leader=True), _acc("a2", 12924)]
        return PE.quyet_dinh(_anh(accs, tang_gom=12924, fc_buoc=buoc, **kw))

    def test_buoc_danh_thi_LEADER_danh_member_nghi(self):
        ket = self._ket(PE.FC_DANH)
        self.assertEqual(ket["a1"], PE.VIEC_2K_DANH)
        self.assertEqual(ket["a2"], PE.VIEC_NGHI)

    def test_buoc_len_tang_thi_LEADER_qua_cong(self):
        ket = self._ket(PE.FC_LEN_TANG)
        self.assertEqual(ket["a1"], PE.VIEC_2K_LEN_TANG)
        self.assertEqual(ket["a2"], PE.VIEC_NGHI)

    def test_THIEU_DOI_thi_KHONG_duoc_qua_cong(self):
        """L0: qua cong mot minh = member bi bo lai tang duoi, leader leo tiep va danh khong noi
        (party 5 06/09: leader qua cong 16:34:53, tang 6 "chi danh duoc 0/3 tran").

        Ban cu bao dam viec nay bang callback `du_party()` NAM CHO 60 giay trong thread leo thap.
        Engine moi doc ANH CHUP - thieu nguoi thi buoc `len_tang` khong bao gio duoc giao.
        """
        accs = [_acc("a1", 12924, leader=True), _acc("a2", 12924)]
        anh = _anh(accs, tang_gom=12924, fc_buoc=PE.FC_LEN_TANG, can_bao_nhieu=4)
        self.assertNotIn(PE.VIEC_2K_LEN_TANG, PE.quyet_dinh(anh).values())

    def test_khong_phai_2K_thi_van_di_duong_danh_event_cu(self):
        """40NPC khong co `fc_buoc` -> phai giu nguyen `danh_event` nhu truoc."""
        ket = self._ket(None)
        self.assertEqual(ket["a1"], PE.VIEC_DANH_EVENT)


class TestKhongDungGoToEventDeGom(unittest.TestCase):
    """`go_to_event` co `leave_party()` ngay dong dau. Goi no o duong GOM = dap tan party vua lap
    (user 20/09: "sao party xong leader bi vang the")."""

    def test_thi_hanh_FC_GOM_di_bang_regroup_chu_khong_phai_go_to_event(self):
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("if viec == VIEC_FC_GOM:")
        self.assertGreater(i, 0)
        khoi = src[i:i + 700]
        self.assertIn("fc_gom(client)", khoi)
        self.assertNotIn("vao_event(", khoi)

    def test_callback_fc_gom_goi_regroup_to_event_start(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _fc_gom_engine_moi(")
        self.assertGreater(i, 0)
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("regroup_to_event_start(", than)
        self.assertNotIn("go_to_event(", than)


class TestXongEventLa2K_ChuKhongPhaiKhungGio40NPC(unittest.TestCase):
    """2K (`nhi_kieu`) de `lich: null` - KHONG co khung gio. Hoi `in_40npc_window()` thi ngoai
    khung 40NPC la no tra "event xong" NGAY -> ca party `claim_40npc_reward` = ve Trac Quan
    (Quang Truong) roi thoat game du 2K chua danh phut nao.
    User 20/09: "lam lon gi ma bon no chay ve quang truong roi out het".
    """

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        self._evs = getattr(R.config, "EVENTS", {})
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        R.config.EVENTS = {"2k": EV_2K}
        R._party_state.pop(0, None)

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.EVENTS = self._evs
        R._party_state.pop(0, None)

    def test_chua_chot_xong_thi_CHUA_xong(self):
        st = R._pstate(0)
        st["go_claim"].clear()
        st["event_battle_done"].clear()
        st["event_exit_now"].clear()
        self.assertFalse(R._event_xong_engine_moi(0),
                         "2K chua danh gi ma da bao xong -> ca party ve Quang Truong + out")

    def test_dieu_phoi_bat_co_thi_MOI_xong(self):
        st = R._pstate(0)
        st["event_exit_now"].set()
        self.assertTrue(R._event_xong_engine_moi(0))

    def test_KHONG_hoi_khung_gio_40NPC_cho_2K(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _event_xong_engine_moi(")
        than = src[i:src.find("\ndef ", i + 10)]
        ma = than[than.find('"""', than.find('"""') + 3):]      # bo docstring
        # nhanh floor_crawl phai chot TRUOC khi cham toi `in_40npc_window`
        self.assertLess(ma.find("floor_crawl"), ma.find("in_40npc_window"))

    def test_2K_xong_thi_RA_KHOI_THAP_chu_khong_doi_thuong_40NPC(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _doi_thuong_engine_moi(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertLess(than.find("floor_crawl"), than.find("claim_40npc_reward"),
                        "2K phai duoc chan TRUOC khi roi vao duong doi thuong cua 40NPC")
        self.assertIn("exit_event(ev)", than)


class TestTinhBuocLeoThap(unittest.TestCase):
    """`tinh_buoc` la ham THUAN - chuoi buoc cua leader, engine goi moi nhip de quyet."""

    EV = {"dest_map": 12922, "party_battle": {
        "kind": "floor_crawl", "top_map": 12934,
        "battle_idx": {"12924": [2, 3, 4]},
        "battle_points": {"default": [[10, 10], [20, 20]]}}}

    def setUp(self):
        self._up = FC._up_gate
        FC._up_gate = lambda scene: (12925, 2, (80, 360))   # cong len o idx 2

    def tearDown(self):
        FC._up_gate = self._up

    def test_con_diem_thi_DANH(self):
        buoc, idx, point, _ = FC.tinh_buoc(self.EV, 12924, 0)
        self.assertEqual(buoc, "danh")
        self.assertEqual(point, (10, 10))
        self.assertNotEqual(idx, 2, "idx cua CONG khong duoc dung de danh quai")

    def test_idx_cua_cong_bi_LOAI(self):
        """Bam trung idx cong = qua cong som, bo lai member va bo do tang."""
        idxs = [FC.tinh_buoc(self.EV, 12924, k)[1] for k in (0, 1)]
        self.assertNotIn(2, idxs)
        self.assertEqual(idxs, [3, 4])

    def test_danh_het_diem_thi_LEN_TANG(self):
        buoc, nxt, door, center = FC.tinh_buoc(self.EV, 12924, 2)
        self.assertEqual(buoc, "len_tang")
        self.assertEqual((nxt, door, center), (12925, 2, (80, 360)))

    def test_tang_cao_nhat_la_XONG(self):
        self.assertEqual(FC.tinh_buoc(self.EV, 12934, 0)[0], "xong")

    def test_khong_co_cong_len_la_HET_DUONG(self):
        FC._up_gate = lambda scene: None
        self.assertEqual(FC.tinh_buoc(self.EV, 12924, 99)[0], "het_duong")

    def test_LUON_tra_4_phan_tu(self):
        """Nguoi goi giai nen MOT lan; tra 3 phan tu o nhanh nay, 4 o nhanh kia thi ho phai goi
        lai ham de lay phan du - vua thua vua de lech."""
        for k in (0, 2):
            self.assertEqual(len(FC.tinh_buoc(self.EV, 12924, k)), 4)


class TestCuaSoDungeonPhaiMoTRUOC_KHI_BAM_CONG(unittest.TestCase):
    """`run_floor_crawl` dat `_team_dungeon_until` o DAU MOI TANG (truoc ca vong danh) nen luc toi
    cong no luon con hieu luc. Ban tach buoc tung dat no trong `danh_mot_diem` -> tang nao khong
    ra tran nao (khu vao 12922) thi cua so CHUA BAO GIO duoc mo va cong khong chiu mo:
        16:06:02 [thba] _enter_gate idx=2 @(80,360): map khong doi (van 12922)
    User 20/09: "p4 p5 p7 thi du nguoi ma deo them danh" - 200 lan thu lien tiep.
    """

    def test_qua_cong_gia_han_cua_so_dungeon(self):
        with io.open(os.path.join(ROOT, "bot", "floor_crawl.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def qua_cong_len_tang(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("_team_dungeon_until", than)
        self.assertLess(than.find("_team_dungeon_until"), than.find("_enter_gate("),
                        "phai gia han TRUOC khi bam cong")


class TestKetOCongThiNGHI_ChuKhongBamLai_MoiGiay(unittest.TestCase):
    """Engine cu thoat han vong leo khi ket o cong (dieu phoi gom + moi lai roi resume) - tuc co
    khoang lang. Engine moi nhip 1 giay khong co cho nghi thi bam cong lien tuc:
        16:07:44 [party 7] ENGINE: '2k_len_tang' giao lai 200 lan lien tiep cho taot006
    """

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        self._evs = getattr(R.config, "EVENTS", {})
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        R.config.EVENTS = {"2k": EV_2K}
        R._party_state.pop(0, None)

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.EVENTS = self._evs
        R._party_state.pop(0, None)

    def test_co_hang_so_nghi(self):
        self.assertGreaterEqual(R.FC_KET_CONG_NGHI_SEC, 5.0,
                                "nghi qua ngan = van bam cong lien tuc -> ma 13")

    def test_dang_nghi_thi_KHONG_giao_len_tang(self):
        """`_fc_buoc_engine_moi` tra None trong luc nghi -> party roi xuong nhanh dieu phoi."""
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _fc_buoc_engine_moi(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("2k_cong_ket_den", than)
        self.assertLess(than.find("2k_cong_ket_den"), than.find('buoc in ("xong"'),
                        "cua nghi phai chan TRUOC khi tra buoc len_tang")

    def test_ket_o_cong_thi_DAT_moc_nghi(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("KET o cong %s -> de dieu phoi gom")
        self.assertGreater(i, 0)
        self.assertIn("2k_cong_ket_den", src[i:i + 900])


class TestKhongMoLaiVongBattleMoiNhip(unittest.TestCase):
    """`start_floor_crawl`/`start_npc40_loop` DE THREAD RIENG roi tra ve NGAY -> engine moi (nhip
    1 giay) thay "viec chay xong ngay" va giao lai lien tuc, moi lan lai gui goi gia han quest-mode
    cho CA PARTY -> server ngat leader.

    Ca that 20/09 party 7 (user: "party xong roi, deo thay di danh, 1 luc sau leader dis"):
        15:29:45 -> 15:30:15  ENGINE: taot006 -> danh_event   <- 30 lan lien tiep
        15:30:16 [taot006] RECONNECT: server rot -> login lai sau 5s (lan 1)
    """

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        self._evs = getattr(R.config, "EVENTS", {})
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        R.config.EVENTS = {"2k": EV_2K}
        R._party_state.pop(0, None)

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.EVENTS = self._evs
        R._party_state.pop(0, None)

    def test_vong_2K_dang_chay_thi_KHONG_goi_lai(self):
        class _C:
            _label = "leader"
            _username = "u1"
            _floor_crawl_started = True

            def start_floor_crawl(self, *a, **k):
                raise AssertionError("da chay roi ma con goi lai -> spam goi, server ngat leader")

        self.assertTrue(R._danh_event_engine_moi(_C(), 0))

    def test_vong_40NPC_dang_chay_thi_KHONG_goi_lai(self):
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "npc40"}}
        R.config.EVENTS = {"npc40": {"party_battle": {"kind": "npc_repeat", "point": [1, 2]}}}

        class _C:
            _label = "leader"
            _username = "u1"
            _npc40_started = True

            def start_npc40_loop(self, *a, **k):
                raise AssertionError("da chay roi ma con goi lai")

        self.assertTrue(R._danh_event_engine_moi(_C(), 0))

    def test_cua_chan_dat_TRUOC_moi_viec_gui_goi(self):
        """Phai chan TRUOC `_set_party_quest_mode` - chinh no la thu gui goi cho ca party."""
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _danh_event_engine_moi(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertLess(than.find("_floor_crawl_started"), than.find("_set_party_quest_mode"))


class TestEngineMoiKhongDeThreadRiengCamLai(unittest.TestCase):
    """User 20/09: "vong leo thap thi co cai lon gi dau, di theo party chi leader di chuyen, bon
    kia tu di theo roi, co gi ma 1 thread ko dieu khien het dc".

    Dung vay: ca vong leo thap chi la chuoi buoc CUA LEADER. Engine moi giao tung buoc
    (`VIEC_2K_DANH` / `VIEC_2K_LEN_TANG`), khong bam nut `start_floor_crawl` roi tha cho thread
    `floorcrawl-*` cam lai - thread do khong doc lenh cua ai, va chinh no de ra ca lo benh:
    engine giao lai moi giay -> spam goi -> leader dis (party 7, 15:30:16).
    """

    def test_engine_moi_KHONG_goi_start_floor_crawl(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _danh_event_engine_moi(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertNotIn("chay_leo_thap_2k(", than,
                         "engine moi ma con khoi dong thread leo thap = dung lai cai da bo")

    def test_van_giu_duong_cu_cho_ENGINE_CU(self):
        """Engine cu (nguong = 0) van phai chay 2K duoc nhu truoc - khong duoc xoa duong cua no."""
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("def chay_leo_thap_2k(", src)
        self.assertEqual(src.count("c.start_floor_crawl("), 1,
                         "co hai ban vong leo thap = se lech nhau, chi la som hay muon")

    def test_moi_buoc_deu_goi_lai_ham_cua_floor_crawl(self):
        """Buoc nho goi lai `floor_crawl`, khong chep logic danh/qua cong sang file khac."""
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _fc_lam_buoc_engine_moi(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("floor_crawl.danh_mot_diem(", than)
        self.assertIn("floor_crawl.qua_cong_len_tang(", than)


if __name__ == "__main__":
    unittest.main()


class TestKhongMoPhongPB_GiuaTran(unittest.TestCase):
    """Leader ket trong tran thi khong vao phong PB duoc, trong khi member da dong y va dang cho
    -> leader HUY vi "roster phong chi 0/4" roi mo lai, lap vo tan.

    Ca that 21/09 party 21 (user: "sao 4 dua trong PB, con 1 dua o ngoai"):
        01:03:44 [dieusau] (LEADER) === PHO BAN TO DOI LV20: tao + moi 4 member ===
        01:03:45 [dieubay]  Nhan moi PHO BAN tu 'dieusau' -> da DONG Y
        01:03:47 [dieusau] BATTLE SEND g=2067 t=2 ...        <- chinh leader dang danh
        01:04:04 [dieusau] (LEADER) roster phong pho ban chi 0/4 member sau 8.2s -> HUY
    `pb_doi` giao lai 3760 lan lien tiep.
    """

    def _anh_pb(self, leader_dang_danh):
        accs = [PE.AnhAcc("a1", la_leader=True, song=True, map_id=12001, kenh=1,
                          dang_danh=leader_dang_danh),
                PE.AnhAcc("a2", song=True, map_id=12001, kenh=1)]
        return PE.AnhParty(0, accs, can_bao_nhieu=1, pha=PE.PHA_TRAIN, pb_doi_level=20)

    def test_leader_dang_danh_thi_KHONG_mo_phong(self):
        ket = PE.quyet_dinh(self._anh_pb(True))
        self.assertNotEqual(ket.get("a1"), PE.VIEC_PB_DOI,
                            "mo phong giua tran = mat luot + relogin ca party")

    def test_het_tran_thi_mo_phong_binh_thuong(self):
        ket = PE.quyet_dinh(self._anh_pb(False))
        self.assertEqual(ket.get("a1"), PE.VIEC_PB_DOI)

    def test_member_van_duoc_bat_co_san_sang(self):
        """`pb_doi_theo` chi bat co, khong gui gi -> khong can chan."""
        self.assertEqual(PE.quyet_dinh(self._anh_pb(False)).get("a2"), PE.VIEC_PB_DOI_THEO)
