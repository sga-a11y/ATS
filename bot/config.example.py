"""Cau hinh bot TS Online - BAN MAU.
Copy file nay thanh `config.py` roi dien thong tin that. config.py da bi gitignore.
"""

# Tai khoan mac dinh (single bot)
USERNAME = "your_username"
PASSWORD = "your_password"

# ==== DANH SACH PARTY ====
# Moi party = 1 list toi da 5 acc (username, password) - pass co the khac nhau.
# acc[0] cua moi party = CHU PARTY.
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
START_CITY_ID = 12061
START_CITY_FLAG = 2             # Ng.Thanh=2, Trac Quan=0, Cu Loc=3 (xem cities.json)
CHANNEL = 1                     # kenh can o cung voi chu party (0 = bo qua)
RECONNECT_DELAY = 10            # giay cho truoc khi ket noi lai khi bi rot
ENTER_DIGIOI = False            # True = sau khi connect tu vao Di Gioi train (solo, KHONG party)
DIGIOI_MAP_ID = 49942           # map_id Di Gioi (0xc316) - doc tu broadcast de biet dang o Di Gioi

# Qua online: nhan khi online du so phut. id qua = so phut moc.
GIFT_MILESTONES = [10, 20, 30, 60, 90, 180]

# Combat tuning
HEAL_HP_THRESHOLD = 0.60    # ally HP <= 60% max -> Toan Tri Lieu
HEAL_SP_COST = 42
PET_FIRE_MIN_SP = 15        # pet SP >= 15 moi xet skill AoE

# DATA PET: doc tu pets.json (pet_id hex -> LIST skill cua pet). pet_id tu S2C 0x13 luc login.
def _load_pets():
    import json, os
    f = os.path.join(os.path.dirname(__file__), os.pardir, "pets.json")
    skills, names = {}, {}
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.get("pets", {}).items():
            pid = int(k, 16)
            skills[pid] = set(v.get("skills", []))
            names[pid] = v.get("name", "")
    except Exception:
        pass
    return skills, names
PET_SKILLS, PET_NAMES = _load_pets()   # pet_id -> set(skill_id) / ten pet

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
}

# Skill IDs
SKILL_NORMAL = 10000        # Danh thuong
SKILL_ROCK = 10005          # Nem Da - AoE 3 ngang
SKILL_FIRE = 12003          # Hoa Tien - AoE 3 ngang
SKILL_HEAL_ALL = 11010      # Toan Tri Lieu (hoi HP toan party)
SKILL_HEAL_ONE = 11004      # Thanh Luu (hoi 1 dong doi)
SKILL_DEFEND = 17001        # Phong thu

# SP threshold (de danh SP cho heal): chi dung skill AoE khi SP >= nguong nay
CHAR_ROCK_MIN_SP = 100      # Nem Da
CHAR_FIRE_MIN_SP = 100      # Hoa Tien

# Unit IDs
UNIT_CHAR = 3
UNIT_PET = 2

XOR_KEY = 0xAD


# ============================================================
#  TU SINH tu PARTIES - KHONG can doc/sua
# ============================================================
ACCOUNTS = [acc for party in PARTIES for acc in party]
ACCOUNT_PARTY = {acc[0]: i for i, party in enumerate(PARTIES) for acc in party}
