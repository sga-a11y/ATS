"""Cac BAN TS Online (region): moi thu KHAC NHAU giua cac ban gom het vao day.

Cac ban dung CHUNG client Unity + Lua (so sanh VTC vs TSM 29/09/2026: 814/928 file Lua/Data giong
tung byte, protocal.lua chi lech 1 goi C:001-052). Khac nhau o: login, server, key XOR, encoding
chuoi, mui gio server, tinh nang da mo. Xem documents/MULTI_REGION.md.

Moi Client giu `self.region` rieng -> 1 bot chay duoc acc cua nhieu ban cung luc.
Ham nao khong nhan region thi dung ban mac dinh (DEFAULT).
"""
from __future__ import annotations

import datetime

DEFAULT = "vtc"

REGIONS = {
    "vtc": {
        "name": "TS Online VN (VTC)",
        "package": "com.vtcmobile.gz06",
        "login": "mobiplay",          # HTTP graph.mobiplay.vn -> access_token -> goi auth 0x01
        "xor_key": 0xAD,
        "encoding": "utf-16-le",      # ByteBuffer.lua: DataManager.encoding_Unicode
        "utc_offset": 7,              # gio server = UTC+7
        "cdn": "https://cdn-gz06.mobigame.vn/tsr/",   # ServerList.dat (bot/servers_cdn.py)
    },
    "tsm": {
        # Capture login 29/09 (captures/tsm_login_20260929.pcap): server 34.81.22.35:6614, serverId=21.
        # C:001-000 +ver(2)=0x0102 +serverId(2) +connectCode(4)=0 +kind(1)=1 (ELogin.AccPwd)
        #           +L(1)+acc +L(1)+pwd. Heartbeat client 20s.
        "name": "TS Online Mobile (Dai Loan, MyCard)",
        "package": "mycard.chinesegamer.tsm",
        "login": "accpwd",
        "xor_key": 0xAD,              # giong VTC (capture: 6d3c = c091 ^ adad)
        "encoding": "big5",           # ByteBuffer.lua: DataManager.encoding_Big5
        "utc_offset": 8,
        # Tu global-metadata.dat cua APK TSM; ServerList.dat cung dinh dang VTC (30/09: 21 server).
        "cdn": "https://tsrtwftp.chinesegamer.net/tsr/",
    },
}


class Region:
    def __init__(self, rid: str):
        d = REGIONS[rid]
        self.id = rid
        self.name = d["name"]
        self.package = d["package"]
        self.login = d["login"]
        self.xor_key = d["xor_key"]
        self.encoding = d["encoding"]
        self.utc_offset = d["utc_offset"]
        self.cdn = d.get("cdn")
        # Do dai chuoi phai CHIA HET cho so nay. UTF-16 = 2; Big5 = 1 (chu ASCII 1 byte ->
        # ten "stmot" dai 5 - check `% 2` cu lam TSM khong doc duoc ten char).
        self.char_bytes = 2 if self.encoding.startswith("utf-16") else 1

    def encode_str(self, s: str) -> bytes:
        return str(s).encode(self.encoding)

    def decode_str(self, b: bytes, errors: str = "strict") -> str:
        return bytes(b).decode(self.encoding, errors)

    def server_now(self) -> datetime.datetime:
        """Gio SERVER hien tai (naive), khong phu thuoc mui gio cua may chay bot."""
        utc = datetime.datetime.now(datetime.timezone.utc)
        return (utc + datetime.timedelta(hours=self.utc_offset)).replace(tzinfo=None)

    def server_ts(self, ts: float) -> datetime.datetime:
        """Doi epoch -> gio server (thay cho time.localtime khi hien gio cho user)."""
        utc = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
        return (utc + datetime.timedelta(hours=self.utc_offset)).replace(tzinfo=None)

    def __repr__(self):
        return "Region(%s)" % self.id


_cache = {}


def get(rid: str | None = None) -> Region:
    rid = rid or DEFAULT
    r = _cache.get(rid)
    if r is None:
        r = _cache[rid] = Region(rid)
    return r


def co_trong_game(entry, game: str | None) -> bool:
    """Entry du lieu (event trong events.json...) co o ban `game` khong.

    Entry khai `"games": ["vtc", "tsm"]`; khong khai = chi VTC (du lieu cu deu boc tu ban VTC).
    Event moi ban KHAC NHAU (lich, map, NPC, qua) -> khong duoc dem event VTC chay tren TSM.
    """
    return (game or DEFAULT) in ((entry or {}).get("games") or [DEFAULT])


def chan_event_sai_game(pc: dict, events: dict) -> None:
    """Party mode 'event' ma event KHONG co o ban cua party -> ve 'stand' + log.

    Goi luc dung PARTY_CONFIG (config.py PC + APK). Chay tiep = tele toi map/NPC cua ban khac,
    dung im hoac bi kick. Dung yen + bao ro de user chon lai event.
    """
    if pc.get("mode") != "event":
        return
    key = pc.get("event_key") or ""
    if co_trong_game((events or {}).get(key), pc.get("game")):
        return
    import logging
    logging.getLogger("bot").warning(
        "Event '%s' KHONG co o ban %s -> party dung yen (chon lai event trong GUI)",
        key, pc.get("game") or DEFAULT)
    pc["mode"] = "stand"


def encode_str(s: str, region: Region | None = None) -> bytes:
    return (region or get()).encode_str(s)


def decode_str(b: bytes, errors: str = "strict", region: Region | None = None) -> str:
    return (region or get()).decode_str(b, errors)


def server_now(region: Region | None = None) -> datetime.datetime:
    return (region or get()).server_now()
