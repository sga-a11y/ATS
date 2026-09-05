"""Chot cap quai DG / map train phai DOI DU LEVEL CA PARTY, khong chot bang acc login truoc.

Bug that (log 05/09, party 1 co 5 acc):
    14:10:05 >>> PARTY 1: TU CHON CAP QUAI DG -> cap 150 (muon 152, level party [167, 197])
                                                                     ^^^^^^^^^^ 1/5 acc
`account_last` chi nam trong RAM (run_party_digioi.py: `account_last = {}`) nen lan chay dau
tien sau khi start bot, acc nao login xong truoc la chot cho ca party bang MINH NO. Ma
`_auto_dg_level` / `_auto_train_target` chot MOT LAN roi giu nguyen CA PHIEN -> sai den luc
restart bot.

Rule user chot 05/09: "du party moi lam gi thi lam" -> CHO VO HAN, KHONG timeout. Loi ra chi
gom: Stop (GUI) va ep dong bo (_resync_ck).
"""
from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# run_party_digioi doc sys.argv[1] ngay khi import -> phai che di (nhu test_party_average_level).
with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class _St:
    """State pet toi thieu: chi can co `active_pet_confirmed` nhu client that."""

    def __init__(self, confirmed=True):
        self.active_pet_confirmed = confirmed


class _C:
    def __init__(self, lv, pet_confirmed=True, pet_name=None, pet_level=None):
        self.char_level = lv
        self.state = _St(pet_confirmed)
        self.pet_name = pet_name
        self.pet_level = pet_level

    def pet_name_out(self):
        return self.pet_name if self.state.active_pet_confirmed else None


class _Nen(unittest.TestCase):
    """Dung 1 party 3 acc gia, khong dung config/mang that."""

    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._clients = dict(R.account_clients)
        self._stops = dict(R.account_stops)
        self._last = dict(R.account_last)
        R.account_clients.clear()
        R.account_stops.clear()
        R.account_last.clear()
        R._party_state.pop(self.PARTY, None)
        # run_account ghi epoch nay luc khoi dong; khong seed thi _resync_ck raise oan.
        self._epoch = dict(R.account_sync_epoch)
        for u in self.ACCS:
            R.account_sync_epoch[u] = R._pstate(self.PARTY).get("sync_epoch", 0)

    def tearDown(self):
        R.party_accounts = self._accounts
        R.account_clients.clear(); R.account_clients.update(self._clients)
        R.account_stops.clear(); R.account_stops.update(self._stops)
        R.account_last.clear(); R.account_last.update(self._last)
        R.account_sync_epoch.clear(); R.account_sync_epoch.update(self._epoch)
        R._party_state.pop(self.PARTY, None)


class TestAiPhaiCho(_Nen):
    def test_acc_chua_tao_thread_VAN_phai_cho(self):
        """start_party tao thread lech nhau vai giay. Loc theo `is_account_running` la barrier
        qua ngay bang 1 acc = dung y het bug cu."""
        self.assertEqual(R._acc_cho_level(self.PARTY), list(self.ACCS))

    def test_acc_bi_Stop_thi_KHONG_cho_nua(self):
        ev = threading.Event(); ev.set()
        R.account_stops["a3"] = ev
        self.assertEqual(R._acc_cho_level(self.PARTY), ["a1", "a2"])

    def test_thieu_acc_chua_login(self):
        R.account_clients["a1"] = _C(150)
        self.assertEqual(R._acc_thieu_level(self.PARTY), ["a2", "a3"])

    def test_co_char_level_nhung_CHUA_xac_nhan_pet_van_la_thieu(self):
        """Pet level cao hon char rat nhieu (log 05/09: char ~154 / pet ~188). Chot khi moi co
        char la trung binh tut hang chuc level."""
        for u in self.ACCS:
            R.account_clients[u] = _C(150)
        R.account_clients["a2"] = _C(150, pet_confirmed=False)
        self.assertEqual(R._acc_thieu_level(self.PARTY), ["a2"])

    def test_xac_nhan_pet_roi_ma_khong_tha_pet_la_HOP_LE(self):
        """active_pet_confirmed=True + khong co pet = acc khong tha pet -> khong cho nua."""
        for u in self.ACCS:
            R.account_clients[u] = _C(150)
        self.assertEqual(R._acc_thieu_level(self.PARTY), [])

    def test_acc_da_tat_lay_level_tu_account_last(self):
        R.account_clients["a1"] = _C(150)
        R.account_clients["a2"] = _C(151)
        R.account_last["a3"] = {"char_level": 149}
        self.assertEqual(R._acc_thieu_level(self.PARTY), [])


class TestVongCho(_Nen):
    def test_du_level_thi_di_tiep_ngay(self):
        for u in self.ACCS:
            R.account_clients[u] = _C(150)
        self.assertTrue(R._cho_du_level_party(self.PARTY, "a1", lambda: False, "test"))

    def test_Stop_thi_thoat_vong_cho(self):
        R.account_clients["a1"] = _C(150)          # thieu a2, a3 -> se cho mai
        self.assertFalse(R._cho_du_level_party(self.PARTY, "a1", lambda: True, "test"))

    def test_ep_dong_bo_van_unwind_duoc(self):
        """Cho vo han ma khong co duong ra cho lenh ep dong bo = treo that."""
        R.account_clients["a1"] = _C(150)
        st = R._pstate(self.PARTY)
        st["sync_epoch"] = 7
        R.account_sync_epoch["a1"] = 6             # lech -> _resync_ck raise
        with self.assertRaises(R.ResyncSignal):
            R._cho_du_level_party(self.PARTY, "a1", lambda: False, "test")

    def test_cho_that_roi_moi_di_khi_acc_cuoi_login_xong(self):
        """Vong cho phai NHAY khi acc con thieu login xong, khong phai chi doc 1 lan."""
        R.account_clients["a1"] = _C(150)
        R.account_clients["a2"] = _C(151)

        def _login_muon():
            R.account_clients["a3"] = _C(149)

        threading.Timer(1.5, _login_muon).start()
        self.assertTrue(R._cho_du_level_party(self.PARTY, "a1", lambda: False, "test"))
        self.assertEqual(R._acc_thieu_level(self.PARTY), [])


class TestChotDungSauKhiCho(_Nen):
    def test_dg_chot_bang_level_CA_PARTY(self):
        R.account_clients["a1"] = _C(150)
        R.account_clients["a2"] = _C(151)
        R.account_clients["a3"] = _C(152)
        idx = R._auto_dg_level(self.PARTY, "avg-30", "a1", lambda: False)
        self.assertIsNotNone(idx)
        # chot 1 lan roi giu: goi lai ra dung ket qua cu
        self.assertEqual(R._auto_dg_level(self.PARTY, "avg-30", "a1", lambda: False), idx)

    def test_bi_Stop_giua_luc_cho_thi_KHONG_chot_bua(self):
        """Thoat vi Stop ma van chot bang du lieu thieu = van dinh dung bug cu."""
        R.account_clients["a1"] = _C(150)
        self.assertIsNone(R._auto_dg_level(self.PARTY, "avg-30", "a1", lambda: True))
        self.assertIsNone(R._pstate(self.PARTY).get("auto_dg_level"))

    def test_dieu_phoi_goi_khong_username_thi_KHONG_CHOT_khi_thieu_acc(self):
        """DIEU PHOI goi kieu nay (khong username/stopped) moi 2 giay - no KHONG duoc cho, nhung
        cung KHONG duoc chot bua bang 1 acc. Chua du thi tra None, du thi chot ngay nhip sau."""
        R.account_clients["a1"] = _C(150)
        self.assertIsNone(R._auto_dg_level(self.PARTY, "avg-30"),
                          "chot bang 1/3 acc = dung bug da lam party 1 va 19 di sai cap")
        self.assertIsNone(R._pstate(self.PARTY).get("auto_dg_level"))
        R.account_clients["a2"] = _C(151)
        R.account_clients["a3"] = _C(152)
        self.assertIsNotNone(R._auto_dg_level(self.PARTY, "avg-30"))

    def test_dieu_phoi_tu_chot_khong_qua_luong_acc_nao(self):
        """`_dieu_phoi_chot_map` la duong chot chinh: bot quyet, khong luong acc nao quyet."""
        import bot.config as _cfg
        cu = dict(getattr(_cfg, "PARTY_CONFIG", {}))
        _cfg.PARTY_CONFIG = {self.PARTY: {"mode": "digioi_train", "di_gioi_pick": "avg-30"}}
        try:
            for u, lv in zip(self.ACCS, (150, 151, 152)):
                R.account_clients[u] = _C(lv)
            R._dieu_phoi_chot_map(self.PARTY, R._pstate(self.PARTY))
            self.assertIsNotNone(R._pstate(self.PARTY).get("auto_dg_level"))
        finally:
            _cfg.PARTY_CONFIG = cu


class TestChoNgoaiLock(unittest.TestCase):
    """Cho 1s/vong MA VAN giu st['lock'] la treo moi thu khac cham vao party state."""

    def _than(self, ten):
        import io
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "run_party_digioi.py")
        with io.open(p, encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def %s(" % ten)
        assert i > 0, ten
        return src[i:src.find("\ndef ", i + 10)]

    def test_cho_nam_ngoai_with_lock(self):
        for ten in ("_auto_dg_level", "_auto_train_target"):
            than = self._than(ten)
            i = than.find("_cho_du_level_party(")
            self.assertGreater(i, 0, "%s chua goi vong cho" % ten)
            truoc = than[:i]
            # Phai co mot `with st["lock"]:` DONG LAI truoc do (khoi doc cache), va lenh cho
            # nam o cot thut dau ham (4 space) chu khong nam trong khoi with (8 space).
            self.assertIn("\n        if not _cho_du_level_party(", than,
                          "%s: lenh cho khong o muc thut dau ham -> nghi nam trong with lock"
                          % ten)
            self.assertNotIn("with st[\"lock\"]:", truoc.rsplit("\n    if username", 1)[-1])

    def test_doc_lai_cache_sau_khi_cho(self):
        """Cho xong phai kiem lai: acc khac co the da chot trong luc minh ngu."""
        for ten, khoa in (("_auto_dg_level", "auto_dg_level"), ("_auto_train_target", "auto_train")):
            than = self._than(ten)
            sau = than[than.find("_cho_du_level_party("):]
            self.assertIn('st.get("%s")' % khoa, sau,
                          "%s: khong doc lai cache sau khi cho -> 2 acc cung chot, ghi de nhau"
                          % ten)


if __name__ == "__main__":
    unittest.main()
