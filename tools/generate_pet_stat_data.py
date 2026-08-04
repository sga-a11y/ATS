"""Generate compact runtime tables for pet HP/SP from decrypted TS Online data."""
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_work" / "pet_crack"
OUT = ROOT / "pet_stats.json"
RELEVANT = {207, 208, 212, 214, 218, 219}


def item_data(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    off = 4
    result = {}
    for _ in range(count):
        name_len = struct.unpack_from("<H", data, off)[0]
        off += 2 + name_len
        kind = data[off]
        item_id = struct.unpack_from("<H", data, off + 1)[0]
        off += 3 + 2 + 4
        attrs = []
        for _ in range(2):
            attr = struct.unpack_from("<H", data, off)[0]
            value = struct.unpack_from("<i", data, off + 3)[0] - 100
            attrs.append([attr, value])
            off += 7
        fit_type = data[off + 2]
        off += 1 + 1 + 1 + 2 + 32 + 1 + 1 + 4 + 4 + 1 + 1 + 4
        element = data[off]
        element_value = struct.unpack_from("<i", data, off + 1)[0] - 100
        off += 5 + 2 + 1 + 2 + 1 + 2 + 1
        suit_id = struct.unpack_from("<H", data, off)[0]
        off += 2 + 1 + 1 + 2 + 4 + 1 + 2 + 1 + 1 + 1 + 4 + 1 + 1 + 1
        desc_len = struct.unpack_from("<H", data, off)[0]
        off += 2 + desc_len
        kept = [[a, v] for a, v in attrs if a in RELEVANT and v]
        if kept or suit_id or 1 <= fit_type <= 6:
            result[str(item_id)] = {
                "a": kept, "e": element, "ev": element_value,
                "k": kind, "s": suit_id,
            }
    return result


def npc_data(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    off = 4
    result = {}
    for _ in range(count):
        name_len = struct.unpack_from("<H", data, off)[0]
        off += 2 + name_len
        item_id = struct.unpack_from("<H", data, off + 1)[0]
        off += 1 + 2 + 2 + 2 + 16 + 4 + 4 + 4 + 12 + 1 + 2
        element = data[off]
        off += 1 + 3 * 2 + 2
        turn = data[off]
        off += 1 + 2 + 1 + 2 + 2 + 2 + 2 + 8 + 1 + 1
        result[str(item_id)] = [element, turn]
    return result


def style_data(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    off = 4
    result = {}
    for _ in range(count):
        style_id = struct.unpack_from("<H", data, off)[0]
        item_ids = list(struct.unpack_from("<5H", data, off + 6))
        scores = list(struct.unpack_from("<6H", data, off + 20))
        result[str(style_id)] = [item_ids, scores]
        off += 32
    return result


def style_values(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    off = 4
    result = []
    for _ in range(count):
        score = struct.unpack_from("<H", data, off)[0]
        off += 2
        attrs = []
        for _ in range(4):
            kind = data[off]
            value = struct.unpack_from("<H", data, off + 1)[0]
            off += 3
            if kind in (27, 30, 31, 32) and value:
                attrs.append([kind, value])
        result.append([score, attrs])
    return result


def card_data(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    off = 4
    result = {}
    for _ in range(count):
        card_id = data[off]
        off += 2 + 4 + 4 + 18 + 1 + 2
        attrs = []
        for _ in range(6):
            kind = data[off]
            value, grow = struct.unpack_from("<HH", data, off + 1)
            off += 5
            if kind in (27, 30, 31, 32) and (value or grow):
                attrs.append([kind, value, grow])
        result[str(card_id)] = attrs
    return result


def suit_data(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    off = 4
    result = {}
    for _ in range(count):
        suit_id = struct.unpack_from("<H", data, off)[0]
        off += 2 + 4 + 1
        attrs = []
        for _ in range(3):
            need, kind = data[off:off + 2]
            value = struct.unpack_from("<H", data, off + 2)[0] - 100
            off += 4
            if kind in RELEVANT and value:
                attrs.append([need, kind, value])
        if attrs:
            result[str(suit_id)] = attrs
    return result


def mount_int_grow(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    off = 4
    result = []
    for _ in range(count):
        level = data[off]
        off += 1 + 1 + 2 + 1 + 4
        attrs = []
        for _ in range(5):
            add, _item, need = struct.unpack_from("<HHH", data, off)
            attrs.append((add, need))
            off += 6
        result.append([level, attrs[1][0], attrs[1][1]])
    return result


def mount_flags(path):
    data = path.read_bytes()
    count = struct.unpack_from("<i", data)[0]
    return [struct.unpack_from("<HHIB", data, 4 + i * 9)[1] for i in range(count)]


def main():
    out = {
        "items": item_data(SRC / "Item_C.dat"),
        "npcs": npc_data(SRC / "Npc_C.dat"),
        "styles": style_data(SRC / "CollectStyle_C.dat"),
        "style_values": style_values(SRC / "CollectStyleValue_C.dat"),
        "cards": card_data(SRC / "CollectCard_C.dat"),
        "suits": suit_data(SRC / "Suit_C.dat"),
        "mount_int_grow": mount_int_grow(SRC / "MountsGrow_C.dat"),
        "mount_flags": mount_flags(SRC / "Mounts_C.dat"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
