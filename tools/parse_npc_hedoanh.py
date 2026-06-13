"""Parse Npc_C.dat (game data) -> pet_hedoanh.json (ten pet -> {he, doanh}).

Npc_C.dat: [count 4B] + records. Moi record co [namelen 2B][name UTF-16LE][...fields].
  - doanh = byte ngay sau ten (pos 0):  1=Hoang 2=Nguy 3=Thuc 4=Ngo 5=Du
  - he    = byte pos 50 sau ten:        1=Dia 2=Thuy 3=Hoa 4=Phong
(Giai ma tu 6 pet biet: Quan Vu, Thai Van Co, Tuong, Cuu Soi, Tao Thao, Luc Ton, Truong Giac.)

Chay: python tools/parse_npc_hedoanh.py [duong_dan_Npc_C.dat]
Mac dinh doc gamedata_Npc.dat o thu muc goc.
"""
import sys, os, json

HE = {1: "Dia", 2: "Thuy", 3: "Hoa", 4: "Phong"}
DOANH = {1: "Hoang", 2: "Nguy", 3: "Thuc", 4: "Ngo", 5: "Du"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(path):
    d = open(path, "rb").read()
    out = {}
    pos = 4   # bo qua count 4B
    n = len(d)
    while pos < n - 2:
        nl = int.from_bytes(d[pos:pos + 2], "little")
        # namelen hop le: chan, 2..40 byte, du cho name + 51 byte field sau
        if 2 <= nl <= 40 and nl % 2 == 0 and pos + 2 + nl + 51 <= n:
            raw = d[pos + 2:pos + 2 + nl]
            try:
                name = raw.decode("utf-16-le")
            except Exception:
                name = None
            if name and all(0x20 <= ord(c) for c in name) and any(c.isalpha() for c in name):
                fe = pos + 2 + nl            # offset sau ten
                doanh_id = d[fe]
                he_id = d[fe + 50]
                if he_id in HE and doanh_id in DOANH and name not in out:
                    out[name] = {"he": HE[he_id], "doanh": DOANH[doanh_id]}
                pos += 2 + nl
                continue
        pos += 1
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "gamedata_Npc.dat")
    table = parse(src)
    # verify 6 pet biet
    known = {"Quan Vũ": ("Phong", "Thuc"), "Thái Văn Cơ": ("Hoa", "Du"),
             "Tưởng Nghĩa Cừ": ("Dia", "Du"), "Cửu Sởi": ("Thuy", "Du"),
             "Tào Tháo": ("Hoa", "Nguy"), "Lục Tốn": ("Thuy", "Ngo"),
             "Trương Giác": ("Dia", "Hoang")}
    ok = 0
    for nm, (he, dn) in known.items():
        got = table.get(nm)
        good = got and got["he"] == he and got["doanh"] == dn
        ok += good
        print("  %-16s %s  %s" % (nm, got, "OK" if good else "SAI/THIEU"))
    print("Verify: %d/%d pet biet dung. Tong pet table: %d" % (ok, len(known), len(table)))
    dst = os.path.join(ROOT, "pet_hedoanh.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=0)
    print("Da ghi:", dst)
