"""Doc DUNG bang Npc_C.dat -> npc_table.json { npc_id: {"name", "rare", "level", "turn", "element"} }.

element (EElement, Logic_Fight_Skill.lua:547): 1=Dia 2=Thuy 3=Hoa 4=Phong 5=Tam 7=Quang 8=Am,
0 = VO HE (enum ghi None=6 nhung .dat khong dung so 6). Dung cho rule chon bai train theo he.

Khac tools/crack_npc_names.py: file do QUET BYTE theo mau [len][name][sep][id] nen bo sot
nhieu npc (vd 46407 "Yen Nhan Truong Phi", 45437 "Ma Quan Vu" - deu CO trong file nhung
khong khop mau). Day doc TUAN TU dung thu tu truong nhu client:

  DataManager.OnLoadNpcData : [count int32] roi count x NpcData.New(reader)
  NpcData.New (Data/NpcData.lua:236) - 49 truong, xem chu thich duoi.

Truong dang chu y:
  rare  [49] 稀a giai cap: 1~3 = dong, 4 = bac, 5 = vang  -> do "xin" cua vo tuong
  turn  [36] 0 = chua chuyen sinh, 1 = da chuyen sinh

File .dat KHONG theo repo (gitignore) - copy tu client vao truoc khi chay.

Chay: python tools/crack_npc_table.py
Ghi:  npc_table.json
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import Reader, _find          # noqa: E402

OUT = os.path.join(ROOT, "npc_table.json")
MAX_NPC_SKILL = 3       # Role.maxNpcSkill (Logic/Role.lua:51)


def read_npcs(path):
    r = Reader(open(path, "rb").read())
    count = r.u32()
    out = {}
    for _ in range(count):
        name = r.text()                     # [1] ten
        r.byte()                            # [2] kind
        nid = r.u16()                       # [3] id
        r.u16(); r.u16()                    # [4][5] picId / maskId
        for _i in range(4):                 # [6]..[9] colorTints
            r.i32()
        r.byte(); r.byte(); r.byte()        # [10][11][12] canBeCatch/bodyKind/weaponKind
        level = r.byte()                    # [13] level
        r.i32(); r.i32()                    # [14][15] hpBase/spBase
        for _i in range(6):                 # [16]..[21] attributes
            r.u16()
        r.byte()                            # [22] moral
        r.u16()                             # [23] moralValue
        # [24] element - EElement (Logic_Fight_Skill.lua:547):
        #   1=Dia 2=Thuy 3=Hoa 4=Phong 5=Tam 7=Quang 8=Am
        #   0 = VO HE. LUU Y: enum co None=6 nhung Npc_C.dat KHONG dung (0 npc), quai vo he ghi 0
        #   (vd Quy Dao Binh, Luu Thien) - dem thuc te: 453 npc he 0, 0 npc he 6.
        element = r.byte()
        for _i in range(MAX_NPC_SKILL):     # [25].. skills
            r.u16()
        r.u16()                             # specialSkill
        turn = r.byte()                     # turn (0 chua CS / 1 da CS)
        r.u16(); r.byte()                   # passiveSkill / passiveSkillLv
        r.u16(); r.u16(); r.u16()           # saddleKind / upgradeItemId / upgradeSkill
        r.u16()                             # limits (2 byte gop)
        for _i in range(4):                 # rideOffsetH/picOffsetX/picOffsetY/hudOffsetH
            r.u16()
        r.byte()                            # shadowKind
        rare = r.byte()                     # [49] rare 1~3 dong, 4 bac, 5 vang
        if nid:
            out[nid] = {"name": name, "rare": rare, "level": level, "turn": turn,
                        "element": element}
    return out


def main():
    path = _find("gamedata_Npc.dat", os.path.join("gamedata", "Data", "Npc_C.dat"))
    if not path:
        raise SystemExit("Khong thay gamedata_Npc.dat (hoac gamedata/Data/Npc_C.dat)")
    npcs = read_npcs(path)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({str(k): v for k, v in sorted(npcs.items())}, fh, ensure_ascii=False, indent=1)
    print("=> %s: %d npc" % (os.path.basename(OUT), len(npcs)))
    for nid in (46407, 45437, 41003, 12020):
        v = npcs.get(nid)
        print("   %6d %s" % (nid, ("%-26s rare=%d lv=%d" % (v["name"], v["rare"], v["level"]))
                             if v else "KHONG CO"))


if __name__ == "__main__":
    main()
