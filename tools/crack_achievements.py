"""Sinh achievements.json: bang THANH TUU (Id -> co hoan thanh / co da nhan / phan thuong).

Dung cho tinh nang "nhan qua thanh tuu". Crack tu client:
  Data/AchievementData.lua  AchievementData.New(reader)  - thu tu truong o duoi
  Logic/DataManager.lua:1217 OnLoadAchievementData: [count i32] roi count x record
  UI/UIAchievement.lua:97-116  3 TRANG THAI hien thi CHI dua vao 2 BIT, khong dung IsComplete():
      completeFlag BAT + getFlag TAT  -> "co the nhan"  (hien nut Nhan)
      completeFlag BAT + getFlag BAT  -> "da hoan thanh" (lam mo)
      con lai (completeFlag TAT)      -> "dang lam"
  Logic/Achievement.lua:
      C:082-001 <完成成就> [count 1B][id u16]  - BAO da hoan thanh
      C:082-002 <成就領獎> [id u16]            - NHAN THUONG   <= bot dung cai nay
  UI/UIAchievement.lua:200  chi gui nhan khi: not HaveGetFlag() and HaveCompeleteFlag()
      va Item.CheckBagIsFull() -> TUI DAY thi KHONG nhan.

completeFlag/getFlag deu la CHI SO BIT tra qua BitFlag.Get = mang "forever flags" tu goi 0x51
(opcode 81) - bot DA PARSE SAN (client._bitflag_get). Nen KHONG can tinh dieu kien gi ca.

Ten thanh tuu la CHI SO vao bang text (TextData_C.dat) - co file thi tra ten, khong co van chay.

File .dat KHONG theo repo (gitignore) - COPY TU CLIENT vao truoc khi chay:
    gamedata_Achievement.dat  (hoac gamedata/Data/AchievementData_C.dat)
    gamedata/Data/TextData_C.dat   (de lay TEN - tuy chon)

Chay: python tools/crack_achievements.py
Ghi:  achievements.json  { "<id>": {"name", "complete_flag", "get_flag", "item", "count", "score"} }
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import Reader, _find          # noqa: E402

OUT = os.path.join(ROOT, "achievements.json")


def read_achievements(path):
    """Doc dung thu tu truong cua AchievementData.New (Data/AchievementData.lua)."""
    r = Reader(open(path, "rb").read())
    count = r.u32()
    out = []
    for _ in range(count):
        rec = {}
        rec["id"] = r.u16()             # 成就ID
        rec["name_id"] = r.u32()        # ten (chi so vao bang text)
        r.byte()                        # mainTag
        r.byte()                        # subTag
        r.byte()                        # sotrId
        r.byte()                        # showKind
        rec["content_id"] = r.u32()     # noi dung dat duoc
        rec["score"] = r.byte()         # diem thanh tuu
        rec["kind"] = r.byte()          # conditions.kind  (ECondition: 14=RoleCount 15=MissionFlag...)
        rec["kind_value"] = r.u32()     # conditions.kindValue (id RoleCount / id nhiem vu ...)
        rec["opr"] = r.byte()           # conditions.opr   (1 = / 2 > / 3 >= / 4 < / 5 <= / 6 !=)
        rec["value"] = r.u32()          # conditions.value (nguong)
        rec["item"] = r.u16()           # 獎勵物品ID
        rec["count"] = r.byte()         # 獎勵物品數量
        rec["complete_flag"] = r.u16()  # 完成永標  <- BitFlag "da hoan thanh"
        rec["get_flag"] = r.u16()       # 領獎永標  <- BitFlag "da nhan thuong"
        r.byte()                        # channel
        r.u32()                         # channelContent
        out.append(rec)
    return out


def load_texts(path):
    """TextData_C.dat -> {id: chuoi}. Khong doc duoc -> {} (ten se de trong, khong sao)."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        r = Reader(open(path, "rb").read())
        n = r.u32()
        return {r.u32(): r.text() for _ in range(n)}
    except Exception as e:
        print("   (khong doc duoc TextData: %s -> bo qua ten)" % e)
        return {}


def main():
    path = _find("gamedata_Achievement.dat",
                 os.path.join("gamedata", "Data", "AchievementData_C.dat"))
    if not path:
        raise SystemExit(
            "Khong thay gamedata_Achievement.dat (hoac gamedata/Data/AchievementData_C.dat).\n"
            "COPY tu client vao thu muc repo roi chay lai.")
    recs = read_achievements(path)
    texts = load_texts(_find(os.path.join("gamedata", "Data", "TextData_C.dat")))

    out = {}
    for d in recs:
        if not d["id"] or not (d["complete_flag"] and d["get_flag"]):
            continue      # thieu co -> bot khong xac dinh duoc trang thai, bo qua
        out[str(d["id"])] = {
            "name": texts.get(d["name_id"], ""),
            "complete_flag": d["complete_flag"],
            "get_flag": d["get_flag"],
            "item": d["item"],
            "count": d["count"],
            "score": d["score"],
            # DIEU KIEN: de bot tu tinh "da hoan thanh" roi gui C:082-001 (giong client)
            "kind": d["kind"],
            "kind_value": d["kind_value"],
            "opr": d["opr"],
            "value": d["value"],
        }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
    n_item = sum(1 for v in out.values() if v["item"])
    print("=> %s: %d thanh tuu (%d co phan thuong item, %d co ten)"
          % (os.path.basename(OUT), len(out), n_item,
             sum(1 for v in out.values() if v["name"])))
    for k, v in list(out.items())[:5]:
        print("   id=%-5s cf=%-5d gf=%-5d item=0x%04x x%d  %s"
              % (k, v["complete_flag"], v["get_flag"], v["item"], v["count"], v["name"]))


if __name__ == "__main__":
    main()
