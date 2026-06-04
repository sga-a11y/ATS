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

# API login
API_KEY = "YOUR_API_KEY"
LOGIN_URL = f"https://graph.mobiplay.vn/accountapiv4/server/login?api_key={API_KEY}"
DEVICE_ID = "YOUR_DEVICE_ID"
TRACKING_ID = "YOUR_TRACKING_ID"

# Game server TCP
GAME_HOST = "103.82.28.98"
GAME_PORT = 6614

# ==== TOOL TREO MAY (bot_standalone.py) ====
LEADER_NAME = "ten_chu_party"   # ten chu party (tham khao/log)
START_CITY_ID = 12001           # thanh xuat phat de chu party moi vao (Trac Quan)
START_CITY_FLAG = 0             # flag tuong ung thanh (xem cities.json)
CHANNEL = 6                     # kenh can o cung voi chu party (0 = bo qua)
RECONNECT_DELAY = 10            # giay cho truoc khi ket noi lai khi bi rot

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
