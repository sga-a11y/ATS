"""Crack npc_names.json tu gamedata/Data/Npc_C.dat: { npc_id_hex: ten }.

Dung de tra TEN QUAI trong battle (vd dieu kien skill 'quai khoang' -> ten chua 'Khoang').
Model-id cua quai lay tu goi spawn S2C 0x07: `0000 [entity 8B] [model_id 2B LE] [x 2B][y 2B]`.
Record trong Npc_C.dat: `[namelen 2B LE][name UTF-16LE][1B sep][id 2B LE][...]` (sep khac nhau:
0x01/0x03/0x07/0x0f/0x10/0x1a...). Xem tools/crack_pets.py (cung format, anchor khac).

Chay: python tools/crack_npc_names.py   (doc gamedata/Data/Npc_C.dat -> ghi npc_names.json)
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPC = os.path.join(ROOT, "gamedata", "Data", "Npc_C.dat")
OUT = os.path.join(ROOT, "npc_names.json")


def parse_names_seq(path):
    """Doc TUAN TU theo NpcData.New - CHINH XAC, thay cho quet chu ky.

    Ban ghi: [nameLen u16][name utf-16le][kind 1][id u16] + 78 byte co dinh (het o +80 sau id).
    Chot tu kiem chung: phai TIEU HET FILE va rideOffset raw (ip+70) quanh 1000.

    VI SAO BO KIEU QUET: doi chieu tren chinh file nay - quet ra 6074 ten, tuan tu ra 8326.
    Quet THIEU 2270 ten (vd 0x2f87 "Oan Truong Phi", 0x396d "Manh Hoach"), BIA 18 muc, va sai 26
    ten: 0x564e ra rac 'rac2ky' thay vi "Banh Trung Thu"; 0x3ee3 cut dau "Quan Cong Tuong" (dung
    la "Tuy Quan Cong Tuong"). Ten quai dung de khop dieu kien skill trong tran -> thieu ten =
    dieu kien AM THAM khong bao gio dung.
    """
    import struct
    d = open(path, "rb").read()
    count = struct.unpack_from("<i", d, 0)[0]
    if not (0 < count < 100000):
        raise SystemExit("header so ban ghi bat thuong: %s" % count)
    names, i, xa = {}, 4, 0
    for _ in range(count):
        nl = struct.unpack_from("<H", d, i)[0]
        j = i + 2 + nl
        if nl > 400 or j + 1 + 80 > len(d):
            raise SystemExit("parse lech tai ban ghi thu %d" % len(names))
        ip = j + 1
        pid = struct.unpack_from("<H", d, ip)[0]
        if not (500 <= struct.unpack_from("<H", d, ip + 70)[0] <= 1500):
            xa += 1
        try:
            nm = d[i + 2:j].decode("utf-16-le").strip()
        except Exception:
            nm = ""
        if pid and nm:
            names[pid] = nm
        i = ip + 80
    if abs(i - len(d)) > 8:
        raise SystemExit("parse xong con du %d byte -> nghi lech" % (len(d) - i))
    if xa > count * 0.05:
        raise SystemExit("nghi parse lech: %d/%d ban ghi co rideOffset bat thuong" % (xa, count))
    return names


def parse_names(path):
    """Quet TOAN BO record co dang [namelen][name][sep][id]. Anchor = 1 ten UTF-16LE tieng Viet
    hop le, ngay sau la 1 byte sep nho (<0x20) roi id 2B. Sai so (record rac) vo hai: bot chi tra
    ten cho model-id NO THUC SU thay tu goi 0x07."""
    d = open(path, "rb").read()
    n = len(d)
    names = {}
    i = 0
    while i < n - 6:
        ln = d[i] | (d[i + 1] << 8)
        # ten quai/npc thuong 2..40 byte UTF-16 (1..20 ky tu)
        if 2 <= ln <= 40 and ln % 2 == 0 and i + 2 + ln + 3 <= n:
            sep = d[i + 2 + ln]
            if sep < 0x20:   # byte phan tach name<->id (quan sat: 0x01/03/07/0f/10/1a...)
                try:
                    name = d[i + 2:i + 2 + ln].decode("utf-16le")
                except Exception:
                    name = None
                if name and all(0x20 <= ord(c) < 0x2200 for c in name) \
                        and any(c.isalpha() for c in name):
                    nid = d[i + 2 + ln + 1] | (d[i + 2 + ln + 2] << 8)
                    # id quai/npc thuong >= 0x2000 (duoi la field rac). Giu id dau tien gap.
                    if nid >= 0x2000 and nid not in names:
                        names[nid] = name
                        # KHONG nhay qua payload (do dai bien) -> quet TUNG offset de khong sot
                        # record. Trung id giu ban dau tien (setdefault-style o tren).
        i += 1
    return names


def main():
    names = parse_names_seq(NPC)
    out = {("0x%04x" % k): v for k, v in sorted(names.items())}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    mineral = [v for v in names.values() if "Khoáng" in v]
    print("npc_names.json: %d ten -> %s" % (len(out), OUT))
    print("  vd co 'Khoang': %d con (%s ...)" % (len(mineral), ", ".join(sorted(set(mineral))[:6])))


if __name__ == "__main__":
    main()
