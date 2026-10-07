"""Core tai ve (bot_bundle) hong -> exe VAN MO duoc bang code trong exe (ca that 07/10).

v1.1.202610071122: core moi `import uuid`, exe 28/09 khong co `uuid` -> gui.py chet ngay o
`import run_party_digioi`, truoc ca cua so lan buoc check update -> user bam mo khong thay gi, khong
tu thoat duoc. Gio gui.py ghi core_loi.log, go core, nap ban trong exe.

Kem: core CU HON exe (cai exe moi, bot_bundle cu con sot) -> bo qua core.
Chay trong tien trinh con: bootstrap sua sys.path/sys.meta_path/sys.modules.
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tao_exe_gia(d, core_ver, run_party_src):
    open(os.path.join(d, "aTSBot.exe"), "w").close()
    pc = os.path.join(d, "bot_bundle", "current", "pc")
    os.makedirs(os.path.join(pc, "bot"))
    open(os.path.join(pc, "bot", "__init__.py"), "w").close()
    open(os.path.join(pc, "bot", "config.py"), "w").close()
    with open(os.path.join(pc, "run_party_digioi.py"), "w", encoding="utf-8") as f:
        f.write(run_party_src)
    with open(os.path.join(d, "bot_bundle", "version.txt"), "w") as f:
        f.write(core_ver)
    return pc


def _gui():
    _argv, sys.argv = sys.argv, sys.argv[:1]   # gui -> run_party_digioi doc argv[1] luc import
    try:
        import gui
    finally:
        sys.argv = _argv
    return gui


def _chay(d, code):
    env = dict(os.environ, ATS_TEST="1", ATS_NO_GUARD="1")
    script = textwrap.dedent("""
        import sys, json, logging
        sys.argv = [%r]
        sys.path.insert(0, %r)
        import gui
    """) % (os.path.join(d, "aTSBot.exe"), ROOT) + textwrap.dedent(code)
    r = subprocess.run([sys.executable, "-c", script], cwd=d, env=env,
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError("tien trinh con loi:\n" + r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class GuiCoreLoiVanMoDuocTest(unittest.TestCase):
    def test_core_thieu_module_thi_chay_code_trong_exe(self):
        with tempfile.TemporaryDirectory() as d:
            _tao_exe_gia(d, "1.1.209912312359", textwrap.dedent("""
                import logging
                logging.getLogger().addHandler(logging.NullHandler())   # core hong giua chung
                import module_exe_cu_khong_co_xyz
            """))
            kq = _chay(d, """
                import bot.config, bot.idle_stats
                print(json.dumps({
                    "ctrl": gui.ctrl.__file__, "config": bot.config.__file__,
                    "dang_dung": gui._CORE_DANG_DUNG, "canh_bao": gui._CORE_CANH_BAO,
                    "finder": any(isinstance(f, gui._BundleFirstFinder) for f in sys.meta_path),
                    "null_handler": any(type(h) is logging.NullHandler
                                        for h in logging.getLogger().handlers),
                }))
            """)
            with open(os.path.join(d, "core_loi.log"), encoding="utf-8") as f:
                tb = f.read()
        self.assertEqual(os.path.normcase(kq["ctrl"]), os.path.normcase(os.path.join(ROOT, "run_party_digioi.py")))
        self.assertEqual(os.path.normcase(kq["config"]), os.path.normcase(os.path.join(ROOT, "bot", "config.py")))
        self.assertFalse(kq["dang_dung"])
        self.assertFalse(kq["finder"])
        self.assertFalse(kq["null_handler"], "handler cua core hong phai bi go")
        self.assertTrue(any("CORE TAI VE LOI" in m and "module_exe_cu_khong_co_xyz" in m
                            for m in kq["canh_bao"]), kq["canh_bao"])
        self.assertIn("ModuleNotFoundError", tb)

    def test_core_tot_van_duoc_dung(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as f:
                pc = _tao_exe_gia(d, "1.1.209912312359", f.read() + "\nMARK = 'core'\n")
            bot_src = os.path.join(ROOT, "bot")
            for fn in os.listdir(bot_src):
                if fn.endswith(".py"):
                    shutil.copy(os.path.join(bot_src, fn), os.path.join(pc, "bot", fn))
            with open(os.path.join(pc, "bot", "idle_stats.py"), "a", encoding="utf-8") as f:
                f.write("\nMARK = 'core'\n")
            kq = _chay(d, """
                import bot.idle_stats
                print(json.dumps({"ctrl": gui.ctrl.MARK, "idle": bot.idle_stats.MARK,
                                  "dang_dung": gui._CORE_DANG_DUNG, "canh_bao": gui._CORE_CANH_BAO}))
            """)
        self.assertEqual((kq["ctrl"], kq["idle"]), ("core", "core"))
        self.assertTrue(kq["dang_dung"])
        self.assertEqual(kq["canh_bao"], [])

    def test_core_cu_hon_exe_thi_bo_qua(self):
        with tempfile.TemporaryDirectory() as d:
            _tao_exe_gia(d, "1.1.202609281601", "raise RuntimeError('core cu khong duoc nap')\n")
            kq = _chay(d, """
                gui._CORE_CANH_BAO.clear()
                gui._bootstrap_bundle_path(base=%r, exe_ver="1.1.202610071122")
                print(json.dumps({"dang_dung": gui._CORE_DANG_DUNG, "canh_bao": gui._CORE_CANH_BAO,
                    "finder": any(isinstance(f, gui._BundleFirstFinder) for f in sys.meta_path)}))
            """ % d)
        self.assertFalse(kq["dang_dung"])
        self.assertFalse(kq["finder"])
        self.assertIn("CU HON exe", kq["canh_bao"][0])

    def test_nap_thu_du_moi_import_bot_cap_module_cua_gui(self):
        with open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        can = set()
        for node in tree.body:          # chi cap module (ngoai ham/class)
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module == "bot":
                    can |= {a.name for a in node.names}
                elif node.module.startswith("bot."):
                    can.add(node.module.split(".", 1)[1])
            elif isinstance(node, ast.Import):
                can |= {a.name.split(".", 1)[1] for a in node.names if a.name.startswith("bot.")}
        self.assertEqual(can - set(_gui()._BOT_GUI_NAP_NGAY), set(),
                         "them vao _BOT_GUI_NAP_NGAY trong gui.py")

    def test_so_sanh_version(self):
        f = _gui()._core_cu_hon_exe
        self.assertTrue(f("1.1.202609281601", "1.1.202610071122"))
        self.assertFalse(f("1.1.202610071122", "1.1.202610071122"))
        self.assertFalse(f("1.1.202610080900", "1.1.202610071122"))
        self.assertTrue(f("9.1.1.202609281601", "1.1.202610071122"))   # ghim van so ban that
        for exe in ("1.1.dev", "?", ""):
            self.assertFalse(f("1.1.202609281601", exe), exe)
        self.assertFalse(f("", "1.1.202610071122"))


if __name__ == "__main__":
    unittest.main()
