"""Decode Warp_C.dat (game VTC com.vtcmobile.gz06) -> map_gates.json.

Record 16B: [warp_id u32][srcMap u16][dstMap u16][x u32][y u32]; header u32 = so record.
Xac nhan tu gamedata/Warp_C.dat (vd 12001 Trac Quan -> 11804 @(310,1530))."""
import struct
import json
import sys


def parse_warp(blob: bytes):
    cnt = struct.unpack_from("<I", blob, 0)[0]
    rows = []
    off = 4
    for _ in range(cnt):
        if off + 16 > len(blob):
            break
        wid, src, dst, x, y = struct.unpack_from("<IHHII", blob, off)
        rows.append({"id": wid, "src": src, "dst": dst, "x": x, "y": y})
        off += 16
    return rows


def build_gates(rows):
    """rows -> {maps: {src_map: {gates:[{x,y,to}]}}}. Gom cong theo srcMap."""
    maps = {}
    for r in rows:
        m = maps.setdefault(str(r["src"]), {"gates": []})
        m["gates"].append({"x": r["x"], "y": r["y"], "to": r["dst"]})
    return {"_note": "Do thi cong di chuyen. map_id -> gates[{x,y,to}]. Seed tu Warp_C.dat + capture.",
            "maps": maps}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "gamedata/Warp_C.dat"
    out = sys.argv[2] if len(sys.argv) > 2 else "map_gates.json"
    rows = parse_warp(open(src, "rb").read())
    data = build_gates(rows)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Decoded {len(rows)} warps -> {len(data['maps'])} maps -> {out}")
