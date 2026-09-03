# -*- coding: utf-8 -*-
"""Sinh `bliss_bag.json`: cac HOP/TUI TRANG BI bot tu mo duoc + noi dung tung hop.

Nguon: `gamedata/Data/BlissBag_C.dat` (36945 dong x 13 byte) - bo cuc theo
`Data_BlissBagData.lua BlissBagData.New`:
    bagId(u16) + itemId(u16) + count(u32) + pr(u32) + kind(u8)
`pr` = trong so xac suat (tong 1 hop = 10000 -> chia ra la % that).
`kind` = NHOM phan thuong; `kindCount` = kind LON NHAT cua hop = SO MON hop nha ra.

VI SAO CAN kindCount: client CHAN mo hop khi so o trong < kindCount (Logic_Item.lua:2298
`ItemUse_48` -> "您身上的物品欄空間不足哦!"). Bot khong check thi gui lenh mo ma server TU CHOI
im lang -> mo hut khong ai biet.

Mo hop = DUNG ITEM binh thuong (`specialAbility` 48 chi la mot chot kiem tra trong luong dung
item, KHONG phai opcode rieng) -> bot dung use_slot san co.

Chay: python tools/crack_bliss_bag.py
"""
from __future__ import annotations

import collections
import io
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT = os.path.join(ROOT, "gamedata", "Data", "BlissBag_C.dat")
OUT = os.path.join(ROOT, "bliss_bag.json")

# LUOT 1: tui/hop THUONG. LUOT 2: ban TINH/CAO (user chot 03/09: "cu duyet tui thuong xong roi
# den duyet tui tinh/cao thoi" - khong mo de quy).
# 'Trang Bi Dung Si' xep luot 2 vi no RA TU Tui Thao Phat (1%).
HOP_THUONG = {
    0xb534: "Hộp Trang Bị Cấp 20",
    0xb535: "Hộp Trang Bị Cấp 30",
    0xb536: "Hộp Trang Bị Cấp 40",
    0xb537: "Hộp Trang Bị Cấp 50",
    0xb539: "Túi Thập Thường",
    0xb531: "Túi Thảo Phạt",
    0xb53e: "Túi Lữ Phụng Tiên",
    0xb545: "Túi Bộc Dương",
    0xb22e: "Hộp Vũ Khí Sơ",
}
HOP_TINH = {
    0xb53a: "Thập Thường Tinh",
    0xb532: "Túi Thảo Phạt Tinh",
    0xb53f: "Túi Lữ Phụng Tiên Tinh",
    0xb546: "Túi Bộc Dương Cao",
    0xb538: "Trang Bị Dũng Sĩ",
}


# DONATE QUAN DOAN duoc hay khong - sao y `UIArmy.ArmyFilter` (bo loc tui khi chon do de dong
# gop). KHONG doan: mon truot bo loc nay thi client khong cho chon, bot gui la server bo qua IM
# LANG (user gap that 03/09: mo hop xong "donate" ma do van nam trong tui, tui day ngay).
#   if itemData.kind == 53 then return true end
#   if itemData.level == 0 then return false end
#   if isVender/isDeliver/isLock then return false end
#   if Contains(Id, <danh sach cam cung>) then return false end
#   if not Contains(material, 1..8, 10..22, 24..36) then return false end
#   if Contains(kind, 20, 21, 22) then return false end
MAT_OK = set(range(1, 9)) | set(range(10, 23)) | set(range(24, 37))   # BO 9 va 23
KIND_CAM = {20, 21, 22}
ID_CAM = {10505, 19209, 20209, 21609, 22909, 20747, 20748, 20749, 26209, 26210, 26211, 26212,
          26213, 26214, 26215, 26216, 26217, 26218, 26219, 16000, 21610, 19210, 22910, 20210,
          11046}


def donate_duoc(tid: int, rec: dict) -> bool:
    """rec = ban ghi trong items_gamedata.json (can `mat`, `lv`, `kd`)."""
    if int(rec.get("kd") or 0) == 53:
        return True
    if int(rec.get("lv") or 0) == 0:
        return False
    if tid in ID_CAM:
        return False
    if int(rec.get("mat") or 0) not in MAT_OK:
        return False
    if int(rec.get("kd") or 0) in KIND_CAM:
        return False
    return True


def doc_bliss(path=DAT):
    """{bagId: [(itemId, count, pr, kind)]} theo dung thu tu file."""
    with open(path, "rb") as fh:
        d = fh.read()
    n = struct.unpack_from("<i", d, 0)[0]
    fmt, sz = "<HHIIB", struct.calcsize("<HHIIB")
    if (len(d) - 4) != n * sz:
        raise SystemExit("BlissBag_C.dat: bo cuc doi (%d ban ghi x %d != %d byte)"
                         % (n, sz, len(d) - 4))
    out = collections.defaultdict(list)
    for i in range(n):
        bag, item, cnt, pr, kind = struct.unpack_from(fmt, d, 4 + i * sz)
        out[bag].append((item, cnt, pr, kind))
    return out


def main():
    if not os.path.exists(DAT):
        print("khong thay %s - keo tu may ao:" % DAT)
        print("  adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/BlissBag_C.dat "
              "gamedata/Data/")
        return 1
    bags = doc_bliss()
    with io.open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
        items = json.load(fh)

    def rec(tid):
        return items.get("0x%04x" % tid) or {}

    out = {"_note": "Hop/tui trang bi bot tu mo. Sinh tu Data/BlissBag_C.dat "
                    "(tools/crack_bliss_bag.py). fc>0 = phan giai duoc.",
           "boxes": {}}
    for luot, bang in (("thuong", HOP_THUONG), ("tinh", HOP_TINH)):
        for tid, ten in bang.items():
            rows = bags.get(tid)
            if not rows:
                print("  !! 0x%04x %s KHONG co trong BlissBag_C.dat -> bo qua" % (tid, ten))
                continue
            tong = sum(r[2] for r in rows) or 1
            ds = []
            for item_id, cnt, pr, _kind in rows:
                r = rec(item_id)
                ds.append({"id": item_id, "name": (r.get("name") or "").strip(),
                           "sl": cnt, "pr": round(pr * 100.0 / tong, 2),
                           "fc": int(r.get("fc") or 0), "ft": int(r.get("ft") or 0),
                           # dn = DONATE quan doan duoc khong (theo UIArmy.ArmyFilter).
                           # fc == 0 va dn == False = MON KET: khong phan giai, khong donate
                           # -> bot VUT BO (user chot 03/09), khong thi no nam li lam day tui.
                           "dn": donate_duoc(item_id, r)})
            out["boxes"]["0x%04x" % tid] = {
                "name": ten,
                "luot": luot,
                # SO O TRONG toi thieu de mo duoc (client chan neu thieu).
                "kindCount": max(r[3] for r in rows),
                "items": ds,
            }
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    print("=> %s: %d hop" % (os.path.basename(OUT), len(out["boxes"])))
    print("%-24s %-7s %-5s %-5s %-9s %-9s %s"
          % ("hop", "luot", "o can", "mon", "phan giai", "donate", "KET (vut bo)"))
    for k, v in out["boxes"].items():
        pg = [i for i in v["items"] if i["fc"] > 0]
        dn = [i for i in v["items"] if i["dn"]]
        ket = [i for i in v["items"] if not i["fc"] and not i["dn"]]
        print("%-24s %-7s %-5d %-5d %-9s %-9s %s"
              % (v["name"], v["luot"], v["kindCount"], len(v["items"]),
                 "%d (%.0f%%)" % (len(pg), sum(i["pr"] for i in pg)),
                 "%d (%.0f%%)" % (len(dn), sum(i["pr"] for i in dn)),
                 "%d (%.0f%%)" % (len(ket), sum(i["pr"] for i in ket))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
