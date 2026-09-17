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


def _anh(accs, pha=E.PHA_TRAIN, **kw):
    return E.AnhParty(50, accs, can_bao_nhieu=len(accs) - 1, co_spot=True, pha=pha, **kw)


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
        self.assertLess(s.index("if anh.pb_doi_level is not None:"), s.index("if anh.dp_viec:"),
                        "PB to doi dat sau dp_viec -> khong bao gio chay toi")
