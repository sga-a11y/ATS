"""Sinh jiugongge.json: cac BANG NHIEM VU 3x3 (九宮格) + co "da nhan thuong" cua tung hang/cot.

Vi sao can file nay: goi server `S:91-1` CHI mang `gridId + 9x(missionId, tien do, xong/chua)` -
KHONG mang trang thai thuong. Client biet "da nhan" nho `BitFlag.Get(JiugonggeInfo.awards[i].getFlag)`
(vinh cuu / 永標, xem S:081-002). Nen phai boc `getFlag` tu file du lieu client.

  JiugonggeInfo_C.dat (Data_JiugonggeInfo.lua):
    [count u32] roi moi ban ghi:
      Id u16, activityId u16, kind u8, kindName u32 (text id), reset u8,
      7 x { awardId u16, quant u32, getFlag u16 }        # 1-3 = hang 1-3, 4-6 = cot 1-3, 7 = TAT CA
  JiugonggeMission_C.dat (Data_JiugonggeMissionData.lua):
    [count u32] roi: Id u16, number u32 (so BANG), kind u8, kindvalue1 u16, description u32 (text id),
                     conditions{ kind u8, kindValue u32, opr u8, value u32 }

LUU Y: EVENT DOI THEO THANG -> file .dat bi GHI DE (cung kich thuoc, khac noi dung!). Chay lai tool
nay sau khi keo data moi tu may:
    adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/JiugonggeInfo_C.dat    gamedata/Data/
    adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/JiugonggeMission_C.dat gamedata/Data/
    adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/TextData_C.dat         gamedata/Data/

BOT KHONG PHU THUOC file nay de biet bang nao dang chay / o nao xong (server gui het). File chi de:
  - BIET line nao DA NHAN -> khoi gui lai (thieu file van chay duoc: gui claim, server tu tu choi).
  - Hien ten bang/nhiem vu trong log cho de doc.

Chay: python tools/crack_jiugongge.py   (-> ghi jiugongge.json)
"""
from __future__ import annotations

import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_scene_names import load_texts        # noqa: E402

OUT = os.path.join(ROOT, "jiugongge.json")
AWARD_LABEL = ("hang 1", "hang 2", "hang 3", "cot 1", "cot 2", "cot 3", "TAT CA")


def _find(name):
    for rel in (("gamedata", "Data", name), ("gamedata", name)):
        p = os.path.join(ROOT, *rel)
        if os.path.isfile(p):
            return p
    raise SystemExit("Khong thay %s (xem docstring de adb pull)" % name)


def read_grids(path, texts):
    d = open(path, "rb").read()
    n = struct.unpack_from("<I", d, 0)[0]
    off, out = 4, {}
    for _ in range(n):
        gid, act, kind = struct.unpack_from("<HHB", d, off)
        off += 5
        kind_name = struct.unpack_from("<I", d, off)[0]
        off += 4
        off += 1                                   # reset
        awards = []
        for _i in range(7):
            aid, quant, flag = struct.unpack_from("<HIH", d, off)
            off += 8
            awards.append({"item": aid, "quant": quant, "flag": flag})
        out[gid] = {"name": texts.get(kind_name, ""), "activity": act, "kind": kind,
                    "awards": awards}
    return out


def read_missions(path, texts):
    d = open(path, "rb").read()
    n = struct.unpack_from("<I", d, 0)[0]
    off, out = 4, {}
    for _ in range(n):
        mid, number, kind, kv1, desc = struct.unpack_from("<HIBHI", d, off)
        off += 13
        c_kind, c_kv, c_opr, c_val = struct.unpack_from("<BIBI", d, off)
        off += 10
        out.setdefault(number, []).append(
            {"id": mid, "desc": texts.get(desc, ""), "need": c_val})
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    texts = load_texts(_find("TextData_C.dat"))
    grids = read_grids(_find("JiugonggeInfo_C.dat"), texts)
    missions = read_missions(_find("JiugonggeMission_C.dat"), texts)
    data = {
        "_note": "AUTO-SINH tu tools/crack_jiugongge.py (JiugonggeInfo_C.dat + JiugonggeMission_C.dat"
                 " + TextData_C.dat). grid_id -> {name, awards[7].flag = co 永標 'da nhan' cua"
                 " hang1-3/cot1-3/TAT CA}. EVENT DOI THEO THANG -> keo data moi roi chay lai tool.",
        "grids": {str(g): v for g, v in sorted(grids.items())},
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print("=> %s: %d bang" % (os.path.basename(OUT), len(grids)))
    for gid, g in sorted(grids.items()):
        flags = [a["flag"] for a in g["awards"]]
        print("   bang %-2d %-32s co 'da nhan' = %s" % (gid, g["name"], flags))
    print()
    for number, ms in sorted(missions.items()):
        if len(ms) == 9:
            print("   panel %-4d: %s" % (number, ", ".join("%s x%d" % (m["desc"], m["need"]) for m in ms[:3])) + " ...")


if __name__ == "__main__":
    main()
