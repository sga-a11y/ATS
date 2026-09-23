# -*- coding: utf-8 -*-
"""APK - LENH LIVE phai nhan PIDX, khong duoc tra nguoc `userPidx`.

Ban PC biet `pidx` va goi thang: `gui.py` -> `ctrl.party_switch_channel(pidx, ch)`.

Ban APK truoc day nhan LIST USERNAME roi tra nguoc `userPidx[username]`:

    private fun pidxSet(usernames: List<String>): List<Int> =
        usernames.mapNotNull { userPidx[it] }.distinct()
    fun sendChannel(usernames: List<String>, ch: Int) {
        pidxSet(usernames).forEach { ... }      // map RONG -> forEach khong chay lan nao
    }

`userPidx` CHI duoc dien khi CHINH service nay goi `start_party` trong phien do
(`activeAccounts.forEach { userPidx[it.username] = pidx }`), va bi XOA SACH khi stop party. Bot da
chay tu truoc roi mo lai app, hoac service bi Android tao lai -> map RONG -> LENH KHONG HE SANG
TOI PYTHON, khong mot dau vet nao trong log.

Ca that 23/09 (user: "apk ket chu pc co ket dau"): bam doi kenh tay tren APK -> lenh khong toi noi.
Bon acc van doi duoc kenh la nho DUONG TU DONG (dieu phoi dong bo kenh), con dua dang ket tran thi
duong tu dong chi CHO chu khong keo ra safe -> nam lai cho quai danh. Ben PC lenh tay toi noi nen
no kien tri 300s + keo ra diem an toan, dua ket cung di duoc.

DAY LA LAN THU HAI cua cung mot con benh: `getChannels` da duoc sua ngay 22/09 (user 21/09: "click
toan bao ko tai dc danh sach kenh"), nhung hom do CHI sua mot ham va BO SOT ca sau ham lenh live.
Test nay giu ca sau, de lan sau them ham moi la thay ngay.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AND = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android")

# Ham -> ham Python cap PARTY ma no goi. Tat ca deu nhan `pidx` lam tham so DAU.
LENH_LIVE = {
    "sendChannel": "party_switch_channel",
    "sendChannelAuto": "party_switch_channel",
    "sendCity": "party_teleport_city",
    "setDiGioiLevel": "party_set_di_gioi_level",
    "sendRouteMaps": "party_route_maps",
    "sendGiftcode": "redeem_giftcode_party",
    "getChannels": "get_channel_list",
}


def _doc(ten):
    with io.open(os.path.join(AND, ten), encoding="utf-8") as fh:
        return fh.read()


def _dong_code(s):
    return [l for l in s.splitlines() if not l.strip().startswith("//")]


def _than_ham(src, ten):
    """Than ham `ten` - CAT NGAY o dau chu thich cua ham ke tiep.

    Cat theo `\\n    fun ` thi nuot ca khoi `/** ... */` dung truoc ham sau, va chu thich do co
    nhac ten cu -> test do oan.
    """
    i = src.find("fun %s(" % ten)
    assert i > 0, "mat %s" % ten
    ket = len(src)
    for _dau in ("\n    fun ", "\n    private fun ", "\n    /**", "\n    //"):
        j = src.find(_dau, i + 10)
        if j > i:
            ket = min(ket, j)
    return src[i:ket]


class TestServiceNhanPidx(unittest.TestCase):
    def setUp(self):
        self.svc = _doc("BotForegroundService.kt")

    def test_moi_lenh_live_deu_nhan_pidx(self):
        for ten in LENH_LIVE:
            self.assertRegex(self.svc, r"fun %s\(pidx: Int" % ten,
                             "%s khong nhan pidx -> phai tra nguoc userPidx" % ten)

    def test_KHONG_con_pidxSet(self):
        _code = "\n".join(_dong_code(self.svc))
        self.assertNotIn("pidxSet(", _code,
                         "con duong tra nguoc username -> pidx qua map cuc bo Kotlin")

    def test_KHONG_lenh_nao_doc_userPidx_de_GUI_LENH(self):
        """`userPidx` van duoc giu cho viec POLL trang thai - do la viec khac. Nhung KHONG duoc
        dung no lam duong ra lenh nua."""
        for ten in LENH_LIVE:
            than = _than_ham(self.svc, ten)
            self.assertNotIn("userPidx", than, "%s van doc userPidx" % ten)

    def test_goi_dung_ham_python_cap_party(self):
        for ten, pyfn in LENH_LIVE.items():
            than = _than_ham(self.svc, ten)
            self.assertIn('"%s"' % pyfn, than, "%s khong goi %s" % (ten, pyfn))

    def test_loi_duoc_GHI_LAI_khong_nuot_im(self):
        """`catch (_: Exception) {}` nuot im thi lenh hong ma khong ai biet - da ton mot vong do
        tim ngay 21/09."""
        for ten in LENH_LIVE:
            than = _than_ham(self.svc, ten)
            self.assertNotIn("catch (_: Exception) {}", than, "%s nuot loi im lang" % ten)
            self.assertIn("android.util.Log.w", than, "%s khong ghi lai loi" % ten)


class TestUITruyenPidx(unittest.TestCase):
    def setUp(self):
        self.ui = _doc("MainActivity.kt")

    def test_KHONG_con_truyen_list_username(self):
        _code = "\n".join(_dong_code(self.ui))
        for ten in LENH_LIVE:
            _xau = re.findall(r"service\?\.%s\(\s*[a-zA-Z]+\.accounts\.map" % ten, _code)
            self.assertEqual(_xau, [], "%s van duoc goi voi list username: %s" % (ten, _xau))

    def test_pidx_suy_tu_vi_tri_party_trong_list(self):
        """Cung nguon voi `startPartyIn` - party nao chay duoc thi lenh live cung toi dung party do."""
        _code = "\n".join(_dong_code(self.ui))
        for ten in ("sendChannel", "sendChannelAuto", "sendCity", "sendRouteMaps", "sendGiftcode"):
            i = _code.find("service?.%s(" % ten)
            self.assertGreater(i, 0, "mat loi goi %s" % ten)
            _truoc = _code[max(0, i - 200):i]
            self.assertIn("parties.indexOf(", _truoc, "%s khong suy pidx tu vi tri party" % ten)


class TestPCVanLaBANDOI_CHUNG(unittest.TestCase):
    """Ban PC la ban doi chung: no goi thang bang pidx. Neu sau nay PC doi kieu thi doi chung
    khong con, va test tren mat y nghia."""

    def test_gui_pc_goi_bang_pidx(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("ctrl.party_switch_channel", s)
        self.assertIn("args=(pidx,", s, "PC khong con truyen pidx -> doi chung khong con")


if __name__ == "__main__":
    unittest.main()
