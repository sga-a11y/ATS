# -*- coding: utf-8 -*-
"""Sinh `eq_affix.json` (bang DONG PHU / 洗鍊 cua trang bi) tu `Data/EquipmentAffix_C.dat`.

Vi sao can: affix1/2/3 trong ThingData KHONG phai "cap" ma la ID TRA BANG. Client lam:
    ItemData:GetAttrText(eqAffixAllDatas[itemSave.affix1].attr) .. " +" ..
    eqAffixAllDatas[itemSave.affix1].level[1]
Tuc: affix o dong thu N -> tra bang lay `attr` (loai chi so) va `level[N]` (tri so cua dong do).
Bot khong co bang nay thi chi hien duoc con so ID vo nghia.

Cau truc (crack Data_EQAffixData.lua EQAffixData.New + DataManager.OnLoadEQAffixData):
    [count i32] + moi ban ghi 11 byte:
      index(1) | kind(1) | attr(2) | level1(2) level2(2) level3(2) | rate(1)
    kind = bitmask VI TRI mac duoc (1 mu, 2 ao, 4 vu khi, 8 ho uyen, 16 giay, 32 dac biet).

Dung:
    python tools/crack_eq_affix.py
"""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "eq_affix.json")


def read_affix(path):
    with open(path, "rb") as fh:
        data = fh.read()
    count = struct.unpack_from("<i", data, 0)[0]
    cur = 4
    out = {}
    for _ in range(count):
        if cur + 11 > len(data):
            break
        idx, kind, attr, l1, l2, l3, rate = struct.unpack_from("<BBHHHHB", data, cur)
        cur += 11
        # Cung mot index co the lap lai cho nhieu vi tri (kind la bitmask) - client cung ghi de
        # vao eqAffixAllDatas[index], nen giu ban cuoi la khop.
        out[idx] = {"attr": attr, "lv": [l1, l2, l3], "kind": kind, "rate": rate}
    return out


def main():
    path = os.path.join(ROOT, "gamedata", "Data", "EquipmentAffix_C.dat")
    if not os.path.exists(path):
        print("khong tim thay EquipmentAffix_C.dat - keo tu may ao:")
        print("  adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/EquipmentAffix_C.dat "
              "gamedata/Data/")
        return 1
    rows = read_affix(path)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"affix": {str(k): v for k, v in sorted(rows.items())}}, fh,
                  ensure_ascii=False, separators=(",", ":"))
    print("da ghi %s: %d dong phu" % (os.path.basename(OUT), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
