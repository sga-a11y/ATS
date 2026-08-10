"""Crack collect_style.json tu gamedata/Data/CollectStyle_C.dat (熔爐/收藏冊 - Bo Suu Tam).

File .dat: header count(u32) + moi entry 32B:
  id(u16) + name(u32 stringID) + itemId[1..5](u16, 5 manh: dau/than/vukhi/tay/chan)
  + info(u32) + itemScore[1..6](u16).
itemId=0 = khong co manh o vi tri do.

Sinh map NGUOC {tid_hex: [collectStyleId, part]} -> bot quet tui, tid nam trong day = do thoi
trang -> gui C2S 0x5f sub02 [id u16][part u8] tha vao S.Tam (gon tui + diem collection).
Xac nhan capture ts_capture_mumu12_congty.pcap: 5f 02 00 01 00 01 (id=1 part=1) -> result 01.

Chay: python tools/crack_collectstyle.py   (doc CollectStyle_C.dat -> ghi collect_style.json)
"""
import struct, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT = os.path.join(ROOT, "gamedata", "Data", "CollectStyle_C.dat")
OUT = os.path.join(ROOT, "collect_style.json")
ENT = 32


def parse(path):
    with open(path, "rb") as f:
        d = f.read()
    count = struct.unpack("<I", d[0:4])[0]
    off = 4
    tid_map = {}
    for _ in range(count):
        if off + ENT > len(d):
            break
        cid = struct.unpack("<H", d[off:off + 2])[0]
        items = struct.unpack("<5H", d[off + 6:off + 16])
        for part, tid in enumerate(items, 1):
            if tid:
                tid_map["0x%04x" % tid] = [cid, part]
        off += ENT
    return count, tid_map


def main():
    count, tid_map = parse(DAT)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(tid_map, f, ensure_ascii=False, indent=0, sort_keys=True)
    print("collect_style.json: %d bo -> %d tid thoi trang -> %s" % (count, len(tid_map), OUT))


if __name__ == "__main__":
    main()
