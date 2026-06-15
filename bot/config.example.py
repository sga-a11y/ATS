"""Cau hinh bot TS Online - BAN MAU.
Copy file nay thanh `config.py` roi dien thong tin that. config.py da bi gitignore.
"""

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

# Whitelist TEN NHAN VAT chu party duoc phep moi - cho acc TU DIEU KHIEN tay + pho ban.
# [] = nhan tu bat ky ai. (Bot cung party tu nhan nhau qua entity, KHONG can ghi o day.)
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
    f = os.path.join(os.path.dirname(__file__), os.pardir, "train_maps.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("maps", {}).items():
            s = v["safe"]
            # safe = [[x,y],...] (nhieu diem) HOAC [x,y] (1 diem, format cu) -> chuan hoa LIST diem
            safes = [tuple(p) for p in s] if (s and isinstance(s[0], (list, tuple))) else [tuple(s)]
            out[int(k)] = {"safe": safes, "mobs": [tuple(m) for m in v.get("mobs", [])]}
    except Exception:
        pass
    return out
TRAIN_MAPS = _load_train_maps()
def _load_map_gates(path=None):
    """Doc map_gates.json -> {map_id:int -> [(x,y,to), ...]} (do thi cong di chuyen).
    Khong co file/loi -> {}. Dung cho pathfind.find_path (auto di toi train map)."""
    import json, os
    f = path or os.path.join(os.path.dirname(__file__), os.pardir, "map_gates.json")
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
START_CITY_FLAG = 2             # Ng.Thanh=2, Trac Quan=0, Cu Loc=3 (xem cities.json)
CHANNEL = 1                     # kenh can o cung voi chu party (0 = bo qua)
RECONNECT_DELAY = 10            # giay cho truoc khi ket noi lai khi bi rot
ENTER_DIGIOI = False            # True = sau khi connect tu vao Di Gioi train (solo, KHONG party)
DIGIOI_MAP_ID = 49942           # map_id Di Gioi (0xc316) - doc tu broadcast de biet dang o Di Gioi
# Auto run-around: chay vong quanh DIEM DANG DUNG (offset tuong doi). Hinh so 8 (tu game auto-run).
RUN_AROUND_OFFSETS = [(-100, -100), (-200, 0), (-100, 100), (0, 0),
                      (100, -100), (200, 0), (100, 100), (0, 0)]
RUN_STEP_WAIT = 2.5            # giay moi buoc di chuyen

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
    f = os.path.join(os.path.dirname(__file__), os.pardir, fn)
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}
PET_HEDOANH = _load_json_root("pet_hedoanh.json")                       # ten pet -> {he, doanh}
VANTIEU_REQUESTS = _load_json_root("vantieu_requests.json").get("requests", {})  # ma 0400 -> {he, doanh}

# Qua online: nhan khi online du so phut. id qua = so phut moc.
GIFT_MILESTONES = [10, 20, 30, 60, 90, 180]

# Combat tuning
HEAL_HP_THRESHOLD = 0.60    # ally HP <= 60% max -> Toan Tri Lieu
HEAL_SP_COST = 42
PET_FIRE_MIN_SP = 100       # pet SP >= 100 moi xet skill combo (duoi 100 -> danh chay)

# DATA PET: doc tu pets.json (pet_id hex -> LIST skill cua pet). pet_id tu S2C 0x13 luc login.
def _load_pets():
    import json, os
    f = os.path.join(os.path.dirname(__file__), os.pardir, "pets.json")
    skills, names, boss, hedoanh = {}, {}, {}, {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("pets", {}).items():
            pid = int(k, 16)
            skills[pid] = set(v.get("skills", []))
            names[pid] = v.get("name", "")
            if v.get("boss_skill"):
                boss[pid] = v["boss_skill"]
            if v.get("he") or v.get("doanh"):   # he/doanh dien tay (cho VAN TIEU match)
                hedoanh[pid] = (v.get("he", ""), v.get("doanh", ""))
    except Exception:
        pass
    return skills, names, boss, hedoanh
PET_SKILLS, PET_NAMES, PET_BOSS_SKILL, PET_HE_DOANH = _load_pets()   # pet_id -> skills/ten/boss/(he,doanh)

# Skill dung de COMBO TRAINING (AoE hang ngang). Uu tien tu trai sang (re SP truoc).
# Unit nao co 1 trong cac skill nay -> dung de combo. Sau nay event/boss co list khac.
COMBO_TRAIN_SKILLS = [12003, 10005, 13013]   # Hoa Tien(15), Nem Da(22), Loan Kich(49)

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
SKILL_FLEE = 17997          # Bo chay (0x4651) - dung nhu skill cho ca char+pet de thoat tran

# SP threshold (de danh SP cho heal): chi dung skill AoE khi SP >= nguong nay
CHAR_ROCK_MIN_SP = 100      # Nem Da
CHAR_FIRE_MIN_SP = 100      # Hoa Tien

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
    f = os.path.join(os.path.dirname(__file__), os.pardir, "servers.json")
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
    f = os.path.join(os.path.dirname(__file__), os.pardir, "accounts.json")
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None
_aj = _load_accounts_json()
if _aj is not None:
    try:
        _parties_raw = _aj.get("parties", [])
        # BO QUA acc khi: bo tick (on=false) HOAC username bat dau '#' (co che cu).
        _ps = [[(a.get("u", ""), a.get("p", "")) for a in party.get("accounts", [])
                if a.get("on", True) and not a.get("u", "").lstrip().startswith("#")]
               for party in _parties_raw]
        if _ps:
            PARTIES = _ps
        for _i, _party in enumerate(_parties_raw):
            _srv = _party.get("server", "trieu_van")
            PARTY_CONFIG[_i] = {
                "mode": _party.get("mode", "stand"),
                "start_city_id": int(_party.get("start_city_id", 0)),
                "mob_index": int(_party.get("mob_index", -1)),  # mac dinh -1 = Bot tu chon
                "city_flag": int(_party.get("city_flag", 0)),
                "server": _srv,
                "server_ip": _server_ip(_srv) or GAME_HOST,
                "server_id": _server_id(_srv),
                "do_dungeon": bool(_party.get("do_dungeon", True)),
            }
            PARTY_LEADERS_BY_IDX[_i] = list(_party.get("leaders", []) or [])
        if PARTY_CONFIG:
            START_CITY_ID = PARTY_CONFIG[0]["start_city_id"]
        if "channel" in _aj:
            CHANNEL = int(_aj["channel"])
        if "party_leaders" in _aj:        # white list CHUNG (ap moi party)
            PARTY_LEADERS = list(_aj.get("party_leaders", []) or [])
    except Exception:
        pass


# White list RIENG tung party (pidx -> [ten leader]); CHUNG = PARTY_LEADERS.
# leaders_for(pidx) = CHUNG + RIENG (union). Rong het -> nhan moi nguoi moi.
def leaders_for(pidx):
    out = list(PARTY_LEADERS)
    for nm in PARTY_LEADERS_BY_IDX.get(pidx, []):
        if nm not in out:
            out.append(nm)
    return out


# ============================================================
#  TU SINH tu PARTIES - KHONG can doc/sua
# ============================================================
ACCOUNTS = [acc for party in PARTIES for acc in party if acc and acc[0]]
ACCOUNT_PARTY = {acc[0]: i for i, party in enumerate(PARTIES) for acc in party if acc and acc[0]}
PARTY_LEADER_ACC = {i: party[0][0] for i, party in enumerate(PARTIES)
                    if party and party[0] and party[0][0]}
LEADER_ACCOUNTS = set(PARTY_LEADER_ACC.values())
