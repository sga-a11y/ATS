"""LUAT TOI THUONG (L0): THIEU DOI thi DUNG viec chinh - va lenh do phai co NGUOI THI HANH.

`documents/RULE_DIEU_PHOI.md` L0: *du party roi lam gi thi lam; party hong thi phai gom lai BANG
DUOC*. Thieu du mot nguoi thi viec chinh dung het.

Dieu phoi CO ra lenh - no in dung su that moi nhip:

    14:27:40 [party 22] DIEU PHOI gen 19: viec=moi - cung map/kenh nhung DOI chua du
                                          (gclm01=0 gclm02=0 gclm03=0 gclm04=0 gclm05=0)

nhung KHONG AI THI HANH: `grep '["viec"]'` chi thay `VIEC_GOM` duoc doc, `VIEC_MOI` thi khong cho
nao. Lenh roi vao hu khong, con acc cu lam viec cua no.

Ca that 07/09 party 23 - 32 PHUT (13:56:17 -> 14:28), user: "rule toi thuong phai du pt cua t dau
roi":

    4 member: (member) CHO ca party xong daily (4/5, reconnecting=0)...
    leader  : BATTLE ACK g=18 / BO CHAY (flee_mode)      <- dang danh MOT MINH

`flee_mode = True` la cach dung: khong danh nua, gap quai thi chay. KHONG dung `stop`/`close` -
acc van phai song de nhan loi moi va di gom (L0 chi cho ngung gom vi ba ly do: het gio khach quan,
user Stop, acc da tat han).
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestLenhCoNguoiThiHanh(unittest.TestCase):
    def test_VIEC_MOI_duoc_DOC_o_vong_thi_hanh(self):
        s = _src()
        doc = [d for d in s.splitlines()
               if "VIEC_MOI" in d and ("== VIEC_MOI" in d or "in (VIEC_MOI" in d)]
        self.assertTrue(doc, "khong cho nao doc VIEC_MOI -> lenh roi vao hu khong")

    def test_moi_lenh_dieu_phoi_deu_co_cho_doc(self):
        """Neo chung: lenh nao dat ra ma khong ai doc thi som muon cung thanh ca p23."""
        s = _src()
        for ten in ("VIEC_GOM", "VIEC_MOI", "VIEC_DONG_BO"):
            # doc truc tiep (`kh["viec"] == VIEC_X`) HOAC qua bien trung gian (`_viec == VIEC_X`)
            doc = [d for d in s.splitlines()
                   if ten in d and (("== " + ten) in d or ("in (" + ten) in d
                                    or (", " + ten) in d)]
            self.assertTrue(doc, "%s khong duoc thi hanh o dau ca" % ten)


class TestDungViecKhiThieuDoi(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("L0: DIEU PHOI ra lenh")
        self.assertGreater(i, 0, "chua thi hanh L0")
        self.khoi = s[max(0, i - 1400):i + 3400]   # comment dai - phai lay du toi phan code

    def test_bat_flee_mode(self):
        self.assertIn("c.flee_mode = True", self.khoi)

    def test_KHONG_tat_acc(self):
        """Tat acc = het duong gom lai. L0 chi cho ngung gom vi het gio / user Stop / acc tat han."""
        for cam in ("c.close()", "stop_party(", "_quit()"):
            self.assertNotIn(cam, self.khoi, cam)

    def test_dung_chay_long_vong_khi_o_DG(self):
        self.assertIn("stop_run_around()", self.khoi)

    def test_KHONG_cat_ngang_tran_dang_danh(self):
        """Bo giua tran la mat luot + co the chet. Doi het tran roi dung."""
        self.assertIn("not c.in_combat()", self.khoi)

    def test_MO_CONG_nhan_loi_moi(self):
        """`party_invite_ready` chi bat o BA nhanh cu the (xong login chores / xong reform / vao map
        40NPC). Member ABORT giua chung thi khong bao gio toi do -> co ket False VINH VIEN va no GIU
        loi moi thay vi accept.

        Ca that 07/09 party 10 (14 phut):
            [luuhai] Chua san sang vao party -> GIU loi moi entity=..., se accept sau viec vat
            [luuhai] (member) ABORT di duong reform: reform_gen 2 -> 3 (acc khac bump)
            [party 10] DIEU PHOI: DOI chua du (luu001=0 ... luu005=0) -> LAP LAI PARTY
        Dieu phoi ra lenh, leader moi that, member thi "de sau viec vat". Thieu doi thi KHONG CON
        viec vat nao quan trong hon (L0)."""
        self.assertIn("c.set_party_invite_ready(True)", self.khoi,
                      "member van GIU loi moi trong khi dieu phoi dang bao lap party")

    def test_leader_KHONG_tu_mo_cong_cho_minh(self):
        """Cong nay la cua MEMBER (nhan loi moi). Leader la nguoi MOI."""
        i = self.khoi.find("c.set_party_invite_ready(True)")
        self.assertGreater(i, 0)
        self.assertIn("not is_leader", self.khoi[max(0, i - 300):i])

    def test_mo_cong_KHONG_phu_thuoc_dang_danh_tran(self):
        """Vao doi la `C:013-008` - tran KHONG chan (khac teleport / doi kenh / qua cong).

        Ca that 08/09 party 6 (user: "p6 ko gom duoc pt, cung kenh cung map roi"): diem safe cua
        map train 21814 hoc SAI nen acc bi keo tran lien tuc ngay tai safe (canh bao "SAFE BI QUAI
        DANH: 8 tran trong 1 phut" keu 32 lan). `in_combat()` gan nhu luon True -> ca cum L0 nam
        sau `not c.in_combat()` khong bao gio chay -> `party_invite_ready` khong bao gio bat ->
        leader moi mai, roster ca 5 acc = 0 suot hon mot tieng."""
        i = self.khoi.find("c.set_party_invite_ready(True)")
        j = self.khoi.find("not c.in_combat()")
        self.assertGreater(j, 0)
        self.assertLess(i, j, "cho mo cong nam SAU cua `not in_combat` -> dang danh tran thi "
                              "khong bao gio nhan duoc loi moi")

    def test_du_doi_lai_thi_LAM_TIEP(self):
        self.assertIn("_bat_danh_neu_du_party()", self.khoi)
        self.assertIn("L0: dieu phoi het lenh gom", self.khoi)

    def test_chi_log_MOT_lan_moi_dot(self):
        """Vong keepalive chay moi vai giay - log moi vong la ngap party.log."""
        self.assertIn("_l0_dung_viec", self.khoi)


class TestLenhDieuPhoiLaTUYET_DOI(unittest.TestCase):
    """User chot 07/09: "lenh cua dieu phoi la phai theo tuyet doi, acc tu cho phep dung yen tu
    danh -> may thay code ngu ko".

    Ban dau chi chan `VIEC_MOI` (doi chua du). Nhung `VIEC_GOM` (lech map) va `VIEC_DONG_BO` (lech
    kenh) cung la "party dang KHONG on, phai gom" - acc danh trong luc do la khong theo lenh.
    Ca that p1 07/09: leader ve Giang Lang, 4 member dung o map khac va van danh."""

    def setUp(self):
        s = _src()
        i = s.find("_viec_now = (_ke_hoach(st) or {}).get(\"viec\")")
        self.assertGreater(i, 0, "khong doc lenh dieu phoi truoc khi tu quyet danh")
        self.khoi = s[i:i + 1200]

    def test_chan_ca_BA_lenh_gom(self):
        for m in ("VIEC_MOI", "VIEC_GOM", "VIEC_DONG_BO"):
            self.assertIn(m, self.khoi, m)

    def test_het_lenh_thi_moi_lam_tiep(self):
        s = _src()
        i = s.find("L0: dieu phoi het lenh gom")
        self.assertGreater(i, 0)
        khoi = s[max(0, i - 400):i + 300]
        for m in ("VIEC_MOI", "VIEC_GOM", "VIEC_DONG_BO"):
            self.assertIn(m, khoi, "nha lenh khong doi xung -> acc ket o trang thai dung viec")


class TestKhongPhaCacLuatKhac(unittest.TestCase):
    def test_van_giu_nhanh_tang_gom_2K(self):
        s = _src()
        self.assertIn('(_ke_hoach(st) or {}).get("tang_gom")', s)

    def test_van_giu_nhanh_kenh_dich(self):
        s = _src()
        self.assertIn('_kd = st.get("kenh_dich")', s)


if __name__ == "__main__":
    unittest.main()
