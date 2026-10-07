"""DO + CHAN: code core (bot/*.py, run_party_digioi.py) chi duoc import module MA EXE CU CO.

Vi sao (ca that 07/10, release v1.1.202610071122): exe Nuitka standalone chi dong goi nhung module
thu vien chuan ma code LUC BUILD exe co import. Core bundle tai ve sau do chay TREN exe cu -> core
moi `import uuid` (bot/bug_report.py) ma exe 28/09 khong co `uuid` -> ModuleNotFoundError ngay luc
nap `run_party_digioi` -> exe khong console chet im lang, bam mo "khong co gi xay ra". Moi user
dang exe cu bi ket (crash TRUOC khi kip check update).

Hai viec:
  1. `python tools/do_module_exe.py <thu muc co aTSBot.exe> [...]`
     DO THAT exe do co nhung module nao: chep exe ra thu muc tam, cam 1 core GIA (run_party_digioi
     tu liet ke module bang importlib.util.find_spec roi thoat), chay exe, doc ket qua. Ghi vao
     `tools/exe_module_baseline.json` (moi exe 1 muc, `co` = GIAO cac exe da do).
  2. `kiem_import_core(root)` - goi tu build_product.py + tests: quet AST moi import trong core,
     import nao khong nam trong baseline -> tra danh sach loi (build DUNG).

Doi baseline (vd bo ho tro exe qua cu, hoac can module moi): xem documents/AUTO_UPDATE.md.
"""
from __future__ import annotations

import ast
import json
import os
import pkgutil
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "tools", "exe_module_baseline.json")
CORE_TOP = ("bot", "run_party_digioi", "train_bot")   # code cua minh, nam trong bundle
# Package stdlib bo qua khi liet ke submodule (to, chi la tool/test cua CPython, import co tac dung phu)
_BO_PKG = {"test", "idlelib", "turtledemo", "lib2to3", "ensurepip", "venv", "pydoc_data",
           "__phello__", "tkinter.test", "unittest.test", "distutils"}


# ------------------------------------------------------------------ quet import trong core

def file_core(root=ROOT):
    out = [os.path.join(root, "run_party_digioi.py")]
    bot = os.path.join(root, "bot")
    out += sorted(os.path.join(bot, f) for f in os.listdir(bot) if f.endswith(".py"))
    return [f for f in out if os.path.isfile(f)]


_BAT_IMPORT = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


def _try_bat_import(node: ast.Try) -> bool:
    for h in node.handlers:
        if h.type is None:
            return True
        ten = [h.type] if not isinstance(h.type, ast.Tuple) else list(h.type.elts)
        for t in ten:
            if isinstance(t, ast.Name) and t.id in _BAT_IMPORT:
                return True
            if isinstance(t, ast.Attribute) and t.attr in _BAT_IMPORT:
                return True
    return False


def _la_module_dev(ten: str) -> bool:
    """`from X import Y`: Y la SUBMODULE (can co trong exe) hay chi la thuoc tinh cua X."""
    try:
        import importlib.util
        return importlib.util.find_spec(ten) is not None
    except Exception:
        return False


def quet_import(path: str):
    """[(ten_module, dong)] moi import TUYET DOI ngoai code cua minh. Bo qua import nam trong
    `try` co bat ImportError/Exception (code da tu lo truong hop thieu module)."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    out = []

    def di(node, duoc_bao_ve):
        if isinstance(node, ast.Try):
            bv = duoc_bao_ve or _try_bat_import(node)
            for n in node.body:
                di(n, bv)
            for n in node.handlers + node.orelse + node.finalbody:
                di(n, duoc_bao_ve)
            return
        if isinstance(node, ast.Import) and not duoc_bao_ve:
            for a in node.names:
                out.append((a.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and not duoc_bao_ve and node.level == 0 and node.module:
            out.append((node.module, node.lineno))
            for a in node.names:
                con = node.module + "." + a.name
                if a.name != "*" and _la_module_dev(con) and "." not in a.name:
                    out.append((con, node.lineno))
        for n in ast.iter_child_nodes(node):
            di(n, duoc_bao_ve)

    di(tree, False)
    return [(m, ln) for m, ln in out if m.split(".")[0] not in CORE_TOP]


def tat_ca_import(root=ROOT):
    """{ten_module: [(file, dong), ...]}"""
    res = {}
    for f in file_core(root):
        for m, ln in quet_import(f):
            res.setdefault(m, []).append((os.path.relpath(f, root), ln))
    return res


def doc_baseline(path=BASELINE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def kiem_import_core(root=ROOT, baseline=None):
    """[] = OK. Con lai: moi dong 1 loi, kem file:dong de sua."""
    bl = baseline or doc_baseline()
    co = set(bl.get("co") or [])
    da_do = set(bl.get("da_do") or [])
    loi = []
    for m, cho in sorted(tat_ca_import(root).items()):
        if m in co:
            continue
        noi = ", ".join("%s:%d" % c for c in cho[:3])
        if m in da_do:
            loi.append("'%s' KHONG co trong exe cu (%s) - dung tai %s"
                       % (m, ", ".join(bl.get("exe", {}).keys()), noi))
        else:
            loi.append("'%s' CHUA DO tren exe cu - dung tai %s (chay lai tools/do_module_exe.py)"
                       % (m, noi))
    return loi


# ------------------------------------------------------------------ do module that cua exe

def ten_can_do(root=ROOT):
    """Top-level stdlib + moi submodule stdlib + moi ten core dang import."""
    ten = set(sys.stdlib_module_names)
    for mod in list(sys.stdlib_module_names):
        if mod in _BO_PKG or mod.startswith("_"):
            continue
        try:
            import importlib.util
            spec = importlib.util.find_spec(mod)
        except Exception:
            continue
        if not spec or not spec.submodule_search_locations:
            continue
        for info in pkgutil.walk_packages(spec.submodule_search_locations, mod + "."):
            if any(info.name == b or info.name.startswith(b + ".") for b in _BO_PKG):
                continue
            ten.add(info.name)
    ten |= set(tat_ca_import(root))
    return sorted(ten)


_PROBE = r'''
import sys, json, os, importlib.util
TEN = %(ten)r
co = []
for n in TEN:
    try:
        if importlib.util.find_spec(n) is not None:
            co.append(n)
    except Exception:
        pass
with open(%(out)r, "w", encoding="utf-8") as f:
    json.dump({"python": sys.version.split()[0], "co": co}, f)
os._exit(0)
'''


def do_exe(exe_dir: str, ten=None, timeout=90):
    """Chay exe that voi core gia -> {"version", "python", "co"}."""
    exe = os.path.join(exe_dir, "aTSBot.exe")
    if not os.path.isfile(exe):
        raise FileNotFoundError(exe)
    ten = ten or ten_can_do()
    tmp = tempfile.mkdtemp(prefix="do_exe_")
    try:
        shutil.copy2(exe, tmp)
        ver = "?"
        try:
            with open(os.path.join(exe_dir, "version.json"), encoding="utf-8") as f:
                v = json.load(f)
            ver = str(v.get("pinned_real_version") or v.get("pc_app_version") or v.get("version") or "?")
        except Exception:
            pass
        pc = os.path.join(tmp, "bot_bundle", "current", "pc")
        os.makedirs(os.path.join(pc, "bot"))
        open(os.path.join(pc, "bot", "config.py"), "w").close()
        out = os.path.join(tmp, "_ket_qua.json")
        with open(os.path.join(pc, "run_party_digioi.py"), "w", encoding="utf-8") as f:
            f.write(_PROBE % {"ten": ten, "out": out})
        p = subprocess.Popen([os.path.join(tmp, "aTSBot.exe")], cwd=tmp)
        han = time.time() + timeout
        while time.time() < han and not os.path.isfile(out):
            time.sleep(0.5)
        time.sleep(1)
        if p.poll() is None:
            subprocess.run(["taskkill", "/f", "/t", "/pid", str(p.pid)], capture_output=True)
        if not os.path.isfile(out):
            raise RuntimeError("exe %s khong nap core gia (ban truoc 08/08 khong dung bundle?)" % ver)
        with open(out, encoding="utf-8") as f:
            kq = json.load(f)
        kq["version"] = ver
        return kq
    finally:
        for _ in range(10):
            try:
                shutil.rmtree(tmp)
                break
            except OSError:
                time.sleep(1)


def ghi_baseline(ket_qua, path=BASELINE):
    try:
        bl = doc_baseline(path)
    except Exception:
        bl = {}
    exe = dict(bl.get("exe") or {})
    da_do = set(bl.get("da_do") or [])
    for kq, ten in ket_qua:
        exe[kq["version"]] = {"python": kq["python"], "co": sorted(kq["co"])}
        da_do |= set(ten)
    co = None
    for v in exe.values():
        co = set(v["co"]) if co is None else co & set(v["co"])
    bl = {
        "ghi_chu": "Sinh boi tools/do_module_exe.py - KHONG sua tay. 'co' = module MOI exe da do "
                   "deu co; core chi duoc import trong nay. Xem documents/AUTO_UPDATE.md.",
        "exe": {k: exe[k] for k in sorted(exe)},
        "da_do": sorted(da_do),
        "co": sorted(co or ()),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bl, f, ensure_ascii=False, indent=1)
    return bl


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    ten = ten_can_do()
    kq = []
    for d in argv:
        r = do_exe(d, ten)
        print("exe v%s (python %s): %d/%d module" % (r["version"], r["python"], len(r["co"]), len(ten)))
        kq.append((r, ten))
    bl = ghi_baseline(kq)
    print("baseline: %d module chung cho %d exe -> %s" % (len(bl["co"]), len(bl["exe"]), BASELINE))
    loi = kiem_import_core()
    for d in loi:
        print("  LOI:", d)
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
