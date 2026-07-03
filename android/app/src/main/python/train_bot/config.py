"""Ban rut gon cua bot/config.py cho Android Train-only: giu hang so + PET_SKILLS/
SKILL_INFO, BO ACCOUNTS/PARTY_CONFIG (Android quan ly account rieng qua Kotlin).

Ghi chu (Task 3 - buoc doc bot/client.py de doi chieu): client.py dung THANG (khong qua
getattr) cac hang so sau -> BAT BUOC phai co trong ban rut gon nay, neu khong AttributeError
ngay khi GameClient duoc tao/connect:
  GAME_HOST, GAME_PORT (GameClient.__init__/connect/relogin), PET_SKILLS (_on_pet_list),
  UNIT_CHAR/UNIT_PET/SKILL_FLEE/SKILL_NORMAL (combat flow), DIGIOI_MAP_ID (in_di_gioi/exit).
Cac hang so khac (ACCOUNT_HEAL, JUNK_PET_SCROLLS, PET_HEDOANH, VANTIEU_*, RUN_AROUND_OFFSETS...)
duoc client.py doc qua getattr(config, "X", default) -> AN TOAN neu thieu, nhung van khai bao
o day (rong/mac dinh) de cac nhanh van tieu/run-around khong crash neu duoc bat sau nay.
"""
import json

HEAL_HP_THRESHOLD = 0.70
HEAL_SP_COST = 42
PET_FIRE_MIN_SP = 65
CHAR_FIRE_MIN_SP = 65
SKILL_NORMAL = 10000
SKILL_ROCK = 10005
SKILL_FIRE = 12003
SKILL_HEAL_ALL = 11010
SKILL_HEAL_ONE = 11004
SKILL_DEFEND = 17001
SKILL_FLEE = 18001
UNIT_CHAR = 3
UNIT_PET = 2

SKILL_SP_COST = {
    12003: 15,   # Hoa Tien
    10005: 22,   # Nem Da
    13013: 49,   # Loan Kich
    11010: 42,   # Toan Tri Lieu
    11004: 22,   # Thanh Luu
    12006: 24,   # Nhat Kich (danh don, boss - Thai Van Co rb0)
    12009: 30,   # Hoa Kiem (danh don, boss)
}

# combat.py fallback constants (dung qua getattr, nhung khai bao san cho du/khop ban goc)
SP_RESTORE_THRESHOLD = 0.5
COMBO_TRAIN_SKILLS = [12003, 10005, 13013]   # Hoa Tien(15), Nem Da(22), Loan Kich(49)

# ---- client.py dung THANG (KHONG qua getattr) -> BAT BUOC co ----
GAME_HOST = "103.82.28.98"
GAME_PORT = 6614
DIGIOI_MAP_ID = 49942           # map_id Di Gioi (0xc316)

# ---- client.py dung qua getattr(..., default) -> co the rong an toan, nhung khai bao du ----
ACCOUNT_HEAL = {}
JUNK_PET_SCROLLS = {}
PET_HEDOANH = {}
VANTIEU_ENABLE = False
VANTIEU_PETS = []
VANTIEU_PETS_NAMES = []
VANTIEU_REQUESTS = {}
RUN_AROUND_OFFSETS = [(-100, -100), (-200, 0), (-100, 100), (0, 0),
                      (100, -100), (200, 0), (100, 100), (0, 0)]
RUN_STEP_WAIT = 0.7
HP_THRESHOLD = 0.4
SP_THRESHOLD = 0.0
GIFT_MILESTONES = [10, 20, 30, 60, 90, 180]
DUNGEON_RUNS_PER_DAY = 2


def _read_asset(name: str) -> str:
    """Doc file text tu android assets/train_bot_data/ qua Context (Chaquopy: Python.getPlatform()
    .getApplication() tra ve Android Application context da truyen luc Python.start())."""
    from com.chaquo.python import Python
    ctx = Python.getPlatform().getApplication()
    stream = ctx.getAssets().open(f"train_bot_data/{name}")
    data = bytes(stream.readAllBytes())
    stream.close()
    return data.decode("utf-8")


def _load_pets():
    """Khop CHINH XAC bot/config.py::_load_pets (dong 161-177): key top-level "pets", pet_id
    la CHUOI HEX (vd "0x0508") -> int(k,16). skills = LIST (giu thu tu, skill[0]=boss fallback)."""
    skills, names, hedoanh = {}, {}, {}
    try:
        d = json.loads(_read_asset("pets.json"))
        for k, v in d.get("pets", {}).items():
            pid = int(k, 16)
            skills[pid] = list(v.get("skills", []))
            names[pid] = v.get("name", "")
            if v.get("he") or v.get("doanh"):
                hedoanh[pid] = (v.get("he", ""), v.get("doanh", ""))
    except Exception:
        pass
    return skills, names, hedoanh


PET_SKILLS, PET_NAMES, PET_HE_DOANH = _load_pets()


def _load_skill_info():
    """Khop CHINH XAC bot/config.py::_load_skill_info (dong 181-192): key top-level "skills",
    skill_id la CHUOI HEX (vd "0x2710") -> int(k,16). GIA TRI: {cost, cat, splash}."""
    out = {}
    try:
        d = json.loads(_read_asset("skills_data.json"))
        for k, v in d.get("skills", {}).items():
            out[int(k, 16)] = v
    except Exception:
        pass
    return out


SKILL_INFO = _load_skill_info()
