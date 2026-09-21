# -*- coding: utf-8 -*-
"""Ghi lai van tay cua `documents/CORE_FLOW.md`.

CHI chay khi USER DA CHO PHEP sua file do. Xem `tests/test_core_flow_khoa.py`.

    python tools/khoa_core_flow.py
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "documents", "CORE_FLOW.md")
VAN_TAY = os.path.join(ROOT, "documents", ".core_flow.sha256")


def main():
    if not os.path.exists(FILE):
        print("KHONG THAY documents/CORE_FLOW.md")
        return 1
    with io.open(FILE, "rb") as fh:
        bam = hashlib.sha256(fh.read()).hexdigest()
    cu = ""
    if os.path.exists(VAN_TAY):
        with io.open(VAN_TAY, encoding="utf-8") as fh:
            _noi_dung = fh.read().strip()
        cu = _noi_dung.split()[0] if _noi_dung else ""
    if cu == bam:
        print("van tay KHONG doi -> khong ghi lai gi")
        return 0
    with io.open(VAN_TAY, "w", encoding="utf-8") as fh:
        fh.write("%s  CORE_FLOW.md  (khoa luc %s)\n"
                 % (bam, time.strftime("%Y-%m-%d %H:%M:%S")))
    print("da khoa van tay MOI: %s" % bam)
    print("-> commit CA HAI file (CORE_FLOW.md + .core_flow.sha256) trong cung mot commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
