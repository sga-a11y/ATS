"""Core bundle CU HON APK thi KHONG duoc dung.

`installPythonBundlePath` cam bundle vao `sys.path.insert(0, ...)` -> module trong bundle LUON
THANG module trong APK, ke ca khi bundle DA LAC HAU. User cai APK moi ma tren may con bundle cu
thi APK moi VAN chay code cu, khong co dau hieu gi ngoai loi giua chung.

Bug that (06/09): APK **v1.1.202609061736** - da co `config.event_hom_nay`, da qua cong chan thu 7
cua sync - van bao tren dien thoai:
    18:01:10 [q***ai] (member) MODE=event start_city=0
    18:01:10 [q***ai] LOI: module 'train_bot.config' has no attribute 'event_hom_nay'
Moi acc mode event dung im, supervisor relogin lien tuc -> "DANG NHAP TRUNG LAP (ma 19)".

`ApkUpdater.effectiveVersion` DA biet so sanh bundle voi APK, nhung cho cam sys.path lai cam vo
dieu kien - do la cho hong.
"""
from __future__ import annotations

import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android")


def _doc(*p):
    with io.open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


class TestBoQuaBundleCu(unittest.TestCase):
    def setUp(self):
        self.src = _doc(KT, "BotForegroundService.kt")
        i = self.src.find("private fun installPythonBundlePath(")
        self.assertGreater(i, 0)
        self.than = self.src[i:self.src.find("\n    private fun ", i + 10)]

    def test_so_bundle_voi_APK_truoc_khi_cam_sys_path(self):
        j = self.than.find("sys.path.insert(0, _p)")
        self.assertGreater(j, 0, "khong con cho cam bundle vao sys.path?")
        truoc = self.than[:j]
        self.assertIn("isNewerVersion(", truoc, "cam bundle vo dieu kien -> bundle cu de len APK")
        self.assertIn("BuildConfig.VERSION_NAME", truoc)

    def test_bundle_khong_moi_hon_thi_RETURN(self):
        i = self.than.find("isNewerVersion(")
        khoi = self.than[i - 200:i + 400]
        self.assertIn("return", khoi, "biet la cu ma van cam vao -> vo nghia")

    def test_bundle_rong_cung_bo_qua(self):
        self.assertIn("bundleVer.isBlank()", self.than)

    def test_co_log_de_biet_dang_chay_code_nao(self):
        i = self.than.find("isNewerVersion(")
        self.assertIn("Log.i", self.than[i:i + 500], "im lang thi user khong biet dang chay ban nao")


class TestIsNewerVersionDungDuocTuNgoai(unittest.TestCase):
    def test_khong_con_private(self):
        s = _doc(KT, "ApkUpdater.kt")
        self.assertIn("internal fun isNewerVersion(", s)
        self.assertNotIn("private fun isNewerVersion(", s)


if __name__ == "__main__":
    unittest.main()
