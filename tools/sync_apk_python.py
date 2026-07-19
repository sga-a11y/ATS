"""Dong bo source Python PC -> APK de 1 NGUON DUY NHAT (fix 1 lan an ca 2 ban).

Copy cac file CHUNG (bot/*.py + run_party_digioi.py) tu ban PC vao APK train_bot/, doi import
tuyet doi 'from bot' -> tuong doi 'from .' cho run_party_digioi (file chung da dung 'from .' san).

CHAY TRUOC MOI LAN BUILD APK:  python tools/sync_apk_python.py
File RIENG cua APK (KHONG dong bo): config.py (doc asset), __init__.py, _appdir.py, train_runner.py
(adapter Kotlin), party_state.py (neu con).
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK = os.path.join(ROOT, "android", "app", "src", "main", "python", "train_bot")

# File CHUNG: copy y nguyen (import 'from . import ...' da tuong thich package train_bot).
SHARED = ["client.py", "combat.py", "state.py", "protocol.py", "auth.py", "login.py",
          "train_block_stats.py", "mob_scanner.py"]

# File PC-only can cho coordinator/client neu co import (pathfind dung boi navigate). Copy neu ton tai.
OPTIONAL = ["pathfind.py", "world_nav.py", "smart_route.py"]


def _rewrite_coordinator(src: str) -> str:
    """run_party_digioi.py o ROOT (khong trong package) dung 'from bot ...' tuyet doi -> khi vao
    package train_bot phai doi thanh tuong doi 'from . ...'."""
    src = src.replace("from bot import config", "from . import config")
    src = src.replace("from bot.login import login", "from .login import login")
    src = src.replace("from bot.client import", "from .client import")
    src = src.replace("from bot._appdir import", "from ._appdir import")   # log path Android (PC khong co bot/_appdir -> fallback except)
    return src


def main():
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


if __name__ == "__main__":
    main()
