# -*- coding: utf-8 -*-
"""Loc `train_block_stats.json`: BO pattern tran VA loai quai chiem duoi 1% o diem do.

User chot 26/08: "khong can nguong dau, khi nao can t se bao loc luon file block train, bot do
phai tinh toan nhieu" -> lam sach du lieu o NGUON thay vi bat bot doan nhieu moi lan chon map.
User chot 30/08: nguong 1%.

Vi sao can: mot tran le lac vao cung ghi thanh pattern, va luat "co block 1x2/1x3/1x4 thi loai
luon diem" bien mot ghi nhan 0.2% thanh du de vut ca diem tot nhat.
    'Trai Pham Thanh3 145-146' diem 0: 4x1 426/439 tran (97% - dung y user) ma bi loai chi vi
    DUNG MOT tran '1x3' -> party 1 phai tut xuong map 142-143.

`total` duoc TRU theo so tran da bo, de ti le cac pattern con lai van dung (va diem con cho ghi
them tran moi thay cho cac tran rac vua bo).

Chay:
    python tools/loc_block_stats.py            # xem truoc, KHONG ghi
    python tools/loc_block_stats.py --ghi      # ghi that (co backup .bak)

LUU Y: bot dang chay cung ghi file nay (`record_battle` doc lai file moi tran). Nen chay khi bot
DUNG; chay luc dang chay thi khong hong gi, chi la pattern rac co the duoc ghi lai neu no tai dien.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "train_block_stats.json")
NGUONG = 0.01


def loc_spot(spot: dict, nguong: float = NGUONG):
    """-> (so_pattern_bo, so_tran_bo, [(pattern, count, ti_le)]). Sua `spot` tai cho."""
    patterns = spot.get("patterns") or {}
    tong = sum(int(v) for v in patterns.values())
    if tong <= 0:
        return 0, 0, []
    bo = [(k, int(v), int(v) / tong) for k, v in patterns.items() if int(v) / tong < nguong]
    if not bo:
        return 0, 0, []
    # KHONG bao gio bo het: giu lai it nhat pattern dong nhat (phong ca ky quac moi count deu be).
    if len(bo) == len(patterns):
        giu = max(patterns.items(), key=lambda kv: int(kv[1]))[0]
        bo = [r for r in bo if r[0] != giu]
        if not bo:
            return 0, 0, []
    so_tran = sum(n for _k, n, _t in bo)
    for k, _n, _t in bo:
        patterns.pop(k, None)
    spot["total"] = max(0, int(spot.get("total", 0)) - so_tran)
    # `last_pattern` vua bi bo thi khong con y nghia -> xoa cho khoi hieu nham.
    if spot.get("last_pattern") in {k for k, _n, _t in bo}:
        spot.pop("last_pattern", None)
        spot.pop("last_slots", None)
    return len(bo), so_tran, bo


def loc_mobs(spot: dict, nguong: float = NGUONG):
    """-> (so_loai_bo, so_lan_bo, [(mob_id, count, ti_le)]). Sua `spot` tai cho.

    `mobs` = so lan GAP tung loai quai o diem do. Quai lac vao mot vai lan (con di tuan tu vung
    khac, quai su kien) van duoc ghi -> chon map theo "level quai / so quai / he" bi lech theo
    con quai KHONG PHAI dan cua diem do. User chot 28/08: "so quai thi cung loai nhung quai < 1%".

    Cung nguyen tac voi pattern: KHONG bao gio bo het - giu lai it nhat con dong nhat.
    """
    mobs = spot.get("mobs") or {}
    tong = sum(int(v) for v in mobs.values())
    if tong <= 0:
        return 0, 0, []
    bo = [(k, int(v), int(v) / tong) for k, v in mobs.items() if int(v) / tong < nguong]
    if not bo:
        return 0, 0, []
    if len(bo) == len(mobs):
        giu = max(mobs.items(), key=lambda kv: int(kv[1]))[0]
        bo = [r for r in bo if r[0] != giu]
        if not bo:
            return 0, 0, []
    so_lan = sum(n for _k, n, _t in bo)
    for k, _n, _t in bo:
        mobs.pop(k, None)
    return len(bo), so_lan, bo


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghi", action="store_true", help="ghi de file that (mac dinh chi xem truoc)")
    ap.add_argument("--nguong", type=float, default=NGUONG, help="ti le, mac dinh 0.01 = 1%%")
    ap.add_argument("--file", default=FILE)
    a = ap.parse_args(argv)

    with open(a.file, encoding="utf-8") as f:
        data = json.load(f)

    tong_pat = tong_tran = 0
    tong_mob = tong_lan = 0
    dong = []
    for mkey, mval in (data.get("maps") or {}).items():
        for skey, spot in (mval.get("spots") or {}).items():
            n_pat, n_tran, bo = loc_spot(spot, a.nguong)
            if n_pat:
                tong_pat += n_pat
                tong_tran += n_tran
                for k, n, ti in sorted(bo, key=lambda r: -r[1]):
                    dong.append("map %-6s %-12s  tran %-14s %5d (%.2f%%)"
                                % (mkey, skey, k, n, ti * 100))
            n_mob, n_lan, bo_m = loc_mobs(spot, a.nguong)
            if n_mob:
                tong_mob += n_mob
                tong_lan += n_lan
                for k, n, ti in sorted(bo_m, key=lambda r: -r[1]):
                    dong.append("map %-6s %-12s  quai %-14s %5d (%.2f%%)"
                                % (mkey, skey, k, n, ti * 100))

    for d in dong[:60]:
        print(d)
    if len(dong) > 60:
        print("... va %d dong nua" % (len(dong) - 60))
    print("-" * 60)
    print("BO %d pattern / %d tran, %d loai quai / %d lan gap (nguong %.2f%%)"
          % (tong_pat, tong_tran, tong_mob, tong_lan, a.nguong * 100))

    if not a.ghi:
        print("(xem truoc - chua ghi. Them --ghi de ghi that)")
        return 0
    if tong_pat or tong_mob:
        shutil.copy2(a.file, a.file + ".bak")
        # DUNG DINH DANG cua `train_block_stats._save_unlocked` (indent=2): file nay bot ghi de
        # lien tuc, ghi khac dinh dang thi diff git thanh vo nghia + lan ghi sau cua bot lai doi
        # nguoc ca file.
        with open(a.file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("da ghi %s (backup: %s.bak)" % (a.file, os.path.basename(a.file)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
