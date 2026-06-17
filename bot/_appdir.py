"""Thu muc goc de doc/ghi file config (JSON). Tach biet dev vs ban dong goi (.exe):
 - DEV (chay python): goc project (thu muc cha cua bot/).
 - FROZEN (PyInstaller / Nuitka onefile): thu muc chua file .exe -> file JSON nam CANH .exe,
   nguoi dung SUA duoc (KHONG nam trong temp -> tranh mat khi dong app)."""
import os
import sys


def app_dir() -> str:
    # PyInstaller: sys.frozen=True, sys.executable = duong dan .exe
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    # Nuitka (onefile/standalone): moi module compiled co bien global __compiled__.
    # sys.argv[0] = duong dan .exe goc (code chay tu temp nhung argv[0] van la .exe).
    if "__compiled__" in globals():
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    # DEV
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
