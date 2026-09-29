"""DIEU KHIEN TU XA qua TIN NHAN RIENG (mat thoai) - xem documents/DIEU_KHIEN_TU_XA.md.

Nick nam trong whitelist (CHUNG + RIENG party = `config.leaders_for(pidx)`) nhan rieng cho mot acc
bot trong party: `off 30p` -> bot nhan lai xac nhan, CA PARTY logout, het 30 phut tu login lai.

Protocol (crack client, `Common/protocal.lua` + `Logic/Chat.lua`):
  S:002-003 <密頻訊息> +玩家ID(8) +稱號(2) +L(1) +名字(L) +L(1) +內容(L, UTF-16LE)
                       +物品數量(1) <<...>> +武將數量(1) <<...>>
  C:002-003 <密頻發話> +玩家ID(8) +L(1) +名字(L) +L(1) +內容(L, UTF-16LE) +物品數量(1) +武將數量(1)
Server gui lai BAN SAO tin minh vua nhan di cung qua S:002-003 voi roleId = CHINH MINH -> phai bo.
Ten nhan vat: UTF-16LE nhu moi cho doc ten khac cua bot (0x27, 0x0e...). CHUA doi chieu pcap -
`_on_whisper` log goi tho de kiem lai lan chay that dau tien.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from . import region as _region

OFF_MAX_PHUT = 600
_OFF_RE = re.compile(r"^\s*off\s+(\d{1,4})\s*p\s*$", re.IGNORECASE)


def parse_off(text):
    """'off 30p' -> 30. Sai cu phap / ngoai 1..OFF_MAX_PHUT -> None."""
    m = _OFF_RE.match(text or "")
    if not m:
        return None
    n = int(m.group(1))
    return n if 1 <= n <= OFF_MAX_PHUT else None


def is_allowed(name, whitelist):
    """Whitelist RONG -> KHONG ai duoc ra lenh (nguoc voi nhan loi moi party: rong = nhan het)."""
    ten = (name or "").strip().casefold()
    return bool(ten) and any(ten == (w or "").strip().casefold() for w in (whitelist or []))


def parse_whisper(pkt: bytes, region=None):
    """Goi S:002-003 day du (header 7 byte + sub 2 byte) -> (sender_id 8 byte, ten, noi dung)."""
    enc = (region or _region.get()).encoding
    b = pkt[9:]
    sender_id = b[0:8]
    off = 8 + 2                       # bo roleId + titleId
    nl = b[off]
    name = b[off + 1:off + 1 + nl].decode(enc, "replace").rstrip("\x00")
    off += 1 + nl
    ml = b[off]
    if off + 1 + ml > len(b):
        raise ValueError("goi mat thoai ngan hon do dai noi dung")
    msg = b[off + 1:off + 1 + ml].decode(enc, "replace").rstrip("\x00")
    return sender_id, name, msg


def _l_str(s: str, region=None) -> bytes:
    raw = s.encode((region or _region.get()).encoding)[:254]
    return bytes([len(raw)]) + raw


def build_whisper(target_id: bytes, target_name: str, text: str, region=None) -> bytes:
    """Payload opcode 0x02 cho C:002-003 (0 item, 0 npc dinh kem)."""
    tid = (target_id or b"")[:8].ljust(8, b"\x00")
    return b"\x03\x00" + tid + _l_str(target_name, region) + _l_str(text, region) + b"\x00\x00"


# ---- HAN OFF (luu file: tat/mo tool giua chung van cho du gio) ----
_lock = threading.Lock()


def _state_path():
    try:
        from ._appdir import app_dir
        return os.path.join(app_dir(), "remote_off.json")
    except Exception:
        return "remote_off.json"


def _load():
    try:
        with open(_state_path(), encoding="utf-8") as fh:
            d = json.load(fh)
        return {str(k): float(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d):
    now = time.time()
    d = {k: v for k, v in d.items() if v > now}
    try:
        with open(_state_path(), "w", encoding="utf-8") as fh:
            json.dump(d, fh)
    except Exception:
        pass


def set_off(usernames, until_ts):
    with _lock:
        d = _load()
        for u in usernames:
            d[u] = float(until_ts)
        _save(d)


def clear_off(username):
    with _lock:
        d = _load()
        if d.pop(username, None) is not None:
            _save(d)


def off_remaining(username):
    """So giay con phai off (0 = khong off)."""
    with _lock:
        return max(0.0, _load().get(username, 0.0) - time.time())


# ---- Cau noi client -> dieu phoi (run_party_digioi dang ky) ----
_off_handler = None


def set_off_handler(fn):
    """fn(client, sender_name, sender_id, minutes) - chay tren THREAD RIENG, khong chan recv."""
    global _off_handler
    _off_handler = fn


def request_off(client, sender_name, sender_id, minutes):
    fn = _off_handler
    if fn is None:
        return False
    threading.Thread(target=fn, args=(client, sender_name, sender_id, minutes),
                     daemon=True, name="remote-off").start()
    return True
