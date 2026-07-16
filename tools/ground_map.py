"""Decode Ground.mmg cua game com.vtcmobile.gz06 va render collision.

MUC DICH: tool PORTABLE cho RE map-collision. Data (Ground.mmg ~27MB) KHONG commit (gitignore,
moi may tu keo tu mumu: adb pull /sdcard/Android/data/<pkg>/files/CompreseData/Ground.mmg).
Tool nay commit de 2 may chay chung. Xem KNOWLEDGE.md muc "7d-RE. MAP COLLISION".

FORMAT (da verify tren 12831.map = 1664x2560 px, grid 84x129, 8 chunk):
  .map data:  u32 width_px, u32 height_px, u8 chunk_count, chunk_count*6 byte,
              u16 grid_w, u16 grid_h, grid_w*grid_h byte grid, ... (event/object/tail).
  Index: [u8 namelen][name][11 byte metadata][u32 offset][u32 size].
  Block data la X-major: grid[(x-1)*grid_h + (y-1)], toa do block bat dau tu 1.
  Lua game coi bit 1 hoac bit 4 la vat can; bit 2 la nuoc.

Dung:  python tools/ground_map.py gamedata/Ground.mmg --list
       python tools/ground_map.py gamedata/Ground.mmg --map 12831 --render out.png
"""
import math
import re
import struct
import sys


def parse_map(data: bytes, offset: int) -> dict:
    """Doc 1 .map tai `offset` trong Ground.mmg. Tra {width_px,height_px,chunks,grid_w,grid_h,grid}."""
    p = offset
    width_px, height_px = struct.unpack_from("<II", data, p); p += 8
    chunk_count = data[p]; p += 1
    chunks = [data[p + i * 6:p + (i + 1) * 6] for i in range(chunk_count)]
    p += chunk_count * 6
    grid_w, grid_h = struct.unpack_from("<HH", data, p); p += 4
    grid = data[p:p + grid_w * grid_h]; p += grid_w * grid_h
    return {"width_px": width_px, "height_px": height_px, "chunk_count": chunk_count,
            "chunks": chunks, "grid_w": grid_w, "grid_h": grid_h, "grid": grid,
            "grid_end": p}


def find_map_offset(data: bytes, map_id: int) -> int:
    entry = list_maps(data).get(f"{map_id}.map")
    return -1 if entry is None else entry[0]


def list_maps(data: bytes):
    """Tra ``{name: (offset, size)}`` tu bang index chen o cuoi Ground.mmg."""
    result = {}
    pattern = re.compile(rb"([0-9]+\.map)(.{11})(.{4})(.{4})", re.DOTALL)
    for match in pattern.finditer(data):
        name = match.group(1)
        start = match.start(1)
        if start == 0 or data[start - 1] != len(name):
            continue
        offset, size = struct.unpack("<II", match.group(3) + match.group(4))
        result[name.decode("ascii")] = (offset, size)
    return result


def block_value(m: dict, x: int, y: int):
    """Doc block 1-based dung orientation X-major cua MapData.lua."""
    w, h = m["grid_w"], m["grid_h"]
    if x < 1 or x > w or y < 1 or y > h:
        return None
    return m["grid"][(x - 1) * h + (y - 1)]


def is_obstacle(value) -> bool:
    return value is None or value & 1 == 1 or value & 4 == 4


def is_sea(value) -> bool:
    return value is not None and value & 2 == 2


def center_offset(width_px: int, height_px: int):
    left = math.floor((800 - width_px) * 0.5 * 0.05) * 20 if width_px < 800 else 0
    top = math.floor((600 - height_px) * 0.5 * 0.05) * 20 if height_px < 600 else 0
    return left, top


def world_to_block(position, center_left=0, center_top=0):
    return (math.ceil((position[0] - center_left) * 0.05),
            math.ceil((position[1] - center_top) * 0.05))


def block_to_world(block, center_left=0, center_top=0):
    return (block[0] * 20 - 10 + center_left,
            block[1] * 20 - 10 + center_top)


def render(m: dict, path: str):
    from PIL import Image
    pal = {0: (20, 20, 20), 1: (235, 235, 235), 2: (60, 120, 220), 3: (220, 180, 60)}
    w, h = m["grid_w"], m["grid_h"]
    img = Image.new("RGB", (w, h))
    px = img.load()
    g = m["grid"]
    for y in range(h):
        for x in range(w):
            value = g[x * h + y]
            px[x, y] = pal.get(value, (220, 40, 40))
    img.save(path)


def main(argv):
    if len(argv) < 2:
        print(__doc__); return
    data = open(argv[1], "rb").read()
    if "--list" in argv:
        entries = list_maps(data)
        print(f"{len(entries)} map trong index. Dau: {list(entries.items())[:10]}")
        return
    if "--map" in argv:
        mid = int(argv[argv.index("--map") + 1])
        off = find_map_offset(data, mid)
        if off < 0:
            print(f"Khong tim thay map {mid} trong index.")
            if "--offset" in argv:
                off = int(argv[argv.index("--offset") + 1])
            else:
                return
        m = parse_map(data, off)
        print(f"map {mid} @ {off}: {m['width_px']}x{m['height_px']}px "
              f"grid {m['grid_w']}x{m['grid_h']} chunks={m['chunk_count']}")
        if "--render" in argv:
            out = argv[argv.index("--render") + 1]
            render(m, out); print("render ->", out)


if __name__ == "__main__":
    main(sys.argv)
