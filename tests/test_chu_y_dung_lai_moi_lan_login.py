"""Bang "Chu y" dung lai MOI LAN CO ACC VAO WORLD - khong dung mot lan roi giu vinh vien.

User 14/09: "cai chu y bi lam sao ma ko thay xuat hien nua" -> "cu acc login xong la cache lai 1
lan, reconnect khi dis cung cache lai, don gian la login vi bat ky ly do gi cung cache lai".

LOI: cache dung o lan `_refresh` DAU TIEN, ma `_refresh` duoc hen `self.after(1000, ...)` - tuc 1
GIAY sau khi mo GUI, luc do chua acc nao login. Ca nam nguon deu rong:
    _party_bag_notify      -> chua co du lieu tui
    ba_dau_notify_items    -> rong
    _party_legion_notify   -> rong
    diem_du_notify_items   -> rong
    account_furnace_notify -> rong
-> cache = [] va KHONG CHO NAO xoa no -> "Chu y" trong vinh vien den khi tat GUI.

(Cache sinh ra 13/09 de chua "click doi party thay do rat lau moi load ra ... not responding":
truoc do moi giay dung lai TOAN BO danh sach cho 50 party tren main thread Tk. Van giu cache, chi
them khoa `login_gen`.)
"""
from __future__ import annotations

import io
import os
import re
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


class TestLoginGenTang(unittest.TestCase):
    """Moc phai tang o CHO DUY NHAT ma ca login dau lan reconnect deu di qua."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_tang_ngay_sau_khi_vao_world(self):
        i = self.src.find('account_clients[username] = c     # GUI doc trang thai')
        self.assertGreater(i, 0, "mat cho dang ky client vao world")
        self.assertIn('st["login_gen"] = int(st.get("login_gen", 0) or 0) + 1',
                      self.src[i:i + 1200],
                      "khong tang login_gen luc acc vao world")

    def test_tang_TRONG_lock(self):
        i = self.src.find('st["login_gen"] = int(')
        self.assertGreater(i, 0)
        self.assertIn('with st["lock"]:', self.src[max(0, i - 200):i])

    def test_chi_co_MOT_cho_tang(self):
        self.assertEqual(self.src.count('st["login_gen"] = int('), 1,
                         "tang o nhieu cho -> so nhay lung tung, cache dung lai oan")

    def test_cho_tang_nam_SAU_moc_reconnect(self):
        """Cung mot dong lenh chay cho ca reconnect - chinh dong ben canh discard 'reconnecting'."""
        i = self.src.find('st["login_gen"] = int(')
        truoc = self.src[max(0, i - 900):i]
        self.assertIn('st["reconnecting"].discard(username)', truoc,
                      "khong nam tren duong reconnect -> dis xong khong dung lai Chu y")


class TestGuiDocLoginGen(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_cache_khoa_theo_login_gen(self):
        self.assertIn('.get("login_gen", 0)', self.src,
                      "GUI khong doc login_gen -> cache khong bao gio dung lai")

    def test_cache_dung_lai_khi_so_DOI(self):
        i = self.src.find("_cache = self._notify_cache.get(pidx)")
        self.assertGreater(i, 0, "mat cho doc cache")
        khoi = self.src[i:i + 400]
        self.assertIn("_cache[0] != _lg", khoi, "khong so login_gen -> giu cache cu mai")

    def test_CO_TTL_vi_nguon_den_SAU_login(self):
        """`login_gen` tang luc acc VAO WORLD, nhung moi nguon Chu y den sau do:

            dong 2833  st["login_gen"] += 1        <- dung cache o day
            dong 2960  _kiem_han_ba_dau(...)       <- Ba Dau ghi o day
            tui do     `log_bag_delayed` tre toi 8 giay
            quan doan / lo / du diem: trong login chores, vai phut sau

        Dung cache dung luc do la dung khi MOI NGUON CON RONG roi giu vinh vien. Party nao tinh co
        co acc reconnect muon thi dung lai -> CO Chu y; party chay em thi RONG MAI.
        User 14/09: "t thay co pt co pt ko".
        """
        from gui import BotGUI
        self.assertGreater(getattr(BotGUI, "NOTIFY_LAM_MOI_SEC", 0), 0,
                           "khong co TTL -> Chu y rong vinh vien voi party khong ai reconnect")
        i = self.src.find("_cache = self._notify_cache.get(pidx)")
        khoi = self.src[i:i + 400]
        self.assertIn("NOTIFY_LAM_MOI_SEC", khoi)

    def test_TTL_du_THUA_de_khong_treo_GUI(self):
        """Muc dich ban dau (user 13/09: "khoi can load lai") van phai giu: truoc do la 100 luot
        dung danh sach MOI GIAY voi 50 party -> GUI "not responding" khi doi tab."""
        from gui import BotGUI
        self.assertGreaterEqual(BotGUI.NOTIFY_LAM_MOI_SEC, 30.0,
                                "lam moi qua day -> lai treo GUI nhu truoc 13/09")

    def test_CO_Chu_y_roi_thi_KHONG_dung_lai(self):
        """User 14/09: "lam deo gi ma phai dung lai nhieu the, neu chua co chu y thi moi can dung
        lai chu". Danh sach Chu y khong doi may trong luc chay."""
        i = self.src.find("_cache = self._notify_cache.get(pidx)")
        khoi = self.src[i:i + 500]
        self.assertIn("not _cache[1] and", khoi,
                      "dung lai ca khi DA CO Chu y -> ton cong vo ich moi 60 giay")

    def test_khong_con_duong_giu_vinh_vien(self):
        self.assertNotIn("if pidx not in self._notify_cache:", self.src,
                         "con duong dung mot lan roi giu vinh vien")


class TestHanhVi(unittest.TestCase):
    """Mo phong dung phep so cua GUI."""

    TTL = 60.0

    @classmethod
    def _lay(cls, cache, pidx, login_gen, dung, bay=0.0):
        """Mo phong DUNG phep so cua GUI (xem `_refresh`)."""
        _c = cache.get(pidx)
        if (_c is None or _c[0] != login_gen
                or (not _c[1] and bay - _c[2] > cls.TTL)):
            _c = (login_gen, dung(), bay)
            cache[pidx] = _c
        return _c[1]

    def test_dang_RONG_thi_thu_lai_sau_TTL(self):
        """Nguon Chu y den SAU luc login - rong thi phai thu lai, khong giu vinh vien."""
        cache, dem = {}, []
        self._lay(cache, 0, 1, lambda: dem.append(1) or [], bay=0.0)
        self._lay(cache, 0, 1, lambda: dem.append(1) or [], bay=10.0)     # chua den han
        self.assertEqual(len(dem), 1)
        self._lay(cache, 0, 1, lambda: dem.append(1) or ["tui gan day"], bay=61.0)
        self.assertEqual(len(dem), 2)
        self.assertEqual(cache[0][1], ["tui gan day"])

    def test_DA_CO_Chu_y_thi_giu_luon(self):
        cache, dem = {}, []
        self._lay(cache, 0, 1, lambda: dem.append(1) or ["ba dau"], bay=0.0)
        for _t in (61.0, 200.0, 9999.0):
            self._lay(cache, 0, 1, lambda: dem.append(1) or ["ba dau"], bay=_t)
        self.assertEqual(len(dem), 1, "da co Chu y ma van dung lai -> ton cong vo ich")

    def test_lan_dau_GUI_chua_ai_login_thi_rong_nhung_KHONG_giu(self):
        cache, dem = {}, []
        # GUI vua mo: chua acc nao login -> nguon rong
        self.assertEqual(self._lay(cache, 0, 0, lambda: dem.append(1) or []), [])
        # acc login xong -> login_gen len 1, nguon co du lieu -> PHAI dung lai
        self.assertEqual(self._lay(cache, 0, 1, lambda: dem.append(1) or ["tui gan day"]),
                         ["tui gan day"])
        self.assertEqual(len(dem), 2)

    def test_khong_dung_lai_khi_khong_co_ai_login(self):
        cache, dem = {}, []
        for _ in range(50):     # 50 vong refresh
            self._lay(cache, 0, 3, lambda: dem.append(1) or ["x"])
        self.assertEqual(len(dem), 1, "dung lai moi vong -> lai treo GUI nhu truoc 13/09")

    def test_reconnect_cung_dung_lai(self):
        cache, dem = {}, []
        self._lay(cache, 0, 1, lambda: dem.append(1) or ["cu"])
        self._lay(cache, 0, 2, lambda: dem.append(1) or ["moi"])   # acc dis roi vao lai
        self.assertEqual(len(dem), 2)
        self.assertEqual(cache[0][1], ["moi"])

    def test_moi_party_mot_khoa_rieng(self):
        cache, dem = {}, []
        self._lay(cache, 0, 1, lambda: dem.append(1) or ["p1"])
        self._lay(cache, 1, 1, lambda: dem.append(1) or ["p2"])
        self.assertEqual(len(dem), 2)
        self.assertEqual(cache[0][1], ["p1"])
        self.assertEqual(cache[1][1], ["p2"])


class TestPstateCoLoginGen(unittest.TestCase):
    def test_pstate_moi_mac_dinh_0(self):
        R._party_state.pop(99, None)
        try:
            self.assertEqual(int(R._pstate(99).get("login_gen", 0) or 0), 0)
        finally:
            R._party_state.pop(99, None)


if __name__ == "__main__":
    unittest.main()
