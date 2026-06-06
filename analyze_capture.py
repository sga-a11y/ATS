"""Phan tich pcap -> rut ra thong tin pet + skill de cap nhat pets.json / skills_db.json.

Chay: python analyze_capture.py [file.pcap]   (mac dinh: ts_capture.pcap)
In ra:
  - Pet id dang dung / doi (S2C+C2S 0x13)
  - Skill char/pet da dung trong tran (C2S 0x32)
  - Bo skill char (S2C 0x28)
"""
import struct, sys

FN = sys.argv[1] if len(sys.argv) > 1 else "ts_capture.pcap"


def frames(fn):
    d = open(fn, "rb").read()
    linktype = struct.unpack("<I", d[20:24])[0]
    L = 16 if linktype == 113 else 14
    off = 24; out = []
    while off + 16 <= len(d):
        _, _, incl, _ = struct.unpack("<IIII", d[off:off+16]); off += 16
        p = d[off:off+incl]; off += incl
        if len(p) < L + 20 or p[L+9] != 6:
            continue
        ihl = (p[L] & 0x0f) * 4; t = L + ihl; doff = (p[t+12] >> 4) * 4
        pay = p[t+doff:]
        if not pay:
            continue
        sp = struct.unpack(">H", p[t:t+2])[0]; dp = struct.unpack(">H", p[t+2:t+4])[0]
        dr = "C2S" if dp == 6614 else ("S2C" if sp == 6614 else None)
        if not dr:
            continue
        raw = bytes(x ^ 0xAD for x in pay)
        i = 0
        while i + 7 <= len(raw):
            if raw[i] == 0xc0 and raw[i+1] == 0x91:
                ln = struct.unpack("<H", raw[i+2:i+4])[0]
                if 7 <= ln <= 4096 and i + ln <= len(raw):
                    out.append((dr, raw[i+6], raw[i+7:i+ln])); i += ln; continue
            i += 1
    return out


def main():
    fr = frames(FN)
    print(f"=== {FN}: {len(fr)} packets ===\n")

    # Pet id (0x13)
    pets = []
    for dr, op, b in fr:
        if op == 0x13 and len(b) >= 4 and b[:2] in (b"\x01\x00", b"\x04\x00"):
            pid = int.from_bytes(b[2:4], "little")
            tag = "dang dung" if b[:2] == b"\x04\x00" else "doi sang"
            pets.append((pid, tag))
    print("--- PET ID (0x13) ---")
    for pid, tag in pets:
        print(f"  0x{pid:x}  ({tag})")
    if not pets:
        print("  (khong co)")

    # Skill char/pet da dung (C2S 0x32)
    print("\n--- SKILL DA DUNG (C2S 0x32) ---")
    seen = {}
    for dr, op, b in fr:
        if dr == "C2S" and op == 0x32 and len(b) >= 8:
            unit = b[2]; sk = struct.unpack_from("<H", b, 6)[0]
            u = "CHAR" if unit == 3 else ("PET" if unit == 2 else f"u{unit}")
            seen.setdefault(u, set()).add(sk)
    for u, sks in seen.items():
        print(f"  {u}: {sorted(sks)}  (hex: {[hex(s) for s in sorted(sks)]})")
    if not seen:
        print("  (khong co tran danh trong capture)")

    # Char skill bar (S2C 0x28)
    print("\n--- CHAR SKILL BAR (S2C 0x28) ---")
    found28 = False
    for dr, op, b in fr:
        if op == 0x28 and len(b) > 6:
            found28 = True
            payload = b[7-7:] if len(b) >= 4 else b
            # parse: [01 00][unit][count][skills 2B*count]
            i = 2; out = []
            while i + 2 <= len(b):
                unit = b[i]; cnt = b[i+1]
                if unit not in (2, 3) or cnt == 0 or cnt > 20:
                    break
                i += 2; sks = []
                for _ in range(cnt):
                    if i + 2 > len(b):
                        break
                    s = int.from_bytes(b[i:i+2], "little"); i += 2
                    if s:
                        sks.append(s)
                u = "CHAR" if unit == 3 else "PET"
                out.append(f"{u}: {[hex(s) for s in sks]}")
            print("  " + " | ".join(out) if out else f"  raw: {b.hex()}")
    if not found28:
        print("  (khong co)")


if __name__ == "__main__":
    main()
