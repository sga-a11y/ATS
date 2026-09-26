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
        """Mot cho quyet, mot nhip (L1). Ca hai gio nam trong `_thi_hanh_hieu_ung`."""
        i_gom = self.src.find("dat_party_dang_gom(pidx, hu.dang_gom)")
        i_keo = self.src.find("dat_nguoi_keo(pidx,")
        self.assertGreater(i_gom, 0)
        self.assertLess(abs(i_keo - i_gom), 1500)

    def test_dang_GOM_thi_giao_cho_tat_ca(self):
        """Luat gio o `party_engine.quyet_dinh_cap_party`: dang GOM/DONG_BO -> `nguoi_keo = "*"`
        (ca party tu ve diem hen), con lai thi CHI leader duoc di."""
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            pe = fh.read()
        i = pe.find("if viec in (DP_GOM, DP_DONG_BO):")
        self.assertGreater(i, 0, "mat luat 'dang gom thi ai cung duoc di'")
        self.assertIn('hu.nguoi_keo = "*"', pe[i:i + 300])

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
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        client = mock.Mock(current_map=100, _pe_la_leader=False)
        client.build_smart_route.return_value = None
        self.assertFalse(E.thi_hanh(client, E.VIEC_VE_MAP, lambda: True, dich=200))
        client.close.assert_not_called()
        client.go_to_town.assert_not_called()

    def test_leader_khong_co_duong_thi_KHONG_tat_party(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot

        client = mock.Mock(current_map=100, _pe_la_leader=True)
        client.build_smart_route.return_value = None
        self.assertFalse(E.thi_hanh(client, E.VIEC_VE_MAP, lambda: True, dich=200))
        client.close.assert_not_called()
        client.follow_smart_route.assert_not_called()




if __name__ == "__main__":
    unittest.main()
