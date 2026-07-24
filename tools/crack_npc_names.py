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
    names = parse_names(NPC)
    out = {("0x%04x" % k): v for k, v in sorted(names.items())}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    mineral = [v for v in names.values() if "Khoáng" in v]
    print("npc_names.json: %d ten -> %s" % (len(out), OUT))
    print("  vd co 'Khoang': %d con (%s ...)" % (len(mineral), ", ".join(sorted(set(mineral))[:6])))


if __name__ == "__main__":
    main()
