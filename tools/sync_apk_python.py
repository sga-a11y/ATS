"""Dong bo source Python PC -> APK de 1 NGUON DUY NHAT (fix 1 lan an ca 2 ban).

Copy cac file CHUNG (bot/*.py + run_party_digioi.py) tu ban PC vao APK train_bot/, doi import
tuyet doi 'from bot' -> tuong doi 'from .' cho run_party_digioi (file chung da dung 'from .' san).

CHAY TRUOC MOI LAN BUILD APK:  python tools/sync_apk_python.py
File RIENG cua APK (KHONG dong bo): config.py (doc asset), __init__.py, _appdir.py, train_runner.py
(adapter Kotlin), party_state.py (neu con).
"""
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK = os.path.join(ROOT, "android", "app", "src", "main", "python", "train_bot")

# File CHUNG: copy y nguyen (import 'from . import ...' da tuong thich package train_bot).
SHARED = ["client.py", "combat.py", "state.py", "protocol.py", "auth.py", "login.py",
          "train_block_stats.py", "mob_scanner.py", "mob_spots.py", "scene_fight.py",
          "train_maps_store.py", "npc40.py", "pet_login_stats.py", "team_dungeon_lv110.py",
          "floor_crawl.py",
          # Core dung chung nhung TRUOC DAY BI BO SOT khoi danh sach -> APK chay ban cu am
          # tham (party_battle.py lech 48 dong: fix "khong nuot lenh danh" khong len APK).
          # 5 file con lai dang trung khop nhung khong duoc sync = bom hen gio.
          "party_battle.py", "battle_tracker.py", "pathfind.py", "scan_image.py",
          "smart_route.py", "world_nav.py"]

# File CHI CO o ban PC - phai liet ke TUONG MINH. Moi file .py trong bot/ khong nam trong
# SHARED cung khong nam o day se lam sync BAO LOI, khong cho build tiep (xem _check_no_drift).
PC_ONLY = ["config.py",        # APK doc tu asset, cau truc khac han
           "_appdir.py",       # duong dan he thong, khac nen tang
           "_version.py", "_guard.py", "updater.py", "donate_qr_data.py",   # chi ban PC dung
           "__init__.py"]

SHARED_ASSETS = ["events.json", "npc_names.json", "use_items.json", "dangerous_npcs.json",
                 "scene_names.json"]

# File PC-only can cho coordinator/client neu co import (pathfind dung boi navigate). Copy neu ton tai.
OPTIONAL = ["pathfind.py", "world_nav.py", "smart_route.py"]


def _rewrite_coordinator(src: str) -> str:
    """run_party_digioi.py o ROOT (khong trong package) dung 'from bot ...' tuyet doi -> khi vao
    package train_bot phai doi thanh tuong doi 'from . ...'."""
    # TONG QUAT bang regex, KHONG chep tay tung dong: truoc day la danh sach cung nen them
    # `from bot import X` moi la SOT -> ban APK giu nguyen import tuyet doi -> ImportError.
    # Da dinh that: `from bot import scan_image` (dong 222) khong duoc doi, may man nam trong
    # try/except nen chi mat anh scan; cho khac thi crash.
    src = re.sub(r"(?m)^(\s*)from bot import ", r"\g<1>from . import ", src)
    src = re.sub(r"(?m)^(\s*)from bot\.(\w+) import ", r"\g<1>from .\g<2> import ", src)
    src = re.sub(r"(?m)^(\s*)import bot\.(\w+) as (\w+)$", r"\g<1>from . import \g<2> as \g<3>", src)
    src = re.sub(r"(?m)^(\s*)import bot\.(\w+)$", r"\g<1>from . import \g<2>", src)
    return src


def _check_no_drift():
    """CHAN viec them file vao bot/ ma quen dong bo sang APK.

    Rule cua user: "APK giong het PC". Truoc day SHARED la allowlist chep tay -> party_battle.py
    bi bo sot, APK chay ban cu 48 dong am tham: build van chay, chi khac HANH VI (fix "khong nuot
    lenh danh" khong len APK, khong ai biet). Gio thieu khai bao la BAO LOI ngay.
    """
    have = {f for f in os.listdir(os.path.join(ROOT, "bot")) if f.endswith(".py")}
    unknown = sorted(have - set(SHARED) - set(OPTIONAL) - set(PC_ONLY))
    if unknown:
        raise SystemExit(
            "SYNC DUNG: file trong bot/ chua khai bao: "
            + ", ".join(unknown)
            + " | dung chung ca 2 ban -> them vao SHARED"
            + " | chi rieng ban PC -> them vao PC_ONLY"
            + " (bo qua im lang = APK chay code cu, y het bug party_battle.py)"
        )


def _check_no_abs_bot_import():
    """Ban APK KHONG duoc con import tuyet doi `bot.*` (package do khong ton tai tren Android)."""
    import glob
    bad = []
    for f in glob.glob(os.path.join(APK, "*.py")):
        for i, line in enumerate(open(f, encoding="utf-8"), 1):
            if re.match(r"\s*(from bot[ .]|import bot)", line):
                bad.append("%s:%d %s" % (os.path.basename(f), i, line.strip()[:60]))
    if bad:
        raise SystemExit("SYNC DUNG: ban APK con import tuyet doi 'bot.*': " + " | ".join(bad))


def _check_synced():
    """Sau khi copy: doi chieu lai tung byte, lech la BAO LOI (copy hong/ghi de nguoc)."""
    bad = []
    for f in SHARED:
        a = os.path.join(ROOT, "bot", f)
        b = os.path.join(APK, f)
        if not os.path.exists(b) or open(a, "rb").read() != open(b, "rb").read():
            bad.append(f)
    if bad:
        raise SystemExit("SYNC DUNG: copy xong van LECH: %s" % ", ".join(bad))


def main():
    _check_no_drift()
    for f in SHARED:
        shutil.copy(os.path.join(ROOT, "bot", f), os.path.join(APK, f))
        print("synced (shared):", f)
    for f in OPTIONAL:
        s = os.path.join(ROOT, "bot", f)
        if os.path.exists(s):
            shutil.copy(s, os.path.join(APK, f))
            print("synced (optional):", f)
    with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        src = fh.read()
    with open(os.path.join(APK, "run_party_digioi.py"), "w", encoding="utf-8") as fh:
        fh.write(_rewrite_coordinator(src))
    print("synced (coordinator): run_party_digioi.py (import bot -> relative)")
    asset_dir = os.path.join(ROOT, "android", "app", "src", "main", "assets", "train_bot_data")
    for f in SHARED_ASSETS:
        shutil.copy(os.path.join(ROOT, f), os.path.join(asset_dir, f))
        print("synced (asset):", f)


if __name__ == "__main__":
    main()
    _check_synced()
    _check_no_abs_bot_import()
    print("OK: PC va APK giong het nhau (%d file shared)" % len(SHARED))
