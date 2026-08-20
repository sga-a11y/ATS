"""Sinh mark_bitids.json: missionId -> bitId cua NHIEM VU (任務永標).

Dung de bot tu tinh dieu kien THANH TUU loai kind=15 (ECondition.MissionFlag) - 435/600 thanh tuu.

Crack tu client:
  Logic/DataManager.lua:935 OnLoadMarkData: [count i32] roi count x record
  Data/MarkData.lua ReadInfo - thu tu truong:
      name        : [len u16][bytes UTF-16LE]
      kind        : 1B   (0 khong / 1 chinh tuyen / 2 phu / 3 chi dan / 4 PB don / 5 PB doi /
                          6 khac / 7 nhiem vu ngay / 8 ngay nhung khong hien)
      id          : u16  <- MA NHIEM VU
      bitId       : u16  <- CHI SO BIT trong mang co cua MarkManager   <= CAI CAN LAY
      gainWay     : 1B
      description : [len u16][bytes UTF-16LE]
  Logic/MarkManager.lua:336 GetMissionFlag(missionId) = CheckFlag(flags, markDatas[missionId].bitId)
  Mang `flags` den tu goi 0x18: S:024-007 (init) va S:024-005 (cap nhat) - bot parse trong
  client._on_mission_steps.

CheckFlag: bit thu N nam o byte N//8, bit N%8 (giong BitFlag 0x51 - xem KNOWLEDGE.md).

File .dat KHONG theo repo (gitignore) - COPY TU CLIENT vao truoc khi chay:
    gamedata/Data/Mark_C.dat

Chay: python tools/crack_mark_bitids.py
Ghi:  mark_bitids.json  { "<missionId>": <bitId> }   (chi ghi bitId != 0)
"""
from __future__ import annotations

import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "mark_bitids.json")
DAT = os.path.join(ROOT, "gamedata", "Data", "Mark_C.dat")


class R:
    def __init__(self, b: bytes):
        self.b, self.i = b, 0

    def u8(self) -> int:
        v = self.b[self.i]
        self.i += 1
        return v

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.b, self.i)[0]
        self.i += 2
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.b, self.i)[0]
        self.i += 4
        return v

    def s(self) -> str:
        n = self.u16()
        v = self.b[self.i:self.i + n].decode("utf-16-le", "replace")
        self.i += n
        return v.rstrip("\x00")


def main() -> None:
    if not os.path.isfile(DAT):
        raise SystemExit("THIEU %s - copy tu client (xem docstring)" % DAT)
    r = R(open(DAT, "rb").read())
    count = r.i32()
    out, names = {}, {}
    for _ in range(count):
        name = r.s()
        r.u8()                      # kind
        mid = r.u16()
        bit = r.u16()
        r.u8()                      # gainWay
        r.s()                       # description
        if mid and bit:
            out[str(mid)] = bit
            names[mid] = name
    if r.i != len(r.b):
        raise SystemExit("PARSE LECH: doc %d/%d byte -> cau truc record sai" % (r.i, len(r.b)))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("doc %d nhiem vu, ghi %d co -> %s" % (count, len(out), OUT))
    print("bitId lon nhat = %d (can bitmap >= %d byte)" % (max(out.values()), max(out.values()) // 8 + 1))
    for mid in list(out)[:3]:
        print("   vd mission %s ('%s') -> bit %d" % (mid, names[int(mid)][:28], out[mid]))


if __name__ == "__main__":
    main()
