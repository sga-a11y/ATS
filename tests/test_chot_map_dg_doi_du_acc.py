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
        # Moi muc kem LY DO (acc nay thieu gi) - xem `test_noi_ro_vi_sao_chua_chot_bai.py`.
        _t = R._acc_thieu_level(self.PARTY)
        self.assertEqual([x.split("(")[0] for x in _t], ["a2", "a3"])
        self.assertTrue(all("(" in x for x in _t), "khong noi ro thieu gi: %s" % _t)

    def test_CHUA_xac_nhan_pet_thi_KHONG_cho_nua(self):
        """User 14/09: "chon bai train thi dua vao lv nhung con hien tai thoi, dua nao thieu pet
        thi ke me no di".

        Truoc day cho ca `active_pet_confirmed` (pet level cao hon char vai chuc nen chot som se
        tut hang bai). Cai gia qua dat: chua chot duoc bai -> `auto_train` rong -> dieu phoi khong
        biet map train dich -> khong biet thanh tap ket -> ca party lap party bua o Trac Quan roi
        teleport lam tan doi (party 29, 14/09: 27 phut khong chot duoc bai).
        """
        for u in self.ACCS:
            R.account_clients[u] = _C(150)
        R.account_clients["a2"] = _C(150, pet_confirmed=False)
        self.assertEqual(R._acc_thieu_level(self.PARTY), [])

    def test_thieu_pet_VAN_gop_char_level(self):
        """Khong loai acc khoi phep tinh - user 14/09: "van tinh char cua acc do chu"."""
        for u in self.ACCS:
            R.account_clients[u] = _C(150)
        R.account_clients["a2"] = _C(177, pet_confirmed=False)
        self.assertIn(177, R._party_levels(self.PARTY),
                      "acc thieu pet bi loai khoi phep tinh level party")

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


class TestAccKHONG_TU_CHOT(_Nen):
    """Acc CHI DOC ket qua dieu phoi da chot - khong tu chot, khong vong cho.

    Ba lop test cu o day (`TestVongCho`, `TestChotDungSauKhiCho`, `TestChoNgoaiLock`) neo ham
    `_cho_du_level_party` - VONG CHO VO HAN ma acc roi vao khi tu goi `_auto_dg_level(pidx, pick,
    username, _stopped)`. Vong do khong doc lenh dieu phoi va chi log mot dong moi 30 giay: acc nam
    trong do thi DIEC, dieu phoi ra lenh gom deu deu ma khong ai nghe.

    Da xoa han ca vong cho lan hai duong acc tu chot. Gio:
        DIEU PHOI  -> `_auto_dg_level(pidx, pick)` / `_auto_train_target(pidx, pcfg)` moi 2 giay
        ACC        -> `_doc_cap_dg(pidx)` / `_doc_bai_train(pidx)` - CHI DOC, khong cho gi
    """

    def test_khong_con_vong_cho_vo_han(self):
        self.assertFalse(hasattr(R, "_cho_du_level_party"),
                         "vong cho vo han song lai -> acc lai diec lenh dieu phoi")

    def test_acc_chi_DOC_cap_quai_DG(self):
        st = R._pstate(self.PARTY)
        self.assertIsNone(R._doc_cap_dg(self.PARTY))
        st["auto_dg_level"] = 7
        self.assertEqual(R._doc_cap_dg(self.PARTY), 7)

    def test_acc_chi_DOC_bai_train(self):
        st = R._pstate(self.PARTY)
        self.assertIsNone(R._doc_bai_train(self.PARTY))
        st["auto_train"] = (21841, -1)
        self.assertEqual(R._doc_bai_train(self.PARTY), (21841, -1))

    def test_ham_chot_KHONG_con_nhan_username(self):
        """Con tham so username la con duong acc tu chot + roi vao vong cho."""
        import inspect
        for _f in (R._auto_dg_level, R._auto_train_target):
            _tham = list(inspect.signature(_f).parameters)
            self.assertNotIn("username", _tham, _f.__name__)
            self.assertNotIn("stopped", _tham, _f.__name__)

    def test_KHONG_acc_nao_goi_ham_chot(self):
        import io as _io, os as _os
        p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                          "run_party_digioi.py")
        with _io.open(p, encoding="utf-8") as fh:
            src = fh.read()
        # Soi LOI GOI THAT bang AST (chu thich/docstring co ke lai dang goi cu).
        import ast
        _xau = []
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in ("_auto_dg_level", "_auto_train_target"):
                continue
            # Chi DIEU PHOI duoc goi, va goi bang DUNG hai tham so (khong username/stopped).
            if len(node.args) > 2 or node.keywords:
                _xau.append((node.func.id, node.lineno))
        self.assertEqual(_xau, [], "acc van tu chot (goi kem username/stopped): %s" % _xau)

    def test_van_chot_dung_khi_du_level(self):
        for u in self.ACCS:
            R.account_clients[u] = _C(150, pet_level=178)
        _cfg = R.config
        cu = getattr(_cfg, "PARTY_CONFIG", {})
        try:
            _cfg.PARTY_CONFIG = {self.PARTY: {"di_gioi_pick": "avg-30"}}
            R._auto_dg_level(self.PARTY, "avg-30")
            self.assertIsNotNone(R._pstate(self.PARTY).get("auto_dg_level"))
        finally:
            _cfg.PARTY_CONFIG = cu


if __name__ == "__main__":
    unittest.main()
