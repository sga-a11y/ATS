import ipaddress
import socket
import struct
import sys
from collections import Counter


XOR_KEY = 0xAD


def _read_pcap(fn):
    d = open(fn, "rb").read()
    if len(d) < 24:
        return []
    linktype = struct.unpack("<I", d[20:24])[0]
    link_len = 16 if linktype == 113 else 14
    off = 24
    packets = []
    while off + 16 <= len(d):
        _ts_sec, _ts_usec, incl, _orig = struct.unpack("<IIII", d[off:off + 16])
        off += 16
        packets.append(d[off:off + incl])
        off += incl
    return [(link_len, p) for p in packets]


def _is_private(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def _direction(src, sp, dst, dp):
    if dp == 6614:
        return "C2S"
    if sp == 6614:
        return "S2C"
    if _is_private(src) and not _is_private(dst):
        return "C2S"
    if _is_private(dst) and not _is_private(src):
        return "S2C"
    return "?"


def _decoded_frames(payload):
    raw = bytes(x ^ XOR_KEY for x in payload)
    i = 0
    out = []
    while i + 7 <= len(raw):
        if raw[i] == 0xC0 and raw[i + 1] == 0x91:
            ln = struct.unpack("<H", raw[i + 2:i + 4])[0]
            if 7 <= ln <= 65535 and i + ln <= len(raw):
                out.append((raw[i + 6], raw[i + 7:i + ln]))
                i += ln
                continue
        i += 1
    return out


def load_frames(fn):
    out = []
    payload_flows = Counter()
    for link_len, p in _read_pcap(fn):
        if len(p) < link_len + 20:
            continue
        proto = p[link_len + 9]
        if proto not in (6, 17):
            continue
        ihl = (p[link_len] & 0x0F) * 4
        min_l4 = 20 if proto == 6 else 8
        if ihl < 20 or len(p) < link_len + ihl + min_l4:
            continue
        ip0 = link_len
        t = link_len + ihl
        if proto == 6:
            doff = (p[t + 12] >> 4) * 4
            if doff < 20 or len(p) < t + doff:
                continue
            payload = p[t + doff:]
        else:
            doff = 8
            payload = p[t + doff:]
        if not payload:
            continue

        src = socket.inet_ntoa(p[ip0 + 12:ip0 + 16])
        dst = socket.inet_ntoa(p[ip0 + 16:ip0 + 20])
        sp = struct.unpack(">H", p[t:t + 2])[0]
        dp = struct.unpack(">H", p[t + 2:t + 4])[0]
        proto_name = "TCP" if proto == 6 else "UDP"
        payload_flows[(proto_name, src, sp, dst, dp)] += len(payload)

        if proto != 6:
            continue

        frames = _decoded_frames(payload)
        if not frames:
            continue
        dr = _direction(src, sp, dst, dp)
        for op, body in frames:
            out.append({
                "dir": dr,
                "op": op,
                "body": body,
                "src": src,
                "sp": sp,
                "dst": dst,
                "dp": dp,
            })
    return out, payload_flows


def _describe(op, b):
    if op == 0x17 and len(b) >= 2:
        sub = b[:2].hex()
        if b[:2] == b"\x0f\x00" and len(b) >= 9:
            return "use_slot slot=%02x qty=%d target=%02x" % (b[2], b[3], b[7])
        if b[:2] == b"\x0b\x00" and len(b) >= 3:
            return "use/open item? slot=%02x" % b[2]
        return "item sub=%s" % sub
    if op == 0x14 and len(b) >= 2:
        return "party/dialog sub=%s" % b[:2].hex()
    if op == 0x07 and len(b) >= 4:
        return "switch_channel? sub=%s channel=%d" % (b[:2].hex(), int.from_bytes(b[2:4], "little"))
    if op == 0x44 and len(b) >= 6:
        return "teleport_city city=%d flag=%d" % (int.from_bytes(b[3:5], "little"), b[5])
    return ""


def _flow_label(fr):
    return "%s:%d -> %s:%d" % (fr["src"], fr["sp"], fr["dst"], fr["dp"])


if __name__ == "__main__":
    fn = sys.argv[1] if len(sys.argv) > 1 else "ts_capture_mumu12_congty.pcap"
    frames, payload_flows = load_frames(fn)
    c2s = [f for f in frames if f["dir"] == "C2S"]

    print("TS frames:", len(frames))
    if frames:
        print("Detected TS flows:")
        for flow, n in Counter(_flow_label(f) for f in frames).most_common():
            print("  %4d  %s" % (n, flow))
    else:
        print("No decoded TS frames. Top payload flows in pcap:")
        for (proto, src, sp, dst, dp), n in payload_flows.most_common(15):
            print("  %7d bytes  %-3s %s:%d -> %s:%d" % (n, proto, src, sp, dst, dp))

    print("C2S opcodes:", dict(Counter("0x%02x" % f["op"] for f in c2s)))
    print("Tong C2S frames:", len(c2s))
    print("--- Chuoi C2S (op: body) ---")
    for f in c2s:
        desc = _describe(f["op"], f["body"])
        suffix = ("  # " + desc) if desc else ""
        print("  0x%02x %s%s" % (f["op"], f["body"].hex(), suffix))
