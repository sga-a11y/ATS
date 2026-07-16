"""Decode Ground.mmg (pack .map cua game com.vtcmobile.gz06) -> lưới grid + object + render debug.

MUC DICH: tool PORTABLE cho RE map-collision. Data (Ground.mmg ~27MB) KHONG commit (gitignore,
moi may tu keo tu mumu: adb pull /sdcard/Android/data/<pkg>/files/CompreseData/Ground.mmg).
Tool nay commit de 2 may chay chung. Xem KNOWLEDGE.md muc "7d-RE. MAP COLLISION".

FORMAT (da verify tren 12831.map = 1664x2560 px, grid 84x129, 8 chunk):
  .map data:  u32 width_px, u32 height_px, u8 chunk_count, chunk_count*6 byte,
              u16 grid_w, u16 grid_h, grid_w*grid_h byte grid, ... (event/object/tail).
  Index (cuoi file): cac entry [u8 namelen][name "<id>.map"][19 byte data]  (namelen=9 -> 29 byte).

CANH BAO (da xac nhan): grid value (0/1/2...) trong .map KHONG phai passability truc tiep -
  safe/mob/gate diem nam ca tren o 0 lan 1. Collision THAT o tang Lua (BlockController:IsObstacle).
  Tool nay de KHAO SAT/doi chieu, chua phai nguon walkability cuoi cung.

TODO: giai ma offset-encoding cua index (offset .map data KHONG nam plain-u32 trong 19 byte entry;
  co bang offset rieng). Hien enumerate ten qua index; lay grid qua scan/known-offset.

Dung:  python tools/ground_map.py gamedata/Ground.mmg --list
       python tools/ground_map.py gamedata/Ground.mmg --map 12831 --render out.png
"""
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
    """Tim offset .map data cua map_id. Tam thoi: quet data-region cho .map header hop le va
    doi chieu (chua co index offset). Tra -1 neu khong thay.

    Cach dung duoc ngay: neu biet dims (width_px,height_px) tu KNOWLEDGE thi search header;
    khong thi quet tuan tu tu 0 parse .map lien tiep (yeu cau parse het tail - chua xong)."""
    # Placeholder: quet nguyen file tim vi tri ma parse_map ra grid hop ly + name entry ton tai.
    # (Se thay bang index-offset khi giai ma xong.)
    name = f"{map_id}.map".encode()
    if data.find(b"\x09" + name) < 0 and data.find(bytes([len(name)]) + name) < 0:
        return -1
    # chua co lien ket name->offset; tra -1, de caller dung offset thu cong.
    return -1


def list_maps(data: bytes):
    """Enumerate ten map tu index (cac entry [len][name.map][19B]) o cuoi file."""
    names = []
    i = 0
    n = len(data)
    while i < n - 1:
        L = data[i]
        if 5 <= L <= 14 and data[i + 1:i + 1 + L].endswith(b".map") \
                and data[i + 1:i + 1 - 4 + L].isdigit():
            names.append(data[i + 1:i + 1 + L].decode())
            i += 1 + L + 19   # entry = len + name + 19 byte data
        else:
            i += 1
    return names


def render(m: dict, path: str):
    from PIL import Image
    pal = {0: (20, 20, 20), 1: (235, 235, 235), 2: (60, 120, 220), 3: (220, 180, 60)}
    w, h = m["grid_w"], m["grid_h"]
    img = Image.new("RGB", (w, h))
    px = img.load()
    g = m["grid"]
    for y in range(h):
        for x in range(w):
            px[x, y] = pal.get(g[y * w + x], (220, 40, 40))
    img.save(path)


def main(argv):
    if len(argv) < 2:
        print(__doc__); return
    data = open(argv[1], "rb").read()
    if "--list" in argv:
        names = list_maps(data)
        print(f"{len(names)} map trong index. Dau: {names[:10]}")
        return
    if "--map" in argv:
        mid = int(argv[argv.index("--map") + 1])
        off = find_map_offset(data, mid)
        if off < 0:
            print(f"Chua co lien ket name->offset trong tool (TODO index). "
                  f"Tam thoi truyen --offset <byte> thu cong.")
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
