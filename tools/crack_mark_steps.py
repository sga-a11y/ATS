"""Crack Mark_C.dat + MarkStep_C.dat + MarkGroupData.dat -> marks.json (nhiem vu + tung buoc).

Crack tu client:
  Logic/DataManager.lua OnLoadMarkData / OnLoadMarkStepData / OnLoadMarkGroupData
  Data/MarkData.lua ReadInfo / ReadStep

MarkStep record:
  id u16, step u8, description str,
  5 x [kind u8 (0 khong/1 bat npc/2 giet npc/3 gom item), id u16, count u8, sceneId u16,
       x u16, y u16, eventKind u8, eventId u8],
  endGuide str, endSceneId u16, endX u16, endY u16, endEventKind u8, endEventId u8,
  teleport u8, checkTeam bool
MarkGroupData (doc toi het file): [id i32][count u8] << [stepId u8][areaId x5][endAreaId] >>
str = [len u16 (so byte)][UTF-16LE]

File .dat KHONG theo repo - pull tu MuMu vao gamedata/Data/ (xem KNOWLEDGE.md).
Chay: python tools/crack_mark_steps.py
"""
from __future__ import annotations

import json
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "gamedata", "Data")
OUT = os.path.join(ROOT, "marks.json")


class R:
    def __init__(self, b: bytes):
        self.b, self.i = b, 0

    def can(self) -> bool:
        return self.i < len(self.b)

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


def read(name: str) -> R:
    with open(os.path.join(DATA, name), "rb") as f:
        return R(f.read())


def main():
    marks = {}
    r = read("Mark_C.dat")
    for _ in range(r.i32()):
        name = r.s()
        kind = r.u8()
        mid = r.u16()
        bit = r.u16()
        gain = r.u8()
        desc = r.s()
        if mid:
            marks[mid] = {"name": name, "kind": kind, "bitId": bit, "gainWay": gain,
                          "desc": desc, "steps": {}}
    assert not r.can(), f"Mark_C du {len(r.b) - r.i} byte"

    r = read("MarkStep_C.dat")
    for _ in range(r.i32()):
        mid = r.u16()
        step = r.u8()
        d = {"desc": r.s(), "conds": []}
        for _ in range(5):
            c = {"kind": r.u8(), "id": r.u16(), "count": r.u8(), "scene": r.u16(),
                 "x": r.u16(), "y": r.u16(), "evKind": r.u8(), "evId": r.u8()}
            d["conds"].append(c)
        d["endGuide"] = r.s()
        d["endScene"] = r.u16()
        d["endX"], d["endY"] = r.u16(), r.u16()
        d["endEvKind"], d["endEvId"] = r.u8(), r.u8()
        d["teleport"] = r.u8()
        d["checkTeam"] = bool(r.u8())
        if mid in marks:
            marks[mid]["steps"][step] = d
    assert not r.can(), f"MarkStep_C du {len(r.b) - r.i} byte"

    r = read("MarkGroupData.dat")
    while r.can():
        mid = r.i32()
        for _ in range(r.u8()):
            st = r.u8()
            areas = [r.u8() for _ in range(5)]
            end_area = r.u8()
            s = marks.get(mid, {}).get("steps", {}).get(st)
            if s:
                for c, a in zip(s["conds"], areas):
                    c["area"] = a
                s["endArea"] = end_area

    for m in marks.values():
        for s in m["steps"].values():
            s["conds"] = [c for c in s["conds"] if c["kind"] or c["id"] or c["scene"]]

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(marks, f, ensure_ascii=False, indent=1)
    print(f"{len(marks)} nhiem vu, {sum(len(m['steps']) for m in marks.values())} buoc -> {OUT}")


if __name__ == "__main__":
    main()
