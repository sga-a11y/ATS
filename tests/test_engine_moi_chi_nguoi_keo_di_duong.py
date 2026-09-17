# -*- coding: utf-8 -*-
"""CHI NGUOI KEO duoc di duong - engine moi phai nghe `dat_nguoi_keo` cua dieu phoi.

Di ra bai train bat buoc TELEPORT, ma teleport phai ROI DOI truoc (client game chan thang o
`UITeleport.CheckTeleport()`). Nen viec di duong phai giao cho DUNG MOT nguoi; hai acc cung di la
party tan. `client.teleport` co san cua chan nay, NHUNG no nam trong `if self.party_members:` -
leader roi doi TRUOC khi tele thi doi tan, member khong con `party_members` nen cua het hieu luc.

Ca that 17/09 party 44, trong DUNG MOT GIAY (00:02:48), ca 5 acc deu duoc giao `ve_map` toi map
train 15457 trong khi dieu phoi giao viec di duong cho MOT minh 'tp601':
    tpmot -> pre-route hop 12061   tphai -> hop 12061   tpnam -> hop 12061
    tpba  -> hop 12001             tpbon -> hop 12001
(`pre_route_town_hop` boc ngau nhien 50-50 Trac Quan / Nghiep Thanh tren TUNG acc.)
Party vua du 4/4 luc 00:02:48 -> 00:02:49 tan, roi moi dua mot thanh; user: "p44, dua o Nghiep
thanh dua o Trac quan ma lai thay deu co danh dau dang trong pt".
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E


def _a(u, **kw):
    kw.setdefault("map_id", 12001)
    kw.setdefault("kenh", 1)
    return E.AnhAcc(u, **kw)


def _anh(accs, keo="*", thanh=12001):
    a = E.AnhParty(43, accs, can_bao_nhieu=len(accs) - 1, co_spot=True)
    a.dp_viec = E.DP_DI_TRAIN
    a.nguoi_keo = keo
    a.thanh_dich = thanh
    return a


class TestChiNguoiKeoDuocDiDuong(unittest.TestCase):
    def test_chi_nguoi_keo_nhan_VE_MAP(self):
        """Member DA o thanh tap ket -> dung yen cho leader keo qua cong."""
        accs = [_a("l", la_leader=True, so_member=4), _a("m1"), _a("m2")]
        v = E.quyet_dinh(_anh(accs, keo="l", thanh=12001))
        self.assertEqual(v["l"], E.VIEC_VE_MAP)
        self.assertEqual(v["m1"], E.VIEC_NGHI, "member tu di duong -> tu teleport -> party tan")
        self.assertEqual(v["m2"], E.VIEC_NGHI)

    def test_member_CHUA_toi_thanh_tap_ket_thi_VAN_PHAI_VE(self):
        """"Khong duoc lap duong" KHONG phai "dung im": flow cu van bat member ve thanh tap ket
        (reform -> `go_to_town(route_plan["city"])`), roi leader moi keo ca doi qua cong.

        Ca that 17/09 p45 09:26:55 - leader DA toi Tho Xuan (15021, thanh cua route) ma bon member
        van dung Hoi Ke (18021), roster 0/4 mai (nen `so_member=0` o day).

        DU DOI thi nguoc lai: member DI THEO leader qua cong, khong ve thanh - xem
        `TestMemberDiTheoLeaderKhongVeThanh`."""
        accs = [_a("l", la_leader=True, so_member=0, map_id=15021),
                _a("m1", map_id=18021), _a("m2", map_id=18021)]
        v = E.quyet_dinh(_anh(accs, keo="l", thanh=15021))
        self.assertEqual(v["l"], E.VIEC_VE_MAP)
        self.assertEqual(v["m1"], E.VIEC_VE_THANH, "member ket o thanh cu, party khong bao gio du")
        self.assertEqual(v["m2"], E.VIEC_VE_THANH)

    def test_sao_thi_CA_PARTY_duoc_di(self):
        """"*" = dang GOM (doi da hong nen ai cung phai tu ve diem hen) hoac party khong co
        bot-leader. Khoa lai luc nay la ca party dung im - dung cai L0 cam."""
        accs = [_a("l", la_leader=True, so_member=4), _a("m1")]
        v = E.quyet_dinh(_anh(accs, keo="*"))
        self.assertTrue(all(x == E.VIEC_VE_MAP for x in v.values()), v)

    def test_khong_doc_duoc_thi_KHONG_khoa_ai(self):
        """L0: khong bao gio de party dung im vi mot phep do loi."""
        accs = [_a("l", la_leader=True, so_member=4), _a("m1")]
        v = E.quyet_dinh(_anh(accs, keo=""))
        self.assertTrue(all(x == E.VIEC_VE_MAP for x in v.values()), v)


class TestNguoiKeoCungPhaiVeDiemGom(unittest.TestCase):
    """Flow cu bat MOI acc ve `_target_city` truoc roi moi di tiep:
        _target_city = _gc if _nghiep_fallback_active() else fc

    Cho nguoi keo di thang thi no bo party lai: leader DA o thanh cua route (no mo duoc), con
    member chua mo nen dung o thanh gom - leader cu the chay ra bai mot minh.
    Ca that 17/09 party 45 (nhanh "thanh chua mo" da chay dung ma van hong):
        10:00:01 ENGINE: thanh 15021 CHUA MO voi [cd702..cd705] -> CA PARTY gom o thanh 18021
        10:00:24 chdumot@15021(L) chduhai@18021 chduba@18021 chdubon@18021 chdunam@18021
    """

    def test_leader_chua_ve_diem_gom_thi_VE_THANH(self):
        """CHUA DU DOI (so_member=0) ma leader lac khoi diem gom -> phai ve."""
        accs = [_a("l", la_leader=True, so_member=0, map_id=15021),
                _a("m1", map_id=18021), _a("m2", map_id=18021)]
        v = E.quyet_dinh(_anh(accs, keo="l", thanh=18021))
        self.assertEqual(v["l"], E.VIEC_VE_THANH, "leader bo party lai, chay ra bai mot minh")

    def test_DU_DOI_roi_thi_nguoi_keo_duoc_DI_du_da_roi_diem_gom(self):
        """Du roi thi nguoi keo PHAI duoc di, va no di la roi diem gom. Ep ve luc do thanh vong
        "du doi -> di -> bi keo ve -> du doi -> ..." va party KHONG BAO GIO ra toi bai.

        Ca that 17/09 party 42 (user: "di ve thanh tap trung dung roi, nhung sau do ko di ra bai
        train"):
            18:46:31 gen 38: du doi, cung map/kenh -> DI TRAIN map 26811 (con o [23000])
            18:46:33 gen 39: con lech map [23000, 23001]   <- leader vua di, bi keo ve
            18:46:34 gen 40: cung map/kenh nhung DOI chua du
        """
        accs = [_a("l", la_leader=True, so_member=2, map_id=23001),
                _a("m1", map_id=23000), _a("m2", map_id=23000)]
        v = E.quyet_dinh(_anh(accs, keo="l", thanh=23000))
        self.assertEqual(v["l"], E.VIEC_VE_MAP, "keo leader ve diem gom -> khong bao gio ra bai")

    def test_ve_du_roi_thi_nguoi_keo_moi_DI(self):
        accs = [_a("l", la_leader=True, so_member=4, map_id=18021),
                _a("m1", map_id=18021), _a("m2", map_id=18021)]
        v = E.quyet_dinh(_anh(accs, keo="l", thanh=18021))
        self.assertEqual(v["l"], E.VIEC_VE_MAP)
        self.assertEqual(v["m1"], E.VIEC_NGHI)


class TestMemberDiTheoLeaderKhongVeThanh(unittest.TestCase):
    """DU DOI roi thi member DI THEO LEADER (game keo qua cong) -> DUNG YEN.

    Bat no ve thanh luc nay la cat ngang chuyen di: ca party dang tren duong ra bai, member thi
    teleport nguoc ve thanh - ma teleport con ROI DOI.

    Ca that 17/09 party 56 (user: "sao vua danh vua doi tele ve thanh la sao"):
        19:43:43 gen 20: du doi, cung map/kenh -> DI TRAIN map 11801 (con o [11539])  roster 4/4
        19:43:54 ENGINE: tik907..tik910 -> ve_thanh    <- dang di giua duong
        19:43:58 gen 21: ... (con o [11532])           <- van dang di
    """

    def test_dang_di_giua_duong_thi_member_DUNG_YEN(self):
        accs = [_a("l", la_leader=True, so_member=4, map_id=11532),
                _a("m1", map_id=11532), _a("m2", map_id=11532)]
        v = E.quyet_dinh(_anh(accs, keo="l", thanh=11011))
        self.assertEqual(v["l"], E.VIEC_VE_MAP)
        for u in ("m1", "m2"):
            self.assertEqual(v[u], E.VIEC_NGHI,
                             "member bi keo ve thanh giua chuyen di -> teleport + ROI DOI")

    def test_CHUA_DU_DOI_thi_van_ve_diem_gom(self):
        accs = [_a("l", la_leader=True, so_member=0, map_id=11011),
                _a("m1", map_id=11532)]
        v = E.quyet_dinh(_anh(accs, keo="l", thanh=11011))
        self.assertEqual(v["m1"], E.VIEC_VE_THANH)


if __name__ == "__main__":
    unittest.main()
