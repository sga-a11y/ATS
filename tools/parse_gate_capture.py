"""Trich data cong tu pcap di qua cong (game VTC) -> snippet map_gates.json.

Moi lan di qua cong: C2S 0x14 0800[idx] (VAO cong) + goi 0x06 move ngay truoc (toa do cong).
Map nguon/dich doc tu S2C 0x03/0x0c (co field map_id trong dai 11000-19999).

Dung: python tools/parse_gate_capture.py gate.pcap
       (in cac cong + JSON de merge tay vao map_gates.json)
"""
import struct
import sys


def load(fn):
    d = open(fn, "rb").read()
    lt = struct.unpack("<I", d[20:24])[0]
    L = 16 if lt == 113 else 14
    off = 24
    out = []
    xor = lambda b: bytes(x ^ 0xAD for x in b)
    buf = {"c": b"", "s": b""}
    while off + 16 <= len(d):
        ts, tu, incl, _ = struct.unpack("<IIII", d[off:off + 16])
        off += 16
        if off + incl > len(d):
            break
        p = d[off:off + incl]
        off += incl
        if len(p) < L + 20 or p[L + 9] != 6:
            continue
        ihl = (p[L] & 0x0f) * 4
        t = L + ihl
        doff = (p[t + 12] >> 4) * 4
        pay = p[t + doff:]
        if not pay:
            continue
        k = "c" if struct.unpack(">H", p[t + 2:t + 4])[0] == 6614 else "s"
        buf[k] += xor(pay)
        s = buf[k]
        i = 0
        while i + 7 <= len(s):
            if s[i] == 0xc0 and s[i + 1] == 0x91:
                ln = struct.unpack("<H", s[i + 2:i + 4])[0]
                if 7 <= ln <= 2000 and i + ln <= len(s):
                    out.append((ts + tu / 1e6, "C2S" if k == "c" else "S2C", s[i + 6], s[i + 7:i + ln]))
                    i += ln
                    continue
            i += 1
        buf[k] = s[i:]
    return out


def _map_of_0x03(payload):
    """map_id o offset 21 (u16 LE) trong S2C 0x03 (xac nhan tu capture)."""
    if len(payload) >= 23:
        v = struct.unpack_from("<H", payload, 21)[0]
        if 11000 <= v <= 19999:
            return v
    return None


def parse(fn):
    fr = load(fn)
    cur_map = None
    last_move = None
    events = []   # dict: {idx, x, y, src, dst}
    for ts, d_, op, b in fr:
        if d_ == "S2C" and op == 0x03:
            m = _map_of_0x03(b)
            if m and m != cur_map:
                # map vua doi -> gan dst cho event gan nhat con thieu
                if events and events[-1]["dst"] is None and m != events[-1]["src"]:
                    events[-1]["dst"] = m
                cur_map = m
            elif m:
                cur_map = m
        elif d_ == "C2S" and op == 0x06 and len(b) >= 7:
            last_move = (struct.unpack_from("<H", b, 3)[0], struct.unpack_from("<H", b, 5)[0])
        elif d_ == "C2S" and op == 0x14 and b[:2] == b"\x08\x00" and len(b) >= 4:
            if last_move:
                events.append({"idx": b[2], "x": last_move[0], "y": last_move[1],
                               "src": cur_map, "dst": None})
    return events


if __name__ == "__main__":
    fn = sys.argv[1] if len(sys.argv) > 1 else "gate.pcap"
    evs = parse(fn)
    print(f"=== {len(evs)} cong di qua trong {fn} ===")
    for e in evs:
        print(f"  src_map={e['src']}  idx={e['idx']}  toa_do=({e['x']},{e['y']})  -> dst_map={e['dst']}")
    print("\n=== Snippet merge vao map_gates.json ===")
    for e in evs:
        dst = e["dst"] if e["dst"] is not None else "???"
        print(f'  "{e["src"]}": {{ "gates": [ {{"x":{e["x"]}, "y":{e["y"]}, "to":{dst}, "idx":{e["idx"]}}} ] }},')
