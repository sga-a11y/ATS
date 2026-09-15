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


def _anh(accs, can=3, map_dich=None, co_spot=True, pha=E.PHA_TRAIN, pb=None):
    """Mac dinh `co_spot=True`: cac ca duoi day noi ve CHUOI GOM, khong phai ve bai quai.
    Rieng `TestPhaiCoBaiQuaiMoiDanh` thu chinh cai cua do."""
    return E.AnhParty(40, accs, can_bao_nhieu=can, map_dich=map_dich, co_spot=co_spot, pha=pha,
                      pb_doi_level=pb)


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
                    _a("m2", map_id=12061, viec_vat=True)], can=3)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_VIEC_VAT)
        self.assertEqual(v["l"], E.VIEC_RA_SPOT, "party con lai van chay tiep binh thuong")

    def test_khong_giao_viec_khac_cho_acc_dang_viec_vat(self):
        anh = _anh([_a("l", la_leader=True, so_member=1, map_id=23011), _a("m1"),
                    _a("m2", map_id=12061, viec_vat=True)], can=3)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_VIEC_VAT)


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
        anh = _anh([_a("l", la_leader=True, so_member=3, trong_dg=True, map_id=49942),
                    _a("m1", trong_dg=True, map_id=49942)], pha=E.PHA_DG)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_TRAIN for x in v.values()), v)

    def test_het_gio_DG_thi_DUNG_YEN_cho_doi_pha(self):
        """Acc het gio KHONG duoc tu di train mot minh - doi pha la viec cap party."""
        anh = _anh([_a("l", la_leader=True, so_member=3, con_gio_dg=False),
                    _a("m1", con_gio_dg=False)], pha=E.PHA_DG)
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_NGHI for x in v.values()), v)


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
                    _a("m2", viec_vat=True, map_id=12061)], can=2, pb=50)
        v = E.quyet_dinh(anh)
        self.assertEqual(v["m2"], E.VIEC_VIEC_VAT)


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
