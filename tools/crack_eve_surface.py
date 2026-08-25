# -*- coding: utf-8 -*-
"""Doc bang LUA CHON (surface) cua tung scene tu `CompreseData/Eve.emg`.

Vi sao can: ma gui khi server CHO CHON o cong (`0x14 09 <ma>`) chi la VI TRI MUC, khong mang y
nghia - 30 = muc 1, 31 = muc 2... Moi cong mot kieu, nen doan ma la sai va rat dat (doan sai ->
server tra "su kien vi pham" -> NGAT KET NOI). File nay cho biet moi surface co bao nhieu muc va
noi dung tung muc, de tra ve THANG ma dung.

Cau truc file (crack `Data_Eve_EventData.lua`, thu tu doc CO DINH):
    Npc -> Goods -> Door -> Mine -> Surface -> SceneInfo -> Group -> NpcEvent -> Fight
Header dau file la bang index: [count u16] + moi ban ghi 32 byte (ten + offset/size).

Dung:
    python tools/crack_eve_surface.py --scene 63000
    python tools/crack_eve_surface.py --scene 63000 --surface 2
"""
import argparse
import os
import struct

EVE_DEFAULT = os.path.join("gamedata", "Eve.emg")
TALK_DEFAULT = os.path.join("gamedata", "Talk_C.dat")


def read_talk(path):
    """Talk_C.dat: [count i32] + moi dong `[id u16][len u16][chuoi UTF-16LE]`.

    Doc theo `Logic_DataManager.lua:1022-1026` (ReadUInt16 id, ReadBytes(ReadUInt16())).
    """
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as fh:
        d = fh.read()
    count = struct.unpack_from("<i", d, 0)[0]
    cur = 4
    out = {}
    for _ in range(count):
        if cur + 4 > len(d):
            break
        tid = struct.unpack_from("<H", d, cur)[0]
        ln = struct.unpack_from("<H", d, cur + 2)[0]
        cur += 4
        out[tid] = d[cur:cur + ln].decode("utf-16-le", errors="replace")
        cur += ln
    return out

# style cua sentence (Data_Eve_Eve_SurfaceData.lua)
STYLE = {1: "chu", 2: "nut", 3: "MUC-DANH-SACH", 4: "nut-dong"}
KIND = {1: "Talk.dat", 2: "Item.dat", 3: "Npc.dat"}


def read_index(data):
    """[count u16] + 32B/ban ghi; offset/size nam o byte 24..32; +103 nhu build_world_nav."""
    count = struct.unpack_from("<H", data, 0)[0]
    cur = 2
    out = {}
    for _ in range(count):
        n = data[cur]
        raw = data[cur + 1:cur + 1 + n]
        off, size = struct.unpack_from("<ii", data, cur + 24)
        cur += 32
        try:
            name = raw.decode("ascii")
        except UnicodeDecodeError:
            continue
        stem = os.path.splitext(name)[0]
        if stem.isdigit():
            out[int(stem)] = (off + 103, size)
    return out


def _skip_npc_goods(data, cur):
    npc_count = struct.unpack_from("<i", data, cur)[0]
    cur += 4
    for _ in range(npc_count):
        ec = struct.unpack_from("<H", data, cur + 4)[0]
        cur += 6 + ec
        cur += 1 + data[cur]                 # sale
        cur += 1 + (data[cur] + 1) * 8 + 81  # motion node
    goods_count = struct.unpack_from("<H", data, cur)[0]
    return cur + 2 + goods_count * 13


def _skip_doors(data, cur):
    count = struct.unpack_from("<H", data, cur)[0]
    cur += 2
    for _ in range(count):
        ec = struct.unpack_from("<H", data, cur + 2)[0]
        cur += 4 + ec + 16 + 6
    return cur


def _skip_mines(data, cur):
    """MineData (Data_Eve_Eve_MineData.lua): id u16 + eventCount u16 + events + 4 x i32 + 1 byte.

    KHAC DoorData o duoi cung: door co imgInfo(5B) + close(1B) = 6, mine chi co sizeKind = 1.
    Nham cho nay thi con tro chay ra ngoai file (da dinh mot lan).
    """
    count = struct.unpack_from("<H", data, cur)[0]
    cur += 2
    for _ in range(count):
        ec = struct.unpack_from("<H", data, cur + 2)[0]
        cur += 4 + ec + 16 + 1
    return cur


def read_surfaces(data, offset):
    cur = _skip_npc_goods(data, offset)
    cur = _skip_doors(data, cur)
    cur = _skip_mines(data, cur)
    count = struct.unpack_from("<H", data, cur)[0]
    cur += 2
    out = {}
    for _ in range(count):
        sid, _rel, sc, oi, oc, om = struct.unpack_from("<HHBBBB", data, cur)
        cur += 8
        sentences = []
        for _ in range(sc):
            did, dk, style, cut = struct.unpack_from("<HBBB", data, cur)
            cur += 5
            sentences.append({"dataId": did, "dataKind": dk, "style": style, "canCut": bool(cut)})
        out[sid] = {"optionIndex": oi, "optionCount": oc, "optionMode": om,
                    "sentences": sentences}
    return out


def ma_cho_muc(i):
    """Ma `C:020-009` cho muc thu i (1-based) - theo Logic_Event_EventHandler.lua:429-436."""
    return 30 + (i - 1) if i <= 10 else 60 + (i - 10)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eve", default=EVE_DEFAULT)
    ap.add_argument("--talk", default=TALK_DEFAULT)
    ap.add_argument("--scene", type=int, required=True)
    ap.add_argument("--surface", type=int, default=None)
    args = ap.parse_args()

    talk = read_talk(args.talk)
    with open(args.eve, "rb") as fh:
        data = fh.read()
    idx = read_index(data)
    if args.scene not in idx:
        raise SystemExit("khong co scene %d trong Eve.emg (%d scene)" % (args.scene, len(idx)))
    off, size = idx[args.scene]
    surfaces = read_surfaces(data, off)
    print("scene %d: %d surface" % (args.scene, len(surfaces)))
    for sid in sorted(surfaces):
        if args.surface is not None and sid != args.surface:
            continue
        s = surfaces[sid]
        muc = [x for x in s["sentences"] if x["style"] == 3]
        print("\n--- surface %d | optionMode=%d optionCount=%d | %d muc danh sach ---"
              % (sid, s["optionMode"], s["optionCount"], len(muc)))
        if not muc:
            print("    KHONG co muc danh sach -> hop Co/Khong: 20 = Co, 21 = Khong")
        def _chu(x):
            if x["dataKind"] == 1 and x["dataId"] in talk:
                return talk[x["dataId"]].replace("\n", " / ")
            return "(dataId=%d, %s)" % (x["dataId"], KIND.get(x["dataKind"], "?"))

        for i, x in enumerate(muc, 1):
            print("    muc %d -> ma %-3d %s" % (i, ma_cho_muc(i), _chu(x)))
        for x in s["sentences"]:
            if x["style"] != 3:
                print("    [%s] %s" % (STYLE.get(x["style"], x["style"]), _chu(x)))


if __name__ == "__main__":
    main()
