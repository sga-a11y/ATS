"""Sinh warp_points.json: bang DIEM DICH CHUYEN (thien hanh) + CO NHIEM VU de mo tung diem.

VI SAO CAN: truoc day bot TELE MU - cu gui lenh, khong di duoc thi ĐOÁN la thanh chua mo. Client
thi BIET TRUOC. Doc UI_UITeleport.lua:656 (SetupSkyPointData):

    for i = 0, Count(warpDatas)-1 do
      if warpDatas[i].mark ~= 0
         and CheckFlag(MarkManager.flags, markDatas[warpDatas[i].mark].bitId) then
          -- diem NAY da mo

Tuc: moi diem co mot CO NHIEM VU (mark); co co do = da mo. Bot DA doc duoc ca hai thu:
  - MarkManager.flags  -> client.mark_flags (S:024-007 init + S:024-005 delta)
  - markDatas[].bitId  -> mark_bitids.json (tools/crack_mark_bitids.py)
Chi thieu bang warpDatas nay.

Cau truc (Data_WarpData.lua): [count u32] + count * 16 byte
    name u32 | scene u16 | mark u16 | x i32 | y i32

`flag` trong cities.json chinh la CHI SO trong bang nay (NO cua C:068-001
<使用晶石天行異能> +場景ID(2) +NO(1)) - da doi chieu: 19/19 thanh khop.

Chay: python tools/crack_warp.py
"""
from __future__ import annotations

import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import _find          # noqa: E402

OUT = os.path.join(ROOT, "warp_points.json")
REC = 16


def read_warps(path):
    data = open(path, "rb").read()
    n = struct.unpack("<I", data[:4])[0]
    if 4 + n * REC > len(data):
        raise SystemExit("Warp_C.dat: so ban ghi (%d) khong khop kich thuoc (%d byte)"
                         % (n, len(data)))
    out = []
    for i in range(n):
        off = 4 + i * REC
        name, scene, mark, x, y = struct.unpack("<IHHii", data[off:off + REC])
        out.append({"scene": scene, "mark": mark, "x": x, "y": y})
    return out


def main():
    path = _find("gamedata_Warp.dat", os.path.join("gamedata", "Warp_C.dat"))
    if not path:
        raise SystemExit("Khong thay gamedata/Warp_C.dat (hoac gamedata_Warp.dat)")
    warps = read_warps(path)

    # Doi chieu voi cities.json: `flag` phai la chi so trong bang nay. Lech = doc sai cau truc.
    try:
        with open(os.path.join(ROOT, "cities.json"), encoding="utf-8") as fh:
            cities = json.load(fh).get("cities", {})
    except Exception:
        cities = {}
    lech = [v.get("name") for v in cities.values()
            if not (0 <= int(v.get("flag", -1)) < len(warps))
            or warps[int(v["flag"])]["scene"] != int(v.get("city_id", 0))]
    if lech:
        raise SystemExit("Warp_C.dat doc SAI: %d thanh trong cities.json khong khop chi so warp: %s"
                         % (len(lech), ", ".join(map(str, lech))))

    # Doi chieu mark -> bitId: thieu bitId thi khong the biet diem do da mo hay chua.
    try:
        with open(os.path.join(ROOT, "mark_bitids.json"), encoding="utf-8") as fh:
            bitids = json.load(fh)
    except Exception:
        bitids = {}
    thieu = [w["mark"] for w in warps
             if w["mark"] and str(w["mark"]) not in bitids and w["mark"] not in bitids]
    if thieu:
        raise SystemExit("mark_bitids.json thieu %d mark cua warp: %s "
                         "(chay lai tools/crack_mark_bitids.py)"
                         % (len(thieu), thieu[:10]))

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"warps": warps}, fh, ensure_ascii=False, indent=1)
    print("=> warp_points.json: %d diem (khop %d/%d thanh trong cities.json)"
          % (len(warps), len(cities), len(cities)))


if __name__ == "__main__":
    main()
