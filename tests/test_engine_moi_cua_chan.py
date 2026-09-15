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

    def tearDown(self):
        if self._cu is None:
            if hasattr(R.config, "PARTY_ENGINE_MOI_TU"):
                delattr(R.config, "PARTY_ENGINE_MOI_TU")
        else:
            R.config.PARTY_ENGINE_MOI_TU = self._cu

    def test_mac_dinh_TAT(self):
        """Mac dinh phai la TAT: engine moi chua co so lieu, khong duoc tu bat tren may user."""
        self.assertEqual(R.PARTY_ENGINE_MOI_TU, 0)

    def test_so_0_la_tat_han(self):
        R.config.PARTY_ENGINE_MOI_TU = 0
        self.assertFalse(any(R.dung_engine_moi(i) for i in range(60)))

    def test_nguong_41_dung_pham_vi_user_chot(self):
        """User 15/09: "party >40 la theo co che moi"."""
        R.config.PARTY_ENGINE_MOI_TU = 41
        self.assertFalse(R.dung_engine_moi(39), "party 40 phai giu engine cu")
        self.assertTrue(R.dung_engine_moi(40), "party 41 phai la engine moi")
        self.assertTrue(R.dung_engine_moi(53))

    def test_chay_thu_2_party_truoc(self):
        """Ha dan tu 53 -> 41 (muc 7): bat ca 14 party ngay dem dau la hong mot dem mat 62 acc."""
        R.config.PARTY_ENGINE_MOI_TU = 53
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
        self.assertIn("_bao_gui", s[i:i + 1200], "nhip khong bao GUI -> user mu ca party")

    def test_noi_vao_set_account_activity(self):
        s = _src("run_party_digioi.py")
        i = s.find("def _dang_ky_engine_moi(")
        self.assertGreater(i, 0)
        self.assertIn("set_account_activity", s[i:i + 2500],
                      "khong noi vao duong GUI co san")

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

    def test_chi_LEADER_chot_bai(self):
        """Nam acc cung chot bai = nam tam quai khac nhau, party toe ra nam huong."""
        # `rfind`: cho GOI nam sau cho DINH NGHIA trong file
        i = self.src.rfind("_chuan_bi_bai_train(c, st, pidx, label)")
        self.assertGreater(i, 0)
        self.assertIn("if is_leader:", self.src[max(0, i - 900):i])


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

    def test_engine_TAT_mac_dinh_tren_ca_hai_ban(self):
        s = _src("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        self.assertIn("PARTY_ENGINE_MOI_TU = 0", s,
                      "APK bat engine moi khi chua co so lieu = mang ban thu ra dien thoai user")

    def test_py38_future_annotations(self):
        """Chaquopy chay Python 3.8: file .py moi thieu dong nay la crash
        'type object is not subscriptable'."""
        s = _src("bot", "party_engine.py")
        self.assertIn("from __future__ import annotations", s)


if __name__ == "__main__":
    unittest.main()
