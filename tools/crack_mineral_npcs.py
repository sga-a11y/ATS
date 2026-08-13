"""Sinh mineral_npcs.json: TAT CA quai KHOANG (NPC kind == 16 / 礦石) tu Npc_C.dat.

Client nhan dien quai khoang bang npcData.kind == 16 (Logic_FightField.CheckMineral), KHONG theo
ten. Bot cu chi bat ten bat dau "Khoang " -> SOT gan het (Thuy Tinh, Quang, Long Thu, Khoang dao
chu...): chi ~9/252. Dung set nay -> check tid quai trong tran (entity[2:4]) chuan 100%.

  NpcData.New (Data_NpcData.lua): [1]name(u16len+utf16) [2]kind(u8) [3]id(u16)...
  kind == 16 = ENpcKind.Mine (礦石).

Chay: python tools/crack_mineral_npcs.py   (-> ghi mineral_npcs.json)
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import Reader, _find     # noqa: E402

OUT = os.path.join(ROOT, "mineral_npcs.json")
MINE_KIND = 16
MAX_NPC_SKILL = 3


def read_mineral(path):
    """Doc TUAN TU Npc_C.dat (giong crack_npc_table.read_npcs) -> {tid_hex: name} cho kind==16."""
    r = Reader(open(path, "rb").read())
    count = r.u32()
    out = {}
    for _ in range(count):
        name = r.text()                     # [1]
        kind = r.byte()                     # [2] kind (16 = Mine)
        nid = r.u16()                       # [3] id
        r.u16(); r.u16()                    # [4][5]
        for _i in range(4):
            r.i32()                         # [6]..[9]
        r.byte(); r.byte(); r.byte()        # [10][11][12]
        r.byte()                            # [13] level
        r.i32(); r.i32()                    # [14][15]
        for _i in range(6):
            r.u16()                         # [16]..[21]
        r.byte(); r.u16(); r.byte()         # [22][23][24]
        for _i in range(MAX_NPC_SKILL):
            r.u16()                         # skills
        r.u16(); r.byte()                   # specialSkill / turn
        r.u16(); r.byte()                   # passiveSkill / passiveSkillLv
        r.u16(); r.u16(); r.u16()           # saddle / upgradeItem / upgradeSkill
        r.u16()                             # limits
        for _i in range(4):
            r.u16()                         # offsets
        r.byte(); r.byte()                  # shadowKind / rare
        if nid and kind == MINE_KIND:
            out["0x%04x" % nid] = name
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = _find("gamedata_Npc.dat", os.path.join("gamedata", "Data", "Npc_C.dat"))
    if not path:
        raise SystemExit("Khong thay gamedata_Npc.dat (hoac gamedata/Data/Npc_C.dat)")
    npcs = read_mineral(path)
    data = {
        "_note": "AUTO-SINH tu tools/crack_mineral_npcs.py (Npc_C.dat, NPC kind==16 = quai KHOANG). "
                 "tid_hex -> ten. Bot check template_id quai trong tran (entity[2:4]) thuoc set nay "
                 "-> bo chay (chuan theo client CheckMineral, KHONG phu thuoc ten).",
        "ids": npcs,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0)
    print("=> %s: %d quai khoang (kind==16)" % (os.path.basename(OUT), len(npcs)))


if __name__ == "__main__":
    main()
