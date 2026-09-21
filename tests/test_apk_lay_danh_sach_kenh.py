# -*- coding: utf-8 -*-
"""APK lay DANH SACH KENH y het ban PC: truyen PIDX, khong qua map cuc bo cua Kotlin.

User 21/09: "ban apk hinh nhu ko doi dc kenh, click toan bao ko tai dc danh sach kenh, ma dang
co 2 kenh".

Loi: `BotForegroundService.getChannels` nhan `username` roi tra `userPidx[username]` - map CUC BO
cua Kotlin, chi duoc dien khi CHINH service do goi `start_party` trong phien nay. Bot da chay tu
truoc roi mo lai app (hoac service bi tao lai) -> map RONG -> tra rong NGAY, khong he goi sang
Python -> UI bao "Khong tai duoc danh sach kenh" du kenh van co.

Lech NGUON SU THAT: `isRunning` hoi Python (su that), con `getChannels` doc map Kotlin.

Ban PC khong co map nao ca - `gui.py` goi thang `ctrl.get_channel_list(pidx)`. User chot:
"dong bo tu PC qua, cam viet moi".
"""
from __future__ import annotations

import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KT_SV = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android",
                     "BotForegroundService.kt")
KT_UI = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android",
                     "MainActivity.kt")


def _doc(p):
    with io.open(p, encoding="utf-8") as fh:
        return fh.read()


def _than_kt(src, dau):
    i = src.find(dau)
    if i < 0:
        return ""
    sau = src.find("\n    fun ", i + 10)
    return src[i:sau if sau > 0 else len(src)]


class TestGiongBanPC(unittest.TestCase):
    def setUp(self):
        self.sv = _doc(KT_SV)
        self.ui = _doc(KT_UI)

    def test_getChannels_nhan_PIDX(self):
        self.assertIn("fun getChannels(pidx: Int)", self.sv,
                      "van nhan username -> phai tra map cuc bo de ra pidx")

    def test_KHONG_dung_map_cuc_bo_userPidx(self):
        than = _than_kt(self.sv, "    fun getChannels(")
        self.assertTrue(than)
        _ma = "\n".join(d for d in than.split("\n") if not d.strip().startswith("//"))
        self.assertNotIn("userPidx", _ma,
                         "map nay chi co khi chinh app start party trong phien -> mo lai app la rong")

    def test_van_goi_DUNG_ham_Python_nhu_PC(self):
        than = _than_kt(self.sv, "    fun getChannels(")
        self.assertIn('callAttr("get_channel_list", pidx)', than)
        # PC: gui.py goi `ctrl.get_channel_list(pidx)` - cung mot ham, cung tham so.
        self.assertIn("get_channel_list(pidx)", _doc(os.path.join(ROOT, "gui.py")))

    def test_UI_truyen_pidx_theo_vi_tri_party(self):
        i = self.ui.find("onGetChannels = {")
        self.assertGreater(i, 0, "mat nut lay danh sach kenh")
        khoi = self.ui[i:i + 900]
        self.assertIn("parties.indexOf(party)", khoi,
                      "phai suy pidx giong startPartyIn / onFurnaceNotify")
        _ma = "\n".join(d for d in khoi.split("\n") if not d.strip().startswith("//"))
        self.assertNotIn("it.username", _ma, "van truyen username")

    def test_loi_phai_duoc_GHI_LAI(self):
        """Nuot im thi UI chi bao 'khong tai duoc' ma khong ai biet vi sao."""
        than = _than_kt(self.sv, "    fun getChannels(")
        i = than.find("catch")
        self.assertGreater(i, 0)
        self.assertIn("Log.w", than[i:], "van nuot loi -> lan sau lai phai doan")


if __name__ == "__main__":
    unittest.main()
