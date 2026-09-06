"""Ban APK cua `config.py` phai co DU moi ham ma code DUNG CHUNG goi qua `config.<ten>`.

`config.py` la PC_ONLY (`tools/sync_apk_python.py`): ban APK doc asset thay vi doc file nen cau
truc khac han, sync KHONG chep no. Tuc day la mot cho CHEP TAY nua - dung cai bay "chep tay o dau
la lech o do" trong CLAUDE.md. Va lech o day KHONG lam build hong: no nem AttributeError GIUA LUC
CHAY, tren may user.

Da xay ra that (06/09/2026): them `event_hom_nay()` vao `bot/config.py` cho lich loan dau T5/T7,
quen ban APK. Build xanh, test xanh, APK cai duoc - roi moi acc mode event tren dien thoai deu:

    13:31:35 [quanhai] (member) MODE=event start_city=0
    13:31:35 [quanhai] LOI: module 'train_bot.config' has no attribute 'event_hom_nay'
    13:36:25 [quanhai] SERVER NGAT KET NOI: DANG NHAP TRUNG LAP (ma 19)

Acc dung im o map event, supervisor relogin lien tuc, hai phien chong nhau -> ma 19.
"""
from __future__ import annotations

import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _sync_mod():
    spec = importlib.util.spec_from_file_location(
        "_sync", os.path.join(ROOT, "tools", "sync_apk_python.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestAPKConfigDuHam(unittest.TestCase):
    def setUp(self):
        self.m = _sync_mod()
        self.apk_cfg = os.path.join(self.m.APK, "config.py")

    def test_khong_thieu_ham_nao(self):
        goi = set()
        nguon = [os.path.join(ROOT, "bot", f) for f in self.m.SHARED + self.m.OPTIONAL]
        nguon.append(os.path.join(ROOT, "run_party_digioi.py"))
        for f in nguon:
            if not os.path.exists(f):
                continue
            with io.open(f, encoding="utf-8") as fh:
                goi |= set(re.findall(
                    r"(?<![A-Za-z0-9_])config[.]([a-z_][a-z0-9_]*)[ ]*[(]", fh.read()))
        with io.open(self.apk_cfg, encoding="utf-8") as fh:
            co = set(re.findall(r"^def ([a-z_][a-z0-9_]*)", fh.read(), re.M))
        thieu = sorted(n for n in goi - co if not n.startswith("_"))
        self.assertEqual(thieu, [], "ban APK cua config.py thieu ham -> AttributeError luc CHAY")

    def test_event_hom_nay_co_o_CA_HAI_ban(self):
        """Ham cu the da lam hong ban APK 06/09."""
        for f in (os.path.join(ROOT, "bot", "config.py"), self.apk_cfg):
            with io.open(f, encoding="utf-8") as fh:
                self.assertIn("def event_hom_nay(", fh.read(), f)

    def test_hai_ban_cho_ket_qua_GIONG_NHAU(self):
        """Khong chi 'co ton tai' - phai cung hanh vi tren cung du lieu."""
        import bot.config as pc
        spec = importlib.util.spec_from_file_location("_apkcfg", self.apk_cfg)
        try:
            ac = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ac)
        except Exception:
            self.skipTest("ban APK cua config khong nap duoc ngoai Android")
        for key in ("loan_dau", "khong_co_that"):
            self.assertEqual(bool(pc.event_hom_nay(key)), bool(ac.event_hom_nay(key)), key)


class TestCongChan(unittest.TestCase):
    """CONG 7 trong sync_apk_python.py - build phai DUNG, khong ra ban thieu."""

    def setUp(self):
        self.m = _sync_mod()
        self.apk_cfg = os.path.join(self.m.APK, "config.py")

    def test_co_cong__check_config_api(self):
        with io.open(os.path.join(ROOT, "tools", "sync_apk_python.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("def _check_config_api(", src)
        self.assertIn("_check_config_api()", src.split('if __name__')[-1], "cong chua duoc goi")

    def test_cong_BAT_duoc_khi_thieu(self):
        d = tempfile.mkdtemp()
        bak = os.path.join(d, "config.py")
        shutil.copy(self.apk_cfg, bak)
        try:
            with io.open(bak, encoding="utf-8") as fh:
                s = fh.read()
            s = s.replace("def event_hom_nay(key", "def event_hom_nay_DA_XOA(key", 1)
            with io.open(self.apk_cfg, "w", encoding="utf-8", newline="") as fh:
                fh.write(s)
            with self.assertRaises(SystemExit) as e:
                self.m._check_config_api()
            self.assertIn("event_hom_nay", str(e.exception))
        finally:
            shutil.copy(bak, self.apk_cfg)

    def test_cong_KHONG_bao_nham_furnace_config_get(self):
        """`furnace_config.get(` khong phai module `config` - bat nham la cong keu suot."""
        self.m._check_config_api()   # khong duoc nem gi

    def test_file_cong_khong_dinh_byte_la(self):
        """Bay heredoc trong CLAUDE.md: `\\b` thanh byte backspace 0x08 that -> regex khong khop
        gi ca ma nhin bang mat van thay dung. Da dinh dung luc viet cong nay (06/09)."""
        with io.open(os.path.join(ROOT, "tools", "sync_apk_python.py"), encoding="utf-8") as fh:
            s = fh.read()
        la = sorted({hex(ord(c)) for c in s if ord(c) < 9 or 11 <= ord(c) <= 31})
        self.assertEqual(la, [], "file co byte dieu khien -> regex/chuoi hong am tham")


if __name__ == "__main__":
    unittest.main()
