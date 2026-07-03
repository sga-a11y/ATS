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
    .getApplication() tra ve Android Application context da truyen luc Python.start()).

    KHONG dung InputStream.readAllBytes() - ham nay chi co tu Java 9 / Android API 33+,
    minSdk cua app la 26 -> tren thiet bi/emulator cu hon se nem AttributeError, bi
    "except: pass" (o cho goi ham nay) nuot am tham, khien du lieu (PET_SKILLS/SKILL_INFO/
    CITIES...) TRONG RONG ma khong ai biet (xac nhan bug that qua log stderr thuc te).
    Dung BufferedReader/InputStreamReader (co tu API 1) doc tung dong thay the, an toan
    tren MOI phien ban Android."""
    from com.chaquo.python import Python
    from java import jclass
    ctx = Python.getPlatform().getApplication()
    stream = ctx.getAssets().open(f"train_bot_data/{name}")
    reader = jclass("java.io.BufferedReader")(
        jclass("java.io.InputStreamReader")(stream, "UTF-8")
    )
    lines = []
    line = reader.readLine()
    while line is not None:
        lines.append(str(line))
        line = reader.readLine()
    reader.close()
    return "\n".join(lines)


def _log_asset_error(name: str, e: Exception) -> None:
    """In loi ra stderr (Logcat) thay vi nuot am tham - bai hoc that: truoc day _read_asset()
    dung readAllBytes() (chi co tu API 33+, minSdk app la 26) nem AttributeError tren thiet
    bi cu hon, nhung bi except:pass o cac ham _load_* nuot mat -> CITIES/PET_SKILLS/SKILL_INFO
    RONG ma khong ai biet cho toi khi test thuc te tren may that. KHONG raise (giu logic goc
    "an toan neu thieu file"), chi dam bao loi LUON hien ra Logcat de de chan doan lan sau."""
    import sys
    print(f"[config] doc {name} LOI: {type(e).__name__}: {e}", file=sys.stderr)


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
    except Exception as e:
        _log_asset_error("pets.json", e)
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
    except Exception as e:
        _log_asset_error("skills_data.json", e)
    return out


SKILL_INFO = _load_skill_info()


def _load_cities():
    """Doc cities.json (danh sach thanh de teleport, opcode 0x44) - dung cho mode
    'Dung yen tai thanh': key -> (city_id, flag). Ca 2 gia tri BAT BUOC dung cung nhau
    (xem cities.json._packet_format) - flag SAI se bi server tu choi teleport."""
    out = {}
    try:
        d = json.loads(_read_asset("cities.json"))
        for key, info in d.get("cities", {}).items():
            out[key] = (info["city_id"], info["flag"])
    except Exception as e:
        _log_asset_error("cities.json", e)
    return out


CITIES = _load_cities()
