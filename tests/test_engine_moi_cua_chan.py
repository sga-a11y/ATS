"""ENGINE MOI: BON CUA CHAN. Thieu mot cai la hai engine danh nhau tren cung mot party.

Ca party chay song song hai co che chi an toan khi RANH GIOI tuyet doi: party nao thuoc engine
moi thi engine cu KHONG duoc dung vao, va nguoc lai. Hai nguon cung ra lenh cho mot party chinh
la cai benh dang chua (party 11, 15/09: leader nghe mot dang, member ket o cho khong nghe duoc gi).

Thiet ke: documents/ENGINE_PARTY_MOI.md muc 4.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestChonEngine(unittest.TestCase):
    """MOT cho duy nhat tra loi 'party nay dung engine nao' - rai rac ra la lech."""

    def setUp(self):
        self._cu = getattr(R.config, "PARTY_ENGINE_MOI_TU", None)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        if self._cu is None:
            if hasattr(R.config, "PARTY_ENGINE_MOI_TU"):
                delattr(R.config, "PARTY_ENGINE_MOI_TU")
        else:
            R.config.PARTY_ENGINE_MOI_TU = self._cu

    def test_nguong_hien_tai_dung_pham_vi_user_chot(self):
        """User chot 15/09: "party >40 la theo co che moi" -> 41.

        So nay la CONG TAC SONG: doi no la doi engine cua 14 party (62 acc) that. Neo lai de khong
        ai vo tinh day no xuong party 1-40 (hoac len, lam mat hieu luc ca dot chay thu)."""
        self.assertIn(R.PARTY_ENGINE_MOI_TU, (0, 41, 45, 49, 53),
                      "nguong la (0=tat, 53=thu 2 party, 49/45=ha dan, 41=du pham vi user chot)")

    def test_so_0_la_tat_han(self):
        R.config.PARTY_ENGINE_MOI_TU = 0
        self.assertFalse(any(R.dung_engine_moi(i) for i in range(60)))

    def test_nguong_41_dung_pham_vi_user_chot(self):
        """User 15/09: "party >40 la theo co che moi"."""
        R.config.PARTY_ENGINE_MOI_TU = 41
        R.config.PARTY_CONFIG = {i: {"mode": "digioi_train"} for i in range(60)}
        self.assertFalse(R.dung_engine_moi(39), "party 40 phai giu engine cu")
        self.assertTrue(R.dung_engine_moi(40), "party 41 phai la engine moi")
        self.assertTrue(R.dung_engine_moi(53))

    def test_chay_thu_2_party_truoc(self):
        """Ha dan tu 53 -> 41 (muc 7): bat ca 14 party ngay dem dau la hong mot dem mat 62 acc."""
        R.config.PARTY_ENGINE_MOI_TU = 53
        R.config.PARTY_CONFIG = {i: {"mode": "digioi_train"} for i in range(60)}
        self.assertFalse(R.dung_engine_moi(51), "party 52 con engine cu")
        self.assertTrue(R.dung_engine_moi(52))
        self.assertEqual(sum(1 for i in range(54) if R.dung_engine_moi(i)), 2)

    def test_config_hong_thi_coi_nhu_TAT(self):
        R.config.PARTY_ENGINE_MOI_TU = "bay bay"
        self.assertFalse(R.dung_engine_moi(50), "doc config loi ma van bat engine moi = nguy hiem")


class TestCuaChan1_DieuPhoiCu(unittest.TestCase):
    """Dieu phoi cu KHONG duoc ra lenh cho party engine moi."""

    def test_vong_dieu_phoi_bo_qua_party_engine_moi(self):
        s = _src("run_party_digioi.py")
        i = s.find("def _dieu_phoi_loop()")
        self.assertGreater(i, 0)
        j = s.find("song = _acc_song(pidx)", i)
        self.assertGreater(j, i)
        self.assertIn("dung_engine_moi(pidx)", s[i:j],
                      "dieu phoi cu van quet party engine moi -> hai nguon cung ra lenh")

    def test_chan_TRUOC_khi_doc_trang_thai(self):
        """Chan sau khi da `_dieu_phoi_quyet` thi lenh da ghi vao st roi - chan bang thua."""
        s = _src("run_party_digioi.py")
        i = s.find("def _dieu_phoi_loop()")
        chan = s.find("dung_engine_moi(pidx)", i)
        quyet = s.find("_dieu_phoi_quyet(", i)
        self.assertGreater(chan, 0)
        self.assertLess(chan, quyet, "chan phai nam TRUOC buoc ra lenh")


class TestCuaChan2_KhongChayKichBanCu(unittest.TestCase):
    """Acc thuoc party engine moi KHONG duoc chay kich ban `run_account` - hai luong dieu khien
    mot client la hong chac."""

    def setUp(self):
        self.src = _src("run_party_digioi.py")

    def test_co_diem_re_trong_run_account(self):
        i = self.src.find("if dung_engine_moi(pidx):")
        self.assertGreater(i, 0, "khong co cua re -> engine moi khong bao gio chay")
        self.assertIn("_dang_ky_engine_moi(", self.src[i:i + 400])
        self.assertIn("return", self.src[i:i + 400], "phai RETURN, khong chay tiep kich ban cu")

    def test_re_SAU_khi_login_xong(self):
        """Re truoc khi vao world = engine moi nhan client chua san sang; re qua muon = da chay
        mat mot phan kich ban cu."""
        i = self.src.find("account_clients[username] = c     # GUI doc trang thai")
        j = self.src.find("if dung_engine_moi(pidx):")
        self.assertGreater(i, 0)
        self.assertGreater(j, i, "cua re phai nam SAU khi da vao world")
        self.assertIn("vao world.", self.src[i:j])

    def test_KHONG_chep_lai_doan_login(self):
        """Doan login co qua nhieu chi tiet song con (chan toc do ma 90, error_code=1, co chet-ve-
        thanh, van tieu per-acc). Chep sang engine moi la chac chan lech dan."""
        i = self.src.find("def _dang_ky_engine_moi(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        for _cam in ("GameClient(", "c.connect()", "login(username"):
            self.assertNotIn(_cam, than, "engine moi tu login lai -> se lech voi engine cu: %s" % _cam)


class TestCuaChan3_WatcherCu(unittest.TestCase):
    """Watcher cu khong chi DOC - no ep dong bo (bump reform_gen -> ResyncSignal -> relogin)."""

    def test_watcher_thoat_ngay_voi_party_engine_moi(self):
        s = _src("run_party_digioi.py")
        i = s.find("def _party_watcher(pidx)")
        self.assertGreater(i, 0)
        khoi = s[i:i + 900]
        self.assertIn("dung_engine_moi(pidx)", khoi, "watcher cu van ep dong bo party engine moi")
        self.assertIn("return", khoi)

    def test_chan_TRUOC_vong_quan_sat(self):
        s = _src("run_party_digioi.py")
        i = s.find("def _party_watcher(pidx)")
        chan = s.find("dung_engine_moi(pidx)", i)
        vong = s.find("while True:", i)
        self.assertLess(chan, vong, "chan phai nam truoc vong quan sat")


class TestCuaChan4_GuiVanThay(unittest.TestCase):
    """User phai thay 14 party do tren GUI y nhu cac party khac."""

    def test_engine_bao_hoat_dong_cho_gui(self):
        s = _src("bot", "party_engine.py")
        self.assertIn("self._bao_gui", s)
        i = s.find("def nhip(self)")
        self.assertGreater(i, 0)
        self.assertIn("_bao_gui", s[i:i + 2500], "nhip khong bao GUI -> user mu ca party")

    def test_noi_vao_set_account_activity(self):
        s = _src("run_party_digioi.py")
        i = s.find("def _dang_ky_engine_moi(")
        self.assertGreater(i, 0)
        # Soi CA THAN HAM, khong cat theo so ky tu: moi lan them mot khoi chu thich la cua so
        # co dinh lai day mat phan can kiem (test do 16/09 chi vi the).
        than = s[i:s.find(chr(10) + "def ", i + 10)]
        self.assertIn("set_account_activity", than, "khong noi vao duong GUI co san")

    def test_bao_gui_loi_KHONG_lam_hong_nhip(self):
        """GUI hong thi mac GUI - khong duoc lam party dung im (L0)."""
        s = _src("bot", "party_engine.py")
        i = s.find("_bao_gui(")
        self.assertGreater(i, 0)
        self.assertIn("except", s[max(0, i - 200):i + 300])


class TestPhaDocTuStateCu(unittest.TestCase):
    """PHA doc `dt_phase` cua state party - nguon engine cu van dung. Nho mot con so rieng la tao
    ra NGUON SU THAT THU HAI ve cung mot thu, dung benh da giet party 11."""

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {5: {"mode": "digioi_train"}, 6: {"mode": "digioi"},
                                 7: {"mode": "train"}}

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc

    def test_digioi_train_theo_dt_phase(self):
        from bot import party_engine as E
        self.assertEqual(R._pha_engine_moi(5, {"dt_phase": "digioi"}), E.PHA_DG)
        self.assertEqual(R._pha_engine_moi(5, {"dt_phase": "train"}), E.PHA_TRAIN)

    def test_mode_digioi_thuan_thi_LUON_pha_DG(self):
        from bot import party_engine as E
        self.assertEqual(R._pha_engine_moi(6, {}), E.PHA_DG)

    def test_mode_thuong_thi_LUON_pha_TRAIN(self):
        from bot import party_engine as E
        self.assertEqual(R._pha_engine_moi(7, {"dt_phase": "digioi"}), E.PHA_TRAIN)

    def test_chua_co_dt_phase_thi_mac_dinh_VAO_DG_TRUOC(self):
        """Mac dinh phai la DG: party moi khoi dong ma nhay thang sang train la MAT LUOT DI GIOI
        ca ngay (120 phut EXP)."""
        from bot import party_engine as E
        self.assertEqual(R._pha_engine_moi(5, {}), E.PHA_DG)


class TestKhongBoSOT_viec_engine_cu_lam(unittest.TestCase):
    """Engine moi khong chay `run_account` va bi cam dung `_dieu_phoi_quyet` => moi thu HAI CHO DO
    ghi ra state deu MAT. Ra soat 15/09 loi ra hai lo, ca hai deu lam party DUNG IM vinh vien:

        `dt_phase`     - het gio Di Gioi ma khong ai doi pha -> ket pha DG mai mai
        `mob_spot` /
        `train_map_dich` - khong ai chot map train + bai quai -> gom du party xong dung im o thanh

    Bai nay giu cho ca ba thu do luon co nguoi ghi.
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")

    def test_engine_moi_TU_doi_pha_DG_sang_train(self):
        s = _src("bot", "party_engine.py")
        self.assertIn("def _doi_pha_neu_het_gio_dg", s, "khong ai doi pha -> ket pha DG vinh vien")
        i = s.find("def nhip(self)")
        self.assertIn("_doi_pha_neu_het_gio_dg", s[i:i + 400], "doi pha khong chay moi nhip")

    def test_doi_pha_GHI_NGUOC_ra_state(self):
        """Khong ghi nguoc thi `_pha_engine_moi` doc lai `dt_phase` cu -> nhip sau ve lai pha DG."""
        self.assertIn("def _ghi_pha_engine_moi(", self.src)
        self.assertIn("ghi_pha=", self.src)

    def test_engine_moi_TU_chot_map_train_va_bai_quai(self):
        self.assertIn("def _chuan_bi_bai_train(", self.src,
                      "khong ai chot bai -> party gom du xong dung im o thanh")
        i = self.src.find("def _chuan_bi_bai_train(")
        than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]
        self.assertIn("_dieu_phoi_chot_map(", than, "phai goi lai ham co san, khong tu che")
        self.assertIn("_resolve_train_mob_centers(", than)
        self.assertIn('st["mob_spot"]', than)
        self.assertIn('st["train_map_dich"]', than)

    def test_chot_bai_chay_o_vong_GIU_SONG_khong_phai_trong_NHIP(self):
        """`_resolve_train_mob_centers` co the chan vai giay; nhip quyet dinh thi tuyet doi khong
        duoc chan (do la ca diem cua engine moi)."""
        s = _src("bot", "party_engine.py")
        i = s.find("def nhip(self)")
        khoi = s[i:i + 1500]
        self.assertNotIn("_chuan_bi_bai_train", khoi)
        self.assertNotIn("_resolve_train_mob_centers", khoi)

    def test_chi_MOT_NGUOI_chot_bai(self):
        """Nam acc cung chot bai = nam tam quai khac nhau, party toe ra nam huong.

        Gio viec nay chay trong NHIP ENGINE (1 thread/party) nen tu no da chi co mot nguoi lam -
        va no lay client cua LEADER. Truoc day chay o thread tung acc, phai tu chan bang
        `if is_leader:` (de ra them thread, chinh la thu lam GUI treo ngay 15/09)."""
        i = self.src.find("def _cap_nhat_engine(")
        self.assertGreater(i, 0, "viec chot bai khong con chay trong nhip engine")
        than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]
        self.assertIn("PARTY_LEADER_ACC.get(pidx)", than, "khong lay client cua LEADER")
        self.assertIn("_chuan_bi_bai_train(", than)

    def test_cap_nhat_cau_hinh_chay_TRONG_NHIP_khong_de_ra_thread(self):
        """Do that 15/09 tren may user: 799 thread, 798 cai ngoi tranh GIL, main thread Tk doi ->
        GUI "not responding". Engine moi de ra them thread la di nguoc chinh cai no phai chua."""
        s = _src("bot", "party_engine.py")
        i = s.find("def nhip(self)")
        self.assertIn("_cap_nhat", s[i:i + 400], "cau hinh khong duoc cap nhat trong nhip")
        # worker KHONG duoc tu tao thread o ban chay that
        i2 = s.find("def start(self):")
        self.assertIn("Chi dung trong test", s[i2:i2 + 400],
                      "worker tu tao thread -> them 1 thread/acc")
        self.assertIn("def chay_o_day(self", s,
                      "khong co duong chay tren thread san co cua acc")


class TestPBToDoiKHONG_CHO_AI_BAO_CAO(unittest.TestCase):
    """RULE_DIEU_PHOI: "khong acc nao cho acc khac bao cao. Ca party chay trong MOT tien trinh nen
    `account_clients[u]` da co san moi thu".

    Lop `_handle_auto_team_dungeon` cua engine cu co barrier dua tren bao cao: moi acc tu gan
    `_o5_da_xong` len client, leader doc dau vet do; acc nao chua bao thi leader "coi nhu DA XONG"
    va BO pho ban. Voi engine moi (mot luong nam ca 5 client) co che do vua THUA vua HONG.

    Ca that 16/09 party 41 - quay vong 6 giay/lan tu 09:34, khong danh tran nao:
        09:37:27 [dtsau] (LEADER) o5: 5/5 acc chua bao (['dt806'..'dt810']) -> coi nhu DA XONG
        09:37:33  ... y het ...
    Con dt807/808/810 thi dung o `pb_doi_theo` cho duoc keo vao phong mai mai.
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")
        i = self.src.find("def _chay_pb_doi_engine_moi(")
        self.assertGreater(i, 0)
        self.than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]

    def test_KHONG_qua_lop_cho_bao_cao(self):
        self.assertNotIn("_handle_auto_team_dungeon(", self.than,
                         "van di qua barrier bao cao -> leader bo PB moi luot")

    def test_KHONG_gan_dau_vet_gia_de_chieu_long_barrier(self):
        """Va dau vet `_o5_da_xong` la chieu long mot co che le ra khong ton tai o engine moi.

        (Nhac ten no trong ghi chu thi duoc - cam la GAN gia tri.)"""
        self.assertNotIn("_o5_da_xong =", self.than)
        self.assertNotIn("._o5_da_xong", self.than.replace("`_o5_da_xong`", ""))

    def test_goi_thang_kich_ban_danh_PB(self):
        self.assertIn("do_team_dungeon(", self.than)

    def test_con_luot_doc_tu_DONG_HO_SERVER(self):
        """Khong dem local, khong hoi acc khac: `team_dungeon_remaining` <- `mission_steps`."""
        eng = _src("bot", "party_engine.py")
        i = eng.find("def _pb_doi_level(self)")
        self.assertGreater(i, 0)
        than = eng[i:i + 1600]
        self.assertIn("team_dungeon_remaining", than)
        self.assertIn("mission_steps_loaded", than, "chua co bang mission-step ma da ket luan")


class TestStopVE_SAFE_TRUOC_y_flow_cu(unittest.TestCase):
    """STOP -> ve safe roi moi dong, LAM Y `run_account` dong 7150-7153 + 7207-7229:

        LEADER train : `_return_safe_on_stop = train_safes` -> chay ve safe gan nhat roi bao
                       `stop_leader_done`
        member train : `_wait_leader_on_stop = True` -> CHO leader ve safe (toi da 60s) roi thoat

    De acc dung ngay tai bai quai thi lan login sau vao la bi quai danh ngay.
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")

    def test_co_ham_ve_safe_khi_stop(self):
        self.assertIn("def _ve_safe_khi_stop_engine_moi(", self.src)

    def test_LEADER_ve_safe_roi_BAO_member(self):
        i = self.src.find("def _ve_safe_khi_stop_engine_moi(")
        than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]
        self.assertIn("_nearest_safe(", than, "leader khong tim safe gan nhat")
        self.assertIn('st["stop_leader_done"].set()', than, "khong bao member -> member cho 60s vo ich")

    def test_member_CHO_leader_roi_moi_thoat(self):
        i = self.src.find("def _ve_safe_khi_stop_engine_moi(")
        than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]
        self.assertIn('st["stop_leader_done"].wait(', than)
        self.assertIn("STOP_CHO_LEADER_SEC", than, "cho vo han -> STOP khong bao gio dut")

    def test_bao_stop_account_DUNG_DONG_SOCKET_NGAY(self):
        """Thieu hai co nay thi STOP dong socket lap tuc, worker KHONG KIP ve safe."""
        i = self.src.find("def _cap_nhat_engine(")
        than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]
        self.assertIn("_return_safe_on_stop", than)
        self.assertIn("_wait_leader_on_stop", than)

    def test_chi_bat_co_khi_DANG_O_MAP_TRAIN(self):
        """Bat bua thi STOP phai cho watchdog 25s moi dut, du acc dang dung o thanh."""
        i = self.src.find("def _cap_nhat_engine(")
        than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]
        self.assertIn("_tren_bai", than)

    def test_worker_goi_ve_safe_SAU_khi_thoat_vong(self):
        s = _src("bot", "party_engine.py")
        i = s.find("def chay_o_day(self")
        than = s[i:i + 1200]
        self.assertLess(than.find("self._vong()"), than.find("_ve_safe_khi_stop"),
                        "ve safe TRUOC khi thoat vong -> chay ve safe giua luc dang lam viec khac")


class TestHoiThangHamCu_KhongTuVietPhepThu(unittest.TestCase):
    """"Thanh di ngang qua" phai HOI `_o_thanh_di_qua`, khong tu viet lai phep thu.

    Ham cu da can nhac ky: chi True khi CHAC CHAN (la thanh teleport, da biet dich, va khac ca
    dich lan map train) - "tha lap party thua con hon khong bao gio lap". Tu viet lai la de ra mot
    phep thu thu hai cho cung mot cau hoi.
    """

    def test_engine_hoi_qua_callback(self):
        s = _src("bot", "party_engine.py")
        self.assertIn("self.hoi_thanh", s)
        i = s.find("def chup(self)")
        self.assertIn("hoi_thanh", s[i:i + 3000], "chup anh khong hoi -> luon coi la thanh tap ket")

    def test_noi_vao_dung_ham_cu(self):
        s = _src("run_party_digioi.py")
        i = s.find("hoi_thanh=")
        self.assertGreater(i, 0, "khong noi callback -> engine mu ve thanh trung gian")
        self.assertIn("_o_thanh_di_qua(", s[i:i + 200], "tu viet phep thu rieng")

    def test_hoi_LOI_thi_coi_nhu_thanh_tap_ket(self):
        """Hoi loi ma coi la thanh trung gian thi party se di lang quang mai, khong bao gio lap."""
        s = _src("bot", "party_engine.py")
        i = s.find("self.hoi_thanh(")
        self.assertGreater(i, 0)
        self.assertIn("except", s[i:i + 200])


class TestDungDU_PHEP_THU_CUA_ENGINE_CU(unittest.TestCase):
    """RA SOAT 16/09 (user: "tu quet lai toan bo cai moi xem con cai nao ko dung flow cu ko").

    Doi chieu tung phep thu `_dieu_phoi_quyet` dung voi engine moi. Nam cai bi bo sot lan dau:
    `_leader_dang_rot`, `_dang_doi_kenh`, `_thieu_acc_song`, `_ai_lech_instance`, `_o_thanh_di_qua`.
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")
        i = self.src.find("def _chua_nen_ra_lenh_engine_moi(")
        self.assertGreater(i, 0, "khong co cua 'chua nen ra lenh'")
        self.than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]

    def test_KHONG_goi_lai_phep_thu_nao(self):
        """SUA 16/09: bon phep thu do nam BEN TRONG `_dieu_phoi_quyet` va chinh no da ra lenh xu
        ly (leader rot -> MOI, dang doi kenh/thieu acc -> LAM, lech instance -> DONG_BO). Goi lai
        o day = tang chan DE LEN dung cai lenh giai quyet tinh huong do, va vi `cho_ly_do` lam
        `quyet_dinh` GIU NGUYEN viec dang lam nen party ket cung vinh vien.

        Ca that party 43: dieu phoi chot `dong_bo` lien tuc trong 100 giay ma engine van giao
        `lap_party` (120 lan lien tiep)."""
        for phep in ("_leader_dang_rot(", "_dang_doi_kenh(", "_thieu_acc_song(",
                     "_ai_lech_instance("):
            self.assertNotIn(phep, self.than.split(chr(34) * 3)[-1],
                             "%s da nam trong _dieu_phoi_quyet - khong duoc chan lai o day" % phep)

    def test_luon_ra_lenh_duoc(self):
        """L0: khong duoc co duong nao lam party dung im vinh vien."""
        self.assertIn('return ""', self.than)

    def test_engine_hoi_cua_nay_MOI_NHIP(self):
        eng = _src("bot", "party_engine.py")
        i = eng.find("def chup(self)")
        self.assertIn("hoi_cho", eng[i:i + 5000], "khong hoi -> ra lenh giua luc party xao tron")

    def test_QUYET_DINH_lay_tu_dieu_phoi_cu(self):
        """Engine moi KHONG tu nghi ra chuoi lenh: chuoi that co 11 nhanh + 15 phep thu, ban tu
        viet chi co 4 bac -> moi nhanh thieu la mot loi user phai di tim ho."""
        eng = _src("bot", "party_engine.py")
        i = eng.find("def chup(self)")
        self.assertIn("hoi_dieu_phoi", eng[i:i + 5000], "khong hoi dieu phoi -> lai tu bia chuoi lenh")
        self.assertIn("DICH_VIEC", eng, "khong co bang dich viec cap party -> viec thi hanh")
        src = _src("run_party_digioi.py")
        i2 = src.find("def _dieu_phoi_quyet_engine_moi(")
        self.assertGreater(i2, 0, "khong co cau noi toi `_dieu_phoi_quyet`")
        than = src[i2:src.find(chr(10) + "def ", i2 + 10)]
        self.assertIn("_dieu_phoi_quyet(", than, "tu viet lai thay vi goi ham cu")


class TestFLAG_THANH_lay_tu_bang_config(unittest.TestCase):
    """Moi thanh mot flag rieng trong `config.TELEPORT_CITIES`: Trac Quan 0, Nghiep Thanh 2,
    Cu Loc 3, Bac Hai 1, Kien Nghiep 9... Engine cu luon doc flag tu bang do
    (`_gc_flag = TELEPORT_CITIES[_gc]["flag"]`).

    Truyen thieu flag la bay ve NHAM THANH, va vi map khong bao gio khop dich nen no TELE LAI
    lien tuc (user 16/09: "deo gi ma tele lien tuc lai con bi sai flag").
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")
        i = self.src.find("def _thanh_dich_engine_moi(")
        self.assertGreater(i, 0, "khong co ham tra (city, flag)")
        self.than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]

    def test_GOI_THANG_ham_chot_thanh_cua_engine_cu(self):
        """`chot_thanh_tap_ket` (truoc la closure `_chot_thanh_tap_ket` trong `_do_reform`, tach ra
        cap module 17/09). No da lo: thanh cua CHINH ROUTE, fallback `TRAIN_ROUTES.from_city`,
        fallback "khong co route van phai gom", va MOT ban chot dung chung trong `st["route_plan"]`.

        Truoc day engine moi dung `_pick_start_city` (loc theo "thanh CA PARTY deu da mo") - ra
        thanh KHAC voi thanh router dung, nen party gom o thanh A con leader di duong tu thanh B,
        ma teleport bat buoc ROI DOI -> party vua du lai tan.
        Ca that 17/09 party 45 (user: "p45 van moi dua 1 thanh"):
            09:01:45 >>> PARTY 45: thanh xuat phat = Hoi Ke (id 18021, 9 cong toi 15457)
            09:02:06 TRANG THAI: chdumot@12061(L) chduhai@18021 chduba@18021 chdubon@18021 ...
        """
        self.assertIn("chot_thanh_tap_ket(", self.than, "tu chon thanh thay vi goi ham cu")

    def test_KHONG_viet_lai_phep_chon_thanh(self):
        """Chep lai la de ra ban thu hai cho cung cau hoi - hai ben se chon thanh khac nhau."""
        _thi_hanh = self.than.split(chr(34) * 3)[-1]     # bo docstring, chi soi phan THI HANH
        # `_gather_city` VAN duoc goi o day, va do la DUNG FLOW CU: thanh cua route chua mo thi
        # gom o thanh khac roi leader keo di bo (`_activate_nghiep_fallback`). Cai cam la tu nghi
        # ra phep chon thanh RIENG.
        for _cam in ("_pick_start_city(", "build_smart_route(", "_thanh_dong_acc_nhat("):
            self.assertNotIn(_cam, _thi_hanh,
                             "%s da nam trong `chot_thanh_tap_ket` - khong goi lai o day" % _cam)

    def test_tra_ve_CA_HAI(self):
        """`route_plan` mang san `flag` di kem `city` - thieu flag la bay ve NHAM THANH."""
        self.assertIn('int(_p.get("flag") or 0)', self.than)


class TestChiNHAN_MODE_BIET_LAM(unittest.TestCase):
    """Engine moi khong co nhanh nao cho `event` (40NPC / 2K / loan dau): khong dang ky event,
    khong vao map event, khong doc `go_claim`/`event_battle_done`, khong biet "danh xong thi out".

    Nhan party mode do thi no xu ly y nhu train -> LAP PARTY NGAY GIUA THANH khi chua vao map
    event (user 16/09: "p41, mode 40npc -> chua vao map event da thay lap pt").
    """

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        self._ng = getattr(R.config, "PARTY_ENGINE_MOI_TU", None)
        R.config.PARTY_ENGINE_MOI_TU = 41
        R.config.PARTY_CONFIG = {
            40: {"mode": "event", "event_key": "npc_40"},
            41: {"mode": "digioi_train"},
            42: {"mode": "digioi"},
            43: {"mode": "train"},
            44: {"mode": "city"},
            45: {},                       # khong khai mode
        }

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        if self._ng is None:
            if hasattr(R.config, "PARTY_ENGINE_MOI_TU"):
                delattr(R.config, "PARTY_ENGINE_MOI_TU")
        else:
            R.config.PARTY_ENGINE_MOI_TU = self._ng

    def test_mode_EVENT_da_lam_nen_duoc_nhan(self):
        """Lam 16/09: PHA_EVENT + ba viec `vao_event`/`danh_event`/`doi_thuong`, deu goi lai duong
        cua engine cu."""
        self.assertTrue(R.dung_engine_moi(40))

    def test_mode_engine_moi_BIET_LAM_thi_nhan(self):
        self.assertTrue(R.dung_engine_moi(41))
        self.assertTrue(R.dung_engine_moi(42))

    def test_mode_LA_deu_tra_cho_engine_cu(self):
        for _p in (43, 44, 45):
            self.assertFalse(R.dung_engine_moi(_p), "nhan bua mode party %d" % (_p + 1))

    def test_danh_sach_mode_ghi_RO_RANG(self):
        self.assertEqual(R.MODE_ENGINE_MOI, ("digioi_train", "digioi", "event"),
                         "them mode vao day CHI SAU khi engine moi that su lam duoc mode do")

    def test_ba_viec_event_deu_GOI_LAI_duong_cu(self):
        """Khong duoc tu viet lai vong danh: xu ly thua / hoi mau giua tran nam trong
        `start_npc40_loop` + hai callback cua engine cu."""
        src = _src("run_party_digioi.py")
        for ten, phai_co in (("_vao_event_engine_moi", "c.go_to_event("),
                             ("_danh_event_engine_moi", "c.start_npc40_loop("),
                             ("_doi_thuong_engine_moi", "c.claim_40npc_reward(")):
            i = src.find("def %s(" % ten)
            self.assertGreater(i, 0, "thieu cau noi %s" % ten)
            than = src[i:src.find(chr(10) + "def ", i + 10)]
            self.assertIn(phai_co, than, "%s khong goi %s" % (ten, phai_co))

    def test_danh_event_giu_DU_HAI_callback(self):
        """`_on_npc40_loss` (thua -> dung) va `_before_npc40_repeat` (hoi mau CA PARTY truoc tran
        ke). Thieu mot la party danh tiep voi mau can hoac mo lai battle sau khi da thua."""
        src = _src("run_party_digioi.py")
        i = src.find("def _danh_event_engine_moi(")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        self.assertIn("_on_npc40_loss", than)
        self.assertIn("_before_npc40_repeat", than)
        self.assertIn("heal_npc40_between_battles", than, "quen hoi mau giua hai tran")
        self.assertIn("_set_party_quest_mode(", than, "quen gia han quest-mode cho ca party")

    def test_doi_thuong_thi_THOAT_GAME(self):
        """User 14/09: "event thi danh xong out, train deo gi o day"."""
        src = _src("run_party_digioi.py")
        i = src.find("def _doi_thuong_engine_moi(")
        than = src[i:src.find(chr(10) + "def ", i + 10)]
        self.assertIn("leave_party()", than, "khong huy party truoc khi doi thuong")
        self.assertIn("stop_account(", than, "doi thuong xong ma khong thoat game")

    def test_nguong_van_duoc_ton_trong(self):
        """Mode dung nhung party duoi nguong thi van la engine cu."""
        R.config.PARTY_CONFIG[10] = {"mode": "digioi_train"}
        self.assertFalse(R.dung_engine_moi(10))


class TestEVENT_xoa_co_khi_LOGIN_MOI(unittest.TestCase):
    """PHIEN LOGIN MOI -> xoa co "da thua / da xong" cua phien truoc (engine cu, dong 5914-5919).

    `go_claim` / `event_battle_done` song trong `_party_state[pidx]` = state theo TIEN TRINH, khong
    phai theo lan login. Khong xoa thi acc VUA LOGIN da doc thay "event xong" -> di doi thuong +
    thoat NGAY, khong danh tran nao. Ghi chu ban cu: "`go_claim` set mot lan la moi acc login sau
    do doc thay -> LOG VAO XONG OUT LUON, khong danh tran nao".
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")
        i = self.src.find("def _dang_ky_engine_moi(")
        self.than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]

    def test_co_xoa_hai_co(self):
        self.assertIn('st["go_claim"].clear()', self.than, "khong xoa -> login xong out luon")
        self.assertIn('st["event_battle_done"].clear()', self.than)

    def test_CHI_xoa_khi_KHONG_phai_reconnect(self):
        """`is_reconnect` = rot giua chung -> GIU quyet dinh cua party, khong de mot acc vao lai
        lam ca party danh tiep trong khi bon kia da bo cuoc."""
        self.assertIn("if not is_reconnect", self.than)

    def test_chi_ap_cho_mode_event(self):
        self.assertIn('.get("mode") == "event"', self.than)

    def test_diem_re_truyen_is_reconnect(self):
        i = self.src.find("_dang_ky_engine_moi(username, c, pidx, is_leader, label, _stopped")
        self.assertGreater(i, 0)
        self.assertIn("is_reconnect=is_reconnect", self.src[i:i + 200],
                      "khong truyen -> engine moi luon tuong la login moi")


class TestAPKPhaiCoFileEngine(unittest.TestCase):
    """`party_engine.py` PHAI duoc chep sang APK, DU engine dang chay thu tren PC.

    Lan dau t khai no la PC_ONLY cho "an toan" - va do la SAI HAN: `run_party_digioi.py` la file
    DUNG CHUNG va co `from . import party_engine` ngay dau file. Thieu file ben APK thi APK
    **CRASH LUC IMPORT**, chu khong phai "chay engine cu binh thuong".

    Dung ho loi CLAUDE.md da canh bao (cong chan thu 7): lech PC/APK khong lam build hong, no no
    GIUA LUC CHAY tren may user.

    An toan nam o cho khac: `PARTY_ENGINE_MOI_TU = 0` -> engine TAT tren ca hai ban.
    """

    def test_party_engine_duoc_SYNC_sang_APK(self):
        s = _src("tools", "sync_apk_python.py")
        i = s.find("SHARED = [")
        j = s.find("]", i)
        self.assertIn("party_engine.py", s[i:j],
                      "khong sync -> APK crash luc import `from . import party_engine`")

    def test_file_co_THAT_o_ban_APK(self):
        self.assertTrue(
            os.path.isfile(os.path.join(ROOT, "android", "app", "src", "main", "python",
                                        "train_bot", "party_engine.py")),
            "ban APK thieu party_engine.py -> crash ngay khi import")

    def test_ban_APK_co_import_party_engine(self):
        """Neu mot ngay nao do bo import nay thi test tren khong con y nghia - neo lai de biet."""
        s = _src("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        self.assertIn("from . import party_engine", s)

    def test_APK_dung_CUNG_nguong_voi_PC(self):
        """File dung chung -> hai ban phai giong het (sync tu kiem). Neo lai de thay ro: bat engine
        o PC la bat luon o APK, khong co duong tach rieng."""
        apk = _src("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        pc = _src("run_party_digioi.py")
        i = pc.find("PARTY_ENGINE_MOI_TU = ")
        dong = pc[i:pc.find(chr(10), i)]
        self.assertIn(dong, apk, "PC va APK lech nguong engine")

    def test_py38_future_annotations(self):
        """Chaquopy chay Python 3.8: file .py moi thieu dong nay la crash
        'type object is not subscriptable'."""
        s = _src("bot", "party_engine.py")
        self.assertIn("from __future__ import annotations", s)


if __name__ == "__main__":
    unittest.main()


class TestKHONG_CO_CUA_CHAN_DE_LEN_DIEU_PHOI(unittest.TestCase):
    """`_chua_nen_ra_lenh_engine_moi` KHONG duoc goi lai cac phep thu cua `_dieu_phoi_quyet`.

    Ca that 16/09 party 43: dieu phoi chot `dong_bo` (tq405 khac instance du cung so kenh) nhung
    cua chan `_ai_lech_instance` lam `cho_ly_do` != "" -> `quyet_dinh` giu nguyen viec dang lam ->
    `lap_party` giao lai 120 lan lien tiep, khong bao gio dong bo kenh.
    """

    def test_than_ham_khong_con_goi_phep_thu_nao(self):
        import io as _io
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        i = s.index("def _chua_nen_ra_lenh_engine_moi(pidx):")
        j = s.index("def _ve_safe_khi_stop_engine_moi(", i)
        than = s[i:j]
        # bo docstring roi moi soi phan THI HANH
        than = than.split('"""')[-1]
        for _f in ("_leader_dang_rot", "_dang_doi_kenh", "_thieu_acc_song", "_ai_lech_instance"):
            self.assertNotIn(_f + "(", than,
                             "%s da nam trong _dieu_phoi_quyet - goi lai o day la tang chan de len "
                             "chinh lenh giai quyet no" % _f)
        self.assertIn('return ""', than)


class TestENGINE_MOI_PHAI_CHOT_KENH_DICH(unittest.TestCase):
    """Vong dieu phoi cu goi `_dieu_phoi_chot_kenh` NGAY SAU `_dieu_phoi_quyet` - no moi la nguoi
    CHON kenh (it nguoi nhat ma du cho ca team, tranh kenh vua bao DAY). `kh["kenh"]` khong tu co.

    Thieu buoc nay: lenh `dong_bo` mang kenh dich = None, `thi_hanh` gap `dich is None` la coi nhu
    XONG NGAY -> party lech kenh vinh vien.
    Ca that 16/09 party 43 (user: "p43 bi lech kenh ma ko dong bo lai"): 21:21:19 -> 21:22:57 dieu
    phoi chot `dong_bo` deu deu ma KHONG MOT DONG `CHOT kenh dich` nao.
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")
        i = self.src.find("def _dieu_phoi_quyet_engine_moi(")
        self.assertGreater(i, 0)
        self.than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]

    def test_co_goi_chot_kenh_va_chot_map(self):
        self.assertIn("_dieu_phoi_chot_kenh(", self.than, "khong ai chon kenh dich cho engine moi")
        self.assertIn("_dieu_phoi_chot_map(", self.than)

    def test_chay_NOT_chuoi_cua_vong_dieu_phoi_cu(self):
        """Vong quet cu goi BON ham nua ngay sau `_dieu_phoi_quyet`. `_dieu_phoi_thi_hanh` moi la
        cho bien `gom`/`dong_bo` thanh hanh dong that (bump reform), va `_dieu_phoi_thi_hanh_kenh`
        moi la nguoi GUI lenh doi kenh."""
        for _f in ("_ghi_ke_hoach(", "_dieu_phoi_thi_hanh(", "_dieu_phoi_thi_hanh_kenh("):
            self.assertIn(_f, self.than, "engine moi bo mat %s cua vong dieu phoi cu" % _f)

    def test_KHONG_co_nguon_thu_hai_gui_lenh_kenh(self):
        """`dong_bo` khong duoc dich thanh viec thi hanh: dieu phoi da tu gui lenh doi kenh."""
        eng = _src("bot", "party_engine.py")
        i = eng.index("DICH_VIEC = {")
        _bang = eng[i:i + 2000]
        self.assertIn("DP_DONG_BO: VIEC_NGHI", _bang)
        self.assertIn("DP_GOM: VIEC_NGHI", _bang)


class TestLEADER_VAO_LAI_thi_HA_CO_DANH_EVENT(unittest.TestCase):
    """`event_battle_active` bat khi leader mo `start_npc40_loop` - vong do song TREN CLIENT cua
    leader. Leader rot la vong chet, nhung co nam trong `_party_state` nen con bat mai.

    Hau qua: `_dieu_phoi_thi_hanh_kenh` hoi `_vi_sao_chua_doi_kenh` -> "CA PARTY dang danh event"
    -> KHONG BAO GIO gui lenh doi kenh. Ca that 16/09 party 45 (user: "p45 moi dua 1 kenh"):
    leader vao lai o kenh 9, dieu phoi chot dung kenh dich 1 ma lenh bi chan, roster ket 0/4.
    """

    def setUp(self):
        self.src = _src("run_party_digioi.py")
        i = self.src.find("def _dang_ky_engine_moi(")
        self.assertGreater(i, 0)
        self.than = self.src[i:self.src.find(chr(10) + "def ", i + 10)]

    def test_co_ha_co_khi_leader_reconnect(self):
        self.assertIn('st["event_battle_active"] = False', self.than,
                      "leader vao lai ma khong ha co -> lenh doi kenh bi chan vinh vien")

    def test_chi_ha_cho_LEADER_va_mode_EVENT(self):
        i = self.than.find('st["event_battle_active"] = False')
        dieu_kien = self.than[:i]
        self.assertIn("is_reconnect and username == config.PARTY_LEADER_ACC.get(pidx)", dieu_kien,
                      "member vao lai ma ha co la cat ngang tran party dang danh that")
        self.assertIn('== "event"', dieu_kien)
