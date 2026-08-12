"""Crack exclusive_weapons.json: VU KHI CHUYEN DUNG (VKCD) <-> VO TUONG duoc dung.

Nguon: client Lua da giai ma (xem KNOWLEDGE.md muc crack Lua):
  Data/ItemData.lua
    self.kind    = ReadByte()    --[2]  loai item; EItemKind.ExclusiveWeapon = 87 (專武)
    self.Id      = ReadUInt16()  --[3]  item id
    self.spare3  = ReadUInt16()  --[38] "bi danh" -> VOI kind==87 day la NPC ID cua vo tuong
  ItemData:GetName()
    if self.kind == EItemKind.ExclusiveWeapon then
        local npcName = npcDatas[self.spare3]        <-- CHINH XAC: spare3 = npc id
        result = result .. " 「" .. npcName:GetName() .. "」"
Nen: item kind==87  ->  spare3 = id vo tuong so huu.

File .dat KHONG theo repo (gitignore) - copy tu client vao truoc khi chay:
  gamedata_Item.dat  (hoac gamedata/Data/Item_C.dat)
  gamedata_Npc.dat   (hoac gamedata/Data/Npc_C.dat)

Record ItemData la BIEN DO DAI (co 2 chuoi UTF-16LE: name va description) nen KHONG the
nhay theo buoc co dinh -> doc TUAN TU dung thu tu truong nhu Lua.

Chay: python tools/crack_exclusive_weapons.py
Ghi:  exclusive_weapons.json  { "<item_id_hex>": {"item": ten, "npc_id": id, "npc": ten_vo_tuong} }
"""
from __future__ import annotations

import json
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "exclusive_weapons.json")
KIND_EXCLUSIVE_WEAPON = 87          # EItemKind.ExclusiveWeapon (ItemData.lua:118) = 專武


def _find(*names):
    """File .dat co the nam o goc repo (gamedata_X.dat) hoac gamedata/Data/X_C.dat."""
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(ROOT, n)
        if os.path.isfile(p):
            return p
    return None


class Reader:
    """Doc tuan tu little-endian, giong DatReader cua client."""

    def __init__(self, buf: bytes):
        self.b = buf
        self.i = 0

    def byte(self) -> int:
        v = self.b[self.i]
        self.i += 1
        return v

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.b, self.i)[0]
        self.i += 2
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.b, self.i)[0]
        self.i += 4
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.b, self.i)[0]
        self.i += 4
        return v

    def text(self) -> str:
        """[len u16][UTF-16LE] - len tinh theo BYTE (giong ReadBytes(ReadUInt16()))."""
        n = self.u16()
        s = self.b[self.i:self.i + n]
        self.i += n
        return s.decode("utf-16-le", "ignore")


def parse_items(path):
    """Doc Item_C.dat theo dung thu tu truong trong ItemData.New(). Tra list dict."""
    r = Reader(open(path, "rb").read())
    count = r.u32()
    out = []
    for _ in range(count):
        it = {}
        it["name"] = r.text()                     # [1]
        it["kind"] = r.byte()                     # [2]
        it["id"] = r.u16()                        # [3]
        r.u16()                                   # [4] iconId
        r.u16(); r.u16()                          # [5][6] picId nam/nu
        r.u16(); r.byte(); r.i32()                # [7][8][9]  attribute[1]
        r.u16(); r.byte(); r.i32()                # [10][11][12] attribute[2]
        r.byte()                                  # [13] material
        it["level"] = r.byte()                    # [14]
        it["fitType"] = r.byte()                  # [15] 3 = vu khi
        r.u16()                                   # [16] specialAbility
        for _i in range(8):                       # [17]..[24] colorTints
            r.i32()
        r.byte()                                  # [25] openUsed
        it["needLv"] = r.byte()                   # [26]
        r.i32(); r.i32()                          # [27][28] price/sellPrice
        r.byte()                                  # [29] gender
        r.byte()                                  # [30] restrict
        r.i32()                                   # [31] threshold
        r.byte()                                  # [32] element
        r.i32()                                   # [33] elementValue
        r.u16()                                   # [34] skillLink
        r.byte()                                  # [35] turn
        r.u16()                                   # [36] giftDot
        r.byte()                                  # [37] spare2
        it["spare3"] = r.u16()                    # [38] <-- npc id khi kind==87
        r.byte()                                  # [39] restrict2
        r.u16()                                   # [40] suitId
        r.byte()                                  # [41] spare5
        r.byte()                                  # [42] directUse
        r.u16()                                   # [43] roleCountIndex
        r.i32()                                   # [44] roleCountValue
        r.byte()                                  # [45] sort
        r.byte(); r.byte()                        # [46][47] equipSwitch nam/nu
        r.byte()                                  # [48] btnState
        r.byte()                                  # [49] durable
        it["furnaceKind"] = r.byte()              # [50] 3 = chuyen vu
        r.u32()                                   # [51] furnaceCount
        it["quality"] = r.byte()                  # [52] 0 trang 1 luc 2 lam 3 tim 4 do
        r.byte(); r.byte()                        # [53][54] auctionTag/SubTag
        it["desc"] = r.text()                     # mo ta
        out.append(it)
    return out


def parse_npc_names(path):
    """Ten NPC theo id - QUET BYTE theo mau (cach cu cua tools/crack_npc_names.py).

    CHI giu lai cho tuong thich: no BO SOT nhieu npc (ban dac biet 45xxx/46xxx) va doi khi cat
    mat chu dau. Code moi nen dung tools/crack_npc_table.py (doc TUAN TU dung layout NpcData.New).
    """
    buf = open(path, "rb").read()
    names = {}
    i = 0
    n = len(buf)
    while i + 4 < n:
        ln = struct.unpack_from("<H", buf, i)[0]
        if 2 <= ln <= 80 and ln % 2 == 0 and i + 2 + ln + 3 <= n:
            raw = buf[i + 2:i + 2 + ln]
            try:
                nm = raw.decode("utf-16-le")
            except Exception:
                i += 1
                continue
            if nm and all(ord(c) >= 0x20 for c in nm):
                sep = buf[i + 2 + ln]
                if sep < 0x20:
                    nid = struct.unpack_from("<H", buf, i + 2 + ln + 1)[0]
                    if nid and nid not in names:
                        names[nid] = nm
                    i += 2 + ln + 3
                    continue
        i += 1
    return names


def main():
    item_path = _find("gamedata_Item.dat", os.path.join("gamedata", "Data", "Item_C.dat"))
    npc_path = _find("gamedata_Npc.dat", os.path.join("gamedata", "Data", "Npc_C.dat"))
    if not item_path:
        raise SystemExit("Khong thay gamedata_Item.dat (hoac gamedata/Data/Item_C.dat)")
    items = parse_items(item_path)
    # Doc TUAN TU (crack_npc_table) thay vi quet byte: bang cu bo sot dung cac ban dac biet
    # ('Ma Quan Vu', 'Nhan Dieu Tuyet 2', 'Loka'...) -> 13 vkcd tung khong co ten tuong.
    from crack_npc_table import read_npcs
    npcs = {i: v["name"] for i, v in read_npcs(npc_path).items()} if npc_path else {}
    print("doc %d item tu %s" % (len(items), os.path.basename(item_path)))
    print("doc %d ten npc" % len(npcs))

    out = {}
    for it in items:
        if it["kind"] != KIND_EXCLUSIVE_WEAPON:
            continue
        out["0x%04x" % it["id"]] = {
            "item": it["name"],
            "npc_id": it["spare3"],
            "npc": npcs.get(it["spare3"], ""),
            "level": it["level"],
            "quality": it["quality"],
        }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print("=> %d vu khi chuyen dung -> %s" % (len(out), os.path.basename(OUT)))
    for k, v in sorted(out.items(), key=lambda kv: kv[1]["item"])[:15]:
        print("   %s  %-28s -> %s (npc %d)" % (k, v["item"], v["npc"] or "?", v["npc_id"]))


if __name__ == "__main__":
    main()
