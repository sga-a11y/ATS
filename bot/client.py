"""TCP client TS Online: ket noi, auth, heartbeat, recv loop, dispatch + combat."""
import socket
import struct
import threading
import time
import logging
import collections

from . import config, protocol, combat


from .auth import build_auth_packet
from .state import BattleState

log = logging.getLogger("bot")

# Registry entity cac bot cung party (chia se trong process). party_idx -> set(entity bytes).
# Bot dang ky self_entity luc login -> khi nhan loi moi, accept neu nguoi moi cung party.
_PARTY_ENTITIES = {}
_PARTY_LOCK = threading.Lock()

def _register_party_entity(party_idx, entity):
    if party_idx is None or not entity:
        return
    with _PARTY_LOCK:
        _PARTY_ENTITIES.setdefault(party_idx, set()).add(bytes(entity))

def _is_party_member(party_idx, entity):
    if party_idx is None:
        return False
    with _PARTY_LOCK:
        return bytes(entity) in _PARTY_ENTITIES.get(party_idx, set())

# Member da ACCEPT loi moi tu party-mate (tin hieu chia se de LEADER biet party da thanh).
# party_idx -> set(self_entity cua cac member da join). Tin cay hon doc roster broadcast.
_PARTY_JOINED = {}

def _mark_joined(party_idx, entity):
    if party_idx is None or not entity:
        return
    with _PARTY_LOCK:
        _PARTY_JOINED.setdefault(party_idx, set()).add(bytes(entity))

def joined_member_count(party_idx):
    with _PARTY_LOCK:
        return len(_PARTY_JOINED.get(party_idx, set()))

def reset_party_joined(party_idx):
    """Xoa danh sach member da join (khi leader GIAI TAN party de relogin) -> leader tinh lai tu
    dau, vong retry 60s se MOI LAI cho du member. Member se _mark_joined lai khi accept loi moi moi."""
    if party_idx is None:
        return
    with _PARTY_LOCK:
        _PARTY_JOINED.pop(party_idx, None)

def is_joined(party_idx, entity):
    """Member nay da accept vao party chua (self_entity co trong _PARTY_JOINED)."""
    if party_idx is None or not entity:
        return False
    with _PARTY_LOCK:
        return bytes(entity) in _PARTY_JOINED.get(party_idx, set())

# party_idx -> entity QUAN SU (leader da set). Chia se de GUI hien vai tro "quan su".
_PARTY_STRATEGIST = {}

def strategist_of(party_idx):
    with _PARTY_LOCK:
        return _PARTY_STRATEGIST.get(party_idx)

def is_strategist(party_idx, entity):
    if party_idx is None or not entity:
        return False
    with _PARTY_LOCK:
        return _PARTY_STRATEGIST.get(party_idx) == bytes(entity)

# Chi so INT (tri luc) tung char trong party (chia se de leader chon quan su INT cao nhat).
# party_idx -> {entity: int_value}.  STAT_INT = id 0x1b (xac nhan tu int.pcap).
STAT_INT = 0x1b
_PARTY_INT = {}

def _register_party_int(party_idx, entity, value):
    if party_idx is None or not entity:
        return
    with _PARTY_LOCK:
        _PARTY_INT.setdefault(party_idx, {})[bytes(entity)] = value

# entity(bytes) -> ten nhan vat (chia se giua cac thread acc trong process). Moi acc tu dang ky
# entity+ten cua chinh no -> leader tra cuu ten member khi log (set quan su, moi...).
_PARTY_NAMES = {}

def _register_party_name(entity, name):
    if not entity or not name:
        return
    with _PARTY_LOCK:
        _PARTY_NAMES[bytes(entity)] = name

def name_for_entity(entity):
    """Ten nhan vat theo entity (khop 8B day du HOAC 4B prefix). None neu chua biet."""
    if not entity:
        return None
    eb = bytes(entity)
    with _PARTY_LOCK:
        if eb in _PARTY_NAMES:
            return _PARTY_NAMES[eb]
        for k, v in _PARTY_NAMES.items():   # khop prefix 4B (entity party luu dang rut gon)
            if k[:4] == eb[:4]:
                return v
    return None

def best_int_member(party_idx, candidates):
    """Tra entity co INT cao nhat trong 'candidates' (list entity). None neu khong biet INT."""
    with _PARTY_LOCK:
        ints = _PARTY_INT.get(party_idx, {})
    known = [(e, ints[e]) for e in candidates if e in ints]
    if not known:
        return None
    return max(known, key=lambda x: x[1])[0]


def check_duplicate_accounts(parties):
    """Kiem tra 1 username dien o NHIEU noi trong config.PARTIES -> raise ValueError de bao loi
    ngay luc khoi dong (con biet duong sua config)."""
    seen = {}          # username -> (party_idx, slot_idx)
    dups = []
    for pi, party in enumerate(parties or []):
        for si, acc in enumerate(party or []):
            if not (acc and acc[0] and acc[0].strip()):
                continue
            u = acc[0].strip()
            if u in seen:
                dups.append((u, seen[u], (pi, si)))
            else:
                seen[u] = (pi, si)
    if dups:
        # CHI canh bao (khong chan) - van cho chay. Acc trung se bi login 2 lan -> co the bi
        # da/disconnect, nen tot nhat van nen sua, nhung khong block GUI khoi dong.
        lines = [f"  - '{u}' dien o party{a[0]} slot{a[1]} VA party{b[0]} slot{b[1]}"
                 for u, a, b in dups]
        log.warning("CONFIG: co user dien TRUNG o nhieu noi (van cho chay):\n" + "\n".join(lines))


# Khung gio nhan mail (gio bat dau, moi khung 2h): 12-14, 16-18, 22-24.
MAIL_WINDOWS = [12, 16, 22]


def mail_window_now():
    """Tra ve gio bat dau cua khung mail hien tai (12/16/22), hoac None neu ngoai khung."""
    import datetime
    h = datetime.datetime.now().hour
    for ws in MAIL_WINDOWS:
        if ws <= h < ws + 2:
            return ws
    return None


_GIFT_FILE = "gift_state.json"
_gift_lock = threading.Lock()

# ITEM HP/SP: bot TU HOC qua self-calibrate (probe -> doc delta HP/SP tu S2C 0x08),
# luu items_learned.json. KHONG can gamedata/config. Format:
#   { "<tid>": {"hp": <heal HP do duoc>, "sp": <heal SP>, "name": "", "none": false} }
#   none=true -> da thu, item KHONG hoi HP/SP (vat pham khac) -> khoi probe lai.
# tid consumable da xac dinh tu phan tich capture = DIEM XUAT PHAT danh sach probe
# (heal van DO LIVE, khong gan cung). Bot tu mo rong qua owned_items (S2C 0x16 inventory).
_KNOWN_CONSUMABLES = [0x0116, 0x0117, 0x011b, 0x011c, 0x0139]

def _learned_file_path():
    """Duong dan TUYET DOI items_learned.json (canh root project/.exe) -> KHONG le thuoc CWD."""
    try:
        from ._appdir import app_dir
        import os
        return os.path.join(app_dir(), "items_learned.json")
    except Exception:
        return "items_learned.json"

_LEARNED_FILE = _learned_file_path()
_learned_lock = threading.Lock()
# CACHE RIENG TUNG ACC: { username: { tid: {hp,sp,hp_zero,sp_zero,none} } }. Item availability +
# luong heal KHAC NHAU moi acc (stack rieng, heal scale theo level) -> KHONG dung chung duoc.
_all_learned = None

def _load_all_learned() -> dict:
    """{ tid_str: {hp,sp,hp_zero,sp_zero,none,unusable} }. CHUNG mọi acc (key = tid template)."""
    global _all_learned
    if _all_learned is not None:
        return _all_learned
    import json as _json
    try:
        with open(_LEARNED_FILE, encoding="utf-8") as fh:
            d = _json.load(fh)
        # chi nhan format phang tid->dict (gia tri la dict co 'hp'/'sp'); khac -> bo, lam lai
        _all_learned = d if isinstance(d, dict) and all(
            isinstance(v, dict) and ("hp" in v or "sp" in v or "unusable" in v) for v in d.values()) else {}
    except Exception:
        _all_learned = {}
    # MOI PHIEN: bo 'unusable'/'strikes' -> re-verify lai (item bi tu choi = server reject = KHONG mat
    # item -> probe lai mien phi). Tranh mark oan luc loan (relogin/lag) khoa vinh vien. Giu hp/sp/none.
    for v in _all_learned.values():
        v.pop("unusable", None)
        v.pop("strikes", None)
    return _all_learned

def _save_all_learned():
    import json as _json
    with _learned_lock:
        try:
            d = _all_learned or {}
            # SAP XEP: item HOI (hp/sp>0) len dau (heal lon truoc), roi den item khac (none...).
            ordered = dict(sorted(d.items(),
                                  key=lambda kv: -(kv[1].get("hp", 0) + kv[1].get("sp", 0))))
            with open(_LEARNED_FILE, "w", encoding="utf-8") as fh:
                _json.dump(ordered, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("save items_learned.json fail: %s", e)

# ITEM DA XAC NHAN 100% (items_known.json): { tid: {name,hp,sp} }. Bot KHONG bao gio tu sua/probe/khoa
# nhung tid nay -> tin tuyet doi (vd cac item da capture). Locked > auto-learn.
_known_items = None
def _load_known_items() -> dict:
    """{ tid_int: {name,hp,sp} } tu items_known.json (canh root). Khoa cung, auto-learn ko dung den."""
    global _known_items
    if _known_items is not None:
        return _known_items
    import json as _json, os as _os
    _known_items = {}
    try:
        from ._appdir import app_dir
        path = _os.path.join(app_dir(), "items_known.json")
    except Exception:
        path = "items_known.json"
    try:
        with open(path, encoding="utf-8") as fh:
            for k, v in _json.load(fh).get("items", {}).items():
                tid = int(k, 16) if isinstance(k, str) and k.lower().startswith("0x") else int(k)
                _known_items[tid] = {"name": v.get("name", ""), "type": v.get("type", ""),
                                     "hp": int(v.get("hp", 0)), "sp": int(v.get("sp", 0))}
    except Exception:
        pass
    return _known_items

# TU DIEN GAMEDATA (items_gamedata.json): { item_id_hex: {name,hp,sp} } - tu crack gamedata_Item.dat.
# Bot tra item_id -> biet loai+heal NGAY, KHONG can probe. items_known.json (m khai) uu tien hon.
_gamedata_items = None
def _load_gamedata_items() -> dict:
    """{ item_id_int: {name,hp,sp} } tu items_gamedata.json (622 thuoc HP/SP, crack tu gamedata)."""
    global _gamedata_items
    if _gamedata_items is not None:
        return _gamedata_items
    import json as _json, os as _os
    _gamedata_items = {}
    try:
        from ._appdir import app_dir
        path = _os.path.join(app_dir(), "items_gamedata.json")
    except Exception:
        path = "items_gamedata.json"
    try:
        with open(path, encoding="utf-8") as fh:
            for k, v in _json.load(fh).items():
                iid = int(k, 16) if isinstance(k, str) and k.lower().startswith("0x") else int(k)
                _gamedata_items[iid] = {"name": v.get("name", ""), "battle": bool(v.get("battle")),
                                        "hp": int(v.get("hp", 0)), "sp": int(v.get("sp", 0))}
    except Exception:
        pass
    return _gamedata_items




def _gift_key(label: str) -> str:
    import datetime
    return f"{label}:{datetime.date.today().isoformat()}"


def _load_gift_state(label: str) -> dict:
    """Load state qua online HOM NAY: {'online_sec': float, 'claimed': set}."""
    import json, os
    default = {"online_sec": 0.0, "claimed": set()}
    if not os.path.exists(_GIFT_FILE):
        return default
    try:
        with open(_GIFT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        rec = data.get(_gift_key(label))
        if not rec:
            return default
        return {"online_sec": float(rec.get("online_sec", 0)),
                "claimed": set(rec.get("claimed", []))}
    except Exception:
        return default


def _save_gift_state(label: str, online_sec: float, claimed: set):
    """Luu online_sec + claimed cho hom nay; don key ngay cu."""
    import json, os, datetime
    today = datetime.date.today().isoformat()
    with _gift_lock:
        data = {}
        if os.path.exists(_GIFT_FILE):
            try:
                with open(_GIFT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data = {k: v for k, v in data.items() if k.endswith(today)}
        data[_gift_key(label)] = {"online_sec": round(online_sec, 1),
                                  "claimed": sorted(claimed)}
        try:
            with open(_GIFT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass


# ---- State DIEM DANH (so lan da diem danh) ----
_CHECKIN_FILE = "checkin_state.json"

def _load_checkin(label: str, kind: str = "checkin") -> dict:
    """{'date': 'YYYY-MM-DD', 'day': N} - lan nhan gan nhat (kind: checkin / gift14 / ...)."""
    import json, os
    if not os.path.exists(_CHECKIN_FILE):
        return {"date": "", "day": 0}
    try:
        with open(_CHECKIN_FILE, encoding="utf-8") as f:
            return json.load(f).get(f"{label}:{kind}", {"date": "", "day": 0})
    except Exception:
        return {"date": "", "day": 0}

def _save_checkin(label: str, kind: str, date: str, day: int):
    import json, os
    with _gift_lock:
        data = {}
        if os.path.exists(_CHECKIN_FILE):
            try:
                with open(_CHECKIN_FILE, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[f"{label}:{kind}"] = {"date": date, "day": day}
        try:
            with open(_CHECKIN_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass


# ---- Tracker viec lam HANG NGAY 1 lan (vd qua quan doan): {label:task -> date} ----
_DAILY_FILE = "daily_state.json"

def _daily_done(label: str, task: str) -> bool:
    import json, os, datetime
    if not os.path.exists(_DAILY_FILE):
        return False
    try:
        with open(_DAILY_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d.get(f"{label}:{task}") == datetime.date.today().isoformat()
    except Exception:
        return False

def _mark_daily(label: str, task: str):
    import json, os, datetime
    today = datetime.date.today().isoformat()
    with _gift_lock:
        d = {}
        if os.path.exists(_DAILY_FILE):
            try:
                with open(_DAILY_FILE, encoding="utf-8") as f:
                    d = json.load(f)
            except Exception:
                d = {}
        d = {k: v for k, v in d.items() if v == today}   # don key ngay cu
        d[f"{label}:{task}"] = today
        try:
            with open(_DAILY_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f)
        except Exception:
            pass


# ---- State VAN TIEU: chi luu SO LUOT da gui hom nay (claim doc theo gio server tu panel) ----
_VANTIEU_FILE = "vantieu_state.json"

def _vantieu_count(label: str) -> int:
    """So luot van tieu DA gui hom nay (local fallback; ngay moi -> 0)."""
    import json, os, datetime
    today = datetime.date.today().isoformat()
    if not os.path.exists(_VANTIEU_FILE):
        return 0
    try:
        with open(_VANTIEU_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return 0
    ent = d.get(label)
    return ent.get("count", 0) if (ent and ent.get("date") == today) else 0

def _vantieu_set_count(label: str, count: int):
    import json, os, datetime
    today = datetime.date.today().isoformat()
    with _gift_lock:
        d = {}
        if os.path.exists(_VANTIEU_FILE):
            try:
                with open(_VANTIEU_FILE, encoding="utf-8") as f:
                    d = json.load(f)
            except Exception:
                d = {}
        d = {k: v for k, v in d.items() if v.get("date") == today}   # don ngay cu
        d[label] = {"date": today, "count": count}
        try:
            with open(_VANTIEU_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f)
        except Exception:
            pass


class GameClient:
    def __init__(self, user_id: str, access_token: str, host: str = None, server_id: int = 1):
        self.user_id = user_id
        self.access_token = access_token
        self.host = host or config.GAME_HOST   # IP server (theo party); None -> mac dinh
        self.server_id = server_id             # ID server trong goi auth (1=Trieu Van, 2=Tao Thao)
        self.sock = None
        self.recv_buf = b""
        self._recent_sends = collections.deque(maxlen=40)  # (op, hex) - dump khi bi kick de debug
        self._recent_recvs = collections.deque(maxlen=40)  # (ts, op, hex) goi server gui - debug kick
        self.running = False
        self.state = BattleState()

        # combat turn handling
        self.available = {}          # unit -> list (atype, target)
        self._acted_turn = False
        self._decision_timer = None
        self.auto_combat = True
        self.auto_accept_party = True
        self.self_entity = None      # entity 8 byte cua nhan vat minh
        self.last_turn_time = 0.0    # thoi diem nhan luot/battle gan nhat
        self._label = ""             # nhan log: username luc dau, doi sang TEN NHAN VAT khi biet
        self._username = ""          # username login (key tra cuu config rieng tung acc)
        self._heal_giveup = {}       # target(0 char/1 pet) -> thoi diem het tam nghi hoi mau (con ket/da day)
        self._username = ""          # username login (giu lai de tham chieu)
        self.char_name = None        # ten nhan vat trong game (tu 0x27 theo self_entity)
        self.char_int = None         # chi so INT (tri luc) - tu S2C 0x08 id=0x1b
        self.char_level = None       # cap nhan vat - tu S2C 0x05 (payload offset 21 = pkt[28])
        self.pet_level = None        # cap pet dang dung - tu S2C 0x0f sub=08
        self.pet_name = None         # ten pet dang dung - tu S2C 0x0f sub=08
        self._cached_pet_list_pkt = None  # cache 0x0f de re-process khi 0x13 den sau
        self._gift_status = {}        # gtype -> status phan hoi (S2C 0x57: 01 diem danh, 04 qua 14 ngay)
        self._last_guild_pkt = None   # cache goi 0x27 (guild) de resolve ten neu toi truoc 0x69
        self.flee_mode = False        # True = dang di chuyen -> vao battle thi BO CHAY (khong danh)
        self.dungeon_complete = False  # True khi nhan goi hoan thanh dungeon (S2C 0x14 sub 0x64)
        self.submit_delay = 0.5      # delay truoc khi gui combat
        self._first_turn = True      # luot dau tran -> atype=2, sau -> atype=3
        self._battle_entered = False # da gui 0x41 "vao tran" chua
        self.channels = {}           # {so_kenh: (so_nguoi, suc_chua)} - tu S2C 0x07 list
        self._chan_event = threading.Event()
        self.server_closed = False   # True khi server CHU DONG dong ket noi (rot/bao tri/kick)
        self._phoban_until = 0.0     # < time.time() = dang vao pho ban (theo+danh, khong teleport ve)
        self._gate_transit = False   # True khi dang gui chuoi 0x14 qua cong -> combat KHONG gui 0x32
        self.current_map = None      # map_id hien tai (doc tu broadcast 0x0c/0x07/0x03)
        self._pending_0b = []        # buffer 0x0b den TRUOC khi co self_entity (race login)
        self._pending_03 = None      # cache 0x03 self-spawn (resolve ten neu toi TRUOC 0x69)
        self.party_leader = None     # entity chu party (tu 0x0d sub=06)
        self.party_members = []      # list entity cac member theo thu tu (= slot B2)
        self.party_idx = None        # chi so party cua bot (tu config.ACCOUNT_PARTY) - de nhan moi cung party
        self.entity_names = {}       # entity(bytes) -> set(str) - TAT CA strings tim duoc tu 0x27
        self._running_route = False   # dang chay auto run-around
        self.pos = None              # vi tri hien tai (x,y) cua minh - doc tu S2C 0x06 self
        self.digioi_minutes = 0      # so phut DI GIOI hom nay (tu S2C 0x55 id=0x1b)
        self._last_digioi_ts = 0.0   # thoi diem nhan timer 0x1b gan nhat (0 = chua bao gio)
        self.dungeon_runs_today = None  # so luot dungeon da danh hom nay (S2C 0x55 stat 0x9b)
        self.xu = None               # so XU hien co (tu S2C 0x1a id=4) - None = chua nhan
        self._decompose_seq = 0      # tang moi khi nhan S2C 0x59 (xac nhan phan giai 1 cuon xong)
        self.bag_counts = {}         # tid (int) -> tong so luong (gom moi slot) - cho decompose/owns
        self.bag_slots = {}          # slot (int) -> [tid, count]  (S2C 0x16 sub0400). Use item = gui slot.
        self._pending_confirm_slot = None  # slot dang cho S2C 0x17 sub09 xac nhan (probe confirm-gated)
        self._use_confirmed = False        # True khi nhan confirm cho _pending_confirm_slot
        self._no_item = set()        # (target,kind) het thuoc -> skip toi TRAN SAU (reset khi 0x34)
        self._quest_cells = set()    # o nhiem vu hang ngay DA HOAN THANH (S2C 0x5b 02 00 01 01 00 [cell])
        self.friend_entities = []    # entity 8B cua ban be (S2C 0x0e 05 push luc login)
        self.friend_status = {}      # entity hex -> trailer[18]: bit0x01=DA TANG, bit0x02=CO QUA nhan
        self._gift_recv = 0          # dem qua ban tang da nhan (S2C 0x0e 0d xac nhan nhan 1 qua)
        self.vantieu_started = None  # so luot van tieu DA gui hom nay (S2C 0x55 sid=0x08)
        self.vantieu_max = 3         # gioi han van tieu/ngay (server bao kem, mac dinh 3)
        self.vantieu_slots = {}      # slot -> {"end": OLE date ket thuc, "pet": id} (tu panel 0x56 0300)
        self.vantieu_req_code = None # ma yeu cau slot ke tiep (0x56 0400, hex b0b1b2) - tra VANTIEU_REQUESTS
        self.vantieu_roster = {}     # index pet KHO (1-based) -> ten (S2C 0x1f 0600 luc login) -> tra PET_HEDOANH
        self.vantieu_unlocked = 1    # so slot DA MO (S2C 0x56 0600 [N]); slot con lai khoa = can vang
        self._dg_query = None        # raw S2C 0x54 (tra loi query luot dungeon)
        self._dg_query_event = threading.Event()
        self._connect_time = None    # thoi diem connect phien nay
        self._online_base = 0.0      # giay online TICH LUY hom nay (load tu file, truoc phien nay)
        self.claimed_gifts = set()   # cac moc qua online da nhan hom nay (load tu file)
        self._mail_ids = []          # mail_id thu thap tu S2C 0x53 (de nhan + xoa)
        self._event14_items = []     # itemid event "qua 14 ngay" tu S2C 0x7c sub=01 (de nhan)
        self._event14_ok = 0         # so phan nhan THANH CONG (S2C 0x7c sub=02 byte ok=01)
        self._event14_acks = []      # raw ack S2C 0x7c sub=02 (debug)
        self._event14_bagfull = False  # True neu server tra code 06 (tui day)

    # ---- ket noi + auth ----
    def connect(self):
        self.state.label = self._label
        self._connect_time = time.time()
        st = _load_gift_state(self._label)
        self._online_base = st["online_sec"]   # online tich luy truoc phien nay (hom nay)
        self.claimed_gifts = st["claimed"]
        self.sock = socket.create_connection((self.host, config.GAME_PORT), timeout=15)
        log.info("Da ket noi %s:%s", self.host, config.GAME_PORT)
        self.sock.sendall(build_auth_packet(self.user_id, self.access_token, self.server_id))
        log.info("Da gui auth (user_id=%s, server_id=%s)", self.user_id, self.server_id)
        self.running = True
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        self._login_setup()   # chuoi setup sau auth -> char thanh combat-active (quai moi aggro)

    def _login_setup(self):
        """Chuoi C2S client THAT gui NGAY sau auth (capture login.pcap). Thieu chuoi nay ->
        char ket noi nhung KHONG combat-active -> quai tren map thuong NGO LO bot (khong aggro).
        Quan trong nhat la 0x41 'dang ky san sang battle'. (DG van danh duoc du thieu, nhung map
        thuong thi BAT BUOC.)"""
        seq = [(0x19, "2900f0"), (0x2b, "0400"), (0x01, "1000"), (0x7c, "0400"),
               (0x41, "0200"), (0x0c, "0100"), (0x57, "0300"), (0x01, "1000"),
               (0x62, "020001000000"), (0x41, "01003235010100000101000000")]
        for op, pl in seq:
            try:
                self.send(op, bytes.fromhex(pl))
            except OSError:
                return
            time.sleep(0.2)

    def combat_ready(self):
        """Sau khi DOI KENH / lap party, char co the mat combat-active -> gui LAI toan bo
        chuoi setup (gom 0x41 'san sang battle') de quai aggro lai."""
        self._login_setup()

    def send(self, opcode: int, payload: bytes):
        if not self.running or self.sock is None:
            return   # da rot ket noi -> bo qua (timer combat co the fire sau khi socket dong)
        if opcode != protocol.OP_HEARTBEAT:
            log.debug("[%s] SEND op=0x%02x: %s", self._label, opcode, payload.hex())
            self._recent_sends.append((time.strftime("%H:%M:%S"), opcode, payload.hex()))
        try:
            self.sock.sendall(protocol.encode(opcode, payload))
        except OSError:
            self.running = False   # socket dong -> dung gui, dung moi vong lap

    def relogin(self):
        """Thoat game roi login lai (cung acc). Server tha DUNG CHO LOGOUT (login=logout pos)
        + gui 0x03 self-spawn -> self.pos RESYNC ve toa do THAT (het drift dead-reckoning).
        Fallback khi KET o bai (lau khong co battle): ve safe -> relogin lay lai vi tri chuan
        -> di tiep toi spot. KHONG load lai gift state (giu nguyen claim trong phien)."""
        log.info("[%s] RELOGIN: dong ket noi + login lai de resync vi tri", self._label)
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.running = False
        time.sleep(1.0)
        # reset state battle/turn (tranh ket dong cu sau relogin)
        self.available = {}
        self._acted_turn = False
        self.flee_mode = False
        self.state.in_battle = False
        self.last_turn_time = 0.0
        self.pos = None   # se duoc 0x03 self-spawn resync ngay sau login
        try:
            self.sock = socket.create_connection((self.host, config.GAME_PORT), timeout=15)
            self.sock.sendall(build_auth_packet(self.user_id, self.access_token, self.server_id))
        except OSError as e:
            log.warning("[%s] RELOGIN that bai (ket noi): %s", self._label, e)
            return False
        self.running = True
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        self._login_setup()
        # cho 0x03 self-spawn resync pos (toi da 6s)
        for _ in range(30):
            time.sleep(0.2)
            if self.pos is not None:
                break
        log.info("[%s] RELOGIN xong, pos=%s map=%s", self._label, self.pos, self.current_map)
        return True

    def close(self):
        self.running = False
        if self.sock:
            self.sock.close()

    def in_combat(self, idle_secs: float = 4.0) -> bool:
        """Dang trong tran neu vua nhan luot/battle trong vong idle_secs giay."""
        busy = (time.time() - self.last_turn_time) < idle_secs
        if not busy:
            self.state.in_battle = False
        # KHONG reset _battle_entered/_first_turn: client THAT gui 0x41 + atype=2
        # chi 1 LAN/phien (join he thong battle), 6 tran sau van atype=3, khong gui lai 0x41
        return busy

    # ---- heartbeat ----
    def _heartbeat_loop(self):
        while self.running:
            time.sleep(15)
            try:
                self.send(protocol.OP_HEARTBEAT, b"\x00\x00")
            except OSError:
                break

    # ---- recv ----
    def _recv_loop(self):
        while self.running:
            try:
                data = self.sock.recv(8192)
            except OSError:
                self.running = False   # rot ket noi -> dung MOI vong lap (tranh loop mai tren socket chet)
                break
            if not data:
                log.warning("[%s] Server dong ket noi", self._label or self._username)
                # DUMP 12 goi gui + 12 goi NHAN gan nhat -> tim goi gay kick
                for ts, op, hx in list(self._recent_sends)[-12:]:
                    log.warning("[%s]   gui-cuoi %s 0x%02x %s", self._label, ts, op, hx)
                for ts, op, hx in list(self._recent_recvs)[-12:]:
                    log.warning("[%s]   nhan-cuoi %s 0x%02x %s", self._label, ts, op, hx)
                self.server_closed = True   # server CHU DONG dong (rot/bao tri/kick) - khong phai STOP
                self.running = False   # rot ket noi -> dung MOI vong lap
                break
            self.recv_buf += protocol.xor(data)
            pkts, consumed = protocol.parse_stream(self.recv_buf)
            self.recv_buf = self.recv_buf[consumed:]
            for opcode, pkt in pkts:
                self._recent_recvs.append((time.strftime("%H:%M:%S"), opcode, pkt.hex()[:60]))
                try:
                    self._dispatch(opcode, pkt)
                except Exception as e:
                    # 1 goi loi KHONG duoc lam chet recv thread / nuot cac goi sau trong batch
                    # (vd response 0x57 nhan qua) -> bat rieng tung goi.
                    log.warning("[%s] Loi xu ly goi 0x%02x (bo qua): %s", self._label, opcode, e)

    def _dispatch(self, opcode: int, pkt: bytes):
        log.debug("[%s] RECV op=0x%02x len=%d %s", self._label, opcode, len(pkt), pkt.hex())
        # Hoan thanh dungeon: S2C 0x14 sub 0x64 (man tong ket) -> set co de do_daily_dungeon biet xong
        if opcode == 0x14 and len(pkt) >= 8 and pkt[7] == 0x64:
            self.dungeon_complete = True
        # Phan giai cuon pet: S2C 0x59 = ket qua phan giai 1 cuon (nhan xu). Tang seq de
        # decompose_junk_scrolls biet cuon vua gui da phan giai THANH CONG (con cuon -> gui tiep).
        if opcode == 0x59:
            self._decompose_seq += 1
        # INT (tri luc): gui luc login trong gói char-info S2C 0x05 (payload ~252B), INT o payload[9]
        # = pkt[16]. (Xac nhan int2.pcap: 2 lan login INT 4->5, byte nay doi 4->5). INT cao = hoi SP
        # tot hon khi lam quan su -> leader chon member INT cao nhat. Cap nhat khi cong diem cung qua day.
        if opcode == 0x05 and len(pkt) > 200 and len(pkt) > 16:
            self.char_int = pkt[16]
            _register_party_int(self.party_idx, self.self_entity, self.char_int)
            # CAP nhan vat: payload offset 21 = pkt[28] (khop capture: char lv 64). Hien o GUI.
            if len(pkt) > 28 and 1 <= pkt[28] <= 200:
                self.char_level = pkt[28]
            # SKILL DA HOC DAY DU: 0x05 co list [count 2B LE] + count*[skill 2B LE][level 1B].
            # (0x28 chi la skill BAR, thieu skill khong dat phim tat -> char danh chay). Parse o
            # day moi du. UNION (khong ghi de) de khong mat skill tu 0x28.
            self._parse_skill_list_0x05(pkt)
        # PET dang dung: S2C 0x0f sub=0008 = danh sach pet mang theo, record DAU = pet active.
        elif opcode == 0x0f and pkt[7:9] == b"\x08\x00" and len(pkt) >= 49:
            self._cached_pet_list_pkt = pkt
            self._on_pet_list(pkt)
        # Cap nhat INT khi cong diem (S2C 0x08: 01 00 1b 01 [val 2B])
        elif opcode == 0x08 and len(pkt) >= 13 and pkt[7:9] == b"\x01\x00" and pkt[9] == STAT_INT and pkt[10] == 0x01:
            self.char_int = int.from_bytes(pkt[11:13], "little")
            _register_party_int(self.party_idx, self.self_entity, self.char_int)
        # HP/SP LIVE: S2C 0x08 sub=0100 [stat 1B][unit 1B][val 2B LE]. 0x19=HP, 0x1a=SP.
        # unit: 01=char, 02=pet (?). Ban CA NGOAI combat -> nguon HP/SP de hoi mau (0x33 chi trong tran).
        elif opcode == 0x08 and len(pkt) >= 13 and pkt[7:9] == b"\x01\x00" and pkt[9] in (0x19, 0x1a):
            stat = pkt[9]
            unit = pkt[10]
            val = int.from_bytes(pkt[11:13], "little")
            if unit == 0x01:
                tgt = self.state.char
            elif unit == 0x02:
                tgt = self.state.pet
            else:
                tgt = None
                log.info("[%s] 0x08 HP/SP unit LA = 0x%02x stat=0x%02x val=%d raw=%s",
                         self._label, unit, stat, val, pkt.hex())
            if tgt is not None:
                if stat == 0x19:
                    tgt.hp = val
                else:
                    tgt.sp = val
        # DUNG ITEM xac nhan: S2C 0x17 sub=0900 [slot 1B][01]... -> item o slot do dung THANH CONG.
        # Tru count slot, set co confirm (probe confirm-gated: co confirm = item DUNG DUOC).
        elif opcode == 0x17 and len(pkt) >= 11 and pkt[7:9] == b"\x09\x00":
            slot = pkt[9]
            if slot == self._pending_confirm_slot:
                self._use_confirmed = True
            rec = self.bag_slots.get(slot)
            if rec:
                rec[1] = max(0, rec[1] - 1)
                tid = rec[0]
                if tid in self.bag_counts:
                    self.bag_counts[tid] = max(0, self.bag_counts[tid] - 1)
        # INVENTORY (TUI THAT): S2C 0x17 sub=0500. header [00][count 2B] + record 36B:
        #   [idx 1B][item_id 2B LE][count 4B LE][29 pad]. idx = use-id (dung item gui [idx][01]).
        #   bag_slots[idx]=[item_id, count]; bag_counts[item_id]=tong. Snapshot day -> THAY THE.
        elif opcode == 0x17 and len(pkt) >= 12 and pkt[7:9] == b"\x05\x00":
            body = pkt[9:]
            n = int.from_bytes(body[1:3], "little")
            off = 3
            new_slots = {}
            for _ in range(n):
                if off + 7 > len(body):
                    break
                idx = body[off]
                item_id = int.from_bytes(body[off + 1:off + 3], "little")
                cnt = int.from_bytes(body[off + 3:off + 7], "little")
                off += 36
                if 0 < idx < 256 and item_id > 0 and 0 < cnt < 10_000_000:
                    new_slots[idx] = [item_id, cnt]
            if new_slots:
                self.bag_slots = new_slots
                self.bag_counts = {}
                for it, c in self.bag_slots.values():
                    self.bag_counts[it] = self.bag_counts.get(it, 0) + c
        # BAN BE / qua hang ngay: S2C 0x0e
        #   sub 05 = list ban luc login: [05 00][count 2B] + N*[entity 8B][namelen 1B][name][trailer 35B]
        #   sub 0c = status qua:        [0c 00][count 1B] + N*[entity 8B][status 1B] (03=co qua nhan, 07=da nhan)
        if opcode == 0x0e and len(pkt) >= 9:
            self._on_friend_gift(pkt)
        # NHIEM VU HANG NGAY (bingo 9 o): mo panel (C2S 0x5b 02 00 09...) -> server tra status tung o.
        #   02 00 01 01 00 [o] = o DA XONG (ke ca quest dem battle-50 KHI DA DU 50 -> 020001010009)
        #   02 00 03 / 02 00 04 = CHUA xong (03 = dang dem do, 04 = chua bat dau) -> BO QUA
        if opcode == 0x5b and len(pkt) >= 13 and pkt[7:12] == b"\x02\x00\x01\x01\x00":
            self._quest_cells.add(pkt[12])
        # Track map_id hien tai: 0x0c/0x07 = [00 00][entity 8B][map_id 2B]...
        # CHI doc map khi entity == CHINH MINH (tranh bi NHIEM map cua nguoi xung quanh ben
        # canh map khac -> doc nham 12842 thay vi 12831). self_entity None (luc login) -> tam lay.
        if opcode in (0x0c, 0x07) and len(pkt) >= 19 and pkt[7:9] == b"\x00\x00":
            ent = pkt[9:17]
            if self.self_entity is None or ent == self.self_entity:
                mid = int.from_bytes(pkt[17:19], "little")
                if mid > 1000:   # loc gia tri rac (map_id that >1000)
                    self.current_map = mid
        # 0x03 = goi SELF server gui khi load map: [00 00][entity 8B][... 11B][map_id 2B].
        # KHAC voi 0x0c/0x07 (broadcast nguoi xung quanh): 0x03 ve CHINH MINH -> doc duoc map
        # NGAY CA KHI DUNG MOT MINH (DG/dungeon vang nguoi). Chi doc khi entity == self.
        if opcode == 0x03 and len(pkt) >= 30 and pkt[7:9] == b"\x00\x00":
            ent = pkt[9:17]
            if self.self_entity is None or ent == self.self_entity:
                mid = int.from_bytes(pkt[28:30], "little")
                if mid > 1000:
                    self.current_map = mid
                # RESYNC vi tri THAT do server cap: 0x03 self-spawn co toa do o payload
                # offset 23/25 = pkt[30:32]/pkt[32:34] (relogin.pcap: f2 03=1010, ca 03=970).
                # Sua dead-reckoning bi lech sau khi di xa/qua cong. Login=dung cho logout.
                if len(pkt) >= 34:
                    sx = int.from_bytes(pkt[30:32], "little")
                    sy = int.from_bytes(pkt[32:34], "little")
                    if 0 < sx < 20000 and 0 < sy < 20000:
                        self.pos = (sx, sy)
                        log.info("[%s] RESYNC pos tu 0x03 = (%d,%d) map=%s",
                                 self._label, sx, sy, self.current_map)
            # TEN NHAN VAT tu 0x03 self-spawn (nguon dang tin: MOI acc co, KHONG can bang hoi).
            if self.self_entity is None:
                self._pending_03 = pkt   # chua biet self -> cache, retry khi 0x69 toi
            elif self.char_name is None and ent == self.self_entity:
                self._resolve_name_from_03(pkt)
        # (Server KHONG echo vi tri CUA MINH qua 0x06 -> dung dead-reckoning trong move_to/enter)
        if opcode == protocol.OP_STAT_UPD:        # 0x33
            self.state.update_0x33(pkt)
        elif opcode == protocol.OP_FULLSTAT:      # 0x0b
            if self.self_entity is None:
                # chua biet self_entity -> buffer lai de xu khi co (tranh mat goi stat luc login)
                self._pending_0b.append(pkt)
                if len(self._pending_0b) > 20:
                    self._pending_0b.pop(0)
            # 0x0b battle (full stat): [entity][10x00][03][SLOT] -> vi tri tran cua minh.
            # Entity-based, dang tin (khong dua HP). Cap nhat moi tran (vi tri co the doi).
            if self.self_entity and len(pkt) > 100:
                idx = pkt.find(self.self_entity)
                if idx >= 0 and idx + 19 < len(pkt) and pkt[idx + 18] == 0x03:
                    slot = pkt[idx + 19]
                    if slot < 10 and slot != self.state.self_slot:
                        self.state.self_slot = slot
                        self.state.my_atype = slot
                        log.info("[%s] self_slot=%d (tu 0x0b battle, entity)", self._label, slot)
            self.state.update_0x0b(pkt)
        elif opcode == 0x53:                      # mail: S2C sub=01 = 1 mail (push luc login)
            # payload: [01 00][mailid 4B LE][cat 4B LE][sender/time 8B][00][title UTF16...]
            if pkt[7:9] == b"\x01\x00" and len(pkt) >= 17:
                mid = pkt[9:13]    # mail_id 4B LE
                cat = pkt[13:17]   # category 4B LE (3, 5,... -> THAY DOI tung mail!)
                if (mid, cat) not in self._mail_ids:
                    self._mail_ids.append((mid, cat))
        elif opcode == 0x7c:                      # event "qua 14 ngay" (panel claim item)
            # sub 01 = list phan qua: [01 00][count 4B LE] + count*[itemid 4B LE][qty 4B LE]
            if pkt[7:9] == b"\x01\x00" and len(pkt) >= 13:
                cnt = int.from_bytes(pkt[9:13], "little")
                items = []
                for i in range(cnt):
                    off = 13 + i * 8
                    if off + 8 > len(pkt):
                        break
                    items.append(pkt[off:off + 4])   # itemid 4B LE
                if items:
                    self._event14_items = items
            # sub 02 = grant qua (nhan THANH CONG): [02 00][01000000][itemid][qty]
            elif pkt[7:9] == b"\x02\x00" and len(pkt) >= 11:
                self._event14_acks.append(pkt[7:].hex())
                if pkt[9] == 0x01:
                    self._event14_ok += 1
            # sub 03 = KET QUA claim: [03 00][01000000][code]; code 00=OK, 06=TUI DAY
            elif pkt[7:9] == b"\x03\x00" and len(pkt) >= 14:
                code = pkt[13]
                self._event14_acks.append("ket_qua_code=%d" % code)
                if code == 0x06:
                    self._event14_bagfull = True
        elif opcode == protocol.OP_ACTIONS:       # 0x35
            self._on_actions(pkt)
        elif opcode == 0x13 and len(pkt) >= 11 and pkt[7:9] in (b"\x04\x00", b"\x01\x00"):
            # pet dang dung: [04 00] luc login, [01 00] khi doi pet. id = 2B LE
            pid = int.from_bytes(pkt[9:11], "little")
            self.state.active_pet_id = pid
            if self._cached_pet_list_pkt is not None:
                self._on_pet_list(self._cached_pet_list_pkt)
            self.state.pet_skills = getattr(config, "PET_SKILLS", {}).get(pid, [])   # LIST (boss skill[0])
            known = pid in getattr(config, "PET_NAMES", {}) or pid in getattr(config, "PET_SKILLS", {})
            name = getattr(config, "PET_NAMES", {}).get(pid, "?")
            # TEN pet DANG DUNG = ten cua active_pet_id tu pets.json (TIN CAY, dung nhu log login).
            # KHONG dua vao parse ten tu 0x0f (de tim nham con dau list). 0x0f chi dung lay LEVEL.
            if name and name != "?":
                self.pet_name = name
            if known:
                log.info("[%s] Pet id=0x%x '%s' -> skills=%s",
                         self._label, pid, name, [hex(s) for s in sorted(self.state.pet_skills)])
            else:
                log.warning("[%s] PET MOI chua co trong pets.json: id=0x%x (hex='0x%x') "
                            "-> them vao pets.json {skills, name, boss_skill}",
                            self._label, pid, pid)
        elif opcode == 0x2f:                      # party PHO BAN (dungeon)
            self._on_dungeon(pkt)
        elif opcode == 0x54:                      # exp offline / query luot dungeon
            self._dg_query = pkt[7:]              # luu raw de query_dungeon_attempts doc
            self._dg_query_event.set()
            self._on_offline_exp(pkt)
        elif opcode == 0x55 and pkt[7:9] == b"\x01\x00" and len(pkt) >= 17:
            # BANG STAT: [01 00][count 4B] + count*([id 2B][val 4B][max 4B] = 10B).
            # Login gui FULL (~1500 stat); update le gui count=1. Doc digioi/dungeon/van tieu.
            body = pkt[7:]
            cnt = int.from_bytes(body[2:6], "little")
            off, n = 6, 0
            while n < cnt and off + 10 <= len(body):
                sid = int.from_bytes(body[off:off + 2], "little")
                val = int.from_bytes(body[off + 2:off + 6], "little")
                mx = int.from_bytes(body[off + 6:off + 10], "little")
                if sid == 0x1b:                   # so phut Di Gioi
                    self.digioi_minutes = val & 0xFFFF
                    self._last_digioi_ts = time.time()
                elif sid == 0x08:                 # van tieu: so luot DA gui hom nay + gioi han
                    self.vantieu_started = val
                    self.vantieu_max = mx or 3
                # KHONG doc 0x9b lam "luot dungeon": login bulk gui 0x9b=9 (KHONG khop thuc te
                # 1-2 luot) -> sai -> dungeon dem THUAN LOCAL (checkin_state.json).
                off += 10
                n += 1
        elif opcode == 0x56:                      # van tieu (escort) panel/status
            self._on_vantieu(pkt)
        elif opcode == 0x1f and pkt[7:9] == b"\x06\x00":  # list pet KHO (vận tiêu) luc login
            self._on_vantieu_roster(pkt)
        elif opcode == 0x1a and len(pkt) >= 13:   # currency: [id 2B][val 4B]
            sid = int.from_bytes(pkt[7:9], "little")
            if sid == 4:                          # id=4 -> so XU hien co
                self.xu = int.from_bytes(pkt[9:13], "little")
            # sid==2 = so xu vua bi tru (cost), bo qua
        elif opcode == 0x57:                      # qua online
            self._on_gift(pkt)
        elif opcode == 0x28:                      # skill bar char/pet
            self._on_skill_bar(pkt)
        elif opcode == 0x27:                      # player info co ten (entity + UTF-16LE name)
            self._on_player_info(pkt)
        elif opcode == 0x69:                      # chua self_entity
            if self.self_entity is None and len(pkt) >= 17:
                self.self_entity = pkt[9:17]
                self.state.self_entity = self.self_entity
                log.info("[%s] self_entity = %s", self._label, self.self_entity.hex())
                _register_party_entity(self.party_idx, self.self_entity)  # chia se cho cung party
                if self.char_int is not None:   # INT da nhan truoc 0x69 -> dang ky lai khi co entity
                    _register_party_int(self.party_idx, self.self_entity, self.char_int)
                # ten nhan vat: neu 0x27 (guild list) da toi TRUOC 0x69 -> resolve tu goi da cache
                self._resolve_self_name(self._last_guild_pkt)
                # fallback (acc KHONG bang hoi): resolve ten tu 0x03 self-spawn da cache
                if self.char_name is None and self._pending_03 is not None:
                    self._resolve_name_from_03(self._pending_03)
                # xu lai cac goi 0x0b da buffer (co the chua stat cua minh den truoc 0x69)
                for p in self._pending_0b:
                    self.state.update_0x0b(p)
                self._pending_0b = []
        elif opcode == 0x07 and pkt[7:9] == b"\x01\x00" and len(pkt) >= 16:
            # danh sach kenh (channel list): payload bat dau '01 00 [count]'
            # (phan biet voi 0x07 broadcast di chuyen bat dau '00 00 [entity]')
            self._on_channel_list(pkt)
        # DEBUG kenh: log 0x07 (tru broadcast di chuyen 00 00) de tim "kenh hien tai"
        if __import__("os").environ.get("CHANDBG") and opcode == 0x07 and pkt[7:9] != b"\x00\x00":
            log.info("[%s] CHANDBG 0x07 %s", self._label, pkt.hex())
        elif opcode == protocol.OP_PLAYER_STATE:  # 0x0d - party
            self._on_party(pkt)
        elif opcode == protocol.OP_BATTLE_START:   # 0x34 - mốc battle that (KHONG dung 0x41!)
            self.state.in_battle = True
            self._no_item.clear()        # tran moi -> co the drop them item -> cho phep check hoi lai
            self.state.reset_enemies()   # tran moi -> xoa HP quai tran cu
            self.state.allies.clear()    # tran moi -> xoa HP dong doi tran cu (tranh ket hp=0 cua
            #                              con da chet tran truoc -> 0x33 tran moi nap lai HP tuoi)
            self.state.char_spam = False  # tran moi -> reset spam (set lai neu vao tran SP day)
            self.state.pet_spam = False
            self.last_turn_time = time.time()
            # KHONG reset _first_turn: atype=2 chi cho tran DAU TIEN ca phien, sau do=3
            # (moi tran chi 1 turn; client that dung 2 cho tran dau, 3 cac tran sau)
        # 0x41 (OP_BATTLE_ENTER) KHONG dung: fire ca luc login -> false positive
        # cac opcode khac: bo qua

    def _on_pet_list(self, pkt: bytes):
        """S2C 0x0f sub=0008: danh sach pet MANG THEO. Lay con DANG XUAT CHIEN (active_pet_id),
        KHONG phai con dau list. Record: [01 marker][pet_id 2B LE][...][LEVEL @+6][...][namelen @+30][ten @+31].
        -> tim vi tri pet_id active (ngay sau marker 0x01) roi doc level/ten tai offset co dinh.
        (khop capture: Thai Van Co id=0xa051 lv 45.) active_pet_id chua biet -> dung record dau."""
        b = pkt[7:]
        if len(b) < 35 or b[2] < 1:
            return
        # Record DAI ~254+namelen byte: [marker=SO SLOT 1B][pet_id 2B LE][exp 4B][LEVEL @+7]...
        #   [namelen @+31][ten UTF16 @+32][tail 222B]. MARKER la slot (1,2,4,8,..) KHONG phai luon
        # 0x01 -> KHONG loc theo marker. WALK tung record (stride 254+namelen) -> tim con active_pet_id.
        apid = getattr(self.state, "active_pet_id", None)
        n = b[2]
        start, chosen, first = 3, None, None
        for _ in range(n):
            if start + 33 > len(b):
                break
            if first is None:
                first = start
            pid = int.from_bytes(b[start + 1:start + 3], "little")
            if apid and pid == apid:
                chosen = start
                break
            start = start + 254 + b[start + 31]
        if chosen is None:
            chosen = first   # active chua biet / khong tim thay -> con dau (fallback)
        if chosen is None or chosen + 33 > len(b):
            return
        found_active = apid is not None and int.from_bytes(b[chosen + 1:chosen + 3], "little") == apid
        lvl = b[chosen + 7]   # LEVEL cua con active (truoc day b[p+6], p=pet_id_off -> = chosen+7)
        if 1 <= lvl <= 200:
            self.pet_level = lvl
        # TEN: chi cho pet KHONG co trong pets.json (0x13 da set ten tin cay). Chi khi tim DUNG record
        # active + chua co ten -> tranh 0x0f ghi de ten dung bang ten con dau.
        if found_active and self.pet_name is None:
            nl = b[chosen + 31]
            if 0 < nl <= 40 and chosen + 32 + nl <= len(b):
                try:
                    nm = b[chosen + 32:chosen + 32 + nl].decode("utf-16-le").strip("\x00")
                    if nm:
                        self.pet_name = nm
                except Exception:
                    pass

    def _on_party(self, pkt: bytes):
        """S2C 0x0d. sub=09 = loi moi -> accept. sub=06 = roster [leader][count][members]."""
        if len(pkt) < 9:
            return
        sub = pkt[7]
        if sub == 0x09 and self.auto_accept_party and len(pkt) >= 17:
            entity = pkt[9:17]   # entity nguoi MOI (leader), KHONG set lam self_entity
            # --- Uu tien: nguoi moi la THANH VIEN CUNG PARTY (theo entity chia se) -> accept luon ---
            if _is_party_member(self.party_idx, entity):
                self.send(protocol.OP_PLAYER_STATE, b"\x08\x00\x01" + entity)
                _mark_joined(self.party_idx, self.self_entity)   # bao LEADER: minh da join
                log.info("[%s] Loi moi tu THANH VIEN CUNG PARTY -> ACCEPT (da join)", self._label)
                return
            # --- Loc theo whitelist (CHUNG + RIENG party) (nguoi ngoai/leader nguoi that) ---
            leaders = (config.leaders_for(self.party_idx)
                       if hasattr(config, "leaders_for") else getattr(config, "PARTY_LEADERS", []))
            if leaders:
                _ldlc = {l.strip().lower() for l in leaders}   # whitelist KHONG phan biet hoa/thuong
                known = self.entity_names.get(entity, set())
                if known:
                    # Biet strings cua entity nay: accept neu BAT KY string nao khop (case-insensitive)
                    if not any(s.strip().lower() in _ldlc for s in known):
                        log.info("[%s] TU CHOI loi moi tu entity=%s strings=%s (khong trong PARTY_LEADERS=%s)",
                                 self._label, entity.hex()[:12], known, leaders)
                        return
                else:
                    # Chua biet ten -> cho qua, log canh bao
                    log.info("[%s] Chua biet ten entity=%s -> CHAP NHAN (chua co 0x27)",
                             self._label, entity.hex()[:12])
            self.send(protocol.OP_PLAYER_STATE, b"\x08\x00\x01" + entity)
            log.info("[%s] Nhan loi moi party -> da gui ACCEPT", self._label)
        elif sub == 0x06 and len(pkt) >= 18:
            # roster: [sub 06][00][leader 8B][count 1B][member 8B]*count
            leader = pkt[9:17]
            count = pkt[17]
            members = []
            for i in range(count):
                off = 18 + i * 8
                if off + 8 <= len(pkt):
                    members.append(pkt[off:off + 8])
            if members:
                # CHI nhan roster CUA PARTY MINH (self la leader HOAC trong members).
                # 0x0d sub06 phat TOAN MAP -> party khac cung map cung gui roster cua ho;
                # neu khong loc se GHI DE party_members + atype bang roster party LA.
                if self.self_entity != leader and self.self_entity not in members:
                    return
                self.party_leader = leader
                self.party_members = members
                # slot cua minh = vi tri trong danh sach member (1-based) -> map B2 trong 0x33
                if self.self_entity in members:
                    idx = members.index(self.self_entity)
                    # atype = VI TRI BATTLE (0-4, leader LUON o giua=2). Member dien [1,3,0,4] theo thu tu.
                    FILL = [1, 3, 0, 4]
                    self.state.my_atype = FILL[idx] if idx < len(FILL) else idx
                    # slot stats trong 0x33 = VI TRI BATTLE (= atype), KHONG phai idx+1
                    self.state.self_slot = self.state.my_atype
                    log.info("[%s] Party roster: %d member, minh slot=atype=%d",
                             self._label, count, self.state.my_atype)
                else:
                    # minh LA LEADER -> luon o giua (atype=2)
                    self.state.my_atype = 2
                    self.state.self_slot = 2
                    log.info("[%s] Party roster: %d member, minh LA LEADER (atype=2)",
                             self._label, count)

    def _on_dungeon(self, pkt: bytes):
        """S2C 0x2f - party PHO BAN.
        sub=0x0f: loi moi [0f 00][id 4B][01 00][leader entity 8B][namelen][ten UTF-16LE]
          -> ten leader trong PARTY_LEADERS thi DONG Y: C2S 0x2f [03 00][id 4B][00]
          -> sau do tu an CHUAN BI: C2S 0x2f [0b 00]
        """
        if len(pkt) < 9:
            return
        body = pkt[7:]
        sub = int.from_bytes(body[0:2], "little")
        if sub == 0x0f and self.auto_accept_party and len(body) >= 17:
            invite_id = body[2:6]
            nl = body[16]
            name = ""
            try:
                name = body[17:17 + nl].decode("utf-16-le")
            except Exception:
                pass
            leaders = (config.leaders_for(self.party_idx)
                       if hasattr(config, "leaders_for") else getattr(config, "PARTY_LEADERS", []))
            if leaders and name:
                _ldlc = {l.strip().lower() for l in leaders}   # KHONG phan biet hoa/thuong
                if name.strip().lower() not in _ldlc:
                    log.info("[%s] TU CHOI moi pho ban tu '%s' (khong trong whitelist)",
                             self._label, name)
                    return
            # Dong y vao pho ban
            self.send(0x2f, b"\x03\x00" + invite_id + b"\x00")
            log.info("[%s] Nhan moi PHO BAN tu '%s' -> da DONG Y", self._label, name or "?")
            # Da nhan pho ban -> THEO + DANH (khong flee, khong teleport ve thanh nua trong 10p):
            # go_to_town se BAIL khi thay co (tranh xung dot 'city mode keo ve' vs 'pho ban keo vao').
            self._phoban_until = time.time() + 600
            self.flee_mode = False
            # Tu an CHUAN BI sau 2.5s (cho load scene pho ban)
            threading.Timer(2.5, self._dungeon_ready).start()

    def _dungeon_ready(self):
        if not self.running:
            return
        self.send(0x2f, b"\x0b\x00")
        log.info("[%s] Pho ban: da an CHUAN BI", self._label)

    # ---- xu ly available actions (0x35) ----
    def _on_actions(self, pkt: bytes):
        """0x35 (>=20B): liet ke cac combo [unit][atype][target] hop le cho luot nay."""
        if len(pkt) < 20:
            return  # 11-byte = confirmation, bo qua
        # 0x35 34-byte = toi luot minh -> dang trong tran
        self.state.in_battle = True
        self.last_turn_time = time.time()
        body = pkt[7:]
        # bo 2 byte dau (01 00), moi entry 5 byte: unit atype target 00 00
        i = 2
        while i + 3 <= len(body):
            unit, atype, target = body[i], body[i + 1], body[i + 2]
            if unit in (config.UNIT_CHAR, config.UNIT_PET):
                self.available.setdefault(unit, [])
                if (atype, target) not in self.available[unit]:
                    self.available[unit].append((atype, target))
            i += 5
        # KHONG lay atype tu 0x35 (no liet ke ca 5 vi tri party -> khong on dinh).
        # self_slot xac dinh qua roster (FILL) hoac khop char maxHP trong update_0x33.
        # debounce: quyet dinh 0.4s sau goi 0x35 cuoi cung
        if self.auto_combat:
            self._arm_decision()

    def _arm_decision(self):
        if self._decision_timer:
            self._decision_timer.cancel()
        self._decision_timer = threading.Timer(self.submit_delay, self._make_decisions)
        self._decision_timer.start()

    def _make_decisions(self):
        if self._acted_turn:
            return
        self.state.party_idx = self.party_idx   # sync de dieu phoi hoi sinh chéo account
        # DANG QUA CONG (gui chuoi 0x14): KHONG gui 0x32 danh -> tranh "vua qua cong vua danh"
        # (0x32 xen giua 0x14 -> server kick leader). Bo luot nay; transit doi map -> tran cu bo,
        # neu transit that bai (van map cu) -> luot sau danh binh thuong.
        if self._gate_transit:
            self.available = {}
            threading.Timer(1.0, self._reset_turn).start()
            return
        # Neu stats chua load (hp_max=0) -> doi toi da 1s cho 0x0b kip den
        if self.state.char.hp_max == 0 and self.state.pet.hp_max == 0:
            for _ in range(10):
                time.sleep(0.1)
                if self.state.char.hp_max != 0 or self.state.pet.hp_max != 0:
                    break
            else:
                log.warning("[%s] Stats chua load sau 1s -> bo qua luot", self._label)
                self.available = {}
                threading.Timer(1.5, self._reset_turn).start()
                return
        self._acted_turn = True
        try:
            char_opts = self.available.get(config.UNIT_CHAR, [])
            pet_opts = self.available.get(config.UNIT_PET, [])
            # CHI dieu khien pet neu 0x35 co option pet o DUNG vi tri cua minh (my_atype).
            # Pet o CUNG atype voi char (khac hang/unit). Khong co pet@my_atype = acc KHONG co pet
            # (trong tran nay) -> gui lenh pet se sai -> server da/disconnect.
            if self.state.my_atype not in {o[0] for o in pet_opts}:
                pet_opts = []
            # CON DA CHET (hp_max>0 va hp<=0) -> KHONG gui lenh cho no (gui lenh cho xac chet ->
            # server coi la lenh sai -> DA/disconnect). hp tu 0x33 moi luot.
            char_dead = self.state.char.hp_max > 0 and self.state.char.hp <= 0
            pet_dead = self.state.pet.hp_max > 0 and self.state.pet.hp <= 0
            ft = self._first_turn
            # FLEE MODE: bo chay thay vi danh. PHAI dung dung my_atype (vi tri cua MINH trong
            # party) - KHONG lay char_opts[0][0] (la atype cua VI TRI DAU danh sach, co the la
            # nguoi khac) -> sai atype thi server DA/KICK (Tao Thao kick luon).
            if getattr(self, "flee_mode", False):
                my_at = self.state.my_atype
                # PET flee phai CUNG atype voi CHAR. Dung option pet THO tu 0x35 (raw_pet),
                # KHONG dung pet_opts (da bi loc theo my_atype o tren) - vi my_atype co the
                # SAI/CU (vd roster khong co self -> lay tu 0x0b) -> loc nham -> bo sot pet ->
                # pet khong hanh dong -> turn khong hoan tat -> KET TRAN khong thoat duoc.
                raw_pet = self.available.get(config.UNIT_PET, [])
                pet_atypes = {o[0] for o in raw_pet}
                a = None
                if char_opts:
                    a = my_at if my_at in {o[0] for o in char_opts} else char_opts[0][0]
                    if not char_dead:   # char con song moi flee (xac chet -> khong gui)
                        self._send_combat(combat.Decision(config.UNIT_CHAR, a, a, config.SKILL_FLEE, b=3))
                # Gui pet flee CHI khi 0x35 co option pet o DUNG slot char dang flee (a) VA pet con song.
                if a is not None and a in pet_atypes and not pet_dead:
                    self._send_combat(combat.Decision(config.UNIT_PET, a, a, config.SKILL_FLEE, b=2))
                log.info("[%s] BO CHAY (flee_mode, char_at=%s pet_at=%s my_atype=%s char_opts=%s pet_opts=%s)",
                         self._label, a, (a if (a is not None and a in pet_atypes) else None),
                         my_at, sorted({o[0] for o in char_opts}), sorted(pet_atypes))
                return
            if char_opts and not char_dead:
                d = combat.decide_char(self.state, char_opts, ft)
                self._send_combat(d)
                log.info("[%s] CHAR %s | %s | skills=%s | quai@%s",
                         self._label, d, self.state.char,
                         [hex(s) for s in sorted(self.state.skills_char)],
                         self.state.enemy_slots)
            elif char_opts and char_dead:
                log.info("[%s] CHAR HP=0 (da chet) -> KHONG gui lenh attack", self._label)
            if pet_opts and not pet_dead:
                d = combat.decide_pet(self.state, pet_opts, ft)
                self._send_combat(d)
                log.info("[%s] PET  %s | %s", self._label, d, self.state.pet)
            elif pet_opts and pet_dead:
                log.info("[%s] PET HP=0 (da chet) -> KHONG gui lenh attack", self._label)
            self._first_turn = False
        finally:
            # reset cho luot sau
            self.available = {}
            threading.Timer(1.5, self._reset_turn).start()

    def _reset_turn(self):
        self._acted_turn = False

    def _send_combat(self, d: combat.Decision, tail: bytes = None):
        """0x32: 01 00 [unit][atype][b11=00][target][skill LE][tail].
        tail = 2 byte nonce; client THAT gui gia tri thay doi moi goi. TEST: random."""
        import os, random
        if tail is None:
            if os.environ.get("RAND_TAIL"):
                tail = struct.pack("<H", random.randint(1, 0xFFFF))
            else:
                tail = b"\x00\x00"
        payload = (b"\x01\x00"
                   + bytes([d.unit, d.atype, getattr(d, "b", 0), d.target])
                   + struct.pack("<H", d.skill)
                   + tail)
        self.send(protocol.OP_COMBAT, payload)

    def flee_battle(self):
        """BO CHAY khoi tran: gui 0x32 skill=0x4651 cho ca char + pet, TARGET = chinh minh
        (target = vi tri tran cua minh = atype; flee.pcap: char atype=2->target=2).
        char b=3, pet b=2 (tu flee.pcap)."""
        at = self.state.my_atype
        self._send_combat(combat.Decision(unit=config.UNIT_CHAR, atype=at, target=at, skill=config.SKILL_FLEE, b=3))
        if self.state.active_pet_id is not None:   # chi gui pet khi CO pet (theo goi 0x13 login)
            self._send_combat(combat.Decision(unit=config.UNIT_PET, atype=at, target=at, skill=config.SKILL_FLEE, b=2))
        log.info("[%s] BO CHAY khoi tran (skill %d, target=atype=%d)", self._label, config.SKILL_FLEE, at)

    # ---- qua online (0x57) ----
    def request_offline_exp(self, exp_type: int = 0x1c):
        """Hoi info exp offline (type 0x1c). Neu co exp -> tu nhan (xu ly o _on_offline_exp)."""
        self.send(0x54, b"\x01\x00" + struct.pack("<H", exp_type))

    def claim_mail(self):
        """Mail (opcode 0x53): voi MOI mail trong list -> doc + nhan qua + xoa.
        (mailid, cat) doc tu S2C 0x53 sub=01 (server push luc login), KHONG hardcode.
        Da xac nhan tu capture mail2/mail3.pcap:
          doc:   53 03 00 [mailid 4B LE][cat 4B LE]
          nhan:  53 01 00 [mailid 4B LE][cat 4B LE]   -> qua ve qua S2C 0x02/0x23
          xoa:   53 02 00 [mailid 4B LE][cat 4B LE]
        cat THAY DOI tung mail (3, 5,...) nen phai dung dung cat cua tung mail."""
        # KHONG xoa _mail_ids o dau (server push luc login TRUOC khi ham nay chay).
        mails = list(self._mail_ids)
        self._mail_ids = []                      # consume sau khi gom
        if not mails:
            return
        n = 0
        for mid, cat in mails:
            self.send(0x53, b"\x03\x00" + mid + cat)   # doc/mo mail (mark as read)
            time.sleep(0.4)
            self.send(0x53, b"\x01\x00" + mid + cat)   # nhan qua mail nay
            time.sleep(0.4)
            self.send(0x53, b"\x02\x00" + mid + cat)   # xoa mail nay
            time.sleep(0.4)
            n += 1
        log.info("[%s] Mail: da nhan qua + xoa %d mail", self._label, n)

    def _on_offline_exp(self, pkt: bytes):
        """S2C 0x54.
        sub=1: [01 00][type 2B][flag 1B][exp 4B LE] -> neu exp>0 thi gui nhan.
        sub=2: [02 00][type 2B][status 1B] -> status=1: nhan thanh cong.
        """
        if len(pkt) < 11:
            return
        body = pkt[7:]
        sub = int.from_bytes(body[0:2], "little")
        if sub == 0x01 and len(body) >= 9:
            exp_type = int.from_bytes(body[2:4], "little")
            exp = int.from_bytes(body[5:9], "little")
            if exp_type == 0x0d:
                return   # type 0x0d = VE DUNGEON (do do_daily_dungeon xu ly), KHONG phai exp offline
            if exp > 0:
                log.info("[%s] Co %d exp offline (type=0x%x) -> nhan", self._label, exp, exp_type)
                self.send(0x54, b"\x02\x00\x02" + struct.pack("<H", exp_type))
        elif sub == 0x02 and len(body) >= 5:
            status = body[4]
            if status:
                log.info("[%s] Nhan exp offline THANH CONG", self._label)

    def claim_online_gifts(self):
        """Nhan qua online GIONG client that: chi claim moc da DU GIO online.
        Thoi gian online TICH LUY hom nay = online_base (luu tu cac phien truoc) +
        uptime phien hien tai. Tich luy nay <= online time that nen khi >= moc thi qua
        CHAC CHAN da san sang (khong claim som -> khong bi nghi bot). Luu lai moi lan goi
        de reconnect khong mat tien do.
        Tra ve True neu da nhan het tat ca moc.
        """
        milestones = getattr(config, "GIFT_MILESTONES", [])
        if not milestones or self._connect_time is None:
            return False
        online_sec = self._online_base + (time.time() - self._connect_time)
        online_min = online_sec / 60.0
        for m in milestones:
            if m in self.claimed_gifts:
                continue
            if online_min >= m:
                self.send(0x57, b"\x02\x00\x03" + struct.pack("<I", m) + b"\x01")
                self.claimed_gifts.add(m)
                log.info("[%s] Nhan qua online moc %d phut (online=%.1f phut)",
                         self._label, m, online_min)
        # luu online tich luy + claimed (de reconnect tiep tuc dung)
        _save_gift_state(self._label, online_sec, self.claimed_gifts)
        return all(m in self.claimed_gifts for m in milestones)

    def _gift_claim(self, gtype: int, day: int, wait: float = 1.5) -> int:
        """Gui 1 goi nhan qua ngay 'day': C2S 0x57 02 00 [gtype] [day 4B LE] 01.
        gtype: 01=diem danh, 04=qua 14 ngay. Tra ve status (0=OK; 2=da nhan; 5=chua toi; -1 ko phan hoi)."""
        self._gift_status[gtype] = None
        self.send(0x57, b"\x02\x00" + bytes([gtype]) + struct.pack("<I", day) + b"\x01")
        t = time.time()
        while time.time() - t < wait:
            if self._gift_status.get(gtype) is not None:
                return self._gift_status[gtype]
            time.sleep(0.1)
        return -1

    def _claim_daily_gift(self, kind: str, gtype: int, max_day: int, name: str, finite: bool = False):
        """Nhan qua theo NGAY (so lan nhan: hom nay day=N -> mai N+1). 1 lan/ngay, tu dem + luu.
        finite=True (vd qua 14 ngay): nhan het max_day thi DUNG han. Status: 0=OK,2=da nhan,5=chua toi."""
        import datetime
        today = datetime.date.today().isoformat()
        st = _load_checkin(self._label, kind)
        if st.get("date") == today:
            return True
        if finite and st.get("day", 0) >= max_day:
            return True   # da nhan het (vd ngay 14) -> khong lam nua
        # 1) Biet so dem -> thu day+1 (binh thuong 1 goi la xong)
        if 0 < st.get("day", 0) < max_day:
            s1 = self._gift_claim(gtype, st["day"] + 1)
            if s1 == 0:
                _save_checkin(self._label, kind, today, st["day"] + 1)
                log.info("[%s] %s ngay %d OK", self._label, name, st["day"] + 1)
                return True
            log.info("[%s] %s ngay %d -> status=%d (0=OK,2=da nhan,5=chua toi,-1=ko phan hoi)",
                     self._label, name, st["day"] + 1, s1)
        # 2) Lan dau / desync -> quet 1..max_day
        last = st.get("day", 0)
        seen2 = False             # co thay ngay nao "da nhan" (status=2) khong
        stats = []                # status tung ngay (de chuan doan khi that bai)
        for d in range(1, max_day + 1):
            s = self._gift_claim(gtype, d)
            stats.append(s)
            if s == 0:
                _save_checkin(self._label, kind, today, d)
                log.info("[%s] %s ngay %d OK (scan)", self._label, name, d)
                return True
            if s == 2:
                last = max(last, d); seen2 = True
        # CHI danh dau "xong hom nay" khi THUC SU co ngay da nhan (status=2).
        # Neu KHONG nhan duoc + KHONG ngay nao da nhan (toan 5/-1/khac) -> KHONG luu today
        # -> lan login sau THU LAI (tranh bug: danh dau xong ma game chua nhan).
        from collections import Counter
        if seen2:
            _save_checkin(self._label, kind, today, last)
            log.info("[%s] %s: da nhan hom nay roi (ngay %d) -> luu", self._label, name, last)
        else:
            log.warning("[%s] %s: KHONG nhan duoc phan nao (status cac ngay: %s) -> KHONG danh dau, "
                        "se thu lai login sau", self._label, name, dict(Counter(stats)))
        return True

    def claim_checkin(self):
        """DIEM DANH hang ngay (0x57 type=01)."""
        return self._claim_daily_gift("checkin", 0x01, 40, "Diem danh")

    def claim_14day_gift(self):
        """QUA 14 NGAY user moi (0x57 type=04). Nhan het 14 ngay thi dung."""
        return self._claim_daily_gift("gift14", 0x04, 14, "Qua 14 ngay", finite=True)

    def claim_event_14day(self):
        """Event TANG QUA 14 NGAY (opcode 0x7c) - KHAC qua 14 ngay new-user (0x57).
        Mo list (7c 0100) -> server tra cac phan claim duoc (S2C 0x7c sub=01) ->
        nhan tung phan: 7c 03 00 [itemid 4B LE][qty=01000000]. Server tu choi phan chua
        toi ngay (vo hai). Xac nhan tu capture ev14.pcap (nhan ngay 1 = item 0x044d).
        Chay moi login: phan da nhan se khong con trong list nua."""
        self._event14_items = []
        self._event14_ok = 0
        self._event14_acks = []
        self._event14_bagfull = False
        self.send(0x7c, b"\x01\x00")          # mo/query list event
        time.sleep(1.5)                       # cho list ve
        items = list(self._event14_items)
        if not items:
            return
        for it in items:
            if not self.running or self._event14_bagfull:
                break                          # tui day -> dung luon, khoi thu tiep
            self.send(0x7c, b"\x03\x00" + it + b"\x01\x00\x00\x00")   # nhan 1 phan
            time.sleep(0.5)
        time.sleep(0.6)
        if self._event14_bagfull:
            log.warning("[%s] Event 14 ngay: KHONG nhan duoc vi TUI DO DAY (server code 06) "
                        "-> Anh don bot tui roi login lai de bot nhan.", self._label)
        else:
            log.info("[%s] Event 14 ngay: thu %d phan, nhan thanh cong %d",
                     self._label, len(items), self._event14_ok)

    def redeem_giftcode(self, code: str):
        """NHAP GIFTCODE (C2S 0x57 sub=02). Qua thuong ve qua MAIL -> tu claim_mail() nhan.
        Format: 57 [02 00][05][len 1B = so byte UTF16][code UTF16LE][01].
        Xac nhan tu capture gift.pcap (code 'TS1106')."""
        code = (code or "").strip()
        if not code:
            return False
        cb = code.encode("utf-16-le")
        if len(cb) > 255:
            log.warning("[%s] giftcode qua dai", self._label); return False
        self.send(0x57, b"\x02\x00\x05" + bytes([len(cb)]) + cb + b"\x01")
        log.info("[%s] Nhap giftcode '%s'", self._label, code)
        time.sleep(1.2)             # cho server xu ly + day qua vao mail
        self.claim_mail()           # qua giftcode ve mail -> nhan + xoa luon
        return True

    def claim_legion_gift(self):
        """Nhan qua QUAN DOAN hang ngay. C2S 0x27 [69 00] -> server tra reward (0x17).
        1 lan/ngay (daily_state.json). Khong trong quan doan thi vo hai."""
        if _daily_done(self._label, "legion"):
            return
        self.send(0x7c, b"\x04\x00")   # mo panel quan doan
        time.sleep(0.5)
        self.send(0x27, b"\x69\x00")   # nhan qua quan doan
        _mark_daily(self._label, "legion")
        log.info("[%s] Nhan qua quan doan hang ngay", self._label)

    # Thuoc cao cap KHONG dung lam nguyen lieu hop (giu lai de danh boss)
    _COMBINE_EXCLUDE = ("Hương Dũng Ma Dược", "Hương Dũng Đại Dược")

    def do_combine_item(self):
        """HOP VAT PHAM (nhiem vu bingo o 7): hop 2 do an/thuoc -> ra item random.
        KEY: goi hop dung COMPOUND_ID = 0x0100 + IDX SLOT TUI (idx = vi tri item trong tui chinh,
        chinh la cai bag_slots dung de heal). Vi the cid DONG theo phien (slot doi -> cid doi) - bot
        doc idx LIVE tu bag_slots nen luon dung. Chon 2 do an/thuoc SL it nhat (don stack le), tru
        item battle (hoi sinh) + Huong Dung. C2S 0x17: 0e 00 [cid1 2B] 00 00 00 [cid2 2B] 00*8 01."""
        items = _load_gamedata_items()
        pots = []   # (qty, idx, tid) - do an/thuoc (hp/sp) trong tui
        for idx, (tid, cnt) in self.bag_slots.items():
            if cnt < 1 or idx > 0xFF:
                continue
            info = items.get(tid)
            if not info or (info.get("hp", 0) <= 0 and info.get("sp", 0) <= 0):
                continue
            if info.get("battle"):     # item hoi sinh (Phuc Hon/Tu Quang) - khong hop
                continue
            if any(x in info.get("name", "") for x in self._COMBINE_EXCLUDE):
                continue
            pots.append((cnt, idx, tid))
        pots.sort()   # it nhat truoc
        if len(pots) >= 2:                  # 2 loai it nhat (don stack le)
            (_, i1, t1), (_, i2, t2) = pots[0], pots[1]
        elif pots and pots[0][0] >= 2:      # chi 1 loai -> hop 2 cai cua no
            (_, i1, t1) = pots[0]; i2, t2 = i1, t1
        else:
            log.info("[%s] Hop do: khong du do an/thuoc trong tui de hop", self._label)
            return
        cid1, cid2 = 0x100 + i1, 0x100 + i2
        pkt = (b"\x0e\x00" + struct.pack("<H", cid1) + b"\x00\x00\x00"
               + struct.pack("<H", cid2) + b"\x00" * 8 + b"\x01")
        self.send(0x17, pkt)
        time.sleep(0.5)
        log.info("[%s] Hop vat pham: %s(slot%d) + %s(slot%d)", self._label,
                 items.get(t1, {}).get("name", hex(t1)), i1, items.get(t2, {}).get("name", hex(t2)), i2)

    def do_world_boss(self):
        """BOSS THE GIOI (nhiem vu o 2): event teleport (0x20 02 00 08) -> map boss 0x2d ->
        engage NPC 0x3232 (0x41) -> VAO 1 tran (combat engine tu danh). CHI CAN VAO TRAN la o2
        mark (khong can thang). Co GIO EVENT -> ngoai gio teleport/engage fail (khong vao tran)
        -> bo qua. Xong thi teleport ve Trac Quan (12001) cho khoi ket map boss. Goi khi o2 chua xong."""
        import datetime
        vn_hour = (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).hour
        if not (12 <= vn_hour < 23):          # event boss chi mo 12h-23h (gio VN)
            log.info("[%s] Boss the gioi: ngoai gio event (12h-23h VN, hien %dh) -> bo qua",
                     self._label, vn_hour)
            return
        orig = self.current_map
        self.flee_mode = True                 # sach tran truoc khi gui goi teleport (tranh kick)
        for _ in range(20):
            if not self.running:
                return
            if not self.in_combat():
                break
            time.sleep(1)
        if not self.running:
            return
        time.sleep(1.0)
        self.heal_full()          # HOI FULL HP/SP truoc khi danh boss the gioi
        self.state.boss_mode = True
        # TAT FLEE NGAY (truoc khi teleport): tran boss co the bat dau ngay luc transit/toi noi ->
        # flee con bat la receiver BO CHAY mat tran. Khu boss chi co boss nen tat flee la an toan.
        self.flee_mode = False
        # (1) MO event boss TRUOC roi moi teleport (replay capture: 0x4d 0x0c -> 0x20 -> 0x14).
        #     Thieu 0x4d/0x0c -> server tu choi teleport (0x14 01002d00) -> tra loi 0x00 code7 -> kick.
        self.send(0x4d, b"\x03\x00\x05\x00");    time.sleep(0.4)   # mo/chon event boss
        self.send(0x0c, b"\x01\x00");            time.sleep(0.4)   # xin info
        self.send(0x20, b"\x02\x00\x08");        time.sleep(0.5)   # chon diem teleport boss
        self.send(0x14, b"\x01\x00\x2d\x00");    time.sleep(0.8)   # teleport map boss 0x2d
        self.send(0x14, b"\x09\x00\x1e");        time.sleep(0.3)
        self.send(0x14, b"\x06\x00");            time.sleep(1.2)
        # (2) engage NPC boss
        self.send(0x41, bytes.fromhex("01003232010100000101000000")); time.sleep(1.0)
        # (3) cho VAO tran (event active?) trong 12s
        entered = False
        t0 = time.time()
        while time.time() - t0 < 12:
            if not self.running:
                self.state.boss_mode = False
                return
            if self.state.in_battle:
                entered = True
                break
            time.sleep(0.3)
        if not entered:
            log.info("[%s] Boss the gioi: khong vao duoc tran (ngoai gio event?) -> bo qua", self._label)
        else:
            log.info("[%s] Boss the gioi: DA VAO TRAN -> danh CHO HET TRAN", self._label)
            # cho tran KET THUC THAT (in_battle ve False), cap 120s (boss khoe thi cap se cat)
            t0 = time.time()
            while self.running and self.state.in_battle and time.time() - t0 < 120:
                time.sleep(1)
            log.info("[%s] Boss the gioi: tran ket thuc (sau %ds)", self._label, int(time.time() - t0))
        self.state.boss_mode = False
        # (4) teleport ve Trac Quan (thanh chung moi server) -> flow train sau do tu route tiep
        if self.running and (orig is None or self.current_map != orig):
            self._wait_combat_clear()
            self.teleport(12001, 0)
            time.sleep(1.5)

    # Nhiem vu hang ngay BINGO 3x3: 9 o (1..9). Du 1 HANG hoac COT (3 o) -> 1 qua; du 6 qua -> 1 qua
    # TONG KET. Line id: hang R1-3=1-3, cot C1-3=4-6, tong ket=7. Reward id = 0x2f + line-1.
    _Q_LINES = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9),      # 3 hang
                4: (1, 4, 7), 5: (2, 5, 8), 6: (3, 6, 9)}      # 3 cot
    _Q_OPEN = bytes.fromhex(
        "0200090100012f0001000230000100033100010004320001000533000100063400010007350001000836000100")

    def _query_quests(self):
        """Mo panel nhiem vu (C2S 0x5b 02 00 09...) -> server tra o nao DA HOAN THANH
        (S2C 0x5b 02 00 01 01 00 [cell] -> handler nhet vao self._quest_cells).
        KHONG reset _quest_cells o day -> TICH LUY qua nhieu lan query (frame status TO 208B co the
        chi ve o lan mo panel DAU; query lan 2 reset se mat -> thieu o nhu o9). Reset o claim_daily_quests."""
        self.send(0x5b, self._Q_OPEN)
        time.sleep(1.5)             # cho server gui status 9 o (bulk)
        # O9 (battle-50, quest DEM) trong bulk LUON tra 020003 (ko ro done) -> QUERY RIENG o9
        # (id 0x37): server tra 020001010009 neu DA xong -> handler bat. Chua xong: 020003/020004.
        self.send(0x5b, bytes.fromhex("0200010100093700"))
        time.sleep(0.8)
        return self._quest_cells

    def claim_daily_quests(self, heavy: bool = True):
        """STATUS-DRIVEN: query 9 o -> o CHUA xong (bot lam duoc) thi LAM -> re-query -> claim
        hang/cot du 3 o (0x5b 03 00 01 00 [line][id]) + TONG KET neu du 6.
          heavy=True (mac dinh): lam ca nhiem vu NANG (boss the gioi o2 - teleport di) + nhe.
          heavy=False: CHI nhiem vu NHE (gacha o4/o6, hop o7 - khong roi cho) + claim. Dung cho
            mode DI GIOI (goi sau khi VAO DG, tranh boss teleport van ra khoi DG; o1/o2/o5 nang
            se claim_daily_quests(heavy=True) goi SAU khi xong DG).
        Chay moi login: o da xong -> bo qua; gacha thieu xu lan truoc -> login sau tu retry."""
        # CHI tin trang thai server tra LUC NAY (KHONG cache): moi lan query server gui lai DAY DU o da
        # xong (020001010009...). Cache cu thua + tung POISON (parse sai o9 -> luu nham -> relogin van bao xong).
        self._quest_cells = set()
        done = self._query_quests()
        # lam cac nhiem vu con thieu (gacha tu check xu, hop tu check nguyen lieu)
        acted = False
        if 6 not in done:
            self.claim_gacha_pet();  acted = True   # o 6 = gacha pet (NHE)
        if 4 not in done:
            self.claim_gacha_card(); acted = True   # o 4 = gacha card (NHE)
        if 7 not in done:
            self.do_combine_item();  acted = True   # o 7 = hop vat pham (NHE)
        if heavy and 2 not in done:
            self.do_world_boss();    acted = True   # o 2 = boss the gioi (mo event 0x4d/0x0c truoc teleport)
        # (o1 dungeon = do_daily_dungeon rieng; o5 team dungeon = chua co - deu NANG)
        if acted:
            done = self._query_quests()   # refresh sau khi lam
        # Claim hang/cot khi DU CA 3 o (server tra status day du moi query -> tin truc tiep).
        lines = [L for L, cells in self._Q_LINES.items() if all(c in done for c in cells)]
        n = 0
        for L in lines:                       # thu claim tung hang/cot (server tu validate)
            self.send(0x5b, b"\x03\x00\x01\x00" + bytes([L]) + struct.pack("<H", 0x2f + L - 1))
            time.sleep(0.3); n += 1
        if len(lines) >= 6:                   # du 6 -> claim TONG KET (line 7)
            self.send(0x5b, b"\x03\x00\x01\x00\x07" + struct.pack("<H", 0x2f + 6))
            time.sleep(0.3); n += 1
        log.info("[%s] Nhiem vu hang ngay: o xong=%s (%d/9), thu claim %d line (line %s)",
                 self._label, sorted(done), len(done), n, lines)

    def _on_friend_gift(self, pkt: bytes):
        """Parse S2C 0x0e ban be:
          sub 05 (list login): [05 00][count 2B] + N*[entity 8B][namelen 1B][name][trailer 35B]
            trailer[18]: bit0x01 = DA TANG qua cho ban nay, bit0x02 = ban CO QUA cho minh nhan.
          sub 0d: xac nhan nhan 1 qua.
        Luu friend_entities (merge) + friend_status[entity]=trailer[18]."""
        body = pkt[7:]
        if len(body) < 3:
            return
        sub = body[0]
        if sub == 0x05:           # list ban (login push) - full list roi tung ban 1 goi (update)
            cnt = int.from_bytes(body[2:4], "little")
            i = 4
            new = []
            for _ in range(cnt):
                if i + 9 > len(body):
                    break
                ent = body[i:i + 8]
                nl = body[i + 8]
                tr = body[i + 9 + nl:i + 9 + nl + 35]
                if len(tr) >= 19:
                    self.friend_status[ent.hex()] = tr[18]   # cap nhat status moi nhat
                if ent not in self.friend_entities:
                    self.friend_entities.append(ent); new.append(ent)
                i += 9 + nl + 35
            if new:
                log.info("[%s] Ban be: %d ban (tu 0x0e 05): %s", self._label,
                         len(self.friend_entities), [e.hex()[:4] for e in self.friend_entities])
        elif sub == 0x0d:         # xac nhan NHAN 1 qua tu ban: [0d 00][entity 8B][01 00]
            self._gift_recv += 1

    def claim_friend_gifts(self):
        """TANG qua cho ban CHUA tang + NHAN qua ban da tang minh. HOAN TOAN theo STATUS server
        (friend_status[entity]=trailer[18] tu 0x0e 05 login): bit0x01=DA TANG, bit0x02=CO QUA nhan.
          TANG:  C2S 0x0e [12 00][count][entity*N]  - chi ban CHUA tang (status & 0x01 == 0)
          NHAN:  C2S 0x0e [13 00][count][entity*N]  - chi ban CO QUA   (status & 0x02)
        KHONG can daily_mark: status doc truc tiep -> relogin se thay 'da tang/da nhan' -> tu bo qua
        (idempotent). Chay moi login -> bat duoc ca qua ban gui TRONG NGAY."""
        ents = list(self.friend_entities)
        if not ents:
            return   # chua nhan duoc list ban -> login sau thu lai
        to_send = [e for e in ents if not (self.friend_status.get(e.hex(), 0) & 0x01)]  # chua tang
        to_recv = [e for e in ents if (self.friend_status.get(e.hex(), 0) & 0x02)]       # co qua
        if to_send:
            self.send(0x0e, b"\x12\x00" + bytes([len(to_send)]) + b"".join(to_send))
            time.sleep(0.5)
        self._gift_recv = 0
        if to_recv:
            self.send(0x0e, b"\x13\x00" + bytes([len(to_recv)]) + b"".join(to_recv))
            time.sleep(1.0)   # cho 0x0e 0d xac nhan
        if to_send or to_recv:
            log.info("[%s] Qua ban be: tang %d ban (chua tang), nhan %d/%d qua",
                     self._label, len(to_send), self._gift_recv, len(to_recv))

    def _run_one_dungeon(self, max_sec: int) -> bool:
        """Chay 1 luot dungeon: query -> vao -> danh boss -> nhan thuong -> ra. True neu vao duoc."""
        orig = self.current_map
        # (1) TRANH BI KICK: phai SACH tran trUOC khi gui goi vao dungeon. Neu con dang
        #     danh tren map train (navigate flee) ma gui 0x2f/0x14 -> server kick (Server dong
        #     ket noi). Giu flee BAT, cho het tran (in_combat ve False sau ~4s idle), toi 30s.
        self.flee_mode = True
        for _ in range(30):
            if not self.running:
                return False
            if not self.in_combat():
                break
            time.sleep(1)
        if not self.running:
            return False
        time.sleep(1.0)               # them 1s cho server chot "ra tran"
        self.heal_full()              # HOI FULL HP/SP truoc khi vao danh boss dungeon
        self.state.boss_mode = True
        self.dungeon_complete = False
        # (2) Chuoi vao dungeon (capture dungeon.pcap), GUI LIEN khong cho map doi:
        #   0x2f 0100 query -> 0x2f 0200020000 VAO -> 0x14 08000100 KHOI DONG tran boss
        #   -> 0x0c 0100 xin info -> 0x14 0600 confirm.
        # LUU Y: map CHI doi sang dungeon SAU KHI gui 0x14 08000100 (code cu cho map doi
        #   truoc roi moi gui 0x14 -> deadlock -> ket o map boss khong danh).
        self.send(0x2f, b"\x01\x00"); time.sleep(0.6)             # query pho ban
        self.send(0x2f, b"\x02\x00\x02\x00\x00"); time.sleep(0.6)  # VAO dungeon
        self.send(0x14, b"\x08\x00\x01\x00"); time.sleep(0.4)      # khoi dong tran boss
        self.send(0x0c, b"\x01\x00"); time.sleep(0.4)              # xin info tran
        self.send(0x14, b"\x06\x00")                               # confirm
        # (3) Xac nhan DA vao dungeon. SOLO dungeon KHONG co nguoi xung quanh -> current_map
        #     (doc tu broadcast nguoi KHAC) KHONG cap nhat sang map dungeon -> KHONG dua vao map.
        #     Dung tin hieu IN_BATTLE (boss giao chien) lam dau hieu da vao: da sach tran truoc
        #     do nen in_battle bat LAI = chinh la tran BOSS. CHI dung in_battle, KHONG dung
        #     "map doi" lam dau hieu: vao dungeon la VAO TRAN BOSS ngay; con map doi co the chi
        #     la di qua TOWN (12001/12002...) khi het luot -> bat nham "da vao" dù boss khong co.
        entered = False
        t0 = time.time()
        while time.time() - t0 < 15:
            if not self.running:
                self.state.boss_mode = False; return False
            if self.state.in_battle:
                self.flee_mode = False   # boss giao chien -> DANH ngay (tat flee TRUOC khi timer fire)
                entered = True; break
            time.sleep(0.1)
        if not entered:
            log.info("[%s] Khong vao duoc dungeon (het luot/het vang?)", self._label)
            self.state.boss_mode = False
            # Neu bi DAY vao sanh dungeon (map doi khac orig) ma khong danh duoc -> THOAT ve map cu
            # (server het luot van teleport vao sanh 12000... -> phai ra keo lech khoi map train).
            if self.current_map is not None and orig is not None and self.current_map != orig:
                log.info("[%s] bi day vao sanh dungeon (map=%s) -> thoat ve map cu %s",
                         self._label, self.current_map, orig)
                self.leave_party(); time.sleep(0.6)
                self.send(0x14, b"\x06\x00"); time.sleep(0.6)
                for _ in range(20):
                    if not self.running or self.current_map == orig:
                        break
                    time.sleep(1)
            return False
        log.info("[%s] Da vao dungeon (in_battle=%s map=%s) -> danh boss",
                 self._label, self.state.in_battle, self.current_map)
        try:
            t0 = time.time()
            last_dbg = 0.0
            while self.running and time.time() - t0 < max_sec:
                time.sleep(1)
                now = time.time()
                if now - last_dbg >= 6:   # log chan doan moi 6s: co trong tran ko, quai, HP
                    last_dbg = now
                    log.info("[%s] dungeon: map=%s in_battle=%s quai=%s char_hp=%s/%s pet_sp=%s",
                             self._label, self.current_map, self.state.in_battle,
                             self.state.enemy_slots, self.state.char.hp, self.state.char.hp_max,
                             self.state.pet.sp)
                if self.dungeon_complete:
                    log.info("[%s] Dungeon HOAN THANH -> nhan thuong + ra", self._label)
                    self.send(0x52, b"\x01\x00\x01\x1d\x00")   # claim/confirm tong ket
                    time.sleep(0.6)
                    self.leave_party()                          # thoat dungeon (game tu dua ve map cu)
                    break
            # cho game tu dua ve map train (current_map cap nhat lai khi thay nguoi o safe)
            for _ in range(15):
                if not self.running or self.current_map == orig:
                    break
                time.sleep(1)
        finally:
            self.state.boss_mode = False
            self.flee_mode = True    # ra khoi dungeon -> bat lai flee (con phai ve safe/lap party)
        return True

    def buy_dungeon_ticket(self, wait: float = 2.5):
        """MUA ve dungeon bang vang. C2S 0x54 0100... (mo) -> 0x54 0200020d000200 (MUA).
        S2C 0x54 02000d00[01] -> byte cuoi 01 = MUA THANH CONG. Tra ve True/False."""
        self.send(0x54, b"\x01\x00\x0d\x00\x02\x00"); time.sleep(0.5)   # mo giao dien mua
        self._dg_query = None                                          # cho doi tra loi MUA
        self.send(0x54, b"\x02\x00\x02\x0d\x00\x02\x00")               # MUA (ton vang)
        for _ in range(int(wait / 0.2)):
            r = self._dg_query
            if r is not None and len(r) >= 5 and r[0:2] == b"\x02\x00":
                ok = (r[4] == 0x01)
                log.info("[%s] Mua ve dungeon -> %s (%s)", self._label,
                         "OK" if ok else "THAT BAI", r.hex())
                return ok
            time.sleep(0.2)
        log.info("[%s] Mua ve dungeon: khong nhan phan hoi -> coi nhu THAT BAI", self._label)
        return False

    def do_daily_dungeon(self, max_sec: int = 360):
        """SOLO daily dungeon, toi da DUNGEON_RUNS_PER_DAY luot/ngay (mac dinh 2).
        Luot 1 dung VE FREE (vao thang); luot >=2 MUA ve (0x54 0200020d000200) roi vao.
        Bot tu dem (checkin_state) + sync stat 0x9b. KHONG detect duoc het luot truoc khi vao
        (0x54 type 0x0d = exp offline; 0x9b chi gui SAU khi danh) -> neu local count BI STALE
        (vd da danh tay), luot free vao hut 1 lan roi cache 'het luot' khong thu nua."""
        import datetime
        runs_target = getattr(config, "DUNGEON_RUNS_PER_DAY", 2)
        today = datetime.date.today().isoformat()
        # TIN HIEU SERVER THAT: o 1 nhiem vu (solo dungeon 2 lan) DA XONG -> chac chan du luot.
        # Dang tin hon dem local (khong detect duoc luot da danh tay/session truoc). Neu chua co
        # trang thai quest (vd nhanh digioi goi dungeon TRUOC claim_daily_quests) -> tu query.
        if not self._quest_cells:
            try: self._query_quests()
            except Exception: pass
        if 1 in self._quest_cells:
            _save_checkin(self._label, "dungeon", today, runs_target)
            log.info("[%s] Dungeon: nhiem vu o1 (solo 2 lan) DA XONG theo server -> bo qua", self._label)
            return
        st = _load_checkin(self._label, "dungeon")
        count = st["day"] if st.get("date") == today else 0
        if self.dungeon_runs_today is not None:      # server-truth (chi co SAU khi danh) -> sync
            count = max(count, self.dungeon_runs_today)
        # SERVER (o1) noi CHUA xong nhung local bao du -> local STALE -> danh lai (>=1 luot).
        if self._quest_cells and 1 not in self._quest_cells and count >= runs_target:
            log.info("[%s] Dungeon: o1 chua xong (server) nhung local bao %d/%d -> local stale, danh lai",
                     self._label, count, runs_target)
            count = runs_target - 1
        if count >= runs_target:
            _save_checkin(self._label, "dungeon", today, count)
            log.info("[%s] Dungeon: da du %d/%d luot hom nay (local) -> bo qua "
                     "(xoa checkin_state.json key '%s:dungeon' neu muon danh lai)",
                     self._label, count, runs_target, self._label)
            return
        log.info("[%s] SOLO daily dungeon: da %d/%d luot hom nay", self._label, count, runs_target)
        self.leave_party(); time.sleep(1.5)   # thoat party (solo moi vao duoc dungeon)
        while count < runs_target and self.running:
            if count >= 1:   # luot 2+ -> HET free -> MUA ve bang vang
                if not self.buy_dungeon_ticket():
                    # mua THAT BAI (het vang / het luot mua) -> KHONG vao (tranh dump) -> dung
                    log.info("[%s] Mua ve dungeon that bai -> dung (khong vao de tranh dump)",
                             self._label)
                    _save_checkin(self._label, "dungeon", today, runs_target)
                    break
            # count==0 -> dung VE FREE, vao thang (khong mua)
            ok = self._run_one_dungeon(max_sec)
            count += 1   # DU thanh cong hay vao loi (dump) -> van count +1: coi nhu da DUNG 1 luot
                         # -> KHONG gui lai luot do nua; qua luot sau (luot sau se MUA ve -> vao chac).
            _save_checkin(self._label, "dungeon", today, count)
            if ok:
                log.info("[%s] Xong dungeon luot %d/%d", self._label, count, runs_target)
            else:
                log.info("[%s] Dungeon luot %d vao loi/dump (da danh tay?) -> van count +1, qua luot sau",
                         self._label, count)
            time.sleep(2)
        log.info("[%s] Hoan tat daily dungeon (%d luot)", self._label, count)

    GACHA_COST = 9000   # xu / luot gacha (pet va card deu 9k)

    def _wait_xu(self, timeout: float = 3.0):
        """Cho S2C 0x1a id=4 (so xu) toi, toi da 'timeout' giay."""
        t0 = time.time()
        while self.xu is None and time.time() - t0 < timeout:
            time.sleep(0.2)

    def claim_gacha_pet(self):
        """Gacha PET hang ngay (1 lan/ngay). C2S 0x42 (draw) + 3x 0x5b (reveal) - replay client that.
        Chi gacha khi xu >= 9000; thieu xu -> bo qua, login sau thu lai.
        Goi tu claim_daily_quests khi o 6 CHUA xong (status-driven, khong gate _daily_done)."""
        self._wait_xu()
        if self.xu is None or self.xu < self.GACHA_COST:
            log.info("[%s] Gacha pet: thieu xu (%s < %d) -> bo qua",
                     self._label, self.xu, self.GACHA_COST)
            return
        self.send(0x42, bytes.fromhex("0100050101015bb22823010000"))
        time.sleep(0.5)
        for _ in range(3):
            self.send(0x5b, bytes.fromhex("0200010100063400"))
            time.sleep(0.2)
        self.xu -= self.GACHA_COST   # server khong push lai balance -> tu tru
        log.info("[%s] Gacha PET hang ngay (xu con ~%d)", self._label, self.xu)

    def claim_gacha_card(self):
        """Gacha CARD hang ngay. Tuong tu gacha pet, banner id = 5cb2.
        Goi tu claim_daily_quests khi o 4 CHUA xong (status-driven, khong gate _daily_done)."""
        self._wait_xu()
        if self.xu is None or self.xu < self.GACHA_COST:
            log.info("[%s] Gacha card: thieu xu (%s < %d) -> bo qua",
                     self._label, self.xu, self.GACHA_COST)
            return
        self.send(0x42, bytes.fromhex("0100050101025cb22823010000"))
        time.sleep(0.5)
        for _ in range(3):
            self.send(0x5b, bytes.fromhex("0200010100043200"))
            time.sleep(0.2)
        self.xu -= self.GACHA_COST
        log.info("[%s] Gacha CARD hang ngay (xu con ~%d)", self._label, self.xu)

    def _learned(self) -> dict:
        """Cache item da hoc theo TID (template) - CHUNG mọi acc: item giong nhau = tid giong = heal giong.
        { tid_str: {hp,sp,hp_zero,sp_zero,none,unusable} }."""
        return _load_all_learned()

    def use_item(self, item_id: int, target: int = 0) -> bool:
        """Dung item trong tui. target=0: char, 1: pet.
        C2S 0x17: 0f 00 [tid 2B LE] 00 00 00 00 [target 1B] 00. Server confirm S2C 0x17 sub=09 -> tu tru.
        Chi chan khi BIET CHAC het (bag_counts==0); tid chua biet -> cho phep (server tu tu choi)."""
        if self.bag_counts.get(item_id, 1) <= 0:
            return False
        payload = b"\x0f\x00" + item_id.to_bytes(2, "little") + b"\x00\x00\x00\x00" + bytes([target]) + b"\x00"
        self.send(0x17, payload)
        return True

    def log_bag_delayed(self, delay: float = 8.0):
        """In tui SAU 'delay' giay (doi cac trang 0x16 ve het -> tui DAY DU). Goi luc login.
        Sau khi in tui xong -> mo tui Vat Lieu Su Kien (neu du so luong)."""
        def _run():
            time.sleep(delay)
            if self.running:
                self.log_bag()
                self.use_event_bags()
        threading.Thread(target=_run, daemon=True).start()

    # Tui Vat Lieu Su Kien (gamedata 0xb257): >=100 cai -> dung 100 cai 1 lenh luc login.
    EVENT_BAG_ID = 0xb257
    EVENT_BAG_MIN = 100
    EVENT_BAG_USE = 100
    EVENT_BAG_MAX_TIMES = 5   # toi da 5 lan (500 cai) 1 login

    def use_event_bags(self):
        """Login: dung Tui Vat Lieu Su Kien theo BOI cua 100, toi da 5 lan. So lan = min(co//100, 5)
        (>=100&<200 -> 1 lan; >=200&<300 -> 2 lan; ...; >=500 -> 5 lan). Moi lan 1 lenh 100 cai."""
        slot = next((s for s, (tid, cnt) in self.bag_slots.items()
                     if tid == self.EVENT_BAG_ID and cnt >= self.EVENT_BAG_MIN), None)
        if slot is None:
            return
        cnt = self.bag_slots[slot][1]
        times = min(cnt // self.EVENT_BAG_USE, self.EVENT_BAG_MAX_TIMES)
        used = 0
        for _ in range(times):
            if not self.use_slot(slot, qty=self.EVENT_BAG_USE):
                break
            used += 1
            time.sleep(0.5)   # cho server xu ly truoc lenh ke
        if used:
            log.info("[%s] dung %d Tui Vat Lieu Su Kien (%d lan x%d, co %d)",
                     self._label, used * self.EVENT_BAG_USE, used, self.EVENT_BAG_USE, cnt)

    def log_bag(self):
        """In tui theo SLOT, moi slot ghi ro la item KHAI (items_known.json) / HOC (probe) / CHUA BIET.
        De m doi chieu xem bot hieu dung khong, roi dien tiep items_known.json."""
        if not self.bag_slots:
            log.info("[%s] bag: chua nhan S2C 0x16 inventory", self._label)
            return
        known = _load_known_items()
        gdata = _load_gamedata_items()
        learned = self._learned()
        n_known = n_gdata = n_learn = n_unknown = 0
        log.info("[%s] === BAG (%d slot) === slot(idx): item_id x count -> item", self._label, len(self.bag_slots))
        for slot in sorted(self.bag_slots):
            tid, cnt = self.bag_slots[slot]
            k = known.get(tid); g = gdata.get(tid); lv = learned.get(str(tid)) or {}
            if k:
                n_known += 1
                eff = [s for s in ["+%dHP" % k["hp"] if k.get("hp") else "",
                                   "+%dSP" % k["sp"] if k.get("sp") else "", k.get("type", "")] if s]
                tag = "KHAI: %s %s" % (k.get("name", ""), " ".join(eff) or "(?)")
            elif g:
                n_gdata += 1
                eff = " ".join([s for s in ["+%dHP" % g["hp"] if g.get("hp") else "",
                                            "+%dSP" % g["sp"] if g.get("sp") else ""] if s])
                bt = " [CHI TRONG TRAN]" if g.get("battle") else ""
                tag = "gamedata: %s %s%s" % (g.get("name", ""), eff, bt)
            elif lv.get("hp", 0) > 0 or lv.get("sp", 0) > 0:
                n_learn += 1
                tag = "HOC: +%dHP +%dSP" % (lv.get("hp", 0), lv.get("sp", 0))
            elif lv.get("none"):
                n_learn += 1; tag = "HOC: khong hoi (none)"
            elif lv.get("unusable"):
                n_learn += 1; tag = "HOC: ko dung duoc"
            else:
                n_unknown += 1; tag = "??? CHUA BIET"
            log.info("[%s]   slot %d: id=0x%04x x %d -> %s", self._label, slot, tid, cnt, tag)
        log.info("[%s] === Tong: %d KHAI, %d gamedata, %d HOC, %d CHUA BIET ===",
                 self._label, n_known, n_gdata, n_learn, n_unknown)

    # ---------- HOI MAU: closed-loop tren HP/SP live (S2C 0x08) + self-calibrate ----------
    def _heal_threshold(self, kind: str) -> float:
        """Nguong hoi mau cho acc nay. kind: hp_char/sp_char/hp_pet/sp_pet.
        Uu tien config.ACCOUNT_HEAL[username][kind]; thieu -> HP_THRESHOLD/SP_THRESHOLD chung."""
        glob = getattr(config, "SP_THRESHOLD", 0.0) if kind.startswith("sp") \
            else getattr(config, "HP_THRESHOLD", 0.4)
        over = getattr(config, "ACCOUNT_HEAL", {}).get(self._username, {})
        return over.get(kind, glob)

    def use_slot(self, slot: int, target: int = 0, qty: int = 1) -> bool:
        """Dung item o SLOT. C2S 0x17: 0f 00 [slot 1B][qty 1B] 00 00 00 00 [target 1B] 00.
        qty = so luong dung 1 lenh (1..255; verify capture: dung 22 -> byte=0x16). Heal qty=1.
        Server confirm S2C 0x17 sub=09 (= dung duoc). Tra False neu slot het."""
        rec = self.bag_slots.get(slot)
        if rec is not None and rec[1] <= 0:
            return False
        qty = max(1, min(int(qty), 255))
        payload = b"\x0f\x00" + bytes([slot & 0xFF, qty]) + b"\x00\x00\x00\x00" + bytes([target & 0xFF]) + b"\x00"
        self.send(0x17, payload)
        return True

    def _learn_item(self, tid: int, dhp: int, dsp: int, room_hp: bool = True, room_sp: bool = True,
                    cap_hp: bool = False, cap_sp: bool = False):
        """Ghi nho (theo TID) item hoi bao nhieu HP/SP. room_*: stat do co cho do khong.
        cap_*: do XONG ma stat KICH TRAN (do hut) -> chi lay floor (max). Khong kich tran -> so CHINH XAC
        -> GHI DE (sua lai dung). none = ca 2 stat da test deu khong hoi."""
        if tid in _load_known_items() or tid in _load_gamedata_items():
            return   # DA BIET (m khai / gamedata) -> KHOA, khong tu sua/probe
        learned = self._learned()
        key = str(tid)
        cur = learned.get(key, {})
        # DA TUNG ghi nhan hoi (hp/sp>0) ma lan nay 0 -> co the loi/bi keo vao battle -> GIU NGUYEN,
        # khong downgrade (khong set *_zero/none). Item da biet la item tot, 1 lan 0 khong phu nhan.
        if dhp <= 0 and dsp <= 0 and (cur.get("hp", 0) > 0 or cur.get("sp", 0) > 0):
            return
        hp = cur.get("hp", 0)
        if dhp > 0:
            hp = max(hp, dhp) if cap_hp else dhp   # kich tran -> floor; sach -> dung that, ghi de
        sp = cur.get("sp", 0)
        if dsp > 0:
            sp = max(sp, dsp) if cap_sp else dsp
        hp_zero = cur.get("hp_zero", False) or (room_hp and dhp <= 0)
        sp_zero = cur.get("sp_zero", False) or (room_sp and dsp <= 0)
        none = (hp == 0 and sp == 0 and hp_zero and sp_zero)
        old = (cur.get("hp", 0), cur.get("sp", 0))
        learned[key] = {"hp": hp, "sp": sp, "hp_zero": hp_zero, "sp_zero": sp_zero,
                        "none": none, "unusable": cur.get("unusable", False)}
        if dhp > 0 or dsp > 0:
            fix = " (SUA tu %d/%d)" % old if old != (hp, sp) and (old[0] or old[1]) else ""
            log.info("[%s] HOC item tid 0x%04x: %dHP %dSP%s%s", self._label, tid, hp, sp,
                     " [kich tran-floor]" if (cap_hp and dhp > 0) or (cap_sp and dsp > 0) else "", fix)
        elif none:
            log.info("[%s] item tid 0x%04x dung duoc nhung KHONG hoi HP/SP -> none", self._label, tid)
        _save_all_learned()

    def _mark_unusable(self, tid: int):
        """Probe KHONG duoc confirm. 1 lan co the do LAG/mat goi -> chua khoa. >=2 lan lien tiep moi
        ghi unusable (item that su ko dung duoc). Confirm lai bat ky luc nao -> reset strike (xem _learn_item)."""
        learned = self._learned()
        key = str(tid)
        cur = learned.get(key, {})
        cur["strikes"] = cur.get("strikes", 0) + 1
        if cur["strikes"] >= 2:
            cur["unusable"] = True
            log.info("[%s] item tid 0x%04x ko confirm 2 lan -> unusable", self._label, tid)
        else:
            log.info("[%s] item tid 0x%04x ko confirm (strike %d/2, co the lag) -> thu lai sau",
                     self._label, tid, cur["strikes"])
        learned[key] = cur
        _save_all_learned()

    def _item_info(self, tid: int) -> dict:
        """Thong tin hoi cua tid. Uu tien: items_known.json (m khai) > items_gamedata.json (crack) > learned.
        2 nguon dau = LOCKED (khong probe/sua)."""
        k = _load_known_items().get(tid)
        if k is not None:
            return {"hp": k.get("hp", 0), "sp": k.get("sp", 0), "type": k.get("type", ""),
                    "none": False, "unusable": False, "locked": True}
        g = _load_gamedata_items().get(tid)
        if g is not None:
            return {"hp": g.get("hp", 0), "sp": g.get("sp", 0), "battle": g.get("battle", False),
                    "name": g.get("name", ""), "none": False, "unusable": False, "locked": True}
        return self._learned().get(str(tid)) or {}

    def _slot_for_known(self, kind: str, skip_slots) -> tuple:
        """Tim SLOT chua item DA BIET (locked hoac da hoc) hoi 'kind', count>0. Uu tien heal lon."""
        best = None
        for slot, (tid, cnt) in self.bag_slots.items():
            if cnt <= 0 or slot in skip_slots:
                continue
            v = self._item_info(tid)
            if not v or v.get("none") or v.get("unusable") or v.get("battle"):
                continue   # battle=True: do hoi sinh, CHI dung trong tran -> ko hoi ngoai
            heal = v.get(kind, 0)
            if heal > 0 and (best is None or heal > best[2]):
                best = (slot, tid, heal)
        return best

    def do_heal(self):
        """Hoi mau NGOAI tran cho CHAR (target=0) + PET (target=1), dung thuoc DA BIET (gamedata/khai).
        KHONG probe (gamedata da biet het thuoc). Hoi den NGUONG la dung."""
        if self.in_combat() or not self.bag_slots:
            return
        c = self.state.char
        if c.hp_max > 0:
            self._heal_unit(0, c, "char", "hp_char", "hp")
            self._heal_unit(0, c, "char", "sp_char", "sp")
        p = self.state.pet
        if p.hp_max > 0:
            self._heal_unit(1, p, "pet", "hp_pet", "hp")
            self._heal_unit(1, p, "pet", "sp_pet", "sp")

    def heal_full(self):
        """Hoi FULL HP+SP char + pet (nguong=1.0) - goi TRUOC khi danh boss (solo dungeon + world
        boss) de chac thang. Chi ngoai tran. Het thuoc thi hoi duoc bao nhieu hay bay nhieu."""
        if self.in_combat() or not self.bag_slots:
            return
        log.info("[%s] Hoi FULL HP/SP truoc khi danh boss...", self._label)
        c = self.state.char
        if c.hp_max > 0:
            self._heal_unit(0, c, "char", "hp_char", "hp", thr_override=1.0)
            self._heal_unit(0, c, "char", "sp_char", "sp", thr_override=1.0)
        p = self.state.pet
        if p.hp_max > 0:
            self._heal_unit(1, p, "pet", "hp_pet", "hp", thr_override=1.0)
            self._heal_unit(1, p, "pet", "sp_pet", "sp", thr_override=1.0)

    def _heal_unit(self, target: int, unit, label: str, thr_key: str, kind: str, thr_override=None):
        """Hoi 1 con 1 stat bang thuoc DA BIET den nguong. char do qua 0x08 (chinh xac);
        pet ko do duoc -> uoc tinh theo heal (open-loop). Het thuoc nay -> tu chuyen thuoc khac.
        thr_override: ep nguong (vd 1.0 = FULL) - dung cho heal_full truoc boss."""
        if self.in_combat():
            return
        nokey = (target, kind)
        if nokey in self._no_item:
            return                 # da bao het thuoc loai nay -> cho TRAN SAU (0x34 reset) moi check
        thr = thr_override if thr_override is not None else self._heal_threshold(thr_key)
        mx = unit.hp_max if kind == "hp" else unit.sp_max
        cur = unit.hp if kind == "hp" else unit.sp
        if thr <= 0 or mx <= 0 or cur >= mx * thr:
            return
        target_val = int(mx * thr)
        remaining = target_val - cur   # uoc tinh con thieu (cho pet open-loop)
        healed = False
        for _ in range(40):
            if self.in_combat():
                break
            cur = unit.hp if kind == "hp" else unit.sp
            if target == 0 and cur >= target_val:
                break              # CHAR: 0x08 bao da dat nguong -> dung
            if remaining <= 0:
                break              # uoc tinh da du (chu yeu cho pet)
            found = self._slot_for_known(kind, set())
            if found is None:
                log.info("[%s] %s HET thuoc %s -> bo qua, cho tran sau (co the drop them)",
                         self._label, label, kind.upper())
                self._no_item.add(nokey)   # skip toi tran sau
                break
            slot, tid, heal = found
            if not self.use_slot(slot, target):
                break
            remaining -= heal
            healed = True
            log.info("[%s] hoi %s slot=%d 0x%04x +%d%s (con thieu ~%d)",
                     self._label, label, slot, tid, heal, kind.upper(), max(0, remaining))
            time.sleep(0.3)
        # PET (target!=0) hoi open-loop: HP that KHONG cap nhat ngoai tran -> set OPTIMISTIC = nguong
        # de keepalive sau KHONG hoi lai vo han (HP that se cap nhat lai dau tran sau qua 0x33).
        if target != 0 and healed:
            if kind == "hp":
                unit.hp = max(unit.hp, target_val)
            else:
                unit.sp = max(unit.sp, target_val)

    def decompose_junk_scrolls(self, wait: float = 1.2):
        """Phan giai cuon GOI PET RAC (gacha ra nhieu) -> nhan lai xu. C2S 0x59:
          03 00 01 [slot 1B][01] 00 00 00   (giong use-item: tham chieu theo SLOT, KHONG phai tid).
        AN TOAN: chi phan giai SLOT co tid nam trong CONFIG.JUNK_PET_SCROLLS (= danh sach TID cuon rac,
        template -> dung mọi acc). Tim slot trong bag_slots theo tid -> gui 0x59 voi slot do.
        So luong biet tu bag_slots[slot]; khong confirm -> dung ngay (tranh ban mu)."""
        junk_tids = set()
        # NGUON CHINH: items_known.json -> tid co type chua 'scroll'/'junk' = cuon rac (phan giai).
        for tid, info in _load_known_items().items():
            if str(info.get("type", "")).lower() in ("scroll", "junk", "cuon"):
                junk_tids.add(tid)
        # Tuong thich cu: junk_scrolls.json / config.JUNK_PET_SCROLLS (key = tid hex).
        for k in (getattr(config, "JUNK_PET_SCROLLS", {}) or {}):
            try:
                junk_tids.add(int(k, 16) if isinstance(k, str) else int(k))
            except Exception:
                pass
        if not junk_tids:
            return
        total = 0
        guard = 0
        while self.running and guard < 1000:
            guard += 1
            # tim 1 SLOT con cuon rac (tid nam trong junk_tids)
            target = None
            for slot, (tid, cnt) in list(self.bag_slots.items()):
                if cnt > 0 and tid in junk_tids:
                    target = (slot, tid)
                    break
            if target is None:
                break   # het cuon rac trong tui
            slot, tid = target
            seq0 = self._decompose_seq
            self.send(0x59, b"\x03\x00\x01" + bytes([slot & 0xFF, 0x01]) + b"\x00\x00\x00")
            t0 = time.time()
            while self._decompose_seq == seq0 and time.time() - t0 < wait and self.running:
                time.sleep(0.1)
            if self._decompose_seq == seq0:
                # khong confirm -> coi nhu slot het, xoa khoi tracking (tranh loop) va dung slot nay
                self.bag_slots.pop(slot, None)
                continue
            # confirm -> tru count slot (S2C 0x16 cung se update lai)
            rec = self.bag_slots.get(slot)
            if rec:
                rec[1] = max(0, rec[1] - 1)
                if rec[1] <= 0:
                    self.bag_slots.pop(slot, None)
            total += 1
            log.info("[%s] phan giai cuon rac slot=%d tid=0x%04x ('%s')",
                     self._label, slot, tid, junk.get(hex(tid), junk.get(str(tid), "")))
            time.sleep(0.25)
        if total:
            log.info("[%s] Phan giai cuon rac: tong %d cuon -> nhan xu", self._label, total)

    def _on_vantieu(self, pkt: bytes):
        """S2C 0x56 panel: [03 00][count 1B] + count*[slot 1B][start 8B OLE][end 8B OLE]
        [x 1B][pet 1B][yy 2B] (21B/entry). Doc slot + GIO KET THUC (OLE date) vao vantieu_slots.
        A=0 (toan byte 00) = slot rong (vua claim)."""
        body = pkt[7:]
        if len(body) < 3:
            return
        if body[0:2] == b"\x06\x00":          # so slot DA MO (con lai khoa = can vang unlock)
            self.vantieu_unlocked = body[2]
            return
        if body[0:2] == b"\x04\x00" and len(body) >= 5:  # MA YEU CAU (b0 b1 b2) cho slot ke tiep
            self.vantieu_req_code = body[2:5].hex()
            return
        if body[0:2] != b"\x03\x00":
            return
        count = body[2]
        off = 3
        for _ in range(count):
            if off + 21 > len(body):
                break
            slot = body[off]
            try:
                start_ole = struct.unpack("<d", body[off + 1:off + 9])[0]
                end_ole = struct.unpack("<d", body[off + 9:off + 17])[0]
            except Exception:
                break
            pet = body[off + 18]
            if start_ole <= 0:                 # slot rong (da claim)
                self.vantieu_slots.pop(slot, None)
            else:
                self.vantieu_slots[slot] = {"end": end_ole, "pet": pet}
            off += 21

    def _on_vantieu_roster(self, pkt: bytes):
        """S2C 0x1f sub=0600: list pet KHO dung de van tieu (gui luc login).
        Entry: [index 1B][11B: ?+pet_id+stats][ten UTF-16LE][null 0000]. index = chi so gui 0x56 0200."""
        b = pkt[7:]
        roster, pos = {}, 2
        while pos + 13 < len(b):
            index = b[pos]
            npos = pos + 13
            end = npos
            while end + 1 < len(b) and b[end:end + 2] != b"\x00\x00":
                end += 2
            try:
                name = b[npos:end].decode("utf-16-le")
            except Exception:
                name = ""
            if name and 1 <= index <= 30 and all(0x20 <= ord(c) for c in name):
                roster[index] = name
                pos = end + 2
            else:
                pos += 1
        if roster:
            self.vantieu_roster = roster
            log.info("[%s] Van tieu roster (kho): %s", self._label,
                     {i: roster[i] for i in sorted(roster)})

    @staticmethod
    def _ole_to_dt(ole):
        import datetime
        return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=ole)

    def _match_vantieu_pet(self, cands, used, req):
        """cands = list (inn_index, ten_pet). Chon con KHOP 'req' (he,doanh) nhat trong con CON TRONG.
        Score: dung ca he+doanh=2, dung 1=1, ko khop=0 (van gui de duoc qua co ban).
        Tra ve inn_index, None = het con trong. (req luon DA BIET - ma la xu ly o do_van_tieu.)"""
        best, best_score, best_nm, best_hd = None, -1, None, None
        for idx, nm in cands:
            if idx in used:
                continue
            hd = config.PET_HEDOANH.get(nm, {})
            score = (hd.get("he") == req["he"]) + (hd.get("doanh") == req["doanh"])
            if score > best_score:
                best, best_score, best_nm, best_hd = idx, score, nm, hd
        if best is None:
            return None
        tag = {2: "khop ca he+doanh", 1: "khop 1", 0: "KHONG khop (gui tam, qua co ban)"}[best_score]
        log.info("[%s] Van tieu match: yeu cau=%s -> slot %d '%s' %s [%s]",
                 self._label, req, best, best_nm, best_hd, tag)
        return best

    def do_van_tieu(self):
        """Van tieu (escort) opcode 0x56. Gui pet (VANTIEU_PETS = index list quan tro) ->
        ~4h sau nhan qua. Goi luc login + dinh ky.
          mo panel:  0x56 0100  -> S2C 0x56 0300 (slot + gio ket thuc OLE)
          gui pet:   0x56 0200 [pet_index]
          nhan qua:  0x56 0500 [slot]
        CLAIM theo GIO KET THUC tu server (now >= end), KHONG hardcode thoi luong.
        So luot/ngay = max(local_count, server vantieu_started) so voi vantieu_max (3).
        TRA VE: epoch thoi diem CAN GOI LAI (escort xong som nhat) hoac None (het viec hom nay)
        -> caller hen dung gio, KHONG check mu dinh ky."""
        import datetime
        if not getattr(config, "VANTIEU_ENABLE", False):
            return None
        pets = list(getattr(config, "VANTIEU_PETS", []) or [])
        self.vantieu_slots = {}           # reset -> panel gui lai trang thai moi
        self.send(0x56, b"\x01\x00")      # mo panel
        time.sleep(1.2)
        now = datetime.datetime.now()
        # 1) NHAN qua slot da xong (now >= gio ket thuc)
        for slot, info in list(self.vantieu_slots.items()):
            if now >= self._ole_to_dt(info["end"]):
                self.send(0x56, b"\x05\x00" + bytes([slot & 0xFF]))
                time.sleep(0.5)
                self.vantieu_slots.pop(slot, None)
                log.info("[%s] Van tieu: nhan qua slot %d (da xong)", self._label, slot)
        # 2) GUI pet moi: CHI vao slot DA MO (1..vantieu_unlocked, KHONG tu unlock = ton vang)
        #    va trong gioi han luot/ngay (vantieu_max). slot dang chay -> bo qua.
        # cands = list (inn_index, ten_pet) de match. Uu tien ROSTER tu server (0x1f, AUTO);
        # khong co thi dung config VANTIEU_PETS_NAMES (theo thu tu slot).
        if self.vantieu_roster:
            cands = [(i, self.vantieu_roster[i]) for i in sorted(self.vantieu_roster)]
        else:
            cands = [(i + 1, nm) for i, nm in enumerate(getattr(config, "VANTIEU_PETS_NAMES", []) or [])]
        # Smart match: 0400 = ma yeu cau (ON DINH khi panel ALL-FREE 030000, khong co escort chay).
        # Khi co escort chay (vantieu_slots khong rong), 0400 = token escort do, KHONG phai yeu cau
        # slot trong -> do_van_tieu chi smart match khi vantieu_slots RONG (xem vong loop ben duoi).
        smart = bool(cands) and bool(getattr(config, "VANTIEU_REQUESTS", {}))
        if pets or smart:
            daily_cap = self.vantieu_max or 3
            unlocked = self.vantieu_unlocked or 1
            started = max(_vantieu_count(self._label), self.vantieu_started or 0)
            occupied = set(self.vantieu_slots)
            free_slots = [s for s in range(1, unlocked + 1) if s not in occupied]
            used, i = set(), 0
            while started < daily_cap and free_slots:
                if smart and not self.vantieu_slots:
                    # ALL-FREE (chua escort nao chay) -> 0400 = yeu cau slot trong, CHUAN -> smart match.
                    req = config.VANTIEU_REQUESTS.get(self.vantieu_req_code or "")
                    if req is None:            # MA LA (hiem neu bang 20/20 du) -> GUI DAI con trong
                        log.warning("[%s] Van tieu: ma yeu cau '%s' chua co trong bang -> gui dai con "
                                    "trong. Mo panel xem he/doanh roi them vao vantieu_requests.json.",
                                    self._label, self.vantieu_req_code)
                        pet = next((idx for idx, _ in cands if idx not in used), None)
                    else:
                        pet = self._match_vantieu_pet(cands, used, req)
                    if pet is None:            # het con trong
                        break
                elif smart:
                    # Co escort chay -> 0400 = token escort do (KHONG phai yeu cau slot trong)
                    # -> chua doc duoc yeu cau slot 2 -> DUNG (chi smart slot 1). Slot 2 to-do.
                    break
                else:                          # gui theo index co dinh (VANTIEU_PETS)
                    if i >= len(pets):
                        break
                    pet = pets[i]; i += 1
                slot = free_slots.pop(0)
                self.send(0x56, b"\x02\x00" + bytes([pet & 0xFF]))
                time.sleep(0.9)
                used.add(pet); started += 1
                _vantieu_set_count(self._label, started)
                log.info("[%s] Van tieu: gui pet #%d -> slot %d (da gui %d/%d, %d slot mo)",
                         self._label, pet, slot, started, daily_cap, unlocked)
        # HEN GIO: escort dang chay xong som nhat (panel da cap nhat slot moi gui qua _on_vantieu).
        ends = [self._ole_to_dt(info["end"]).timestamp() for info in self.vantieu_slots.values()]
        if ends:
            nxt = min(ends) + 10        # +10s dem cho chac chan da xong
            log.info("[%s] Van tieu: check lai luc %s",
                     self._label, datetime.datetime.fromtimestamp(nxt).strftime("%H:%M:%S"))
            return nxt
        return None                     # khong con escort dang chay -> het viec hom nay

    def _on_gift(self, pkt: bytes):
        """S2C 0x57 sub=2: [02 00][type 1B][status 1B]. type=03 qua online, type=01 DIEM DANH.
        status=0 = thanh cong."""
        if len(pkt) < 11:
            return
        if int.from_bytes(pkt[7:9], "little") == 0x02:
            gtype = pkt[9]; status = pkt[10]
            if gtype in (0x01, 0x04):              # diem danh / qua 14 ngay (log DEBUG -> ko spam scan)
                self._gift_status[gtype] = status
                log.debug("[%s] Gift type=%d: status=%d", self._label, gtype, status)
            else:                                  # qua online (type=03)
                log.info("[%s] Qua online: %s", self._label,
                         "THANH CONG" if status == 0 else f"status={status}")

    # ---- parse skill DA HOC DAY DU (0x05 char-info) ----
    def _parse_skill_list_0x05(self, pkt: bytes):
        """Trong goi char-info 0x05 co list skill DA HOC: [count 2B LE] + count*[skill 2B LE]
        [level 1B]. (0x28 chi la skill BAR -> thieu skill khong dat phim tat.) Tim list bang
        chu ky: 1 vi tri co count C nho (1..60) + dung C entry [id trong 0x2710..0x3fff][lv 1..99].
        Lay run dau tien -> UNION vao skills_char (khong mat skill bar)."""
        payload = pkt[7:]
        n = len(payload)
        for off in range(0, n - 3):
            c = int.from_bytes(payload[off:off + 2], "little")
            if not (1 <= c <= 60) or off + 2 + c * 3 > n:
                continue
            ids = []
            ok = True
            for k in range(c):
                p = off + 2 + k * 3
                sid = int.from_bytes(payload[p:p + 2], "little")
                lv = payload[p + 2]
                if not (0x2710 <= sid <= 0x3fff and 1 <= lv <= 99):
                    ok = False
                    break
                ids.append(sid)
            if ok and ids:
                # GIU THU TU (skill[0]=boss fallback): append id chua co. 0x05 la list day du.
                for s in ids:
                    if s not in self.state.skills_char:
                        self.state.skills_char.append(s)
                log.info("[%s] Char skills (day du tu 0x05, %d): %s", self._label, len(ids),
                         [hex(s) for s in ids])
                return

    # ---- parse skill bar (0x28) ----
    def _on_skill_bar(self, pkt: bytes):
        """S2C 0x28: skill bar cua char/pet.
        Format: [01 00][unit 1B][?? 1B][skill_id 2B LE ...][0000 = terminator/slot trong]...
        unit=3: CHAR, unit=2: PET. Byte sau unit KHONG phai count tin cay (capture: =5 nhung co
        6 skill) -> DOC SKILL TOI KHI GAP 0x0000 (terminator), khong dua theo count (bug cu cat
        mat skill cuoi -> vd thieu Nem Da 0x2715 -> char danh chay).
        CHI lay block CHAR (unit=3) DAU TIEN (sau padding co the co block rac id la -> bo qua)."""
        if len(pkt) < 12:
            return
        payload = pkt[7:]
        i = 2  # bo prefix 01 00
        seen_char = False
        while i + 2 <= len(payload) and not seen_char:
            unit = payload[i]
            if unit not in (2, 3):
                i += 1
                continue   # padding/byte la -> truot toi block hop le
            i += 2         # bo unit + byte sau (khong dung)
            skills = set()
            while i + 2 <= len(payload):
                sid = int.from_bytes(payload[i:i + 2], 'little')
                i += 2
                if sid == 0:
                    break  # terminator -> het skill cua unit nay
                if len(skills) > 40:
                    break  # canh rac
                skills.add(sid)
            if unit == 3:
                for s in skills:   # gop bar 0x28 vao list (append id chua co, giu thu tu 0x05)
                    if s not in self.state.skills_char:
                        self.state.skills_char.append(s)
                seen_char = True
                log.info("[%s] Char skills (bar 0x28): %s", self._label,
                         [hex(s) for s in sorted(skills)])
            elif unit == 2:
                self.state.skills_pet = skills

    # ---- parse player info (0x27) ----
    def _resolve_self_name(self, pkt: bytes):
        """Doc TEN NHAN VAT cua minh tu goi guild 0x27: tim self_entity roi name ngay sau
        (entity 8B + name_len 1B + name UTF-16LE)."""
        if self.char_name or not self.self_entity or not pkt:
            return
        k = pkt.find(self.self_entity)
        if k < 0 or k + 9 > len(pkt):
            return
        nl = pkt[k + 8]
        if not (0 < nl <= 40) or k + 9 + nl > len(pkt):
            return
        try:
            nm = pkt[k + 9:k + 9 + nl].decode('utf-16-le')
        except Exception:
            return
        if nm:
            self.char_name = nm
            self._label = nm
            log.info("[%s] Ten nhan vat = '%s'", self._username, nm)

    def _resolve_name_from_03(self, pkt: bytes):
        """Ten nhan vat tu goi 0x03 self-spawn - gui cho MOI acc luc login (KHONG can bang hoi).
        Layout: [0000][self_entity 8B][~36B stat][name_len 1B @body[46]][name UTF-16LE].
        Guard: 2 byte truoc name_len = 0000. Verify 3/3 acc (haabo/gamo/luubay). Fallback: quet."""
        if self.char_name or not self.self_entity or not pkt or len(pkt) < 55:
            return
        body = pkt[7:]
        if len(body) < 48 or body[2:10] != self.self_entity:
            return
        def _try(off):
            if off < 2 or off + 1 >= len(body):
                return None
            nl = body[off]
            if not (0 < nl <= 40) or nl % 2 or off + 1 + nl > len(body):
                return None
            if body[off - 2:off] != b"\x00\x00":
                return None
            try:
                nm = body[off + 1:off + 1 + nl].decode("utf-16-le")
            except Exception:
                return None
            return nm if (nm and nm.isprintable()) else None
        nm = _try(46)   # offset co dinh
        if not nm:      # fallback: quet sau entity tim [0000][len][name printable]
            for off in range(12, min(len(body) - 1, 90)):
                nm = _try(off)
                if nm:
                    break
        if nm:
            self.char_name = nm
            self._label = nm
            _register_party_name(self.self_entity, nm)
            log.info("[%s] Ten nhan vat = '%s' (tu 0x03)", self._username, nm)

    def _on_player_info(self, pkt: bytes):
        """S2C 0x27 sub=0x02: danh sach thanh vien guild.
        Format: [sub 2B=0200][guild_len 1B][guild_name UTF-16LE][01][count 1B]
                [entry: entity(8B) + name_len(1B) + name(UTF-16LE name_len B) + 32B extra] x count
        Chi xu ly sub=0x02; bo qua cac sub khac (0x09 la guild-join notify, khong co ten nhan vat).
        """
        if len(pkt) < 14:
            return
        payload = pkt[7:]
        sub = int.from_bytes(payload[0:2], 'little')
        if sub != 0x02:
            return
        # --- TEN NHAN VAT CUA MINH: quet truc tiep self_entity trong goi roi doc name ngay sau
        # (parser entry ben duoi tinh stride khong chuan -> bo sot self; cach nay chac chan) ---
        self._last_guild_pkt = pkt   # cache de 0x69 retry neu 0x27 toi TRUOC 0x69
        self._resolve_self_name(pkt)
        guild_len = payload[2]
        # entries bat dau sau: 2B(sub) + 1B(guild_len) + guild_len + 1B(unknown) + 1B(count) = guild_len+5
        entries_off = 3 + guild_len + 2
        if entries_off > len(payload):
            return
        off = entries_off
        parsed = 0
        while off + 9 <= len(payload):
            entity = payload[off:off + 8]
            name_len = payload[off + 8]
            if name_len == 0 or off + 9 + name_len > len(payload):
                break
            try:
                name = payload[off + 9:off + 9 + name_len].decode('utf-16-le')
            except Exception:
                name = ''
            if name:
                self.entity_names.setdefault(entity, set()).add(name)
                # Neu la entity CUA MINH -> dung lam ten nhan vat trong log
                if self.self_entity and entity == self.self_entity and self.char_name != name:
                    self.char_name = name
                    self._label = name
                    _register_party_name(self.self_entity, name)   # de leader tra ten member
                    log.info("[%s] Ten nhan vat = '%s'", self._username, name)
                log.debug("[%s] guild member: %s -> '%s'", self._label, entity.hex()[:12], name)
            off += 9 + name_len + 32
            parsed += 1
        if parsed:
            log.info("[%s] 0x27 parsed %d guild members (entity_names cap nhat)", self._label, parsed)

    # ---- lenh tien ich ----
    def switch_channel(self, channel: int):
        """Chuyen sang sub-channel (vd Di Gioi dong nguoi). C2S 0x07 = 02 00 [ch LE]."""
        self.send(0x07, b"\x02\x00" + struct.pack("<H", channel))
        log.info("[%s] Chuyen kenh -> %d", self._label, channel)

    def _on_channel_list(self, pkt: bytes):
        """S2C 0x07 list: payload = [01 00][count 1B][ block 6B: ch2 cur2 cap2 ]*count."""
        data = pkt[10:]   # bo header(6)+op(1)+ '01 00 count'(3)
        chans = {}
        for i in range(0, len(data) - 5, 6):
            ch, cur, cap = struct.unpack_from("<HHH", data, i)
            if 0 < ch < 1000 and cap > 0:
                chans[ch] = (cur, cap)
        if chans:
            self.channels = chans
            self._chan_event.set()
            log.info("[%s] Nhan danh sach %d kenh", self._label, len(chans))

    def request_channel_list(self):
        """Gui 0x07 0100 de server tra ve danh sach kenh + so nguoi."""
        self._chan_event.clear()
        self.channels = {}
        self.send(0x07, b"\x01\x00")

    def pick_best_channel(self, wait: float = 2.0, exclude=(1,), tries: int = 4, need: int = 1):
        """Hoi danh sach kenh -> chuyen sang kenh IT NGUOI nhat MA CON DU CHO cho CA PARTY.
        need = so acc cua party (kenh phai con >= need cho trong, neu khong ca party khong gom
        ve duoc 1 kenh -> 1 so acc bi ket o instance khac).
        exclude: bo qua kenh nao (vd kenh 1 thuong dong/mac dinh).
        Tra ve:
          0    = chi 1 kenh (khong co list / chi co kenh mac dinh) -> ca party DA cung kenh, GIU NGUYEN.
          None = co nhieu kenh NHUNG khong kenh nao du cho ca party -> caller nen RETRY (cho kenh trong).
          int  = da chuyen sang kenh it nguoi MA con du cho ca party."""
        for i in range(tries):
            if not self.running:
                return None
            self.request_channel_list()
            if self._chan_event.wait(wait):
                break
            log.info("[%s] Chua nhan duoc danh sach kenh, hoi lai (%d/%d)...",
                     self._label, i + 1, tries)
        else:
            # KHONG lay duoc list -> server chi co 1 kenh -> ca party DA o cung kenh (kenh 1).
            log.info("[%s] Khong co danh sach kenh -> chi 1 kenh, ca party da cung kenh -> giu nguyen",
                     self._label)
            return 0
        cand = [(ch, cur, cap) for ch, (cur, cap) in self.channels.items()
                if ch not in exclude]
        if not cand:
            log.info("[%s] Chi co kenh mac dinh -> giu nguyen (ca party cung kenh)", self._label)
            return 0
        # CHI chon kenh con DU CHO cho ca party (cap - cur >= need)
        fit = [c for c in cand if (c[2] - c[1]) >= need]
        if not fit:
            log.warning("[%s] KHONG kenh nao du %d cho trong cho ca party -> RETRY (cho kenh trong)",
                        self._label, need)
            return None
        best = min(fit, key=lambda c: c[1])   # it nguoi nhat trong cac kenh du cho
        log.info("[%s] Kenh it nguoi MA DU CHO ca party (%d): kenh %d (%d/%d) -> chuyen sang",
                 self._label, need, best[0], best[1], best[2])
        self.switch_channel(best[0])
        return best[0]

    def invite_entity(self, entity: bytes):
        """Moi 1 nguoi vao party BANG ENTITY. C2S 0x0d sub=07 = 07 00 [entity 8B].
        (Da xac nhan tu capture invite_dg.pcap - moi theo entity, KHONG phai index 0x52!)"""
        if not entity:
            return
        self.send(protocol.OP_PLAYER_STATE, b"\x07\x00" + bytes(entity))

    def invite_members(self, gap: float = 1.0):
        """Leader moi TAT CA entity member cung party (tru minh) bang 0x0d sub=07.
        Bot da biet entity member qua _PARTY_ENTITIES (chia se trong process khi login)."""
        ents = [e for e in _PARTY_ENTITIES.get(self.party_idx, set()) if e != self.self_entity]
        log.info("[%s] (LEADER) moi %d member theo entity: %s",
                 self._label, len(ents), [e.hex()[:8] for e in ents])
        for e in ents:
            self.invite_entity(e)
            time.sleep(gap)

    def leave_party(self):
        """Roi/giai tan party hien tai (de co the VAO DI GIOI - khong vao duoc khi dang trong party).
        Gui giai tan 0x0d sub=04 voi self_entity: neu minh la leader -> tan ca party;
        member -> server bo qua (vo hai). Goi cho MOI bot truoc khi vao DG de don party sot."""
        if not self.self_entity:
            return
        self.send(protocol.OP_PLAYER_STATE, b"\x04\x00" + self.self_entity)
        log.info("[%s] Roi/giai tan party cu (truoc khi vao DG)", self._label)

    def set_strategist(self, entity: bytes = None):
        """Set quan su (SP regen moi turn). C2S 0x0d sub=05 = 0d 05 00 [entity].
        entity=None -> dung self_entity (party 2 nguoi target ngam = nguoi con lai)."""
        ent = entity or self.self_entity
        if not ent:
            return
        self.send(protocol.OP_PLAYER_STATE, b"\x05\x00" + ent)
        log.info("[%s] Set quan su entity=%s", self._label, ent.hex()[:12])

    def set_party_strategist(self):
        """Leader set quan su -> SP regen cho party. CHON member da JOIN co INT CAO NHAT
        (INT cao = hoi SP tot hon khi lam quan su). Chua biet INT thi lay member dau tien."""
        joined = [e for e in _PARTY_JOINED.get(self.party_idx, set()) if e != self.self_entity]
        ents = joined or [e for e in _PARTY_ENTITIES.get(self.party_idx, set()) if e != self.self_entity]
        if not ents:
            log.warning("[%s] (LEADER) khong co member de set quan su", self._label)
            return
        best = best_int_member(self.party_idx, ents)
        chosen = best or ents[0]
        ival = _PARTY_INT.get(self.party_idx, {}).get(chosen)
        with _PARTY_LOCK:
            _PARTY_STRATEGIST[self.party_idx] = bytes(chosen)   # de GUI hien "quan su"
        self.set_strategist(chosen)
        nm = name_for_entity(chosen) or chosen.hex()[:8]
        log.info("[%s] (LEADER) set quan su = member '%s' (INT=%s)%s",
                 self._label, nm, ival,
                 "" if best else " [chua biet INT -> chon dau tien]")

    def increase_stat(self, stat_id: int, amount: int = 1):
        """Tang 1 chi so. C2S 0x08 = 01 00 00 00 [stat_id] [amount] 00 00 00 00
        (xac nhan tu int.pcap: tang INT id=0x1b). Dung cho auto cong diem sau nay."""
        self.send(0x08, b"\x01\x00\x00\x00" + bytes([stat_id & 0xFF, amount & 0xFF]) + b"\x00\x00\x00\x00")
        log.info("[%s] Tang stat id=0x%02x +%d", self._label, stat_id, amount)

    def move_to(self, x: int, y: int):
        """C2S 0x06: di chuyen nhan vat toi (x,y). Server tu di toi do.
        Dead-reckoning: server KHONG echo vi tri minh -> tu nho pos = diem vua gui di."""
        self.send(0x06, b"\x01\x00\x01" + struct.pack("<HH", x, y))
        self.pos = (x, y)

    def navigate_to(self, x: int, y: int, moves_needed: int = None, step: float = 1.5,
                    max_iter: int = 80):
        """Di chuyen toi (x,y) tren map thuong; dinh battle giua duong -> BO CHAY (flee_mode) roi
        di tiep. game DI TUNG BUOC (move_to chi tien 1 doan ngan moi lan) -> diem XA can NHIEU buoc.
        moves_needed=None -> tu tinh theo KHOANG CACH (tu self.pos): ~100px/buoc, clamp [4, 30].
        (Truoc day cung 4 buoc -> diem xa khong toi -> ket giua duong, khong co quai.)
        Dung in_combat nguong NGAN (1.5s). KHONG tu tat flee_mode - caller quan ly."""
        import math
        if moves_needed is None:
            if self.pos:
                dist = math.hypot(x - self.pos[0], y - self.pos[1])
                moves_needed = max(4, min(30, int(dist / 100) + 2))
            else:
                moves_needed = 30   # khong biet vi tri (vd vua qua cong) -> di hao phong cho chac toi
        self.flee_mode = True
        moves = 0
        for _ in range(max_iter):
            if not self.running:    # bi STOP -> dung di chuyen
                return
            if self.in_combat(idle_secs=1.5):   # dang battle/vua co luot -> cho flee xong
                time.sleep(0.5)
                continue
            self.move_to(x, y)
            moves += 1              # CONG DON (khong reset du bi battle xen giua)
            time.sleep(step)
            if moves >= moves_needed:
                break
        self.pos = (x, y)
        log.info("[%s] da toi diem (%d,%d) sau %d buoc", self._label, x, y, moves)

    def follow_path(self, waypoints, step: float = 1.0, flee: bool = True):
        """Di bo theo CHUOI WAYPOINT (capture duong di THAT trong map) toi diem quai xa.
        Moi waypoint move_to + cho HET TRAN roi di tiep.
        flee=True: ne quai (di nhanh, khong ton SP). flee=False: party DU NGUOI -> DANH quai gap
        tren duong (flee party-battle hay bi TREO -> ca party chet, nen co party thi danh thang hon).
        Dung khi navigate thang KHONG toi duoc (dia hinh/cap khoang cach). Replay tung buoc nho."""
        if not waypoints:
            return
        self.flee_mode = bool(flee)
        log.info("[%s] follow_path: %d waypoint -> (%s) [%s]", self._label, len(waypoints),
                 waypoints[-1], "FLEE" if flee else "DANH")
        for wx, wy in waypoints:
            if not self.running:
                return
            # CHO THOAT TRAN HOAN TOAN (flee xong) TRUOC khi di tiep - KHONG move giua battle
            # (move giua tran pha luot flee). idle_secs cao de khong nham battle co khoang nghi.
            t0 = time.time()
            while self.in_combat(idle_secs=3.0):
                if not self.running or time.time() - t0 > 60:
                    break
                time.sleep(0.5)
            self.move_to(int(wx), int(wy))
            time.sleep(step)
        self.pos = tuple(waypoints[-1])
        log.info("[%s] follow_path xong -> %s", self._label, self.pos)

    def in_di_gioi(self) -> bool:
        """Dang o map Di Gioi? Doc map_id thuc te (khong dua vao so kenh)."""
        return self.current_map == config.DIGIOI_MAP_ID

    def _left_di_gioi(self) -> bool:
        """Da ra khoi Di Gioi chua (map_id da khac Di Gioi)."""
        return self.current_map is not None and self.current_map != config.DIGIOI_MAP_ID

    def exit_di_gioi(self, step_wait: float = 2.0):
        """Di Gioi KHONG co lenh thoat: phai DI BO tung buoc nho toi CONG (270,210).
        Replay DUNG chuoi buoc THAT tu capture (cac buoc ~50-110px, da chung minh hop le)
        + cho step_wait giay moi buoc cho nhan vat di toi noi. Toi cong -> map tu doi.
        Kiem tra thoat bang map_id THAT (khong dua so kenh)."""
        log.info("[%s] Thoat Di Gioi: di bo tung buoc toi cong (270,210)...", self._label)
        # chuoi buoc THAT tu exit_new.pcap (x,y)
        steps = [(738, 648), (682, 609), (625, 569), (570, 530),
                 (462, 411), (417, 360), (390, 330)]
        for _ in range(3):   # lap lai vai vong neu chua ra
            for x, y in steps:
                self.move_to(x, y)
                time.sleep(step_wait)
            self.send(0x14, bytes.fromhex("04000100")); time.sleep(0.8)
            self.move_to(270, 210);                     time.sleep(step_wait)
            self.send(0x14, bytes.fromhex("08000100")); time.sleep(0.8)
            self.send(0x0c, bytes.fromhex("0100"));     time.sleep(0.5)
            self.send(0x14, bytes.fromhex("0600"));     time.sleep(1.5)
            if self._left_di_gioi():
                log.info("[%s] Da THOAT Di Gioi -> map %s", self._label, self.current_map)
                return True
        log.warning("[%s] Van chua thoat duoc Di Gioi (map %s)", self._label, self.current_map)
        return False

    def start_run_around(self, stay_in_di_gioi=True):
        """Bat auto run-around: chay vong quanh DIEM DANG DUNG (anchor = vi tri hien tai)
        + offset hinh so 8. Dung quanh quai -> battle -> het tran chay tiep. Chay nen."""
        if self._running_route:
            return
        self._running_route = True
        threading.Thread(target=self._run_around_loop, args=(stay_in_di_gioi,), daemon=True).start()

    def stop_run_around(self):
        self._running_route = False

    def _run_around_loop(self, stay_in_di_gioi):
        if not getattr(config, "RUN_AROUND_OFFSETS", []):
            self._running_route = False
            return
        # Anchor = vi tri hien tai (dead-reckoning: set khi vao Di Gioi / lenh move cuoi).
        # Server KHONG echo vi tri minh -> dua vao pos tu nho. Chua biet -> fallback spawn Di Gioi.
        anchor = self.pos or getattr(config, "RUN_FALLBACK_ANCHOR", (870, 740))
        ax, ay = anchor
        log.info("[%s] Run-around quanh (%d,%d)", self._label, ax, ay)
        i = 0
        while self.running and self._running_route:
            # neu (co ve) da roi DG -> TAM DUNG, KHONG break (phong doc nham map nguoi khac:
            # map se flip lai DG -> chay tiep; neu roi that su -> pause vo hai). map=None -> cu chay.
            if stay_in_di_gioi and self.current_map is not None and self.current_map != config.DIGIOI_MAP_ID:
                time.sleep(1.0)
                continue
            if self.in_combat(getattr(config, "RUN_RESUME_IDLE", 2.0)):
                # dang danh -> TAM DUNG di chuyen, GIU nguyen diem dang di.
                # nguong 2.0s (thay 4.0) -> het tran resume nhanh hon; van an toan vi co logic
                # "khong tang i khi bi gian doan" + move giua tran bi server bo qua.
                time.sleep(0.3)
                continue
            offsets = getattr(config, "RUN_AROUND_OFFSETS", []) or [(0, 0)]   # doc lai moi vong (tune live)
            dx, dy = offsets[i % len(offsets)]
            self.move_to(ax + dx, ay + dy)
            # cho char di toi diem; neu GIUA CHUNG vao combat -> KHONG tang i (lan sau gui lai diem nay,
            # tranh "bo diem/di tat"). Chi sang diem ke khi di tron 1 buoc khong bi gian doan.
            wait = getattr(config, "RUN_STEP_WAIT", 0.8)
            interrupted = False
            slept = 0.0
            while slept < wait:
                step = min(0.1, wait - slept)
                time.sleep(step); slept += step
                if self.in_combat():
                    interrupted = True
                    break
            if not interrupted:
                i += 1
        self._running_route = False
        log.info("[%s] Dung run-around", self._label)

    def enter_di_gioi(self):
        """Vao map Di Gioi (map train chinh). Chi 2 goi co dinh: 0x61 010001 -> 0x61 020002.
        LUU Y: KHONG vao duoc khi dang trong party."""
        self.send(0x61, bytes.fromhex("010001"))   # mo/load zone Di Gioi
        log.info("[%s] Vao Di Gioi: gui 0x61 010001", self._label)
        time.sleep(1.5)                              # cho server load zone
        self.send(0x61, bytes.fromhex("020002"))   # xac nhan vao
        # spawn Di Gioi co dinh -> set pos (server khong echo, dung dead-reckoning tu day)
        self.pos = getattr(config, "RUN_FALLBACK_ANCHOR", (870, 740))
        log.info("[%s] Vao Di Gioi: gui 0x61 020002 (xong), spawn pos=%s", self._label, self.pos)

    def enter_di_gioi_safe(self, tries: int = 12, wait: float = 3.0) -> bool:
        """Vao DI GIOI co retry, ne 2 case fail:
          - current_map=None  -> CHUA vao world xong (login chua xong) -> cho.
          - in_combat()       -> dang KET BATTLE (login ngay bai quai) -> cho het tran (battle chan vao DG).
        Gui 0x61 khi san sang, lap lai cho toi khi in_di_gioi()=True."""
        for i in range(tries):
            if not self.running:        # bi STOP (GUI/close) -> thoat ngay
                return False
            if self.in_di_gioi():
                return True
            if self.current_map is None:
                log.info("[%s] cho vao world xong (map chua co)... (%d)", self._label, i + 1)
                time.sleep(wait); continue
            if self.in_combat():
                log.info("[%s] dang ket battle -> cho het tran roi vao DG... (%d)", self._label, i + 1)
                time.sleep(wait); continue
            self.enter_di_gioi()
            time.sleep(wait)
            if self.in_di_gioi():
                log.info("[%s] da VAO DI GIOI (map=%s)", self._label, self.current_map)
                return True
        log.warning("[%s] VAO DI GIOI THAT BAI sau %d lan (map=%s, combat=%s) "
                    "-> nhieu kha nang HET GIO DI GIOI hom nay",
                    self._label, tries, self.current_map, self.in_combat())
        return False

    def go_to_town(self, city_id: int, flag: int = 0, tries: int = 30, wait: float = 2.0):
        """Teleport ve thanh, LAP LAI cho toi khi RA KHOI map hien tai (neu dang o bai quai/
        battle thi teleport bi chan, phai cho khoang trong giua 2 tran). Xac nhan = map da doi
        (city_id != map_id voi 1 so thanh nhu Ng.Thanh, nen check 'da roi map cu')."""
        log.info("[%s] Ve thanh %d (lap lai neu con battle chan teleport)...", self._label, city_id)
        # Dang o DI GIOI -> teleport (0x44) bi tu choi. PHAI di bo ra cong thoat truoc.
        if self.in_di_gioi():
            log.info("[%s] Dang o Di Gioi -> di bo ra cong thoat truoc khi teleport ve thanh...",
                     self._label)
            self.exit_di_gioi()
        ok = 0
        deadline = time.time() + tries * wait + 90   # +90s du cho thoat battle (khong tinh vao luot teleport)
        while time.time() < deadline:
            if not self.running:    # STOP / mat ket noi -> NGUNG ngay (khong spam teleport nua)
                log.info("[%s] go_to_town: dung (stop/disconnect)", self._label)
                return False
            # DANG VAO PHO BAN (vua nhan loi moi) -> NGUNG teleport ve thanh, de bot THEO + DANH
            # pho ban (tranh spam teleport + flee do xung dot voi 'city mode keo ve thanh').
            if time.time() < getattr(self, "_phoban_until", 0):
                log.info("[%s] go_to_town: dang vao pho ban -> ngung teleport (theo + danh pho ban)",
                         self._label)
                self.flee_mode = False
                return False
            # DANG BATTLE -> teleport bi chan, va spam teleport luc battle PHA luot FLEE
            # (char mat luot, khong chay duoc -> bi danh chet). -> BAT flee, CHO thoat tran roi teleport.
            # idle_secs=4.0 (KHONG phai 1.5): nhip luot flee ~2-3s, neu 1.5 thi giua 2 luot doc
            # nham "het tran" -> teleport chen giua -> pha flee -> tran khong bao gio ket thuc.
            if self.in_combat(idle_secs=4.0):
                self.flee_mode = True
                time.sleep(1.0)
                continue
            self.teleport(city_id, flag)
            # cho 'wait' giay NHUNG van check stop/battle moi 0.2s
            end = time.time() + wait
            while time.time() < end:
                if not self.running:
                    return False
                if self.in_combat(idle_secs=1.5):
                    break   # vao tran giua chung -> ngung cho, quay lai xu ly flee
                time.sleep(0.2)
            if self.current_map == city_id:
                ok += 1
                if ok >= 2:   # 2 lan lien tiep == city_id -> on dinh (tranh nhieu luc chuyen map)
                    log.info("[%s] Da ve thanh %d", self._label, city_id)
                    return True
            else:
                ok = 0
        log.warning("[%s] Chua ve duoc thanh %d (map=%s)", self._label, city_id, self.current_map)
        return False

    def teleport(self, city_id: int, flag: int = 0):
        """flag bat buoc dung dung cho tung thanh (xem cities.json)."""
        payload = b"\x01\x00" + struct.pack("<H", city_id) + bytes([flag])
        self.send(protocol.OP_TELEPORT, payload)
        log.info("[%s] Teleport -> city %s (flag %s)", self._label, city_id, flag)

    def _wait_combat_clear(self, idle: float = 3.0, cap: float = 90.0) -> bool:
        """Cho HET TRAN (khong co luot battle trong 'idle' giay) toi 'cap' giay.
        Tra False neu bi STOP/rot. Dung truoc khi move/transit (battle NUOT lenh 0x06/0x14)."""
        t0 = time.time()
        while self.in_combat(idle_secs=idle) and self.running and time.time() - t0 < cap:
            time.sleep(0.5)
        return self.running

    def _route_move(self, x: int, y: int, settle: float = 0.6, tries: int = 8):
        """Di 1 buoc route AN TOAN: cho het tran -> move -> neu vua move lai dinh tran
        (battle nuot lenh -> nhan vat KHONG toi noi) thi cho het tran roi MOVE LAI.
        Bao dam nhan vat thuc su toi (x,y) truoc khi sang buoc/cong sau."""
        for _ in range(tries):
            if not self.running:
                return
            if not self._wait_combat_clear():
                return
            self.move_to(x, y); time.sleep(settle)
            if not self.in_combat(idle_secs=1.5):
                return   # move xong, khong dinh tran -> coi nhu da toi

    def _enter_gate(self, x: int, y: int, idx: int, timeout: float = 60.0) -> bool:
        """Toi cong (x,y) + gui chuoi 0x14 04/08[idx] (giong thoat Di Gioi) -> cho MAP DOI.
        Cong trung gian khong biet map dich nen xac nhan = current_map khac map luc bat dau.
        QUAN TRONG: chi move toi cong + gui transit khi HET TRAN. Neu gui 0x06/0x14 luc dang
        battle -> server nuot lenh (khong toi cong) hoac DA ket noi -> ket cong / leader rot."""
        start_map = self.current_map
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.running:
                return False
            if self.current_map is not None and self.current_map != start_map:
                log.info("[%s] qua cong idx=%d -> map %s", self._label, idx, self.current_map)
                self.pos = None   # qua cong -> vi tri cu vo nghia (map moi) -> navigate sau di hao phong
                return True
            # CHO HET TRAN truoc khi toi cong + transit (battle nuot lenh -> ket cong / kick leader).
            # idle=6.0 (KHONG dung 3s mac dinh): khoang NGHI GIUA 2 LUOT battle co the 3-4s -> idle ngan
            # bi danh lua "het tran" -> transit giua tran -> SERVER KICK (vd leader vang o bai quai).
            if not self._wait_combat_clear(idle=6.0):
                return False
            if x or y:   # x=y=0 -> cong "vao lien" (spawn ngay tai cong) -> KHONG move, chi trigger
                self.move_to(x, y)
            # Dung tai cong: cho 0x35 (battle offer) kip den neu buoc vao quai. idle=6.0 de chac chan
            # het tran (khong nham khoang nghi giua luot). Co tran -> loop lai danh het roi moi transit.
            time.sleep(1.5)
            if self.in_combat(idle_secs=6.0):
                continue   # con trong tran (hoac vua dinh tran) -> fight het roi moi transit
            # transit: bat flag de combat (luong recv) KHONG gui 0x32 xen vao giua chuoi 0x14
            self._gate_transit = True
            try:
                self.send(0x14, b"\x04\x00" + bytes([idx]) + b"\x00"); time.sleep(0.3)
                self.send(0x14, b"\x08\x00" + bytes([idx]) + b"\x00"); time.sleep(0.3)
                self.send(0x0c, b"\x01\x00"); time.sleep(0.2)
                self.send(0x14, b"\x06\x00"); time.sleep(1.0)
            finally:
                self._gate_transit = False
        log.warning("[%s] _enter_gate idx=%d @(%d,%d): map khong doi (van %s)",
                    self._label, idx, x, y, self.current_map)
        return False

    def follow_route(self, route, step_wait: float = 0.5) -> bool:
        """Replay route tu THANH toi train map. route = {from_city, city_flag, dest_map, steps}.
        steps: {"move":[x,y]} = di 1 buoc | {"gate":idx,"x","y"} = toi cong roi gui 0x14.
        Bot CHI leader can goi (member tu bi keo theo trong party). Tra True neu toi dest_map."""
        dest = int(route.get("dest_map", 0))
        city = int(route.get("from_city", 0))
        flag = int(route.get("city_flag", 0))
        log.info("[%s] follow_route -> map %s (qua thanh %s flag %s)", self._label, dest, city, flag)
        self.flee_mode = True
        if city and not self.go_to_town(city, flag):
            log.warning("[%s] follow_route: khong teleport ve thanh %s duoc", self._label, city)
            return False
        for st in route.get("steps", []):
            if not self.running:
                return False
            if "gate" in st:
                if not self._enter_gate(int(st["x"]), int(st["y"]), int(st["gate"])):
                    log.warning("[%s] follow_route: ket o cong idx=%s -> dung", self._label, st.get("gate"))
                    return False
            else:
                x, y = int(st["move"][0]), int(st["move"][1])
                self._route_move(x, y)   # cho het tran roi move (battle nuot lenh -> khong toi)
        ok = self.current_map == dest
        log.info("[%s] follow_route xong: map=%s (dich %s) -> %s",
                 self._label, self.current_map, dest, "OK" if ok else "CHUA TOI")
        return ok
