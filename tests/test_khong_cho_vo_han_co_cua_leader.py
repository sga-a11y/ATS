"""Member KHONG duoc nam cho vo han mot co do LEADER bat.

User 10/09: "p50 bi lam sao" -> "van con de leader quyet dinh co a" -> "cu lam the nao de lenh cua
dieu phoi la tuyet doi, va dieu phoi ko ngu toi muc phai de acc quyet dinh, ko ngu toi muc thay
lech map ma van ko lam dc gi".

CA THAT party 50 (`dk101..dk105`, char `dakmot/dakhai/dakba/dakbon/daknam`):

    11:53:51 [dakmot] (LEADER) reform: 4/4 member join lai -> KEO qua cong ra train map
                      -> set `route_party_ready`, di qua cong
    11:54:05 [dakmot] qua cong idx=1 -> map 18000          <- leader sang map moi MOT MINH
    11:54:21..38  3 member: PARTY ... ROI doi -> roster 3 -> 2 -> 1   (doi TAN)
                  leader vao vong reform moi -> `route_party_ready.clear()`
    11:54:38 -> 12:00   ba acc IM HOAN TOAN, khong ca dong keepalive `pos=`

py-spy tren tien trinh that xac nhan ba luong dung dung o vong cho:
    3x  _do_reform (run_party_digioi.py:4155)   <- `while not st["route_party_ready"].is_set()`

Hai vong do truoc day viet thang trong code la "CHO VO HAN". Loi thoat DUY NHAT la `_ab()`
(reform_gen doi), nen khi leader im luon thi member ket vinh vien. Va co con bi leader `clear()`
giua chung (vao vong reform moi) -> member dang cho vong HAI bi da nguoc ve vong MOT.

Trong luc do dieu phoi BIET het: `12:00:40 party dang o 2 MAP KHAC NHAU [18000, 18021] -> se gom`
- nhung khong ai nghe duoc lenh, vi ca ba deu nam trong barrier.
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config


class _C:
    def __init__(self, map_id=None, running=True, label="acc"):
        self.current_map = map_id
        self.running = running
        self._label = label


class _Nen(unittest.TestCase):
    PIDX = 0
    SC = 18444          # map train
    LEADER = "lead"

    def setUp(self):
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        self._lead = dict(getattr(config, "PARTY_LEADER_ACC", {}))
        config.PARTY_LEADER_ACC = {self.PIDX: self.LEADER}
        R._party_state.pop(self.PIDX, None)
        self.st = R._pstate(self.PIDX)
        self._rs = R._resync_ck
        R._resync_ck = lambda *_a, **_k: None
        self._han = R.CHO_LEADER_KEO_SEC

    def tearDown(self):
        R.account_clients.clear(); R.account_clients.update(self._cl)
        config.PARTY_LEADER_ACC = self._lead
        R._party_state.pop(self.PIDX, None)
        R._resync_ck = self._rs
        R.CHO_LEADER_KEO_SEC = self._han

    def _goi(self, c, co="route_party_ready", abort=lambda: False):
        return R._cho_leader_keo(self.st, self.PIDX, c, self.SC, abort, "u", co)


class TestThoatDuocKhiCoKhongBaoGioBat(_Nen):
    def test_co_da_bat_thi_di_tiep_ngay(self):
        self.st["route_party_ready"].set()
        R.account_clients[self.LEADER] = _C(map_id=12001)
        self.assertTrue(self._goi(_C(map_id=12001)))

    def test_LEADER_TAT_thi_THOI_CHO(self):
        """Cho mot leader da tat = cho ma."""
        R.account_clients[self.LEADER] = _C(map_id=12001, running=False)
        self.assertFalse(self._goi(_C(map_id=12001)))

    def test_LEADER_KHONG_CO_trong_danh_sach_thi_THOI_CHO(self):
        self.assertFalse(self._goi(_C(map_id=12001)))

    def test_leader_DA_TOI_map_train_ma_co_chua_bat_thi_DI_TIEP(self):
        """Dung ca party 50: leader qua cong roi nhay sang vong reform moi va `clear()` mat co."""
        R.account_clients[self.LEADER] = _C(map_id=self.SC)
        self.assertTrue(self._goi(_C(map_id=12001)))

    def test_MINH_da_o_map_train_thi_DI_TIEP(self):
        R.account_clients[self.LEADER] = _C(map_id=12001)
        self.assertTrue(self._goi(_C(map_id=self.SC)))

    def test_QUA_HAN_thi_THOI_CHO(self):
        R.CHO_LEADER_KEO_SEC = 0.0
        R.account_clients[self.LEADER] = _C(map_id=12001)
        self.assertFalse(self._goi(_C(map_id=12001)))

    def test_abort_thi_THOI_CHO(self):
        R.account_clients[self.LEADER] = _C(map_id=12001)
        self.assertFalse(self._goi(_C(map_id=12001), abort=lambda: True))

    def test_KHONG_ket_vinh_vien_khi_co_bi_CLEAR_giua_chung(self):
        """Leader bat co roi `clear()` ngay (vao vong reform moi) - member khong duoc ket lai."""
        R.CHO_LEADER_KEO_SEC = 3.0
        R.account_clients[self.LEADER] = _C(map_id=12001)
        self.st["route_party_ready"].set()

        def _clear_sau():
            time.sleep(0.2)
            self.st["route_party_ready"].clear()

        threading.Thread(target=_clear_sau, daemon=True).start()
        t0 = time.time()
        self._goi(_C(map_id=12001))
        self.assertLess(time.time() - t0, R.CHO_LEADER_KEO_SEC + 2.0,
                        "co bi clear giua chung -> ket lai tu dau")


class TestKhongConVongCHO_VO_HAN(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def _ma(self):
        """Bo comment/docstring - chi xet MA chay."""
        s = re.sub(r'"""[\s\S]*?"""', "", self.src)
        return re.sub(r"#.*", "", s)

    def test_moi_barrier_deu_co_LOI_THOAT(self):
        """Barrier cho co cua leader phai co it nhat MOT loi thoat khong phu thuoc leader:
        han thoi gian, nghe duoc lenh dieu phoi, hoac thoat khi leader tat.

        Cho vo han + diec = ca ba member party 50 im 6 phut trong khi dieu phoi dang ra lenh gom.
        """
        ma = self._ma()
        for m in re.finditer(r'while not st\[\s*"([a-z_]+)"\s*\]\.is_set\(\):', ma):
            ten = m.group(1)
            than = ma[m.end():m.end() + 2000]
            co_loi_thoat = ("_nghe_lenh_kenh()" in than
                            or "khong con chay" in than
                            or "time.time() > _het" in than)
            self.assertTrue(co_loi_thoat,
                            "barrier `%s` cho vo han ma khong co loi thoat nao" % ten)

    def test_duong_member_dung_ham_co_han(self):
        """Neo theo NHANH member trong `_do_reform`, khong theo cua so ky tu."""
        i = self.src.find("# member: dung yen TRONG LUC leader keo")
        self.assertGreater(i, 0, "khong tim thay nhanh member trong _do_reform")
        khoi = self.src[i:i + 3000]
        self.assertEqual(khoi.count("_cho_leader_keo("), 2,
                         "ca hai chang (lap party / keo qua route) deu phai qua ham co han")

    def test_ham_cho_co_HAN_CUNG(self):
        i = self.src.find("def _cho_leader_keo(")
        self.assertGreater(i, 0)
        khoi = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("CHO_LEADER_KEO_SEC", khoi)
        self.assertIn("time.time() > _het", khoi)

    def test_ham_cho_DOC_THANG_trang_thai_leader(self):
        """Khong doi ai bao cao - doc `account_clients` cung tien trinh (L2)."""
        i = self.src.find("def _cho_leader_keo(")
        khoi = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("account_clients.get(", khoi)
        self.assertIn("running", khoi)

    def test_barrier_moi_loi_cung_co_loi_thoat_khi_leader_tat(self):
        """Vong cho loi moi (`invited`) cung khong duoc cho mot leader da tat."""
        i = self.src.find('while not st["invited"].is_set():')
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 1500]
        self.assertIn("LEADER khong con chay", khoi)


if __name__ == "__main__":
    unittest.main()
