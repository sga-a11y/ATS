"""Mode "cleanbag" (Don tui - placeholder) da bo 04/10/2026: don tui that la tick "Tu don tui do"
trong Cai dat nang cao. Config cu con luu "cleanbag" phai chay nhu "stand", khong treo mode la."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK_PY = os.path.join(ROOT, "android", "app", "src", "main", "python", "train_bot")


def _doc(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return f.read()


class TestBoModeCleanbag(unittest.TestCase):
    def test_gui_khong_con_mode_cleanbag(self):
        src = _doc(ROOT, "gui.py")
        khoi = re.search(r"MODE_OPTIONS = \[(.*?)\n\]", src, re.S).group(1)
        self.assertNotIn("cleanbag", khoi)
        self.assertNotIn("Dọn dẹp túi đồ (chưa làm", src)
        self.assertIn('_MODE_CU = {"cleanbag": "stand"}', src)

    def test_config_cu_cleanbag_doi_thanh_stand(self):
        for f in (os.path.join(ROOT, "bot", "config.py"), os.path.join(APK_PY, "config.py")):
            self.assertIn('{"cleanbag": "stand"}.get(_party.get("mode", "stand")', _doc(f), f)

    def test_party_modes_khong_con_cleanbag(self):
        for f in (os.path.join(ROOT, "bot", "party_modes.py"),
                  os.path.join(APK_PY, "party_modes.py")):
            self.assertNotIn("cleanbag", _doc(f), f)


if __name__ == "__main__":
    unittest.main()
