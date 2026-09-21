"""Quyet dinh CAP PARTY da chuyen vao ENGINE (`party_engine.quyet_dinh_cap_party`).

User 21/09: "chuyen ve cung 1 thread thi de cai dieu phoi lam lon gi nua, thread biet het tat ca
thong tin roi thi no phai nam vai tro dieu phoi luon" / "ve lau dai tao se xoa engine cu va dieu
phoi".

Bai test nay ep hai thu:
  1. THU TU NHANH LA LUAT - nhanh duoi chi dung khi nhanh tren da loai tru xong. Moi nhanh o day
     deu kem ca hong that da sinh ra no, giong ban goc `_dieu_phoi_quyet`.
  2. HAM THUAN - khong doc dong ho, khong khoa, khong I/O: moi thay doi trang thai phai di ra
     bang `HieuUng` de nguoi goi thi hanh.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as PE


def _anh(**kw):
    """Anh chup MAC DINH = party lanh lan: du doi, cung map, cung kenh, dang train."""
    mac_dinh = dict(
        bay_gio=1000.0, so_acc_song=5, so_acc_cau_hinh=5, raw_mode="train", pha=PE.PHA_TRAIN,
        can_lap_doi=True, ngoai_gio_40npc=False, event_xong=False, ca_party_het_gio_dg=False,
        maps={21001: ["a1", "a2", "a3", "a4", "a5"]}, kenhs={1}, chua_biet_map=[],
        lech_kenh_that=0, mot_minh=(), du_doi=True, leader_dang_rot=False, dang_doi_kenh=False,
        thieu_acc_song=False, ai_lech_instance=[], o_thanh_di_qua=False, thanh_tap_ket=12001,
        ca_party_o_thanh=False, acc_dung_hinh=[], viec_di_train=PE.DP_LAM, ly_do_di_train="",
        tinh_hinh_doi="a1=4 a2=4", ly_do_lech="lech", ly_do_lech_dg="lech trong DG",
        kenh_hien_tai=1, lech_tu=None, het_lech_tu=None, o_thanh_tu=0.0,
        reform_gen=0, reform_gen_thoa=0, leader_acc="a1", co_leader_dang_song=True,
        thanh_cu=None, han_lech_map=10.0, han_lech_chung=45.0, han_het_lech=8.0,
        han_dung_hinh=240.0,
    )
    mac_dinh.update(kw)
    return PE.AnhCapParty(**mac_dinh)


class TestBaCuaDauChanTruocMoiThu(unittest.TestCase):
    """Ba lenh `moi`/`gom`/`dong_bo` deu sinh ra tu ham nay, nen phai chan ngay o cua dau."""

    def test_mode_khong_can_lap_doi(self):
        viec, ly_do, _hu = PE.quyet_dinh_cap_party(_anh(can_lap_doi=False, du_doi=False,
                                                        maps={1: ["a"], 2: ["b"]}))
        self.assertEqual(viec, PE.DP_LAM)
        self.assertIn("KHONG CAN LAP DOI", ly_do)

    def test_40npc_ngoai_gio(self):
        viec, _l, _hu = PE.quyet_dinh_cap_party(_anh(ngoai_gio_40npc=True, du_doi=False))
        self.assertEqual(viec, PE.DP_LAM)

    def test_event_da_xong(self):
        """User 14/09: "event thi danh xong out, train deo gi o day"."""
        viec, _l, _hu = PE.quyet_dinh_cap_party(_anh(event_xong=True, du_doi=False,
                                                     maps={1: ["a"], 2: ["b"]}))
        self.assertEqual(viec, PE.DP_LAM)


class TestThuTuNhanh(unittest.TestCase):
    def test_LECH_MAP_thi_chua_den_luot_lap_party(self):
        """User 08/09: "gom lai thi cai dau tien phai check la co cung map hay ko"."""
        viec, ly_do, _hu = PE.quyet_dinh_cap_party(
            _anh(maps={12001: ["a1"], 21001: ["a2"]}, du_doi=False))
        self.assertEqual(viec, PE.DP_LAM)
        self.assertIn("lech map", ly_do)

    def test_lech_map_QUA_HAN_thi_GOM(self):
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(maps={12001: ["a1"], 21001: ["a2"]}, du_doi=False,
                 lech_tu=1000.0 - 99, bay_gio=1000.0))
        self.assertEqual(viec, PE.DP_GOM)

    def test_lech_kenh_qua_han_CUNG_MAP_thi_DONG_BO_khong_gom(self):
        """Party 5 (06/09): ca 5 acc o map 12922 ma ra lenh GOM - gom ve thanh giua thap 2K la vo
        nghia, leader quay vong 201.495 lan."""
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(kenhs={1, 5}, du_doi=False, lech_tu=1000.0 - 99))
        self.assertEqual(viec, PE.DP_DONG_BO)

    def test_thieu_acc_login_thi_CHUA_ket_luan(self):
        """Party 2 (13/09): 2 dua vao truoc cung kenh 1 -> ket luan nham "ca party cung kenh"."""
        viec, ly_do, _hu = PE.quyet_dinh_cap_party(
            _anh(thieu_acc_song=True, so_acc_song=2, du_doi=False))
        self.assertEqual(viec, PE.DP_LAM)
        self.assertIn("login xong", ly_do)

    def test_chua_biet_map_thi_CHUA_xuong_bac_kenh(self):
        """Party 9 (13/09): 4 dua cung map + 1 chua biet -> tut xuong bac kenh -> khong bao gio
        chot duoc kenh dich."""
        viec, ly_do, _hu = PE.quyet_dinh_cap_party(_anh(chua_biet_map=["a5"], du_doi=False))
        self.assertEqual(viec, PE.DP_LAM)
        self.assertIn("chua doc duoc map", ly_do)

    def test_leader_rot_thi_MOI_va_reset_so_nho(self):
        viec, _l, hu = PE.quyet_dinh_cap_party(_anh(leader_dang_rot=True, du_doi=False))
        self.assertEqual(viec, PE.DP_MOI)
        self.assertTrue(hu.reset_joined, "so nho khong duoc giu nguoi cua party da tan (L2d)")

    def test_dang_doi_kenh_thi_CHO_roster_on_dinh(self):
        viec, _l, _hu = PE.quyet_dinh_cap_party(_anh(dang_doi_kenh=True, du_doi=False))
        self.assertEqual(viec, PE.DP_LAM)

    def test_du_doi_cung_map_kenh_thi_DI_TRAIN(self):
        viec, _l, _hu = PE.quyet_dinh_cap_party(_anh(viec_di_train=PE.DP_DI_TRAIN))
        self.assertEqual(viec, PE.DP_DI_TRAIN)


class TestKhacInstanceThiDanhDauKenhHONG(unittest.TestCase):
    """Ca that 21/09 party 43 - DUNG MOT TIENG o Tuong Duong (82 lan). `dong_bo` ma khong danh dau
    kenh hong thi la lenh RONG: ca party DA cung so kenh roi."""

    def test_ra_lenh_dong_bo(self):
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(du_doi=False, ai_lech_instance=["tq402"]))
        self.assertEqual(viec, PE.DP_DONG_BO)

    def test_danh_dau_kenh_hien_tai_la_HONG(self):
        _v, ly_do, hu = PE.quyet_dinh_cap_party(
            _anh(du_doi=False, ai_lech_instance=["tq402"], kenh_hien_tai=10))
        self.assertEqual(hu.kenh_hong, 10)
        self.assertIn("HONG", ly_do)

    def test_DU_DOI_thi_khong_dinh_toi_nhanh_nay(self):
        """Roster DU la bang chung ca party cung mot cho - khong duoc dua vao so kenh de pha."""
        _v, _l, hu = PE.quyet_dinh_cap_party(_anh(du_doi=True, ai_lech_instance=["tq402"]))
        self.assertIsNone(hu.kenh_hong)


class TestDungHinhVaDamChanOThanh(unittest.TestCase):
    """Ba phep do cu (lech map/kenh/thieu nguoi) deu XANH khi ca party cung dam chan mot cho SAI.
    Ca that party 1, 07/09: 44 PHUT dung im o Truong Sa."""

    def test_dam_chan_o_thanh_qua_han_thi_GOM(self):
        viec, ly_do, _hu = PE.quyet_dinh_cap_party(
            _anh(ca_party_o_thanh=True, o_thanh_tu=1000.0 - 999, maps={12001: ["a1"]}))
        self.assertEqual(viec, PE.DP_GOM)
        self.assertIn("dam chan o THANH", ly_do)

    def test_chua_qua_han_thi_chua_pha_the(self):
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(ca_party_o_thanh=True, o_thanh_tu=1000.0 - 5, maps={12001: ["a1"]}))
        self.assertEqual(viec, PE.DP_LAM)

    def test_CHUA_DU_DOI_thi_dung_o_thanh_la_DUNG(self):
        """Party chua du doi thi dung o thanh chinh la viec dung - do la diem gom cua vong reform.
        Bump luc do = abort chinh vong gom vua ra lenh (party 1, 08/09: mat 3 phut moi thoat)."""
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(du_doi=False, ca_party_o_thanh=True, o_thanh_tu=1000.0 - 999,
                 maps={12001: ["a1"]}))
        self.assertNotEqual(viec, PE.DP_GOM)

    def test_pha_event_KHONG_xet_dam_chan_o_thanh(self):
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(pha=PE.PHA_EVENT, ca_party_o_thanh=True, o_thanh_tu=1000.0 - 999))
        self.assertEqual(viec, PE.DP_LAM)

    def test_acc_dung_hinh_ngoai_DG_thi_GOM(self):
        viec, ly_do, hu = PE.quyet_dinh_cap_party(_anh(acc_dung_hinh=["a3"]))
        self.assertEqual(viec, PE.DP_GOM)
        self.assertIn("DUNG HINH", ly_do)
        self.assertTrue(hu.xoa_nhip_acc)

    def test_acc_dung_hinh_TRONG_DG_thi_DONG_BO(self):
        """Trong DG dung hinh thi DONG BO TAI CHO - tu DG ra thanh la loi ca party ra khoi DG."""
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(pha=PE.PHA_DG, acc_dung_hinh=["a3"], du_doi=False))
        self.assertEqual(viec, PE.DP_DONG_BO)

    def test_DG_party_DU_va_CUNG_KENH_thi_KHONG_resync(self):
        """`resync_gen` chi lam duoc mot viec: bat moi member roi doi roi moi lai - party DU +
        cung kenh thi do la DAP DOI DANG LANH. Chinh no lam leader "moi 2198s chua du party
        (2/4)" dem 10->11/09."""
        viec, _l, _hu = PE.quyet_dinh_cap_party(
            _anh(pha=PE.PHA_DG, acc_dung_hinh=["a3"], du_doi=True, kenhs={1}))
        self.assertEqual(viec, PE.DP_LAM, "party DU + cung kenh ma van resync = dap doi dang lanh")


class TestNguoiKeo(unittest.TestCase):
    """Di ra bai train bat buoc teleport, ma teleport phai ROI DOI truoc - hai acc cung di la
    party tan, nen phai giao cho DUNG MOT nguoi."""

    def test_dang_gom_thi_AI_CUNG_duoc_di(self):
        for _anh_gom in (_anh(acc_dung_hinh=["a3"]),                       # ngoai DG -> GOM
                         _anh(pha=PE.PHA_DG, acc_dung_hinh=["a3"],         # trong DG -> DONG_BO
                              du_doi=False)):
            viec, _l, hu = PE.quyet_dinh_cap_party(_anh_gom)
            self.assertIn(viec, (PE.DP_GOM, PE.DP_DONG_BO))
            self.assertEqual(hu.nguoi_keo, "*")

    def test_binh_thuong_thi_CHI_leader(self):
        _v, _l, hu = PE.quyet_dinh_cap_party(_anh(viec_di_train=PE.DP_DI_TRAIN))
        self.assertEqual(hu.nguoi_keo, "a1")

    def test_leader_khong_con_chay_thi_giao_cho_tat_ca(self):
        """Khong de ca party dung cho mot acc khong con chay (L0)."""
        _v, _l, hu = PE.quyet_dinh_cap_party(
            _anh(viec_di_train=PE.DP_DI_TRAIN, co_leader_dang_song=False))
        self.assertEqual(hu.nguoi_keo, "*")


class TestHamPhaiTHUAN(unittest.TestCase):
    def test_khong_doc_dong_ho_khong_khoa_khong_log(self):
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def quyet_dinh_cap_party(")
        self.assertGreater(i, 0)
        than = src[i:]
        ma = "\n".join(l for l in than.split("\n") if not l.strip().startswith("#"))
        for cam in ("time.time()", "with st[", "log.", "account_clients"):
            self.assertNotIn(cam, ma, "ham quyet dinh phai THUAN - khong duoc co %r" % cam)

    def test_moi_thay_doi_trang_thai_deu_di_ra_bang_HieuUng(self):
        hu = PE.HieuUng()
        for truong in ("doi_pha_train", "reset_joined", "kenh_hong", "rut_reform", "dang_gom",
                       "nguoi_keo", "chot_tang_gom", "chot_2k_xong", "xoa_nhip_acc"):
            self.assertTrue(hasattr(hu, truong), "thieu hieu ung %r" % truong)

    def test_dong_ho_lech_di_ra_bang_HieuUng(self):
        """Ham thuan khong giu state - moc thoi gian vao bang anh, ra bang hieu ung."""
        _v, _l, hu = PE.quyet_dinh_cap_party(
            _anh(maps={1: ["a"], 2: ["b"]}, du_doi=False, lech_tu=None, bay_gio=777.0))
        self.assertEqual(hu.lech_tu, 777.0, "bat dau lech -> phai bam moc")


if __name__ == "__main__":
    unittest.main()


class TestEngineMoiTuQuyet_KhongGoiDieuPhoi(unittest.TestCase):
    """User 21/09: "xoa dieu phoi ko dung o engine moi thoi, engine cu van dung".

    Engine moi chay THANG ba buoc trong luong cua chinh party:
        `_chup_anh_cap_party` -> `quyet_dinh_cap_party` (THUAN) -> `_thi_hanh_hieu_ung`
    Engine CU van di duong cu (`_dieu_phoi_quyet`), va ca hai dung CHUNG mot bo luat nen khong co
    ban thu hai de ma lech.
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        i = self.src.find("def _dieu_phoi_quyet_engine_moi(")
        self.assertGreater(i, 0)
        self.than = self.src[i:self.src.find("\ndef ", i + 10)]

    def test_KHONG_goi_dieu_phoi_cua_engine_cu(self):
        ma = "\n".join(l for l in self.than.split("\n") if not l.strip().startswith("#"))
        self.assertNotIn("_dieu_phoi_quyet(", ma,
                         "engine moi van di qua dieu phoi cu -> xoa dieu phoi la gay engine moi")

    def test_tu_chay_ba_buoc(self):
        for buoc in ("_chup_anh_cap_party(", "party_engine.quyet_dinh_cap_party(",
                     "_thi_hanh_hieu_ung("):
            self.assertIn(buoc, self.than, "thieu buoc %r" % buoc)

    def test_ENGINE_CU_van_giu_duong_cu(self):
        """Khong duoc vi don engine moi ma cat duong cua engine cu."""
        self.assertIn("def _dieu_phoi_quyet(", self.src)
        i = self.src.find("def _dieu_phoi_loop()")
        self.assertGreater(i, 0, "mat vong dieu phoi cua engine cu")
        self.assertIn("_dieu_phoi_quyet(pidx, st, song", self.src[i:i + 3000],
                      "vong dieu phoi cu khong con goi quyet dinh")

    def test_HAI_duong_dung_CHUNG_mot_bo_luat(self):
        """Hai ban luat = som muon lech nhau - do chinh la benh dang chua."""
        self.assertEqual(self.src.count("party_engine.quyet_dinh_cap_party("), 2,
                         "phai dung dung 2 cho goi (engine cu + engine moi), cung mot ham")
