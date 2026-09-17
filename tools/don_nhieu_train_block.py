# -*- coding: utf-8 -*-
"""DON NHIEU trong `train_block_stats.json` (user chot 17/09).

    * block (pattern) nao < 1% so tran cua diem  -> XOA
    * he quai (npc) nao < 10 con                 -> XOA

VI SAO: hai bo dem nay ghi theo cai bot THAY luc danh, nen bat duoc ca thu khong thuoc ve diem:
quai lac tu bay ben canh, mot tran phuc kich, mot lan bot dung sai cho vai giay. Chung de lai
nhung dong chiem vai phan nghin nhung van hien trong bang thong ke va lam sai ca "diem nay co
may con".
Vi du that (map 14801): `17162` gap 4843 con, `17163` gap 3 con - dong thu hai la nhieu.

RANG BUOC PHAI GIU:
  * `total` LUON bang tong `patterns` (dung o toan bo 857 diem hien co) -> xoa pattern thi phai
    tru `total` dung bang ngan ay tran.
  * `last_pattern` phai la mot pattern CON TON TAI - no duoc doc de hien "lan gan nhat danh kieu
    gi"; tro toi cai vua xoa la bang thong ke hien mot kieu khong con trong danh sach.
  * KHONG xoa ca diem: `mobs` rong chi nghia la "chua quet du quai", con `patterns` thi khong
    diem nao bi xoa sach (da kiem truoc khi lam).

Chay:
    python tools/don_nhieu_train_block.py          # xem truoc, KHONG ghi
    python tools/don_nhieu_train_block.py --ghi    # ghi that (co backup .bak)
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "train_block_stats.json")

NGUONG_PATTERN = 0.01     # < 1% so tran cua diem
NGUONG_MOB = 10           # < 10 con


def don(data):
    """Sua TAI CHO. Tra ve dict thong ke nhung gi da bo."""
    tk = {"pattern_xoa": 0, "tran_xoa": 0, "mob_xoa": 0, "con_xoa": 0,
          "last_pattern_sua": 0, "spot": 0, "map": 0}
    for _m, v in (data.get("maps") or {}).items():
        tk["map"] += 1
        for _s, sv in (v.get("spots") or {}).items():
            tk["spot"] += 1
            tot = int(sv.get("total") or 0)
            pats = sv.get("patterns") or {}
            if tot and pats:
                bo = {k for k, c in pats.items() if int(c) < tot * NGUONG_PATTERN}
                if bo:
                    _mat = sum(int(pats[k]) for k in bo)
                    for k in bo:
                        del pats[k]
                    tk["pattern_xoa"] += len(bo)
                    tk["tran_xoa"] += _mat
                    # `total` phai bang tong `patterns` - xem docstring.
                    sv["total"] = max(0, tot - _mat)
                    if sv.get("last_pattern") in bo:
                        # Lay kieu danh NHIEU NHAT con lai thay cho cai vua xoa.
                        sv["last_pattern"] = (max(pats, key=lambda k: int(pats[k]))
                                              if pats else None)
                        sv.pop("last_slots", None)
                        tk["last_pattern_sua"] += 1
            mobs = sv.get("mobs")
            if mobs:
                bo_m = {k for k, c in mobs.items() if int(c) < NGUONG_MOB}
                if bo_m:
                    tk["con_xoa"] += sum(int(mobs[k]) for k in bo_m)
                    for k in bo_m:
                        del mobs[k]
                    tk["mob_xoa"] += len(bo_m)
                if not mobs:
                    sv.pop("mobs", None)     # rong = "chua quet du quai", giong luc chua co
    return tk


def main():
    ghi = "--ghi" in sys.argv
    with io.open(FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    truoc_pat = sum(len((sv.get("patterns") or {}))
                    for v in data["maps"].values() for sv in (v.get("spots") or {}).values())
    truoc_mob = sum(len((sv.get("mobs") or {}))
                    for v in data["maps"].values() for sv in (v.get("spots") or {}).values())
    tk = don(data)
    print("map %d | diem %d" % (tk["map"], tk["spot"]))
    print("block  : %d -> %d  (xoa %d, mat %d tran)"
          % (truoc_pat, truoc_pat - tk["pattern_xoa"], tk["pattern_xoa"], tk["tran_xoa"]))
    print("he quai: %d -> %d  (xoa %d, mat %d con)"
          % (truoc_mob, truoc_mob - tk["mob_xoa"], tk["mob_xoa"], tk["con_xoa"]))
    print("last_pattern phai chot lai: %d" % tk["last_pattern_sua"])
    # Bat bien: `total` == tong `patterns`
    lech = [(m, s) for m, v in data["maps"].items()
            for s, sv in (v.get("spots") or {}).items()
            if int(sv.get("total") or 0) != sum(int(x) for x in (sv.get("patterns") or {}).values())]
    if lech:
        print("LOI: %d diem co total != tong patterns -> KHONG ghi" % len(lech))
        return 1
    if not ghi:
        print("\n(xem truoc - chua ghi gi. Them --ghi de ghi that)")
        return 0
    shutil.copy2(FILE, FILE + ".bak")
    with io.open(FILE, "w", encoding="utf-8") as fh:
        # GIU DUNG DANG BOT VAN GHI (`bot/train_block_stats.py`: indent=2, khong sort) - khac di
        # thi lan bot ghi ke tiep se sinh mot diff khong lo toan file.
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print("\nda ghi %s (ban cu: %s.bak)" % (FILE, os.path.basename(FILE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
