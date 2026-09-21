# -*- coding: utf-8 -*-
"""ENGINE MOI phai lam NHIEM VU NGAY (PB don o1 + claim 9 o).

Engine moi khong chay `run_account` nen mat sach khoi "viec hang ngay" cua no:
    c.do_daily_dungeon()          - o 1 (pho ban don 2 luot)
    c.claim_daily_quests(heavy)   - claim 9 o, keo theo o2 (boss the gioi) va o5 (PB to doi)

Do tren log 17/09 (user: "xem 1 luot cac acc xem co acc nao hom nay chua hoan thanh daily quest
ko"): 60 acc thuoc party 41-56 - dung la cac party chay ENGINE MOI - KHONG co MOT DONG
`Nhiem vu hang ngay` nao ca ngay, trong khi party engine cu deu 8-9/9 o. Kiem cheo: may acc
"co log daily" o p46/p52 deu ghi luc 08:07-08:14, TRUOC khi engine moi khoi dong cho party do
(09:26) - tuc he chuyen sang engine moi la daily ngung han.

RANG BUOC user dat ra: "sua di, dung lam hong cai lap pt la dc".
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E


def _a(u, **kw):
    kw.setdefault("map_id", 23001)
    kw.setdefault("kenh", 1)
    return E.AnhAcc(u, **kw)


def _anh(accs, pha=E.PHA_TRAIN, thanh_dich=None, **kw):
    a = E.AnhParty(50, accs, can_bao_nhieu=len(accs) - 1, co_spot=True, pha=pha, **kw)
    a.thanh_dich = thanh_dich
    return a


class TestGiaoViecNhiemVuNgay(unittest.TestCase):
    def test_chua_lam_thi_GIAO(self):
        accs = [_a("l", la_leader=True, so_member=2, xong_daily=False),
                _a("m1", xong_daily=False), _a("m2", xong_daily=False)]
        v = E.quyet_dinh(_anh(accs))
        self.assertTrue(all(x == E.VIEC_DAILY for x in v.values()), v)

    def test_lam_xong_roi_thi_THOI(self):
        accs = [_a("l", la_leader=True, so_member=2), _a("m1"), _a("m2")]
        v = E.quyet_dinh(_anh(accs))
        self.assertNotIn(E.VIEC_DAILY, v.values())

    def test_PHA_DI_GIOI_thi_KHONG_lam(self):
        """O 2 la BOSS THE GIOI -> `do_world_boss()` teleport di roi tra ve Trac Quan, tuc VUT acc
        ra khoi Di Gioi. Flow cu cung hoan toi sau DG (`_do_startup_daily` co `not is_digioi`)."""
        accs = [_a("l", la_leader=True, so_member=2, xong_daily=False, con_gio_dg=True),
                _a("m1", xong_daily=False, con_gio_dg=True)]
        v = E.quyet_dinh(_anh(accs, pha=E.PHA_DG))
        self.assertNotIn(E.VIEC_DAILY, v.values())

    def test_viec_vat_sau_login_van_duoc_uu_tien_truoc(self):
        accs = [_a("l", la_leader=True, so_member=2, xong_chore=False, xong_daily=False)]
        self.assertEqual(E.quyet_dinh(_anh(accs))["l"], E.VIEC_LOGIN_CHORE)


class TestKHONG_DUNG_TOI_LAP_PARTY(unittest.TestCase):
    """User: "sua di, dung lam hong cai lap pt la dc".

    Nhiem vu ngay keo acc di noi khac (PB don, boss the gioi). Neu no bi tinh vao phep do lech
    map/kenh thi party se "luc nao cung lech" -> gom vo tan, dung cai da giet party 11.
    """

    def test_acc_dang_lam_daily_KHONG_tinh_vao_phep_do_map(self):
        accs = [_a("l", la_leader=True, so_member=2), _a("m1"),
                _a("m2", map_id=12061, xong_daily=False, viec_dang_lam=E.VIEC_DAILY)]
        anh = _anh(accs)
        self.assertEqual(anh.maps(), [23001], "acc dang lam daily bi tinh vao -> party luon 'lech map'")

    def test_nam_trong_danh_sach_viec_CHAN(self):
        """Dang lam daily thi engine KHONG ra lenh de len - de no lam not, y `login_chore`."""
        self.assertIn(E.VIEC_DAILY, E.BAN_THI_CHO)

    def test_party_van_lap_duoc_khi_mot_dua_dang_lam_daily(self):
        accs = [_a("l", la_leader=True, so_member=0), _a("m1"),
                _a("m2", map_id=12061, xong_daily=False, viec_dang_lam=E.VIEC_DAILY)]
        v = E.quyet_dinh(_anh(accs))
        self.assertEqual(v["l"], E.VIEC_LAP_PARTY, "mot dua di lam daily lam ca party khong lap duoc")
        self.assertEqual(v["m2"], E.VIEC_DAILY, "cat ngang daily cua no")


class TestThiHanh(unittest.TestCase):
    class _Cli:
        def __init__(self):
            self.running = True
            self._label = "test"

    def test_goi_daily_fn_va_danh_dau_XONG(self):
        c = self._Cli()
        da = []
        E.thi_hanh(c, E.VIEC_DAILY, lambda: True, daily_fn=lambda _c: da.append(1))
        self.assertEqual(da, [1])
        self.assertTrue(c._pe_xong_daily, "khong danh dau -> giao lai mai")

    def test_loi_van_danh_dau_XONG(self):
        """Mot o hong KHONG duoc lam mat ca luot - acc phai di lam viec chinh."""
        c = self._Cli()

        def _no(_c):
            raise RuntimeError("server tu choi")
        E.thi_hanh(c, E.VIEC_DAILY, lambda: True, daily_fn=_no)
        self.assertTrue(c._pe_xong_daily)

    def test_khong_co_ham_thi_KHONG_ket(self):
        c = self._Cli()
        E.thi_hanh(c, E.VIEC_DAILY, lambda: True, daily_fn=None)
        self.assertTrue(c._pe_xong_daily, "khong ai lam duoc ma van giao lai = quay vong vo tan")


class TestNoiVaoEngine(unittest.TestCase):
    def _doc(self, *p):
        with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
            return fh.read()

    def test_engine_duoc_truyen_daily_fn(self):
        s = self._doc("run_party_digioi.py")
        self.assertIn("daily_fn=lambda", s, "khong noi vao -> viec co ma khong ai lam")
        self.assertIn("def _nhiem_vu_ngay_engine_moi(", s)

    def test_dung_DUNG_hai_ham_cua_flow_cu(self):
        s = self._doc("run_party_digioi.py")
        i = s.index("def _nhiem_vu_ngay_engine_moi(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        self.assertIn("c.do_daily_dungeon()", than, "thieu o 1 (PB don 2 luot)")
        self.assertIn("c.claim_daily_quests(heavy=", than, "thieu claim 9 o")

    def test_van_nghe_checkbox_do_daily_cua_user(self):
        s = self._doc("run_party_digioi.py")
        i = s.index("def _nhiem_vu_ngay_engine_moi(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        self.assertIn('"do_daily"', than, "user tat ma bot van lam")

    def test_heavy_theo_dung_luat_flow_cu(self):
        """User chot 27/08: "chi can tele neu can danh world boss thoi" - dang o BAI TRAIN ma
        khong bat boss thi chi lam phan NHE, khong teleport di dau."""
        s = self._doc("run_party_digioi.py")
        i = s.index("def _nhiem_vu_ngay_engine_moi(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        self.assertIn("auto_world_boss", than)
        self.assertIn("_o_bai", than)


if __name__ == "__main__":
    unittest.main()


class TestO5_PHO_BAN_TO_DOI_KHONG_HOAN_NUA(unittest.TestCase):
    """PB to doi KHONG hoan theo lenh dieu phoi nua - y het boss the gioi / PB don da bo tu 14/09.

    Cua hoan cu dat dung vao THOI DIEM LUON DANG GOM: viec nay chay o login chores, ma luc moi
    login ca party dung moi dua mot noi -> dieu phoi ra lenh gom/moi -> HOAN -> va vi chi chay MOT
    LAN, mat luot CA NGAY.

    Do tren log 14/09 (khi bo cua hoan cho boss/PB don): 2739 lan `Boss the gioi: HOAN`,
    3224 lan `Dungeon: HOAN`, o 1 chi 14/152 acc sang duoc -> 96% acc khong xong nhiem vu ngay.
    Do tren log 17/09 (user: "thay danh PB don roi, nhung ko danh PB doi"): o5 hoan 100% so lan.
        23:28:45 [chdumot] (LEADER) pho ban to doi: HOAN - dieu phoi dang ra lenh 'moi'
    """

    def test_khong_con_cua_hoan_trong_handle_o5(self):
        import io as _io
        p = os.path.join(ROOT, "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        i = s.index("def _handle_o5_team(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        # bo docstring roi moi soi phan THI HANH
        than = than.split(chr(34) * 3)[-1]
        self.assertNotIn("if party_dang_gom(pidx):", than,
                         "cua hoan dat dung vao luc LUON DANG GOM -> mat luot PB doi ca ngay")

    def test_van_giao_daily_du_dieu_phoi_dang_gom(self):
        accs = [_a("l", la_leader=True, so_member=0, xong_daily=False),
                _a("m1", xong_daily=False)]
        anh = _anh(accs)
        anh.dp_viec = E.DP_MOI
        v = E.quyet_dinh(anh)
        self.assertTrue(all(x == E.VIEC_DAILY for x in v.values()), v)


class TestKhongDungLop_CHO_BAO_CAO(unittest.TestCase):
    """Engine moi co viec RIENG cho PB to doi (`VIEC_PB_DOI` -> `do_team_dungeon`), goi THANG.

    `claim_daily_quests` goi `_o5_team_fn` -> `_handle_o5_team`, ma ham do chay tren BARRIER BAO
    CAO: moi acc tu gan `_o5_da_xong` len client, leader doc dau vet do. Engine moi khong chay
    `_run_auto_team_dungeons_if_needed` nen khong acc nao co dau vet => leader "coi nhu DA XONG"
    va bo PB.

    Ca that 17/09 party 45 (user: "p45 van ko danh PB doi" -> "con can phai bao nua sao"):
        23:49:19 [chdumot] (LEADER) o5: 5/5 acc chua bao ([cd701..cd705]) -> coi nhu DA XONG
        23:49:32 [party 45] ENGINE: cd701 -> pb_doi     <- duong DUNG, chay song song
    """

    def test_TAT_hook_o5_khi_claim(self):
        import io as _io
        p = os.path.join(ROOT, "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        i = s.index("def _nhiem_vu_ngay_engine_moi(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        self.assertIn("c._o5_team_fn = None", than, "van chay duong cho-bao-cao cua engine cu")
        self.assertIn("finally:", than, "khong tra lai hook -> engine CU cung mat PB doi")

    def test_engine_moi_van_co_viec_PB_DOI_rieng(self):
        self.assertIn(E.VIEC_PB_DOI, E.THU_TU)


class TestKhongTuCheCoChe(unittest.TestCase):
    def test_khong_co_co_cho_o5_tu_che(self):
        """PB to doi gio KHONG hoan nua nen khong can co "quay lai lam o5" - bo di cho gon."""
        import io as _io
        for p in (("run_party_digioi.py",), ("bot", "party_engine.py")):
            with _io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
                self.assertNotIn("_pe_daily_cho_o5", fh.read(), p[-1])


class TestPB_DOI_phai_dat_TRUOC_dp_viec(unittest.TestCase):
    """Nhanh `dp_viec` `return ket` ngay khi dich duoc viec, nen dat PB to doi o SAU no la KHONG
    BAO GIO chay toi: party dang train thi dieu phoi ra `lam` -> `VIEC_TRAIN` cho ca lu -> return.

    Dung cai loi da gap voi nhanh event 16/09 ("p41 van ko vao event").

    Ca that 17/09 party 45 (user: "p45 van ko danh PB doi"): 23:50 daily xong con 7/9 (thieu o5)
    ma tu do khong mot lan nao duoc giao `pb_doi`, trong khi 23:48 - luc dieu phoi CHUA quyet
    duoc - thi co.
    """

    def test_dang_train_van_duoc_giao_PB_DOI(self):
        accs = [_a("l", la_leader=True, so_member=2), _a("m1"), _a("m2")]
        anh = _anh(accs)
        anh.dp_viec = E.DP_LAM          # dieu phoi bao "cu danh di"
        anh.pb_doi_level = 20           # ma PB to doi con luot
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_PB_DOI, "dp_viec nuot mat nhanh PB to doi")
        self.assertEqual(v["m1"], E.VIEC_PB_DOI_THEO)

    def test_dang_gom_cung_van_duoc_giao(self):
        """PB moi theo roleId: KHONG can cung map, cung kenh, hay du party thuong truoc."""
        accs = [_a("l", la_leader=True, so_member=0, map_id=12001), _a("m1", map_id=23001)]
        anh = _anh(accs)
        anh.dp_viec = E.DP_GOM
        anh.pb_doi_level = 50
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_PB_DOI)

    def test_het_luot_thi_KHONG_giao(self):
        accs = [_a("l", la_leader=True, so_member=2), _a("m1")]
        anh = _anh(accs)
        anh.dp_viec = E.DP_LAM
        anh.pb_doi_level = None         # None = chua ket luan / het luot
        self.assertNotIn(E.VIEC_PB_DOI, E.quyet_dinh(anh).values())

    def test_dat_TRUOC_nhanh_dp_viec_trong_ma_nguon(self):
        import io as _io
        p = os.path.join(ROOT, "bot", "party_engine.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        self.assertLess(s.index("if anh.pb_doi_level is not None"), s.index("if anh.dp_viec:"),
                        "PB to doi dat sau dp_viec -> khong bao gio chay toi")


class TestPB_DOI_phai_DU_CA_PARTY(unittest.TestCase):
    """CA PARTY phai CON LUOT + DU CAP moi vao PB to doi - y bon cua cua flow cu
    (`_handle_auto_team_dungeon`): doc luot TUNG member, thieu status cua ai do thi BO QUA, va chi
    chay khi `len(need) == len(members)`.

    Truoc day engine moi chi doc luot cua MOI LEADER -> leader tao phong roi moi, nhung member da
    het luot / chua du cap thi khong vao duoc => phong thieu nguoi, leader huy roi tao lai.

    Ca that 20/09 party 41 (user: "p41, di PB khi co 1 dua ben ngoai"):
        11:24:49 [dtsau] (LEADER) roster phong pho ban chi 3/4 member sau 8.0s -> THIEU nguoi
        11:25:10 [dtsau] (LEADER) roster phong pho ban chi 1/4 member sau 8.0s -> THIEU nguoi
        11:25:27 ENGINE: 'pb_doi_theo' giao lai 80 lan lien tiep cho dt807
    """

    class _Cli:
        def __init__(self, con=1, loaded=True):
            self.running = True
            self._label = "x"
            self._con = con
            self.mission_steps_loaded = loaded

        def team_dungeon_remaining(self, lv):
            return self._con

    def _eng(self, clients, du_cap=True):
        return E.PartyEngine(
            40, lambda: [("u%d" % i, c, i == 0) for i, c in enumerate(clients)],
            pb_doi_levels=(20,), hoi_du_cap=lambda _lv: du_cap)

    def test_ca_party_con_luot_thi_CHAY(self):
        eng = self._eng([self._Cli(), self._Cli(), self._Cli()])
        self.assertEqual(eng._pb_doi_level(), 20)

    def test_MOT_dua_het_luot_thi_THOI(self):
        eng = self._eng([self._Cli(), self._Cli(con=0), self._Cli()])
        self.assertIsNone(eng._pb_doi_level(), "vao PB voi mot dua ben ngoai")

    def test_MOT_dua_chua_co_status_thi_CHUA_KET_LUAN(self):
        eng = self._eng([self._Cli(), self._Cli(loaded=False)])
        self.assertIsNone(eng._pb_doi_level())

    def test_chua_DU_CAP_thi_THOI(self):
        """Server khong cho acc duoi cap ready - co tao phong cung chi ra "ready 0/4"."""
        eng = self._eng([self._Cli(), self._Cli()], du_cap=False)
        self.assertIsNone(eng._pb_doi_level())


class TestPB_DOI_check_SAU_daily(unittest.TestCase):
    """User chot 20/09: "check PB doi sau daily quest" - ve THU TU KIEM TRA trong mot nhip.

    Nhanh PB to doi phai dung SAU nhanh nhiem vu ngay (0b2), KHONG phai "doi ca party xong daily
    moi duoc vao PB".

    CHI SUA ENGINE MOI - `run_account` giu nguyen thu tu cu.
    """

    def test_nhanh_daily_dung_TRUOC_nhanh_PB_trong_ma_nguon(self):
        import io as _io
        p = os.path.join(ROOT, "bot", "party_engine.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        self.assertLess(s.index("ket[a.username] = VIEC_DAILY"),
                        s.index("if anh.pb_doi_level is not None"),
                        "check PB to doi dung TRUOC check nhiem vu ngay")

    def test_con_dua_DANG_LAM_VIEC_LE_thi_CHUA_mo_phong(self):
        """Dua dang lam viec le KHONG nhan `pb_doi_theo`, ma leader van moi du 4 -> server chi
        cong nhan nhung dua vao duoc, leader do roster thay thieu roi HUY, tao lai.

        Ca that 20/09 party 41 (user: "van thay 3 dua trong PB, 2 dua ben ngoai"):
            11:43:23 dtsau@62013(L) dtbay@62013 dt9ch@62013 | dttam@22000* dtmuoi@22000*
            11:45:54 (LEADER) lv110 member ready 4/4 -> START      <- bot TU bao ready
            11:46:06 (LEADER) roster phong pho ban chi 2/4 -> THIEU nguoi, HUY danh de gom lai
        """
        accs = [_a("l", la_leader=True, so_member=2),
                _a("m1"), _a("m2", xong_daily=False)]
        anh = _anh(accs)
        anh.pb_doi_level = 20
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_PB_DOI, v.values(), "mo phong PB khi con dua dang ban viec le")
        self.assertEqual(v["m2"], E.VIEC_DAILY, "cat ngang viec le cua no")

    def test_du_nguoi_RANH_thi_mo_phong(self):
        accs = [_a("l", la_leader=True, so_member=2), _a("m1"), _a("m2")]
        anh = _anh(accs)
        anh.pb_doi_level = 20
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_PB_DOI)
        self.assertEqual(v["m1"], E.VIEC_PB_DOI_THEO)

    def test_KHONG_dung_toi_engine_cu(self):
        """`run_account` giu nguyen thu tu cu cua no."""
        import io as _io
        p = os.path.join(ROOT, "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        i = s.index("def run_account(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        self.assertNotIn("xong_daily", than, "da dung vao thu tu cua engine cu")


class TestCHUA_DU_ACC_LOGIN_thi_KHONG_lap_party(unittest.TestCase):
    """Acc DANG LOGIN phai tinh la THIEU - chua duoc ket luan "ca party cung map/kenh".

    Phep dem map/kenh chi nhin acc DANG SONG, nen khi mot dua chua vao world thi ket luan do dua
    tren mau khong day du: dua chua login co the o kenh khac han. Lap doi luc nay la lap thieu
    nguoi, roi dua kia vao lai phai gom lai tu dau.

    Flow cu co san `_thieu_acc_song`:
        `_con_kha_nang` = acc con THREAD song (`is_account_running`) - acc dang login VAN duoc tinh
        `song`          = acc da co client va vao world
        thieu <=> len(song) < len(_con_kha_nang)
    va no da lo ca "acc TAT han thi khong cho" (cho mot acc da tat la cho vinh vien).
    Engine moi HOI LAI ham do, khong tu dem.

    Ca that 20/09 party 55 (user: "ca party chua cung map cung kenh ma da lap party"):
        12:31:20 ENGINE: tik901/903/904/905 -> lap_party    <- tik902 CHUA vao world
        12:33:17 [tik902] chua vao world - SERVER CHAN TOC DO DANG NHAP (lan 1)
    """

    def test_thieu_acc_thi_DUNG_YEN(self):
        accs = [_a("l", la_leader=True, so_member=0), _a("m1"), _a("m2")]
        anh = _anh(accs)
        anh.thieu_acc_song = True
        v = E.quyet_dinh(anh)
        self.assertNotIn(E.VIEC_LAP_PARTY, v.values(), "lap doi khi con dua chua vao world")

    def test_du_acc_roi_thi_lap_binh_thuong(self):
        accs = [_a("l", la_leader=True, so_member=0), _a("m1"), _a("m2")]
        v = E.quyet_dinh(_anh(accs))
        self.assertEqual(v["l"], E.VIEC_LAP_PARTY)

    def test_ENGINE_TU_BIET_khong_hoi_ai(self):
        """Mot luong nam ca party thi phai TU BIET du acc hay chua - khong hoi qua callback.

        `_clients_cua_party` tra ca acc CHUA co client (dang login) va bo acc DA TAT HAN, nen
        engine chi can nhin anh chup la biet.
        """
        import io as _io
        p = os.path.join(ROOT, "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        i = s.index("def _clients_cua_party(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        self.assertIn("is_account_running(u)", than, "khong tra acc dang login -> engine mu")
        self.assertIn("ra.append((u, None))", than)
        self.assertNotIn("hoi_thieu_acc", s, "van di hoi thay vi tu biet")

    def test_acc_DA_TAT_HAN_thi_khong_cho(self):
        """Cho mot acc da tat la cho vinh vien - `_clients_cua_party` phai bo no ra."""
        import io as _io
        p = os.path.join(ROOT, "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            s = fh.read()
        i = s.index("def _clients_cua_party(")
        than = s[i:s.index(chr(10) + "def ", i + 10)]
        self.assertIn("elif is_account_running(u):", than,
                      "acc da tat van duoc tra ve -> party khong bao gio du")


class TestGOM_giao_lai_cho_toi_khi_TOI_NOI(unittest.TestCase):
    """Acc chua ve toi diem gom thi con phai ve - engine giao LAI moi nhip.

    Flow cu lap NGAY TRONG hanh dong (`_do_reform`: `while not _ab() and c.current_map !=
    _target_city: ... time.sleep(10)`), vi ben do `reform_gen` bump MOT NHAT roi cooldown 180s.
    Engine moi khong co vong do - no giao viec moi nhip - nen phai giao LAI, khong thi acc nao
    tele fail (dang danh / thanh chua mo / server chan) se dung im toi 3 phut sau.

    Ca that 20/09 party 42 (user: "leader o trac quan, member o truong sa"):
        13:05:14 gen 20: viec=gom - ca party dam chan o THANH 12001 1095s   <- 18 phut
        13:05:14 ENGINE: dieu phoi bump reform_gen -> ca party thi hanh
        13:05:26 ENGINE: luu401..luu405 -> nghi   <- leader van 12001, member 23001

    KHONG quay vong nhu p43 16/09: `giao()` chi HUY viec khi viec DOI, ma day van la `ve_thanh`
    voi CUNG mot dich (`chot_thanh_tap_ket` co cache). Cai gay ra p43 la dich NHAY lien tuc.
    """

    def test_acc_lac_khoi_diem_gom_thi_VE_THANH(self):
        accs = [_a("l", la_leader=True, so_member=0, map_id=12001),
                _a("m1", map_id=23001), _a("m2", map_id=23001)]
        anh = _anh(accs, thanh_dich=23001)
        anh.dp_viec = E.DP_GOM
        v = E.quyet_dinh(anh)
        self.assertEqual(v["l"], E.VIEC_VE_THANH, "leader ket o thanh khac, khong ai nhac lai")

    def test_dua_DA_VE_thi_de_yen(self):
        """Bat tele lai la tu pha: teleport bat buoc `leave_party()`."""
        accs = [_a("l", la_leader=True, so_member=0, map_id=12001),
                _a("m1", map_id=23001)]
        anh = _anh(accs, thanh_dich=23001)
        anh.dp_viec = E.DP_GOM
        self.assertNotEqual(E.quyet_dinh(anh).get("m1"), E.VIEC_VE_THANH)

    def test_CA_PARTY_da_ve_thi_thoi(self):
        accs = [_a("l", la_leader=True, so_member=0, map_id=23001),
                _a("m1", map_id=23001)]
        anh = _anh(accs, thanh_dich=23001)
        anh.dp_viec = E.DP_GOM
        self.assertNotIn(E.VIEC_VE_THANH, E.quyet_dinh(anh).values())

    def test_da_o_dich_thi_thi_hanh_KHONG_tele_lai(self):
        class _Cli:
            running = True
            _label = "x"
            current_map = 23001
            goi = 0

            def go_to_town(self, city, flag):
                type(self).goi += 1
                return True

        self.assertTrue(E.thi_hanh(_Cli(), E.VIEC_VE_THANH, lambda: True, dich=(23001, 4)))
        self.assertEqual(_Cli.goi, 0, "tele lai khi da dung o dich = tu pha party")
