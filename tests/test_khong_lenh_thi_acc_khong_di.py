"""ROI DOI DE TELEPORT = PHA PARTY. Chi lam khi DIEU PHOI giao viec di duong.

User 11/09: "dieu phoi ko ra lenh thi acc ko quyet dinh gi ca" -> "deo hieu sao code mai ko xong vu
nay, cu thich de acc quyet dinh co" -> "xoa acc tu quyet, dieu phoi la nguoi quyet dinh, va va cai
lon".

VI SAO SUA MAI KHONG XONG: moi lan chi bit MOT duong goi, lan sau acc tu di bang duong khac.
Trong MOT ngay 11/09 da phai bit bon lan:
    party 3   member het han cho -> tu lap duong (`_chot_thanh_tap_ket(False)`)
    party 6   member tu chay smart route ra bai
    party 6   member sai map -> tu goi `_do_reform` moi 5 giay
    party 2/7 member tu ve thanh giua luc leader keo
Ra soat cho goi la sai cach: `run_party_digioi.py` co HON BON MUOI cho goi hanh dong cap party
(`_do_reform`, `stop_party`, `leave_party`, `pre_route_town_hop`, `switch_channel`...).

DIEM NGHEN DUY NHAT: moi duong di deu ket thuc bang teleport, va client CHAN teleport khi con
trong doi nen phai `leave_party()` truoc. Chinh chu thich trong `go_to_town` da ghi: "Roi doi o DAY
chu khong o go_to_town: moi duong tele deu di qua ham nay nen khong sot". Nen luat dat o DO - mot
cho, phu het moi duong.

LENH: `nguoi_keo(pidx)` do dieu phoi chot moi nhip.
    ten mot acc  -> chi acc do duoc di duong (leader keo, ca party bi keo theo, doi khong tan)
    "*"          -> ai cung duoc: party khong co bot-leader, HOAC dang GOM (luc do ca party deu
                    phai tu ve diem hen, va roi doi la dung vi doi dang hong nen moi phai gom)
    chua chot    -> KHONG AI duoc pha party
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


def _than_teleport():
    """`teleport()` - noi DUY NHAT acc tu roi doi de bay. `go_to_town` goi vao day, va chu thich
    trong code ghi ro: "Roi doi o DAY chu khong o go_to_town: moi duong tele deu di qua ham nay
    nen khong sot"."""
    src = _doc(os.path.join("bot", "client.py"))
    i = src.find("    def teleport(self, city_id")
    assert i > 0
    j = src.find("\n    def ", i + 10)
    return _ma(src[i:j])


class TestLuatDatODiemNghen(unittest.TestCase):
    def setUp(self):
        self.than = _than_teleport()

    def test_cua_nam_ngay_o_cho_ROI_DOI(self):
        i_lenh = self.than.find("nguoi_keo(self.party_idx)")
        i_roi = self.than.find("self.leave_party()")
        self.assertGreater(i_lenh, 0, "diem nghen khong doc lenh dieu phoi -> acc lai tu pha party")
        self.assertGreater(i_roi, 0)
        self.assertLess(i_lenh, i_roi, "phai kiem lenh TRUOC khi roi doi")

    def test_khong_duoc_giao_thi_KHONG_roi_doi(self):
        i = self.than.find("nguoi_keo(self.party_idx)")
        khoi = self.than[i:i + 500]
        self.assertIn("return False", khoi)

    def test_chi_ap_khi_DANG_o_trong_doi(self):
        """Khong o doi thi khong co gi de pha - di binh thuong."""
        i = self.than.find("nguoi_keo(self.party_idx)")
        truoc = self.than[max(0, i - 300):i]
        self.assertIn("if self.party_members:", truoc)

    def test_KHONG_rai_cua_o_cho_khac(self):
        """Rai cua tung duong chinh la cach da that bai bon lan trong mot ngay."""
        src = _doc(os.path.join("bot", "client.py"))
        self.assertNotIn("_chan_tu_di_route", src)


class TestDieuPhoiLaNoiRaLENH(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_dieu_phoi_chot_nguoi_keo_moi_nhip(self):
        self.assertIn("dat_nguoi_keo(pidx,", self.src)

    def test_chot_ngay_canh_cac_lenh_cap_party_khac(self):
        """Mot cho quyet, mot nhip (L1)."""
        i_gom = self.src.find("dat_party_dang_gom(pidx, viec in")
        i_keo = self.src.find("dat_nguoi_keo(pidx,")
        self.assertGreater(i_gom, 0)
        self.assertLess(abs(i_keo - i_gom), 1500)

    def test_dang_GOM_thi_giao_cho_tat_ca(self):
        i = self.src.find("dat_nguoi_keo(pidx,")
        khoi = self.src[max(0, i - 1200):i]
        self.assertIn("viec in (VIEC_GOM, VIEC_DONG_BO)", khoi)

    def test_nguoi_keo_tat_thi_giao_lai(self):
        """L0: khong de ca party cho mot acc khong con chay."""
        i = self.src.find("dat_nguoi_keo(pidx,")
        self.assertIn("khong con chay", self.src[max(0, i - 900):i])


class TestChayThatPhepQuyet(unittest.TestCase):
    """Chay that bieu thuc quyet dinh, khong chi doc chu."""

    @staticmethod
    def _duoc_di(keo, minh):
        return keo in ("*", minh)

    def test_chua_ra_lenh_thi_khong_ai_di(self):
        self.assertFalse(self._duoc_di(None, "a1"))

    def test_duoc_giao_thi_di(self):
        self.assertTrue(self._duoc_di("a1", "a1"))

    def test_nguoi_khac_duoc_giao_thi_minh_dung_yen(self):
        self.assertFalse(self._duoc_di("a1", "a2"))

    def test_sao_thi_ai_cung_di(self):
        self.assertTrue(self._duoc_di("*", "a2"))


class TestCoLenhVanHanh(unittest.TestCase):
    def setUp(self):
        C.dat_nguoi_keo(7, None)

    def tearDown(self):
        C.dat_nguoi_keo(7, None)

    def test_dat_va_doc_lai_duoc(self):
        C.dat_nguoi_keo(7, "a1")
        self.assertEqual(C.nguoi_keo(7), "a1")

    def test_xoa_lenh(self):
        C.dat_nguoi_keo(7, "a1")
        C.dat_nguoi_keo(7, None)
        self.assertIsNone(C.nguoi_keo(7))

    def test_party_khac_khong_anh_huong(self):
        C.dat_nguoi_keo(7, "a1")
        self.assertIsNone(C.nguoi_keo(8))


class TestMemberSaiMapKhongCoXuLyRieng(unittest.TestCase):
    """Sai map la TRANG THAI, khong phai mot viec. Vong "cho leader keo" da bi XOA 11/09 - no la
    vong acc tu chon buoc vao va trong do no diec voi moi lenh cap party (ttmuoi nam trong do MOT
    TIENG RUOI, 10:31:36 -> 11:59, khong nghe thay lenh gom luc 11:58:26)."""

    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_khong_con_vong_cho_leader_keo(self):
        # Neo vao dong cua MEMBER (nhanh leader sai map dung chuoi gan giong).
        i = self.src.find("(member) SAI MAP (o %s, can %s)")
        self.assertGreater(i, 0, "mat nhanh member sai map")
        khoi = _ma(self.src[i:i + 1500])
        self.assertNotIn("while c.running", khoi, "lai dung them mot vong acc tu cho")
        self.assertNotIn("_do_reform", khoi, "member lai tu goi reform")

    def test_ra_vong_chinh_de_nghe_lenh(self):
        # Co HAI dong "(member) SAI MAP": mot cho ca KHONG dung duoc duong (route-less), mot cho
        # ca thuong. Neo vao dong thu hai bang chinh cau chu cua no.
        i = self.src.find("(member) SAI MAP (o %s, can %s) -> KHONG tu xu ly")
        self.assertGreater(i, 0)
        self.assertIn("ra vong ", self.src[i:i + 600])
        self.assertIn("nghe lenh dieu phoi", self.src[i:i + 600])


class TestAccKhongTuTatCaParty(unittest.TestCase):
    """Tat ca party la quyet dinh NANG NHAT trong file, va no tung do MOT ACC tu dua ra dua tren
    tinh trang cua rieng no.

    Ca that (APK, user 11/09 - "den doan chay trainmap thi bao loi gi do va tat acc luon"):
        16:23:00 [acc2] (member) route-less + SAI MAP (o 12001, can 21864) -> TAT CA PARTY
        16:23:00 [acc2] STOP: route-less train + member sai map (caller=...stop_party)
    Map 21864 khong co `route` cung trong train_maps.json, va smart route thi KHONG AI dung cho
    member -> `route_available` rut gon con dung `has_leader`. Party khong dat bot-leader la dinh;
    party co leader thi khong bao gio -> dung kieu "khong phai luc nao cung bi".

    Sai map la TRANG THAI: dieu phoi doc map ca party moi 2 giay va ra lenh gom. Con tat party thi
    user phai vao bat lai bang tay.
    """

    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_chi_GUI_duoc_tat_party(self):
        """`stop_party` chi con MOT noi goi: nut Stop tren GUI."""
        _goi = [d.strip() for d in _ma(self.src).split(chr(10))
                if "stop_party(pidx" in d and not d.lstrip().startswith("def ")]
        self.assertEqual(_goi, [], "con acc tu tat ca party theo tinh trang cua rieng no")

    def test_member_khong_co_duong_thi_KHONG_tat_party(self):
        i = self.src.find("(member) SAI MAP (o %s, can %s) va khong dung duoc duong")
        self.assertGreater(i, 0, "mat nhanh route-less cua member")
        self.assertIn("KHONG tat party", self.src[i:i + 400])

    def test_leader_khong_co_duong_thi_KHONG_tat_party(self):
        i = self.src.find("(LEADER) SAI MAP (o %s, can %s) va khong dung duoc duong")
        self.assertGreater(i, 0, "mat nhanh route-less cua leader")
        self.assertIn("KHONG tat party", self.src[i:i + 400])


class TestKhongCoLeaderThiMemberTuDungDuocDuong(unittest.TestCase):
    """Party KHONG dat bot-leader -> khong ai keo member ca, nen no phai TU dung duoc duong.

    Ban cu chi `build_smart_route` khi `is_leader`, nen member cua party khong-leader luon bi coi
    la "route-less" du smart router thua suc dung duong (map 21864).
    """

    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_member_party_khong_leader_van_dung_duong(self):
        i = self.src.find("smart_route = None")
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 1600]
        self.assertIn("if is_leader or not has_leader:", khoi,
                      "member cua party khong-leader khong dung duoc duong -> bi coi la route-less")

    def test_van_khong_dung_duong_ho_khi_DA_co_leader(self):
        """Co leader thi leader keo - member tu dung duong nua la hai nguoi cung di, party tan."""
        i = self.src.find("if is_leader or not has_leader:")
        self.assertGreater(i, 0)
        self.assertIn("build_smart_route", self.src[i:i + 400])


if __name__ == "__main__":
    unittest.main()
