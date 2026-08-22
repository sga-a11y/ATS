"""Sinh mounts_grow.json: bang NANG CAP + BOI DUONG THU CUOI (座騎).

Vi sao can: de bot tu boi duong thu cuoi bang 5 vien "ky don" trong tui, phai biet moi cap can
VIEN NAO + BAO NHIEU DIEM, va nang cap thi ton vien gi + bao nhieu vang. Server KHONG gui nhung
so nay - no chi gui `S:079-001 [level u8][6 attributePoint u16][...]` (diem CONG DON tho).

Bo cuc MountsGrow_C.dat (theo `MountsGrowData.New` trong _lua_dec/Data/MountsData.lua),
ban ghi 39 byte, khong co con tro/chuoi nen doc TUAN TU thang:
    [count i32] roi moi ban ghi:
      level u8 | speed u8 | upItemId u16 | upItemCount u8 | upMoney u32
      roi 5 LAN (kind 1..5): [addValue u16][upItemId u16][upItemCount u16]
    kind: 1=Atk 2=Int 3=Def 4=ExtraHp 5=ExtraSp  (tu Mounts.SetAttributePoint)

3 MOC TU KIEM CHUNG (parse lech la hong ngay, khong am tham):
  1. 4 + count*39 PHAI bang dung kich thuoc file.
  2. Moi upItemId PHAI tra ra ten trong items_gamedata.json.
  3. Cot INT (kind 2) PHAI trung `mount_int_grow` trong pet_stats.json (da dung lau, sinh boi
     tools/generate_pet_stat_data.py).

LUU Y: tools/generate_pet_stat_data.py cung doc file nay nhung VUT BO upItemId va chi giu cot INT
(hoi do chi can tinh INT de chon quan su). Tool nay giu DAY DU.

File .dat KHONG theo repo - keo tu may truoc khi chay:
    adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/MountsGrow_C.dat gamedata/Data/
Chay: python tools/crack_mounts_grow.py    (-> ghi mounts_grow.json)
"""
from __future__ import annotations

import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "mounts_grow.json")
REC = 39
KIND_TEN = {1: "Atk", 2: "Int", 3: "Def", 4: "ExtraHp", 5: "ExtraSp"}


def _tim():
    for p in (os.path.join(ROOT, "gamedata", "Data", "MountsGrow_C.dat"),
              os.path.join(ROOT, "_work", "pet_crack", "MountsGrow_C.dat"),
              os.path.join(ROOT, "gamedata_MountsGrow.dat")):
        if os.path.isfile(p):
            return p
    return None


def parse(path):
    with open(path, "rb") as fh:
        d = fh.read()
    count = struct.unpack_from("<i", d)[0]
    if not 0 < count < 1000:
        raise SystemExit("count vo ly: %d" % count)
    if 4 + count * REC != len(d):
        raise SystemExit("PARSE LECH: 4 + %d*%d = %d nhung file %d byte"
                         % (count, REC, 4 + count * REC, len(d)))
    out, off = {}, 4
    for _ in range(count):
        level = d[off]
        speed = d[off + 1]
        up_id, up_cnt = struct.unpack_from("<HB", d, off + 2)
        up_money = struct.unpack_from("<I", d, off + 5)[0]
        o = off + 9
        attrs = {}
        for kind in range(1, 6):
            add, iid, cnt = struct.unpack_from("<HHH", d, o)
            o += 6
            attrs[str(kind)] = {"add": add, "item": iid, "need": cnt}
        out[str(level)] = {
            "speed": speed,
            "up_item": up_id, "up_count": up_cnt, "up_money": up_money,
            "attrs": attrs,
        }
        off += REC
    return out


def main():
    path = _tim()
    if not path:
        raise SystemExit(
            "Khong thay MountsGrow_C.dat.\n"
            "  adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/MountsGrow_C.dat "
            "gamedata/Data/")
    bang = parse(path)
    print("doc tuan tu: %d cap (tu %s)" % (len(bang), os.path.basename(path)))

    # --- MOC 2: moi upItemId phai tra ra TEN ---
    with open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
        items = json.load(fh)
    items = items.get("items", items)

    def ten(i):
        v = items.get("0x%04x" % i)
        return v.get("name") if isinstance(v, dict) else None

    thieu = []
    for lv, r in bang.items():
        if r["up_item"] and not ten(r["up_item"]):
            thieu.append((lv, "up", r["up_item"]))
        for k, a in r["attrs"].items():
            if a["item"] and not ten(a["item"]):
                thieu.append((lv, k, a["item"]))
    print("  item khong tra duoc ten: %d" % len(thieu))
    if thieu:
        raise SystemExit("=> NGHI PARSE LECH: %s" % thieu[:5])

    # --- MOC 3: cot INT phai trung pet_stats.json ---
    try:
        with open(os.path.join(ROOT, "pet_stats.json"), encoding="utf-8") as fh:
            cu = json.load(fh).get("mount_int_grow") or []
        moi = [[int(lv), bang[lv]["attrs"]["2"]["add"], bang[lv]["attrs"]["2"]["need"]]
               for lv in sorted(bang, key=int)]
        print("  doi chieu cot INT voi pet_stats.json: %s"
              % ("KHOP" if cu == moi else "LECH -> %s vs %s" % (cu[:3], moi[:3])))
        if cu and cu != moi:
            raise SystemExit("=> NGHI PARSE LECH: cot INT khong trung ban da dung lau")
    except FileNotFoundError:
        print("  (bo qua doi chieu INT: khong co pet_stats.json)")

    data = {
        "_note": "Bang nang cap + boi duong THU CUOI. Sinh boi tools/crack_mounts_grow.py tu "
                 "MountsGrow_C.dat (doc TUAN TU, ban ghi 39B). kind: 1=Atk 2=Int 3=Def 4=ExtraHp "
                 "5=ExtraSp. 'need' = so DIEM can de len 1 cap cua chi so do (diem cong don, moi "
                 "vien = 1 diem). RANG BUOC client: cap chi so KHONG duoc vuot cap thu cuoi.",
        "levels": bang,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print("=> %s: %d cap" % (os.path.basename(OUT), len(bang)))

    doi = sorted({r["up_item"] for r in bang.values() if r["up_item"]})
    print("   item NANG CAP dung o cac cap: %s" % ["0x%04x %s" % (i, ten(i)) for i in doi])
    print("   item BOI DUONG (co dinh moi cap): %s"
          % ["kind %s = 0x%04x %s" % (k, a["item"], ten(a["item"]))
             for k, a in sorted(bang["1"]["attrs"].items())])


if __name__ == "__main__":
    main()
