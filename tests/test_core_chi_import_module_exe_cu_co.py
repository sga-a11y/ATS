"""Core bundle chay TREN exe cu -> chi duoc import module ma exe cu co (ca that 07/10).

Release v1.1.202610071122: bot/bug_report.py them `import uuid`, exe Nuitka 28/09 khong dong goi
`uuid` -> exe cu nap core moi la ModuleNotFoundError ngay luc khoi dong -> bam mo khong co gi xay
ra, user ket (crash truoc khi kip check update). Baseline do THAT tren exe cu bang
tools/do_module_exe.py. Test do = them import moi ma exe cu khong co -> doi cach viet, dung sua
baseline bang tay.
"""
import os
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import do_module_exe as dm   # noqa: E402


class CoreChiImportModuleExeCuCoTest(unittest.TestCase):
    def test_core_hien_tai_khong_import_module_exe_cu_thieu(self):
        loi = dm.kiem_import_core(ROOT)
        self.assertEqual(loi, [], "\n".join(loi))

    def test_baseline_do_tren_exe_cu_khong_co_uuid(self):
        bl = dm.doc_baseline()
        self.assertIn("1.1.202609281436", bl["exe"])     # exe user dang ket 07/10
        self.assertNotIn("uuid", bl["co"])
        self.assertIn("uuid", bl["da_do"])
        for m in ("json", "zipfile", "urllib.request", "ssl", "random", "platform"):
            self.assertIn(m, bl["co"], m)

    def test_bat_duoc_import_moi_ke_ca_trong_ham(self):
        bl = {"exe": {"x": {}}, "co": ["os", "json"], "da_do": ["os", "json", "uuid", "csv"]}
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "bot"))
            with open(os.path.join(d, "run_party_digioi.py"), "w") as f:
                f.write("import os\nfrom bot import a\n")
            with open(os.path.join(d, "bot", "a.py"), "w") as f:
                f.write(textwrap.dedent("""
                    import json
                    from . import b
                    def f():
                        import uuid
                    try:
                        import csv
                    except ImportError:
                        csv = None
                    import zzz_chua_do
                """))
            loi = dm.kiem_import_core(d, bl)
        self.assertEqual(len(loi), 2, loi)
        self.assertIn("'uuid' KHONG co trong exe cu", loi[0])
        self.assertIn("a.py:5", loi[0])
        self.assertIn("'zzz_chua_do' CHUA DO", loi[1])


if __name__ == "__main__":
    unittest.main()
