"""Cau hinh bot TS Online - BAN MAU.
Copy file nay thanh `config.py` roi dien thong tin that. config.py da bi gitignore.
"""
from ._appdir import app_dir as _base_dir   # thu muc goc (dev=project, frozen=canh .exe)
import json
import os

TEAM_DUNGEON_LEVELS = (20, 50, 80, 110)
DEFAULT_TEAM_DUNGEONS = {20: True, 50: True, 80: True, 110: False}
SHOP_ITEM_KEYS = ("ho_phu", "thien_chau", "bao_hop")
DEFAULT_SHOP_ITEMS = {"ho_phu": False, "thien_chau": False, "bao_hop": False}


def normalize_team_dungeons(value):
    out = dict(DEFAULT_TEAM_DUNGEONS)
    if isinstance(value, dict):
        for lv in TEAM_DUNGEON_LEVELS:
            if str(lv) in value:
                out[lv] = bool(value.get(str(lv)))
            elif lv in value:
                out[lv] = bool(value.get(lv))
    elif isinstance(value, (list, tuple, set)):
        enabled = {int(x) for x in value if str(x).isdigit()}
        for lv in TEAM_DUNGEON_LEVELS:
            out[lv] = lv in enabled
    return out


def normalize_shop_items(value, legacy=None):
    out = dict(DEFAULT_SHOP_ITEMS)
    if isinstance(legacy, dict):
        for key in SHOP_ITEM_KEYS:
            if key in legacy:
                out[key] = bool(legacy.get(key))
    if isinstance(value, dict):
        for key in SHOP_ITEM_KEYS:
            if key in value:
                out[key] = bool(value.get(key))
    elif isinstance(value, (list, tuple, set)):
        enabled = {str(x) for x in value}
        for key in SHOP_ITEM_KEYS:
            out[key] = key in enabled
    return out


TRAIN_MAPS_PATH = os.path.join(_base_dir(), "train_maps.json")

# Tai khoan mac dinh (single bot)
USERNAME = "your_username"
PASSWORD = "your_password"

# ==== DANH SACH PARTY ====
# Moi party = 1 list toi da 5 acc (username, password) - pass co the khac nhau.
# SLOT 0 = CHU PARTY (bot tu moi + dan train). ("","") = khong co bot-leader (chi member).
PARTIES = [
    [   # Party 1
        ("acc1", "password1"),
        ("acc2", "password2"),
        ("acc3", "password3"),
        ("acc4", "password4"),
        ("acc5", "password5"),
    ],
    # [   # Party 2
    #     ("acc6", "password6"), ...
    # ],
]

# Whitelist TEN NHAN VAT ngoai party:
# - Neu party KHONG co bot-leader: bot dung yen va chi nhan loi moi tu cac ten nay (rong = nhan bat ky).
# - Neu party CO bot-leader va mode train: moi cac ten dang dung xung quanh TRUOC bot member.
#   Acc ngoai vao hay khong khong anh huong flow bot.
PARTY_LEADERS = []  # vi du: ["chihao", "haabo", "nasau"]

# API login - API_KEY la HANG SO co dinh cua game, KHONG can sua.
# (device_id & tracking_id duoc login.py tu sinh tu username -> khong can dien)
API_KEY = "17ade453e0892461edb01969b6e17e3a"
LOGIN_URL = f"https://graph.mobiplay.vn/accountapiv4/server/login?api_key={API_KEY}"

# Game server TCP - co dinh, KHONG can sua
GAME_HOST = "103.82.28.98"
GAME_PORT = 6614

# ==== TOOL TREO MAY (bot_standalone.py) - chi can quan tam phan nay ====
LEADER_NAME = "ten_chu_party"   # ten chu party (tham khao/log)

# START_CITY_ID: thanh ve sau khi login. 12061=Ng.Thanh | 12001=Trac Quan | 12011=Cu Loc
#   = 0  -> KHONG teleport: dung yen tai cho login (van chuyen CHANNEL, van tu danh khi vao tran).
#   = MAP ID trung voi map LUC LOGIN -> vao che do PARTY-TRAIN tren map do (chay toi TRAIN_SAFE,
#     dong bo kenh, moi party, leader ra TRAIN_MOB_SPOTS dung cay). Xem log "MAP HIEN TAI" luc login.
START_CITY_ID = 12061
# Data map party-train doc tu train_maps.json (map_id -> {safe, mobs}).
#   START_CITY_ID CO trong data  -> MAP-TRAIN (chay toi safe, lap party, ra mobs cay)
#   START_CITY_ID == DIGIOI_MAP_ID -> train Di Gioi (run-around)
#   con lai -> dung i tai cho
def _load_train_maps():
    import json, os
    f = TRAIN_MAPS_PATH
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("maps", {}).items():
            s = v["safe"]
            # safe = [[x,y],...] (nhieu diem) HOAC [x,y] (1 diem, format cu) -> chuan hoa LIST diem
            if not s:
                safes = []
            elif isinstance(s[0], (list, tuple)):
                safes = [tuple(p) for p in s]
            else:
                safes = [tuple(s)]
            out[int(k)] = {"safe": safes, "mobs": [tuple(m) for m in v.get("mobs", [])],
                           "name": v.get("name", k),
                           "group": (v.get("group") or "Chưa phân nhóm")}
    except Exception:
        pass
    return out
TRAIN_MAPS = _load_train_maps()
def _load_teleport_cities(path=None):
    """Doc cities.json -> {city_id:int -> {flag, name}}. Chi cac id nay duoc dung voi opcode teleport."""
    import json, os
    f = path or os.path.join(_base_dir(), "cities.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        for key, value in data.get("cities", data).items():
            city_id = int(value.get("city_id", 0))
            if city_id:
                out[city_id] = {
                    "flag": int(value.get("flag", 0)),
                    "name": value.get("name", key),
                }
    except Exception:
        pass
    return out
TELEPORT_CITIES = _load_teleport_cities()
TELEPORT_CITY_IDS = set(TELEPORT_CITIES)
def is_teleport_city(city_id):
    try:
        return int(city_id) in TELEPORT_CITY_IDS
    except Exception:
        return False
def _load_map_gates(path=None):
    """Doc map_gates.json -> {map_id:int -> [(x,y,to), ...]} (do thi cong di chuyen).
    Khong co file/loi -> {}. Dung cho pathfind.find_path (auto di toi train map)."""
    import json, os
    f = path or os.path.join(_base_dir(), "map_gates.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("maps", {}).items():
            out[int(k)] = [(int(g["x"]), int(g["y"]), int(g["to"])) for g in v.get("gates", [])]
    except Exception:
        pass
    return out
MAP_GATES = _load_map_gates()

# Smart path trong map. Neu Ground.mmg khong ton tai, navigate_to tu fallback cach cu.
SMART_PATHFIND = True
GROUND_MAP_PATH = os.path.join(_base_dir(), "gamedata", "Ground.mmg")
SCENE_FIGHT_PATH = os.path.join(_base_dir(), "gamedata", "SceneFight_C.dat")
SMART_WORLD_ROUTING = True
WORLD_NAV_PATH = os.path.join(_base_dir(), "world_nav.json")
SMART_ROUTE_CACHE_PATH = os.path.join(_base_dir(), "smart_routes.json")
SMART_ROUTE_FALLBACK = True
SMART_PATH_STEP_WAIT = 0.55     # giay giua 2 lenh move khi co Ground.mmg path (giam = chay muot hon)
SMART_PATH_SEGMENT = 100        # px toi da moi lenh move smart path; chia nho de khong spam 1 diem cua
MOB_SCAN_ENABLED = True
MOB_SCAN_STATION_STRIDE = (320, 240)
MOB_SCAN_QUIET_SECONDS = 8.0
MOB_SCAN_STATION_TIMEOUT = 90.0
MOB_SCAN_MIN_SAMPLES = 3
MOB_SCAN_MAX_PATROL_DIAMETER = 800
# KHONG con dung de gom bai quai nua (compute_centers/compute_regions gio la 1 CON = 1 BAI,
# lay TAM BBOX o vuong tuan tra). Chi con dung o _merge_center_points (scan_full_map) de bo
# tam trung nhau. Giu 60 - do tren capture map 20801: gom theo khoang cach lam mat rat nhieu
# bai (200 -> 7/16 bai; bo gom han -> dung 16/16).
MOB_SCAN_MERGE_DISTANCE = 60
MOB_SCAN_SECOND_PASS = True
MOB_SPOTS_CACHE_PATH = os.path.join(_base_dir(), "mob_spots.json")
MOB_PACKET_PROBE_SECONDS = 60
MOB_PACKET_CAPTURE_MAX_PACKETS = 50000
MOB_PACKET_CAPTURE_DIR = _base_dir()
def _load_train_routes(path=None):
    """Doc train_routes.json -> {dest_map:int -> {from_city, city_flag, dest_map, steps}}.
    Route replay tu thanh toi train map (leader di, member tu keo theo)."""
    import json, os
    f = path or os.path.join(_base_dir(), "train_routes.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("routes", {}).items():
            out[int(k)] = v
    except Exception:
        pass
    return out
TRAIN_ROUTES = _load_train_routes()
def _load_events(path=None):
    """Doc events.json -> {event_key -> {label, select, staging_map, dest_map, steps}}.
    Mode 'event': tele toi map event roi dung yen (moi nick tu teleport rieng)."""
    import json, os
    f = path or os.path.join(_base_dir(), "events.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).get("events", {}).items():
                out[k] = v
    except Exception:
        pass
    return out
EVENTS = _load_events()
def _load_mob_paths(path=None):
    """Doc mob_paths.json -> {map_id:int -> {(sx,sy):tuple -> [(x,y),...]}}.
    Duong di bo TRONG map toi diem quai XA (capture) - bot replay thay navigate thang."""
    import json, os
    f = path or os.path.join(_base_dir(), "mob_paths.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for mk, spots in d.get("maps", {}).items():
            mp = {}
            for sk, wps in spots.items():
                sx, sy = (int(v) for v in sk.split(","))
                mp[(sx, sy)] = [(int(p[0]), int(p[1])) for p in wps]
            out[int(mk)] = mp
    except Exception:
        pass
    return out
MOB_PATHS = _load_mob_paths()
START_CITY_FLAG = 2             # Ng.Thanh=2, Trac Quan=0, Cu Loc=3 (xem cities.json)
CHANNEL = 1                     # kenh can o cung voi chu party (0 = bo qua)
RECONNECT_DELAY = 10            # giay cho truoc khi ket noi lai khi bi rot
ENTER_DIGIOI = False            # True = sau khi connect tu vao Di Gioi train (solo, KHONG party)
DIGIOI_MAP_ID = 49942           # map_id Di Gioi (0xc316) - doc tu broadcast de biet dang o Di Gioi
# Auto run-around: chay vong quanh DIEM DANG DUNG (offset tuong doi). Hinh so 8 (tu game auto-run).
RUN_AROUND_OFFSETS = [(-100, -100), (-200, 0), (-100, 100), (0, 0),
                      (100, -100), (200, 0), (100, 100), (0, 0)]
RUN_STEP_WAIT = 0.7            # giay moi buoc chay vong Di Gioi (giam = chay nhanh hon; <0.1 de bi flood/kick)

# Solo daily dungeon: so luot/ngay (luot 1 mien phi, luot 2+ MUA bang vang). =1 chi danh luot free.
DUNGEON_RUNS_PER_DAY = 2

# Van tieu (escort): moi ngay 3 luot, gui pet di -> 1h sau nhan qua.
# VANTIEU_PETS = vi tri pet trong list QUAN TRO de gui (index 1-based), 1 pet/luot.
#   vd [1,2,3] = gui pet thu 1,2,3 cho 3 luot. [] = KHONG tu gui (chi nhan qua).
VANTIEU_ENABLE = True
VANTIEU_PETS = [1, 2, 3]
# Smart match (phase-2): ten pet trong QUAN TRO theo DUNG THU TU slot (slot1, slot2,...).
# Bot tra he/doanh tung con (PET_HEDOANH) -> chon con KHOP yeu cau nhat -> gui. [] = tat (dung VANTIEU_PETS).
VANTIEU_PETS_NAMES = []

# Phase-2 van tieu match: he/doanh pet (tu game data Npc_C.dat) + yeu cau (ma 0400).
def _load_json_root(fn):
    import json, os
    f = os.path.join(_base_dir(), fn)
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}
PET_HEDOANH = _load_json_root("pet_hedoanh.json")                       # ten pet -> {he, doanh}
VANTIEU_REQUESTS = _load_json_root("vantieu_requests.json").get("requests", {})  # ma 0400 -> {he, doanh}
VANTIEU_DISPATCH_EFFECTS = _load_json_root("vantieu_dispatch_bonus.json").get("effects", {})  # effect id -> {he|doanh}

# Qua online: id qua = so phut moc; thoi gian/da nhan doc tu server RoleCount+BitFlag.
GIFT_MILESTONES = [10, 20, 30, 60, 90, 180]

# Combat tuning
HEAL_HP_THRESHOLD = 0.70    # ally HP <= 70% max -> Toan Tri Lieu
HEAL_SP_COST = 42
SP_RESTORE_THRESHOLD = 0.5  # quest: cast Toan Hoi Ma (hoi SP team) khi co dong doi SP < 50% max
SUPPORT_RESERVE_SP = 100    # quest: unit CO skill hoi (hoi sinh/11010/11009) chi danh skill atk khi SP>100 (duoi -> danh thuong de danh SP)
PET_FIRE_MIN_SP = 65        # combo (Hoa Tien/Nem Da/Loan Kich): SP < 65 -> danh thuong

# DATA PET: doc tu pets.json (AUTO-SINH tools/crack_pets.py). pet_id hex -> name + skills (LIST,
# giu thu tu: skill[0]=boss fallback) + (he,doanh). boss/combo TU SUY o combat tu SKILL_INFO.
def _load_pets():
    import json, os
    f = os.path.join(_base_dir(), "pets.json")
    skills, names, hedoanh = {}, {}, {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("pets", {}).items():
            pid = int(k, 16)
            skills[pid] = list(v.get("skills", []))   # LIST (giu thu tu cho boss skill[0])
            names[pid] = v.get("name", "")
            if v.get("he") or v.get("doanh"):   # he/doanh (cho VAN TIEU match)
                hedoanh[pid] = (v.get("he", ""), v.get("doanh", ""))
    except Exception:
        pass
    return skills, names, hedoanh
PET_SKILLS, PET_NAMES, PET_HE_DOANH = _load_pets()   # pet_id -> skills/ten/(he,doanh)


# DAC KY RIENG cua vo tuong (NpcData [35] 武將特有技) - AUTO-SINH tools/crack_npc_special_skill.py.
# CHI duoc dung khi CON PET DO da MO dac ky (co specialSkillLearned, doc tu goi pet list ->
# client.pet_special_skill). Client kiem tra DUNG hai dieu kien nay (RoleController.lua:4786).
def _load_pet_special_skill():
    import json, os
    f = os.path.join(_base_dir(), "npc_special_skill.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in (json.load(fh).get("skills") or {}).items():
                out[int(k, 16)] = int(v)
    except Exception:
        pass
    return out
PET_SPECIAL_SKILL = _load_pet_special_skill()   # pet_id -> skill_id dac ky (chua chac da mo)

# DATA TEN QUAI/NPC: doc tu npc_names.json (AUTO tools/crack_npc_names.py). template_id -> ten.
# Dung tra TEN QUAI trong battle (entity[2:4] = template_id) cho dieu kien skill 'quai khoang'
# (ten bat dau bang 'Khoang ') va sau nay 'NPC nguy hiem' (ten thuoc list cau hinh).
def _load_npc_names():
    import json, os
    f = os.path.join(_base_dir(), "npc_names.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.items():
            tid = int(k, 16) if isinstance(k, str) and k.lower().startswith("0x") else int(k)
            out[tid] = v
    except Exception:
        pass
    return out
NPC_NAMES = _load_npc_names()   # template_id (int) -> ten quai/npc

# TEN MAP THEO GAME: doc tu scene_names.json (AUTO tools/crack_scene_names.py, boc tu
# Data/SceneSet_C.dat + Data/TextData_C.dat cua client). map_id -> ten hien thi trong game
# (vd 12924 -> "Thang Thap", 12934 -> "Dinh Thap"). Dung cho log/UI cho de doc.
def _load_scene_names():
    import json, os
    try:
        with open(os.path.join(_base_dir(), "scene_names.json"), encoding="utf-8") as fh:
            return {int(k): v for k, v in json.load(fh).items()}
    except Exception:
        return {}
SCENE_NAMES = _load_scene_names()   # map_id (int) -> ten map theo game


def map_display_name(map_id):
    """Ten map de HIEN THI (GUI/APK): ten theo game + so tang neu la thap event.

    Thap 2K: 12924..12938 deu ten "Thang Thap" -> khong biet dang o tang may. Them so tang
    (suy tu party_battle.floor_base cua event) -> "Thang Thap 8". Map khac tra ten theo game.
    """
    try:
        mid = int(map_id)
    except (TypeError, ValueError):
        return str(map_id)
    nm = SCENE_NAMES.get(mid)
    if not nm:
        return str(mid)
    for ev in (EVENTS or {}).values():
        pb = (ev or {}).get("party_battle") or {}
        if pb.get("kind") != "floor_crawl":
            continue
        base = int(pb.get("floor_base") or 0)
        top = int(pb.get("top_map") or 0)
        if base and top and base < mid <= top:
            return "%s %d" % (nm, mid - base)
    return nm


def scene_name(map_id, with_id=True):
    """Ten map theo game: 'Thang Thap (12924)'. Khong biet ten -> tra chinh map id."""
    try:
        mid = int(map_id)
    except Exception:
        return str(map_id)
    nm = SCENE_NAMES.get(mid)
    if not nm:
        return str(mid)
    return "%s (%d)" % (nm, mid) if with_id else nm


DEFAULT_DANGEROUS_NPC_NAMES = [
    "Chu Công",
    "Hằng Nga",
    "Gia Cát Lượng",
    "Tư Mã Ý",
    "Lục Tốn",
    "Bàng Thống",
    "Lữ Bố",
    "Trần Cung",
]


def _dangerous_npcs_path():
    return os.path.join(_base_dir(), "dangerous_npcs.json")


def normalize_dangerous_npc_names(value):
    if isinstance(value, dict):
        value = value.get("names", [])
    out = []
    if isinstance(value, str):
        value = value.replace(",", "\n").splitlines()
    if isinstance(value, (list, tuple, set)):
        for name in value:
            text = str(name or "").strip()
            if text and text not in out:
                out.append(text)
    return out


def _load_dangerous_npc_names():
    path = _dangerous_npcs_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "names" in data:
            return normalize_dangerous_npc_names(data.get("names"))
    except Exception:
        pass
    return list(DEFAULT_DANGEROUS_NPC_NAMES)


def save_dangerous_npc_names(names):
    clean = normalize_dangerous_npc_names(names)
    path = _dangerous_npcs_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"names": clean}, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    global DANGEROUS_NPC_NAMES
    DANGEROUS_NPC_NAMES = clean
    return clean


DANGEROUS_NPC_NAMES = _load_dangerous_npc_names()

# DATA SKILL: doc tu skills_data.json (AUTO crack_skills.py). skill_id -> {cost, dame, splash}.
# combat tu suy combo (dame AoE re) + boss (dame splash 4>1) -> KHONG can list cung.
def _load_skill_info():
    import json, os
    f = os.path.join(_base_dir(), "skills_data.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).get("skills", {}).items():
                out[int(k, 16)] = v
    except Exception:
        pass
    return out
SKILL_INFO = _load_skill_info()

# Skill COMBO TRAINING (AoE) - CHI dung FALLBACK khi thieu skills_data.json. Binh thuong tu suy.
COMBO_TRAIN_SKILLS = [12003, 10005, 13013]   # Hoa Tien(15), Nem Da(22), Loan Kich(49)

# Cuon GOI PET RAC -> bot tu PHAN GIAI sau gacha (nhan lai xu). Doc tu junk_scrolls.json
# (itemId hex -> ten). Them cuon rac moi BANG CACH SUA junk_scrolls.json, khoi dong code.
def _load_junk_scrolls():
    import json, os
    f = os.path.join(_base_dir(), "junk_scrolls.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).get("scrolls", {}).items():
                out[int(k, 16)] = v
    except Exception:
        pass
    return out
JUNK_PET_SCROLLS = _load_junk_scrolls()

# NGUYEN LIEU RAC -> bot tu DONATE cho quan doan luc login (don tui). Doc tu donate_items.json
# (itemId hex -> ten). Them item BANG CACH SUA donate_items.json roi khoi dong lai.
def _load_donate_items():
    import json, os
    f = os.path.join(_base_dir(), "donate_items.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).get("items", {}).items():
                out[int(k, 16)] = v
    except Exception:
        pass
    return out
DONATE_ITEMS = _load_donate_items()

# NGUYEN LIEU DONATE quan doan (list EDIT duoc, giong list phan giai cuon pet): TAT CA nguyen lieu
# hop thanh (20 kind, donate_materials.json). MAC DINH donate HET; user danh dau GIU trong GUI
# (material_modes[tid]='keep'). itemId_int -> {name, kind, lv}. Sinh boi crack_donate_materials.py.
def _load_donate_materials():
    import json, os
    f = os.path.join(_base_dir(), "donate_materials.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).get("items", {}).items():
                out[int(k, 16)] = v
    except Exception:
        pass
    return out
DONATE_MATERIALS = _load_donate_materials()

# QUAI KHOANG (NPC kind==16): set template_id -> bot check quai trong tran de BO CHAY. Client nhan
# dien bang kind==16 (CheckMineral), KHONG theo ten -> bot cu bat ten "Khoang " sot gan het (9/252).
def _load_mineral_npc_ids():
    import json, os
    f = os.path.join(_base_dir(), "mineral_npcs.json")
    out = set()
    try:
        with open(f, encoding="utf-8") as fh:
            for k in json.load(fh).get("ids", {}):
                try:
                    out.add(int(k, 16) if isinstance(k, str) and k.lower().startswith("0x") else int(k))
                except Exception:
                    pass
    except Exception:
        pass
    return out
MINERAL_NPC_IDS = _load_mineral_npc_ids()

# BANG NHIEM VU 3x3 (九宮格): gid -> {name, kind, awards[7].flag}. Sinh boi tools/crack_jiugongge.py.
#   kind 1 = Nhiem vu moi ngay | 2 = Nhiem vu tan thu | 3 = EVENT (vd "Mung Game Ra Mat Hai Thang")
# Bot KHONG phu thuoc file nay de biet bang nao dang chay / o nao xong (server gui het trong S:91-1);
# file chi dung de: biet line nao DA NHAN (co 永標) + hien ten bang trong log. Thieu file van chay.
def _load_jiugongge():
    import json, os
    f = os.path.join(_base_dir(), "jiugongge.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).get("grids", {}).items():
                out[int(k)] = v
    except Exception:
        pass
    return out
JIUGONGGE = _load_jiugongge()

# Item TU DONG SU DUNG luc login. Doc tu use_items.json. 2 format value:
#   "0x..": "Ten"                          -> dung HET ca stack, TUNG CAI 1 (item chi cho dung 1/lenh)
#   "0x..": {"name":"Ten","qty":25}        -> dung TOI DA 25 cai/login (co > 25 -> dung 25, de lai du;
#                                             co < 25 -> dung het). Batch nhieu cai 1 lenh.
# Tra dict: tid -> {"name": str, "qty": int|None}. qty None = khong gioi han (dung het, 1/lenh).
def _load_use_items():
    import json, os
    f = os.path.join(_base_dir(), "use_items.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            for k, v in json.load(fh).get("items", {}).items():
                tid = int(k, 16)
                if isinstance(v, dict):
                    out[tid] = {"name": v.get("name", ""), "qty": v.get("qty"),
                                "phuc_than": bool(v.get("phuc_than", False)),
                                "equip": bool(v.get("equip", False))}
                else:
                    out[tid] = {"name": v, "qty": None, "phuc_than": False, "equip": False}
    except Exception:
        pass
    return out
USE_LOGIN_ITEMS = _load_use_items()

# SP cost tung skill (de check du SP truoc khi dung, tranh bi da khi thieu SP).
SKILL_SP_COST = {
    12003: 15,   # Hoa Tien
    10005: 22,   # Nem Da
    13013: 49,   # Loan Kich
    11010: 42,   # Toan Tri Lieu
    11004: 22,   # Thanh Luu
    12006: 24,   # Nhat Kich (danh don, boss - Thai Van Co rb0)
    12009: 30,   # Hoa Kiem (danh don, boss)
}

# Skill IDs
SKILL_NORMAL = 10000        # Danh thuong
SKILL_ROCK = 10005          # Nem Da - AoE 3 ngang
SKILL_FIRE = 12003          # Hoa Tien - AoE 3 ngang
SKILL_HEAL_ALL = 11010      # Toan Tri Lieu (hoi HP toan party)
SKILL_HEAL_ONE = 11004      # Thanh Luu (hoi 1 dong doi)
SKILL_DEFEND = 17001        # Phong thu
SKILL_FLEE = 18001          # Bo chay (0x4651=18001) char+pet thoat tran. FIX: truoc ghi 17997=0x464D SAI -> server khong nhan flee -> ket tran. flee.pcap goi 0x32 skill=51 46 = 0x4651

# SP threshold (de danh SP cho heal): chi dung skill AoE khi SP >= nguong nay
CHAR_ROCK_MIN_SP = 100      # Nem Da
CHAR_FIRE_MIN_SP = 65       # combo (Hoa Tien/Nem Da/Loan Kich): SP < 65 -> danh thuong

# Nguong HP/SP de tu dong hoi mau sau tran. Bot TU HOC item (probe + do delta HP/SP
# qua S2C 0x08), luu items_learned.json - khong can config item ID.
HP_THRESHOLD = 0.4          # Hoi HP khi HP < 40% max (char va pet) - MAC DINH chung
SP_THRESHOLD = 0.0          # = 0 -> KHONG uong thuoc SP (tat hoi SP) - MAC DINH chung

# Override nguong hoi mau RIENG tung acc (theo username). GUI ghi vao accounts.json (field "heal"
# moi acc) -> tu nap vao day. 4 nguong: hp_char/sp_char (char), hp_pet/sp_pet (pet). Thieu key nao
# -> lay HP_THRESHOLD/SP_THRESHOLD chung. Acc khong liet ke -> dung mac dinh het.
# VAN TIEU rieng tung acc (GUI ghi field "vantieu" cho moi acc trong accounts.json).
# {username: {"on": bool, "pets": [pet_id...]}}. Khong co entry = mac dinh BAT + dung TAT CA pet.
ACCOUNT_VANTIEU = {}

ACCOUNT_HEAL = {
    # "acc1": {"hp_char": 0.7, "sp_char": 0.5, "hp_pet": 0.6, "sp_pet": 0.4},
}

# Config SOI LO rieng tung acc (accounts.json field "furnace"). {tab: {"on": bool, "items":
# {tid: "auto"/"notify"}}} voi tab in vo_tuong/trang_bi/chuyen_sinh. auto=tu mua, notify=chi bao.
ACCOUNT_FURNACE = {
    # "acc1": {"vo_tuong": {"on": True, "items": {"0x5c04": "auto"}}},
}

# Config RIENG tung acc (accounts.json field "settings" moi acc - TACH khoi "heal" vi heal chi
# giu 4 nguong hoi mau; settings la cho gom cac config rieng acc, se them key moi sau nay).
# char_defend: "Char đứng Phòng thủ (phục vụ train pet ko vỡ Ngọc phúc thần)" - True -> char CHI
# Phong thu (17001) moi luot battle o MOI mode; False/thieu -> danh binh thuong.
ACCOUNT_CHAR_DEFEND = {}   # username -> bool
ACCOUNT_BATTLE = {}        # username -> {"char": {...}, "pet": {...}} custom battle settings

# Unit IDs
UNIT_CHAR = 3
UNIT_PET = 2

XOR_KEY = 0xAD


# ============================================================
#  OVERRIDE tu accounts.json (GUI gui.py sua file nay). MOI PARTY CONFIG RIENG.
#  PARTY_CONFIG[pidx] = {mode, start_city_id, mob_index, city_flag}.
# ============================================================
PARTY_CONFIG = {}
PARTY_LEADERS_BY_IDX = {}   # pidx -> [ten leader] white list rieng party (tu accounts.json)
def _load_servers():
    import json, os
    f = os.path.join(_base_dir(), "servers.json")
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh).get("servers", {})
    except Exception:
        return {}
SERVERS = _load_servers()
def _server_ip(name):
    s = SERVERS.get(name); return s.get("ip") if s else None
def _server_id(name):
    s = SERVERS.get(name); return int(s.get("id", 1)) if s else 1
def _load_accounts_json():
    import json, os
    f = os.path.join(_base_dir(), "accounts.json")
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None
    # accounts.json co the la dang PROFILES {active, profiles:{ten:{channel,parties,...}}} ->
    # rut bo cau hinh DANG CHON. Dang FLAT cu {channel,parties} -> dung nguyen (backward compat).
    if isinstance(d, dict) and isinstance(d.get("profiles"), dict):
        profs = d["profiles"]
        return profs.get(d.get("active")) or (next(iter(profs.values())) if profs else {})
    return d
_aj = _load_accounts_json()
if _aj is not None:
    try:
        _parties_raw = _aj.get("parties", [])
        # BO QUA acc khi: bo tick (on=false) HOAC username bat dau '#' (co che cu).
        _ps = [[(a.get("u", ""), a.get("p", "")) for a in party.get("accounts", [])
                if a.get("on", True) and not a.get("u", "").lstrip().startswith("#")]
               for party in _parties_raw]
        # Nguong hoi mau rieng tung acc (GUI ghi field "heal" cho moi acc trong accounts.json).
        for _party in _parties_raw:
            for _a in _party.get("accounts", []):
                _u = _a.get("u", "").lstrip().lstrip("#").strip()
                _h = _a.get("heal")
                if _u and isinstance(_h, dict):
                    ACCOUNT_HEAL[_u] = {_k: float(_v) for _k, _v in _h.items()
                                        if _k in ("hp_char", "sp_char", "hp_pet", "sp_pet")}
                _f = _a.get("furnace")
                if _u and isinstance(_f, dict):
                    _fc = {}
                    for _tab in ("vo_tuong", "trang_bi", "chuyen_sinh"):
                        _t = _f.get(_tab)
                        if not isinstance(_t, dict):
                            continue
                        _items = {}
                        for _ik, _iv in (_t.get("items") or {}).items():
                            if _iv not in ("auto", "notify"):
                                continue
                            try:
                                _tid = int(_ik, 16) if isinstance(_ik, str) and _ik.lower().startswith("0x") else int(_ik)
                                _items[_tid] = _iv
                            except Exception:
                                pass
                        if _items:
                            _fc[_tab] = {"on": bool(_t.get("on", True)), "items": _items}
                    if _fc:
                        ACCOUNT_FURNACE[_u] = _fc
                # VAN TIEU rieng tung acc: {"on": bool, "pets": [pet_id...]}.
                # pets RONG = dung TAT CA pet trong nha tro (mac dinh, y het hanh vi cu).
                _v = _a.get("vantieu")
                if _u and isinstance(_v, dict):
                    _vp = []
                    for _x in (_v.get("pets") or []):
                        try:
                            _vp.append(int(_x))
                        except Exception:
                            pass
                    ACCOUNT_VANTIEU[_u] = {"on": bool(_v.get("on", True)), "pets": _vp}
                _s = _a.get("settings")
                if _u and isinstance(_s, dict):
                    if _s.get("char_defend"):
                        ACCOUNT_CHAR_DEFEND[_u] = True
                    _b = _s.get("battle")
                    if isinstance(_b, dict):
                        ACCOUNT_BATTLE[_u] = _b
        # accounts.json TON TAI -> LUON dung no (ke ca RONG) => ban product accounts.json rong thi
        # KHONG hien party mac dinh cua config (tranh lo/nham acc).
        PARTIES = _ps
        for _i, _party in enumerate(_parties_raw):
            _srv = _party.get("server", "trieu_van")
            _shop_items = normalize_shop_items(_party.get("shop_items"), {
                "ho_phu": _party.get("buy_ho_phu", False),
                "thien_chau": _party.get("buy_thien_chau", False),
                "bao_hop": _party.get("buy_bao_hop", False),
            })
            _auto_buy_shop = bool(_party.get("auto_buy_shop", any(_shop_items.values())))
            # PASSTHROUGH truoc: MOI key GUI ghi vao accounts.json deu xuong bot.
            # (Truoc day day la danh sach CHEP TAY -> them tick moi o GUI ma quen them o day thi
            #  bot chay mac dinh, KHONG AI BAO. Da mat: material_modes, auto_bag_clean,
            #  auto_event_exchange... - xem CLAUDE.md muc "chep tay o dau la lech o do".)
            PARTY_CONFIG[_i] = {_k: _v for _k, _v in _party.items()
                                if _k not in ("accounts", "leaders")}
            # Cac dong duoi CHI de EP KIEU / doi ten / mac dinh - khong phai de "khai bao key".
            PARTY_CONFIG[_i].update({
                "mode": _party.get("mode", "stand"),
                "start_city_id": int(_party.get("start_city_id", 0)),
                "mob_index": int(_party.get("mob_index", -1)),  # mac dinh -1 = Bot tu chon
                "city_flag": int(_party.get("city_flag", 0)),
                "server": _srv,
                "server_ip": _server_ip(_srv) or GAME_HOST,
                "server_id": _server_id(_srv),
                "do_daily": bool(_party.get("do_daily", _party.get("do_dungeon", True))),
                "claim_offline_exp": bool(_party.get("claim_offline_exp", True)),
                "auto_world_boss": bool(_party.get("auto_world_boss", True)),
                "auto_team_dungeon": bool(_party.get("auto_team_dungeon", True)),
                "team_dungeons": normalize_team_dungeons(_party.get("team_dungeons")),
                "digioi_mode": _party.get("digioi_mode", "party"),   # Di Gioi: "party" | "solo"
                "event_key": _party.get("event_key", ""),   # mode 'event': key trong events.json (npc_40, nhi_kieu...)
                "use_phuc_than": bool(_party.get("use_phuc_than", False)),
                "use_digioi_ho_phu": bool(_party.get("use_digioi_ho_phu", False)),
                "fight_legion_boss": bool(_party.get("fight_legion_boss", True)),
                "do_van_tieu": bool(_party.get("do_van_tieu", True)),
                "auto_sell_noi_dat": bool(_party.get("auto_sell_noi_dat", True)),
                "auto_buy_shop": _auto_buy_shop,
                "shop_items": _shop_items,
                "buy_ho_phu": bool(_shop_items.get("ho_phu", False)),
                "buy_thien_chau": bool(_shop_items.get("thien_chau", False)),
                "buy_bao_hop": bool(_shop_items.get("bao_hop", False)),
                "bao_hop_xu_threshold": int(_party.get("bao_hop_xu_threshold", 10000000)),
                "buy_hp": bool(_party.get("buy_hp", False)),
                "hp_qty": int(_party.get("hp_qty", 9999)),
                "hp_thresh": int(_party.get("hp_thresh", 500000)),
                "buy_sp": bool(_party.get("buy_sp", False)),
                "sp_qty": int(_party.get("sp_qty", 9999)),
                "sp_thresh": int(_party.get("sp_thresh", 500000)),
                "di_gioi_level": int(_party.get("di_gioi_level", 2)),   # idx 1..15 cap quai DG (2=cap25)
            })
            PARTY_LEADERS_BY_IDX[_i] = list(_party.get("leaders", []) or [])
        if PARTY_CONFIG:
            START_CITY_ID = PARTY_CONFIG[0]["start_city_id"]
        if "channel" in _aj:
            CHANNEL = int(_aj["channel"])
        if "party_leaders" in _aj:        # white list CHUNG (ap moi party)
            PARTY_LEADERS = list(_aj.get("party_leaders", []) or [])
    except Exception:
        pass


# White list RIENG tung party (pidx -> [ten ngoai party]); CHUNG = PARTY_LEADERS.
# leaders_for(pidx) = CHUNG + RIENG (union). Rong het -> no-leader se nhan moi nguoi moi.
def leaders_for(pidx):
    out = list(PARTY_LEADERS)
    for nm in PARTY_LEADERS_BY_IDX.get(pidx, []):
        if nm not in out:
            out.append(nm)
    return out


def record_leader_name(pidx, char_name):
    """Tu dong THEM ten nhan vat leader vao whitelist "leaders" cua party (KHONG xoa/replace
    ten da co san - chi APPEND neu chua co). User phan anh: da cau hinh account nao la leader
    trong Party roi thi khong nen phai go tay TEN NHAN VAT lai vao o whitelist rieng (2 cho
    cau hinh trung nhau). Goi ngay sau khi leader login xong + biet char_name. Cap nhat CA
    RAM (PARTY_LEADERS_BY_IDX, hieu luc ngay ca phien nay) LAN file cau hinh tren dia
    (accounts.json cho PC / parties.json cho APK - hieu luc lan chay sau, khong mat khi restart)."""
    if not char_name:
        return
    name = char_name.strip()
    if not name:
        return
    cur = PARTY_LEADERS_BY_IDX.setdefault(pidx, [])
    if any(x.strip().lower() == name.lower() for x in cur):
        return   # da co san (khong phan biet hoa/thuong) -> khong them trung
    cur.append(name)
    # LUU BEN vao KHO CAU HINH - CO HAI kho khac nhau, phai ghi ca hai:
    #   - PC/GUI : accounts.json  {"profiles": {<active>: {"parties": [...]}}} (hoac dict phang)
    #   - APK    : parties.json   MANG cac party, do PartyStore.kt ghi o Context.getFilesDir()
    # Truoc day CHI ghi accounts.json -> tren APK ten leader chi vao RAM: khong hien len o
    # whitelist trong UI va MAT sau khi restart app (user phan anh "mat vu tu dien ten leader").
    import json, os

    def _same(x):
        return str(x).strip().lower() == name.lower()

    def _write(path, data):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)   # ghi nguyen tu: app bi kill giua chung khong lam hong file config

    try:      # PC: accounts.json
        f = os.path.join(_base_dir(), "accounts.json")
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict) and isinstance(d.get("profiles"), dict):
            prof = d["profiles"].get(d.get("active"))
        else:
            prof = d
        parties = prof.get("parties", []) if isinstance(prof, dict) else []
        if 0 <= pidx < len(parties):
            leaders = parties[pidx].setdefault("leaders", [])
            if not any(_same(x) for x in leaders):
                leaders.append(name)
                _write(f, d)
    except Exception:
        pass

    try:      # APK: parties.json (PartyStore.kt)
        f = os.path.join(_base_dir(), "parties.json")
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        parties = d if isinstance(d, list) else (d.get("parties") if isinstance(d, dict) else None)
        if isinstance(parties, list) and 0 <= pidx < len(parties) and isinstance(parties[pidx], dict):
            leaders = parties[pidx].setdefault("leaders", [])
            if not any(_same(x) for x in leaders):
                leaders.append(name)
                _write(f, d)
    except Exception:
        pass   # khong lam crash bot vi loi ghi file - RAM van da cap nhat, hieu luc phien nay


# ============================================================
#  TU SINH tu PARTIES - KHONG can doc/sua
# ============================================================
ACCOUNTS = [acc for party in PARTIES for acc in party if acc and acc[0]]
ACCOUNT_PARTY = {acc[0]: i for i, party in enumerate(PARTIES) for acc in party if acc and acc[0]}
PARTY_LEADER_ACC = {i: party[0][0] for i, party in enumerate(PARTIES)
                    if party and party[0] and party[0][0]}
LEADER_ACCOUNTS = set(PARTY_LEADER_ACC.values())
