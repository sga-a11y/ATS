"""ENGINE PARTY MOI: nhip quyet dinh phai dung chuoi user chot, va KHONG duoc co vong cho.

User chot tu dau, nhac lai nhieu lan:
    "lech map thi dong bo map / lech kenh thi dong bo kenh / cung kenh cung map thi lap pt /
     du pt thi chay di train"

Diem cua engine nay la nhip quyet dinh KHONG CHAN - nen khong the sinh ra "vong cho diec lenh",
tuc ca ho loi da giet party 11 (15/09) khong con dat de moc.
Thiet ke: documents/ENGINE_PARTY_MOI.md
"""
from __future__ import annotations

import ast
import io
import os
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E


def _anh(accs, can=3, map_dich=None, co_spot=True, pha=E.PHA_TRAIN, pb=None,
         thanh_di_ngang=False, cho_ly_do="", dp_viec=None, event_xong=False):
    """Mac dinh `co_spot=True`: cac ca duoi day noi ve CHUOI GOM, khong phai ve bai quai.
    Rieng `TestPhaiCoBaiQuaiMoiDanh` thu chinh cai cua do."""
    return E.AnhParty(40, accs, can_bao_nhieu=can, map_dich=map_dich, co_spot=co_spot, pha=pha,
                      pb_doi_level=pb, thanh_di_ngang=thanh_di_ngang, cho_ly_do=cho_ly_do,
                      dp_viec=dp_viec, event_xong=event_xong)


def _a(u, **kw):
    kw.setdefault("map_id", 23851)
    kw.setdefault("kenh", 1)
    return E.AnhAcc(u, **kw)


class TestChuoiUserChot(unittest.TestCase):
    def test_lech_map_thi_DONG_BO_MAP(self):
        anh = _anh([_a("l", la_leader=True, so_member=3),
                    _a("m1"), _a("m2", map_id=23011)])
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_VE_MAP)
        self.assertEqual(v["l"], E.VIEC_NGHI, "dua dang o dung map thi dung yen cho")

    def test_lech_map_thi_KHONG_dong_bo_kenh(self):
        """User 14/09: "dang lech map thi di dong bo map di, may lay kenh lam lon gi luc do"."""
        anh = _anh([_a("l", la_leader=True, so_member=3, kenh=1),
                    _a("m1", kenh=7), _a("m2", map_id=23011, kenh=9)])
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_DOI_KENH, v.values())

    def test_cung_map_lech_kenh_thi_DONG_BO_KENH(self):
        anh = _anh([_a("l", la_leader=True, so_member=3, kenh=1),
                    _a("m1", kenh=1), _a("m2", kenh=7)])
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_DOI_KENH)
        self.assertEqual(v["m1"], E.VIEC_NGHI)

    def test_cung_map_cung_kenh_thieu_doi_thi_LAP_PARTY(self):
        anh = _anh([_a("l", la_leader=True, so_member=1), _a("m1"), _a("m2")], can=3)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)

    def test_du_doi_thi_RA_BAI_roi_DANH(self):
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1"), _a("m2")], can=3)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_RA_SPOT for x in v.values()), v)
        # da ra toi bai roi thi giu nguyen viec danh, khong bat chay lai
        anh2 = _anh([_a("l", la_leader=True, so_member=3, viec_dang_lam=E.VIEC_TRAIN),
                     _a("m1", viec_dang_lam=E.VIEC_TRAIN), _a("m2", viec_dang_lam=E.VIEC_TRAIN)],
                    can=3)
        self.assertTrue(all(x == E.VIEC_TRAIN for x in E.quyet_dinh(anh2).values()))


class TestKhongKetLuanBua(unittest.TestCase):
    def test_chua_biet_map_thi_CHUA_KET_LUAN(self):
        """`map_id=None` = chua doc duoc, KHONG phai "cung map". Doan bua o day la ca party bi keo
        di theo mot con so khong co that."""
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1", map_id=None), _a("m2")])
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_RA_SPOT, v.values())

    def test_roster_doc_cua_LEADER_khong_phai_ban_ngheo_nhat(self):
        """Ca that party 11: leader thay 3/4 nhung member con thay 1/4. Lay ban ngheo nhat thi
        engine tuong party hong va gom lai vo ich, pha dung cai party vua lap."""
        anh = _anh([_a("l", la_leader=True, so_member=3),
                    _a("m1", so_member=1), _a("m2", so_member=0)], can=3)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_RA_SPOT for x in v.values()), v)

    def test_acc_chet_khong_tinh_vao_phep_do(self):
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1"),
                    _a("m2", map_id=12001, song=False)])
        v = E.quyet_dinh(anh)
        self.assertNotIn("m2", v)
        self.assertNotIn(E.VIEC_VE_MAP, v.values())


class TestViecVatKhongBiQuayRay(unittest.TestCase):
    """User 14/09: "khi dang danh PB don va daily quest thi dieu phoi tam thoi ko quay ray".

    Va: viec vat PHAI o map khac (ban Noi Dan o Nghiep Thanh, cat tien trang, boss the gioi) nen
    dem no vao phep do la party LUC NAO cung "lech map" - dung cai lam party 11 quay vong 22 phut.
    """

    def test_acc_viec_vat_o_map_khac_KHONG_tinh_la_lech_map(self):
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1"),
                    _a("m2", map_id=12061, xong_chore=False)], can=3)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_LOGIN_CHORE)
        self.assertEqual(v["l"], E.VIEC_RA_SPOT, "party con lai van chay tiep binh thuong")

    def test_khong_giao_viec_khac_cho_acc_dang_viec_vat(self):
        anh = _anh([_a("l", la_leader=True, so_member=1, map_id=23011), _a("m1"),
                    _a("m2", map_id=12061, xong_chore=False)], can=3)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_LOGIN_CHORE)


class TestViecVatSauLoginLamCHO_XONG(unittest.TestCase):
    """User 14/09: "dang lam may cai viec vat do ko vao pt la dung... vao pt roi bi keo di luon
    thi no hong viec vat".

    Cua hoan cu (da bo 14/09) dat nguoc: no hoan VIEC VAT de di gom - ma luc moi login thi party
    LUC NAO cung dang gom, nen 96% acc mat luot PB don CA NGAY (o 1 bingo: 14/152 acc sang duoc;
    2739 lan `Boss the gioi: HOAN`, 3224 lan `Dungeon: HOAN`).
    """

    def test_chua_xong_chore_thi_lam_chore_khong_bi_keo_di(self):
        anh = _anh([_a("l", la_leader=True, so_member=3),
                    _a("m1", xong_chore=False, map_id=12061)], can=3)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m1"], E.VIEC_LOGIN_CHORE)

    def test_acc_dang_lam_chore_o_map_khac_KHONG_de_ra_lech_map(self):
        """Viec vat PHAI o map khac (ban Noi Dan o Nghiep Thanh, cat tien trang). Dem no vao phep
        do la party luc nao cung "lech map" -> gom vo tan, dung cai da giet party 11."""
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1"),
                    _a("m2", xong_chore=False, map_id=12061)], can=3)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_LOGIN_CHORE)
        self.assertNotIn(E.VIEC_VE_MAP, v.values(), "keo ca party di theo dua dang lam viec vat")


class TestKHONG_VIEC_NAO_DUOC_NHAY_QUA_LAI(unittest.TestCase):
    """CUA CHAN CHUNG cho ca ho loi da can BA LAN:

        `login_chore` <-> `viec_vat`   (15/09, 33 lan xen ke 31 lan)
        `ra_spot`     -> khong bao gio thanh `train`
        `ve_map`      <-> `viec_vat`   (16/09 party 41 - dung o Trac Quan ca ngay)
        `pb_doi_theo` <-> `viec_vat`   (16/09 party 51)

    Moi lan giao viec MOI la HUY viec dang chay. Nhay qua lai moi giay = acc khong bao gio di toi
    dau, va nhin log thi tuong engine van dang lam viec.

    Bai nay CHAY THAT nhip nhieu lan voi anh chup KHONG DOI (tru cai co nhap nhay) va doi hoi viec
    phai ON DINH - khong doc chu trong source.
    """

    def _on_dinh(self, acc_moi, so_nhip=30, **anh_kw):
        """Chay `so_nhip` nhip, moi nhip cap nhat `viec_dang_lam` roi chay lai.
        Tra ve so lan viec DOI (0 hoac 1 la on dinh; nhieu hon la dang quay vong)."""
        accs = [_a("l", la_leader=True, so_member=3, map_id=23851)] + [acc_moi]
        anh = _anh(accs, **anh_kw)
        doi = 0
        truoc = None
        for i in range(so_nhip):
            v = E.quyet_dinh(anh)
            _v = v[acc_moi.username]
            if truoc is not None and _v != truoc:
                doi += 1
            truoc = _v
            acc_moi.viec_dang_lam = _v
            # (khong con co NHAP NHAY nao de mo phong: engine TU BIET acc dang lam gi)
        return doi

    def test_ve_map_KHONG_nhay_khi_co_viec_vat_nhap_nhay(self):
        n = self._on_dinh(_a("m1", map_id=23011), can=1)
        self.assertLessEqual(n, 1, "viec doi %d lan trong 30 nhip -> dang quay vong" % n)

    def test_ra_spot_KHONG_nhay(self):
        n = self._on_dinh(_a("m1", map_id=23851), can=1)
        self.assertLessEqual(n, 1, "viec doi %d lan -> quay vong" % n)

    def test_pb_doi_theo_KHONG_nhay(self):
        n = self._on_dinh(_a("m1", map_id=23851), can=1, pb=50)
        self.assertLessEqual(n, 1, "viec doi %d lan -> quay vong" % n)

    def test_di_gioi_KHONG_nhay(self):
        n = self._on_dinh(_a("m1", map_id=21011, con_gio_dg=True), can=1, pha=E.PHA_DG)
        self.assertLessEqual(n, 1, "viec doi %d lan -> quay vong" % n)

    def test_login_chore_KHONG_nhay(self):
        n = self._on_dinh(_a("m1", map_id=23011, xong_chore=False), can=1)
        self.assertLessEqual(n, 1, "viec doi %d lan -> quay vong" % n)


class TestENGINE_TU_BIET_KHONG_HOI_ACC(unittest.TestCase):
    """Engine la MOT luong nam ca 5 client va CHINH NO giao viec -> no BIET acc dang lam gi.

    Ban dau `chup()` con doc `c.dang_lam_viec_vat()` - co do CLIENT tu gan, NHAP NHAY theo tung
    pha `task_report`. Lay no de quyet dinh thi: nhip ra `viec_vat`, nhip sau ra lai viec cu, moi
    lan giao la HUY viec dang chay -> acc KHONG BAO GIO di toi dau.
        15/09            : `login_chore` <-> `viec_vat`, 33 lan xen ke 31 lan
        16/09 party 41   : `ve_map` <-> `viec_vat` moi giay, dung nguyen o Trac Quan ca ngay
        16/09 party 51   : `pb_doi_theo` <-> `viec_vat`
    User: "chay chung 1 thread ma ko biet duoc acc do dang ban lam gi a".

    Gio nguon su that DUY NHAT ve "acc dang lam gi" la `viec_dang_lam` - viec chinh engine vua giao.
    """

    def test_anh_chup_KHONG_con_truong_viec_vat(self):
        self.assertFalse(hasattr(E.AnhAcc("u"), "viec_vat"),
                         "van giu co doc tu client -> lai nhap nhay")

    def test_chup_KHONG_goi_dang_lam_viec_vat(self):
        src = io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8").read()
        i = src.find("def chup(self)")
        self.assertGreater(i, 0)
        self.assertNotIn("dang_lam_viec_vat", src[i:i + 2500],
                         "van hoi acc dang ban gi - engine tu biet ma")

    def test_acc_dang_LOGIN_CHORE_khong_tinh_vao_phep_do_lech_map(self):
        """Viec vat PHAI o map khac (ban Noi Dan o Nghiep Thanh, cat tien trang, boss the gioi)."""
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=23851),
                    _a("m2", map_id=12061, xong_chore=False)], can=2)
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_VE_MAP, v.values(), "keo ca party di theo dua dang lam viec vat")

    def test_viec_ON_DINH_qua_nhieu_nhip(self):
        """Moi lan giao viec MOI la HUY viec dang chay - nhay qua lai = acc dung yen mai."""
        a1 = _a("m1", map_id=23011)
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851), a1], can=1)
        vets = []
        for _ in range(30):
            v = E.quyet_dinh(anh)
            vets.append(v["m1"])
            a1.viec_dang_lam = v["m1"]
        self.assertEqual(len(set(vets)), 1, "viec doi qua lai: %s" % sorted(set(vets)))


class TestLENH_LA_CAP_PARTY(unittest.TestCase):
    """MOT viec cho CA LU, khong phai moi acc mot viec.

    Engine cu ra DUNG MOT viec cho ca party (`_dieu_phoi_quyet` -> VIEC_GOM / VIEC_MOI /
    VIEC_DONG_BO / VIEC_LAM), roi tung acc thi hanh theo VAI.

    Ban dau engine moi tinh rieng tung acc VA loai acc "dang ban" khoi phep do -> moi nhip tinh
    tren mot tap acc khac nhau -> PARTY BI XE LE.
    Ca that 16/09 party 41 (user: "3 dua o giang dong 2 dua o trac quan"):
        17:37:32 dt806 -> login_chore
        17:37:33 dt807 -> lap_party
        17:37:43 dt809 -> ve_map
    """

    def test_ca_party_nhan_CUNG_MOT_viec(self):
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=23011, dang_ban=True, viec_dang_lam=E.VIEC_LAP_PARTY),
                    _a("m2", map_id=23011)], can=3)
        v = E.quyet_dinh(anh)
        self.assertEqual(len(set(v.values())) - (1 if E.VIEC_NGHI in v.values() else 0), 1,
                         "party bi xe le: %s" % v)

    def test_acc_dang_ban_KHONG_lam_lech_phep_do(self):
        """Loai acc dang ban khoi phep do -> moi nhip mot tap acc khac -> quyet dinh nhay lung tung."""
        a_ban = _a("m1", map_id=23011, dang_ban=True, viec_dang_lam=E.VIEC_LAP_PARTY)
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851), a_ban], can=1)
        self.assertEqual(E.quyet_dinh(anh)["m1"], E.VIEC_VE_MAP,
                         "acc lech map ma bi bo qua vi 'dang ban'")

    def test_acc_lam_VIEC_VAT_van_duoc_de_yen(self):
        """Viec vat la ngoai le DUY NHAT - no phai o map khac va co han gio."""
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=12061, xong_chore=False)], can=1)
        self.assertEqual(E.quyet_dinh(anh)["m1"], E.VIEC_LOGIN_CHORE)

    def test_cua_CHO_khong_cat_ngang_viec_chan(self):
        """"Chua nen ra lenh" = khong ra lenh MOI, chu khong phai cat ngang viec dang chay."""
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=23011, viec_dang_lam=E.VIEC_VE_MAP)],
                   can=1, cho_ly_do="leader dang rot/login lai")
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m1"], E.VIEC_VE_MAP)
        self.assertEqual(v["l"], E.VIEC_NGHI)

    def test_viec_ON_DINH_qua_30_nhip(self):
        a1 = _a("m1", map_id=23011)
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851), a1], can=1)
        for _ in range(30):
            v = E.quyet_dinh(anh)
            self.assertEqual(v["m1"], E.VIEC_VE_MAP)
            a1.viec_dang_lam = v["m1"]


class TestKHONG_DUOC_XE_LE_PARTY(unittest.TestCase):
    """CUA CHAN CHUNG: moi nhip, ca party phai nhan CUNG MOT viec (tru acc dang lam viec vat).

    Party 41, 16/09 (user: "3 dua o giang dong 2 dua o trac quan"): moi acc mot viec -> ba nhom
    di ba huong, khong bao gio gap nhau.

    Bai nay quet MOI tinh huong hay gap chu khong cho user phat hien ho.
    """

    def _viec_thuc(self, v):
        """Bo `nghi` (dung yen cho) va `login_chore`/`viec_vat` (ngoai le hop le)."""
        return {x for x in v.values()
                if x not in (E.VIEC_NGHI, E.VIEC_LOGIN_CHORE, E.VIEC_VIEC_VAT)}

    def _kiem(self, anh, ten):
        v = E.quyet_dinh(anh)
        self.assertLessEqual(len(self._viec_thuc(v)), 1, "%s -> party xe le: %s" % (ten, v))

    def test_lech_map(self):
        self._kiem(_anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                         _a("m1", map_id=23011), _a("m2", map_id=12001)], can=3), "lech map")

    def test_lech_kenh(self):
        self._kiem(_anh([_a("l", la_leader=True, so_member=3, kenh=1),
                         _a("m1", kenh=7), _a("m2", kenh=9)], can=3), "lech kenh")

    def test_thieu_doi(self):
        self._kiem(_anh([_a("l", la_leader=True, so_member=0), _a("m1"), _a("m2")], can=3),
                   "thieu doi")

    def test_co_acc_dang_ban_moi_viec_mot_kieu(self):
        self._kiem(_anh([_a("l", la_leader=True, so_member=0, dang_ban=True,
                            viec_dang_lam=E.VIEC_LAP_PARTY),
                         _a("m1", map_id=23011, dang_ban=True, viec_dang_lam=E.VIEC_VE_MAP),
                         _a("m2", dang_ban=True, viec_dang_lam=E.VIEC_DOI_KENH)], can=3),
                   "moi acc dang lam mot viec khac")

    def test_trong_DG_CHUA_DU_NGUOI_thi_KHONG_DANH(self):
        """L0 - user chot 16/09: "DG van phai du pt moi chay long vong chu".

        Dua vao truoc danh mot minh la BO LAI nhung dua chua vao, va chung vao sau se khong co ai
        keo."""
        v = E.quyet_dinh(_anh([_a("l", la_leader=True, so_member=3, con_gio_dg=True, map_id=21011),
                               _a("m1", con_gio_dg=True, trong_dg=True, map_id=49942),
                               _a("m2", con_gio_dg=True, map_id=12001)], can=3, pha=E.PHA_DG))
        self.assertEqual(v["l"], E.VIEC_DI_GIOI)
        self.assertEqual(v["m2"], E.VIEC_DI_GIOI)
        self.assertNotEqual(v["m1"], E.VIEC_TRAIN, "danh mot minh trong DG, bo lai dong doi")

    def test_trong_DG_DU_NGUOI_VA_DU_DOI_moi_DANH(self):
        accs = [_a("l", la_leader=True, so_member=3, con_gio_dg=True, trong_dg=True, map_id=49942),
                _a("m1", con_gio_dg=True, trong_dg=True, map_id=49942),
                _a("m2", con_gio_dg=True, trong_dg=True, map_id=49942)]
        v = E.quyet_dinh(_anh(accs, can=3, pha=E.PHA_DG))
        self.assertTrue(all(x == E.VIEC_TRAIN for x in v.values()), v)

    def test_trong_DG_du_nguoi_nhung_THIEU_DOI_thi_LAP_PARTY(self):
        accs = [_a("l", la_leader=True, so_member=0, con_gio_dg=True, trong_dg=True, map_id=49942),
                _a("m1", con_gio_dg=True, trong_dg=True, map_id=49942)]
        v = E.quyet_dinh(_anh(accs, can=1, pha=E.PHA_DG))
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)

    def test_pha_DG_chua_ai_vao_thi_TAT_CA_cung_vao(self):
        self._kiem(_anh([_a("l", la_leader=True, so_member=3, con_gio_dg=True, map_id=21011),
                         _a("m1", con_gio_dg=True, map_id=23011),
                         _a("m2", con_gio_dg=True, map_id=12001)], can=3, pha=E.PHA_DG),
                   "pha DG - chua ai vao")

    def test_pb_to_doi(self):
        v = E.quyet_dinh(_anh([_a("l", la_leader=True, so_member=3), _a("m1"), _a("m2")],
                              can=3, pb=50))
        self.assertEqual(v["l"], E.VIEC_PB_DOI, "leader phai la nguoi chay PB")
        self.assertEqual({v["m1"], v["m2"]}, {E.VIEC_PB_DOI_THEO}, "member phai cung mot viec")

    def test_thanh_di_ngang(self):
        self._kiem(_anh([_a("l", la_leader=True, so_member=0, map_id=12001),
                         _a("m1", map_id=12001), _a("m2", map_id=12001)],
                        can=3, thanh_di_ngang=True), "thanh di ngang")


class TestDUNG_QUYET_DINH_CUA_DIEU_PHOI_CU(unittest.TestCase):
    """Engine moi KHONG tu nghi ra chuoi lenh - no lay quyet dinh tu `_dieu_phoi_quyet`.

    Chuoi that co 11 NHANH va 15 phep thu (`_leader_dang_rot`, `_dang_doi_kenh`, `_thieu_acc_song`,
    `_ai_lech_instance`, `_o_thanh_di_qua`, `_thieu_doi`, `_viec_di_train`...). Ban tu viet cua
    engine moi chi co 4 bac, nen moi nhanh thieu la mot loi user phai di tim ho suot hai ngay:
    lap pt o Trac Quan, dung yen o thanh, xe le party, khong doi pha, khong tat acc mode DG...
    User 16/09: "sao may ko tham khao cai cu da co ma cu thich bia ra cai moi".
    """

    def _v(self, dp, **kw):
        accs = [_a("l", la_leader=True, so_member=3, map_id=23851),
                _a("m1", map_id=23011), _a("m2", map_id=12001)]
        return E.quyet_dinh(_anh(accs, can=3, dp_viec=dp, **kw))

    def test_GOM_thi_engine_KHONG_giao_viec(self):
        """`gom` la TRANG THAI, khong phai lenh: `_dieu_phoi_thi_hanh` bien no thanh MOT nhat
        `_bump_reform` roi vao cooldown 180s, ca party ve thanh theo `reform_gen` (test duoi).
        Dich thang thanh `ve_thanh` la giao lai moi giay, dap chinh lenh dang chay.
        Ca that 16/09 party 43 (user: "p43 lap pt o Ng thanh"): 22:41:15 roster DU 4/4 tai 12061,
        22:41:16 con 0/4 vi lenh `ve_thanh` tele len 12001 (moi teleport la mot `leave_party()`)."""
        v = self._v(E.DP_GOM)
        self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)

    def test_REFORM_GEN_moi_thi_ca_party_VE_THANH_TAP_KET(self):
        accs = [_a("l", la_leader=True, map_id=12061), _a("m1", map_id=12061)]
        anh = _anh(accs, can=1)
        anh.reform_moi = True
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_VE_THANH for x in v.values()), v)

    def test_RESYNC_GEN_moi_thi_MEMBER_roi_party_sync_kenh(self):
        """Leader khong vao nhanh nay - no tu sync + moi lai trong vong moi cua no (engine cu)."""
        accs = [_a("l", la_leader=True, map_id=12061), _a("m1", map_id=12061)]
        anh = _anh(accs, can=1)
        anh.resync_moi = True
        v = E.quyet_dinh(anh)
        self.assertEqual(v.get("m1"), E.VIEC_RESYNC)
        self.assertNotEqual(v.get("l"), E.VIEC_RESYNC)

    def test_DONG_BO_thi_engine_KHONG_giao_viec(self):
        """Nguoi gui lenh doi kenh la `_dieu_phoi_thi_hanh_kenh` cua dieu phoi (no tu gui cho tung
        acc lech). Engine moi gui nua la HAI nguon ra lenh cho mot party."""
        v = self._v(E.DP_DONG_BO)
        self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)

    def test_MOI_thi_ca_party_LAP_PARTY(self):
        v = self._v(E.DP_MOI)
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)

    def test_DI_TRAIN_thi_VE_MAP(self):
        v = self._v(E.DP_DI_TRAIN)
        self.assertTrue(all(x == E.VIEC_VE_MAP for x in v.values()), v)

    def test_RA_QUAI_thi_RA_SPOT(self):
        v = self._v(E.DP_RA_QUAI)
        self.assertTrue(all(x == E.VIEC_RA_SPOT for x in v.values()), v)

    def test_LAM_thi_TRAIN(self):
        v = self._v(E.DP_LAM)
        self.assertTrue(all(x == E.VIEC_TRAIN for x in v.values()), v)

    def test_quyet_dinh_cua_dieu_phoi_DE_LEN_ban_tu_tinh(self):
        """Dieu phoi bao LAM thi khong duoc tu y gom, du dang lech map."""
        v = self._v(E.DP_LAM)
        self.assertNotIn(E.VIEC_VE_MAP, v.values(), "tu y gom trong khi dieu phoi bao LAM")

    def test_acc_dang_LAM_VIEC_VAT_van_duoc_de_yen(self):
        accs = [_a("l", la_leader=True, so_member=3, map_id=23851),
                _a("m1", map_id=12061, xong_chore=False)]
        v = E.quyet_dinh(_anh(accs, can=1, dp_viec=E.DP_GOM))
        self.assertEqual(v["m1"], E.VIEC_LOGIN_CHORE, "keo acc dang lam viec vat di gom")

    def test_dieu_phoi_KHONG_tra_loi_thi_tu_quyet_nhu_cu(self):
        v = self._v(None)
        self.assertIn(E.VIEC_VE_MAP, v.values(), "dieu phoi im ma engine cung dung yen")


class TestMODE_EVENT_lam_y_FLOW_CU(unittest.TestCase):
    """LAM Y FLOW CU (`run_account`, nhanh `elif mode == "event"`):
        1. NGOAI GIO event / da xong  -> di doi thuong roi THOAT GAME  (dong 5723-5731)
        2. CHUA VAO MAP EVENT         -> `go_to_event`, CHUA VAO THI CHUA LAP PARTY (dong 5781)
        3. da vao, thieu doi          -> lap party
        4. du doi                     -> LEADER mo vong battle (`start_npc40_loop`)

    User 16/09: "p41, mode 40npc -> chua vao map event da thay lap pt".
    """

    def _ev(self, trong=(), **kw):
        accs = [_a("l", la_leader=True, so_member=kw.pop("roster", 2),
                   trong_event=("l" in trong), map_id=10991 if "l" in trong else 12001)]
        for u in ("m1", "m2"):
            accs.append(_a(u, trong_event=(u in trong),
                           map_id=10991 if u in trong else 12001))
        return E.quyet_dinh(_anh(accs, can=2, pha=E.PHA_EVENT, **kw))

    def test_CHUA_VAO_map_event_thi_VAO_truoc(self):
        v = self._ev(trong=())
        self.assertTrue(all(x == E.VIEC_VAO_EVENT for x in v.values()), v)
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values(), "lap party khi chua vao map event")

    def test_moi_MOT_DUA_vao_thi_van_CHUA_lap_party(self):
        """Bo lai mot dua la no dung ngoai map event ca buoi."""
        v = self._ev(trong=("l",))
        self.assertEqual(v["m1"], E.VIEC_VAO_EVENT)
        self.assertEqual(v["m2"], E.VIEC_VAO_EVENT)
        self.assertEqual(v["l"], E.VIEC_LAP_PARTY, "chua du nguoi ma da mo battle")

    def test_VAO_DU_nhung_THIEU_DOI_thi_LAP_PARTY(self):
        v = self._ev(trong=("l", "m1", "m2"), roster=0)
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)

    def test_VAO_DU_ma_LECH_KENH_thi_DONG_BO_KENH_truoc(self):
        """Engine cu: `if event_party_mode: do_channel_sync()` ngay truoc khi mo gate moi.
        Map event cung chia kenh - lech kenh la KHONG THAY NHAU, leader moi mai khong ai join
        (bug user 40NPC 29/07)."""
        accs = [_a("l", la_leader=True, so_member=0, trong_event=True, map_id=10991, kenh=1),
                _a("m1", trong_event=True, map_id=10991, kenh=7),
                _a("m2", trong_event=True, map_id=10991, kenh=1)]
        anh = _anh(accs, can=2, pha=E.PHA_EVENT)
        anh.dp_viec = E.DP_DONG_BO
        v = E.quyet_dinh(anh)
        # `dong_bo` -> engine KHONG giao viec: `_dieu_phoi_thi_hanh_kenh` cua dieu phoi tu gui lenh
        # doi kenh cho tung acc lech. Cai phai giu la: KHONG moi party khi con lech kenh.
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values(), "moi party khi con lech kenh -> khong ai join")

    def test_CUNG_KENH_roi_thi_moi_LAP_PARTY(self):
        accs = [_a("l", la_leader=True, so_member=0, trong_event=True, map_id=10991, kenh=1),
                _a("m1", trong_event=True, map_id=10991, kenh=1)]
        anh = _anh(accs, can=1, pha=E.PHA_EVENT)
        anh.dp_viec = E.DP_MOI
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)

    def test_CHUA_VAO_DU_thi_KHONG_nhuong_dieu_phoi(self):
        """Con dua ngoai map event ma nhuong `gom` cho dieu phoi -> no keo ca doi VE THANH,
        bo mat dua da vao. Chi nhuong khi CA DOI da vao."""
        accs = [_a("l", la_leader=True, so_member=0, trong_event=True, map_id=10991, kenh=1),
                _a("m1", trong_event=False, map_id=1001, kenh=1)]
        anh = _anh(accs, can=1, pha=E.PHA_EVENT)
        anh.dp_viec = E.DP_GOM
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m1"], E.VIEC_VAO_EVENT)
        self.assertNotIn(E.VIEC_VE_THANH, v.values(), "keo acc da vao map event ve thanh")

    def test_DU_DOI_thi_LEADER_mo_battle_member_dung_yen(self):
        v = self._ev(trong=("l", "m1", "m2"), roster=2)
        self.assertEqual(v["l"], E.VIEC_DANH_EVENT)
        self.assertEqual(v["m1"], E.VIEC_NGHI, "member tu mo battle -> moi dua mot tran")
        self.assertEqual(v["m2"], E.VIEC_NGHI)

    def test_EVENT_XONG_thi_di_DOI_THUONG_het(self):
        """`go_claim` / `event_battle_done` / ngoai gio -> huy party + doi thuong + THOAT GAME.
        User 14/09: "event thi danh xong out, train deo gi o day"."""
        v = self._ev(trong=("l", "m1", "m2"), roster=2, event_xong=True)
        self.assertTrue(all(x == E.VIEC_DOI_THUONG for x in v.values()), v)

    def test_event_xong_thi_KHONG_gom_KHONG_moi(self):
        v = self._ev(trong=("l",), event_xong=True)
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values())
        self.assertNotIn(E.VIEC_VAO_EVENT, v.values())


class TestTHU_TU_BAC_trong_nhip(unittest.TestCase):
    """Hai pha dac thu (EVENT / DI GIOI) phai xet TRUOC khi dich `dp_viec`.

    Dieu phoi cu ra `VIEC_LAM` cho ca hai mode do (no khong biet "vao map event" hay "vao DG" la
    viec gi), ma `lam` -> `train`. Dat sau thi nhanh event/DG KHONG BAO GIO chay toi.

    Ca that 16/09 party 41 mode 40NPC (user: "p41 van ko vao event"):
        20:54:45 [party 41] ENGINE: dt806..dt810 -> train     <- dang phai la `vao_event`
    """

    def test_pha_EVENT_thang_dp_viec_LAM(self):
        accs = [_a("l", la_leader=True, so_member=2, map_id=12001),
                _a("m1", map_id=12001)]
        v = E.quyet_dinh(_anh(accs, can=1, pha=E.PHA_EVENT, dp_viec=E.DP_LAM))
        self.assertTrue(all(x == E.VIEC_VAO_EVENT for x in v.values()),
                        "dp_viec='lam' de len nhanh event -> khong bao gio vao map event: %s" % v)

    def test_pha_DG_thang_dp_viec_LAM(self):
        accs = [_a("l", la_leader=True, so_member=2, con_gio_dg=True, map_id=12001),
                _a("m1", con_gio_dg=True, map_id=12001)]
        v = E.quyet_dinh(_anh(accs, can=1, pha=E.PHA_DG, dp_viec=E.DP_LAM))
        self.assertTrue(all(x == E.VIEC_DI_GIOI for x in v.values()), v)

    def test_pha_TRAIN_thi_van_NGHE_dieu_phoi(self):
        accs = [_a("l", la_leader=True, so_member=2, map_id=23851),
                _a("m1", map_id=23011)]
        v = E.quyet_dinh(_anh(accs, can=1, pha=E.PHA_TRAIN, dp_viec=E.DP_DI_TRAIN))
        self.assertTrue(all(x == E.VIEC_VE_MAP for x in v.values()), v)


class TestPhaDiGioi(unittest.TestCase):
    """Di Gioi la instance rieng: vao roi thi khong con khai niem lech map/kenh voi nhau."""

    def test_con_gio_thi_VAO_DI_GIOI(self):
        anh = _anh([_a("l", la_leader=True, so_member=3, con_gio_dg=True),
                    _a("m1", con_gio_dg=True, map_id=23011)], pha=E.PHA_DG)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_DI_GIOI for x in v.values()), v)

    def test_lech_map_o_pha_DG_KHONG_gom(self):
        """Truoc khi vao DG thi moi dua mot noi la BINH THUONG - gom lai la vo nghia, va con lam
        cham viec vao DG (DG tinh gio, gom mat 3 phut la mat 3 phut EXP)."""
        anh = _anh([_a("l", la_leader=True, so_member=3, con_gio_dg=True, map_id=21011),
                    _a("m1", con_gio_dg=True, map_id=23011),
                    _a("m2", con_gio_dg=True, map_id=55002)], pha=E.PHA_DG)
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_VE_MAP, v.values())

    def test_da_vao_DG_thi_DANH(self):
        # `con_gio_dg=True`: het gio thi ket thuc bat ke dang o dau (xem
        # TestHetGioDGThiKET_THUC_BAT_KE_DANG_O_DAU)
        anh = _anh([_a("l", la_leader=True, so_member=3, trong_dg=True, con_gio_dg=True,
                       map_id=49942),
                    _a("m1", trong_dg=True, con_gio_dg=True, map_id=49942)], pha=E.PHA_DG)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_TRAIN for x in v.values()), v)

    def test_het_gio_DG_thi_DUNG_YEN_cho_doi_pha(self):
        """Acc het gio KHONG duoc tu di train mot minh - doi pha la viec cap party."""
        anh = _anh([_a("l", la_leader=True, so_member=3, con_gio_dg=False),
                    _a("m1", con_gio_dg=False)], pha=E.PHA_DG)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)


class TestTrongDiGioiVanPhaiLapDoi(unittest.TestCase):
    """User 16/09: "party 40+ ko thay lap pt".

    Do tren log: 63 lan `ENGINE: ... -> train`, **0 lan `-> lap_party`**. Vi party mode
    `digioi_train` nam o pha DG gan nhu suot, ma nhanh pha DG cu chi co `di_gioi` -> `train`:
    ca party vao Di Gioi xong la moi dua danh MOT MINH, khong bao gio lap doi - trong khi
    `digioi_mode = "party"` doi ho danh chung.
    """

    def _dg(self, trong=(), can=3, roster=0):
        accs = [_a("l", la_leader=True, so_member=roster, trong_dg=("l" in trong),
                   con_gio_dg=True, map_id=49942 if "l" in trong else 21011)]
        for u in ("m1", "m2"):
            accs.append(_a(u, trong_dg=(u in trong), con_gio_dg=True,
                           map_id=49942 if u in trong else 21011))
        return _anh(accs, can=can, pha=E.PHA_DG)

    def test_da_vao_DG_ma_THIEU_DOI_thi_LAP_PARTY(self):
        v = E.quyet_dinh(self._dg(trong=("l", "m1", "m2"), can=2, roster=0))
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)

    def test_da_vao_DG_va_DU_DOI_thi_DANH(self):
        v = E.quyet_dinh(self._dg(trong=("l", "m1", "m2"), can=2, roster=2))
        self.assertTrue(all(x == E.VIEC_TRAIN for x in v.values()), v)

    def test_nguoi_CHUA_VAO_van_di_vao_KHONG_bat_cho_nhau(self):
        """DG tinh GIO - dung cho nhau la mat phut EXP."""
        v = E.quyet_dinh(self._dg(trong=("l",), can=2, roster=0))
        self.assertEqual(v["m1"], E.VIEC_DI_GIOI)
        self.assertEqual(v["m2"], E.VIEC_DI_GIOI)
        self.assertEqual(v["l"], E.VIEC_LAP_PARTY, "nguoi vao truoc phai bat dau moi")

    def test_het_gio_thi_van_dung_yen_cho_doi_pha(self):
        accs = [_a("l", la_leader=True, so_member=0, con_gio_dg=False),
                _a("m1", con_gio_dg=False)]
        v = E.quyet_dinh(_anh(accs, can=1, pha=E.PHA_DG))
        self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)


class TestHetGioDGThiKET_THUC_BAT_KE_DANG_O_DAU(unittest.TestCase):
    """Flow cu (`_cho_party_xong_dg`): `if remain <= 0 ... -> _ket_thuc_pha_dg()`. No KHONG hoi acc
    dang o TRONG hay NGOAI map DG.

    Ban dau engine moi chi xet acc CHUA VAO, nen acc dang o trong DG ma het gio van duoc cho danh
    tiep => mode `digioi` thuan KHONG BAO GIO tat acc.
    User 16/09: "p46 p54, mode Di gioi -> het tiem di gioi roi ma deo tat acc".
    """

    def _dg(self, co_pha_train, trong_dg, con_gio):
        accs = [_a("l", la_leader=True, so_member=1, trong_dg=trong_dg, con_gio_dg=con_gio,
                   map_id=49942 if trong_dg else 21011),
                _a("m1", trong_dg=trong_dg, con_gio_dg=con_gio,
                   map_id=49942 if trong_dg else 21011)]
        anh = _anh(accs, can=1, pha=E.PHA_DG)
        anh.co_pha_train = co_pha_train
        return anh

    def test_DANG_TRONG_DG_ma_het_gio_thi_mode_digioi_THOAT(self):
        v = E.quyet_dinh(self._dg(co_pha_train=False, trong_dg=True, con_gio=False))
        self.assertTrue(all(x == E.VIEC_THOAT for x in v.values()), v)

    def test_NGOAI_DG_ma_het_gio_thi_mode_digioi_cung_THOAT(self):
        v = E.quyet_dinh(self._dg(co_pha_train=False, trong_dg=False, con_gio=False))
        self.assertTrue(all(x == E.VIEC_THOAT for x in v.values()), v)

    def test_digioi_train_het_gio_thi_DUNG_YEN_cho_doi_pha(self):
        for _trong in (True, False):
            v = E.quyet_dinh(self._dg(co_pha_train=True, trong_dg=_trong, con_gio=False))
            self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)

    def test_CON_GIO_thi_van_danh_binh_thuong(self):
        v = E.quyet_dinh(self._dg(co_pha_train=False, trong_dg=True, con_gio=True))
        self.assertNotIn(E.VIEC_THOAT, v.values(), "con gio ma da tat acc")

    def test_nguoi_het_gio_THOAT_nguoi_con_gio_VAN_DANH(self):
        """Moi acc mot dong ho rieng - khong duoc lay mot acc lam chuan cho ca party."""
        accs = [_a("l", la_leader=True, so_member=1, trong_dg=True, con_gio_dg=True, map_id=49942),
                _a("m1", trong_dg=True, con_gio_dg=False, map_id=49942)]
        anh = _anh(accs, can=1, pha=E.PHA_DG)
        anh.co_pha_train = False
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m1"], E.VIEC_THOAT)
        self.assertNotEqual(v["l"], E.VIEC_THOAT)


class TestKhongLapPartyOThanhDiNgang(unittest.TestCase):
    """CHI LAP PARTY O THANH TAP KET HOAC MAP TRAIN (luat cu, user chot 13/09).

    Thanh DI NGANG QUA thi di tiep da: buoc ngay sau la TELEPORT, ma teleport bat buoc
    `leave_party()` -> party vua lap lai tan, ca chuoi quay lai tu dau.

    Ca that party 4, 13/09: "p4, bon no lap pt o Trac quan lam lon gi the".
    Lap lai tren engine moi 16/09 party 41: "party 41 dung lap party o Trac quan" - ban dau engine
    moi chi hoi "cung map chua", nen ca party dung o thanh cung duoc coi la "cung map" roi lap
    party ngay tai do.
    """

    def test_o_thanh_di_ngang_thi_DI_TIEP_khong_lap_party(self):
        anh = _anh([_a("l", la_leader=True, so_member=0, map_id=12001),
                    _a("m1", map_id=12001)], can=1, thanh_di_ngang=True)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_VE_MAP for x in v.values()), v)
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values(), "lap party o thanh trung gian = lap xong lai tan")

    def test_o_thanh_TAP_KET_thi_VAN_LAP(self):
        anh = _anh([_a("l", la_leader=True, so_member=0, map_id=12001),
                    _a("m1", map_id=12001)], can=1, thanh_di_ngang=False)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_LAP_PARTY for x in v.values()), v)

    def test_DU_DOI_roi_thi_thanh_di_ngang_KHONG_can_thiep(self):
        """Du doi roi thi di tiep binh thuong theo chuoi - khong dinh gi toi bac lap party."""
        anh = _anh([_a("l", la_leader=True, so_member=1, map_id=12001),
                    _a("m1", map_id=12001)], can=1, thanh_di_ngang=True)
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values())


class TestChuaNenRaLenhThiDUNG_YEN(unittest.TestCase):
    """Engine cu co BON cua nay TRUOC ca chuoi (`_dieu_phoi_quyet`):

        `_leader_dang_rot`  - leader dang rot/login lai: ra lenh luc nay la ra cho mot party dang
                              thieu nguoi chi huy, gom xong cung tan
        `_dang_doi_kenh`    - co acc dang chuyen kenh: de len lenh khac la no bo do giua chung
        `_thieu_acc_song`   - chua du acc login xong: doi hinh chua that, moi phep do deu sai
        `_ai_lech_instance` - cung map + cung kenh nhung KHAC INSTANCE (khong thay nhau): moi mai
                              khong duoc, phai doi kenh cho lech instance vo

    Engine moi ban dau bo sach bon cai nay -> ra lenh vao dung luc party dang xao tron.
    """

    def test_co_ly_do_cho_thi_CA_PARTY_dung_yen(self):
        anh = _anh([_a("l", la_leader=True, so_member=0, map_id=12001),
                    _a("m1", map_id=23851, kenh=7)], can=1,
                   cho_ly_do="leader dang rot/login lai")
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)

    def test_cua_cho_dat_TRUOC_moi_bac_khac(self):
        """Ke ca dang lech map - gom luc leader chua login xong la gom hut."""
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=23011)], can=1, cho_ly_do="chua du acc login xong")
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_VE_MAP, v.values())

    def test_HET_ly_do_thi_chay_binh_thuong_ngay(self):
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=23011)], can=1, cho_ly_do="")
        self.assertEqual(E.quyet_dinh(anh)["m1"], E.VIEC_VE_MAP)

    def test_acc_dang_viec_vat_cung_dung_yen(self):
        """Khong duoc de acc nao ra ngoai danh sach - im lang la benh cua engine cu."""
        anh = _anh([_a("l", la_leader=True, so_member=1),
                    _a("m1", map_id=12061, xong_chore=False)], can=1, cho_ly_do="co acc dang doi kenh")
        v = E.quyet_dinh(anh)
        self.assertEqual(set(v), {"l", "m1"})


class TestDG_co_dua_HET_GIO_thi_DUNG_YEN(unittest.TestCase):
    """Y engine cu (`_start_training` dong 6368-6375): "Co acc KHAC het gio DG -> party khong gom
    duoc nua -> KHONG chay long vong danh 1 minh (de chet vi khong co party hoi mau). DUNG YEN
    burn time trong DG den khi het gio cua chinh minh."
    """

    def test_co_dua_het_gio_thi_KHONG_chay_long_vong(self):
        accs = [_a("l", la_leader=True, so_member=3, con_gio_dg=True, trong_dg=True, map_id=49942),
                _a("m1", con_gio_dg=True, trong_dg=True, map_id=49942),
                _a("m2", con_gio_dg=False, trong_dg=True, map_id=49942)]
        anh = _anh(accs, can=2, pha=E.PHA_DG)
        anh.co_pha_train = True
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_NGHI, "danh le trong DG khi party da vo -> de chet")
        self.assertEqual(v["m1"], E.VIEC_NGHI)

    def test_CON_DU_gio_thi_van_danh(self):
        accs = [_a("l", la_leader=True, so_member=3, con_gio_dg=True, trong_dg=True, map_id=49942),
                _a("m1", con_gio_dg=True, trong_dg=True, map_id=49942)]
        anh = _anh(accs, can=1, pha=E.PHA_DG)
        self.assertEqual(E.quyet_dinh(anh)["l"], E.VIEC_TRAIN)


class TestPhaiCoBaiQuaiMoiDanh(unittest.TestCase):
    """User 14/09: "vay la dang o thanh, thay vi chay ra map train may lai tinh la dang o map train
    va chay ra spot a". Du party KHONG co nghia la duoc dung yen danh o bat cu dau."""

    def test_chua_chot_bai_quai_thi_DUNG_YEN(self):
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1")], can=3, co_spot=False)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)
        self.assertNotIn(E.VIEC_TRAIN, v.values(), "bat combat giua thanh")


class TestPhoBanToDoi(unittest.TestCase):
    """DUONG LAP DOI CUA PB KHAC HAN party thuong (user 15/09: "duong lap pt PB no khac voi lap pt
    di train"). Theo KNOWLEDGE.md:

        party thuong : moi `0x0d/0900`, member phai MO GATE (`set_party_invite_ready`)
        phong PB     : moi `Dungeon.SendInvite` -> `0x2f/0800`; member nhan `0x2f/0f00` roi join
                       room `0x2f/0300` + ready `0x2f/0b00` - `_on_dungeon` TU LAM het

    "PB invite KHONG bat buoc check gan nhu party thuong vi server/client cho moi theo roleId da
    biet" => KHONG can cung map, KHONG can cung kenh, KHONG can du party thuong truoc.
    """

    def test_danh_PB_TRUOC_ca_chuoi_gom(self):
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1"), _a("m2")], can=3, pb=50)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_PB_DOI, "leader phai la nguoi chay kich ban PB")
        self.assertEqual(v["m1"], E.VIEC_PB_DOI_THEO)
        self.assertNotIn(E.VIEC_RA_SPOT, v.values())

    def test_KHONG_doi_du_party_thuong(self):
        """Bat gom du 4/4 roi moi cho danh PB la tu dat them dieu kien ma game khong doi - va moi
        phut gom la mot phut co the mat luot PB."""
        anh = _anh([_a("l", la_leader=True, so_member=0), _a("m1"), _a("m2")], can=3, pb=50)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_PB_DOI)
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values(), "doi party thuong truoc PB = doi thu khong can")

    def test_KHONG_doi_cung_map_cung_kenh(self):
        """Server moi theo roleId da biet, khong check gan nhu party thuong."""
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851, kenh=1),
                    _a("m1", map_id=23011, kenh=7),
                    _a("m2", map_id=12001, kenh=9)], can=2, pb=50)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_PB_DOI)
        self.assertNotIn(E.VIEC_VE_MAP, v.values(), "gom map truoc PB = mat thoi gian vo ich")
        self.assertNotIn(E.VIEC_DOI_KENH, v.values())

    def test_het_luot_PB_thi_di_train_binh_thuong(self):
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1")], can=1, pb=None)
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_PB_DOI, v.values())
        self.assertIn(E.VIEC_RA_SPOT, v.values())

    def test_acc_dang_viec_vat_KHONG_bi_keo_vao_PB(self):
        anh = _anh([_a("l", la_leader=True, so_member=3), _a("m1"),
                    _a("m2", map_id=12061, xong_chore=False)], can=2, pb=50)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_LOGIN_CHORE, "keo acc dang lam viec vat vao PB")


class TestNhipKhongDuocCHAN(unittest.TestCase):
    """Dieu KIEN TIEN QUYET cua ca engine: nhip khong chan => khong the co vong cho diec lenh.

    Party 11 (15/09) chet vi `luumuoi` ket trong `while not st["invited"].is_set()` - vong do nghe
    lenh kenh + `rally_gen` nhung khong nghe `reform_gen`. Neu nhip nay lo len mot `sleep`/`wait`
    thi ho loi do quay lai ngay, nen chan bang test.
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        self.cay = ast.parse(self.src)

    def _ham(self, ten):
        return next(n for n in ast.walk(self.cay)
                    if isinstance(n, ast.FunctionDef) and n.name == ten)

    def test_quyet_dinh_khong_sleep_khong_wait(self):
        than = self._ham("quyet_dinh")
        for n in ast.walk(than):
            if isinstance(n, ast.Call):
                ten = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                self.assertNotIn(ten, ("sleep", "wait", "join"),
                                 "nhip quyet dinh bi CHAN -> de lai sinh vong cho diec lenh")

    def test_quyet_dinh_khong_co_vong_lap_vo_han(self):
        than = self._ham("quyet_dinh")
        for n in ast.walk(than):
            if isinstance(n, ast.While):
                self.fail("nhip quyet dinh co `while` -> co the ket, dung cai dang chua")

    def test_quyet_dinh_la_ham_THUAN(self):
        """Khong doc dong ho, khong doc state ngoai: cung mot anh phai ra cung mot ket qua."""
        than = self._ham("quyet_dinh")
        for n in ast.walk(than):
            if isinstance(n, ast.Call):
                goc = getattr(getattr(n.func, "value", None), "id", None)
                self.assertNotEqual(goc, "time", "nhip doc dong ho -> khong con thuan, khong test duoc")

    def test_chay_lai_nhieu_lan_ra_ket_qua_GIONG_HET(self):
        anh = _anh([_a("l", la_leader=True, so_member=1), _a("m1", kenh=7), _a("m2")])
        dau = E.quyet_dinh(anh)
        for _ in range(50):
            self.assertEqual(E.quyet_dinh(anh), dau)

    def test_nhip_du_nhanh_cho_ca_tram_party(self):
        """Do tren engine cu: 1 quyet dinh = 0,014ms. Nhip 1s cho 54 party phai la con muoi."""
        anh = _anh([_a("u%d" % i, la_leader=(i == 0), so_member=1, kenh=1 + (i % 2))
                    for i in range(5)])
        t0 = time.perf_counter()
        for _ in range(1000):
            E.quyet_dinh(anh)
        moi_lan_ms = (time.perf_counter() - t0) * 1000 / 1000
        self.assertLess(moi_lan_ms, 1.0, "mot nhip %.3fms - qua cham" % moi_lan_ms)


class TestDonVeDau(unittest.TestCase):
    """Party o nhieu map ma engine chua chot diem tap ket -> don ve MAP DONG NGUOI NHAT.

    Lay bua mot map la co luc bat ba dua dang dung dung cho di theo MOT dua lac (vd dua chet hoi
    sinh ve thanh) - ca party roi bai train de chay theo no.
    """

    def test_ve_map_dong_nguoi_nhat(self):
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=23851), _a("m2", map_id=23011)])
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_VE_MAP, "ba nguoi phai chay theo mot nguoi lac")
        self.assertEqual(v["l"], E.VIEC_NGHI)
        self.assertEqual(v["m1"], E.VIEC_NGHI)

    def test_hoa_thi_theo_LEADER(self):
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23011),
                    _a("m1", map_id=23851)])
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_NGHI, "hoa 1-1 thi lay map cua leader lam dich")
        self.assertEqual(v["m1"], E.VIEC_VE_MAP)

    def test_da_chot_diem_tap_ket_thi_THEO_DICH_DO(self):
        """Engine da chot thanh tap ket -> ca party ve do, ke ca khi dang dong o map khac."""
        anh = _anh([_a("l", la_leader=True, so_member=3, map_id=23851),
                    _a("m1", map_id=23851), _a("m2", map_id=23011)], map_dich=23011)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_NGHI)
        self.assertEqual(v["l"], E.VIEC_VE_MAP)


class TestWorkerHuyDuocViec(unittest.TestCase):
    """Viec chan phai NHA RA khi co lenh moi - neu khong thi lenh van khong toi duoc acc, y het
    engine cu."""

    def test_giao_viec_moi_thi_viec_cu_bi_huy(self):
        dau_vet = []
        cho_xong = threading.Event()

        def _lam(_cli, viec, con_lam):
            dau_vet.append(viec)
            while con_lam():           # gia lam viec chan dai
                time.sleep(0.01)
            cho_xong.set()

        w = E.AccWorker("u", None, _lam)
        w.start()
        try:
            w.giao(E.VIEC_VE_MAP)
            for _ in range(200):
                if dau_vet:
                    break
                time.sleep(0.01)
            self.assertEqual(dau_vet[:1], [E.VIEC_VE_MAP])
            w.giao(E.VIEC_TRAIN)       # lenh moi -> viec cu phai nha ra
            self.assertTrue(cho_xong.wait(3), "viec chan KHONG huy duoc -> lenh moi khong toi noi")
        finally:
            w.stop()

    def test_viec_loi_KHONG_giet_worker(self):
        """Mot viec no khong duoc lam chet luong - nhip sau con giao lai duoc (L0: phai cuu acc)."""
        dem = []

        def _lam(_cli, viec, _con):
            dem.append(viec)
            raise RuntimeError("no thu")

        w = E.AccWorker("u", None, _lam)
        w.start()
        try:
            w.giao(E.VIEC_VE_MAP)
            for _ in range(200):
                if len(dem) >= 2:
                    break
                time.sleep(0.01)
            self.assertGreaterEqual(len(dem), 2, "worker chet sau loi dau tien")
        finally:
            w.stop()

if __name__ == "__main__":
    unittest.main()
