"""Cau hinh bot TS Online (tai khoan THAT - file nay gitignore)."""

# Tai khoan mac dinh (single bot)
USERNAME = "sga002"
PASSWORD = "s112233"

# ==== DANH SACH PARTY ====
# Moi party = 1 list toi da 5 acc (username, password) - pass co the khac nhau.
# SLOT 0 = CHU PARTY (bot tu gui loi moi + dan train). Slot 1-4 = member (chi cho duoc moi).
# SLOT 0 = ("", "") -> party KHONG co bot-leader (chi member, cho leader ngoai/tay moi).
PARTIES = [ #[("sga005", "s112233"),],
   # [("sga001", "s112233"),("sga002", "s112233"),("sga003", "s112233"),("sga004", "s112233"),("sga006", "s112233"),],
   # [("sga005", "s112233"),("sga007", "s112233"),("sga008", "s112233"),("sga009", "s112233"),("sga010", "s112233"),],
   # [("sga011", "s112233"),("sga012", "s112233"),("sga013", "s112233"),("sga014", "s112233"),("sga015", "s112233"),],
    [("", "s112233"),("sga017", "s112233"),("sga018", "s112233"),("sga019", "s112233"),("sga020", "s112233"),],
]

# Whitelist TEN NHAN VAT chu party duoc phep moi (cho acc Anh TU DIEU KHIEN tay, va pho ban).
# [] = nhan tu bat ky ai. (Bot cung party tu nhan nhau qua entity, KHONG can ghi o day.)
PARTY_LEADERS = ["nanam","nasau", "gamo", "gaha","thmo"]

# API login - API_KEY hang so co dinh; device_id & tracking_id login.py tu sinh tu username
API_KEY = "17ade453e0892461edb01969b6e17e3a"
LOGIN_URL = f"https://graph.mobiplay.vn/accountapiv4/server/login?api_key={API_KEY}"

# Game server TCP - co dinh
GAME_HOST = "103.82.28.98"
GAME_PORT = 6614

# ==== TOOL TREO MAY ====
LEADER_NAME = "gamo"   # ten chu party (tham khao/log)

# START_CITY_ID: thanh ve sau login. 12061=Ng.Thanh | 12001=Trac Quan | 12011=Cu Loc
#   = 0 -> KHONG teleport: dung yen tai cho login (van chuyen CHANNEL, van tu danh khi vao tran).
#   = MAP ID trung voi map LUC LOGIN -> vao che do PARTY-TRAIN tren map do (chay toi TRAIN_SAFE,
#     dong bo kenh, moi party, leader ra TRAIN_MOB_SPOTS dung cay). Xem log "MAP HIEN TAI" luc login.
#START_CITY_ID = 12831 49942
START_CITY_ID =  12001
# Data map party-train doc tu train_maps.json (map_id -> {safe, mobs}).
#   START_CITY_ID CO trong data  -> vao MAP-TRAIN (chay toi safe, lap party, ra mobs cay)
#   START_CITY_ID == DIGIOI_MAP_ID -> train Di Gioi (run-around)
#   con lai -> dung i tai cho (chi tu danh khi bi tan cong)
def _load_train_maps():
    import json, os
    f = os.path.join(os.path.dirname(__file__), os.pardir, "train_maps.json")
    out = {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("maps", {}).items():
            out[int(k)] = {"safe": tuple(v["safe"]),
                           "mobs": [tuple(m) for m in v.get("mobs", [])]}
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
def _load_train_routes(path=None):
    """Doc train_routes.json -> {dest_map:int -> {from_city, city_flag, dest_map, steps}}.
    Route replay tu thanh toi train map (leader di, member tu keo theo)."""
    import json, os
    f = path or os.path.join(os.path.dirname(__file__), os.pardir, "train_routes.json")
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
START_CITY_FLAG = 0             # Ng.Thanh=2, Trac Quan=0, Cu Loc=3
CHANNEL = 4                     # kenh can o cung voi chu party (0 = bo qua)
RECONNECT_DELAY = 10            # giay cho truoc khi ket noi lai khi bi rot
ENTER_DIGIOI = False            # True = sau khi connect tu vao Di Gioi train (solo, KHONG party)
DIGIOI_MAP_ID = 49942           # map_id Di Gioi (0xc316)
# Auto run-around: vong lap chay quanh DIEM DANG DUNG (offset tuong doi tu vi tri hien tai).
# Hinh so 8 (bat tu game auto-run, da capture). Bot anchor = vi tri hien tai roi chay anchor+offset.
RUN_AROUND_OFFSETS = [(-100, -100), (-200, 0), (-100, 100), (0, 0),
                      (100, -100), (200, 0), (100, 100), (0, 0)]
RUN_STEP_WAIT = 0.75           # giay cho moi buoc di chuyen (giam = chay nhanh hon; <0.1 de bi flood/kick)
RUN_RESUME_IDLE = 2.0          # giay khong nhan luot moi -> coi nhu het tran, chay tiep (giam = resume nhanh hon sau battle)
# Vi tri minh chi broadcast KHI di chuyen. Neu dung yen chua biet pos -> probe 1 move toi day
# (vung spawn Di Gioi) de doc duoc vi tri thuc, roi anchor run-around tai do.
RUN_FALLBACK_ANCHOR = (870, 740)

# Solo daily dungeon: so luot/ngay (luot 1 mien phi, luot 2+ MUA bang vang). =1 chi danh luot free.
DUNGEON_RUNS_PER_DAY = 2

# Qua online: nhan khi online du so phut. id qua = so phut moc.
GIFT_MILESTONES = [10, 20, 30, 60, 90, 180]

# Combat tuning
HEAL_HP_THRESHOLD = 0.60    # ally HP <= 60% max -> Toan Tri Lieu
HEAL_SP_COST = 42
PET_FIRE_MIN_SP = 15        # pet SP >= 15 moi xet skill AoE

# DATA PET: doc tu pets.json (pet_id hex -> skills/name/boss_skill). pet_id tu S2C 0x13 luc login.
def _load_pets():
    import json, os
    f = os.path.join(os.path.dirname(__file__), os.pardir, "pets.json")
    skills, names, boss = {}, {}, {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("pets", {}).items():
            pid = int(k, 16)
            skills[pid] = set(v.get("skills", []))
            names[pid] = v.get("name", "")
            if v.get("boss_skill"):
                boss[pid] = v["boss_skill"]   # skill danh don dung khi danh BOSS
    except Exception:
        pass
    return skills, names, boss
PET_SKILLS, PET_NAMES, PET_BOSS_SKILL = _load_pets()

# Skill COMBO TRAINING (AoE hang ngang). Uu tien tu trai sang (re SP truoc).
COMBO_TRAIN_SKILLS = [12003, 10005, 13013]   # Hoa Tien(15), Nem Da(22), Loan Kich(49)

# SP cost tung skill (check du SP truoc khi dung, tranh bi da khi thieu SP)
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

# SP threshold (danh SP cho heal): chi dung skill AoE khi SP >= nguong nay
CHAR_ROCK_MIN_SP = 100      # Nem Da
CHAR_FIRE_MIN_SP = 100      # Hoa Tien

# Unit IDs
UNIT_CHAR = 3
UNIT_PET = 2

XOR_KEY = 0xAD


# ============================================================
#  OVERRIDE tu accounts.json (GUI sua file nay - KHONG dung code).
#  MOI PARTY CO CONFIG RIENG: mode + start_city_id (+ mob_index / city_flag).
#  PARTY_CONFIG[pidx] = {mode, start_city_id, mob_index, city_flag}.
#  mode: 'digioi' (train Di Gioi) | 'train' (train map) | 'city' (tap trung ve thanh, dung yen)
#        | 'stand' (login dau dung yen do, sc=0) | 'cleanbag' (don tui - chua lam).
# ============================================================
PARTY_CONFIG = {}
def _load_servers():
    import json, os
    f = os.path.join(os.path.dirname(__file__), os.pardir, "servers.json")
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh).get("servers", {})
    except Exception:
        return {}
SERVERS = _load_servers()   # name -> {label, ip}
def _server_ip(name):
    s = SERVERS.get(name)
    return s.get("ip") if s else None
def _server_id(name):
    s = SERVERS.get(name)
    return int(s.get("id", 1)) if s else 1
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
        # acc BO TICK (on=false) HOAC username bat dau bang '#' = BO QUA - khong dua vao PARTIES
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
        # START_CITY_ID toan cuc = party dau (fallback cho CLI/bot_standalone)
        if PARTY_CONFIG:
            START_CITY_ID = PARTY_CONFIG[0]["start_city_id"]
        if "channel" in _aj:
            CHANNEL = int(_aj["channel"])
    except Exception:
        pass


# ============================================================
#  TU SINH tu PARTIES - KHONG can doc/sua
# ============================================================
# Bo cac slot trong ("","" hoac rong). acc hop le = co username.
ACCOUNTS = [acc for party in PARTIES for acc in party if acc and acc[0]]
ACCOUNT_PARTY = {acc[0]: i for i, party in enumerate(PARTIES) for acc in party if acc and acc[0]}
# party idx -> username chu party (slot 0 neu khong trong). LEADER_ACCOUNTS = set username la leader.
PARTY_LEADER_ACC = {i: party[0][0] for i, party in enumerate(PARTIES)
                    if party and party[0] and party[0][0]}
LEADER_ACCOUNTS = set(PARTY_LEADER_ACC.values())
