"""DIEU PHOI phai bat duoc "party DUNG HINH", khong chi bat "lech map/kenh".

Ban cu `_dieu_phoi_quyet` chi xet ba thu: lech map · lech kenh · thieu nguoi trong doi. Ba thu do
deu BINH THUONG thi no ket luan `VIEC_LAM` va khong lam gi nua - ke ca khi ca party dung im hang
gio.

Ca that 07/09 party 1 - 44 PHUT (12:36:15 -> 13:20:31, 327 luot log):

    4 acc : reform: CHO ca party ve Trường Sa (4/5) - THIEU: brubb46677
            [map=23001, da ve Trường Sa, cho ca party (37s)]
    brub  : (member) CHO leader quyet dinh (leader co the dang reconnect)...

CA NAM DUA DEU DA O TRUONG SA (23001), cung kenh, du doi. brub cho leader; leader cho brub. Con so
"(37s)" trong log dung im suot 44 phut - dau hieu ro rang la brub ket trong vong cho nen khong cap
nhat gi nua. Dieu phoi khong thay gi "lech" nen im theo.

Sua hai dau:
  1. Bo vong `while not (leader_ok or leader_bad)` - cho VO HAN, khong co loi ra cap party (L9).
  2. Dieu phoi do TIEN DO: (map, vi tri, dang danh) cua tung acc; y het nhau qua
     KE_HOACH_DUNG_HINH_SEC thi PHA THE bang lenh gom / dong bo.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class _St:
    in_battle = False


class _C:
    def __init__(self, map_id=23001, pos=(500, 600), ch=1, roster=1):
        self.current_map = map_id
        self.pos = pos
        self.current_channel = ch
        self.running = True
        self.state = _St()
        # roster SERVER gui ve (`0x0d`) - dieu phoi doc cai NAY, khong doc bo dem trong cua bot
        self.party_members = [b"x" * 8] * roster

    def in_combat(self, *_a, **_k):
        return False


class TestAccDungHinh(unittest.TestCase):
    """Do TUNG ACC, khong do ca party. Ban dau do ca party (mot dau vet chung) nen chi can MOT acc
    dong day la coi nhu "co tien do" -> lot luoi dung cai can bat: party 23 (07/09, 33 phut) co
    leader DANH THAT lien tuc trong khi 4 member dung im cho no."""

    def setUp(self):
        self.st = {}

    def _do(self, song, han=1.0):
        return R._acc_dung_hinh(self.st, song, han)

    def test_lan_dau_chua_ket_luan(self):
        self.assertEqual(self._do([("a", _C())]), [])

    def test_dung_im_qua_han_thi_bao(self):
        c = _C(); song = [("a", c)]
        self._do(song)
        self.st["nhip_acc"]["a"] = (self.st["nhip_acc"]["a"][0], time.time() - 10)
        self.assertEqual(self._do(song), ["a"])

    def test_co_di_chuyen_thi_khong_bao(self):
        c = _C(); song = [("a", c)]
        self._do(song)
        self.st["nhip_acc"]["a"] = (self.st["nhip_acc"]["a"][0], time.time() - 10)
        c.pos = (900, 900)
        self.assertEqual(self._do(song), [])

    def test_doi_map_thi_khong_bao(self):
        c = _C(); song = [("a", c)]
        self._do(song)
        self.st["nhip_acc"]["a"] = (self.st["nhip_acc"]["a"][0], time.time() - 10)
        c.current_map = 23872
        self.assertEqual(self._do(song), [])

    def test_acc_DANG_DANH_khong_bi_tinh(self):
        """Trong mot tran, map/vi tri dung yen la binh thuong - co tran dai vai phut."""
        c = _C(); c.state.in_battle = True
        song = [("a", c)]
        self._do(song)
        self.st["nhip_acc"]["a"] = (self.st["nhip_acc"]["a"][0], time.time() - 10)
        self.assertEqual(self._do(song), [])

    def test_MOT_acc_ket_du_ca_party_dang_chay(self):
        """Chinh la ca party 23: leader danh that, 4 member dung im."""
        lead = _C(); lead.state.in_battle = True
        m1, m2 = _C(pos=(700, 700)), _C(pos=(710, 700))
        song = [("lead", lead), ("m1", m1), ("m2", m2)]
        self._do(song)
        for u in ("m1", "m2"):
            self.st["nhip_acc"][u] = (self.st["nhip_acc"][u][0], time.time() - 10)
        self.assertEqual(sorted(self._do(song)), ["m1", "m2"])

    def test_acc_bien_mat_thi_bo_moc_cu(self):
        song = [("a", _C()), ("b", _C(pos=(700, 700)))]
        self._do(song)
        self._do([("a", _C())])
        self.assertNotIn("b", self.st["nhip_acc"])

    def test_client_hong_khong_lam_no_ham(self):
        class _Hong:
            current_map = 23001
            pos = (1, 2)
        self._do([("x", _Hong())])   # khong duoc nem


class TestRaLenhKhiDungHinh(unittest.TestCase):
    PARTY = 771

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in ("a", "b")]
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

    def _song(self, map_id=23872):
        """Map 23872 = bai train (KHONG phai thanh) -> khong dinh nhanh "dam chan o thanh"."""
        for u in ("a", "b"):
            R.account_clients[u] = _C(map_id=map_id)
        self.st["n_members"] = 1
        return [(u, R.account_clients[u]) for u in ("a", "b")]

    def test_vua_dung_thi_CHUA_ra_lenh(self):
        song = self._song()
        kh, _ly, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertEqual(kh["viec"], R.VIEC_LAM, "vua doc lan dau da keu ket")

    def _lui_dong_ho(self, *accs):
        for u in (accs or tuple(self.st.get("nhip_acc") or ())):
            _v = self.st["nhip_acc"][u]
            self.st["nhip_acc"][u] = (_v[0], time.time() - R.KE_HOACH_DUNG_HINH_SEC - 5)

    def test_dung_qua_han_thi_RA_LENH_GOM(self):
        song = self._song()
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self._lui_dong_ho()
        kh, ly_do, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertEqual(kh["viec"], R.VIEC_GOM)
        self.assertIn("DUNG HINH", ly_do)

    def test_co_nhuc_nhich_thi_dong_ho_chay_lai(self):
        song = self._song()
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self._lui_dong_ho()
        for _u, c in song:                                # ca party deu di chuyen
            c.pos = (900, 900)
        kh, _ly, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertEqual(kh["viec"], R.VIEC_LAM)

    def test_ra_lenh_roi_thi_tinh_lai_tu_dau(self):
        """Khong duoc ban lenh gom moi nhip sau khi da qua han mot lan."""
        song = self._song()
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self._lui_dong_ho()
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        kh, _ly, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertEqual(kh["viec"], R.VIEC_LAM, "ban lenh gom lien tuc -> bao reform")


class TestDamChanODuoiThanh(unittest.TestCase):
    """User 07/09: "ko lech map ko lech kenh nhung ko party va ko thuc hien dung mode duoc chon thi
    phai xu ly chu". Ba phep do cu chi so cac acc VOI NHAU, khong so voi VIEC PHAI LAM."""

    PARTY = 772

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in ("a", "b")]
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

    def _song(self, map_id):
        for u in ("a", "b"):
            R.account_clients[u] = _C(map_id=map_id)
        return [(u, R.account_clients[u]) for u in ("a", "b")]

    def test_dam_chan_o_thanh_qua_lau_thi_RA_LENH(self):
        song = self._song(23001)          # Truong Sa
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.st["o_thanh_tu"] = time.time() - R.KE_HOACH_DUNG_HINH_SEC - 5
        kh, ly_do, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertEqual(kh["viec"], R.VIEC_GOM)
        self.assertIn("THANH", ly_do)

    def test_o_BAI_TRAIN_thi_khong_dinh(self):
        song = self._song(23872)
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.st["o_thanh_tu"] = time.time() - R.KE_HOACH_DUNG_HINH_SEC - 5
        kh, _ly, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertNotIn("THANH", str(_ly or ""))

    def test_roi_thanh_thi_dong_ho_XOA(self):
        song = self._song(23001)
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        for _u, c in song:
            c.current_map = 23872
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertFalse(self.st.get("o_thanh_tu"))

    def test_MOT_acc_ra_khoi_thanh_la_chua_tinh(self):
        """Con acc dang di duong thi party van dang lam viec - chua phai dam chan."""
        song = self._song(23001)
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.st["o_thanh_tu"] = time.time() - R.KE_HOACH_DUNG_HINH_SEC - 5
        R.account_clients["a"].current_map = 23872
        kh, _ly, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertNotIn("THANH", str(_ly or ""))


class TestDoiDuTheoROSTER_SERVER(unittest.TestCase):
    """`joined_member_count()` doc `_PARTY_JOINED` - bang do CHINH BOT ghi, va no om STALE: party
    tan ma khong ai unmark thi bot van tuong con du.

    Ca that 07/09 party 1 (user: "du doi cai lon, bon no co cung party deo dau"): dieu phoi ket
    luan "du doi" -> VIEC_LAM -> im 44 phut, trong khi log cua chinh leader lap lai lien tuc:
        13:26:49 [xGAx] KHONG o party nao (roster server + local deu rong)"""

    def test_roster_rong_la_THIEU_DOI(self):
        song = [("a", _C(roster=0)), ("b", _C(roster=0))]
        self.assertTrue(R._thieu_doi(0, song))

    def test_MOT_acc_roster_rong_cung_la_thieu(self):
        song = [("a", _C(roster=2)), ("b", _C(roster=2)), ("c", _C(roster=0))]
        self.assertTrue(R._thieu_doi(0, song))

    def test_du_roster_thi_KHONG_thieu(self):
        song = [("a", _C(roster=2)), ("b", _C(roster=2)), ("c", _C(roster=2))]
        self.assertFalse(R._thieu_doi(0, song))

    def test_mot_acc_thi_khong_can_doi(self):
        self.assertFalse(R._thieu_doi(0, [("a", _C(roster=0))]))

    def test_KHONG_dung_bo_dem_trong_cua_bot(self):
        s = _src()
        i = s.find("elif song and _thieu_doi(pidx, song):")
        self.assertGreater(i, 0, "dieu phoi van dem doi bang joined_member_count")
        self.assertIn("party_members", _src()[s.find("def _thieu_doi("):][:1200])


class TestLeaderDisLaMatDoi(unittest.TestCase):
    """User chot 07/09: "khi thang leader dis va o trang thai dang login thi chac chan tat ca deu
    ko co party, server tu giai tan party roi". Doi truong roi khoi the gioi thi server thao doi.

    Khong the trong vao roster de biet: member con song chi thay `0x0d` khi server chiu gui, va
    trong luc do roster cua ho con giu so cu -> bot ngoi im. Day la ket luan SUY RA TU SU KIEN."""

    PARTY = 773

    def setUp(self):
        self._pa = R.party_accounts
        # a = LEADER (phan tu thu 3 = is_leader)
        R.party_accounts = lambda pidx: [("a", "p", True, True), ("b", "p", False, False),
                                         ("c", "p", False, False)]
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

    def test_leader_vang_mat_la_mat_doi(self):
        song = [("b", _C()), ("c", _C())]        # a (leader) dang relogin
        self.assertTrue(R._leader_dang_rot(self.PARTY, song))

    def test_leader_con_song_thi_khong_ket_luan(self):
        song = [("a", _C()), ("b", _C()), ("c", _C())]
        self.assertFalse(R._leader_dang_rot(self.PARTY, song))

    def test_khong_acc_nao_song_thi_khong_ket_luan(self):
        """Ca party cung dang relogin - khong phai ca "mat doi", de reconnect lo."""
        self.assertFalse(R._leader_dang_rot(self.PARTY, []))

    def test_dieu_phoi_ra_lenh_MOI_ngay(self):
        for u in ("b", "c"):
            R.account_clients[u] = _C(map_id=23872, roster=2)   # roster con giu so CU
        song = [(u, R.account_clients[u]) for u in ("b", "c")]
        kh, ly_do, _lt = R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertEqual(kh["viec"], R.VIEC_MOI)
        self.assertIn("LEADER", ly_do)

    def test_xoa_so_nho_khi_doi_da_tan(self):
        """Giu nguoi cua party da tan trong `_PARTY_JOINED` = lai tai dien bug L2d."""
        for u in ("b", "c"):
            R.account_clients[u] = _C(map_id=23872, roster=2)
            R.account_clients[u].self_entity = u.encode()
            R.mark_joined(self.PARTY, u.encode())
        song = [(u, R.account_clients[u]) for u in ("b", "c")]
        R._dieu_phoi_quyet(self.PARTY, self.st, song, None)
        self.assertEqual(R.joined_member_count(self.PARTY), 0)


class TestBoVongChoLeader(unittest.TestCase):
    def test_khong_con_cho_vo_han_leader_quyet_dinh(self):
        s = _src()
        for d in s.splitlines():          # chu thich ca hong van duoc phep nhac ten
            if "log." in d:
                self.assertNotIn("CHO leader quyet dinh", d, d.strip())
        for d in s.splitlines():
            if d.strip().startswith("#"):
                continue
            self.assertNotIn('while not (st["leader_ok"]', d, d.strip())

    def test_VAN_theo_lenh_huy_cua_leader(self):
        """`leader_bad` la lenh HUY that (leader sai map / mat ket noi) - bo di la ca party train
        voi mot leader hong."""
        s = _src()
        self.assertIn('if st["leader_bad"].is_set():', s)


if __name__ == "__main__":
    unittest.main()
