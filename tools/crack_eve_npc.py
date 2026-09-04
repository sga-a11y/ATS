# -*- coding: utf-8 -*-
"""Liet ke NPC cua mot scene trong `CompreseData/Eve.emg`.

Vi sao can: mo thoai NPC la goi `0x20 sub0200 + <id NPC TRONG SCENE>` (xem sell_noi_dat dung
`0x20 02 00 08`). So `08` do KHONG phai npcId toan cuc ma la `Eve_NpcData.id` - so thu tu cua
NPC trong chinh scene do. Doan so nay la sai va dat (goi nham -> server coi la vi pham).
File nay doc thang bang NpcData nen tra ve THANG id dung, kem toa do de biet phai di toi dau.

Cau truc mot ban ghi: xem `Data_Eve_Eve_NpcData.lua` (doc tuan tu, khong co truong do dai tong).

Dung:
    python tools/crack_eve_npc.py --scene 12263
    python tools/crack_eve_npc.py --scene 12263 --ten "tien trang"
"""
import argparse
import json
import os
import struct

from crack_eve_surface import EVE_DEFAULT, read_index


def _npc_names():
    try:
        with open("npc_names.json", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def read_npcs(data, offset):
    """[(id, npcId, x, y)] - doc dung thu tu truong cua Eve_NpcData.New."""
    cur = offset
    count = struct.unpack_from("<i", data, cur)[0]
    cur += 4
    out = []
    for _ in range(count):
        nid, npc_id, ec = struct.unpack_from("<HHH", data, cur)
        cur += 6 + ec                      # id + npcId + eventCount + events
        cur += 1 + data[cur]               # saleKindCount + saleKinds
        mn = data[cur]
        cur += 1 + (mn + 1) * 8            # motionNodeCount + (mn+1) node x2 i32
        cur += 3 + 1 + 2 + 1               # motionType/Back/CycleNum + direction + suspendMS + speedLv
        cur += 16                          # roleGrid (4 x i32)
        cur += 8                           # moveOffsetGrid
        x, y = struct.unpack_from("<ii", data, cur)
        cur += 8                           # position
        cur += 1 + 1 + 2 + 1 + 1           # roleStatus
        cur += 16 + 16                     # innerNode + outerNode
        cur += 1 + 2 + 1                   # traceSpeedLv + traceRadius + close
        out.append((nid, npc_id, x, y))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eve", default=EVE_DEFAULT)
    ap.add_argument("--scene", type=int, required=True)
    ap.add_argument("--ten", help="chi in NPC co ten chua chuoi nay (khong phan biet hoa thuong)")
    a = ap.parse_args()

    with open(a.eve, "rb") as fh:
        data = fh.read()
    idx = read_index(data)
    if a.scene not in idx:
        raise SystemExit("scene %d khong co trong Eve.emg" % a.scene)
    off, _size = idx[a.scene]
    ten = _npc_names()
    print("scene %d:" % a.scene)
    for nid, npc_id, x, y in read_npcs(data, off):
        nm = ten.get(str(npc_id)) or ten.get(npc_id) or ""
        if a.ten and a.ten.lower() not in str(nm).lower():
            continue
        print("  id=%-3d npcId=%-6d pos=(%d,%d)  %s" % (nid, npc_id, x, y, nm))


if __name__ == "__main__":
    main()
