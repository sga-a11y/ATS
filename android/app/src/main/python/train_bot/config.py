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
VANTIEU_ENABLE = True
VANTIEU_PETS = []          # KHONG dung (chi dung che do smart-match qua VANTIEU_REQUESTS)
VANTIEU_PETS_NAMES = []    # KHONG dung (chi dung che do smart-match qua VANTIEU_REQUESTS)
RUN_AROUND_OFFSETS = [(-100, -100), (-200, 0), (-100, 100), (0, 0),
                      (100, -100), (200, 0), (100, 100), (0, 0)]
RUN_STEP_WAIT = 0.7
HP_THRESHOLD = 0.4
SP_THRESHOLD = 0.0
GIFT_MILESTONES = [10, 20, 30, 60, 90, 180]
DUNGEON_RUNS_PER_DAY = 2
MOB_PATHS = {}   # duong di bo trong map (mob_paths.json PC) - APK chua co -> rong (navigate thang)


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


def _load_donate_items():
    """Doc donate_items.json -> {tid:int -> ten}. Item RAC bot tu donate cho quan doan luc login
    (don tui). KEY = TID hex chuoi. Mirror bot/config.py::_load_donate_items."""
    out = {}
    try:
        d = json.loads(_read_asset("donate_items.json"))
        for k, v in d.get("items", {}).items():
            out[int(k, 16)] = v
    except Exception as e:
        _log_asset_error("donate_items.json", e)
    return out


DONATE_ITEMS = _load_donate_items()


def _load_use_items():
    """Doc use_items.json -> {tid:int -> {name, qty:int|None}}. Item tu dung luc login.
    Format value: "Ten" (qty None = dung het, 1/lenh) | {name, qty} (dung toi da qty/login).
    Mirror bot/config.py::_load_use_items."""
    out = {}
    try:
        d = json.loads(_read_asset("use_items.json"))
        for k, v in d.get("items", {}).items():
            tid = int(k, 16)
            if isinstance(v, dict):
                out[tid] = {"name": v.get("name", ""), "qty": v.get("qty"),
                            "phuc_than": bool(v.get("phuc_than", False))}
            else:
                out[tid] = {"name": v, "qty": None, "phuc_than": False}
    except Exception as e:
        _log_asset_error("use_items.json", e)
    return out


USE_LOGIN_ITEMS = _load_use_items()


def _load_events():
    """Doc events.json -> {event_key -> {label, select, staging_map, dest_map, steps, exit}}.
    Mode 'event': tele toi map event roi dung yen. Mirror bot/config.py::_load_events."""
    out = {}
    try:
        d = json.loads(_read_asset("events.json"))
        for k, v in d.get("events", {}).items():
            out[k] = v
    except Exception as e:
        _log_asset_error("events.json", e)
    return out


EVENTS = _load_events()

DIGIOI_LIMIT = 120   # so phut Di Gioi/ngay (khop run_party_digioi.py DIGIOI_LIMIT)


def leaders_for(pidx):
    """White list leader cua party pidx = CHUNG (PARTY_LEADERS) + RIENG (PARTY_LEADERS_BY_IDX).
    Rong het -> nhan moi nguoi moi. GIONG PC (client.py goi config.leaders_for(self.party_idx))."""
    out = list(PARTY_LEADERS)
    for nm in PARTY_LEADERS_BY_IDX.get(pidx, []):
        if nm not in out:
            out.append(nm)
    return out


def record_leader_name(pidx, char_name):
    """Tu dong THEM ten nhan vat leader vao whitelist "leaders" cua party (KHONG xoa/replace ten
    da co san - chi APPEND neu chua co). Mirror bot/config.py::record_leader_name (PC) - user da
    cau hinh account nao la leader trong Party roi thi khong can go tay lai ten o whitelist rieng.
    Goi ngay sau khi leader login xong + biet char_name."""
    if not char_name:
        return
    name = char_name.strip()
    if not name:
        return
    cur = PARTY_LEADERS_BY_IDX.setdefault(pidx, [])
    if any(x.strip().lower() == name.lower() for x in cur):
        return
    cur.append(name)
    try:
        import os
        f = os.path.join(_app_dir(), "accounts.json")
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict) and isinstance(d.get("profiles"), dict):
            prof = d["profiles"].get(d.get("active"))
        else:
            prof = d
        parties = prof.get("parties", []) if isinstance(prof, dict) else []
        if 0 <= pidx < len(parties):
            leaders = parties[pidx].setdefault("leaders", [])
            if not any(x.strip().lower() == name.lower() for x in leaders):
                leaders.append(name)
                with open(f, "w", encoding="utf-8") as fh:
                    json.dump(d, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_vantieu_requests():
    """Doc vantieu_requests.json (bang tra ma yeu cau -> pet phu hop, dung cho che do smart-match
    cua do_van_tieu()). Giu NGUYEN cau truc dict tu file (client.py tu xu ly key/value truc tiep,
    khong can convert kieu nhu pets.json)."""
    try:
        d = json.loads(_read_asset("vantieu_requests.json"))
        return d.get("requests", d)   # ho tro ca 2 dang: co wrapper "requests" hoac phang truc tiep
    except Exception as e:
        _log_asset_error("vantieu_requests.json", e)
        return {}


VANTIEU_REQUESTS = _load_vantieu_requests()


def _load_train_maps():
    """Doc train_maps.json: {map_id(str): {"name", "safe": [[x,y],...], "mobs": [[x,y],...]}}."""
    try:
        d = json.loads(_read_asset("train_maps.json"))
        return d.get("maps", d)
    except Exception as e:
        _log_asset_error("train_maps.json", e)
        return {}


TRAIN_MAPS = _load_train_maps()


def _load_train_routes():
    """Doc train_routes.json: {map_id(str): {"name","from_city","city_flag","dest_map","steps"}}."""
    try:
        d = json.loads(_read_asset("train_routes.json"))
        return d.get("routes", d)
    except Exception as e:
        _log_asset_error("train_routes.json", e)
        return {}


TRAIN_ROUTES = _load_train_routes()


# ============================================================
#  PARTY / ACCOUNT / SERVER - DOC accounts.json (app_dir) + servers.json (asset), GIONG PC.
#  Kotlin ghi accounts.json (format PC) roi goi config.reload_parties() + run_party_digioi.start_all().
# ============================================================
from ._appdir import app_dir as _app_dir

PARTY_LEADERS = []          # white list leader CHUNG (moi party)
CHANNEL = 1
START_CITY_ID = 0
PARTIES = []                # [ [(user,pass),...], ... ] theo pidx
PARTY_CONFIG = {}           # pidx -> {mode, server, server_ip, server_id, city_flag, start_city_id,
                            #          mob_index, do_daily, digioi_mode, event_key}
PARTY_LEADERS_BY_IDX = {}   # pidx -> [ten leader] rieng party
ACCOUNTS = []
ACCOUNT_PARTY = {}
PARTY_LEADER_ACC = {}       # pidx -> username leader (acc dau)


def _load_servers():
    try:
        return json.loads(_read_asset("servers.json")).get("servers", {})
    except Exception:
        return {}


SERVERS = _load_servers()


def _server_ip(name):
    s = SERVERS.get(name)
    return s.get("ip") if s else None


def _server_id(name):
    s = SERVERS.get(name)
    return int(s.get("id", 1)) if s else 1


def _load_accounts_json():
    import os
    try:
        f = os.path.join(_app_dir(), "accounts.json")   # _app_dir() co the nem neu Context chua san sang
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None
    # PROFILES {active, profiles:{ten:{parties,...}}} -> rut cau hinh DANG CHON (giong PC).
    if isinstance(d, dict) and isinstance(d.get("profiles"), dict):
        profs = d["profiles"]
        return profs.get(d.get("active")) or (next(iter(profs.values())) if profs else {})
    return d


def reload_parties():
    """Doc lai accounts.json -> PARTIES/PARTY_CONFIG/PARTY_LEADER_ACC/... (mirror PC config).
    Goi tu Kotlin SAU khi ghi accounts.json, TRUOC khi run_party_digioi.start_all()."""
    global PARTIES, PARTY_CONFIG, PARTY_LEADERS_BY_IDX, PARTY_LEADER_ACC
    global ACCOUNTS, ACCOUNT_PARTY, START_CITY_ID, PARTY_LEADERS, CHANNEL
    _aj = _load_accounts_json()
    PARTY_CONFIG = {}
    PARTY_LEADERS_BY_IDX = {}
    if _aj is None:
        PARTIES = []
    else:
        _praw = _aj.get("parties", [])
        PARTIES = [[(a.get("u", ""), a.get("p", "")) for a in p.get("accounts", [])
                    if a.get("on", True) and not a.get("u", "").lstrip().startswith("#")]
                   for p in _praw]
        for _p in _praw:
            for _a in _p.get("accounts", []):
                _u = _a.get("u", "").lstrip().lstrip("#").strip()
                _h = _a.get("heal")
                if _u and isinstance(_h, dict):
                    ACCOUNT_HEAL[_u] = {k: float(v) for k, v in _h.items()
                                        if k in ("hp_char", "sp_char", "hp_pet", "sp_pet")}
        for _i, _p in enumerate(_praw):
            _srv = _p.get("server", "trieu_van")
            PARTY_CONFIG[_i] = {
                "mode": _p.get("mode", "stand"),
                "start_city_id": int(_p.get("start_city_id", 0)),
                "mob_index": int(_p.get("mob_index", -1)),
                "city_flag": int(_p.get("city_flag", 0)),
                "server": _srv,
                "server_ip": _server_ip(_srv) or GAME_HOST,
                "server_id": _server_id(_srv),
                "do_daily": bool(_p.get("do_daily", _p.get("do_dungeon", True))),
                "digioi_mode": _p.get("digioi_mode", "party"),
                "event_key": _p.get("event_key", ""),
            }
            PARTY_LEADERS_BY_IDX[_i] = list(_p.get("leaders", []) or [])
        if PARTY_CONFIG:
            START_CITY_ID = PARTY_CONFIG[0]["start_city_id"]
        if "channel" in _aj:
            CHANNEL = int(_aj["channel"])
        if "party_leaders" in _aj:
            PARTY_LEADERS = list(_aj.get("party_leaders", []) or [])
    ACCOUNTS = [acc for party in PARTIES for acc in party if acc and acc[0]]
    ACCOUNT_PARTY = {acc[0]: i for i, party in enumerate(PARTIES) for acc in party if acc and acc[0]}
    PARTY_LEADER_ACC = {i: party[0][0] for i, party in enumerate(PARTIES)
                        if party and party[0] and party[0][0]}


try:
    reload_parties()   # lan dau: PARTIES rong (Kotlin populate qua setup_party_runtime khi Start)
except Exception:
    pass
