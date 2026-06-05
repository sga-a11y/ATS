"""Cau hinh bot TS Online - BAN MAU.
Copy file nay thanh `config.py` roi dien thong tin that. config.py da bi gitignore.
"""

# Tai khoan mac dinh (single bot)
USERNAME = "your_username"
PASSWORD = "your_password"

# Danh sach account cho run_party.py (multi-bot)
ACCOUNTS = [
    ("acc1", "password1"),
    # ("acc2", "password2"),
]

# API login - API_KEY la HANG SO co dinh cua game, KHONG can sua.
# (device_id & tracking_id duoc login.py tu sinh tu username -> khong can dien)
API_KEY = "17ade453e0892461edb01969b6e17e3a"
LOGIN_URL = f"https://graph.mobiplay.vn/accountapiv4/server/login?api_key={API_KEY}"

# Game server TCP - co dinh, KHONG can sua
GAME_HOST = "103.82.28.98"
GAME_PORT = 6614

# ==== TOOL TREO MAY (bot_standalone.py) - chi can quan tam phan nay ====
LEADER_NAME = "ten_chu_party"   # ten chu party (tham khao/log)
START_CITY_ID = 12061           # 12061 = Ng.Thanh | 12001 = Trac Quan | 12011 = Cu Loc
START_CITY_FLAG = 2             # Ng.Thanh=2, Trac Quan=0, Cu Loc=3 (xem cities.json)
CHANNEL = 1                     # kenh can o cung voi chu party (0 = bo qua)
RECONNECT_DELAY = 10            # giay cho truoc khi ket noi lai khi bi rot
ENTER_DIGIOI = False            # True = sau khi connect tu vao Di Gioi train (solo, KHONG party)

# Combat tuning
CHAR_FIRE_MIN_SP = 100      # SP >= 100 -> Hoa Tien
HEAL_HP_THRESHOLD = 0.60    # ally HP <= 60% max -> Toan Tri Lieu
PET_FIRE_MIN_SP = 15        # pet SP >= 15 -> Hoa Tien

# Skill IDs
SKILL_NORMAL = 10000        # Danh thuong
SKILL_FIRE = 12003          # Hoa Tien
SKILL_HEAL_ALL = 11010      # Toan Tri Lieu
SKILL_HEAL_ONE = 11004      # Thanh Luu
SKILL_DEFEND = 17001        # Phong thu

# Unit IDs
UNIT_CHAR = 3
UNIT_PET = 2

XOR_KEY = 0xAD
