"""DANG CO ACC BAY GIUA HAI KENH -> GIU NGUYEN DICH, khong chot lai.

`current_channel` cua acc vua goi `switch_channel` la so DO DANG: no da `leave_party()` va roi kenh
cu, chua vao kenh moi. Moi phep dem tren bang do deu la rac.

Ca that 08/09 party 1 (user: "p1 sao leader deo tap trung") - BA dich trong TAM giay:

    00:42:40 [party 1] party lech kenh {5: 2, 7: 1} -> CHOT kenh dich = 5
    00:42:46 [party 1] party lech kenh {5: 2, 7: 3} -> CHOT kenh dich = 7
    00:42:48 [party 1] party lech kenh {5: 2, 7: 3} -> CHOT kenh dich = 3

Hai dong cuoi CUNG mot phan bo ma hai ket luan trai nguoc. Moi lan doi dich la mot lan leader
`leave_party()` (luat `Team.IsAlone`) - tuc tu tay pha party vua gom.

Han kien nhan 45s (`KENH_DICH_KIEN_NHAN_SEC`) khong cuu duoc, vi nhanh "dang chung kenh" o TREN
xoa `kenh_dich` ve None truoc, roi nhip sau vao chot lai tu dau. Nen guard phai dung o DAU ham.
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _C:
    def __init__(self, ch, dang_doi=False):
        self.running = True
        self.current_map = 12001
        self.current_channel = ch
        self.channels = {}
        self.party_members = []
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0
        # `_dang_doi_kenh` doc dau vet nay tren client
        self._doi_kenh_tu = time.time() if dang_doi else 0.0
        self.hoi = 0

    def in_combat(self, *_a, **_k):
        return False

    def request_channel_list(self):
        self.hoi += 1


class TestGiuDichKhiDangBayGiuaKenh(unittest.TestCase):
    PARTY = 5151
    ACCS = ("a", "b", "c", "d", "e")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        R.config.PARTY_CONFIG = self._pc

    def _song(self, chans, dang_doi=()):
        for i, (u, ch) in enumerate(zip(self.ACCS, chans)):
            R.account_clients[u] = _C(ch, dang_doi=i in dang_doi)
        return [(u, R.account_clients[u]) for u in self.ACCS]

    def test_dang_doi_thi_GIU_dich_cu(self):
        song = self._song([5, 5, 7, 7, 7], dang_doi=(2,))
        self.st["kenh_dich"] = 5
        self.st["kenh_dich_luc"] = time.time()
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 5)

    def test_dang_doi_thi_KHONG_xoa_dich(self):
        """Xoa ve None = mat luon han kien nhan -> nhip sau chot lai tu dau."""
        song = self._song([5, 5, 7, 7, 7], dang_doi=(2,))
        self.st["kenh_dich"] = 5
        self.st["kenh_dich_luc"] = time.time()
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertEqual(self.st["kenh_dich"], 5)

    def test_acc_CHUA_RO_kenh_thi_khong_ket_luan_chung_kenh(self):
        """Noi lo "bang thu gon lai con MOT kenh -> tuong chung kenh gia" duoc chan o GOC chu khong
        phai bang guard: doi map la `current_channel` ve None (xem `_on_...` trong client), va vong
        dem gap `not ch` thi return ngay - khong xoa dich, khong chot gi."""
        song = self._song([5, 5, 5, 5, 5], dang_doi=(4,))
        R.account_clients[self.ACCS[4]].current_channel = None    # dang bay giua hai kenh
        self.st["kenh_dich"] = 7
        self.st["kenh_dich_luc"] = time.time()
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertEqual(self.st["kenh_dich"], 7)

    def test_kenh_dich_bi_bao_DAY_thi_PHAI_chot_lai(self):
        """Guard nay tung giu dich VO DIEU KIEN va tu no thanh mot bug moi (08/09).

        Acc khong vao duoc kenh day thi no RETRY lien tuc, ma retry lien tuc = luc nao cung "dang
        doi kenh" -> guard giu dich vinh vien. Party 3 ket 6 phut ruoi khong mot lenh nao:
            04:21:11 [party 3] kenh dich 27 qua han nhung DA GOM DUOC 3/5 -> GIA HAN  <- lenh cuoi
            04:27:04 [batbat]  Doi kenh 27 THAT BAI: khu da day nguoi (result=4)
            04:27:14 [hoathap] Doi kenh 27 THAT BAI: khu da day nguoi (result=4)
        User: "neu thay co dua ko ve duoc kenh do kenh day -> chon lai kenh di".
        """
        song = self._song([27, 27, 27, 5, 5], dang_doi=(3, 4))
        self.st["kenh_dich"] = 27
        self.st["kenh_dich_luc"] = time.time()
        for i in (3, 4):                       # hai acc bi server tu choi: kenh DAY
            _c = R.account_clients[self.ACCS[i]]
            _c._chan_switch_result = 4
            _c._chan_switch_target = 27
            _c._chan_switch_luc = time.time()
        self.assertNotEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 27,
                            "van giu kenh da DAY -> hai acc retry mai, party khong bao gio gom du")

    def test_ma_4_thi_HOI_LAI_danh_sach_kenh_ngay(self):
        """Server bao DAY tuc bang `c.channels` dang sai; chot tiep bang so cu la lai chon dung
        kenh do. Phai ep hoi lai `S:007-001` chu khong doi het `DS_KENH_LAM_MOI_SEC`."""
        song = self._song([27, 27, 27, 5, 5], dang_doi=(3,))
        self.st["kenh_dich"] = 27
        self.st["kenh_dich_luc"] = time.time()
        self.st["ds_kenh_luc"] = time.time()
        _c = R.account_clients[self.ACCS[3]]
        _c._chan_switch_result = 4
        _c._chan_switch_target = 27
        _c._chan_switch_luc = time.time()
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertEqual(sum(_c.hoi for _u, _c in song), 1,
                         "khong hoi lai danh sach kenh -> chot lai bang so cu, lai dam vao kenh day")

    def test_KHONG_co_ma_4_thi_van_giu_cach_quang(self):
        """Hoi lai moi nhip = spam `0x07 0100` -> nguy co ma 13. Chi ep hoi khi co ma 4."""
        song = self._song([27, 27, 27, 5, 5])
        self.st["ds_kenh_luc"] = time.time()
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertEqual(sum(_c.hoi for _u, _c in song), 0)

    def test_DA_CHUNG_KENH_thi_XOA_DICH_du_dang_co_acc_doi_kenh(self):
        """Ca party cung mot kenh roi = XONG. Khong con gi de chot.

        Guard nay tung dat TREN nhanh "da chung kenh" va tu no thanh mot bug (08/09 party 11):
        acc bi server tu choi doi kenh se THU LAI lien tuc, tuc LUC NAO CUNG "dang doi kenh", nen
        ham thoat ngay o guard va KHONG BAO GIO chay toi cho xoa dich.
            14:07:15 [party 11] gen 31: pha=train map=21011 kenh=1 viec=lam   <- ca party kenh 1
            14:09:44..14:10:08  ca 5 acc: "Doi kenh 27 THAT BAI: khong co khu do (result=2)"
        User: "m ko thay ca lu da cung kenh 1 roi a, tim kenh khac lam cai lon gi nua".
        """
        song = self._song([1, 1, 1, 1, 1], dang_doi=(0, 1, 2, 3, 4))
        self.st["kenh_dich"] = 27
        self.st["kenh_dich_luc"] = time.time()
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertIsNone(self.st["kenh_dich"],
                          "ca party da chung kenh ma van bam kenh dich cu")

    def test_khong_ai_dang_doi_thi_VAN_chot_binh_thuong(self):
        song = self._song([5, 5, 7, 7, 7])
        self.assertIsNotNone(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song))

    def test_chua_co_dich_thi_tra_None_chu_khong_no(self):
        song = self._song([5, 5, 7, 7, 7], dang_doi=(2,))
        self.assertIsNone(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song))


class TestMoiKetQuaDoiKenhDeuDuocXU_LY(unittest.TestCase):
    """Moi lan doi kenh phai ket thuc bang MOT ket qua, va ket qua nao cung phai duoc XU LY.

    User 08/09: "giu nguyen dich cai lon me may, moi lan doi kenh phai duoc thanh cong hay fail va
    vi sao fail chu" -> "co the check ket qua ma ko dung, dieu phoi ngu the a".

    Bang ma `S:007-002`: 0 OK · 1 trung kenh dang o (cung la OK) · 2 khong co khu · 3 dang to doi ·
    4 kenh day. Cong them -1 = `switch_channel` het luot ma server IM LANG (timeout) - ban cu
    khong ghi gi ca, nen dieu phoi khong bao gio biet lenh da that bai.
    """

    def _c(self, r, target=27):
        c = _C(5, dang_doi=True)
        c._chan_switch_result = r
        c._chan_switch_target = target
        c._chan_switch_luc = time.time()
        return c

    def test_ma_4_va_TIMEOUT_deu_vao_so_den(self):
        day4, _, _ = R._doc_ket_qua_doi_kenh([("a", self._c(4))])
        dayT, _, _ = R._doc_ket_qua_doi_kenh([("a", self._c(-1))])
        self.assertEqual(day4, {27})
        self.assertEqual(dayT, {27}, "timeout bi bo qua -> dieu phoi giu dich mot kenh vao khong duoc")

    def test_ma_2_vao_so_den_va_bat_co(self):
        day, _ma3, ma2 = R._doc_ket_qua_doi_kenh([("a", self._c(2))])
        self.assertEqual(day, {27}, "ma 2 chi bat co chung, so kenh khong ai ghi -> chot lai dung no")
        self.assertTrue(ma2)

    def test_ma_3_bat_co_rieng(self):
        day, ma3, _ = R._doc_ket_qua_doi_kenh([("a", self._c(3))])
        self.assertTrue(ma3)
        self.assertEqual(day, set(), "ma 3 la loi CUA MINH (dang to doi), khong phai kenh hong")

    def test_ma_0_va_1_khong_lam_kenh_thanh_hong(self):
        for r in (0, 1):
            day, ma3, ma2 = R._doc_ket_qua_doi_kenh([("a", self._c(r))])
            self.assertEqual((day, ma3, ma2), (set(), False, False), "ma %s" % r)

    def test_CO_KET_QUA_thi_khong_con_la_dang_doi_kenh(self):
        """"Dang do" = da gui lenh MA CHUA CO ket qua. Ban cu chi xem "vua bam lenh trong 25s" nen
        acc bi tu choi (thu lai lien tuc) thi LUC NAO CUNG dang doi kenh."""
        self.assertFalse(R._dang_doi_kenh([("a", self._c(4))]))

    def test_CHUA_co_ket_qua_thi_van_la_dang_doi_kenh(self):
        c = _C(5, dang_doi=True)          # vua gui lenh, chua nhan `S:007-002`
        self.assertTrue(R._dang_doi_kenh([("a", c)]))

    def test_ket_qua_CU_khong_tinh_la_da_xong(self):
        """Ma cua LAN TRUOC (truoc `_doi_kenh_tu`) khong chung minh lan NAY da xong."""
        c = self._c(4)
        c._chan_switch_luc = c._doi_kenh_tu - 5.0
        self.assertTrue(R._dang_doi_kenh([("a", c)]))


class TestThuTuGuard(unittest.TestCase):
    """Guard phai dat SAU nhanh "da chung kenh".

    Ban dau toi dat no o DAU ham, voi ly do "nhanh chung kenh xoa `kenh_dich` mat roi". Ly do do
    SAI: ca party da chung kenh thi xoa dich la DUNG - het viec, khong con gi de chot. Dat guard o
    tren bien no thanh mot cai bay: acc bi tu choi doi kenh thu lai lien tuc -> luc nao cung "dang
    doi kenh" -> ham thoat ngay o guard, KHONG BAO GIO toi cho xoa dich (party 11, 08/09).

    Con noi lo ban dau (acc bay giua kenh lam bang `dem` trong nhu "chung kenh" gia) da duoc chan o
    goc: doi map la `current_channel` ve None, va vong dem `dem` gap `not ch` thi return ngay.
    """

    def test_guard_dat_SAU_nhanh_da_chung_kenh(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i0 = s.find("def _dieu_phoi_chot_kenh(")
        self.assertGreater(i0, 0)
        i_guard = s.find("if song and _dang_doi_kenh(song):", i0)
        i_xoa = s.find('st["kenh_dich"] = None', i0)
        self.assertGreater(i_guard, i0, "khong co guard trong ham chot kenh")
        self.assertGreater(i_guard, i_xoa,
                           "guard dat truoc nhanh 'da chung kenh' -> party chung kenh roi van bam "
                           "kenh dich cu mai")


if __name__ == "__main__":
    unittest.main()
