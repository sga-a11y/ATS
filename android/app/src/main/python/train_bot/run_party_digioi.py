"""PARTY TRAIN DI GIOI - flow tu dong day du.

Flow moi party (slot 0 = chu party / leader, slot 1-4 = member):
  1. Login het cac acc trong party + ket noi game.
  2. Moi acc VAO DI GIOI (solo - KHONG vao duoc khi dang trong party).
  3. Leader chon KENH IT NGUOI nhat -> chia se -> ca party chuyen sang kenh do.
  4. Leader MOI 4 member (quet index nguoi gan; member tu accept qua entity cung party).
  5. Leader CHAY LONG VONG (run-around) den het gio; member tu follow + tu danh.

Chay:  python run_party_digioi.py [so_phut]   (mac dinh chay vo han)
"""
import os, sys, time, json, logging, threading, random, math
try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
from . import config
from . import mob_spots
from . import train_pick
from . import loandau
from . import npc40
from . import floor_crawl
from . import party_engine
from . import party_modes
from . import party_route
from . import train_pick as train_pick_mod   # alias: trong setup_party_runtime co tham so ten train_pick
from .mob_scanner import MobScanSession, compute_regions, scan_full_map
from .scene_fight import get_scene_fight_seed
from .train_maps_store import save_learned_regions
from .login import login
from .client import (ATTR_KEY_TO_CODE, ATTR_CODE_TO_TEN, ATTR_KINDS,
                        save_point_cache, load_point_cache,
                        load_cat_do_items, save_cat_do_items, CAT_DO_CAT, CAT_DO_LAY,
                        save_skill_char_cache, load_skill_char_cache,
                        GameClient, check_duplicate_accounts, joined_member_count, is_joined,
                        is_strategist, reset_party_joined, unmark_joined, mark_joined,
                        set_account_activity, get_account_activity, get_account_task,
                        in_instance_map, in_floor_crawl_map,
                        dat_pha_pho_ban, dang_pha_pho_ban,
                        dat_party_dang_gom, party_dang_gom, dat_nguoi_keo, nguoi_keo,
                        DISCONNECT_RATE_LIMIT, TEAM_DUNGEON_MAPS)

_lvl = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
try:
    # Android: "party.log" (duong dan tuong doi) ghi vao "/" - READ-ONLY tren Android (BUG THAT:
    # OSError Errno 30). Phai ghi vao thu muc rieng cua app (Context.getFilesDir(), xem _appdir.py
    # ben APK). Tren PC import nay FAIL (bot/ khong co _appdir) -> fallback "party.log" nhu cu.
    from ._appdir import app_dir as _app_dir
    _log_path = os.path.join(_app_dir(), "party.log")
except Exception:
    _log_path = "party.log"
# CHAY DUOI UNITTEST -> GHI FILE KHAC. Import module nay trong test se mo DUNG `party.log` ma bot
# THAT dang chay ghi vao, lai con `mode="w"` (truncate). Hau qua da xay ra 07/09: log cua user bi
# tron dong cua test (`[party 78] ... acc0/acc1/acc2`, mot party khong ton tai trong config) va bi
# cat cut - trong khi chinh cai log do dang duoc dung de chan doan loi that.
if "unittest" in sys.modules or os.environ.get("ATS_TEST"):
    _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "party_test.log")
# RotatingFileHandler: gioi han party.log ~1GB (backup 2 -> toi da ~3GB) de file KHONG phinh
# vo han (truoc day 30 party 8h ra 570MB). mode="w" -> van truncate moi lan khoi dong nhu cu.
# Lich su: 50MB -> 100MB -> 500MB (20/08) -> 1GB (30/08). Ly do tang tiep: dieu tra acc ket/party
# dung hinh can log CU hang gio truoc; 100MB voi 30 party chi giu duoc vai chuc phut.
from logging.handlers import RotatingFileHandler as _RotLog
_file_handler = _RotLog(_log_path, mode="w", maxBytes=1024 * 1024 * 1024, backupCount=2,
                        encoding="utf-8")
logging.basicConfig(level=_lvl, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[_file_handler, logging.StreamHandler()])
log = logging.getLogger("partydg")

check_duplicate_accounts(config.PARTIES)   # bao loi neu 1 user dien trung nhieu noi

MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 0   # 0 = vo han

# Trang thai chia se theo tung party: kenh leader chon + co hieu cac buoc
_party_state = {}   # party_idx -> {"channel": ch, "channel_ready": Event, "invited": Event}
_clients = []
_threads = []   # thread tung acc - de biet khi nao TAT CA da thoat
DIGIOI_LIMIT = 120   # so phut Di Gioi/ngay (de tinh "con lai")
HO_PHU_CHECK_SEC = 180   # Di Gioi Ho Phu: check moi 3 phut (login + dinh ky)

# One decision thread per party. Account threads perform login, I/O and engine work.
_party_engines = {}
_party_engines_lock = threading.Lock()


def dung_engine_moi(pidx) -> bool:
    """Every party is owned by its PartyEngine, regardless of the old rollout threshold."""
    return True

# Phuc Than: chay theo SU KIEN (buff tut < 5 / ngoc hong -> client.phuc_than_pending). So nay chi
# la LUOI AN TOAN khi server khong gui goi - truoc day la 1800 (30 phut) va la duong CHINH nen
# phan ung rat cham (ngoc hong phut thu 1 -> mat he so EXP toi 29 phut).
PHUC_THAN_CHECK_SEC = 300


def _map_cau_hinh(raw, gia_tri_bool=False):
    """Map cau hinh tu APK: nhan CHUOI "k=v" moi dong (hoac dict, cho ban PC/test).

    APK **KHONG duoc truyen thang Map/List** qua Chaquopy: ban release bi R8 rut gon ten lop nen
    Python nhan mot object Java, khong phai dict. Hai kieu hong, ca hai deu da xay ra that:
      - `dict(raw)`            -> `TypeError: 'w' object is not iterable` (CRASH, loi APK 04/09;
                                  truoc do la `'t' object` o APK 1.1.202608181827).
      - `isinstance(raw, dict)` -> False -> tra {} IM LANG, tick cua user bi bo qua khong bao gi.
    Nen moi cho truyen map/list qua Chaquopy phai NOI CHUOI o Kotlin (giong `leaders`,
    `eventExchangeItems`, `mobElements`, `save_cat_do_items_str`) va parse lai o day.

    `gia_tri_bool=True`: gia tri "1"/"true" -> True, con lai False (dung cho `box_modes` -
    `tu_mo_hop_trang_bi` doc gia tri kieu bool; de nguyen chuoi thi "false" cung THANH TRUTHY).
    """
    if isinstance(raw, dict):
        out = dict(raw)
    elif isinstance(raw, str):
        out = {}
        for dong in raw.splitlines():
            dong = dong.strip()
            if not dong or "=" not in dong:
                continue
            k, v = dong.split("=", 1)
            out[k.strip()] = v.strip()
    else:
        return {}
    if gia_tri_bool:
        out = {k: (str(v).strip().lower() in ("1", "true", "yes", "on") if not isinstance(v, bool)
                   else v)
               for k, v in out.items()}
    return out


def _scroll_modes_map(raw):
    """{"0xc946": "drop"} (config) -> {51526: "drop"} (client). Chi chua muc user DA DOI khac
    mac dinh (mac dinh: cuon cua tuong co vkcd = keep, con lai = drop) nen cuon moi cua game tu
    theo mac dinh, khong bat user tick lai."""
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if v not in ("keep", "drop"):
                continue
            try:
                out[int(k, 16) if isinstance(k, str) and k.lower().startswith("0x") else int(k)] = v
            except Exception:
                pass
    return out


def _jitter(pt):
    """Xê dịch tọa độ ±10 ngẫu nhiên (9 khả năng) để bot không đứng cùng 1 điểm."""
    dx, dy = random.choice([-10, 0, 10]), random.choice([-10, 0, 10])
    return (pt[0] + dx, pt[1] + dy)


def _xa_diem_quai(pos, spot, nguong=60):
    """Vi tri hien tai co XA diem quai khong (de biet 'du party ma khong danh' la do dung sai cho).

    Nguong 60 > bien do _jitter (+-10) nen dung dung o spot khong bao gio bi coi la xa. pos=None
    (chua biet toa do) -> coi la KHONG xa: khong ro thi dung keo di lung tung.
    """
    if not pos or not spot:
        return False
    return abs(pos[0] - spot[0]) > nguong or abs(pos[1] - spot[1]) > nguong


def _nearest_safe(pos, safes):
    """Diem safe gan vi tri 'pos' nhat (khoang cach binh phuong). pos=None -> diem dau."""
    if not safes:
        return None
    if not pos:
        return safes[0]
    px, py = pos
    return min(safes, key=lambda s: (s[0] - px) ** 2 + (s[1] - py) ** 2)


def _resolve_train_safe(client, map_id, configured_safes):
    ground = client.get_ground_store()
    fingerprint = ground.map_fingerprint(map_id) if ground is not None else None
    if fingerprint:
        cached = mob_spots.load_safe(map_id, fingerprint)
        if cached is not None:
            return cached
    valid = [tuple(map(int, point)) for point in configured_safes or ()
             if len(point) == 2]
    return _nearest_safe(getattr(client, "pos", None), valid)


def _needs_train_safe_bootstrap(login_map, map_id, train_safes):
    return login_map == map_id and not train_safes


def _capture_arrival_safe(client, map_id, came_from_other_map):
    if not came_from_other_map or client.current_map != map_id:
        return None
    ground = client.get_ground_store()
    if ground is None:
        return None
    fingerprint = ground.map_fingerprint(map_id)
    if not fingerprint:
        return None
    cached = mob_spots.load_safe(map_id, fingerprint)
    if cached is not None:
        return cached
    # SAU WARP `pos` bi xoa (=None) va chi co lai khi server gui 0x03 resync. Map dich KHONG co
    # safe cau hinh -> khong navigate (khong cho pos). Cho pos ngan (5s); neu co -> safe = o di
    # duoc gan pos. Neu pos VAN None (vd 14861: leg khong co target_arrival + 0x03 den tre) ->
    # KHONG bo cuoc: dung SEED SceneFight lam safe (diem walkable chuan cua map, cung la noi mob
    # probe di toi). Truoc day thieu fallback nay -> 'khong lay duoc safe' -> TAT PARTY oan
    # (train rung Tan Quan 1 den noi out het).
    _t0 = time.time()
    while not client.pos and getattr(client, "running", True) and time.time() - _t0 < 5.0:
        time.sleep(0.2)
    safe = None
    if client.pos:
        arrival = tuple(map(int, client.pos))
        safe = ground.nearest_walkable_world(map_id, arrival, arrival)
    if safe is None:
        seed = get_scene_fight_seed(map_id)
        if seed is not None:
            safe = ground.nearest_walkable_world(map_id, tuple(map(int, seed)),
                                                 tuple(map(int, seed))) or tuple(map(int, seed))
    if safe is None:
        return None
    safe = tuple(map(int, safe))
    mob_spots.save_safe(map_id, fingerprint, safe)
    log.info("[%s] map %s hoc safe sau warp = %s%s",
             getattr(client, "_label", ""), map_id, safe,
             "" if client.pos else " (tu SEED SceneFight - pos chua ve)")
    return safe


def _train_route_available(smart_route, legacy_route, has_leader):
    return bool(
        smart_route
        or legacy_route
        or (has_leader and getattr(config, "SMART_WORLD_ROUTING", True))
    )


def _needs_train_mob_probe(client, map_id, train_map):
    # XOA safe+mobs = yeu cau quet lai. `pick_train_spot` UU TIEN CAO NHAT map chua co diem nao
    # trong khoang level, nen map do duoc chon ngay va party den quet - khong bi loai khoi vong
    # quay (day la ly do phai co uu tien do; thieu no thi khong ai toi = khong bao gio quet).
    # `rescan` = duong danh dau phu: giu diem cu de van train duoc, nhung toi noi thi quet lai.
    return bool(train_map.get("rescan")) or not bool(train_map.get("mobs"))


def _stationary_train_mob_probe(client, map_id, train_map=None, stop=None, seconds=None,
                                clock=time.monotonic, sleep=time.sleep):
    stop = stop or (lambda: False)
    seconds = float(seconds if seconds is not None else getattr(
        config, "MOB_PACKET_PROBE_SECONDS", 60
    ))
    ground = client.get_ground_store()
    fingerprint = ground.map_fingerprint(map_id) if ground is not None else None
    seed = get_scene_fight_seed(map_id)
    party_entities = (client.known_party_entities()
                      if hasattr(client, "known_party_entities") else set())
    session = MobScanSession(
        map_id, getattr(client, "self_entity", None), party_entities,
        quiet_seconds=0.0,
        min_samples=int(getattr(config, "MOB_SCAN_MIN_SAMPLES", 3)),
        max_patrol_diameter=float(getattr(
            config, "MOB_SCAN_MAX_PATROL_DIAMETER", 800
        )),
        merge_distance=float(getattr(config, "MOB_SCAN_MERGE_DISTANCE", 200)),
    )
    started = clock()
    completed = False
    session.begin_station(started)
    client.begin_mob_observation(session)
    path, count = None, 0
    _lb = getattr(client, "_label", "")
    stations = []          # khai bao TRUOC try: doan ve anh o duoi con dung
    try:
        channel = int(getattr(client, "current_channel", 0)
                      or getattr(config, "CHANNEL", 1) or 1)
        client.switch_channel(channel)
        # DUNG 1 CHO LA DU. Do lai tren capture map 20801: 30s dau tai MOT diem da thay DU
        # 16/16 bai quai (va 16/16 co safe). Di them 5 diem nua ton 5 phut ma con TE HON
        # (quan sat nhieu -> vung 'hazard' phinh -> kho tim safe, chi con 14/16).
        # Truoc day tuong thieu bai la do quet khong het map -> SAI: nguyen nhan that la
        # thuat toan GOM bai theo khoang cach (da sua: 1 con quai = 1 bai).
        if seed is not None:
            stations.append((int(seed[0]), int(seed[1])))
            log.info("[%s] AUTO LEARN map %s: di toi seed SceneFight %s, quan sat %.0fs",
                     _lb, map_id, seed, seconds)
            client.navigate_to(*seed, flee=True, abort=stop)
        else:
            cur = getattr(client, "pos", None)
            if cur:
                stations.append((int(cur[0]), int(cur[1])))
            log.warning("[%s] AUTO LEARN map %s: khong co SceneFight seed, quan sat tai cho %.0fs",
                        _lb, map_id, seconds)
        next_progress = 10.0
        while getattr(client, "running", False) and not stop():
            elapsed = clock() - started
            if elapsed >= seconds:
                completed = True
                break
            if elapsed >= next_progress:
                log.info("[%s] AUTO LEARN map %s: %.0f/%.0fs, %d entity ung vien",
                         _lb, map_id, elapsed, seconds, session.candidate_count())
                next_progress += 10.0
            sleep(min(1.0, max(0.0, seconds - elapsed)))
    finally:
        path, count = client.finish_mob_packet_capture()
        client.end_mob_observation(session)
    start = seed or getattr(client, "pos", None) or (0, 0)
    configured_safes = [tuple(map(int, point)) for point in
                        ((train_map or {}).get("safe", []) or [])
                        if len(point) == 2]
    fallback_safe = _nearest_safe(start, configured_safes)
    if fallback_safe is None and fingerprint:
        fallback_safe = mob_spots.load_safe(map_id, fingerprint)
    learned = compute_regions(
        session, ground, start, fallback_safe=fallback_safe,
        now=clock(), stable_only=False   # thoi diem SAU khi quet xong tat ca diem
    )
    centers = [region.center.point for region in learned]
    safes = [region.safe for region in learned]
    # ANH KET QUA SCAN (chi PC) - de mat nguoi kiem tra nhanh: dia hinh + duong chay tung con
    # quai + bbox + tam bai + safe + cac tram da dung quan sat.
    try:
        from . import scan_image
        _img = scan_image.render_scan(ground, map_id, session.bounded_traces(),
                                      centers, safes, stations=stations)
        if _img:
            log.info("[%s] AUTO LEARN map %s: anh ket qua -> %s", _lb, map_id, _img)
    except Exception as e:
        log.warning("[%s] AUTO LEARN map %s: khong ve duoc anh (bo qua): %s", _lb, map_id, e)
    complete_regions = bool(completed and centers and all(safe is not None for safe in safes))
    if complete_regions and train_map is not None:
        safes = [tuple(map(int, safe)) for safe in safes]
        centers = [tuple(map(int, center)) for center in centers]
        if save_learned_regions(config.TRAIN_MAPS_PATH, map_id, safes, centers):
            train_map["safe"] = safes
            train_map["mobs"] = centers
            for center, safe in zip(centers, safes):
                log.info("[%s] AUTO LEARN map %s: bai %s -> safe %s",
                         getattr(client, "_label", ""), map_id, center, safe)
        else:
            log.warning("[%s] AUTO LEARN map %s: khong ghi train_maps (map da co bai hoac file loi)",
                        getattr(client, "_label", ""), map_id)
    if not centers:
        log.warning("[%s] AUTO LEARN map %s: chua thay trace quai hop le "
                    "(%d packet, file %s)", getattr(client, "_label", ""),
                    map_id, count, path or "khong co")
    return centers


def _resolve_train_mob_centers(client, map_id, train_map, stop=None):
    """Use learned/configured centers; otherwise capture packets while stationary."""
    fallback = [tuple(map(int, point)) for point in (train_map.get("mobs", []) or [])]
    if not getattr(config, "MOB_SCAN_ENABLED", True):
        return fallback
    stop = stop or (lambda: False)
    if fallback:
        log.info("[%s] map %s dung %d diem quai config (khong quet map)",
                 getattr(client, "_label", ""), map_id, len(fallback))
        return fallback
    if stop():
        return []
    return _stationary_train_mob_probe(
        client, map_id, train_map=train_map, stop=stop
    )


def _wait_for_rally(event, stopped, running, st=None, label="", pidx=None):
    """CHO leader chot diem tap ket - NHUNG van NGHE duoc lenh dieu phoi.

    Ban cu: `while not event.wait(2.0)` chi thoat khi Stop / mat ket noi. Vo han, KHONG LOG MOT
    DONG NAO, va DIEC voi moi lenh cap party. Member roi vao day thi bien mat khoi log - nhin
    tuong treo, ma dieu phoi thi ra lenh gom deu deu cho khong ai nghe.

    Ca that party 50, 14/09 (user: "no van dung o thanh"):
        15:15:06 [dakba] (member) SAI MAP (o 15001, can 15861) -> ra vong chinh de nghe lenh
        ... IM HOAN TOAN 16 phut, khong mot dong log ...
        15:22:41 / 15:25:42 / 15:28:42 / 15:31:43 [party 50] REFORM gen -> 4,5,6,7 - party dang o
                                                  2 MAP khac nhau [12001, 15001] -> gom ve cung map
    dakba cho `rally_ready`; leader `dakmot` con o 12001 nen khong bao gio chot rally. Hai ben cho
    nhau, ca party dung im.

    GIO: co lenh MOI (reform_gen tang) -> tra False de acc ra vong chinh thi hanh. Thoat kieu nay
    KHONG phai acc tu quyet - no dang di THI HANH lenh, va lenh do la cua dieu phoi.
    """
    _g0 = int((st or {}).get("reform_gen", 0) or 0)
    _t0 = time.time()
    _log_luc = 0.0
    while not event.wait(2.0):
        if stopped() or not running():
            return False
        if st is not None:
            _g = int(st.get("reform_gen", 0) or 0)
            if _g > _g0:
                log.info("[%s] cho leader chot diem tap ket %.0fs thi CO LENH MOI (reform_gen %d "
                         "-> %d) -> ra vong chinh thi hanh", label or "?", time.time() - _t0,
                         _g0, _g)
                return False
            _viec = (_ke_hoach(st) or {}).get("viec")
            if _viec in (VIEC_GOM, VIEC_DONG_BO):
                log.info("[%s] cho leader chot diem tap ket %.0fs thi DIEU PHOI ra lenh '%s' -> ra "
                         "vong chinh thi hanh", label or "?", time.time() - _t0, _viec)
                return False
        # KHONG im lang: cho lau ma khong log thi nhin log tuong acc chet.
        if time.time() - _log_luc > 60.0:
            _log_luc = time.time()
            log.info("[%s] dang cho leader chot diem tap ket (%.0fs)%s", label or "?",
                     time.time() - _t0, "" if pidx is None else " [party %d]" % (pidx + 1))
    return True


def _go_town_safe(c, label, city_id=12001, flag=0):
    """SACH TRAN (flee) roi BAY VE THANH (mac dinh Trac Quan 12001) - dung khi digioi HET GIO bi
    ket o map quai. Phai cho het tran TRUOC khi teleport (teleport luc dang danh -> server KICK)."""
    c.flee_mode = True
    try:
        c._wait_combat_clear(idle=2.0, cap=15.0)   # flee het tran truoc khi teleport
    except Exception:
        pass
    try:
        c.go_to_town(city_id, flag)
    except Exception as e:
        log.warning("[%s] ve thanh (het gio DG): %s", label, e)


def _use_consumables(c):
    """Hoi HP/SP sau tran (goi NGOAI tran). Bot tu hoc item qua self-calibrate, khong can config.
    - CHAR: closed-loop tren HP/SP live (S2C 0x08) + probe item chua biet de tu hoc.
    - PET: best-effort dung item DA HOC (khong do duoc HP pet ngoai combat -> tinh theo 0x33 cuoi)."""
    c.do_heal()   # hoi char + pet, moi con tu probe/do bang HP cua chinh no

# ==== REGISTRY cho GUI dieu khien tung acc ====
account_clients = {}   # username -> GameClient (doc trang thai live)
account_stops = {}     # username -> threading.Event (GUI yeu cau dung acc nay)
account_threads = {}   # username -> Thread
account_last = {}      # username -> {"map","char"} luc CUOI truoc khi thoat (de biet thoat o dau)
account_exit_reason = {}  # username -> ly do thoat (de tong ket 1 dong khi ca party tat het)
account_furnace_notify = {}  # username -> list item lo can BAO (mode notify) de GUI popup hoi mua

# SAFE BI QUAI DANH: username -> {map, safe, so_tran, tu_luc, lan_bao}
# Diem safe la cho DUNG NGHI giua cac tran. Hoc sai thi acc dung do chiu tran vo han: hoc bang
# `nearest_walkable_outside(clearance=200, max_path=600)` - tuc chi cach cac VET TUAN TRA DA QUAN
# SAT duoc 200, ma lan quet co the chua thay het duong quai di.
#
# Ca that 07/09 party 3, map 21852 (Trai Di Lang2): `safe[2]=(2090,1170)` cach `mob[2]=(1830,1250)`
# dung 272. Ca 5 acc login ve dung safe do roi an don: 147 luot `combat=True` tai (2090,1170) trong
# 19 phut, vi tri chi dao dong 20 don vi - khong he chay di dau.
#
# User chot 07/09: KHONG tu doi safe, KHONG tu quet lai map ("t deo tin may scan lai la on") -
# chi BAO cho user tu kiem. Tinh nang chung cho MOI map.
account_safe_canh_bao = {}
SAFE_DANH_NGUONG = 8       # so tran tai safe truoc khi bao
SAFE_DANH_CUA_SO = 600.0   # ...trong bay nhieu giay
SAFE_GAN = 120             # coi la "dang dung o safe" khi cach safe duoi bay nhieu don vi

# QUANG TRUONG Trac Quan - cho server NHA NGUOI RA sau Di Gioi / sau event (map loan dau 10991 ->
# 12003). KHONG train duoc, KHONG phai thanh (`is_teleport_city(12003)` = False) nen khong the lay
# lam diem tap ket: gom ca party ve day roi cung khong co viec gi lam.
MAP_TRUNG_CHUYEN = 12003


def _ghi_nhan_tran_tai_safe(username, map_id, pos, safe, pos_dang_tin=True):
    """Acc vua VAO TRAN khi dang dung o safe -> dem. Qua nguong thi ghi canh bao cho GUI.

    Chi DEM va BAO - khong tu doi safe, khong tu quet lai map.

    `pos_dang_tin=False` -> BO QUA. `c.pos` la so DEAD-RECKONING bot tu cong sau moi lenh move; khi
    lenh bi tran nuot thi acc dung nguyen cho cu ma so do van chay tiep toi dich. Dem bang so do la
    dem tran cua mot cho KHONG PHAI safe, roi bao "safe hoc SAI" - bao oan.

    User 08/09: "hom qua t check map khac, bot bao safe bi danh, t log vao thi ko he bi danh, chung
    to cai di chuyen ra safe cua may ngu - dang di chuyen ma vao battle thi no bi mat di chuyen
    nhung m van tinh la di chuyen den safe ok".
    """
    if not safe or not pos or not map_id or not pos_dang_tin:
        return
    try:
        if math.dist(tuple(pos)[:2], tuple(safe)[:2]) > SAFE_GAN:
            return
    except Exception:
        return
    now = time.time()
    rec = account_safe_canh_bao.get(username)
    _key = (int(map_id), tuple(int(v) for v in tuple(safe)[:2]))
    if (rec is None or rec.get("key") != _key
            or now - float(rec.get("tu_luc") or 0) > SAFE_DANH_CUA_SO):
        rec = {"key": _key, "map": int(map_id), "safe": list(_key[1]),
               "so_tran": 0, "tu_luc": now, "lan_bao": 0.0}
        account_safe_canh_bao[username] = rec
    rec["so_tran"] += 1
    if rec["so_tran"] >= SAFE_DANH_NGUONG and now - float(rec.get("lan_bao") or 0) > SAFE_DANH_CUA_SO:
        rec["lan_bao"] = now
        rec["luc"] = now
        log.warning("[%s] SAFE BI QUAI DANH: %d tran trong %.0f phut ngay tai safe %s cua map %s "
                    "-> diem safe nay co the hoc SAI, user kiem lai giup",
                    username, rec["so_tran"], (now - rec["tu_luc"]) / 60.0, rec["safe"], rec["map"])


def safe_canh_bao_items(pidx):
    """[{user, map, safe, so_tran, luc}] - safe bi quai danh cua CA party pidx (cho UI)."""
    out = []
    try:
        accs = party_accounts(pidx)
    except Exception:
        return out
    for tpl in accs:
        u = tpl[0] if isinstance(tpl, (tuple, list)) else tpl
        rec = account_safe_canh_bao.get(u)
        if rec and rec.get("lan_bao"):
            out.append({"user": u, "map": rec["map"], "safe": rec["safe"],
                        "so_tran": rec["so_tran"], "luc": rec.get("luc") or rec["lan_bao"]})
    return out


def safe_canh_bao_bo_qua(username):
    """User da xem/sua xong -> bo canh bao cua acc nay."""
    account_safe_canh_bao.pop(str(username or "").strip(), None)
    return True
account_stop_reasons = {}  # username -> ai/nhanh nao set stop_ev gan nhat
account_reconnect = {}
# username -> client CON SONG, trao tay giua 2 pha (DG -> train) de KHOI dang nhap lai.
account_continue = {}     # username -> client CON SONG, trao tay giua 2 pha (DG -> train).
                          # Co gia tri = DOI PHA tai cho, KHONG phai rot: supervisor chay lai
                          # run_account NGAY voi chinh ket noi do, khong dang nhap lai.
account_forced_reconnect = set()  # survivor 40NPC bi dong de relogin cung party; KHONG tang disc_gen
account_forced_reconnect_reason = {}
account_sync_epoch = {}   # username -> epoch dang chay; != st["sync_epoch"] => ep dong bo (relogin)
# username -> so lan DA relogin vi 'ket ngoai DG nhung server con gio'. PHAI de o day (khong
# phai tren client): moi lan relogin, run_account tao GameClient MOI -> dem tren `c` se reset
# ve 0 -> RELOGIN VO HAN va party treo o hang rao 'x/5 acc xong DG' (dung bug cu can tranh).
_dg_stuck_relogin = {}
_start_cancel_generation = 0  # STOP ALL tang so nay de huy chuoi START dang do


class ResyncSignal(BaseException):
    """EP DONG BO - uu tien TUYET DOI. Ke thua BaseException (KHONG phai Exception) de KHONG bi
    cac `except Exception` sau trong barrier nuot mat -> unwind xuyen MOI vong cho vo han, ra thang
    supervisor. Supervisor coi nhu forced-reconnect -> relogin -> duong reconnect tu bam leader
    (clear sach hanh dong + tham so cu, dung nhu yeu cau: dong bo uu tien cao nhat)."""
    pass


def _resync_ck(st, username):
    """Goi trong MOI vong cho vo han (barrier report/relogin PB, reform, sync kenh, keo route, DG...).
    Khi sync_epoch bi bump (leader/GUI/watchdog ep dong bo) -> raise ResyncSignal ngay lan check ke."""
    if account_sync_epoch.get(username) != st.get("sync_epoch", 0):
        raise ResyncSignal


BARRIER_STUCK_SECS = 180.0   # barrier ket qua lau (khong nhich) -> AUTO ep dong bo (watchdog)
RESYNC_COOLDOWN = 300.0      # khong AUTO-resync cung party qua 1 lan / 5p (chong loop relogin)


RESYNC_SOFT_TRIES = 2   # so lan ep dong bo NHE truoc khi buoc phai relogin (nang)


def request_party_resync(pidx, reason="ép đồng bộ", cooldown=0.0, hard=False):
    """EP CA PARTY dong bo lai theo leader.

    NHE (mac dinh) - bump reform_gen: acc dang di duong tu DUNG (navigate_to/follow_path/
    follow_smart_route deu nhan abort=_ab co xet reform_gen), roi ca party gom ve cung thanh +
    cung kenh + lap lai party. KHONG login lai.
    NANG (hard=True) - bump sync_epoch: acc dang cho se raise ResyncSignal -> RELOGIN.

    VI SAO DOI MAC DINH: truoc day CHI co duong nang. Log that (10:55, acc chumuoi): acc VUA LOGIN
    XONG, dang dung DUNG map train 14823, chi vi party co acc khac map ma bi "EP DONG BO -> relogin
    bam leader" - trong khi no chi can DI/TELEPORT. Tu khi server chan toc do dang nhap (ma 90),
    relogin thua nhu vay lam acc ket vong dang nhap hang phut (10:55:21 -> 10:56:26 van chua vao
    duoc). User: "tai sao lai phai relogin, chi can chuyen map thoi chu".

    Van GIU duong nang lam BUOC LEO THANG: nhe RESYNC_SOFT_TRIES lan lien tiep ma party van ket
    thi moi relogin.
    cooldown>0 (auto): bo qua neu vua resync trong `cooldown` giay (chong loop).
    Tra (gen_moi, da_dung_hard) hoac None neu bi cooldown chan."""
    st = _pstate(pidx)
    now = time.time()
    with st["lock"]:
        if cooldown and now - st.get("last_resync_ts", 0.0) < cooldown:
            return None
        st["last_resync_ts"] = now
        st["team_dungeon_need_redo"] = False
        _soft = int(st.get("resync_soft_count", 0))
        if not hard and _soft >= RESYNC_SOFT_TRIES:
            hard = True            # nhe mai khong an -> leo thang
        if hard:
            st["resync_soft_count"] = 0
            st["sync_epoch"] = int(st.get("sync_epoch", 0)) + 1
            ep = st["sync_epoch"]
        else:
            st["resync_soft_count"] = _soft + 1
            ep = _bump_reform(st, "ep dong bo (nhe): " + reason)
    if hard:
        log.warning("[party %s] EP DONG BO NANG (%s) -> sync_epoch=%d, moi acc RELOGIN bam leader",
                    pidx, reason, ep)
    else:
        log.warning("[party %s] EP DONG BO NHE (%s) -> reform_gen=%d, gom ve cung map/kenh "
                    "(KHONG relogin)", pidx, reason, ep)
    return ep, hard


def _barrier_watchdog(st, pidx, t0, tag):
    """Goi moi vong cho: barrier ket > BARRIER_STUCK_SECS -> AUTO ep dong bo (cooldown chong loop).
    Khong tu raise - vong cho da co _resync_ck ngay sau se bat epoch moi va raise ResyncSignal."""
    if time.time() - t0 > BARRIER_STUCK_SECS:
        request_party_resync(pidx, "watchdog:" + tag, cooldown=RESYNC_COOLDOWN)
LOGIN_ERR1_RETRY_MIN_SEC = 60
LOGIN_ERR1_RETRY_MAX_SEC = 120


def _running_party_usernames(pidx):
    return [u for u, _p, _l, _pk in party_accounts(pidx)
            if is_account_running(u) and account_clients.get(u) is not None]


PARTY_EVENT_DUNGEON_WINDOW = 3600.0   # do dai cua so "dang trong kich ban dungeon" cho event party


def _inside_floor_crawl_tower(ev, map_id):
    """Dang DUNG SAN trong thap cua event floor_crawl (2K) chua? (dest_map <= map <= top_map)

    Dung khi login lai giua chung: game GIU nguyen vi tri trong thap. Neu con o trong thap thi
    KHONG duoc chon lai event - goi 0x4d se keo ca doi ve map cho 12921 va MAT HET tang da leo
    (xac nhan log 11:23: acc dang o 12922, sau khi chon event thi smart path chay tren 12921).
    """
    pb = (ev or {}).get("party_battle") or {}
    if pb.get("kind") != "floor_crawl":
        return False
    dest = int((ev or {}).get("dest_map") or 0)
    top = int(pb.get("top_map") or 0)
    try:
        m = int(map_id or 0)
    except (TypeError, ValueError):
        return False
    return bool(dest and top and dest <= m <= top)


def _party_same_map(st, username, cur_map, expected, stopped, label="", role="", wait=30.0,
                    pidx=None):
    """TRUOC KHI SYNC KENH: ca party phai dang o CUNG MOT MAP.

    Sync kenh khi cac acc o KHAC map la VO NGHIA: picker chot expected_map = map cua RIENG no,
    cac acc o map khac bao cao "sai map" mai -> vong sync treo (log 11:57: leader vao lai 12922
    trong khi 3 member con o 12931 -> "cho acc bao cao map (1/4)" khong bao gio xong).
    Ap dung cho MOI mode, khong rieng 2K.

    Tra True neu tat ca cung map (hoac chua doc duoc acc nao khac -> khong co gi de doi chieu).
    """
    # BOT TU THAY map cua tung acc. Ban cu bat acc ghi `presync_maps[username]` roi CHO du bao cao
    # (toi `wait` giay) - vua bat bao cao (L2) vua cho (L9), va acc ban viec khac thi khong bao gio
    # bao -> cho het gio roi quyet voi du lieu thieu.
    maps = set()
    try:
        for _t in party_accounts(pidx) if pidx is not None else ():
            _u = _t[0]
            if _u in st.get("reconnecting", ()):
                continue
            _c = account_clients.get(_u)
            if _c is not None and getattr(_c, "running", False):
                maps.add(int(getattr(_c, "current_map", 0) or 0))
    except Exception:
        pass
    if not maps:
        maps = {int(cur_map or 0)}
    if len(maps) <= 1:
        return True
    log.warning("[%s] (%s) BO QUA sync kenh: party dang o KHAC MAP %s -> sync kenh luc nay vo "
                "nghia (picker se cho bao cao map mai khong xong)", label, role, sorted(maps))
    return False


def _manual_whitelist_names(pidx, c=None):
    """Ten whitelist thoa CA BA dieu kien -> moi duoc cam doi kenh:

      1. KHONG phai acc bot nao dang chay (doi chieu account_clients TOAN BO, moi party -
         nick do co the la bot cua party khac, van la bot, van tu doi kenh duoc).
      2. La nick NGUOI CHOI dieu khien tay (he qua cua 1).
      3. DANG DUNG DO THAT: leader thay entity cua no va no o cung map hien tai.

    Bot doi kenh duoc cho chinh no nhung KHONG doi ho nick tay -> doi la bo roi ho o kenh cu,
    ho khong nhan duoc loi moi party (bug that 15:03). NHUNG chi cam khi ho CO MAT: mot nick
    khong dung do thi giu nguyen kenh chang cuu duoc ai, chi lam party nam rai nhieu kenh ->
    3/4 member khong nhan duoc loi moi -> 1/4 -> giai tan -> lap vo tan (bug that 17:25:
    member o kenh 3/3/2, leader kenh 1, whitelist ['tuyet','chihao'] deu KHONG co entity).
    """
    try:
        wanted = (config.leaders_for(pidx) if hasattr(config, "leaders_for")
                  else list(getattr(config, "PARTY_LEADERS", []) or []))
    except Exception:
        wanted = []
    bots = set()
    for u, cli in list(account_clients.items()):
        bots.add(str(u).strip().casefold())
        nm = getattr(cli, "char_name", None)
        if nm:
            bots.add(str(nm).strip().casefold())
    for u in party_accounts(pidx):
        bots.add(str(u).strip().casefold())

    cands = [str(x).strip() for x in (wanted or [])
             if str(x).strip() and str(x).strip().casefold() not in bots]
    if not cands or c is None:
        return []

    out = []
    for name in cands:
        key = name.casefold()
        ent = None
        for e, names in list((getattr(c, "entity_names", None) or {}).items()):
            if any(str(x).strip().casefold() == key for x in (names or ())):
                ent = e
                break
        if ent is None:
            continue                      # chua thay bao gio -> khong co mat -> KHONG cam
        try:
            visible, _why = c._entity_is_visible_on_current_scene(ent)
        except Exception:
            visible = False
        if visible:
            out.append(name)              # co mat that -> cam doi kenh
    return out


def _party_chet_het(pidx):
    """CA PARTY co chet trong tran vua roi khong - doc HP cua CHINH TUNG ACC.

    Server KHONG gui goi "thang/thua": `S:011-000 <結束戰鬥>` chi mang `roleId + npcIndex`, va
    `FightManager.FightOver` chi `SetWar(EWar.None)`. Client biet chet bang HP
    (`FightField.lua:1034`: `if Hp <= 0 then SetBeh(EFightBeh.Dead)`). Bot lam y het - va lam
    duoc TOT HON client vi ca 5 acc nam trong MOT tien trinh: hoi thang client cua tung dua.

    KHONG dung `npc40.party_defeated(state.allies)`: `allies` la danh sach DONG DOI, chi day du
    khi co `0x0b` party-broadcast va bi `clear()` moi `0x34`. Rong thi no tra
    `bool(known) and alive == 0` = **False** = "khong thua". Log that party 1 (06/09) tang 11:
        15:14:41 [gamo] 2K: xong tran idx=2, party song 0/0     <- ca party vua chet sach
    "0/0" khong phai "song 0 tren 0" ma la "KHONG BIET".

    Moi acc tu chot `chet_tran_nay` LIEN TUC trong tran (xem `client._chot_minh_chet`) vi sau
    tran server hoi/hoi sinh -> doc HP luc do la mat dau vet.
    """
    acc = [account_clients.get(u) for u in _active_party_usernames(pidx)]
    acc = [c for c in acc if c is not None and c.running]
    if not acc:
        return False
    return all(bool(getattr(c, "chet_tran_nay", False)) for c in acc)


def _party_left_tower(pidx, ev):
    """CO acc nao bi VANG khoi thap khong = dau hieu THUA (bay hon -> server day ve out_map).

    party_defeated() doc HP cua allies nen KHONG bat duoc ca nay: acc bay hon bi day ra khoi
    instance, HP cua no van binh thuong -> leader bao "party song 6/6" trong khi thuc te da thua
    (log 13:03: ttbay pos=(502,495) map=12003 con leader van o 12932).
    """
    for u in _active_party_usernames(pidx):
        cli = account_clients.get(u)
        if cli is None or not cli.running:
            continue
        m = int(getattr(cli, "current_map", 0) or 0)
        if m and not _inside_floor_crawl_tower(ev, m):
            log.warning("[P%s] 2K: acc '%s' da VANG khoi thap (map %s) -> coi la THUA", pidx, u, m)
            return True
    return False


def _maps_cua_party(st, pidx):
    """[map] cua cac acc CON SONG trong party - doc THANG client, khong acc nao bao cao.

    Acc dang relogin (`reconnecting`, hoac client da tat) khong tinh: map cua no la so cu."""
    ra = []
    if pidx is None:
        return ra
    try:
        accs = party_accounts(pidx)
    except Exception:
        return ra
    _rec = st.get("reconnecting", ()) if st else ()
    for _t in accs:
        _u = _t[0]
        if _u in _rec:
            continue
        _c = account_clients.get(_u)
        if _c is None or not getattr(_c, "running", False):
            continue
        _m = int(getattr(_c, "current_map", 0) or 0)
        if _m:
            ra.append(_m)
    return ra


def _cung_map_ca_party(pidx, st=None):
    """Ca party (acc con song) co dang o CUNG mot map khong - doc THANG client (L2).

    Doc SAU CUNG, khong dung so chup tu truoc: cac vong cho (ra rally, doi kenh) keo dai hang chuc
    giay, so cu la so cua tinh hinh khac. Chinh cho nay lo ra ca party 10 (10/09): `_tinh` noi
    "lech_kenh" (so cu) trong khi thuc te dang lech MAP.
    """
    _ms = {int(m) for m in _maps_cua_party(st if st is not None else _pstate(pidx), pidx) if m}
    return len(_ms) <= 1


def _2k_regroup_target(st, ev, pidx=None):
    """Tang GOM DOI khi party lech tang: TANG THAP NHAT ma ca doi toi duoc.

    - Ca doi deu trong thap -> min(map): dua o tang thap KHOI PHAI DI, dua tren di bo xuong.
    - Co acc dang o NGOAI event -> phai la cua vao dest_map (12922): acc ngoai tele vao binh
      thuong (go_to_event), acc trong thap di bo xuong day.
    """
    dest = int((ev or {}).get("dest_map") or 0)
    maps = _maps_cua_party(st, pidx)
    if maps and all(_inside_floor_crawl_tower(ev, m) for m in maps):
        return min(maps)
    return dest


def _decide_2k_resume(st, username, cur_map, ev, expected, stopped, label="", pidx=None):
    """Quyet dinh RESUME 2K o CAP PARTY (khong phai tung acc tu quyet).

    Moi acc bao map hien tai; chi RESUME khi CA PARTY deu o trong thap VA CUNG MOT TANG.
    Lech nhau -> ca doi VAO LAI tu 12921 de gom nhau (mat tang da leo, nhung con hon ket).

    Bug that (log 11:56): leader bi day ra 12003 con 3 member con o 12931 -> moi acc tu quyet:
    leader vao lai 12922, member o lai 12931 -> sync map cho vo han (1/4 mai).
    """
    if ((ev or {}).get("party_battle") or {}).get("kind") != "floor_crawl":
        return False   # event khac (40NPC...) -> KHONG dung barrier nay, tranh chan 60s vo ich
    # BOT TU THAY map cua tung acc. Ban cu: moi acc ghi `event_start_map[username]` roi CHO du bao
    # cao toi 60 giay - bat bao cao (L2) + cho (L9), ma acc ban viec khac thi khong bao gio bao.
    maps = _maps_cua_party(st, pidx)
    if not maps:
        try:
            maps = [int(cur_map or 0)]
        except (TypeError, ValueError):
            maps = [0]
    inside = [_inside_floor_crawl_tower(ev, x) for x in maps]
    same = len(set(maps)) == 1
    ok = bool(maps) and all(inside) and same
    if not ok and any(inside):
        log.warning("[%s] 2K: party KHONG cung cho (map=%s) -> ca doi VAO LAI tu dau de gom nhau",
                    label, sorted(set(maps)))
    return ok


def _set_party_quest_mode(pidx, on, label="", quiet=False):
    """Bat/tat quest_mode cho CA party (leader + member).

    Event danh theo party (40NPC, 2K) phai EP quest_mode thay vi de auto-latch quyet dinh:
    latch chi bat khi quai > 6 luc vao tran (state.py) -> tran it quai la mat skill toan man.
    Member KHONG chay vong dieu khien nao ca (bi keo vao tran cua leader) nen phai set ho.

    PHAI set kem `_team_dungeon_until`: het moi tran, handler 0x14 sub0700 goi
    reset_enemies(reset_quest=not _in_team_dungeon) -> THIEU cua so nay thi quest_mode vua ep bi
    XOA ngay sau tran DAU TIEN. Truoc day chi leader co cua so (dat trong floor_crawl) nen chi
    leader giu duoc quest_mode; member tu tran 2 tro di tut ve TRAIN mode - xac nhan qua log:
    tttam tran 1 danh 10012 (skill toan man), tran 2 danh 10005 (Nem Da, combo train).
    => GOI LAI ham nay sau MOI tran de gia han cho ca party.
    """
    n = 0
    until = (time.time() + PARTY_EVENT_DUNGEON_WINDOW) if on else 0.0
    for u in _active_party_usernames(pidx):
        cli = account_clients.get(u)
        if cli is not None and cli.running:
            cli.state.quest_mode = bool(on)
            cli._team_dungeon_until = until
            n += 1
    if not quiet:
        log.info("[%s] quest_mode=%s cho %d acc trong party", label or ("P%s" % pidx), bool(on), n)


def _active_party_usernames(pidx):
    """Acc dang duoc START, ke ca dang reconnect/chua vao world xong."""
    active = []
    for u, _p, _l, _pk in party_accounts(pidx):
        if not is_account_running(u):
            continue
        ev = account_stops.get(u)
        if ev is not None and ev.is_set():
            continue
        active.append(u)
    return active


def _dt_party_usernames(pidx):
    users = []
    for u, _p, _l, _pk in party_accounts(pidx):
        ev = account_stops.get(u)
        if ev is not None and ev.is_set():
            continue
        users.append(u)
    return users


def _login_error_code(exc):
    code = getattr(exc, "error_code", None)
    if code is not None:
        return code
    data = getattr(exc, "data", None)
    if isinstance(data, dict):
        return data.get("error_code")
    return None


def _login_error_message(exc):
    data = getattr(exc, "data", None)
    if isinstance(data, dict):
        msg = data.get("message")
        if msg is not None:
            return str(msg)
    return str(exc)


def _party_exit_summary(pidx, exclude_user):
    """Goi trong finally moi acc. Neu MOI acc khac cua party da tat -> log 1 DONG TONG KET
    o cuoi: party thoat het vi ly do gi (gom theo ly do). Chi log 1 lan/lan-chay."""
    st = _pstate(pidx)
    accs = [u for u, _p, _l, _pk in party_accounts(pidx)]
    for u in accs:
        if u == exclude_user:
            continue
        t = account_threads.get(u)
        if t is not None and t.is_alive():
            return   # con acc khac dang chay -> chua phai ca party tat
    with st["lock"]:
        if st.get("summary_done"):
            return
        st["summary_done"] = True
    # gom username theo ly do; moi nick kem MAP luc thoat -> biet vi tri ca party
    groups = {}
    for u in accs:
        r = account_exit_reason.get(u, "ket thuc binh thuong (het gio hoac GUI dung)")
        last = account_last.get(u, {})
        nm = last.get("char") or u
        mp = last.get("map")
        groups.setdefault(r, []).append(f"{nm}@map{mp}" if mp is not None else f"{nm}@?")
    parts = "; ".join(f"{r} [{', '.join(us)}]" for r, us in groups.items())
    log.warning(">>> PARTY %s DA THOAT HET vi: %s", pidx + 1, parts)
    # them 1 dong liet ke RO map tung nick (de soi nick nao sai map)
    pos = ", ".join(f"{(account_last.get(u, {}).get('char') or u)}=map{account_last.get(u, {}).get('map')}"
                    for u in accs)
    log.warning(">>> PARTY %s vi tri tung nick: %s", pidx + 1, pos)


def _dem_san_sang(pidx):
    """So MEMBER da san sang vao party - DOC THANG tung client (`_san_sang_party`).

    Bot dieu khien acc nen bot BIET dua nao da xong viec vat dau phien; khong acc nao phai ghi ten
    minh vao mot bang cap party (`ready_members` cu). Bang do con om stale qua cac lan relogin."""
    n = 0
    try:
        accs = party_accounts(pidx)
    except Exception:
        return 0
    for _t in accs:
        _c = account_clients.get(_t[0])
        if _c is not None and getattr(_c, "running", False) and getattr(_c, "_san_sang_party", False):
            n += 1
    return n


def _party_map_barrier(st, username, self_ok, expected, stopped, pidx=None, train_map=None):
    """CA PARTY co dang o train map khong - BOT TU THAY, khong acc nao bao cao.

    Ban cu: moi acc ghi map_results[username] = self_ok roi CHO du bao cao (`while True`).
    Hai cai sai cung mot luc - bat acc khai (L2) va cho acc khac (L9). Acc ban viec khac thi khong
    khai -> ca party cho mai.

    Gio doc thang `account_clients[u].current_map`. Khong bang, khong cho, tra loi ngay."""
    if pidx is None or not train_map:
        return bool(self_ok)
    try:
        accs = party_accounts(pidx)
    except Exception:
        return bool(self_ok)
    for _t in accs:
        _u = _t[0]
        if _u in st.get("reconnecting", ()):   # dang relogin -> khong ket toi
            continue
        _c = account_clients.get(_u)
        if _c is None or not getattr(_c, "running", False):
            continue
        if int(getattr(_c, "current_map", 0) or 0) != int(train_map):
            return False
    return True


def _ghi_sync_that_bai(st, username, current_map, sync_gen, expected_map, label=None):
    """Acc thay MINH sai map sau khi doi kenh -> bao HONG vong sync (khong phai "bao cao map").

    Ban cu con ghi ca `channel_map_reports[username] = (ok, map)` de leader DEM du nguoi. Do la
    bang bao cao - vi pham L2: ca party chay chung MOT tien trinh, leader doc thang
    `account_clients[u].current_map` va `kenh_that()` la biet het, khong can ai khai bao. Va bat
    khai bao thi acc nao ban viec khac se khong khai -> leader dem thieu -> TIMEOUT 60s -> reform
    -> lap lai (log that party 18, 23:36-23:43: leader dot 6 phut voi "cho acc bao cao map (1/5)"
    trong khi 4 member da o dung map tu dau).

    Chi con giu MOT viec: dat co HONG, vi do la thu leader khong the tu thay (map dung ma van hong
    thi khong co dau hieu ngoai le)."""
    map_ok = expected_map is None or current_map == expected_map
    with st["lock"]:
        if st.get("channel_sync_gen") != sync_gen:
            return False
        if not map_ok:
            st["channel_failed_reason"] = "%s map=%s, can=%s" % (
                label or username, current_map, expected_map,
            )
            st["channel_failed"].set()
    return map_ok


def _prepare_reform_channel_sync(st):
    """Khong cho member dung channel_ready cua generation truoc khi leader mo sync reform moi."""
    with st["lock"]:
        st["channel_ready"].clear()
        st["channel"] = None


def _dong_vong_sync(st):
    """DONG CUA mot vong dong bo kenh da hong.

    Bat buoc goi o MOI duong thoat that bai cua `do_channel_sync`. Khong dong thi `channel_ready`
    ket o trang thai SET vinh vien, va moi acc dang cho/dang do trong vong deo cung mot lenh da
    chet. Bug that P3 (06/09, ket 1 tieng): batbat vao kenh 15 that bai luc 02:38:31, leader
    thoat vong sync luc 02:38:32 ma khong xoa co -> batbat do lai den 03:34 van chua ra, leader
    lap "CHO du member san sang (3/4)" 28 lan.
    """
    with st["lock"]:
        st["channel_ready"].clear()
        st["channel"] = None
        st["channel_failed"].clear()
        st["channel_failed_reason"] = ""


def _event_battle_kind(mode, has_leader, ev):
    """Kieu danh cua event CO LAP PARTY: 'npc_repeat' (40NPC) | 'floor_crawl' (2K) | None."""
    battle = (ev or {}).get("party_battle") or {}
    kind = battle.get("kind")
    if mode == "event" and has_leader and kind in ("npc_repeat", "floor_crawl"):
        return kind
    return None


def _is_party_event(mode, has_leader, ev):
    """Event can LAP PARTY roi moi danh (hoan moi party + sync kenh LAI tai map event).
    Dung chung cho 40NPC lan 2K - phan khac nhau nam o buoc bat dau danh."""
    return _event_battle_kind(mode, has_leader, ev) is not None


def _is_npc_repeat_party_event(mode, has_leader, ev):
    return _event_battle_kind(mode, has_leader, ev) == "npc_repeat"


def _ev_cua_party(pcfg):
    """Ban ghi event cua party (giong duong `run_account` lay) - dung o cap dieu phoi."""
    try:
        ev = config.event_hom_nay(pcfg.get("event_key") or "")
    except Exception:
        ev = None
    if ev is None:
        _evs = getattr(config, "EVENTS", {}) or {}
        if _evs:
            ev = _evs[next(iter(_evs))]
    return ev


def _mode_can_lap_doi(pidx):
    """MODE NAY CO CAN LAP DOI KHONG - thuoc tinh cua MODE, khong phai cua tinh huong.

    `False` = moi acc tu lam viec cua no, KHONG bao gio can chung doi. Voi mode nhu vay thi TOAN BO
    duong lenh cap party tat han: khong lap doi, khong gom map, khong dong bo kenh, khong bump
    reform. Khong phai "tam thoi bo qua" - la khong co viec do ngay tu dau.

    Hien co MOT mode nhu vay: LOAN DAU (`party_battle.kind == "chaos_vs"`). Moi acc tu dang ky, tu
    ghep tran; roster cua nhau la RAC (party 24, 10/09: `daim01=0 daim02=0 ...`, party 21:
    `dieu906=4 dieu907=1 dieu908=2 dieu909=3 dieu910=4` - moi acc thay mot kieu). Ra lenh cap party
    o day khong chi vo ich ma con PHA:
      * doi kenh  -> mat cho da dang ky, acc cho ghep tran toi het gio roi thoi
        20:23:14 [haba] Loan dau: da dang ky, cho ghep tran   <- dang ky o KENH 4
        20:23:19 [haba] Doi kenh OK -> 2                      <- dieu phoi keo sang kenh 2
        20:38:14 [haba] Loan dau: cho ghep tran qua 900s khong vao -> dung
      * bump reform -> abort acc dang cho ghep tran, cung mat luot

    User 10/09: "ko phai chan, ma dieu phoi phai biet mode nay deo can lap pt". Truoc do toi di vao
    lam guard rai rac o tung ham - moi guard la mot cho co the quen, va da quen that: chan o
    `_engine_chot_kenh` roi nhung `_dieu_phoi_quyet` van ra `viec=moi/gom/dong_bo` (party 24).
    """
    try:
        _pc = getattr(config, "PARTY_CONFIG", {}).get(pidx, {}) or {}
        if _pc.get("mode") != "event":
            return True
        _ev = config.event_hom_nay(_pc.get("event_key") or "")
        return _event_solo_battle_kind(_pc.get("mode"), _ev) not in _SOLO_BATTLE_EVENTS
    except Exception as e:
        log.debug("[party %d] loi doc mode co can lap doi: %s", pidx + 1, e)
        return True        # khong biet -> cu coi la CAN (giu hanh vi cu, khong tat nham)


def _party_40npc_ngoai_gio(pidx, pcfg):
    """Party mode 40NPC va DANG NGOAI GIO event -> KHONG con viec gi o cap party.

    Ngoai gio, moi acc chi lam mot viec SOLO: di NPC map 12003 doi 'qua chien dau 40NPC' roi thoat
    game (`claim_40npc_reward`). Khong danh, khong lap doi, khong dung chung kenh.

    Vay ma dieu phoi van chay day du: chot kenh dich, ra lenh doi kenh, va ra lenh GOM vi "lech map
    [10991, 12003]" - trong khi 12003 CHINH LA cho doi thuong, tuc lech map luc do la dung y do.

    Ca that 09/09 sau 22h (user: "mode 40npc, ngoai gio event thi chi log vao va di doi thuong roi
    out, m con phai dong bo kenh lam lon gi"):
        22:00:31 [party 49] gen 26: pha=event map=12003 viec=lam - con lech map [10991, 12003]
        22:00:37 [party 49] gen 27: viec=gom - party dang o 2 MAP khac nhau [10991, 12003]
        22:00:30 [dakbon]   DIEU PHOI GUI doi kenh 2 (dang o 1) -> ket qua 4
        22:00:33 [quanmot]  (LEADER) DIEU PHOI chot kenh 14, minh dang o 1 -> tu chuyen
    Lenh doi kenh keo acc ra khoi viec no dang lam, va con dinh ma 4 (kenh day) nen lap lai mai.
    """
    if (pcfg or {}).get("mode") != "event":
        return False
    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    ev = _ev_cua_party(pcfg)
    if not _is_npc_repeat_party_event("event", has_leader, ev):
        return False
    try:
        return not npc40.in_event_window()
    except Exception:
        return False


# Event SOLO: moi acc TU danh, KHONG lap party, KHONG can leader, khong sync kenh.
_SOLO_BATTLE_EVENTS = ("chaos_vs",)


def _event_solo_battle_kind(mode, ev):
    """Kieu danh cua event SOLO ('chaos_vs' = loan dau loi dai) | None.

    Day la DANG THU BA cua event. Truoc day chi co hai: 'co leader -> lap party roi danh'
    (npc_repeat/floor_crawl) va 'khong leader -> dung yen cho dieu khien tay'. Loan dau khong
    lap party nhung VAN phai tu danh -> phai tach ham rieng.

    KHONG duoc nhet 'chaos_vs' vao `_event_battle_kind`: lam vay se keo theo ca duong lap party
    + sync kenh lai + barrier cua 40NPC/2K, tuc pha duong dang chay cua hai event kia.
    """
    if mode != "event":
        return None
    kind = ((ev or {}).get("party_battle") or {}).get("kind")
    return kind if kind in _SOLO_BATTLE_EVENTS else None


def _loandau_ra_khoi_map(c, ev, label):
    """Ra khoi map loan dau (10991 -> 12003) truoc khi tat game.

    KHONG co buoc doi thuong - server TU trao (user xac nhan 25/08). Nhung van phai ra khoi map
    event: de nguyen trong 10991 thi lan login sau bot bat dau tu map event, khong phai tu thanh.
    Dang o map khac roi thi khong lam gi.
    """
    try:
        # SAN VO GIOI (lien server, THU 7): KHONG phai lam gi ca - cu tat acc.
        #
        # User chot 05/09 sau khi chay that: map event nam tren MAY KHAC, ma login lan sau luon
        # vao MAY GOC -> thoat game la ra khoi map event luon. Khac han thu 3 (map 10991 cung
        # may) - o do khong ra thi lan sau bot khoi dong tu map event chu khong tu thanh.
        #
        # Nen bo han buoc "chay ra NPC roi cho server bao ve may goc": no chi them mot cho co
        # the hong (dialog tren map la, giua luc con dang danh do) ma khong duoc gi.
        if getattr(c, "tren_vo_gioi", False):
            log.info("[%s] Loan dau: dang o san vo gioi (may khac) -> tat acc luon, login sau "
                     "server tu dua ve may goc", label)
            return True
        if int(c.current_map or 0) != int((ev or {}).get("dest_map") or 0):
            return False
        return bool(c.exit_event(ev))
    except Exception as e:
        log.warning("[%s] Loan dau: loi ra khoi map event: %s", label, e)
        return False


def _should_restart_event_party(event_party_mode, battle_active, disc_gen, handled_gen):
    return bool(event_party_mode and battle_active and disc_gen > handled_gen)


def _should_restart_mode_after_disconnect(train_on_map, reconnecting):
    """Train must regroup even when the disconnected account relogs between keepalive ticks."""
    return bool(train_on_map or reconnecting)


def _should_reform_incomplete_party(train_on_map, joined, needed, elapsed, threshold=20.0):
    return bool(train_on_map and needed > 0 and joined < needed and elapsed >= threshold)


def _party_train_tai_cho(maps, kenhs, train_map):
    """CA PARTY DA O MAP TRAIN chua? -> 'cung_kenh' | 'lech_kenh' | 'lech_map'.

    User chot 27/08: "cung o map train roi thi check kenh, neu cung kenh roi thi lap party keo ra
    train, ko cung kenh thi sync kenh thoi, ko can ve thanh". Truoc day moi lan thieu nguoi trong
    party la _do_reform() -> teleport CA PARTY ve thanh roi di bo/route len lai, du ai cung dang
    dung san o bai train -> mat vai phut va de lac them nguoi giua duong.

    Chua doc duoc kenh cua ai (None) thi KHONG dam ket luan 'cung kenh' - coi la lech de di
    duong sync kenh (sync tai cho, van khong ve thanh).
    """
    try:
        tm = int(train_map or 0)
    except (TypeError, ValueError):
        tm = 0
    ms = {int(m) for m in (maps or []) if m is not None}
    if not tm or not ms or ms != {tm}:
        return "lech_map"
    ks = [k for k in (kenhs or [])]
    if any(k is None for k in ks) or len({int(k) for k in ks if k is not None}) > 1:
        return "lech_kenh"
    return "cung_kenh"


def _should_resync_incomplete_digioi_party(
        is_digioi, digioi_solo, joined, needed, elapsed, threshold=20.0):
    return bool(is_digioi and not digioi_solo and needed > 0
                and joined < needed and elapsed >= threshold)


def _leader_tu_kiem_kenh(c, st, label=""):
    """LEADER tu gui lenh doi kenh ve dung kenh party TRUOC KHI moi.

    Member co vong retry nen 60s lai `switch_channel` mot lan -> kenh cua ho luon duoc server
    tra loi va cap nhat. LEADER thi chi doi kenh MOT LAN luc sync roi thoi, khong ai kiem lai:
    no bi day sang kenh khac (chet ve thanh, server dieu) ma `current_channel` van giu so cu ->
    bot bao "ca party cung kenh" trong khi leader dung mot noi (user log nick vao game xem 30/08:
    kenh 10 KHONG co nanam, trong khi bot bao no o 10).

    Gui lenh la CACH DUY NHAT xac minh duoc kenh (khong co truy van - xem `GameClient.kenh_that`):
    dang o dung kenh -> server tra ma 1 <trung khu dang o>; lech -> no keo ve dung kenh luon.
    """
    # `kenh_dich` (lenh dieu phoi) DUNG TREN `channel` (so picker tu chon). Hai so nay tung song
    # song va giang leader qua lai moi 8 giay - xem ghi chu o cho picker dang ky `kenh_dich`.
    ch = st.get("kenh_dich") or st.get("channel")
    if not ch:
        return True
    # Moi 30s mot lan la du: vong moi party chay moi vai giay, kiem tra moi lan thi tung luot moi
    # phai cho ack (toi 6s) -> cham han viec gom party.
    if time.time() - float(getattr(c, "_leader_kiem_kenh_at", 0.0) or 0.0) < 30.0:
        return True
    c._leader_kiem_kenh_at = time.time()
    try:
        _truoc = getattr(c, "current_channel", None)
        # wait/retries NHO: day chi la kiem tra dinh ky, khong phai lan doi kenh chinh. Cho lau
        # la chan ca vong moi party (log 30/08 21:09: 2 luot x 6s TIMEOUT moi 30s).
        ok = c.switch_channel(int(ch), wait=2.5, retries=1)
        if not ok:
            _res = getattr(c, "_chan_switch_result", None)
            if _res in (2, 4):
                # 2 = KHONG CO khu do | 4 = kenh DA DAY. Kenh chot cua party la kenh KHONG VAO
                # DUOC: giu nguyen thi ca party doi mai mot cho khong ai toi duoc.
                #
                # Log 31/08 party 1 (13:33-13:49): `st["channel"]=3` ma ca leader lan 3 member deu
                # `Doi kenh 3 THAT BAI: khong co khu do de doi (result=2)`. Member bao "-> bao
                # leader pick lai" roi nam cho `channel_ready` (khong ai set lai), con leader thi
                # "van moi, vong sau kiem lai" -> moi 13s/lan suot 16 phut, `da join=1`.
                log.warning("[%s] (LEADER) tu kiem kenh: kenh party %s KHONG VAO DUOC (%s) -> BO "
                            "kenh nay, chon lai kenh khac cho ca party", label, ch,
                            "khong ton tai" if _res == 2 else "DA DAY")
                with st["lock"]:
                    st["channel"] = None
                    st["channel_ready"].clear()
            else:
                # KHONG chan viec moi party: doi kenh hong la chuyen rieng, con moi thi cu moi.
                log.warning("[%s] (LEADER) tu kiem kenh: chua ve duoc kenh party %s (nho san %s) "
                            "-> van moi, vong sau kiem lai", label, ch,
                            getattr(c, "current_channel", None))
        elif _truoc is not None and int(_truoc) != int(ch):
            log.warning("[%s] (LEADER) tu kiem kenh: dang o kenh %s chu KHONG phai %s -> da doi ve",
                        label, _truoc, ch)
        return ok
    except Exception as e:
        log.warning("[%s] (LEADER) tu kiem kenh loi (bo qua): %s", label, e)
        return True


def _invite_party_participants(c, train_on_map, gap=1.0):
    """RULE: LUON moi acc WHITELIST TRUOC, bot member SAU.

    Whitelist la nguoi that/nick tay - khong co bot tu accept, can them thoi gian bam dong y;
    moi ho truoc thi trong luc bot lan luot accept thi ho cung kip vao. Moi sau (nhu truoc day
    o duong event/thuong) thi party co the da DU cho bot -> nguoi that KHONG con cho de vao.
    Duong train da lam dung tu truoc (invite_train_party_participants); day la lam cho duong
    con lai giong het.

    LEADER TU KIEM KENH TRUOC KHI MOI: xem `_leader_tu_kiem_kenh`. Dat o day vi day la CUA DUY
    NHAT ma leader di qua khi moi party (8 cho goi toi).

    HAM NAY CHI THI HANH - no KHONG quyet dinh co moi hay khong. Quyet dinh do la cua dieu phoi
    (`VIEC_MOI`), va nguoi doc lenh la `_moi_theo_dieu_phoi`.
    """
    if train_on_map:
        return c.invite_train_party_participants(gap=gap)
    whitelist_count = 0
    try:
        whitelist_count = c.invite_whitelist_leaders(gap=gap)
    except Exception as exc:
        log.warning("[%s] (LEADER) moi whitelist truoc party loi: %s",
                    getattr(c, "_label", "?"), exc)
    return whitelist_count, c.invite_members(gap=gap)


def _invite_whitelist_followers_if_bot_party_ready(c, st, pidx, label, force=False):
    """Leader moi them acc ngoai whitelist SAU khi bot members da du.

    Acc ngoai vao hay khong KHONG tinh vao joined_member_count va khong chan flow bot.
    """
    needed = int(st.get("n_members") or 0)
    if needed > 0 and joined_member_count(pidx) < needed:
        try:
            known = {bytes(e) for e in c.known_party_entities()}
            roster = {bytes(e) for e in (getattr(c, "party_members", None) or [])}
            self_ent = bytes(c.self_entity) if getattr(c, "self_entity", None) else None
            bot_roster = {e for e in roster if e in known and e != self_ent}
        except Exception:
            bot_roster = set()
        if len(bot_roster) < needed:
            return 0
    now = time.time()
    last = float(st.get("whitelist_invite_at") or 0.0)
    if not force and now - last < 60:
        return 0
    st["whitelist_invite_at"] = now
    fn = getattr(c, "invite_whitelist_leaders", None)
    if not fn:
        return 0
    try:
        n = fn(gap=1.0)
        if n:
            log.info("[%s] (LEADER) da moi them %d acc whitelist ngoai party (khong doi accept)",
                     label, n)
        return n
    except Exception as e:
        log.warning("[%s] (LEADER) moi whitelist ngoai party loi: %s", label, e)
        return 0


def _party_is_in_train_phase(pcfg, st):
    raw_mode = pcfg.get("mode")
    if raw_mode == "train":
        return True
    if raw_mode == "digioi_train":
        return st.get("dt_phase") == "train"
    if raw_mode:
        return False
    return pcfg.get("start_city_id") in getattr(config, "TRAIN_MAPS", {})


def _average_party_levels(rows):
    levels = []
    for row in rows:
        char_level = row.get("char_level")
        if not isinstance(char_level, int) or char_level <= 0:
            return None
        levels.append(char_level)
        if row.get("pet_name"):
            pet_level = row.get("pet_level")
            if not isinstance(pet_level, int) or pet_level <= 0:
                return None
            levels.append(pet_level)
    if not levels:
        return None
    return (sum(levels) + len(levels) // 2) // len(levels)


def _party_level_rows(pidx):
    """(char_level, pet_name, pet_level) cua tung acc trong party - NGUON DUY NHAT.

    Acc dang chay thi doc thang client; acc da tat thi lay ban luu `account_last`.

    Truoc day doan nay bi CHEP HAI LAN (`_party_average_level` va `_party_levels`) - cung mot cach
    doc, chi khac cach gop cuoi. User 14/09: "da co cho tinh lv trung binh roi ma cho nay lai tinh
    lai a". Chep tay o dau la o do lech: sua nguon level o mot ham thi ham kia van doc kieu cu.
    """
    rows = []
    for username, *_ in party_accounts(pidx):
        c = account_clients.get(username)
        if c is not None:
            rows.append({
                "char_level": getattr(c, "char_level", None),
                "pet_name": c.pet_name_out(),
                "pet_level": getattr(c, "pet_level", None),
            })
        else:
            rows.append(account_last.get(username, {}))
    return rows


def _party_average_level(pidx):
    if pidx is None:
        return None
    return _average_party_levels(_party_level_rows(pidx))


def _party_levels(pidx):
    """Level CUA CA CHAR VA PET moi thanh vien -> list phang, cho train_pick.

    Cung nguon voi `_party_average_level` (`_party_level_rows`), chi khac cach gop: o day acc nao
    chua biet level thi BO QUA thay vi tra None ca cum. Chon map bang du lieu thieu van hon la
    khong chon duoc (acc dang goi ham nay chac chan da login xong nen luon co it nhat 1 level; acc
    khac lay account_last da luu tu lan chay truoc).
    """
    out = []
    for row in _party_level_rows(pidx):
        lv = row.get("char_level")
        if isinstance(lv, int) and lv > 0:
            out.append(lv)
        if row.get("pet_name"):
            plv = row.get("pet_level")
            if isinstance(plv, int) and plv > 0:
                out.append(plv)
    return out


def _acc_cho_level(pidx):
    """Acc PHAI co level truoc khi chot cap quai DG / map train = MOI acc trong party, TRU acc
    user da bam Stop.

    KHONG loc theo `is_account_running`: start_party tao thread LECH NHAU vai giay, acc chua kip
    tao thread se bi coi la "khong chay" -> barrier qua ngay bang 1 acc, dung y het bug cu.
    """
    out = []
    for username, *_ in party_accounts(pidx):
        ev = account_stops.get(username)
        if ev is not None and ev.is_set():
            continue      # user chu dong tat acc nay -> khong cho no nua
        out.append(username)
    return out


def _acc_thieu_level(pidx):
    """Acc chua san sang gop level = CHUA CO CHAR LEVEL. Pet KHONG tinh.

    Tra list mo ta `"<acc>(<thieu gi>)"` - khong phai ten tron. Ca ba cho goi deu chi dem va LOG,
    ma "thieu" ma khong noi thieu gi thi doc log van phai doan tiep.

    User 14/09: "chon bai train thi dua vao lv nhung con hien tai thoi, dua nao thieu pet thi ke
    me no di".

    Truoc day con doi ca `active_pet_confirmed`, ly do la pet level thuong cao hon char vai chuc
    (log 05/09: char ~154 / pet ~188) nen chot khi moi co char se tut hang bai. Cai gia phai tra
    qua dat: chua chot duoc bai -> `st["auto_train"]` rong -> dieu phoi KHONG BIET map train dich
    -> khong biet thanh tap ket -> ca party lap party bua o thanh di ngang qua (Trac Quan), lap
    xong teleport lam tan doi, quay vong. Mot con pet chua kip xac nhan khoa CA chuoi dieu phoi.
    Chon bai hoi thap con sua duoc; party khong bao gio hinh thanh thi khong.

    KHONG acc nao bi loai khoi phep tinh, va cung KHONG co so 0 nao duoc cong vao: `_party_levels`
    tra list PHANG cac level DANG CO MAT - char level cua moi acc, cong them pet cua acc nao dang
    tha pet. Acc thieu pet gop MOT so thay vi hai. Trung binh van la trung binh cua nhung con co
    mat, khong bi keo tut.
    """
    thieu = []
    for username in _acc_cho_level(pidx):
        c = account_clients.get(username)
        if c is None:
            lv = (account_last.get(username) or {}).get("char_level")
            if not (isinstance(lv, int) and lv > 0):
                thieu.append("%s(chua login, khong co ban luu)" % username)
            continue
        lv = getattr(c, "char_level", None)
        if not (isinstance(lv, int) and lv > 0):
            thieu.append("%s(char_level=%r)" % (username, lv))
    return thieu


# Chan chot bai lau hon bay nhieu giay thi PHAI NOI RA (moi 60s mot dong).
CHOT_BAI_BI_CHAN_BAO_SEC = 60.0


def _bao_chan_chot(pidx, st, viec, thieu):
    """Noi ro VI SAO chua chot duoc cap quai DG / map train, thay vi `return None` cam lang.

    Hai ham chot deu tra None im lang khi thieu level. Chung chay MOI 2 GIAY, nen mot lan chan keo
    dai la hang tram lan tra None ma KHONG DE LAI MOT DONG NAO - den luc di truy thi chi con nuoc
    doan.

    Ca that party 29, 14/09 (user: "p29 thay lap party o trac quan"): party start 23:55:36, mai
    00:23:07 moi co dong `TU CHON MAP` - 27 phut, khoang 810 lan tra None trong im lang. Suot do
    `auto_train` rong -> dieu phoi khong biet map train dich -> khong biet thanh tap ket -> ca
    party lap party o Trac Quan (12001) roi teleport lam tan doi, quay vong. Truy nguoc khong ra
    vi khong co du lieu: pet da xac nhan du ca 5 acc tu 23:55:41, khong exception, khong reconnect.

    Chi LOG, khong doi hanh vi.
    """
    if not thieu:
        st.pop("chot_chan_tu", None)
        st.pop("chot_chan_log", None)
        return
    _tu = float(st.get("chot_chan_tu", 0.0) or 0.0)
    if not _tu:
        st["chot_chan_tu"] = _tu = time.time()
    _lau = time.time() - _tu
    if _lau < CHOT_BAI_BI_CHAN_BAO_SEC:
        return
    if time.time() - float(st.get("chot_chan_log", 0.0) or 0.0) < CHOT_BAI_BI_CHAN_BAO_SEC:
        return
    st["chot_chan_log"] = time.time()
    log.warning("[party %d] DIEU PHOI: CHUA CHOT DUOC %s sau %.0fs - dang cho level cua %d acc: %s"
                " (ca party dung cho: khong biet map train dich thi khong biet thanh tap ket)",
                pidx + 1, viec, _lau, len(thieu), ", ".join(sorted(thieu)))


def _party_city_unlocked(pidx, city_id):
    """(danh sach acc CHUA MO thanh nay, danh sach acc CHUA BIET).

    city_unlocked() tra None = CHUA BIET (chua nhan goi co nhiem vu). Phai tach rieng: coi None la
    "chua mo" thi acc vua login se bi ket luan oan, coi la "da mo" thi lai tele mu nhu cu.
    """
    chua_mo, chua_biet = [], []
    for username, *_ in party_accounts(pidx):
        c = account_clients.get(username)
        if c is None:
            continue
        st = c.city_unlocked(city_id)
        if st is None:
            chua_biet.append(username)
        elif st is False:
            chua_mo.append(username)
    return chua_mo, chua_biet


def _party_unlocked_cities(pidx):
    """city_id ma CA PARTY (acc dang chay) deu da mo. Acc chua biet -> BO QUA thanh do cho chac."""
    out = []
    for cid in (getattr(config, "TELEPORT_CITY_IDS", None) or ()):
        chua_mo, chua_biet = _party_city_unlocked(pidx, cid)
        if not chua_mo and not chua_biet:
            out.append(cid)
    return out


def _pick_start_city(pidx, dest_city):
    """Thanh xuat phat cho party: GAN `dest_city` nhat trong so thanh CA PARTY deu mo.

    Thay cho viec co dinh gom o NGHIEP THANH - cach cu chet khi chinh Nghiep Thanh chua mo, va
    cung khong he gan (Nghiep Thanh -> Kien Nghiep 5 cong, trong khi Hoi Ke chi 2).
    """
    mo = _party_unlocked_cities(pidx)
    if not mo:
        return None
    # Dung ROUTER co san (nearest_city) chu KHONG tu tinh khoang cach: no con biet cong nao di bo
    # qua duoc (image [0,0,0] = warp event, khong di duoc). Tu dem cong se chon phai thanh ma
    # router KHONG dinh tuyen noi -> ca party ket o buoc keo.
    c = next((account_clients[u] for u, *_ in party_accounts(pidx)
              if account_clients.get(u) is not None), None)
    if c is None:
        return None
    got = c.nearest_smart_city(dest_city, allowed=mo)
    if not got:
        log.warning(">>> PARTY %s: khong thanh nao CA PARTY da mo ma di toi %s duoc (da mo: %s)",
                    pidx + 1, dest_city, sorted(mo))
        return None
    cid = int(got["city"])
    ten = (getattr(config, "TELEPORT_CITIES", None) or {}).get(cid, {}).get("name", cid)
    log.info(">>> PARTY %s: thanh xuat phat = %s (id %s, %d cong toi %s; ca party deu da mo)",
             pidx + 1, ten, cid, len(got.get("route", {}).get("legs", ())), dest_city)
    return cid


def _ai_lech_instance(pidx, song, grace=30.0):
    """AI dang o KHAC INSTANCE voi phan con lai - do bang BANG CHUNG THAY NHAU, khong bang so kenh.

    So kenh la so NHO va sai duoc (KNOWLEDGE.md muc 7: game KHONG CO lenh hoi "toi dang o kenh
    nao"). Con `0x03 PlayerAppear` thi chi server moi gui, va chi gui cho nguoi CUNG SCENE + CUNG
    INSTANCE - nen "co thay nhau khong" la cau tra loi CHAC CHAN.
    User 13/09: "biet duoc nhung nguoi xung quanh minh thi biet duoc co cung kenh hay ko".

    HOI MOI ACC, khong chi leader: `_party_khong_thay_nhau` cu chi nhin tu mat leader, nen khi
    CHINH LEADER la dua lech thi khong ai phat hien (user: "thuc ra cai party 1 la leader deo phai
    o kenh 6, no sai chu ko phai member sai").

    Cach lam: trong so acc DANG CUNG MAP, noi hai acc lai neu MOT trong hai thay dua kia -> duoc
    cac NHOM cung instance. Nhom dong nhat la instance dung; ai ngoai nhom do la lech, KE CA
    LEADER. Hoa nhau (2-2) thi khong ket luan - tra rong.

    `grace`: vua toi map thi chua kip nhan `0x03` cua nhau, doi mot lat roi hay ket luan.
    """
    _ds = [(u, c) for u, c in song if getattr(c, "current_map", None)]
    if len(_ds) < 3:
        return []                      # 2 nguoi thi khong co "da so" de dua vao
    _dem_map = {}
    for _u, c in _ds:
        _dem_map.setdefault(int(c.current_map), []).append((_u, c))
    _tren = max(_dem_map.values(), key=len)
    if len(_tren) < 3:
        return []                      # dang lech map -> nhanh khac lo, khong ket luan o day
    _luc = {}
    for _u, c in _tren:
        _t = getattr(c, "_thay_nhau_tu", None)
        if _t is None:
            _t = c._thay_nhau_tu = {}
        _luc[_u] = _t

    def _cung_party(a, b):
        """`a` va `b` co dang O CUNG MOT DOI khong - bang chung CHAC HON ca `0x03`.

        Server KHONG cho lap party xuyen instance: loi moi khong toi noi, accept khong an. Nen hai
        acc co ten trong roster cua nhau la CHAC CHAN cung instance, khong can doi goi `0x03`.

        Ca that party 3, 14/09 (user: "p3 van dung o tuong duong deo chiu di") - vong lap tu nuoi:
            17:18:25 [minh] PARTY: 94d0d7f8 vao doi (leader=4ef7d7f8) -> roster 4 nguoi   <- DU
            17:18:33 [party 3] gen 13: viec=dong_bo - cung map nhung ['minhminhmq'] KHONG THAY
                                       duoc dong doi (khac instance du cung so kenh)
            17:18:31 [minh] PARTY: 94d0d7f8 ROI doi (S:013-004) -> roster con 3
            17:18:31 [minh] PARTY: DOI TRUONG 4ef7d7f8 roi -> doi giai tan
        `minh` VUA vao party voi leader (nen chac chan cung instance) nhung chua kip nhan `0x03`
        cua ai -> bi ket luan lech -> lenh `dong_bo` -> dong bo kenh BAT BUOC roi doi -> party tan
        -> thieu nguoi -> moi lai -> du -> lai ket luan lech. Quay vong, khong bao gio di train.
        """
        try:
            _ea = getattr(a[1], "self_entity", None)
            _eb = getattr(b[1], "self_entity", None)
            if not _ea or not _eb:
                return False
            _ra = {bytes(x) for x in (getattr(a[1], "party_members", None) or ())}
            _rb = {bytes(x) for x in (getattr(b[1], "party_members", None) or ())}
            return bytes(_eb) in _ra or bytes(_ea) in _rb
        except Exception:
            return False

    def _thay(a, b):
        """acc `a` co dang THAY `b` khong (rong = thay)."""
        if _cung_party(a, b):
            return True                # cung doi -> chac chan cung instance
        _ent = getattr(b[1], "self_entity", None)
        if not _ent:
            return True                # chua biet entity -> khong ket luan xau
        try:
            return not a[1].da_thay_tan_mat(_ent)
        except Exception:
            return True

    # Nhom cac acc THAY NHAU (hai chieu deu tinh: mot ben thay la du de ket luan cung instance).
    _nhom = {u: u for u, _c in _tren}

    def _goc(u):
        while _nhom[u] != u:
            _nhom[u] = _nhom[_nhom[u]]
            u = _nhom[u]
        return u

    for i, a in enumerate(_tren):
        for b in _tren[i + 1:]:
            if _thay(a, b) or _thay(b, a):
                _nhom[_goc(a[0])] = _goc(b[0])
    _cum = {}
    for u, _c in _tren:
        _cum.setdefault(_goc(u), []).append(u)
    _to_nhat = max(_cum.values(), key=len)
    if len(_to_nhat) * 2 <= len(_tren):
        return []                      # khong co da so ro rang -> khong ket luan (L13)
    _ngoai = sorted(u for u, _c in _tren if u not in _to_nhat)
    if not _ngoai:
        return []
    # GRACE: chi ket luan khi tinh trang nay KEO DAI - vua toi map thi chua kip nhan 0x03.
    _bay = time.time()
    _ra = []
    for u in _ngoai:
        _t0 = _luc[u].setdefault("tu", _bay)
        if _bay - _t0 >= grace:
            _ra.append(u)
    for u, _c in _tren:
        if u not in _ngoai:
            _luc[u].pop("tu", None)
    return _ra


def _thieu_acc_song(pidx, song):
    """Party CHUA du acc login xong chua? (acc da TAT han thi khong tinh - no khong bao gio ve).

    Phep dem map/kenh cua dieu phoi chi nhin acc DANG SONG, nen khi moi 2/5 dua login xong thi
    "cung map/kenh" la ket luan tren mot mau khong day du - dua chua login co the o kenh khac han.
    Chua biet != khong sao (L13).
    """
    try:
        _cau_hinh = party_accounts(pidx)
    except Exception:
        return False
    if not _cau_hinh:
        return False
    # Acc da tat han (user Stop / khong con thread) thi KHONG cho: cho no la cho vinh vien.
    _con_kha_nang = [u for u, _p, _l, _k in _cau_hinh if is_account_running(u)]
    return len(song) < len(_con_kha_nang)


def _co_ai_dang_o_map(pidx, map_id, tru=None):
    """Party co ai DANG DUNG o `map_id` khong (bo qua chinh `tru`). Doc thang client, khong ai bao.

    Dung de phan biet "MINH bi van ra khoi bai" voi "CA PARTY dang di duong toi bai":
      - con nguoi o bai ma minh khong o do -> minh vang that,
      - khong ai o bai ca -> ca lu dang tren duong, chuyen binh thuong.
    """
    try:
        _m = int(map_id or 0)
    except (TypeError, ValueError):
        return False
    if not _m:
        return False
    for _u, _p, _l, _k in party_accounts(pidx):
        if tru is not None and _u == tru:
            continue
        _c = account_clients.get(_u)
        if _c is None or not getattr(_c, "running", False):
            continue
        if int(getattr(_c, "current_map", 0) or 0) == _m:
            return True
    return False


def _map_train_dich(pidx, st):
    """MAP TRAIN DICH cua party, `None` = that su chua ai biet.

    So bai train NAM O HAI CHO, va bac chan "chi lap party o diem tap ket" truoc day bam dung cai
    duoc dien MUON NHAT:
      - `auto_train`      - DIEU PHOI chot bai (`_engine_chot_map`), co ngay tu dau
      - `train_map_dich`  - luong leader ghi, chi khi DA warp vao bai xong

    Khong phai "chua toi bai thi khong biet dich": co so map train la `_pick_start_city` tinh ra
    thanh tap ket ngay (router thuan du lieu, khong can ai di dau ca). Loi la TRA SAI O - dich da
    chot tu lau ma phep chan lai hoi cai o con rong.

    Ca that party 15, 13/09 (user: "p15, o trac quan lap pt lam lon gi the" -> "biet duoc bai train
    la biet duoc duong di den bai la luc do biet thanh tap ket roi, deo phai luc den map train moi
    biet thanh tap ket"):
        14:23:43 >>> PARTY 15: TU CHON MAP -> Dam Lay Tang Khau1 (map 21841)   <- da chot tu day
        22:57:15 [party 15] gen 4: viec=moi - cung map/kenh nhung DOI chua du (tat ca = 0)
        22:59:26 [party 15] DIEU PHOI: ca party da chung kenh 2 nhung DOI chua du -> LAP LAI PARTY
        23:01:27 ... 23:03:28 ... 23:05:29   (lap lai mai, roster khong bao gio len)
    Ca party o 12001 (Cua thanh Trac Quan) - thanh DI NGANG QUA. `_o_thanh_di_qua` tra False vi
    `train_map_dich` rong, nen bac chan khong he bat len, du bai train biet tu 8 tieng truoc.

    Thu tu doc: `train_map_dich` (leader da toi - chac chan nhat) -> `auto_train` (dieu phoi chot)
    -> `start_city_id` (user chi dinh map tay, khong `train_pick`).
    """
    _d = st.get("train_map_dich")
    if _d:
        try:
            return int(_d)
        except (TypeError, ValueError):
            pass
    _auto = st.get("auto_train")
    if _auto:
        try:
            return int(_auto[0])
        except (TypeError, ValueError, IndexError):
            pass
    pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {}) or {}
    _mode = pcfg.get("mode")
    if pcfg.get("train_pick"):
        return None                  # cho dieu phoi chot, khong doan theo config
    if _mode == "digioi_train" and st.get("dt_phase", "digioi") != "train":
        return None                  # con dang pha DG, chua co chuyen di train
    if _mode not in ("train", "digioi_train"):
        return None
    try:
        _sc = int(pcfg.get("start_city_id", getattr(config, "START_CITY_ID", 0)) or 0)
    except (TypeError, ValueError):
        return None
    return _sc or None


def _thanh_tap_ket_dich(pidx, st):
    """THANH TAP KET DICH cua party = thanh xuat phat gan map train nhat ma CA PARTY deu da mo.

    `None` = chua biet (chua co map train dich, hoac khong thanh nao ca party mo di toi duoc) ->
    nguoi goi KHONG duoc suy ra dieu gi, cu de viec chay binh thuong.

    Cache theo map train: `_pick_start_city` goi router (`nearest_smart_city`), ma vong dieu phoi
    chay moi 2 giay cho MOI party.
    """
    _train = _map_train_dich(pidx, st)
    if not _train:
        return None
    # DIEM GOM MA ENGINE DANG KEO PARTY VE thang tuyet doi - mot party mot ket luan (L1).
    #
    # `_pick_start_city` ben duoi tra loi cau hoi KHAC: "thanh gan bai nhat ma CA PARTY DEU DA MO".
    # Hai cau tra loi lech nhau la binh thuong khi thanh gan bai CHUA MO het: luc do engine gom o
    # thanh khac roi keo di bo sang (xem `_thanh_dich_engine_moi`). Nhung neu `_o_thanh_di_qua` van
    # hoi `_pick_start_city` thi hai ben danh nhau - mot ben keo party ve A, ben kia bao "A chi la
    # thanh di ngang" va CAM lap party o A.
    #
    # Ca that 17/09 party 44+45 (user: "p44 p45 thay van dung o Tho xuan" -> "hay day la truong hop
    # di mo thanh, mo thanh xong no ko chuyen sang train"):
    #   19:06:09 ENGINE: thanh 15021 CHUA MO voi [cd702..cd705] -> gom o 18021 roi KEO DI BO
    #   19:06:23 [chdumot] ENGINE: thanh 15021 chua mo -> KEO party DI BO toi do truoc
    #   (keo toi noi THANH CONG, ca party da o 15021)
    #   19:28:49 REFORM gen -> 6 - dang o thanh DI NGANG QUA 15021, chua toi thanh tap ket 18021
    # Tuc di mo thanh xong roi ma van bi coi la "chua toi noi" -> khong bao gio chuyen sang train.
    _dg = st.get("diem_gom_hien_tai")
    if _dg:
        try:
            return int(_dg)
        except (TypeError, ValueError):
            pass
    _cu = st.get("thanh_tap_ket_cache")
    if _cu and _cu[0] == _train:
        return _cu[1]
    try:
        _tp = _pick_start_city(pidx, _train)
    except Exception as e:
        log.debug("[party %d] chot thanh tap ket loi: %s", pidx + 1, e)
        _tp = None
    # KHONG CACHE "CHUA BIET". `_pick_start_city` tra None khi chua thanh nao CA PARTY mo di toi
    # duoc - ma `city_unlocked` tra None ("chua biet") suot luc acc vua login chua nhan co nhiem
    # vu (`mark_flags`), va `_party_unlocked_cities` BO QUA thanh nao con acc chua biet. Tuc None
    # o day phan lon la TRANG THAI TAM THOI luc party dang len.
    #
    # Cache lai thi no dong bang CA BUOI: `_thanh_tap_ket_dich` rong -> `_o_thanh_di_qua` tat theo
    # ("chua biet dich -> khong ket luan") -> party lap doi ngay tai thanh dang dung, roi leader di
    # duong, `follow_smart_route` tu chon thanh khac -> teleport -> ROI DOI -> tan -> gom lai.
    #
    # Ca that 17/09 party 44 (`reform g=101`) va party 45 (user: "p45 van moi dua 1 thanh"):
    #   08:49:26 [party 45] gen 14: du doi, cung map/kenh -> DI TRAIN map 15457 (con o [18021])
    #   08:49:26 [chdumot] Teleport -> city 12061      <- leader di, party 4/4 tan ngay
    #   08:49:27 [party 45] gen 15: viec=gom - party dang o 2 MAP khac nhau [12061, 18021]
    if _tp:
        st["thanh_tap_ket_cache"] = (_train, _tp)
    return _tp


def _o_thanh_di_qua(pidx, st, noi):
    """`noi` co phai THANH DI NGANG QUA (khong phai diem tap ket) khong?

    Lap party o thanh trung gian la vo ich: buoc ngay sau la TELEPORT di thanh tap ket, ma
    teleport bat buoc `leave_party()` -> party vua lap lai tan.

    Ca that party 4, 13/09 (user: "p4, bon no lap pt o Trac quan lam lon gi the"):
        13:32:44 [party 4] dong_bo - cung map nhung LECH KENH [1,4,10,11]   (dang o 12001)
        13:32:47 [party 4] moi -> CHOT kenh dich = 13
        13:36:01 [party 4] dong_bo - cung map nhung LECH KENH [1,7,10,11]   (van 12001)
        13:36:16 [party 4] LAP LAI PARTY (brubb46677=0 sga008=0 ... sga012=0)
    Roster dung im o 0 suot. Trac Quan la thanh ma `pre_route_town_hop` nem acc qua (random 50-50
    Trac Quan / Nghiep Thanh) tren duong ve thanh xuat phat - CHO DI NGANG, khong phai cho tu.

    KHONG duoc coi Trac Quan / Nghiep Thanh la "trung gian" theo ID: chinh chung co the LA thanh
    tap ket cua party khac (user dan do 13/09). So voi DICH THAT, khong so voi danh sach cung.

    CAU HOI THAT LA "cho nay co duoc phep lap party khong", va cho duoc phep chi co HAI: thanh
    TAP KET, hoac chinh MAP TRAIN. Moi cho khac - thanh di ngang qua HAY map thuong/bai train
    khac - deu phai gom ve thanh tap ket truoc.

    TRUOC 21/09 cho nay doi `noi` PHAI LA THANH TELEPORT moi chan; dang o map thuong thi tra
    False = "lap party duoc". Ca that party 21 (user: "login vao thi ca party dang o trai pham
    thanh 3, bai train la dam lay tang khau 4 -> sao no ko tele ve thanh gan nhat roi di ma no
    lap party tu trai pham thanh 3 roi keo den bai train"):
        login tai 21814 (Trai Pham Thanh, is_teleport_city=False), bai train 21844
    -> lap party ngay tai 21814 roi keo di. Ma tu 21814 sang 21844 bat buoc TELEPORT, teleport
    thi phai `leave_party()` -> party vua lap lai tan, va `ve_map` giao lai 160 lan lien tiep.
    User chot flow: "login vao ma ko phai map train hay thanh gan bai train nhat thi tele thanh
    trung gian (Trac Quan/Ng thanh) roi tele thanh tap trung de keo di" - dung duong
    `pre_route_town_hop` + `go_to_town` ma flow cu da co.

    True chi khi CHAC CHAN: da biet dich, va `noi` khac ca dich lan map train. Chua biet dich thi
    tra False (L13: chua biet != khong sao) - tha lap party thua con hon khong bao gio lap.
    """
    try:
        if not noi:
            return False
        # INSTANCE (pho ban 62xxx, Di Gioi, thap 2K) KHONG tinh la "sai cho": acc dang o trong do
        # la dang LAM VIEC, va tu do khong teleport ra duoc. Ra lenh gom luc nay la keo acc ra
        # khoi pho ban giua chung.
        if in_instance_map(int(noi)) or int(noi) == int(getattr(config, "DIGIOI_MAP_ID", 0) or 0):
            return False
        if in_floor_crawl_map(int(noi)):
            return False
    except Exception:
        return False
    _dich = _thanh_tap_ket_dich(pidx, st)
    if not _dich:
        return False                # chua biet dich -> khong ket luan (L13)
    _train = _map_train_dich(pidx, st)
    if _train and int(noi) == int(_train):
        return False                # dang o chinh map train -> lap party ngay tai bai la dung
    return int(noi) != int(_dich)


def _nhip_cho_kenh(st):
    """Picker bao "toi VAN DANG tim kenh" - member cho theo nhip nay, khong theo dong ho tuyet doi.

    Truoc day member cat cung sau `CHO_KENH_CAP` giay (them 31/08 de chua party 14 treo 11 phut).
    Cai do lam hong dung truong hop server DONG: leader van dang kien tri quet kenh thi member da
    bo cho -> moi dua nam nguyen kenh login.
    Log 01/09 party 4 (sga011-015, server trieu_van 89 kenh, dang o Di Gioi):
        11:25:19 [thmo] KHONG kenh nao du 5 cho trong cho ca party -> RETRY  (lap toi 11:32+)
        11:26:45 [thnam] (member) cho channel_ready qua 90s -> THOI CHO
    -> leader kenh 33, con lai 2/20/71/2 (user: "party 4 bi sao ma moi dua 1 kenh").
    Con han van CAN: picker CHET han (thread ket/rot) thi nhip dung lai va member moi thoat.
    """
    st["kenh_nhip"] = time.time()


def _ve_thanh_tap_trung(c, pidx, label, dest_city, dest_flag):
    """Mode CITY: ve thanh tap trung; thanh CHUA MO tele -> ra lenh DI MAP (party keo nhau di bo).

    Truoc day mode city chi goi `go_to_town(sc, flag)` tron: thanh chua mo thi `go_to_town` bo cuoc
    NGAY ("thanh %s CHUA MO tele -> bo qua ngay") va acc DUNG IM tai cho login. Log 01/09 party 48
    (dt901-905) + party 49 (gclm*): ra khoi Di Gioi ve map 12003 (quang truong Trac Quan) roi nam
    do ca tieng (user: "party 48 49 no ko ve thanh, no dung yen o quang truong, t chon Ng thanh ma").

    KHONG tu di bo LE tung acc. Ban dau lam the va no HONG dung nhu mode train da biet tu lau: cong
    co hoi thoai (cau Gioi kieu, map 63000 cong 10) chi MOT nguoi tra loi duoc, 5 acc di le thi moi
    acc tu bam mot ma -> ket ca lu o cau (log 11:31-11:35, user: "leader chon thoi, lien quan me gi
    den 5 acc" / "m dang cho di le a").
    Dung LAI dung co che da co va da chay tot: lenh "DI MAP AAA -> BBB" (`_do_manual_route`) - no
    gom ca party ve thanh xuat phat, lap party TAM (ke ca party khong co chu PT thi picker dong vai
    leader), LEADER KEO qua tung cong con member follow, den noi thi giai tan. Y het cach mode train
    xu ly "thanh gan bai chua mo" (`_reform_via_nghiep`: gom o thanh da mo roi leader keo di bo).
    """
    dest_city = int(dest_city)

    def _toi_noi():
        # Da o thanh dich -> xoa dau lenh cu de lan sau (bi day ra khoi thanh) con ra lenh lai duoc.
        st = _pstate(pidx)
        with st["lock"]:
            if st.get("route_ve_thanh_dest") == dest_city:
                st["route_ve_thanh_dest"] = None
        return True

    try:
        if c.go_to_town(dest_city, int(dest_flag)):
            return _toi_noi()
    except Exception as e:
        log.warning("[%s] loi ve thanh %s: %s", label, dest_city, e)
    if c.current_map == dest_city:
        return _toi_noi()
    if c.city_unlocked(dest_city) is not False:
        return False        # that bai vi ly do khac (battle chan tele...) - go_to_town da lap du
    _ra_lenh_di_bo_ve_thanh(pidx, dest_city, label)
    return False


def _ra_lenh_di_bo_ve_thanh(pidx, dest_city, label):
    """Dat lenh DI MAP <thanh ca party da mo> -> <thanh user chon> cho CA PARTY.

    Dat MOT LAN cho moi dich (khong phai moi acc, khong phai moi vong): lenh la cua ca party, moi
    acc deu chay nhanh route cua no; acc nao cung dat thi cmd_gen nhay lien tuc -> route bi khoi
    dong lai giua chung mai mai.
    """
    st = _pstate(pidx)
    with st["lock"]:
        if st.get("route_ve_thanh_dest") == int(dest_city):
            return False
        st["route_ve_thanh_dest"] = int(dest_city)
    xuat_phat = _pick_start_city(pidx, dest_city)
    if not xuat_phat:
        log.warning("[%s] thanh %s CHUA MO tele va KHONG thanh nao ca party da mo di toi do duoc "
                    "-> dung tai cho", label, dest_city)
        return False
    _ten = (getattr(config, "TELEPORT_CITIES", None) or {}).get(xuat_phat, {}).get("name", xuat_phat)
    log.warning("[%s] thanh %s CHUA MO tele -> ra lenh DI MAP %s (%s) -> %s: ca party lap doi va "
                "KEO nhau di bo (khong di le)", label, dest_city, xuat_phat, _ten, dest_city)
    party_route_maps(pidx, xuat_phat, dest_city)
    return True


def _thanh_dong_acc_nhat(pidx):
    """THANH ma nhieu acc cua party dang dung nhat (doc thang `account_clients`, khong ai bao cao).

    Dung lam diem gom khi khong co route: it phai di chuyen nhat, va thuong da so party da tu ve
    day roi - chi con vai dua lac. Hoa thi lay so nho de moi acc tinh ra CUNG mot thanh.

    Tra None khi khong acc nao dang o thanh teleport duoc (dang o bai train / phy ban / DG).
    """
    _la_thanh = getattr(config, "is_teleport_city", None)
    if not callable(_la_thanh):
        return None
    dem = {}
    for _u, _p, _l, _k in party_accounts(pidx):
        _c = account_clients.get(_u)
        if _c is None or not getattr(_c, "running", False):
            continue
        m = int(getattr(_c, "current_map", 0) or 0)
        try:
            if m and _la_thanh(m):
                dem[m] = dem.get(m, 0) + 1
        except Exception:
            continue
    if not dem:
        return None
    return sorted(dem.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _gather_city(pidx, dest_city, gen):
    """Diem GOM cua party khi khong ve thang `dest_city` duoc: thanh GAN NHAT ma CA PARTY da mo.

    Truoc day co dinh NGHIEP THANH (12061). Hai loi user chi ra (25/08):
      1. Chinh Nghiep Thanh cung co the CHUA MO -> ke hoach chet han.
      2. Khong he "gan": Nghiep Thanh -> Kien Nghiep mat 5 cong, tu Hoi Ke chi 2.

    Chot 1 LAN moi reform gen roi giu: moi acc tu tinh se ra thanh khac nhau (danh sach thanh da mo
    doi theo acc nao dang chay), ca party se toe ra.
    Fallback 12061 chi dung khi CHUA BIET gi (chua nhan co) - giu hanh vi cu, khong lam te hon.
    """
    st = _pstate(pidx)
    with st["lock"]:
        cur = st.get("gather_city")
        if cur and st.get("gather_city_gen") == gen:
            return cur
    cid = _pick_start_city(pidx, dest_city) or 12061
    with st["lock"]:
        st["gather_city"] = cid
        st["gather_city_gen"] = gen
    return cid


def _auto_dg_level(pidx, pick_mode):
    """idx cap quai Di Gioi (1..15) suy tu level party. None neu chua biet level acc nao.

    Chot 1 LAN/phien giong _auto_train_target: ca party phai cung MOT cap quai. Co
    DIEU PHOI goi ham nay moi 2 giay; acc CHI DOC ket qua (`_doc_cap_dg`).
    """
    st = _pstate(pidx)
    with st["lock"]:
        cur = st.get("auto_dg_level")
        if cur:
            return cur
    # CHUA DU LEVEL CA PARTY -> KHONG CHOT. Dieu phoi goi lai moi 2s nen se chot ngay khi du.
    # (Truoc 05/09 khong co chot nay: `account_last` chi nam trong RAM, reset moi lan start bot,
    #  nen lan chay dau tien acc nao login xong TRUOC la chot cho ca party bang MINH NO. Bang
    #  chung: `PARTY 1: TU CHON CAP QUAI DG -> cap 150 (level party [167, 197])` - party 5 acc
    #  ma chi co 2 so. Chot 1 lan/phien nen sai la sai den luc restart bot.)
    _thieu = _acc_thieu_level(pidx)
    _bao_chan_chot(pidx, st, "CAP QUAI DG", _thieu)
    if _thieu:
        return None
    with st["lock"]:
        cur = st.get("auto_dg_level")   # dieu phoi/acc khac da chot xong trong luc minh cho
        if cur:
            return cur
        levels = _party_levels(pidx)
        if not levels:
            log.warning(">>> PARTY %s: TU CHON CAP QUAI DG nhung chua biet level acc nao -> dung "
                        "cap da luu", pidx + 1)
            return None
        tier = train_pick.desired_dg_level(pick_mode, levels)
        if not tier:
            return None
        idx = train_pick.DG_LEVELS.index(tier) + 1
        log.info(">>> PARTY %s: TU CHON CAP QUAI DG -> cap %d (muon %d, level party %s)",
                 pidx + 1, tier, train_pick.desired_level(pick_mode, levels), sorted(levels))
        st["auto_dg_level"] = idx
        return idx


CHO_DIEU_PHOI_CHOT_BAI_SEC = 60.0   # acc cho dieu phoi chot bai train (no chay moi 2 giay)


def _doc_cap_dg(pidx):
    """idx cap quai Di Gioi DIEU PHOI da chot, None = chua chot.

    CHI DOC - giong `_doc_bai_train`. Acc khong duoc tu chot: do la quyet dinh cap party (mot cap
    quai cho ca doi), va `_engine_chot_map` lam viec do moi 2 giay.

    Truoc day acc TU goi `_auto_dg_level(pidx, pick, username, _stopped)`, ma ban co username thi
    ham do roi vao `_cho_du_level_party` - VONG CHO VO HAN, khong doc lenh dieu phoi, khong log gi
    ngoai mot dong moi 30 giay. Acc nam trong do thi DIEC: dieu phoi ra lenh gom deu deu, no khong
    nghe thay.
    """
    try:
        return _pstate(pidx).get("auto_dg_level")
    except Exception:
        return None


def _doc_bai_train(pidx):
    """(map_id, mob_index) DIEU PHOI da chot cho party, None = chua chot.

    CHI DOC. Acc khong duoc tu chot bai: chot bai la quyet dinh cap party (mot map cho ca doi),
    va `_engine_chot_map` da lam viec do moi 2 giay.
    """
    try:
        return _pstate(pidx).get("auto_train")
    except Exception:
        return None


def _auto_train_target(pidx, pcfg):
    """(map_id, mob_index) cho party dat 'Tu chon map'. QUYET 1 LAN roi giu trong party state.

    Giu lai vi 2 le: (1) moi acc goi rieng, khong chot thi moi dua ra 1 map khac nhau; (2) co yeu to
    ngau nhien khi nhieu diem cung hop -> goi lai la ra diem khac, ca party lech nhau.
    DIEU PHOI goi ham nay moi 2 giay; acc CHI DOC ket qua (`_doc_bai_train`).
    """
    st = _pstate(pidx)
    with st["lock"]:
        cur = st.get("auto_train")
        if cur:
            return cur
    # CHUA DU LEVEL CA PARTY -> KHONG CHOT (xem _auto_dg_level).
    _thieu = _acc_thieu_level(pidx)
    _bao_chan_chot(pidx, st, "MAP TRAIN", _thieu)
    if _thieu:
        return None
    with st["lock"]:
        cur = st.get("auto_train")      # dieu phoi/acc khac da chot xong trong luc minh cho
        if cur:
            return cur
        levels = _party_levels(pidx)
        if not levels:
            log.warning(">>> PARTY %s: TU CHON MAP nhung chua biet level acc nao -> bo qua lan nay",
                        pidx + 1)
            return None
        maps = [(mid, m.get("name") or str(mid), m.get("mobs") or [])
                for mid, m in getattr(config, "TRAIN_MAPS", {}).items()]
        got = train_pick.pick_train_spot(
            pcfg.get("train_pick"), levels, maps,
            mob_min=int(pcfg.get("mob_min") or train_pick.DEFAULT_MOB_MIN),
            mob_max=int(pcfg.get("mob_max") or train_pick.DEFAULT_MOB_MAX),
            elements=pcfg.get("mob_elements") or train_pick.ALL_ELEMENTS)
        if not got:
            log.warning(">>> PARTY %s: TU CHON MAP khong tim duoc diem nao (level party %s)",
                        pidx + 1, sorted(levels))
            return None
        map_id, idx, used_level, why = got
        name = (getattr(config, "TRAIN_MAPS", {}).get(map_id) or {}).get("name", map_id)
        # In CA "muon" lan "level party" - giong dong tu chon cap quai DG. Thieu 2 so nay thi khi
        # user hoi "sao lai chon map nay" la KHONG TRA LOI DUOC tu log: khong biet bot ha level
        # xuong (do khong map nao khop bo loc) hay tai level party khac voi user tuong.
        _muon = train_pick.desired_level(pcfg.get("train_pick"), levels)
        log.info(">>> PARTY %s: TU CHON MAP -> %s (map %s) diem %s | level quai %d "
                 "(muon %s, level party %s) | %s",
                 pidx + 1, name, map_id,
                 ("CHUA QUET (se quet roi lay bai bat ky)" if idx < 0 else idx + 1),
                 used_level, _muon, sorted(levels), why)
        st["auto_train"] = (map_id, idx)
        return st["auto_train"]


# Hai lenh reform phai cach nhau it nhat bay nhieu giay. Do theo viec THUC TE mot lenh can bao lau
# de co tien trien: leader tele ve thanh roi tele ra bai mat ~10-20s (party 19, 08:04:19 -> 08:04:27),
# member di duong con lau hon. 30s = du de thay lenh truoc co an thua khong, ma van du nhanh de cuu
# party hong that (watcher deadlock chay moi 150s nen khong dinh nguong nay).
REFORM_BUMP_CACH_TOI_THIEU_SEC = 30.0


def _reform_cho_xu(st, moc):
    """Co lenh reform MOI (so voi `moc`) va CHUA BI RUT khong?

    Dung cho moi cho lay `reform_gen` de TU CHOI LAM VIEC ("dang co reform pending -> thoi khong
    lam"). Lenh da duoc DIEU PHOI RUT (L16 - `reform_gen_thoa`) thi khong con la ly do de tu choi.

    Ca that party 4, 14/09 (user: "lap pt xong deo di train"):
        16:34:46 [party 4] RUT lenh reform gen 1 - da du doi (...), cung map [21001] kenh [2]
        16:34:46 [party 4] gen 15: viec=di_train - du doi, cung map/kenh -> DI TRAIN map 21833
        16:38:51 [thmo] (LEADER) lenh 'di_train' -> SET QS + ra train
        16:38:51 [thmo] (LEADER) reform pending (acc bi dump dungeon) -> BO QUA keo ra spot
        16:38:56.. pos=(770, 610) map=21001 combat=False    <- dung im
    Leader nhan dung lenh, roi tu bo vi thay "reform pending" - trong khi lenh do da bi rut tu 4
    phut truoc. L16 sang nay chi sua vong chinh, khong ra cac cho khac doc `reform_gen`.

    KHONG dung cho cac cho ABORT ("dang di duong ma co lenh MOI -> bo dang, quay lai xu"): o do
    cau hoi la "gen co doi khong", khong phai "lenh con hieu luc khong".

    NGOAI LE, va la ngoai le DUY NHAT (22/09): `_ab()` cua `_do_reform` PHAI hoi ca "lenh con hieu
    luc khong". Di tiep cho mot lenh DA BI RUT khong vo hai nhu tuong - rut lenh xong viec thanh
    `lam`, dieu phoi chot `nguoi_keo = leader`, nen bon khong phai nguoi keo dam vao cua chan
    teleport trong `go_to_town` va ban lai moi 2 giay MAI MAI (party 1, 21:35 -> 5/5 acc DUNG
    HINH). Dung lai tai cho la DUNG: lenh chi bi rut khi party DA du doi, cung map, cung kenh.
    """
    try:
        _g = int(st.get("reform_gen", 0) or 0)
        if _g <= int(moc or 0):
            return False
        return int(st.get("reform_gen_thoa", 0) or 0) < _g
    except Exception:
        return False


def _bump_reform(st, reason="", uu_tien=False):
    """Tang reform_gen VA log RO ai bump. CALLER PHAI DANG GIU st["lock"].

    Truoc day co 15 cho tang thang reform_gen va KHONG cho nao noi minh la ai -> moi lan party
    "tu dung doi reform" la phai mo nguoc ca 15 cho (that: hoi 00:50 sau khi PB lv50 xong).
    Lay so dong cua NGUOI GOI bang sys._getframe(1) -> khong phai go tay 15 ly do khac nhau.
    """
    try:
        _ln = sys._getframe(1).f_lineno
    except Exception:
        _ln = 0
    # KHOANG LANG TOI THIEU GIUA HAI LAN BUMP.
    #
    # Moi bump la mot lenh ABORT gui toi MOI acc dang di duong (`_ab()` -> "ABORT di duong
    # reform"). Bump lan hai truoc khi lan mot kip thi hanh = tu huy lenh cua chinh minh, va ca
    # party khong bao gio di xong buoc nao.
    #
    # Ca that party 19, 11/09 - HAI lenh cach nhau BON giay:
    #   08:04:21 gen 19: viec=gom - party o 2 MAP khac nhau [12001, 21001] -> REFORM gen -> 3
    #   08:04:23 [quanmot] (LEADER) Da ve thanh 12001 -> Teleport -> city 21001
    #   08:04:25 gen 20: viec=moi - cung map/kenh nhung DOI chua du   -> REFORM gen -> 4
    #   08:04:25 [vumot]   (member) ABORT di duong reform: reform_gen 3 -> 4 (acc khac bump)
    #   08:04:25 [quantam] (member) ABORT di duong reform: reform_gen 3 -> 4 (acc khac bump)
    # Leader vua tele qua 12001 -> 21001 nen co DUNG MOT NHIP ca party "cung map"; dieu phoi tuong
    # gom xong va ra lenh lap party, trong khi hai member con dang tren duong. Ket qua la leader
    # di tiep mot minh (user: "deu leader 1 noi member 1 noi ... leader thi ngu van di 1 minh").
    #
    # Cac cooldown san co khong phu duoc cho nay: `KE_HOACH_GOM_COOLDOWN` chi chan gom->gom,
    # `LAP_LAI_PARTY_COOLDOWN` chi chan lap->lap. Chuoi gom->lap party thi khong ai chan.
    # `uu_tien` = lenh GOM (party dang o nhieu map - tuc doi da hong THAT). No khong bao gio bi
    # khoang lang chan: khoang lang sinh ra de chan lenh "lap lai party" de len lenh gom dang chay
    # (party 19, 08:04:21 -> 08:04:25), chu khong phai de chan chinh lenh gom.
    #
    # Ca that party 10, 11/09 - dung cai loi do:
    #   12:35:41 [party 10] REFORM gen -> 6 - chung kenh roi ma doi khong du -> lap lai party
    #   12:35:55 [party 10] gen 15: viec=gom - party dang o 2 MAP khac nhau [21841, 21844]
    #   12:35:55 [party 10] BO QUA bump reform (...gom ve cung map/kenh): lenh truoc moi ra 14s
    #   ... dieu phoi im 3 phut, khong ai gom, leader dung danh mot minh ...
    # Lenh gom bi bo MOT LAN la thoi: `_ghi_ke_hoach` chi bao khi NOI DUNG doi, ma noi dung van la
    # `viec=gom` nen khong co lan thu lai.
    _truoc = float(st.get("reform_bump_luc", 0.0) or 0.0)
    _cach = time.time() - _truoc
    if not uu_tien and _truoc and _cach < REFORM_BUMP_CACH_TOI_THIEU_SEC:
        log.info("[party %s] BO QUA bump reform tai run_party_digioi.py:%d (%s): lenh truoc moi ra "
                 "%.0fs, chua ai kip thi hanh - bump nua la ABORT chinh no",
                 (st.get("pidx", -1) + 1) if st.get("pidx") is not None else "?",
                 _ln, reason or "khong ro ly do", _cach)
        return st.get("reform_gen", 0)
    st["reform_bump_luc"] = time.time()
    st["reform_gen"] = st.get("reform_gen", 0) + 1
    log.info("[party %s] REFORM gen -> %d (bump tai run_party_digioi.py:%d)%s",
             (st.get("pidx", -1) + 1) if st.get("pidx") is not None else "?",
             st["reform_gen"], _ln, (" - " + reason) if reason else "")
    return st["reform_gen"]


def doi_kenh_theo_lenh_tay(c, pidx, ch, cmd_gen_handled, *, label, role="",
                           is_leader=False, has_leader=True, ra_safe=None,
                           con_chay=None, han_giay=300.0):
    """DOI KENH theo LENH TAY cua GUI - CHUNG cho ca hai engine.

    Truoc 21/09 khoi nay nam TRONG `run_account` (engine cu). Engine moi thi nhanh `channel` cua
    `_lenh_tay_engine_moi` chi `return _lam_xong()` voi ly do "dieu phoi lo bang `kenh_dich`" -
    NHUNG `_engine_chot_kenh` nam trong `_dieu_phoi_loop`, ma vong do BO QUA party dung engine
    moi (cua chan so 1). Tuc khong ai lo ca.

    Khong ai thay cho toi khi nguong `PARTY_ENGINE_MOI_TU` ha xuong 1 (21/09) - luc do MOI party
    deu chay engine moi va nut doi kenh chet han. Log party 1, 21/09:
        18:58:20 >>> PARTY 1: lenh DOI KENH -> 2
        18:58:20 [party 1] ENGINE: sga005..tuyetdo -> lenh_tay
        18:58:22 [party 1] ENGINE: sga005..tuyetdo -> train     <- 2 giay sau ve train, khong doi
    User: "party 1, t bam doi kenh ma no deo doi".

    THU TU BAT BUOC (user chot 30/08): *"lead CHAY RA SAFE, GIAI TAN pt va ca lu chuyen kenh yeu
    cau"*. Lam nguoc (giai tan truoc roi ra safe) thi party tan giua bai quai. Member di TRUOC khi
    leader giai tan cung chet: trong party member tu di theo leader nen vi tri THAT cua no la cho
    leader dung -> gui move theo pos cu = `di chuyen QUA XA (ma 14)` (log 30/08 22:15).

    `ra_safe(ly_do) -> bool`: callback ra diem an toan. Engine cu truyen closure
    `_ra_safe_truoc_khi_doi_kenh` cua no. None = coi nhu da o safe.
    `con_chay() -> bool`: False thi dung ngay (Stop / acc tat).
    Tra True neu da doi duoc kenh.
    """
    st = _pstate(pidx)
    ch = int(ch)
    ok = False
    _con = con_chay or (lambda: True)
    _safe = ra_safe or (lambda _ly_do="": True)
    # Lenh MOI -> quen diem safe cua lenh truoc (map/bai train co the da khac).
    with st["lock"]:
        st["safe_doi_kenh"] = None
    # L1 - MOT ACC, MOT LENH DANG BAY. Co nay bao cho duong TU DONG (`_engine_gui_lenh_kenh`)
    # biet acc nay dang co lenh tay doi kenh chay, dung gui lenh doi kenh chong len.
    # Ca that party 7, 21/09: hai duong cung doi kenh cho cung mot acc, khong ai biet ai ->
    # ca party xong luc 19:52:48 ma toi 19:53:15 moi thoi, chay lai nguyen quy trinh 27 giay.
    # (Duong tu dong da co `_dp_gui_kenh_dang_chay` cho chinh no, chi thieu ve nay.)
    c._lenh_tay_kenh_dang_chay = True
    try:
        # GHIM kenh user chon: doi xong ma khong ghim thi pha sync kenh chay tiep va TU CHON "kenh it
        # nguoi nhat" -> keo ca party sang kenh khac, phu dinh lenh tay (log 31/08 09:57 party 16:
        # chon kenh 1 -> 09:58:22 picker tu sang kenh 2).
        with st["lock"]:
            st["kenh_ghim"] = ch or None
        if is_leader:
            st["cmd_leader_xong"].clear()
            with st["lock"]:
                st["cmd_leader_xong_gen"] = None
        elif has_leader:
            log.info("[%s] (member) manual: CHO leader ra safe + giai tan party truoc khi doi kenh %d...",
                     label, ch)
            _t_cho_lead = time.time()
            # CHO-HOP-LE: rang buoc THU TU CUA GAME, khong phai cho bao cao. Co han 90s va thoat ngay
            # khi co lenh tay moi.
            while st.get("cmd_leader_xong_gen") != cmd_gen_handled:
                if not c.running or not _con():
                    break
                if st.get("cmd_gen", 0) != cmd_gen_handled:
                    break
                if time.time() - _t_cho_lead > 90:
                    log.warning("[%s] (member) manual: cho leader qua 90s -> tu xu ly", label)
                    break
                st["cmd_leader_xong"].wait(1.0)
        # KIEN TRI: dang train thi tran noi tiep tran, vai lan thu dau gan nhu chac chan roi vao giua
        # tran. Bo som = lenh cua user bi nuot im (user 27/08: "dang train ma bam doi kenh thi phai
        # ket thuc tran, chay ra diem an toan roi doi kenh chu").
        _han = time.time() + float(han_giay)
        _lan = 0
        # CHO-HOP-LE: day KHONG phai vong cho acc khac - acc TU lam viec cua no (cho het tran -> ra
        # safe -> doi kenh), chi tinh co trong than co dong `cmd_leader_xong_gen` ma leader tu ghi.
        # Loi ra doc lap: `st["cmd_gen"] != cmd_gen_handled` (user bam lenh khac -> bo ngay), `_con()`
        # (Stop), va han `han_giay`.
        while time.time() < _han:
            _lan += 1
            if not c.running or not _con():
                break
            if st.get("cmd_gen", 0) != cmd_gen_handled:
                log.info("[%s] (%s) manual: co lenh moi -> bo lenh doi kenh %d dang thu", label, role, ch)
                break
            # DANH XONG TRAN roi moi di. KHONG bo chay: party VAN CON DU (giai tan la buoc sau).
            c._wait_combat_clear(idle=2.0, cap=120.0)
            if c.in_combat(idle_secs=3.0):
                log.warning("[%s] (%s) manual: VAN dang trong tran -> chua doi kenh %d, thu lai "
                            "(lan %d, con %.0fs)", label, role, ch, _lan, _han - time.time())
                time.sleep(3)
                continue
            if not _safe("lenh doi kenh tay"):
                continue                       # chua toi safe -> KHONG giai tan, KHONG doi
            if c.in_combat(idle_secs=3.0):     # bi keo tran tren duong ra safe
                log.warning("[%s] (%s) manual: dinh tran luc ra safe -> thu lai (lan %d)", label, role, _lan)
                continue
            # DA O SAFE roi moi GIAI TAN, roi moi tha member di doi kenh.
            if is_leader:
                if getattr(c, "party_members", None):
                    log.info("[%s] (LEADER) manual: DA ra safe -> giai tan party roi doi kenh %d", label, ch)
                    try:
                        c.leave_party(); reset_party_joined(pidx)
                    except Exception as e:
                        log.warning("[%s] (LEADER) manual: loi giai tan party: %s", label, e)
                    time.sleep(2.0)   # cho goi 0x0d sub04 ve de MOI acc resync toa do
                with st["lock"]:
                    st["cmd_leader_xong_gen"] = cmd_gen_handled
                st["cmd_leader_xong"].set()
            # DA O DUNG KENH ROI -> KHONG gui lenh doi nua. CAC BUOC KHAC VAN LAM DU (ra safe, giai
            # tan, ve safe lai) - user chot 21/09: "van chay ra safe, flow yeu cau roi, cam bo".
            #
            # Chi bo dung mot thu: cai goi `0x07` thua. Server tra "TRUNG khu dang o" roi bot cho het
            # timeout - ca that party 7, 21/09:
            #   19:52:48 [ttbay] Doi kenh OK -> 2          <- da sang kenh 2 (duong dong bo keo sang)
            #   19:53:04 [ttbay] Doi kenh: server bao TRUNG khu dang o -> dang o kenh 2
            # 16 giay cho mot goi chac chan bi tu choi. User: "ca team da chuyen kenh xong roi no lai
            # co chuyen kenh lan nua".
            _dang_o = int(getattr(c, "current_channel", 0) or 0)
            if _dang_o == ch:
                log.info("[%s] (%s) manual: DA o kenh %d roi -> khong gui lenh doi nua", label, role, ch)
                ok = True
            else:
                try:
                    ok = c.switch_channel(ch, theo_lenh=True)
                    time.sleep(1.5)
                except Exception as e:
                    log.warning("[%s] manual: loi doi kenh: %s", label, e)
            if ok:
                # Doi kenh GIU NGUYEN toa do, nhung o kenh moi cho do co the day quai va party VUA TAN
                # -> dung le giua bai la an dan ngay (user chot 30/08).
                if not _safe("sau khi doi kenh %d" % ch):
                    log.warning("[%s] (%s) manual: doi kenh %d xong nhung CHUA ve duoc safe -> vong gom "
                                "party se xu tiep", label, role, ch)
                break
            _res = getattr(c, "_chan_switch_result", None)
            log.warning("[%s] (%s) manual: doi kenh %d THAT BAI (lan %d, result=%s)",
                        label, role, ch, _lan, _res)
            if _res in (2, 4, -1):
                # 2 = khong co kenh do | 4 = kenh DAY | -1 = server IM LANG. Thu lai cung the.
                log.warning("[%s] (%s) manual: kenh %d %s -> BO lenh tay, de sync kenh chon kenh khac "
                            "cho ca party", label, role, ch,
                            {2: "khong ton tai", 4: "DA DAY"}.get(_res, "server IM LANG"))
                break
            time.sleep(2)
        if ok:
            with st["lock"]:
                st["channel"] = ch
            log.info("[%s] (%s) manual: da doi kenh -> %d", label, role, ch)
        else:
            log.warning("[%s] (%s) manual: doi kenh %d THAT BAI (%d lan thu) -> GIU kenh cu %s, de buoc "
                        "dong bo kenh gom ca party lai", label, role, ch, _lan,
                        getattr(c, "current_channel", None))
        return ok
    finally:
        # HA CO DU THOAT BANG DUONG NAO (return som, ngoai le, Stop): co ket True la duong tu
        # dong khong bao gio dam gui lenh doi kenh cho acc nay nua.
        c._lenh_tay_kenh_dang_chay = False


def _pstate(pidx):
    if pidx not in _party_state:
        _party_state[pidx] = {"pidx": pidx,
                              "channel": None,
                              "channel_ready": threading.Event(),
                              "channel_failed": threading.Event(),
                              "channel_failed_reason": "",
                              "channel_expected_map": None,
                              "channel_sync_gen": 0,
                              "invited": threading.Event(),
                              "lock": threading.Lock(),
                              "n_members": 0,            # tong so member can cho
                              "started_train": 0,        # so acc da qua check map -> vao train (de barrier dungeon)
                              "dungeon_done": 0,         # so acc da danh xong dungeon (barrier)
                              "dailies_done": 0,         # so acc da xong daily login (barrier cho leader)
                              "o5_state": "idle",        # "idle"|"running"|"done" - member PHAI cho != "idle" (xem _handle_o5_team)
                              "o5_broke": False,         # team dungeon VO do co dis giua chung -> CA party relogin thoat instance
                              "o5_need_redo": False,     # team dungeon VO -> reconnect xong lam LAI daily (team dungeon)
                              "team_dungeon_state": {},       # level -> "idle"|"running"|"done"
                              "team_dungeon_broke": {},       # level -> co dis/fail can relogin thoat instance
                              "team_dungeon_tries": {},       # level -> so lan da thu (1 dau + 1 retry)
                              "team_dungeon_skip_all": False, # bo qua PB con lai CUA LUOT NAY (doc 1 lan roi xoa)
                              "team_dungeon_need_redo": False,
                              "leader_ok": threading.Event(),   # leader DUNG map train -> tiep tuc
                              "leader_bad": threading.Event(),  # leader SAI map -> huy ca party
                              "leader_gone": threading.Event(),  # leader da THOAT -> member ngung retry vao party
                              "stop_leader_done": threading.Event(),  # STOP: leader DA ve safe -> member duoc thoat
                              "route_party_ready": threading.Event(),  # ROUTE: party da lap xong o thanh -> sap keo di
                              "route_done": threading.Event(),         # ROUTE: leader da keo xong (toi train map)
                              "route_plan_ready": threading.Event(),   # ROUTE: leader da build smart/legacy plan cho ca party
                              "route_plan": None,                      # {"gen", "city", "flag", "route"|None, "missing"?}
                              "event_exit_now": threading.Event(),  # 2K ket thuc/THUA -> CA DOI di ra khoi thap
                              # 2K: ket qua vong leo thap do LUONG LEADER bao len - "thua"/"xong"
                              # /"dut" (client chet giua chung). CHI la SU THAT, khong phai quyet
                              # dinh: `_engine_chot_2k_xong` moi la noi bat `event_exit_now`.
                              "2k_ket_qua": None,
                              # ENGINE MOI: tien do leo thap {"scene": map, "k": so diem da danh}
                              "2k_tien_do": None,
                              "2k_cong_ket_den": 0.0,   # ket o cong -> nghi toi luc nay moi thu lai
                              "mob_spot": None,      # diem quai leader chon (de _start_training dung lai)
                              "rally_point": None,   # safe GAN diem quai nhat -> CA PARTY ve day (gan leader)
                              "rally_ready": threading.Event(),  # leader da chon diem quai + rally_point
                              "path_done": threading.Event(),    # leader da di xong follow_path toi diem quai (member bi keo theo)
                              "reform_gen": 0,       # +1 moi khi co acc van map (chet) -> CA party reform tai cho
                              "resync_gen": 0,       # +1 khi leader moi 1p khong du party -> CA party giai tan + sync kenh lai + moi lai (event 40NPC)
                              "rally_gen": 0,        # +1 khi leader bao "lap lai party tai cho" -> MOI acc chay ra safe TRUOC khi moi (party 11, 30/08)
                              # NHIP TIM cua picker: time.time() moi vong no THU chon kenh. Member
                              # cho theo cai nay chu KHONG theo dong ho tuyet doi - xem `_nhip_cho_kenh`.
                              "kenh_nhip": 0.0,
                              # thanh dich da ra lenh DI MAP (mode city, thanh chua mo tele) - de
                              # khong acc nao ra lenh lai lien tuc. Xem `_ra_lenh_di_bo_ve_thanh`.
                              "route_ve_thanh_dest": None,
                              "kenh_dich_luc": 0.0,  # luc chot kenh dich (giu KENH_DICH_KIEN_NHAN_SEC)
                              # 2K: tang gom da chot + luc chot (giu TANG_GOM_KIEN_NHAN_SEC, dung
                              # tinh lai moi nhip keo dich tut theo buoc chan member).
                              "tang_gom": None,
                              "tang_gom_luc": 0.0,
                              "lap_party_luc": 0.0,  # lan cuoi ra lenh lap lai party (cooldown)
                              # Kenh USER TU CHON bang lenh tay: picker KHONG duoc tu chon kenh khac
                              # nua. Bo ghim khi user ra lenh kenh khac.
                              # Log 31/08 09:57 (party 16): user chon kenh 1, doi xong,
                              # 09:58:22 picker tu "Kenh it nguoi MA DU CHO ca party (5): kenh 2"
                              # -> ca lu keo nhau ve kenh 2, phu dinh lenh cua user.
                              "kenh_ghim": None,
                              "cmd_leader_xong": threading.Event(),  # lenh tay: LEADER da ra safe + giai tan party -> member moi duoc di
                              # SO LENH ma leader da lam xong buoc tren. Member chot theo so nay,
                              # khong theo Event: co dung chung con SOT tu lenh truoc thi member
                              # doc trung khe leader chua kip xoa -> di som, party rach.
                              "cmd_leader_xong_gen": None,
                              "sync_epoch": 0,       # +1 = EP DONG BO uu tien cao nhat (request_party_resync): moi acc relogin bam leader

                              "go_claim": threading.Event(),  # 40NPC: het gio/thua 2 tran -> CA party di doi thuong + thoat
                              "cmd_gen": 0,          # +1 moi khi GUI ra lenh thu cong (doi kenh/teleport thanh)
                              "cmd": None,           # ("channel", ch) | ("city", city_id, flag) | ("route", a, b)
                              "manual_route_gen": 0,
                              "manual_route_plan": None,
                              "manual_route_plan_ready": threading.Event(),
                              "manual_route_source_results": {},
                              "manual_route_city_arrived": {},
                              "manual_route_source_done": threading.Event(),
                              "manual_route_party_ready": threading.Event(),
                              "manual_route_done": threading.Event(),
                              "reconnecting": set(),  # username dang ROT + login lai (cho reconnect resync)
                              "disc_gen": 0,          # +1 moi khi co acc rot (bao cac nick khac phan ung)
                              "event_battle_active": False,
                              "event_battle_done": threading.Event(),
                              # MODE "digioi_train" (DG roi Train): pha hien tai cua CA PARTY +
                              # danh sach acc DA XONG DG (het gio). Du CA party xong -> chuyen pha
                              # "train" -> moi acc relogin vao mode train.
                              # KE HOACH do luong DIEU PHOI ghi ra (xem muc "DIEU PHOI PARTY").
                              # Luong acc CHI DOC. None = dieu phoi chua chay nhip nao.
                              "ke_hoach": None,
                              # KENH DICH do DIEU PHOI chot. Moi acc tu soi vao day trong
                              # keepalive va tu chuyen - KHONG bat tay, khong bao cao, nen acc
                              # da lam xong van bat duoc lenh moi. Xem _engine_chot_kenh.
                              "kenh_dich": None,
                              # Lan cuoi DIEU PHOI ra lenh gom. Dung de khong ra lenh gom don dap
                              # (moi lenh abort moi acc dang di duong).
                              "dieu_phoi_gom_luc": 0.0,
                              # Party da bat dau train chua - luat watcher "thieu nguoi qua lau"
                              # doc khoa nay. TRUOC 05/09 KHONG AI GHI no (chi doc o dung 1 cho)
                              # nen luat do CHUA TUNG CHAY LAN NAO: 0 lan trong ca ngay log.
                              "training_started": False,
                              "dt_phase": "digioi",
                              "dt_train_prepared": False,
                              "summary_done": False}  # da log dong tong ket "party thoat het" chua
    return _party_state[pidx]


def _clear_stale_manual_route(st):
    """Huy route cua phien party cu, giu cmd_gen tang dan de worker cu khong nhan nham lenh moi."""
    with st["lock"]:
        next_gen = int(st.get("cmd_gen", 0)) + 1
        st["cmd"] = None
        st["cmd_gen"] = next_gen
        st["manual_route_gen"] = next_gen
        st["manual_route_plan"] = None
        st["manual_route_source_results"] = {}
        st["manual_route_city_arrived"] = {}
        st["manual_route_plan_ready"].clear()
        st["manual_route_source_done"].clear()
        st["manual_route_party_ready"].clear()
        st["manual_route_done"].clear()


def _route_mismatch_timed_out(state, leader_map, mismatch, now, timeout=15.0):
    if not mismatch:
        state.clear()
        return False
    if state.get("leader_map") != leader_map or state.get("msg") != mismatch:
        state.update(leader_map=leader_map, msg=mismatch, since=now)
        return False
    return now - state["since"] >= timeout


DT_RECHECK_SEC = 300   # dang cho dong doi -> cu 5' soat lai gio DG / Ho Phu mot lan


def _acc_het_gio_dg(c):
    """Acc nay HET GIO Di Gioi chua - DIEU PHOI TU DOC, khong acc nao khai bao (L2).

    Tra True = het gio · False = con gio · None = CHUA BIET (chua co dong ho server).

    Ban cu dung co `c._dg_da_xong` do CHINH ACC dat khi no tu ket luan "minh xong DG". Ghi co len
    client van la BAO CAO - chi khac cho cat: acc ket luan, dieu phoi tin theo. Acc ket luan sai
    (dang dis, chua login xong, chua nhan dong ho) la ca party dung cho no.

    Ba nguon SU THAT, doc thang tu client:
      1. `S:097-001` ma 2 <時間已滿> -> server noi thang la het gio;
      2. dong ho `S:085-001` id 0x1b (so phut DA DUNG) -> con >= 1 phut la CON GIO;
      3. chua co dong ho (`_last_digioi_ts` = 0, vd vua login lai) -> CHUA BIET, phai cho.

    `S:085-001` do SERVER TU DAY (crack client khong co goi xin - `protocolTable[85]` chi co ba
    nhanh S:085-*), va client ghi "跨日時會更新資料" = qua ngay server gui lai.
    """
    if c is None or not getattr(c, "running", False):
        return None                        # acc chet/dis -> khong ket luan gi
    if getattr(c, "_dg_enter_result", None) == 2:
        return True                        # server: <時間已滿>
    if not float(getattr(c, "_last_digioi_ts", 0.0) or 0.0):
        return None                        # chua nhan dong ho -> CHUA BIET
    try:
        return (DIGIOI_LIMIT - c.digioi_minutes_live()) < 1
    except Exception:
        return None


def _dt_recheck_time_left(username, label):
    """Acc da bao xong DG: CON GIO THAT khong? Con Ho Phu thi dung. Tra True = con gio, vao lai DG.

    Doc so SERVER (RoleCount 0x1b = so phut DA DUNG), khong tin ket luan cu: sang nay da co ca
    "bi tinh het gio nhung thuc ra van con", stop/start la vao lai duoc.
    """
    c = account_clients.get(username)
    if c is None or not c.running:
        return False
    used = getattr(c, "digioi_minutes", None)
    if used is None:
        return False                       # chua co so server -> khong doan
    left = DIGIOI_LIMIT - int(used)
    if left > 0:
        log.warning("[%s] DG+Train: dang cho dong doi nhung SOAT LAI thay CON %d phut DG "
                    "(server: da dung %d/%d) -> vao lai DG danh tiep",
                    label, left, int(used), DIGIOI_LIMIT)
        return True
    # Het gio that -> con Ho Phu thi dung de duoc them gio (config phai bat).
    if not getattr(c, "use_digioi_ho_phu", False):
        return False
    if not c.use_di_gioi_ho_phu():
        return False
    # Ho Phu dung xong: server cap nhat lai 0x55/0x1b -> cho vai giay roi doc lai.
    for _ in range(10):
        time.sleep(1.0)
        used2 = getattr(c, "digioi_minutes", None)
        if used2 is not None and DIGIOI_LIMIT - int(used2) > 0:
            log.warning("[%s] DG+Train: da dung Di Gioi Ho Phu -> con %d phut -> vao lai DG",
                        label, DIGIOI_LIMIT - int(used2))
            return True
    log.info("[%s] DG+Train: da dung Ho Phu nhung server chua cong gio -> cho tiep, soat lai sau",
             label)
    return False


def _party_members_off_place(c, pidx):
    """Member nao KHAC MAP hoac KHAC KENH voi leader -> tra list mo ta; rong = ca party cung cho.

    Doc THANG tu client cua tung acc (cung tien trinh) nen chinh xac, khong phai bao cao cu.
    Khac map = leader KHONG THAY entity -> moi chac chan that bai, phai gom lai truoc.
    """
    def _ch(cli):
        """Kenh THAT (hoi lai server neu cache qua han) - so hai so nho san la sai suot ma
        khong ai biet, xem `GameClient.kenh_that`."""
        try:
            return cli.kenh_that()
        except Exception:
            return None

    out = []
    lead_map = getattr(c, "current_map", None)
    lead_ch = _ch(c)
    for u, _p, is_lead, _k in party_accounts(pidx):
        if is_lead:
            continue
        mc = account_clients.get(u)
        if mc is None or not mc.running:
            continue                       # acc chua len/da rot -> duong reconnect lo, khong tinh
        if is_joined(pidx, getattr(mc, "self_entity", None)):
            continue                       # da vao party roi
        m_map = getattr(mc, "current_map", None)
        m_ch = _ch(mc)
        _ent = getattr(mc, "self_entity", None)
        if m_map is not None and lead_map is not None and m_map != lead_map:
            out.append("%s o map %s (leader %s)" % (u, m_map, lead_map))
        elif m_ch is not None and lead_ch is not None and m_ch != lead_ch:
            out.append("%s o kenh %s (leader %s)" % (u, m_ch, lead_ch))
    return out


def _party_khong_thay_nhau(c, pidx, grace=30.0):
    """Member CUNG map + CUNG kenh (theo hai con so) ma leader CHUA HE thay quanh minh.

    `0x03 PlayerAppear` chi duoc server gui cho nguoi CUNG SCENE + CUNG INSTANCE. Chua he nhan
    duoc = hai con so kia dang noi doi, thuc te khac instance -> loi moi khong the toi noi, va
    server KHONG gui ma loi nao (dung trieu chung da duoi may ngay).

    KHONG ve thanh: cach chua la LEADER CHON KENH MOI roi dong bo lai - nhung ca party phai DA
    RA DIEM AN TOAN truoc, dung o diem quai thi doi kenh xong van hong (user chot 30/08).
    GRACE 30s: vua toi map thi chua kip nhan 0x03 cua nhau la binh thuong.
    """
    out = []
    _mem = getattr(c, "_chua_thay_tu", None)
    if _mem is None:
        _mem = c._chua_thay_tu = {}
    lead_map = getattr(c, "current_map", None)
    for u, _p, is_lead, _k in party_accounts(pidx):
        if is_lead:
            continue
        mc = account_clients.get(u)
        if mc is None or not mc.running:
            continue
        ent = getattr(mc, "self_entity", None)
        if ent is None:
            continue
        if is_joined(pidx, ent):
            _mem.pop(bytes(ent), None)
            continue
        if getattr(mc, "current_map", None) != lead_map:
            continue                       # lech map -> nhanh khac lo, khong ket luan o day
        try:
            vi = c.da_thay_tan_mat(ent)
        except Exception:
            vi = ""
        if not vi:
            _mem.pop(bytes(ent), None)
            continue
        t0 = _mem.setdefault(bytes(ent), time.time())
        if time.time() - t0 >= grace:
            out.append("%s: %s" % (u, vi))
    return out


def _dt_wait_all_digioi_done(pidx, username, label, stopped_fn):
    """MODE digioi_train: acc nay DA XONG DG -> DUNG YEN cho CA PARTY xong DG.
    Du het -> doi pha party sang "train" (moi acc relogin se chay mode train).

    Tra ve:
      True         - ca party xong DG, san sang di train
      "back_to_dg" - soat lai thay CON GIO DG -> quay lai DG danh tiep (giu ket noi)
      "lenh_moi"   - dieu phoi bump `reform_gen` -> thoi cho, di nghe lenh (giu ket noi)
      False        - BI STOP. CHI dung cho stop that: caller khong set `relogin_train` nen
                     `_ket_thuc_pha_dg()` se DONG KET NOI, acc chet han.
    CHO KHONG GIOI HAN (theo yeu cau user): chi thoat khi CA PARTY xong DG hoac bam Stop -> acc xong
    SOM khong bi tat game oan trong luc acc khac con dang DG (DG toi 2h). Acc da tat/rot han khong
    tinh vao (users = acc DANG CHAY) nen 1 acc chet cung khong ket ca party mai mai."""
    st = _pstate(pidx)
    # KHONG dat co "minh da xong DG" nua (L2 - user 09/09: "bot dieu phoi phai lam va kiem tra
    # cac acc, deo phai cac tu lam roi bao cao"). Ghi co len client van la acc TU KET LUAN roi
    # dieu phoi tin theo; acc ket luan sai (dang dis / chua nhan dong ho server) la ca party dung
    # cho no. Gio dieu phoi tu doc `_acc_het_gio_dg()` cua tung client.
    # Xong DG truoc -> DUNG CHO ca party (co the toi 2 TIENG). Danh dau CHO de watcher khong keu
    # "TREO" oan, va de biet day la cho HOP LE chu khong phai lech viec.
    set_account_activity(username, "xong Di Gioi - cho ca party xong", phase="wait")

    def _prepare_train_phase_once():
        prepared = False
        with st["lock"]:
            if not st.get("dt_train_prepared"):
                st["dt_train_prepared"] = True
                # Phase DG da dung cac flag sync/moi party nay. Sang phase train phai reset
                # nhu mot luot train moi, neu khong leader/member co the dung im o thanh vi doc
                # lai state cu cua phase DG.
                for key in ("leader_ok", "leader_bad", "leader_gone", "invited", "channel_ready",
                            "channel_failed",
                            "stop_leader_done", "route_party_ready", "route_done", "rally_ready",
                            "path_done", "route_plan_ready"):
                    st[key].clear()
                st["channel"] = None
                st["channel_expected_map"] = None
                st["mob_spot"] = None
                st["rally_point"] = None
                st["mob_path"] = None
                st["route_plan"] = None
                st["event_exit_now"].clear()
                st["2k_ket_qua"] = None
                st["o5_state"] = "idle"
                st["o5_broke"] = False
                st["o5_need_redo"] = False
                st["team_dungeon_state"] = {}
                st["team_dungeon_broke"] = {}
                st["team_dungeon_tries"] = {}
                st["team_dungeon_skip_all"] = False
                st["team_dungeon_need_redo"] = False
                st["started_train"] = 0
                st["dungeon_done"] = 0
                st["dailies_done"] = 0
                prepared = True
        if prepared:
            reset_party_joined(pidx)
        return prepared

    last_log = 0.0
    last_recheck = 0.0
    _st_gen = _pstate(pidx)
    _gen0 = _st_gen.get("reform_gen", 0)
    while True:
        if stopped_fn():
            return False
        # NGHE LENH DIEU PHOI. Vong nay co the dung yen HANG TIENG (cho dong doi xong DG); ket o
        # day ma diec voi lenh thi dieu phoi co ra lenh cung vo ich - dung cai da giet party 15
        # (07/09): dieu phoi in "LAP LAI PARTY" moi 2 phut suot 26 phut ma khong ai nghe, vi leader
        # dang ket trong mot vong cho khac.
        if _st_gen.get("reform_gen", 0) != _gen0:
            # TRA "lenh_moi" CHU KHONG PHAI False. `False` o ham nay co nghia la BI STOP, va caller
            # doi xu voi no bang cach KHONG set `relogin_train` -> `_ket_thuc_pha_dg()` goi
            # `c.close()` -> ACC CHET HAN, khong ai login lai.
            #
            # Ca that 09/09 party 2 (user: "danh DG xong thay nhieu acc tat vay"):
            #   06:02:15 [party 2] REFORM gen -> 5 - ep dong bo (nhe): watcher: party thieu nguoi qua lau
            #   06:02:16 [gamo]  dieu phoi ra lenh moi khi dang cho ca party xong DG -> thoi cho
            #   06:02:22 >>> PARTY 2 DA THOAT HET vi: het gio Di Gioi trong luc sync kenh DG
            # `sga001` im tu 06:02:21 den het log (hon 4 tieng). Sau nay 6 party di y het duong nay.
            #
            # "Co lenh dieu phoi moi" la ly do de THOI CHO va di NGHE LENH - khong phai ly do de
            # tat acc.
            log.info("[%s] dieu phoi ra lenh moi khi dang cho ca party xong DG -> thoi cho", label)
            return "lenh_moi"
        # ==== TU SOAT LAI TRONG LUC CHO (moi DT_RECHECK_SEC) ====
        # Dang cho dong doi (co the 2 TIENG) -> thoi gian chet. Truoc khi chiu dung yen, kiem tra
        # lai bang so SERVER xem CO THAT SU het gio khong, va con Ho Phu thi dung de vao danh tiep.
        # (Sang nay da co bug "bi tinh het gio nhung thuc ra van con" -> khong duoc tin ket luan cu.)
        if time.time() - last_recheck > DT_RECHECK_SEC:
            last_recheck = time.time()
            try:
                if _dt_recheck_time_left(username, label):
                    return "back_to_dg"
            except Exception as e:
                log.warning("[%s] DG+Train: loi soat lai gio DG (bo qua): %s", label, e)
        users = set(_dt_party_usernames(pidx))
        switch_to_train = False
        n_users = 0
        # BOT DOC THANG tung client (L2): no dieu khien acc nen no TU BIET acc nao het gio DG -
        # khong acc nao khai bao, ke ca kieu "ghi co len client cua chinh minh".
        #
        # `_acc_het_gio_dg` tra None = CHUA BIET (acc dang dis / chua nhan dong ho server). Chua
        # biet thi KHONG tinh la xong: tinh la xong se lam ca party bo di train trong khi acc do
        # con nguyen gio DG (ca that 09/09 `haabo` - chua vao DG lan nao van bi ghi "xong DG").
        done = {u for u in users if _acc_het_gio_dg(account_clients.get(u)) is True}
        with st["lock"]:
            if st.get("dt_phase") == "train":
                switch_to_train = True  # acc khac da chuyen pha roi -> di train luon
            # DG+Train giu nguyen nguyen tac DU PARTY: chi khi tat ca acc trong party da bao
            # xong DG moi chuyen pha train. Acc dang bi STOP thi bo qua de Stop khong treo.
            elif users and users <= done:
                st["dt_phase"] = "train"
                switch_to_train = True
                n_users = len(users)
        if switch_to_train:
            if _prepare_train_phase_once():
                log.info("[%s] DG+Train: CA PARTY (%d acc) da xong Di Gioi -> reset state DG, "
                         "CHUYEN PHA TRAIN", label, n_users or len(users))
            return True
        if time.time() - last_log > 60:
            last_log = time.time()
            # NEU RA TEN + MAP cua acc con THIEU. Truoc day chi in "(2/5 acc xong)" -> treo ca dem
            # ma khong biet dua nao ket o dau, acc ket lai KHONG in log gi (log 22:59-23:07: 3 acc
            # dung o Quang Truong, khong mot dong log).
            missing = sorted(users - done)
            detail = ", ".join(
                "%s@map%s" % (u, getattr(account_clients.get(u), "current_map", "?"))
                for u in missing
            )
            log.info("[%s] DG+Train: xong DG, DUNG YEN cho party (%d/%d acc xong) - cho khong "
                     "gioi han | CON THIEU: %s", label, len(done & users), len(users),
                     detail or "-")
        time.sleep(5)


def lam_login_chores(c, username, label, role, pcfg, mode="", login_map=None):
    """VIEC VAT SAU LOGIN - tach ra tu `run_account` de CA HAI ENGINE dung chung.

    Truoc day khoi nay nam han trong `run_account`, nen engine moi (khong chay `run_account`)
    MAT SACH: diem danh, qua 14 ngay, qua quan doan, qua ban be, mo rong tui, tu cong diem, nang
    skill, Ba Dau, skill pet, LO HOANG KIM, donate quan doan, ruong trang bi, mua shop...
    Ba trong so do con la nguon cua bang "Chu y" tren GUI (`_tu_cong_diem` -> diem du,
    `_kiem_han_ba_dau` -> Ba Dau, `process_furnace` -> lo) => user 16/09: "hinh nhu bi mat cai chu y".

    Engine moi TU CHE mot danh sach 9 viec thay cho khoi nay - thieu ca chuc muc. Tach ra roi thi
    khong con ban nao "tu nho" nua.
    """
    _early_mode = mode
    if login_map is None:
        login_map = c.current_map
    if pcfg.get("claim_offline_exp", True):
        c.request_offline_exp() # NHAN EXP OFFLINE (treo may) - tu nhan neu co
    c.claim_mail()          # nhan qua mail + xoa mail da doc (qua bao tri,...)
    # NHAN QUA THANH TUU (yeu cau user: ngay SAU check mail, LUON chay - khong can tick).
    # Chi doc 2 bit trong forever-flags (0x51) nen re; tui day thi tu hoan.
    try:
        c.claim_achievements()
    except Exception as e:
        log.warning("[%s] loi nhan qua thanh tuu (bo qua): %s", label, e)
    c.claim_checkin()       # diem danh hang ngay (tu dem so lan)
    c.claim_14day_gift()    # qua 14 ngay user moi (0x57)
    c.claim_event_14day()   # event tang qua 14 ngay (0x7c) - khac cai tren
    c.claim_legion_gift()   # nhan qua quan doan hang ngay
    c.claim_friend_gifts()  # tang qua tat ca ban + nhan qua ban tang (hang ngay)
    c.decompose_junk_scrolls()  # phan giai cuon goi pet RAC (junk_scrolls.json) -> Vo Tuong Phien
    # TU MO RONG TUI DO: mua slot toi khi gia lan KE TIEP vuot nguong user dien. Dat TRUOC
    # cac viec don tui (ban Noi Dat / vut rac) de tui rong san, va truoc `use_items` de co
    # cho nhan do. Mac dinh TAT.
    if pcfg.get("auto_bag_expand") and int(pcfg.get("bag_expand_gold", 0) or 0) > 0:
        try:
            c.tu_mo_rong_tui(int(pcfg.get("bag_expand_gold", 0) or 0))
        except Exception as e:
            log.warning("[%s] loi tu mo rong tui do (bo qua): %s", label, e)
    # TU CONG DIEM TIEM NANG cua NHAN VAT (bang rule rieng tung acc). Chi chay MOT LAN
    # luc login, cung cho voi cac viec vat khac.
    _tu_cong_diem(c, username, label)
    # TU NANG SKILL NHAN VAT (bang rule rieng tung acc, giong Point). Dat NGAY SAU tu cong
    # diem: cung la "tieu diem theo bang rule", va cung chi chay MOT LAN luc login.
    _tu_nang_skill(c, username, label)
    _kiem_han_ba_dau(c, username, label)   # Ba Dau sap het han -> bao o man Chu y
    if pcfg.get("auto_pet_skill", True):   # AUTO NANG SKILL PET: pet co diem skill -> nang (index 0->1->2 toi max)
        try:
            _n = c.auto_upgrade_pet_skills()
            if _n:
                log.info("[%s] auto nang skill pet: da gui nang cho %d pet", label, _n)
        except Exception as e:
            log.warning("[%s] loi auto nang skill pet (bo qua): %s", label, e)
    # SOI LO + xu ly theo config per-acc (ACCOUNT_FURNACE): tab bat + item auto mua / notify.
    # Config trong -> chi soi + log 3 tab (nhu Pha 1). Notify list -> log (Pha 2 GUI popup).
    try:
        _fcfg = getattr(config, "ACCOUNT_FURNACE", {}).get(username, {})
        _notify = c.process_furnace(_fcfg)
        if _notify:
            account_furnace_notify[username] = _notify   # GUI doc de popup hoi mua
    except Exception as e:
        log.warning("[%s] loi soi/mua lo: %s", label, e)
    if pcfg.get("auto_donate_materials", True):
        c.donate_legion()       # donate nguyen lieu cho quan doan (list edit duoc, mac dinh het) -> don tui
    # RUONG TRANG BI: mo -> phan giai duoc thi phan giai, khong thi donate quan doan.
    # DAT NGAY SAU donate nguyen lieu (user chot 03/09) de tan dung ket qua "co donate
    # duoc hay khong": do khong phan giai duoc chi con duong donate, ma donate can da vao
    # quan doan >24h (server tra S:039-015 ma 32 neu chua du) -> chua donate duoc thi mo
    # ruong ra cung vo ich, con lam day tui.
    if pcfg.get("auto_open_boxes", False):
        try:
            _kq = c.tu_mo_hop_trang_bi(chon=pcfg.get("box_modes") or {})
            if _kq.get("bo_qua"):
                log.info("[%s] Ruong trang bi: bo qua (%s)", label, _kq["bo_qua"])
            elif _kq.get("mo"):
                log.info("[%s] Ruong trang bi: mo %d, phan giai %d, donate %d, vut %d",
                         label, _kq["mo"], _kq["phan_giai"], _kq["donate"],
                         _kq.get("vut", 0))
        except Exception as e:
            log.warning("[%s] loi tu mo ruong trang bi: %s", label, e)
    # THA DO THOI TRANG vao Bo Suu Tam (gon tui + diem). DAT TRUOC use_login_items vi tha CHAC
    # CHAN free slot, con use_item doi khi de item MOI ra lam day tui (theo yeu cau user).
    try: c.deposit_fashion_to_collection()
    except Exception as e: log.warning("[%s] loi tha do thoi trang: %s", label, e)
    c.use_login_items()         # tu dung item trong list (use_items.json) -> vd tui vat lieu su kien
    # THU CUOI: nang cap + boi duong bang 5 vien ky don. CHAY NGAY SAU use_login_items()
    # (yeu cau user) vi tui vat pham vua duoc mo ra o buoc tren co the CHINH LA nguon vien
    # ky don (vd "Tui Toa Ky Dan" 0xb22c). LUON BAT, khong co o tick trong setting.
    try:
        c.do_mount_upgrade()
    except Exception as e:
        log.warning("[%s] loi nang cap thu cuoi: %s", label, e)
    # Phuc Than NGAY SAU use_login_items() - luc nay con dung an toan o thanh/diem login
    # (chua di ra bai quai) -> tranh bug dung/deo Phuc Than GIUA luc dang combat ngoai bai
    # (da tung xay ra vi next_phuc_than=0.0 chi trigger o tick dau cua vong lap chinh, co
    # the roi vao luc dang di ra spot/dang danh).
    # Mode EVENT (40NPC/2K): KHONG dung Phuc Than (yeu cau user - vao event khong an he so
    # EXP nay, dung la phi item).
    # DUNG _early_mode: bien `mode` mai ~1300 moi gan (SAU cho nay) -> dung `mode` o day
    # la UnboundLocalError, thread run_account CHET va CA PARTY thoat (bug that 00:48).
    # (Co `phuc_than_tat` dat trong `run_account` ngay sau "vao world" - cho do chay cho MOI acc
    #  MOI lan login. TUNG dat o day, nhung ham nay chi chay khi acc con viec vat login: acc da
    #  xong chore thi co van False -> `use_phuc_than_items` DEO LAI ngoc vua thao. Xem ca that
    #  ttba 21/09 ghi o cho dat co.)
    if pcfg.get("use_phuc_than") and not getattr(c, "phuc_than_tat", False):
        try: c.use_phuc_than_items()
        except Exception as e: log.warning("[%s] loi dung phuc than luc login: %s", label, e)
        next_phuc_than = time.time() + PHUC_THAN_CHECK_SEC
    # Van tieu: nhan qua xong + gui pet; tra ve gio check tiep. Cong tac "Van tieu" trong
    # Cai dat nang cao (mac dinh CO tick - giu hanh vi cu); tat -> khong lam + khong hen gio.
    # Cong tac van tieu nay o TUNG ACC (bang setting Hoi HP/SP), khong con o cap party ->
    # goi thang, chinh do_van_tieu() doc c.vantieu_enable roi tu quyet dinh.
    next_vantieu = c.do_van_tieu()
    # MUA SHOP (Cai dat nang cao, mac dinh TAT): master auto_buy_shop + list shop.
    # Dua theo RoleCount server 0x55 neu biet counter; item chua ro counter thi server tu reject.
    if pcfg.get("auto_buy_shop"):
        _shop_items = pcfg.get("shop_items") or {}
        if pcfg.get("buy_ho_phu") or _shop_items.get("ho_phu"):
            try:
                log.info("[%s] Mua shop: setting Ho Phu bat -> check mua 3 cai/ngay", label)
                c.buy_di_gioi_ho_phu()
            except Exception as e: log.warning("[%s] loi mua Ho Phu: %s", label, e)
        if pcfg.get("buy_thien_chau") or _shop_items.get("thien_chau"):
            try:
                c.buy_hop_thien_chau()
            except Exception as e: log.warning("[%s] loi mua Hop Thien Chau: %s", label, e)
        if pcfg.get("buy_bao_hop") or _shop_items.get("bao_hop"):
            try: c.buy_trieu_goi_bao_hop(int(pcfg.get("bao_hop_xu_threshold", 10000000)))
            except Exception as e: log.warning("[%s] loi mua Bao Hop: %s", label, e)
    # MUA HP/SP (Cai dat nang cao, mac dinh TAT): neu du tru HP/SP < nguong -> di Trac Quan
    # mua Vien Hanh Khi (+62HP) / Thien Kim Du (+62SP). Gop HP+SP 1 chuyen. 1 lan/ngay/acc.
    if pcfg.get("buy_hp") or pcfg.get("buy_sp"):
        try:
            c.buy_hp_sp(
                pcfg.get("buy_hp", False), int(pcfg.get("hp_qty", 9999)),
                int(pcfg.get("hp_thresh", 500000)),
                pcfg.get("buy_sp", False), int(pcfg.get("sp_qty", 9999)),
                int(pcfg.get("sp_thresh", 500000)),
            )
        except Exception as e: log.warning("[%s] loi mua HP/SP: %s", label, e)
        # Chuyen mua HP/SP DOI MAP (Trac Quan -> map NPC -> ve lai Trac Quan). `login_map`
        # doc luc login van la map cu -> cac nhanh duoi bam theo no se tuong acc dang o bai
        # train va KHONG keo ve (user bao 28/08: "no dung ket o Loi dai Huong dung").
        if c.current_map is not None and c.current_map != login_map:
            log.info("[%s] sau mua HP/SP: map %s -> %s, cap nhat lai login_map",
                     label, login_map, c.current_map)
            login_map = c.current_map
    # BOSS QUAN DOAN ngay sau van tieu: danh solo neu con luot (server count 0x55/0x2a) + het
    # cooldown. KHONG lien quan daily quest (tick hay ko van danh). Luc login char SOLO (chua
    # lap party) -> danh duoc. Trong phien: keepalive trigger REFORM khi con luot (xem duoi).
    # Mode EVENT (40NPC): mac dinh KHONG danh boss quan doan (acc event chuyen tam cho event,
    # khong di lang thang danh boss lam tre vao event).
    if pcfg.get("mode") == "event":
        log.info("[%s] (%s) mode event -> bo qua boss quan doan (mac dinh)", label, role)
    else:
        try: c.do_legion_boss()
        except Exception as e: log.warning("[%s] loi do_legion_boss: %s", label, e)
    # Mua HP/SP co the DOI MAP (Trac Quan -> map NPC -> ve lai). Tra `login_map` da cap nhat de
    # caller khong bam theo so cu (user 28/08: "no dung ket o Loi dai Huong dung").
    return login_map


def run_account(username, password, pidx, is_leader, is_picker=False, is_reconnect=False,
                reuse_client=None):
    # is_reconnect=True (supervisor goi lai sau khi rot): RECONNECT NHE - bo qua daily/gacha/mail/
    # vantieu (da lam phien truoc) -> vao world la di THANG toi sync kenh + gom party + keo ra bai,
    # KHONG teleport ve Trac Quan lam daily (truoc day: reconnect chay full startup -> lech nhip leader
    # -> ve thanh khong duoc keo -> "SAI MAP -> THOAT" chet luon).
    label = username
    role = "LEADER" if is_leader else "member"



    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    _resume_2k = False   # True = login lai khi dang DUNG TRONG thap 2K -> leo tiep tai cho
    st = _pstate(pidx)
    # EP DONG BO: ghi epoch phien nay dang chay. Sau khi relogin (do resync) run_account chay lai ->
    # doc epoch MOI (da bump) -> khop -> khong raise lai. _resync_ck so sanh voi gia tri nay.
    account_sync_epoch[username] = st.get("sync_epoch", 0)
    stop_ev = account_stops.get(username)   # GUI yeu cau STOP -> thoat moi giai doan
    def _stopped():
        return stop_ev is not None and stop_ev.is_set()
    er = {"r": "ket thuc binh thuong (het gio hoac GUI dung)"}  # ly do thoat (de tong ket party)
    # MODE digioi_train: xong DG + ca party xong -> CAN relogin de chay pha TRAIN (khong phai "rot").
    # Dung dict de set duoc tu cac nhanh ben trong (khong vuong scope).
    _dt = {"relogin_train": False}
    def _reason(msg):
        er["r"] = msg
    # Server (IP) theo config rieng cua party
    _pc0 = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
    server_ip = _pc0.get("server_ip") or config.GAME_HOST
    server_name = _pc0.get("server", "?")
    server_id = _pc0.get("server_id", 1)
    _login_failed = False   # True neu login/vao world that bai 6 lan -> supervisor van thu lai (backoff)
    _unexpected_error = False  # True neu dinh Exception bat ngo -> cho relogin (dung de acc chet han vi loi thoang qua)
    try:
        # --- Login + cho vao world THUC SU (co self_entity VA co current_map) ---
        c = None
        ok = False
        attempt = 0
        _rl_hits = 0   # so lan bi server CHAN TOC DO dang nhap (ma 90)
        if reuse_client is not None:
            # CHUYEN PHA (DG -> train) GIU NGUYEN KET NOI: khong dang nhap lai.
            # User: "relogin thi lam kho login" - server chan toc do dang nhap (ma 90), 5 acc
            # relogin cung luc la ca party ket vong login hang phut. Ma viec o day chi la doi PHA,
            # ket noi van tot nguyen.
            c = reuse_client
            c._label = label; c._username = username
            c.party_idx = pidx
            c._o5_team_fn = (lambda o5d, _c=c:
                             _handle_o5_team(_c, st, username, label, pidx, is_leader, _stopped, o5d))
            account_clients[username] = c
            ok = True
            log.info("[%s] CHUYEN PHA train - GIU NGUYEN ket noi (khong dang nhap lai)", label)
        while not ok and attempt < 6:
            if _stopped():
                log.info("[%s] STOP truoc khi login xong", label); return
            try:
                cred = login(username, password)
                c = GameClient(cred["user_id"], cred["access_token"], host=server_ip, server_id=server_id)
                c._label = label; c._username = username
                log.info("[%s] server=%s (%s) id=%s", label, server_name, server_ip, server_id)
                c.party_idx = pidx
                # Hook o5 pho ban to doi = BUOC CUOI claim_daily_quests (xem _handle_o5_team)
                c._o5_team_fn = (lambda o5d, _c=c:
                                 _handle_o5_team(_c, st, username, label, pidx, is_leader, _stopped, o5d))
                c.submit_delay = 0.3
                # 2 co "chet -> ve thanh" cua HOP MAY: phai set TRUOC connect() vi chuoi 0x41 duoc
                # gui ngay trong connect(). Doc thang config.PARTY_CONFIG chu khong dung bien pcfg
                # (pcfg mai dong ~1153 moi co, tuc SAU connect). Mac dinh BAT = giong client that.
                _pc0 = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
                c.death_return_town = bool(_pc0.get("death_return_town", True))
                c.pet_death_return_town = bool(_pc0.get("pet_death_return_town", True))
                # VAN TIEU per-acc (bang setting Hoi HP/SP cua acc). Mac dinh: BAT, KHONG tick con
                # nao -> vantieu_candidates() tra ve TAT CA = y het hanh vi cu.
                _vt0 = (getattr(config, "ACCOUNT_VANTIEU", {}) or {}).get(username, {}) or {}
                c.vantieu_enable = bool(_vt0.get("on", getattr(config, "VANTIEU_ENABLE", True)))
                c.vantieu_pick_ids = tuple(_vt0.get("pets") or ())
                c.connect()
                # cho self_entity + map (map=None = chua vao world xong)
                for _ in range(15):
                    if c.self_entity is not None and c.current_map is not None:
                        ok = True; break
                    time.sleep(1)
                if ok:
                    break
                # SERVER CHAN TOC DO (S:000-000 ma 90): thu lai sau ~20s van bi chan tiep -> ket
                # vong. Log that (party 6, 23:15-23:17): taot001/taot003 lap lai deu dan moi ~22s,
                # lan nao cung "DANG NHAP QUA THUONG XUYEN". Backoff o supervisor KHONG cuu duoc vi
                # vong nay nam TRONG run_account, chua he thoat ra toi do.
                # -> cho lau dan, va KHONG tinh la lan login that bai (giong nhanh error_code=1):
                #    day la server chan, khong phai sai tai khoan.
                if int(getattr(c, "disconnect_cause", 0) or 0) == DISCONNECT_RATE_LIMIT:
                    _rl = _rl_hits + 1
                    _w = min(30 * _rl, 300)
                    log.warning("[%s] chua vao world - SERVER CHAN TOC DO DANG NHAP (lan %d) "
                                "-> nghi %ds roi thu lai, KHONG tinh la fail", label, _rl, _w)
                    c.close()
                    for _ in range(_w):
                        if _stopped():
                            break
                        time.sleep(1)
                    _rl_hits = _rl
                    continue
                log.warning("[%s] chua vao world (entity=%s map=%s) -> login lai...",
                            label, c.self_entity is not None, c.current_map)
                c.close(); attempt += 1; time.sleep(5)
            except Exception as e:
                # login() (auth HTTP) / connect() LOI (server lom, mang chap) -> KHONG de nick CHET:
                # coi nhu 1 lan thu that bai, backoff 5s roi thu lai; het 6 lan -> _login_failed ben
                # duoi (supervisor reconnect vo han). Truoc day login() raise -> thoat ca vong -> thread
                # chet han (bug: nick "tat" khi server lom lam login HTTP fail).
                if _login_error_code(e) == 1:
                    wait = random.randint(LOGIN_ERR1_RETRY_MIN_SEC, LOGIN_ERR1_RETRY_MAX_SEC)
                    log.warning("[%s] login error_code=1 (%s) -> nghi %ds roi thu lai, KHONG tinh la fail",
                                label, _login_error_message(e), wait)
                    try:
                        if c is not None: c.close()
                    except Exception: pass
                    for _ in range(wait):
                        if _stopped():
                            break
                        time.sleep(1)
                    continue
                attempt += 1
                log.warning("[%s] login/connect loi (lan %d): %s -> thu lai", label, attempt, e)
                try:
                    if c is not None: c.close()
                except Exception: pass
                time.sleep(5)
        if not ok:
            _login_failed = True   # -> supervisor thu login lai (backoff), KHONG de nick chet luon
            _reason("login/vao world that bai (6 lan) -> supervisor thu lai")
            log.warning("[%s] >>> LOGIN/VAO WORLD THAT BAI sau 6 lan -> supervisor se thu lai", label)
            try:
                if c is not None: c.close()
            except Exception: pass
            return
        _clients.append(c)
        account_clients[username] = c     # GUI doc trang thai
        st["reconnecting"].discard(username)  # (reconnect) da vao world lai -> khong con "dang rot"
        # MOC "CO ACC VUA VAO WORLD" cho GUI. Bang "Chu y" (tui / Ba Dau / quan doan / du diem /
        # lo) dung lai danh sach tu nam nguon cho tung acc, qua nang de chay moi giay tren main
        # thread Tk (user 13/09: "click doi party thay do rat lau moi load ra... not responding").
        # GUI cache theo so nay: SO DOI = dung lai MOT lan, roi giu.
        #
        # Cho nay la moc duy nhat dung cho CA login dau LAN reconnect (user 14/09: "cu acc login
        # xong la cache lai 1 lan, reconnect khi dis cung cache lai, don gian la login vi bat ky
        # ly do gi cung cache lai").
        with st["lock"]:
            st["login_gen"] = int(st.get("login_gen", 0) or 0) + 1
        label = c.char_name or username   # log theo TEN NHAN VAT (neu da resolve), fallback username
        if is_leader and c.char_name:
            # Tu dong them ten nhan vat leader vao whitelist "leaders" cua party - user da cau hinh
            # account nay la leader trong Party roi thi khong can go tay lai ten o whitelist rieng.
            config.record_leader_name(pidx, c.char_name)
        login_map = c.current_map         # map LUC LOGIN (doc som, it bi pollution) - dung de check train
        log.info("[%s] (%s) vao world.", label, role)
        # MODE EVENT: TAT HAN Phuc Than (user chot 21/09) - tick hay khong cung khong dung, dang
        # deo thi THAO RA.
        #
        # DAT O DAY chu khong phai trong `lam_login_chores`: ham do CHI chay khi acc con viec vat
        # login. Acc da xong chore thi co van `False` -> `use_phuc_than_items` chay binh thuong ->
        # DEO LAI ngoc ngay sau khi vua thao.
        # Ca that 21/09 (ttba, party 6 - mode event suot):
        #   20:28:15 Phuc Than: DA THAO ... | 20:28:15 Da coi do: vi tri 6   <- server xac nhan
        #   (20:36 login lai, khong phai thao - dung, luc do chua deo)
        #   21:03:37 DA THAO lai chinh con ngoc do                            <- da bi deo lai
        # User: "no thao ra roi ma lan chay sau van thao tuc la no van con tren nguoi".
        #
        # Cho nay chay cho MOI acc, MOI lan login, va VAN o truoc cua re engine moi ben duoi.
        try:
            c.phuc_than_tat = ((getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {})
                               or {}).get("mode") == "event"
            if c.phuc_than_tat:
                c.thao_ngoc_phuc_than("mode event - khong dung Phuc Than")
        except Exception as e:
            log.warning("[%s] loi tat/thao Phuc Than: %s", label, e)
        # === CUA RE SANG ENGINE MOI (documents/ENGINE_PARTY_MOI.md) ==========================
        # Dat DUNG o day, sau khi login/vao world xong va TRUOC moi kich ban: phan login co qua
        # nhieu chi tiet song con (chan toc do dang nhap ma 90, error_code=1, co chet-ve-thanh,
        # van tieu per-acc) - chep lai sang engine moi thi chac chan lech dan. Mot diem re, khong
        # di chuyen mot dong nao cua engine cu.
        #
        # Party KHONG thuoc engine moi thi dong nay khong lam gi ca (`dung_engine_moi` tra False).
        _dang_ky_engine_moi(username, c, pidx, is_leader, label, _stopped,
                            is_reconnect=is_reconnect)
        return

    except Exception as e:
        import traceback
        _unexpected_error = True   # loi bat ngo -> KHONG de acc chet han, cho supervisor relogin lai
        _reason("LOI ngoai le: %s" % e)
        log.error("[%s] LOI: %s\n%s", label, e, traceback.format_exc())
    finally:
        # Go entity minh khoi _PARTY_JOINED: acc thoat/rot la RA KHOI party that (server tan lien
        # ket). Khong go -> lan reconnect sau leader dem "da join" STALE -> vua moi da tuong du
        # 4/4 (khong ai accept that) -> leader danh 1 minh ca phien (bug thuc te DG 09:18).
        if c is not None:
            try: unmark_joined(c.party_idx, c.self_entity)
            except Exception: pass
        # RECONNECT: server ROT (server_closed) + khong phai GUI-STOP -> supervisor se login lai.
        # Khi do KHONG set leader_gone (member phai CHO, dung thoat theo) + KHONG tong ket.
        # KHONG doi hoi has_leader: party "khong co chu PT" (vd dung yen trong DG cho moi tay) truoc
        # day rot mang la CHET LUON du con gio -> user bao "dang o DG con time ma tu out". Gio moi
        # mode deu tu login lai; dung han chi khi GUI Stop / thoat binh thuong (het gio DG...).
        _forced_reconnect = username in account_forced_reconnect
        reconnectable = (not _stopped()
                         and (_forced_reconnect or _login_failed or _dt["relogin_train"]
                              or _unexpected_error
                              or (c is not None and getattr(c, "server_closed", False))))
        account_reconnect[username] = reconnectable
        # NOI DUNG LY DO. Cau log cua supervisor mac dinh la "server rot" -> relogin CO Y (chuyen
        # pha train sau khi xong DG + viec vat) nhin y het bi server da. Da ton mot buoi truy vu
        # "5 acc party 25 rot lien tuc" ma that ra KHONG acc nao bi rot: khong he co dong
        # "Server dong ket noi", khong co goi-cuoi nao - vi don gian la server khong dong gi ca.
        if (reconnectable and not _forced_reconnect and not _login_failed and not _unexpected_error
                and not (c is not None and getattr(c, "server_closed", False))
                and _dt["relogin_train"]):
            account_forced_reconnect_reason[username] = "chuyen pha TRAIN (relogin CO Y, khong phai rot)"
        if is_leader and not reconnectable and account_threads.get(username) is threading.current_thread():
            st["leader_gone"].set()   # leader thoat that su -> member ngung co vao party
        # ghi lai ly do thoat (neu GUI bam STOP ma chua co ly do cu the -> ghi STOP)
        if _stopped() and er["r"].startswith("ket thuc binh thuong"):
            _reason(account_stop_reasons.get(username) or "STOP")
        # SERVER chu dong dong ket noi (rot/bao tri/kick) - KHONG phai ket thuc binh thuong/STOP
        elif (not _stopped() and er["r"].startswith("ket thuc binh thuong")
              and c is not None and getattr(c, "server_closed", False)):
            _reason("SERVER dong ket noi (rot mang/bao tri/kick) - khong phai tu thoat")
        account_exit_reason[username] = er["r"]
        if _stopped():
            account_stop_reasons.pop(username, None)
        # LUU map + ten nhan vat + LEVEL char/pet + ten pet LUC THOAT -> GUI van hien thong tin
        # nhu luc truoc khi tat (truoc day chi luu map+char -> tat la mat level/pet).
        if c is not None and getattr(c, "current_map", None) is not None:
            account_last[username] = {"map": c.current_map, "char": c.char_name or username,
                                      "char_level": getattr(c, "char_level", None),
                                      "pet_name": c.pet_name_out(),
                                      "pet_level": getattr(c, "pet_level", None)}
        account_clients.pop(username, None)
        if not reconnectable:   # reconnect thi CHUA tong ket "party thoat het" (nick se login lai)
            try:
                _party_exit_summary(pidx, username)   # neu ca party da tat -> log 1 dong tong ket
            except Exception:
                pass


# ============================================================
#  API DIEU KHIEN (cho GUI gui.py goi). Cung dung cho CLI ben duoi.
# ============================================================
def _leader_live_phase(pidx, st):
    """Pha (phase) hien tai cua LEADER neu leader dang LIVE; None neu khong co leader / leader
    dang reconnecting / activity cu (>45s khong update -> thread chet/treo, khong tin duoc).
    Dung cho member: leader la nhac truong -> member dong bo theo pha leader (chi khi leader live)."""
    lead = config.PARTY_LEADER_ACC.get(pidx)
    if not lead:
        return None
    with st["lock"]:
        if lead in st["reconnecting"]:
            return None
    act = get_account_activity(lead)
    if not act:
        return None
    _task, phase, age = act
    if age > 45:
        return None            # leader im >45s -> khong live -> member CHO (leader se tu resync khi ve)
    return phase


def party_accounts(pidx):
    """List (username, password, is_leader, is_picker) cua party pidx (bo slot trong)."""
    party = config.PARTIES[pidx]
    leader_acc = config.PARTY_LEADER_ACC.get(pidx)
    valid = [(u, p) for u, p in party if u and u.strip()]
    picker_acc = leader_acc if leader_acc else (valid[0][0] if valid else None)
    return [(u, p, u == leader_acc, u == picker_acc) for u, p in valid]


def _clear_o5_client_flags(c):
    """Ha co RIENG cua mot acc (dang o trong instance / quest_mode). Pha PB cua CA PARTY thi khong
    nam o day nua - no do dieu phoi giu (`dat_pha_pho_ban`, xem `bot/client._PARTY_PB_PHA`)."""
    active = (
        time.time() < getattr(c, "_team_dungeon_until", 0.0)
        or getattr(c.state, "quest_mode", False)
    )
    c._team_dungeon_until = 0.0
    c.state.quest_mode = False
    return active


def _team_dungeon_flags(pcfg):
    norm = getattr(config, "normalize_team_dungeons", lambda v: v)(pcfg.get("team_dungeons"))
    if not isinstance(norm, dict):
        norm = getattr(config, "DEFAULT_TEAM_DUNGEONS", {20: True, 50: True, 80: True})
    return {int(k): bool(v) for k, v in norm.items()}


def _force_supervisor_reconnect(username, c, reason):
    account_forced_reconnect.add(username)
    account_forced_reconnect_reason[username] = reason
    try:
        c.close()
    except Exception:
        pass
    return False


def _thoat_pb_ca_party(pidx, ly_do):
    """KEO CA PARTY ra khoi instance pho ban - MOT lenh, dieu phoi lam, khong ai phai tu lo.

    PB VO thi server KHONG gui goi ket thuc (`S:047-012`), nen khong acc nao tu biet ma ra. Truoc
    day moi leader tu goi `_exit_pb_or_reconnect` cho CHINH NO -> leader dung ngoai thanh, member
    con nguyen trong map 62xxx, va `go_to_town` cua ho thi BAIL vi dang trong pho ban to doi
    (user 07/09: "leader o ngoai con member van trong PB kia").

    Ca party chay trong MOT tien trinh nen keo het ra la viec lam duoc ngay (L2: khong ai phai cho
    ai bao cao). Acc nao khong con o instance thi bo qua - `leave_team_dungeon` da tu kiem."""
    ra = 0
    for _t in party_accounts(pidx):
        _c = account_clients.get(_t[0])
        if _c is None or not getattr(_c, "running", False):
            continue
        if not in_instance_map(int(getattr(_c, "current_map", 0) or 0)):
            continue
        try:
            if _c.leave_team_dungeon():
                ra += 1
        except Exception as e:
            log.debug("[%s] thoat PB (%s) loi: %s", _t[0], ly_do, e)
    if ra:
        log.info("[party %d] DIEU PHOI: %s -> keo %d acc ra khoi pho ban (C:047-010)",
                 pidx + 1, ly_do, ra)
    return ra


def _exit_pb_or_reconnect(username, c, reason):
    """RA KHOI instance pho ban roi bao "da xu ly" (tra False y het _force_supervisor_reconnect).

    Uu tien lenh THOAT cua client C:047-010 (giu nguyen ket noi). CHI relogin khi thoat khong duoc:
    tu khi server chan toc do dang nhap (ma 90), relogin de dong bo PB lam acc ket vong login hang
    phut (log that party 6, 23:15-23:25). Rule retry PB (team_dungeon_need_redo / o5_need_redo)
    KHONG doi - caller da danh dau truoc khi goi ham nay.
    """
    try:
        # leave_team_dungeon() tra True o CA HAI truong hop: vua gui lenh thoat XONG, va "von da o
        # NGOAI nen khong gui gi". Truoc day cau log duoi noi chung la "da thoat PB bang C:047-010"
        # -> nhin log tuong bot VAN gui goi giua thanh (user chan doan nham 25/08). Phan biet ra.
        _trong_pb = in_instance_map(c.current_map)
        if c.leave_team_dungeon():
            log.info("[%s] %s -> KHONG relogin (%s)", username,
                     "da thoat PB bang C:047-010" if _trong_pb else "von da o NGOAI pho ban",
                     reason)
            return False
    except Exception as e:
        log.warning("[%s] loi thoat PB (%s) -> quay ve relogin: %s", username, reason, e)
    return _force_supervisor_reconnect(username, c, reason)


# (XOA 13/09 `READY_WAIT_SPLIT_SEC`: nguong de LEADER tu quyet luc nao gom party lech map. Lech
#  map la viec cua dieu phoi - no doc map ca party moi 2 giay va ra lenh gom.)
READY_WAIT_REFORM_SEC = 120  # moi mai khong du party -> bo luot moi nay, de dieu phoi quyet tiep
TEAM_DUNGEON_MAX_TRIES = 2   # 1 lan dau + 1 lan RETRY. Qua so nay -> BO QUA HET cac PB.


def _mark_team_dungeon_broken(st, level):
    # Dem so lan da thu level nay. Team yeu thi retry vo han chi lam ket ca party ca dem
    # (log 23:45-23:47: fail -> relogin -> fail -> relogin...). User: moi PB chi retry 1 LAN,
    # van khong qua -> bo qua cac PB CON LAI CUA LUOT NAY roi di lam viec tiep theo. KHONG
    # khoa ca ngay: luot chay sau van check PB binh thuong.
    # CHI dem/clear MOT LAN moi chu ky vo (khi need_redo dang False -> True). Bug that: MOI acc goi
    # _mark deu clear recover_seen -> acc phat hien PB vo TRE (thuong leader o 4231) clear MAT nhung
    # member da qua barrier (_prepare da add seen roi vao vong cho) -> ket "4/5" vo tan, khong bao gio
    # du 5. Ngoai ra tries + 1/acc lam skip_all som. Guard bang need_redo (moi caller deu giu st.lock).
    fresh = not st.get("team_dungeon_need_redo")
    if fresh:
        tries = st.setdefault("team_dungeon_tries", {})
        tries[level] = tries.get(level, 0) + 1
        if tries[level] >= TEAM_DUNGEON_MAX_TRIES:
            st["team_dungeon_skip_all"] = True
    st.setdefault("team_dungeon_broke", {})[level] = True
    st["team_dungeon_need_redo"] = True
    st.setdefault("team_dungeon_state", {})[level] = "done"


def _pb_vo_don_lai(st, pidx, label):
    """PB vo -> DON LAI de chay lai, KHONG cho ai relogin ca.

    Ban cu la mot BARRIER diem danh: moi acc `seen.add(username)`, ai toi cuoi thi `Event.set()`,
    nhung acc nao chua toi thi ngoi trong `while not ev.is_set(): sleep(1)` va cu 30s in
    "cho ca party relogin sau PB vo (1/5)...". Do la vi pham thang L2 (bat acc bao cao) va L9
    (Event cho acc khac) - `documents/RULE_DIEU_PHOI.md`.

    Ca that 07/09 p42: PB lv50 XONG luc 10:35:48, leader rot ngay sau -> bot cham "PB vo" ->
        10:39:15..10:40:16 [luubmot] auto phó bản đội: chờ cả party relogin sau PB vỡ (1/5)...
        10:40:39 [luubhai]  go_to_town: DANG TRONG pho ban to doi (map=62012) -> khong teleport
        10:40:39 [luubhai]  (member) reform: CHUA ve duoc Hội Kê (map=62012) -> nghi 10s thu lai
    Leader cho member relogin; member khong relogin ma di reform, ma reform bi chan vi con trong
    phong. Hai ben cho nhau, khong ai ra.

    Gio KHONG cho: don lai trang thai (mot lan, idempotent duoi lock) roi ai lam viec nay di. Party
    lech nhau la viec cua dieu phoi - no da co `reform_gen`/`VIEC_GOM` de gom, va no DOC THANG
    `account_clients[u]` chu khong doi ai diem danh."""
    with st["lock"]:
        if not st.get("team_dungeon_need_redo"):
            return True   # acc khac da don roi -> khong don hai lan, khong log hai lan
        _skip_all = bool(st.get("team_dungeon_skip_all"))
        st["team_dungeon_broke"] = {}
        st["team_dungeon_need_redo"] = False
        if not _skip_all:
            st["team_dungeon_state"] = {}   # xoa -> chay lai tu dau (lan RETRY duy nhat)
    if _skip_all:
        log.warning("[%s] auto phó bản đội: RETRY vẫn KHÔNG qua -> BỎ QUA các phó bản đội còn "
                    "lại của lượt này, chuyển sang việc tiếp theo", label)
    else:
        log.info("[%s] auto phó bản đội: PB vỡ -> dọn lại, chạy lại từ đầu (lần retry duy nhất). "
                 "KHÔNG chờ ai relogin - điều phối lo gom party.", label)
    return True


def _prepare_team_dungeon_redo_after_reconnect(st, username, label, pidx, stopped_fn):
    if stopped_fn():
        return False
    return _pb_vo_don_lai(st, pidx, label)


def _thieu_level(st, members, level):
    """[(username, cap)] cac acc CHUA du cap vao PB lv`level`. PB lvN yeu cau nhan vat cap >= N.

    Acc chua doc duoc cap (chua co goi 0x05) thi KHONG tinh la thieu - tha cho thu con hon bo oan.

    Vi sao can: server khong cho acc duoi cap READY trong phong PB. Bot khong biet dieu do nen cu
    tao phong roi cho 40s, "lv80 member ready 0/4 -> HUY phong, relogin ca party", lap lai moi chu
    ky. Nang hon: `_finish_digioi_train_if_time_over` thay PB hong la `return` NGAY, bo luon
    `do_daily_dungeon()` (o 1) nam ngay duoi -> cuoi ngay 6 acc party 19 thieu o 1 (02/09).
    """
    # DOC THANG cap cua tung acc tu client - khong acc nao phai "bao cap" nua (L2).
    # Acc chua doc duoc cap (chua co goi 0x05) thi KHONG tinh la thieu - tha cho thu con hon bo oan.
    thieu = []
    for m in members:
        c = account_clients.get(m)
        _lv = getattr(c, "char_level", None) if c is not None else None
        if _lv and int(_lv) < int(level):
            thieu.append((m, int(_lv)))
    return thieu


def _handle_auto_team_dungeon(c, st, username, label, pidx, is_leader, stopped_fn, level):
    level = int(level)
    # TU CHO HET TRAN, khong tin nguoi goi. Mo phong PB giua tran = leader ket trong tran, khong
    # vao duoc phong, trong khi member da dong y va dang cho -> "roster phong chi 0/4" -> HUY +
    # relogin ca party (p21, 21/09). Engine moi da co cua chan o tang quyet dinh, nhung mot ham
    # GUI GOI phai tu bao ve minh: engine cu goi no tu cho khac, va code sau nay cung vay.
    if c.in_combat():
        log.info("[%s] (%s) pho ban doi lv%d: DANG TRONG TRAN -> cho het tran roi moi mo phong",
                 label, "LEADER" if is_leader else "member", level)
        c._wait_combat_clear(idle=3.0, cap=120.0)
        if stopped_fn() or not c.running:
            return False
    if not c.wait_mission_steps(timeout=6.0):
        remaining = None
        log.warning("[%s] (%s) phó bản đội lv%d: chưa có status 0x18 -> bỏ qua level này",
                    label, "LEADER" if is_leader else "member", level)
    else:
        remaining = c.team_dungeon_remaining(level)
    with st["lock"]:
        pass
    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    if not has_leader:
        return True
    if not is_leader:
        last_log = 0.0
        _wd0 = time.time()
        with st["lock"]:
            _pb_g0 = st["reform_gen"]     # gen luc BAT DAU cho; doi = leader da goi ve thanh
        while True:
            if stopped_fn() or not c.running:
                return False
            # KHONG dat _barrier_watchdog o day! Member cho leader chay HET pho ban la CHUYEN
            # BINH THUONG va lau 10-20 phut (5 tran + di duong + thoai). Watchdog 180s tuong la
            # "ket" -> ep dong bo -> DA CA 4 MEMBER RA relogin GIUA pho ban, pha nat luot PB
            # (log that 14:03:10 member bat dau cho -> 14:06:10 = dung 180s -> "EP DONG BO").
            # Vong nay da co du duong thoat: stop/rot, st["reconnecting"], leader bao xong.
            _resync_ck(st, username)   # ep dong bo TAY (GUI) van thoat duoc
            set_account_activity(username, "PB lv%d: cho leader xu ly" % level, phase="wait")
            if time.time() - last_log > 60:
                log.info("[%s] (member) chờ leader xử lý phó bản đội lv%d...", label, level)
                last_log = time.time()
            if st["reconnecting"]:
                log.warning("[%s] (member) đồng đội rớt trong phó bản đội lv%d -> relogin thoát instance",
                            label, level)
                with st["lock"]:
                    _mark_team_dungeon_broken(st, level)
                _clear_o5_client_flags(c)
                return _exit_pb_or_reconnect(
                    username, c, "phó bản đội vỡ do đồng đội rớt"
                )
            # LEADER BI KEO DI REFORM trong luc minh dang cho -> phai THEO, khong thi ca party
            # ket (log 14:04: leader "CHO ca party ve thanh 23001 1/5", 4 member "cho leader xu ly
            # PB"). Ngoi no hay gap: acc con luot BOSS THE GIOI danh 10-20' -> sync kenh timeout
            # 60s -> bump reform_gen -> leader bo PB di reform, member khong hay biet.
            # DAT SAU nhanh "dong doi rot" o tren: nhanh do cung bump reform_gen nhung phai di
            # duong RELOGIN de ca party danh LAI PB - khong duoc de check nay cuop mat.
            with st["lock"]:
                _pb_gnow = st["reform_gen"]
            if _pb_gnow > _pb_g0:
                log.warning("[%s] (member) phó bản đội lv%d: leader chuyển sang REFORM "
                            "(reform_gen %d->%d) -> bỏ chờ, về thành cùng party",
                            label, level, _pb_g0, _pb_gnow)
                return True
            # LENH DANG CO HIEU LUC cung phai bo cho - khong chi lenh MOI HON luc minh vao vong.
            #
            # So `reform_gen` voi moc luc vao vong la acc tu chon "lenh nao nghe": lenh ra TRUOC do
            # vai giay va VAN dang chay thi bi coi la lenh cu.
            #
            # Ca that party 24, 13/09 (user: "thang daihai cu dung o trac quan, ko tap trung ve
            # cung team"):
            #   13:19:21 [daihai] (member) pho ban to doi: HOAN - dieu phoi dang ra lenh 'gom'
            #                     (party dang o 3 MAP khac nhau [12001, 21011, 21852])
            #   13:20:19 [daihai] (member) PB lv50: leader chuyen sang REFORM (1->2) -> bo cho
            #   13:20:19 [daihai] (member) cho leader xu ly pho ban doi lv80...
            #   13:21:19 / 13:22:20  y het nhau, khong dut
            # Sang lv80 no vao vong MOI voi moc gen = 2 - dung bang chinh lenh gom dang chay. Tu do
            # lenh do vinh vien la "cu", nen no dung o Trac Quan cho mot viec khong ai lam.
            if party_dang_gom(pidx):
                log.warning("[%s] (member) phó bản đội lv%d: DIEU PHOI đang ra lệnh cấp party "
                            "-> bỏ chờ leader, về cùng party", label, level)
                return True
            with st["lock"]:
                state = st.setdefault("team_dungeon_state", {}).get(level, "idle")
                broke = bool(st.setdefault("team_dungeon_broke", {}).get(level, False))
            if state == "done":
                if broke:
                    log.warning("[%s] (member) phó bản đội lv%d vỡ -> relogin thoát instance",
                                label, level)
                    _clear_o5_client_flags(c)
                    return _exit_pb_or_reconnect(
                        username, c, "phó bản đội vỡ"
                    )
                _clear_o5_client_flags(c)
                return True
            if not c.in_combat():
                try:
                    c.do_heal()
                except Exception:
                    pass
            time.sleep(2)

    members = [t[0] for t in party_accounts(pidx)]
    if len(members) < 2:
        return True
    last_log = 0.0
    _wd0 = time.time()
    _t0_doc = time.time()
    while True:
        if stopped_fn() or not c.running:
            return False
        _barrier_watchdog(st, pidx, _wd0, "leader-cho-report-PB")
        _resync_ck(st, username)   # ep dong bo -> thoat cho report, relogin bam leader
        # Dong doi rot / PB can danh lai TRONG luc leader dang cho report: truoc day leader KHONG
        # co check nay -> member da _mark_team_dungeon_broken + relogin vao hang recover, con leader
        # ket o vong cho report vo han (bug that: leader "cho report 1/5", member "cho relogin 4/5",
        # 2 hang khac nhau khong bao gio gap). -> leader cung relogin vao hang recover de CA PARTY
        # dong bo roi DANH LAI tu dau (giong het nhanh member o tren).
        with st["lock"]:
            _need_redo = bool(st.get("team_dungeon_need_redo"))
            _recon = bool(st["reconnecting"])
        if _recon or _need_redo:
            log.warning("[%s] (LEADER) đồng đội rớt / PB vỡ khi chờ report lv%d -> kéo CẢ PARTY "
                        "ra khỏi phó bản rồi đánh lại", label, level)
            with st["lock"]:
                _mark_team_dungeon_broken(st, level)
            _clear_o5_client_flags(c)
            # KEO CA PARTY ra truoc: PB vo thi khong co goi ket thuc nen khong ai tu biet duong ra.
            # Truoc day leader chi thoat cho CHINH NO -> leader dung ngoai, member ket trong 62xxx.
            _thoat_pb_ca_party(pidx, "PB lv%d vỡ" % level)
            return _exit_pb_or_reconnect(
                username, c, "phó bản đội vỡ (leader đồng bộ lại để đánh lại)"
            )
        # DOC THANG state cua tung member thay vi CHO no "report": ca party chay chung MOT tien
        # trinh, leader nam san account_clients[m]. team_dungeon_remaining() chi doc state cua
        # chinh client do va tra None khi chua co status 0x18 -> goi thang duoc, khong phai cho.
        # Bat member tu khai la thua VA de ket: member ban viec khac / vua relogin thi khong chay
        # doan report -> leader dung do "cho report (1/5)" hang phut (log that party 1, 00:33).
        _live_rem = {}
        for m in members:
            _mc = account_clients.get(m)
            if _mc is None or not getattr(_mc, "running", False):
                continue
            try:
                _r = _mc.team_dungeon_remaining(level)
            except Exception:
                _r = None
            if _r is not None:
                _live_rem[m] = _r
        reports = dict(_live_rem)
        with st["lock"]:
            _du = all(m in reports or m in st["reconnecting"] for m in members)
        if _du:
            break
        # KHONG cho vo han: acc chua co status 0x18 thi doc lai nhip sau. Nhung phai co han - het
        # han thi quyet voi nhung gi doc duoc (acc thieu coi nhu con luot).
        if time.time() - _t0_doc > 30:
            log.info("[%s] (LEADER) PB lv%d: doc duoc luot cua %d/%d acc -> quyet luon, khong cho",
                     label, level, len(reports), len(members))
            break
        set_account_activity(username, "PB lv%d: doc luot ca party" % level, phase="wait")
        time.sleep(2)

    reports = dict(_live_rem)
    if level not in (20, 50, 80, 110):
        log.warning("[%s] (LEADER) phó bản đội lv%d: đã biết trạng thái lượt nhưng chưa có script "
                    "đường đi/trận an toàn -> bỏ qua", label, level)
        with st["lock"]:
            st.setdefault("team_dungeon_state", {})[level] = "done"
        return True
    # CHUA DU CAP -> bo qua PB nay luon, dung tao phong. Server khong cho acc duoi cap ready nen
    # co co gang cung chi ra "member ready 0/4 sau 40s -> HUY phong, relogin ca party" moi chu ky.
    with st["lock"]:
        _thieu = _thieu_level(st, members, level)
    if _thieu:
        log.info("[%s] (LEADER) phó bản đội lv%d: BỎ QUA - %d acc chưa đủ cấp (%s)", label, level,
                 len(_thieu), ", ".join("%s lv%d" % (m, lv) for m, lv in _thieu))
        with st["lock"]:
            st.setdefault("team_dungeon_state", {})[level] = "done"
        return True
    need = []
    missing = []
    done = []
    for m in members:
        rem = reports.get(m)
        if rem is None:
            missing.append(m)
        elif int(rem) > 0:
            need.append(m)
        else:
            done.append(m)
    if missing:
        log.warning("[%s] (LEADER) phó bản đội lv%d: thiếu status của %s -> bỏ qua",
                    label, level, missing)
        with st["lock"]:
            st.setdefault("team_dungeon_state", {})[level] = "done"
        return True
    if len(need) == len(members):
        log.info("[%s] (LEADER) CA party (%d người) còn lượt phó bản đội lv%d -> chạy",
                 label, len(members), level)
        with st["lock"]:
            st.setdefault("team_dungeon_state", {})[level] = "running"
            st.setdefault("team_dungeon_broke", {})[level] = False
        dg0 = st["disc_gen"]
        ok = False
        broken = False
        # LEADER phai biet dong doi ROT NGAY GIUA pho ban (truoc day chi biet SAU khi danh xong:
        # leader danh mot minh het 5 tran ~15 phut roi moi bao vo - log user 14:06). Cam callback
        # de client tu dung o ranh gioi tran / vong cho ket tran (xem client._td_party_gone).
        c._td_party_broken = lambda: bool(st["reconnecting"]) or st["disc_gen"] > dg0
        try:
            ok = bool(c.do_team_dungeon(level))
            if not ok:
                log.warning("[%s] (LEADER) phó bản đội lv%d trả FAIL", label, level)
            if st["disc_gen"] > dg0 or st["reconnecting"]:
                log.warning("[%s] (LEADER) đồng đội rớt trong phó bản đội lv%d -> relogin thoát instance",
                            label, level)
        finally:
            c._td_party_broken = None   # het pho ban -> go callback (khong de ro ri sang viec khac)
            active = _clear_o5_client_flags(c)
            with st["lock"]:
                broken = ((not ok) or (not c.running)
                          or st["disc_gen"] > dg0 or bool(st["reconnecting"]))
                # PB DA DANH XONG (`ok`) thi ROT SAU DO khong phai la "vo". Van coi la `broken` de
                # thoat instance / relogin, nhung KHONG dem la mot lan thu that bai va KHONG bat
                # lam lai - server da tinh luot roi, danh lai la vo ich.
                # Ca that 07/09 p42, ba dong lien nhau:
                #   10:35:48 [luubmot] (LEADER) === PHO BAN TO DOI LV50 XONG -> roi pho ban ===
                #   10:35:50 [luu401]  RECONNECT: server rot -> login lai sau 5s (lan 1)
                #   10:35:58 [luubmot] SERVER NGAT KET NOI: DANG NHAP TRUNG LAP (ma 19)
                # -> bot danh dau PB vo, ca party vao LAI phong 62012, con leader thi dung
                # "cho ca party relogin sau PB vo (1/5)" - hai ben cho nhau, 5 phut khong ra.
                if broken and not ok:
                    _mark_team_dungeon_broken(st, level)
                st.setdefault("team_dungeon_state", {})[level] = "done"
                # CHI DANH DAU, KHONG bump ngay. Bump o day = bump sau MOI level (20/50/80) ->
                # 3 lan/vong, moi lan da member ra khoi trang thai cho de "ve thanh cung party"
                # roi vai giay sau lai moi vao PB ke tiep (log that 01:12:43-53: lv50 xong ->
                # reform_gen 0->1 -> 4 member "bo cho, ve thanh" -> 01:12:47 duoc moi vao lv80).
                # Reform chi CAN 1 LAN sau khi xong HET cac PB, vi luc do moi that su quay lai train.
                st["td_need_reform"] = True
        if broken:
            # KEO CA PARTY ra khoi instance TRUOC. PB vo thi server khong gui `S:047-012` nen khong
            # acc nao tu biet duong ra; leader chi lo minh thi member ket lai trong 62xxx.
            _thoat_pb_ca_party(pidx, "PB lv%d vỡ" % level)
            return _exit_pb_or_reconnect(
                username, c, "phó bản đội vỡ" if active else "phó bản đội fail"
            )
        return c.running
    with st["lock"]:
        st.setdefault("team_dungeon_state", {})[level] = "done"
    log.info("[%s] (LEADER) phó bản đội lv%d: không phải cả party đều còn lượt (đã hết: %s) -> bỏ qua",
             label, level, done)
    return True


def _pb_that_bai_co_phai_dung_han(c, stopped_fn, label, role):
    """PB to doi tra False: co PHAI ly do de DUNG HAN thread khong?

    `_run_auto_team_dungeons_if_needed` tra False cho CA HAI ca: GUI Stop, va PB that bai (vd
    "roster phong chi 2/4 member -> HUY danh" theo rule "phai du pt"). Caller khong phan biet
    duoc nen truoc day cu `c.close(); return` -> thread chet MA KHONG GHI LY DO -> reconnectable
    = False -> st["leader_gone"].set() -> member thay leader chet that -> THOAT THEO -> CA PARTY
    CHET, phai bat tay lai.

    BUG THAT: party 19 (13:46 PB lv20 roster 1/4) va party 35 (13:48 PB lv110 roster 2/4) - ca hai
    deu chet ca party ngay sau khi PB bi huy.

    CHI dung han khi THUC SU la Stop hoac client da chet. PB hong thi chay tiep viec khac."""
    if stopped_fn() or not getattr(c, "running", False):
        return True
    log.warning("[%s] (%s) pho ban to doi khong xong -> KHONG bo party, chay tiep viec khac",
                label, role)
    return False


WB_WAIT_SEC = 300.0     # cho toi da 5' - 1 luot boss ~20s, du cho ca 5 acc danh het luot


def _wait_party_world_boss(st, pidx, label, stopped_fn):
    """LEADER cho CA PARTY danh xong boss the gioi roi moi lap pho ban to doi.

    BUG THAT (log 15:09, party tq4xx): moi acc chay DOC LAP - ai da du 5/5 luot thi xong ngay, con
    tq402 con 0/5 nen dang danh (moi tran ~20s). Leader thay minh xong la lap phong PB va moi luon
    -> tq402 nhan loi moi + an CHUAN BI trong luc DANG TRONG TRAN boss -> khong vao duoc instance ->
    "roster phong pho ban chi 3/4 member" -> HUY danh, ca party thoat ra lam lai.

    Cho theo CO wb_done (dat trong finally cua _maybe_auto_world_boss) chu KHONG theo "dang trong
    tran": acc co the giua 2 luot boss, luc do khong o trong tran nhung van chua xong viec.
    """
    t0 = time.time()
    _log = 0.0
    while not stopped_fn():
        con = [u for u, _p, _l, _k in party_accounts(pidx)
               if is_account_running(u) and account_clients.get(u) is not None
               and u not in (st.get("wb_done") or ())]
        if not con:
            return True
        if time.time() - t0 > WB_WAIT_SEC:
            log.warning("[%s] (LEADER) cho boss the gioi qua %.0fs ma con %s -> lap pho ban luon",
                        label, WB_WAIT_SEC, con)
            return False
        if time.time() - _log > 20:
            _log = time.time()
            log.info("[%s] (LEADER) CHO %d acc danh xong boss the gioi roi moi lap pho ban: %s",
                     label, len(con), con)
        set_account_activity(st.get("leader_user") or label,
                             "cho party xong boss the gioi", phase="wait")
        time.sleep(2)
    return False


def _run_auto_team_dungeons_if_needed(c, st, username, label, pidx, is_leader, stopped_fn, pcfg):
    # DAU VET tren CHINH CLIENT (bot dieu khien acc nen bot BIET no da xong o5 chua) - khong ghi
    # vao bang cap party de acc khac phai doc "bao cao".
    # (truoc day nhan tham so `o5_done` tu acc goi len - da bo cung luc bo bang bao cao o5.
    #  Trang thai o5 la cua CA PARTY nen doc thang tu `st`, khong acc nao truyen vao nua.)
    with st["lock"]:
        c._o5_da_xong = st.get("o5_state") == "done"

    # THU TU user yeu cau: DOI QUA su kien -> NHAN THUONG BANG 3x3 -> roi moi DANH PB TO DOI.
    # Dat o DAY chu KHONG trong claim_daily_quests: mode TRAIN goi thang ham nay, con
    # claim_daily_quests chay SAU va chi khi do_daily -> tung lam doi qua khong bao gio chay.
    # TRUOC ca check auto_team_dungeon: tat PB doi thi van phai doi qua.
    try:
        c.run_event_pre_dungeon()
    except Exception as e:
        log.warning("[%s] loi doi qua/bang su kien truoc pho ban doi (bo qua): %s", label, e)
    if not pcfg.get("auto_team_dungeon", True):
        return True
    if is_leader:
        _wait_party_world_boss(st, pidx, label, stopped_fn)
    flags = _team_dungeon_flags(pcfg)
    levels = getattr(config, "TEAM_DUNGEON_LEVELS", (20, 50, 80))
    # Bo qua CHI LUOT CHAY NAY: doc xong la XOA co ngay. Luot chay moi (login/chu ky sau) lai
    # check PB binh thuong - KHONG khoa ca ngay.
    with st["lock"]:
        _skip_now = bool(st.get("team_dungeon_skip_all"))
        if _skip_now:
            st["team_dungeon_skip_all"] = False
            st["team_dungeon_tries"] = {}
    if _skip_now:
        log.info("[%s] auto phó bản đội: retry không qua -> BỎ QUA phó bản đội LƯỢT NÀY, "
                 "chuyển sang việc tiếp theo (lượt sau vẫn check bình thường)", label)
        return True
    for level in levels:
        if not flags.get(int(level), False):
            continue
        if not _handle_auto_team_dungeon(c, st, username, label, pidx, is_leader,
                                         stopped_fn, int(level)):
            return False
    # XONG HET cac PB moi reform MOT LAN: luong PB tu giai tan party chung de vao instance, nen
    # phai lap lai party train - nhung chi can lap lai khi THUC SU quay ve train, khong phai sau
    # tung level (xem ghi chu o _handle_auto_team_dungeon).
    with st["lock"]:
        st.pop("td_need_reform", False)   # don co; lap lai party la viec cua dieu phoi (L1)
    return True


def _handle_o5_team(c, st, username, label, pidx, is_leader, stopped_fn, o5_done):
    """O5 PHO BAN TO DOI = BUOC CUOI claim_daily_quests (sau khi check + thu lam moi o khac).
    Moi acc report o5 da xong chua. LEADER cho CA party report -> CHI khi MOI nguoi deu CHUA xong o5
    -> tao + keo party vao danh (member auto-accept 0x2f 0f->03 + ready 0x2f 0b trong _on_dungeon,
    di theo leader).
    MEMBER PHAI CHO leader danh xong (o5_state != "idle" roi thanh "done") MOI duoc return -> tiep tuc
    flow rieng (go_to_town/teleport/lap party train). KHONG cho -> member tu chay tiep SONG SONG luc
    dang trong pho ban -> gui 0x06/0x14/0x44 xen vao giua tran -> server khong nhan atk hop le -> turn
    timeout lap lai ~20-25s -> KET CUNG (da xac nhan qua log thuc te: chuba tu "xong daily login ->
    sync kenh + lap party -> teleport" NGAY GIUA LUC dang danh tran 1)."""

    # THU TU user yeu cau: DOI QUA su kien -> NHAN THUONG BANG 3x3 -> roi moi DANH PB TO DOI.
    # Dat o DAY (khong phai trong claim_daily_quests) vi mode TRAIN goi thang ham nay, con
    # claim_daily_quests chay SAU va chi khi do_daily -> tung lam doi qua khong bao gio chay.
    with st["lock"]:
        pass
    # DIEU PHOI DANG RA LENH GOM -> HOAN PHO BAN. Vao PB la ca party bi keo vao INSTANCE rieng:
    # lenh gom dang chay bi bo giua chung, va acc nao chua kip vao thi ket lai ben ngoai.
    #
    # Ca that party 6, 11/09 (user: "p6 deo thay lap pt di PB luon"):
    #   09:32:23 [party 6] gen 3: viec=gom - party dang o 2 MAP khac nhau [12001, 21001]
    #   09:32:24 [ttnnam] Boss the gioi: HOAN - dieu phoi dang ra lenh gom   <- boss BIET hoan
    #   09:32:30 [ttmot]  (LEADER) === PHO BAN TO DOI LV20: tao + moi 4 member ===   <- PB thi KHONG
    # Viec vat (cat do / ban Noi Dat) va boss the gioi deu da doc co nay tu truoc; rieng duong pho
    # ban to doi thi chua ai noi cho no biet. Cung mot co, cung mot cach doc - khong them co moi.
    # KHONG HOAN THEO LENH DIEU PHOI NUA - y het boss the gioi / PB don da bo tu 14/09.
    #
    # Cua hoan cu dat dung vao THOI DIEM LUON DANG GOM: viec nay chay o login chores, ma luc moi
    # login thi ca party dung moi dua mot noi -> dieu phoi ra lenh gom/moi -> HOAN -> va vi chi
    # chay MOT LAN, mat luot CA NGAY. Do tren log 17/09 (user: "thay danh PB don roi, nhung ko
    # danh PB doi"): o5 hoan 100% so lan, khong acc nao cua party engine moi danh duoc PB doi.
    #   23:28:45 [chdumot] (LEADER) pho ban to doi: HOAN - dieu phoi dang ra lenh 'moi'
    #
    # VI SAO GIO AN TOAN (cung ba ly do da viet cho boss the gioi o `_maybe_auto_world_boss`):
    #   - dieu phoi KHONG con tinh acc dang viec vat / `VIEC_DAILY` vao phep do lech map/kenh
    #   - loi moi party duoc GIU lai den khi acc xong viec
    #   - PB to doi keo CA PARTY vao cung mot instance, va ca party deu dang lam daily cung luc
    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    if not is_leader and not has_leader:
        # Party KHONG CO LEADER BOT (vd "Khong co chu PT", cho nguoi that/tay dieu khien) -> KHONG
        # AI se chay nhanh is_leader ben duoi de set o5_state="done" -> cho vo ich toi HET 600s roi
        # moi timeout thoat (xac nhan qua thuc te: claim_daily_quests() bi "treo" dung ~10 phut o
        # buoc nay, moi acc). Khong co leader thi khong co gi de cho -> bo qua NGAY.
        return
    if not is_leader:
        # CHO VO HAN leader quyet dinh + danh xong team dungeon (thoat: dong doi reconnect / o5 done /
        # Stop / tu rot). Truoc day cap 600s roi "coi nhu xong" -> co the bo giua chung.
        _t0log = time.time()
        _t0 = time.time()
        _gen0 = st.get("reform_gen", 0)
        while True:
            if stopped_fn() or not c.running:
                return
            # LOI RA CAP PARTY. Cho leader la hop le KHI PB DANG CHAY THAT; leader ket o cho khac
            # thi day thanh cai bay: member dung tai bai quai voi flee_mode -> "BO CHAY" lien tuc,
            # tuc BI QUAI DANH LE ma khong danh tra (user 07/09: "member bi quai danh le").
            #   1) dieu phoi ra lenh moi (reform_gen doi) -> phai nghe, khong duoc diec.
            #   2) qua 90s ma pha PB VAN CHUA BAT -> leader khong he vao PB -> thoi cho.
            if st.get("reform_gen", 0) != _gen0:
                log.info("[%s] (member) dieu phoi ra lenh moi khi dang cho PB -> thoi cho", label)
                _clear_o5_client_flags(c)
                return
            if time.time() - _t0 > 90 and not dang_pha_pho_ban(pidx):
                log.warning("[%s] (member) cho leader %.0fs ma pha PB chua he bat -> leader khong "
                            "vao PB, thoi cho va lam viec khac", label, time.time() - _t0)
                _clear_o5_client_flags(c)
                return
            if time.time() - _t0log > 60:
                log.info("[%s] (member) CHO leader danh xong team dungeon...", label)
                _t0log = time.time()
            # CASE 3: dong doi ROT trong luc dang danh team dungeon -> phai RA KHOI instance
            # (trong dungeon teleport/ve thanh bi chan). Truoc day dung relogin; tu khi server chan
            # toc do dang nhap (ma 90) thi relogin lam acc ket vong login -> dung C:047-010.
            if st["reconnecting"]:
                log.warning("[%s] (member) dong doi ROT trong team dungeon -> THOAT PB (C:047-010), "
                            "khong relogin", label)
                try: c.leave_team_dungeon()
                except Exception: pass
                _clear_o5_client_flags(c)
                return
            with st["lock"]:
                state = st["o5_state"]
                _broke = st["o5_broke"]
            if state == "done":
                if _broke:
                    # team dungeon VO do co dis -> member CON KET trong instance (map dungeon),
                    # go_to_town KHONG thoat duoc. TRUOC DAY relogin de ra ("relogin xong la ca lu
                    # tu thoat PB") - dung, nhung tu khi server CHAN TOC DO DANG NHAP (ma 90) thi
                    # login lai rat kho: acc ket vong dang nhap hang phut (party 6, 23:15-23:25).
                    # Gio thoat bang dung lenh cua client C:047-010, GIU NGUYEN ket noi, roi dong bo
                    # + danh lai PB theo rule retry cu (o5_need_redo).
                    log.warning("[%s] (member) team dungeon VO (co dis) -> THOAT PB (C:047-010), "
                                "khong relogin", label)
                    try: c.leave_team_dungeon()
                    except Exception: pass
                # Leader da xong (thanh cong hay fail deu vay) -> pha PB da duoc dieu phoi TAT o
                # `finally`; day chi ha not co RIENG cua acc nay (quest_mode/instance).
                _clear_o5_client_flags(c)
                return
            if not c.in_combat():   # xong 1 tran team dungeon (member auto-danh) -> hoi HP/SP
                try: c.do_heal()
                except Exception: pass
            time.sleep(2)
    members = [t[0] for t in party_accounts(pidx)]
    if len(members) < 2:
        return   # khong du party de danh pho ban to doi
    # KHONG CHO REPORT NUA. Ban cu la `while True` cho VO HAN tat ca member "report o5" - barrier
    # kinh dien (L2 + L9), va no khoa LEADER khoi moi lenh cua dieu phoi: leader ket trong vong con
    # nen khong quay lai vong chinh de nghe.
    #
    # Ca that 07/09 party 15 - 26 PHUT (14:40:59 -> 15:06:32):
    #   [trusauu] (LEADER) CHO ca party report o5 (4/5)...      <- lap lai moi 30s
    #   [trutam]  (member) CHO leader danh xong team dungeon...
    #   [truchin] im tu 14:40:40 (khong bao gio report)
    # trong khi DIEU PHOI ra lenh deu dan moi 2 phut ma khong ai nghe:
    #   14:57:37 / 14:59:37 / 15:01:38 / 15:03:38 / 15:05:38
    #     [party 15] DIEU PHOI: ca party da chung kenh 1 nhung doi chi con 0/3 -> LAP LAI PARTY
    # Hau qua nua: member dung tai bai quai voi flee_mode -> "BO CHAY" lien tuc, tuc BI QUAI DANH LE
    # (user hoi: "member bi quai danh le").
    #
    # Doc MOT PHAT: acc nao chua bao thi coi nhu DA XONG o5 -> khong danh PB to doi luot nay. Mat
    # nhieu nhat MOT luot PB (lan chay sau van check binh thuong), doi lay viec khong ket.
    # BOT DOC THANG tung client. Acc chua chay toi buoc o5 thi chua co dau vet -> coi nhu DA XONG
    # (khong danh PB to doi luot nay), khong dung cho.
    statuses = {}
    for m in members:
        _mc = account_clients.get(m)
        _v = getattr(_mc, "_o5_da_xong", None) if _mc is not None else None
        if _v is not None:
            statuses[m] = bool(_v)
    _thieu = [m for m in members if m not in statuses]
    if _thieu:
        log.info("[%s] (LEADER) o5: %d/%d acc chua bao (%s) -> coi nhu DA XONG, khong danh PB to "
                 "doi luot nay (khong dung cho)", label, len(_thieu), len(members), _thieu)
        for m in _thieu:
            statuses[m] = True
    if all(not statuses.get(m, True) for m in members):       # MOI nguoi deu chua xong
        log.info("[%s] (LEADER) CA party (%d nguoi) chua xong o5 -> PHO BAN TO DOI LV20", label, len(members))
        with st["lock"]:
            st["o5_state"] = "running"   # member biet ma CHO, khong chay tiep
            st["o5_broke"] = False       # reset moi lan danh (co set True o finally neu co dis)
        # DIEU PHOI bat pha PB cho CA party: trong pha nay khong acc nao teleport ve thanh.
        # Truoc day moi acc tu om timer 600s luc accept loi moi -> PB vo thi khong ai ha, member
        # spam "dang vao pho ban -> ngung teleport" hang phut (p51/p53 07/09, 651 dong log).
        dat_pha_pho_ban(pidx, True)
        _dg0 = st["disc_gen"]            # CASE 3: theo doi co dong doi ROT trong luc danh khong
        try:
            ok = c.do_team_dungeon_lv20()
            if ok:
                # claim_daily_quests() claim hang/cot bingo (dung o5) TRUOC KHI goi hook nay (o5 la
                # buoc cuoi) -> luc claim hang/cot, o5 con dang tinh la CHUA xong -> bo lo claim
                # hang/cot/tong ket co dinh kem o5. Goi lai claim_daily_quests(heavy=False) SAU KHI
                # danh xong pho ban de claim bu (heavy=False -> KHONG lam lai o2/goi lai hook o5).
                c.claim_daily_quests(heavy=False)
            # PHONG THIEU NGUOI sau START (roster server < so bot moi - rule "du party moi danh"):
            # leader da HUY danh truoc khi ton luot -> ca party relogin gom lai roi LAM LAI.
            if getattr(c, "_td_incomplete", False):
                # THOAT INSTANCE bang C:047-010, KHONG relogin: tu khi server chan toc do dang nhap
                # (ma 90), relogin de dong bo PB lam acc ket vong login hang phut (party 6, 23:15).
                log.warning("[%s] (LEADER) phong pho ban THIEU nguoi -> thoat PB, gom lai danh lai", label)
                try: c.leave_team_dungeon()
                except Exception: pass
            # CASE 3: co dong doi ROT trong luc danh team dungeon -> leader cung RELOGIN thoat instance
            # (giong member) truoc khi ve flow. reform_gen (finally) + train reaction se gom lai sau.
            if st["disc_gen"] > _dg0 or st["reconnecting"]:
                log.warning("[%s] (LEADER) dong doi ROT trong team dungeon -> THOAT PB (C:047-010), "
                            "khong relogin", label)
                try: c.leave_team_dungeon()
                except Exception: pass
        finally:
            # PHA PB KET THUC (xong / thieu nguoi / co dis deu vay) -> tat cho CA party trong MOT
            # lenh. Khong con canh "leader ha co cua rieng no, member om timer 600s toi het han":
            # ca that 07/09, 651 dong "dang vao pho ban -> ngung teleport" - p53 leader thoat PB
            # luc 02:40:33 ma qv813/814/815 con spam toi 02:45:41 roi bi relogin hang loat;
            # p51 (mh212) ket y het.
            dat_pha_pho_ban(pidx, False)
            _clear_o5_client_flags(c)
            if not ok:
                # PB lv20 KHONG xong -> khong co goi ket thuc -> keo ca party ra bang lenh.
                # (Xong binh thuong thi moi acc tu ra khi nhan `S:047-012`, xem client._on_dungeon.)
                _thoat_pb_ca_party(pidx, "PB lv20 vỡ")
            with st["lock"]:
                # VO do co dis (chinh leader rot = not c.running, HOAC co member rot = disc_gen/
                # reconnecting): bao member -> CA party relogin thoat instance (trong dungeon KHONG
                # teleport ra duoc -> truoc day member spam go_to_town vo tan, xem log party xGAx).
                # `ok` = PB lv20 da danh xong -> rot sau do KHONG phai "chua xong", khong lam lai
                # (xem chu thich cung y o nhanh lv50/80/110 ben tren, ca that p42 07/09).
                if (not ok) and ((not c.running) or st["disc_gen"] > _dg0 or st["reconnecting"]
                                 or getattr(c, "_td_incomplete", False)):
                    st["o5_broke"] = True
                    st["o5_need_redo"] = True   # team dungeon CHUA xong -> reconnect xong lam LAI
                st["o5_state"] = "done"   # bao member (thanh cong hay fail deu THA member ra)
                # do_team_dungeon_lv20 tu goi leave_party() (giai tan party de vao pho ban) - DAY LA
                # PARTY CHUNG voi party train, nhung KHONG co gi bao cho vong lap chinh biet can lap
                # lai -> truoc day member out het, leader chay ra bai TRAIN MOT MINH (khong reform).
                # Bump reform_gen -> co che reform co san (_do_reform, dung cho cac truong hop
                # "bi dump khoi dungeon" khac) se tu dong keo ca party tap hop + lap lai.
    else:
        with st["lock"]:
            st["o5_state"] = "done"      # khong danh -> tha member ngay
        done_list = [m for m in members if statuses.get(m, False)]
        log.info("[%s] (LEADER) o5: KHONG phai ca party chua xong (da xong: %s) -> bo qua pho ban to doi",
                 label, done_list)


def _run_account_supervised(username, password, pidx, is_leader, is_picker=False):
    """Bọc run_account: SERVER ROT (server_closed) -> login lai (backoff 5s x3 -> 30s x10 -> 60s),
    VO HAN toi khi duoc (chi dung khi GUI Stop). Ap dung MOI party, ke ca "khong co chu PT" (truoc
    day khong leader la rot CHET luon -> dung yen trong DG con gio ma tu out).
    run_account bao lai qua account_reconnect[username]."""
    st = _pstate(pidx)
    stop_ev = account_stops.get(username)
    _st = lambda: stop_ev is not None and stop_ev.is_set()
    attempt = 0
    first = True
    while True:
        account_reconnect[username] = False
        _tiep = account_continue.pop(username, None)
        try:
            run_account(username, password, pidx, is_leader, is_picker, is_reconnect=not first,
                        reuse_client=_tiep)
        except ResyncSignal:
            # EP DONG BO: barrier sau da unwind ra day -> dong socket + coi nhu forced reconnect ->
            # relogin ngay (wait=1s) -> duong reconnect bam pha leader (clear sach state cu).
            cli = account_clients.get(username)
            if cli is not None:
                try: cli.close()
                except Exception: pass
            account_reconnect[username] = True
            account_forced_reconnect.add(username)
            account_forced_reconnect_reason[username] = "ép đồng bộ theo leader"
            log.warning("[%s] EP DONG BO -> relogin bam leader", username)
        except Exception:
            # LOI KHONG LUONG TRUOC -> truoc day luong CHET CAM: khong log, khong relogin, GUI van
            # xanh "CHAY". Acc chet giua chung nen KHONG kip vao st["reconnecting"] -> barrier
            # reform dem _n_arr + _n_rec KHONG BAO GIO du -> CA PARTY dung hinh vinh vien, chi in
            # "CHO ca party ve ... - THIEU: <acc>" moi 30s (bug that: party 38 ket 4h38').
            # Rule TOI THUONG la gom DU party -> phai CUU acc (relogin), TUYET DOI khong bo qua no.
            log.exception("[%s] LOI CHET LUONG (khong phai ResyncSignal) -> relogin de cuu party",
                          username)
            cli = account_clients.get(username)
            if cli is not None:
                try: cli.close()
                except Exception: pass
            # KHONG dat `forced`: forced = relogin 1s va BO QUA nhanh train_reform (dieu kien
            # `not forced`). Loi lap lai chac chan se thanh vong crash 1s/lan, va party cung khong
            # duoc bump reform_gen de gom lai. Luong chet thuc chat LA mot kieu rot -> di duong rot
            # binh thuong: co backoff 5s/30s/60s + disc_gen + reform_gen nhu moi lan mat ket noi.
            account_reconnect[username] = True
            account_forced_reconnect_reason[username] = "luồng lỗi bất ngờ"
        first = False
        if account_continue.get(username) is not None:
            # DOI PHA tai cho: KHONG dem la rot -> khong bump disc_gen, khong danh dau
            # st["reconnecting"] (dong doi se khong bao dong gia "dong doi ROT"), khong cho backoff.
            first = False
            continue
        if _st() or not account_reconnect.get(username):
            break   # GUI Stop / thoat binh thuong / khong reconnectable -> dung han
        forced = username in account_forced_reconnect
        account_forced_reconnect.discard(username)
        forced_reason = account_forced_reconnect_reason.pop(username, None)
        pcfg = (getattr(config, "PARTY_CONFIG", {}).get(pidx, {}) or {})
        ev = config.event_hom_nay(pcfg.get("event_key") or "")
        event_reset = (not forced and _is_party_event(
            pcfg.get("mode"), config.PARTY_LEADER_ACC.get(pidx) is not None, ev
        ) and st.get("event_battle_active", False))
        train_reform = (not forced and config.PARTY_LEADER_ACC.get(pidx) is not None
                        and _party_is_in_train_phase(pcfg, st))
        with st["lock"]:
            st["reconnecting"].add(username)
            if not forced:
                st["disc_gen"] += 1
            # (`train_reform` tinh o tren nhung KHONG con ai dung: acc mat ket noi roi login lai
            #  khong tu ra lenh cho ca party ve thanh nua - dieu phoi thay lech map/kenh va gom.)
            if event_reset:
                st["invited"].clear()
                st["event_battle_done"].clear()
        if event_reset:
            reset_party_joined(pidx)
        attempt += 1
        wait = 1 if forced else (5 if attempt <= 3 else (30 if attempt <= 13 else 60))
        # GIAN CACH TUNG ACC TRONG PARTY khi relogin HANG LOAT (ep dong bo theo leader): truoc day
        # ca 5 acc dung wait=1 -> 5 lenh dang nhap don trong ~1s -> server tra ma 90 "dang nhap qua
        # thuong xuyen" -> acc khong vao lai duoc hang phut, party train thieu nguoi.
        # Bug that (party 2, 18:17-18:21): "ep dong bo theo leader -> login lai sau 1s" cho ca party
        # -> 18:18:16 leader keo di khi roster DU 4/4 -> 18:18:23 con 3 -> 18:18:59 con 2.
        # Xep hang theo VI TRI acc trong party -> 1s, 4s, 7s, 10s, 13s.
        #
        # PHAI AP DUNG CA KHI SERVER DA LOAT (khong chi `forced`): luc do moi acc tu retry voi
        # `wait` GIONG HET NHAU (5s) -> ca party login trong ~6s -> dinh ma 90 y het.
        # Do tren party.log 31/08 (party 1): 6 lan ca party rot trong CUNG MOT GIAY (16:41:07 va
        # 17:45:48 la 4 acc, 17:55:30 la 3 acc - deu ma 61 cua server), va 2 chum ma 90 sau do
        # (15:09:36-42, 17:09:53-59) deu la 5 acc login lot trong 6 giay.
        # Dau hieu "server da loat" = dang co >=2 acc cua party trong `reconnecting`.
        # Buoc 8s (khong phai 3s nhu nhanh forced): 5 acc trong 6s DA dinh 90 roi, 3s van qua sat.
        # Trai ~37s, doi lai khong dinh 90 - ma dinh 90 la backoff `30 * attempt` (toi 300s) va
        # thuong dinh ca 5 acc.
        try:
            with st["lock"]:
                _dang_rot = len(st["reconnecting"])
        except Exception:
            _dang_rot = 0
        _gian_buoc = 3 if forced else (8 if _dang_rot >= 2 else 0)
        if _gian_buoc:
            try:
                _order = [u for u, _p, _l, _k in party_accounts(pidx)]
                _them = _gian_buoc * _order.index(username)
                if _them:
                    wait += _them
                    log.info("[%s] RECONNECT: relogin HANG LOAT (%s) -> gian them %ds cho rieng "
                             "acc nay (tranh ma 90)", username,
                             "ca party bi ep" if forced else "%d acc dang rot" % _dang_rot, _them)
            except ValueError:
                pass
        # SERVER CHAN TOC DO DANG NHAP (S:000-000 ma 90 "dang nhap qua thuong xuyen"): login lai
        # ngay chi lam server chan tiep -> VONG XOAY: dut -> login nhanh -> bi chan -> dut...
        # Do tren party.log 1 phien: 1232/1574 lan dut la ma 90 (78%). Nhung lan do backoff dang
        # la 1-5s. Voi ma nay phai CHO LAU, va cang thu nhieu cang phai cho lau hon.
        _cli_last = account_clients.get(username)
        _cause = int(getattr(_cli_last, "disconnect_cause", 0) or 0)
        _reason_extra = ""
        if _cause == DISCONNECT_RATE_LIMIT:
            wait = max(wait, min(30 * attempt, 300))
            _reason_extra = " [server chan toc do dang nhap -> gian nhip]"
        elif _cause:
            _reason_extra = " [%s]" % getattr(_cli_last, "disconnect_reason", "")
        log.warning("[%s] RECONNECT: %s%s -> login lai sau %ds (lan %d)", username,
                    forced_reason or ("bat buoc relogin ca party" if forced else "server rot"),
                    _reason_extra, wait, attempt)
        for _ in range(wait):
            if _st():
                break
            time.sleep(1)
        if _st():
            break
    st["reconnecting"].discard(username)
    if is_leader and account_threads.get(username) is threading.current_thread():
        st["leader_gone"].set()   # thoat that su (het reconnect) -> member thoat theo


def start_account(username, password, pidx, is_leader, is_picker):
    """Khoi dong 1 acc (thread). Neu thread cu con song (vd Stop xong Start LAI ngay de doi map/mode)
    -> BAO DUNG + CHO no chet han roi moi start thread MOI voi config MOI. Truoc day return False
    (bo qua) -> acc giu thread cu chay tiep config CU (bug: doi train map A->B nhung 1 so acc van
    tele ve thanh A' cu vi thread cu doc start_city_id=A tu luc dau, khong doc lai)."""
    t = account_threads.get(username)
    if t is not None and t.is_alive():
        ev = account_stops.get(username)
        if ev is not None:
            account_stop_reasons[username] = "start lai acc: dung thread cu truoc"
            ev.set()                     # bao thread cu dung
        t.join(timeout=12)               # cho chet han (go_to_town... co check stop -> thoat vai giay)
        if t.is_alive():
            log.warning("[%s] start_account: thread cu chua dung sau 12s -> bo qua start "
                        "(tranh 2 thread 1 acc)", username)
            return False
    account_stop_reasons.pop(username, None)
    st = _pstate(pidx)
    if is_leader:
        # Start party da clear leader_gone o dau, nhung neu leader thread CU chet muon sau do
        # (do start_account vua set stop_ev + join) thi finally cua thread cu co the set lai
        # leader_gone, lam member phien MOI vua vao party da thoat theo "chu party thoat".
        # Clear lai ngay truoc khi tao leader thread moi de cat stale signal do.
        st["leader_gone"].clear()
        st["leader_bad"].clear()
    # Start dau tien cua phien party moi: bo route con sot theo pidx tu lan chay/profile cu.
    # Supervisor reconnect khong di qua start_account nen route dang do van duoc tiep tuc.
    if not _active_party_usernames(pidx):
        _clear_stale_manual_route(st)
    # SO MEMBER CAN CHO. Mode KHONG CO VIEC LAP DOI (loan dau) thi con so nay la 0 - khong phai
    # "chan cho khoi moi", ma vi mode do THAT SU khong can cho ai: moi acc tu dang ky, tu ghep
    # tran. Dat dung o day thi MOI vong "chua du member -> moi lai / gom / reform" tu tat, khong
    # phai di vá tung cho.
    #
    # Ca that 10/09 party 19 (user: "p19 thay lap pt", "don gian mode loan dau thi di solo thoi ma
    # cung sai duoc"): dieu phoi da ra dung lenh
    #     21:44:18 [party 19] viec=lam - mode KHONG CAN LAP DOI (moi acc tu dang ky va tu danh)
    # ma leader van lap doi day 4/4 mot phut sau, roi:
    #     21:46:30 [quanmot] (LEADER) DU 4/4 member -> SET QS + ra train
    #     21:46:30 [quanmot] loi start training: cannot access local variable '_start_training'
    # - loan dau ma di duong train, va vap `UnboundLocalError` vi ham do chi duoc `def` tren duong
    # train. Goc cua ca chuoi: `n_members = 4` cho mot mode khong bao gio can 4 nguoi.
    st["n_members"] = (0 if not _mode_can_lap_doi(pidx)
                       else sum(1 for u, p, lead, _ in party_accounts(pidx) if not lead))
    # MODE digioi_train: party khoi dong LAI tu dau (chua acc nao chay) -> reset pha ve "digioi",
    # khong thi lan chay sau se bo qua DG (pha con ket o "train" tu phien truoc).
    if not _running_party_usernames(pidx):
        with st["lock"]:
            st["dt_phase"] = "digioi"
            st["dt_train_prepared"] = False
        # Khong con co "da xong DG" de xoa: dieu phoi doc thang dong ho server tung acc
        # (`_acc_het_gio_dg`), va `relogin()` da bo moc dong ho cu de cho server day lai.
    account_stops[username] = threading.Event()
    t = threading.Thread(target=_run_account_supervised, args=(username, password, pidx, is_leader, is_picker),
                         daemon=True)
    account_threads[username] = t
    _threads.append(t)
    t.start()
    return True


def setup_party_runtime(pidx, mode, server_ip, server_id, accounts,
                        city_flag=0, start_city_id=0, mob_index=-1, do_daily=True,
                        digioi_mode="party", event_key="", leaders=None, has_leader=True,
                        use_phuc_than=False, use_digioi_ho_phu=False,
                        fight_legion_boss=True, do_van_tieu=True,
                        buy_ho_phu=False, buy_bao_hop=False, bao_hop_xu_threshold=10000000,
                        di_gioi_level=2, auto_sell_noi_dat=True,
                        buy_hp=False, hp_qty=9999, hp_thresh=500000,
                        buy_sp=False, sp_qty=9999, sp_thresh=500000,
                        claim_offline_exp=True,
                        auto_team_dungeon=True, team_dungeons=None,
                        auto_buy_shop=None, buy_thien_chau=False,
                        auto_world_boss=True,
                        # THEM O CUOI: Kotlin goi THEO VI TRI (BotForegroundService.kt) nen
                        # chen vao giua se lam lech het cac tham so phia sau.
                        auto_bag_clean=True, auto_discard_junk=True,
                        auto_decompose_scrolls=False, scroll_modes=None,
                        auto_donate_materials=True, material_modes=None,
                        auto_event_exchange=False, event_exchange_items=None,
                        death_return_town=True, pet_death_return_town=True,
                        event_exchange_sig="",
                        train_pick="", mob_min=0, mob_max=0, mob_elements="",
                        di_gioi_pick="", loandau_mot_tran=False,
                        auto_bag_expand=False, bag_expand_gold=0,
                        # TU MO RUONG TRANG BI + TU CAT DO TIEN TRANG. THEM O CUOI CUNG
                        # (Kotlin goi THEO VI TRI - chen vao giua la lech het tham so phia sau).
                        # `cat_do_items` KHONG co o day: list cat la MOT file chung
                        # (cat_do_items.json), khong phai config theo party.
                        auto_open_boxes=False, box_modes=None, auto_cat_do=False,
                        # TU MO RONG TIEN TRANG. THEM O CUOI CUNG (Kotlin goi THEO VI TRI).
                        auto_bank_expand=False, bank_expand_gold=0):
    """ANDROID: Kotlin goi de POPULATE config cho 1 party luc runtime (thay vi doc accounts.json
    nhu PC). accounts = 1 CHUOI STRING duy nhat dang "u1\\x01p1\\x01battle_json\\x01heal_json\\x01u2..." (KHONG phai
    list/List<String> - da xac nhan qua logcat that: Chaquopy KHONG convert dung List<String>
    (ke ca da lam PHANG) thanh Python list khi truyen qua callAttr, "TypeError: 'ArrayList'
    object is not iterable" ngay tai list(accounts). String thi luon convert dung -> Kotlin join
    bang U+0001 (xem BotForegroundService.kt::startParty), o day tu split() lai. Goi XONG roi
    goi start_party(pidx). Cau truc PARTY_CONFIG/PARTIES/PARTY_LEADER_ACC GIONG HET
    config._load_accounts_json ban PC -> tu do run_party_digioi (coordinator CHUNG) chay y het PC."""
    pidx = int(pidx)
    if isinstance(team_dungeons, str):
        try:
            import json
            team_dungeons = json.loads(team_dungeons) if team_dungeons else None
        except Exception:
            team_dungeons = None
    config.PARTY_CONFIG[pidx] = {
        # TU CHON MAP TRAIN. mob_elements: Kotlin truyen CHUOI noi bang "," (khong truyen List -
        # R8 rut gon ten lop -> Chaquopy "TypeError: 't' object is not iterable").
        "train_pick": str(train_pick or ""),
        "di_gioi_pick": str(di_gioi_pick or ""),
        "mob_min": int(mob_min or train_pick_mod.DEFAULT_MOB_MIN),
        "mob_max": int(mob_max or train_pick_mod.DEFAULT_MOB_MAX),
        "mob_elements": ([int(x) for x in str(mob_elements).split(",") if x.strip().isdigit()]
                         or list(train_pick_mod.ALL_ELEMENTS)),
        "mode": mode, "start_city_id": int(start_city_id), "mob_index": int(mob_index),
        "city_flag": int(city_flag), "server": "", "server_ip": server_ip,
        "server_id": int(server_id), "do_daily": bool(do_daily),
        "claim_offline_exp": bool(claim_offline_exp),
        "auto_world_boss": bool(auto_world_boss),
        "auto_team_dungeon": bool(auto_team_dungeon),
        "team_dungeons": config.normalize_team_dungeons(team_dungeons),
        "digioi_mode": digioi_mode, "event_key": event_key or "",
        "loandau_mot_tran": bool(loandau_mot_tran),
        "auto_open_boxes": bool(auto_open_boxes),
        "box_modes": _map_cau_hinh(box_modes, gia_tri_bool=True),
        "auto_cat_do": bool(auto_cat_do),
        "auto_bag_expand": bool(auto_bag_expand),
        "bag_expand_gold": int(bag_expand_gold or 0),
        "auto_bank_expand": bool(auto_bank_expand),
        "bank_expand_gold": int(bank_expand_gold or 0),
        "use_phuc_than": bool(use_phuc_than), "use_digioi_ho_phu": bool(use_digioi_ho_phu),
        "fight_legion_boss": bool(fight_legion_boss),
        "do_van_tieu": bool(do_van_tieu),
        "auto_sell_noi_dat": bool(auto_sell_noi_dat),
        "death_return_town": bool(death_return_town),
        "pet_death_return_town": bool(pet_death_return_town),
        "auto_bag_clean": bool(auto_bag_clean),
        "auto_discard_junk": bool(auto_discard_junk),
        "auto_decompose_scrolls": bool(auto_decompose_scrolls),
        "scroll_modes": _map_cau_hinh(scroll_modes),
        "auto_donate_materials": bool(auto_donate_materials),
        "material_modes": _map_cau_hinh(material_modes),
        "auto_event_exchange": bool(auto_event_exchange),
        "event_exchange_sig": str(event_exchange_sig or ""),
        # APK truyen CHUOI noi bang "\n" (xem BotForegroundService.kt); PC truyen list.
        "event_exchange_items": ([x for x in event_exchange_items.split("\n") if x.strip()]
                                 if isinstance(event_exchange_items, str)
                                 else list(event_exchange_items or [])),
        "auto_buy_shop": bool(auto_buy_shop) if auto_buy_shop is not None else bool(buy_ho_phu or buy_thien_chau or buy_bao_hop),
        "shop_items": config.normalize_shop_items(None, {
            "ho_phu": bool(buy_ho_phu),
            "thien_chau": bool(buy_thien_chau),
            "bao_hop": bool(buy_bao_hop),
        }),
        "buy_ho_phu": bool(buy_ho_phu), "buy_thien_chau": bool(buy_thien_chau),
        "buy_bao_hop": bool(buy_bao_hop),
        "bao_hop_xu_threshold": int(bao_hop_xu_threshold),
        "di_gioi_level": int(di_gioi_level),
        "buy_hp": bool(buy_hp), "hp_qty": int(hp_qty), "hp_thresh": int(hp_thresh),
        "buy_sp": bool(buy_sp), "sp_qty": int(sp_qty), "sp_thresh": int(sp_thresh),
    }
    _flat = str(accounts).split("\x01") if accounts else []
    accs = []
    if len(_flat) >= 5 and len(_flat) % 5 == 0:
        # 5-tuple MOI (APK Kotlin+Python cung build -> nhat quan): u,p,battle,heal,furnace.
        import json
        for i in range(0, len(_flat) - 4, 5):
            u, p, battle_json, heal_json, furnace_json = _flat[i:i + 5]
            if not u:
                continue
            accs.append((u, p))
            try:
                bcfg = json.loads(battle_json) if battle_json else {}
                apply_account_battle(u, bcfg if isinstance(bcfg, dict) else {})
            except Exception:
                apply_account_battle(u, {})
            try:
                hcfg = json.loads(heal_json) if heal_json else {}
                apply_account_heal(u, hcfg if isinstance(hcfg, dict) else {})
            except Exception:
                apply_account_heal(u, {})
            try:
                fcfg = json.loads(furnace_json) if furnace_json else {}
                apply_account_furnace(u, fcfg if isinstance(fcfg, dict) else {})
            except Exception:
                apply_account_furnace(u, {})
    elif len(_flat) >= 4 and len(_flat) % 4 == 0:
        import json
        for i in range(0, len(_flat) - 3, 4):
            u, p, battle_json, heal_json = _flat[i], _flat[i + 1], _flat[i + 2], _flat[i + 3]
            if not u:
                continue
            accs.append((u, p))
            try:
                bcfg = json.loads(battle_json) if battle_json else {}
                apply_account_battle(u, bcfg if isinstance(bcfg, dict) else {})
            except Exception:
                apply_account_battle(u, {})
            try:
                hcfg = json.loads(heal_json) if heal_json else {}
                apply_account_heal(u, hcfg if isinstance(hcfg, dict) else {})
            except Exception:
                apply_account_heal(u, {})
    elif len(_flat) >= 3 and len(_flat) % 3 == 0:
        import json
        for i in range(0, len(_flat) - 2, 3):
            u, p, battle_json = _flat[i], _flat[i + 1], _flat[i + 2]
            if not u:
                continue
            accs.append((u, p))
            try:
                bcfg = json.loads(battle_json) if battle_json else {}
                if isinstance(bcfg, dict):
                    apply_account_battle(u, bcfg)
                else:
                    apply_account_battle(u, {})
            except Exception:
                apply_account_battle(u, {})
            apply_account_heal(u, {})
    else:
        accs = []
        for i in range(0, len(_flat) - 1, 2):
            if _flat[i]:
                accs.append((_flat[i], _flat[i + 1]))
                apply_account_battle(_flat[i], {})
                apply_account_heal(_flat[i], {})
    while len(config.PARTIES) <= pidx:
        config.PARTIES.append([])
    config.PARTIES[pidx] = accs
    if isinstance(leaders, str):
        import re
        leaders = [x.strip() for x in re.split(r"[\n,\r]+", leaders) if x.strip()]
    config.PARTY_LEADERS_BY_IDX[pidx] = list(leaders or [])
    if has_leader and accs:
        config.PARTY_LEADER_ACC[pidx] = accs[0][0]
    else:
        config.PARTY_LEADER_ACC.pop(pidx, None)
    config.ACCOUNTS = [a for party in config.PARTIES for a in party if a and a[0]]
    config.ACCOUNT_PARTY = {a[0]: i for i, party in enumerate(config.PARTIES)
                            for a in party if a and a[0]}
    # IN RA CAC TICK VUA NHAN - CHI APK di qua ham nay (ban PC doc thang `config.py`), nen day la
    # cua so DUY NHAT de biet dien thoai that su gui gi.
    #
    # Truoc 23/09 ham nay nhan xong ghi thang vao `PARTY_CONFIG` roi thoi, khong mot dong log.
    # User bao "khong tick danh boss QD ma no van danh" / "khong tick mua HP SP ma van di mua" ma
    # KHONG CACH NAO biet tick do co toi Python khong - phia Kotlin goi THEO VI TRI 58 doi so, phia
    # Python co 58 tham so, doi chieu tung cap thi khop, nhung "khop tren giay" khong phai bang
    # chung ve gia tri THAT luc chay.
    #
    # APK co man hinh log trong app nen user doc duoc dong nay ma khong can logcat.
    log.info(">>> PARTY %s SETUP: mode=%s | boss_QD=%s boss_TG=%s PB_doi=%s daily=%s van_tieu=%s "
             "| mua_HP=%s(%s/%s) mua_SP=%s(%s/%s) | phuc_than=%s ho_phu_DG=%s "
             "| doi_qua_event=%s(%d mon) mo_ruong=%s cat_do=%s ban_noi_dat=%s "
             "| don_tui=%s vut_rac=%s phan_giai_cuon=%s donate=%s | mua_shop=%s thien_chau=%s "
             "bao_hop=%s | mo_tui=%s mo_tien_trang=%s | chet_ve_thanh=%s pet_chet_ve_thanh=%s",
             pidx + 1, mode,
             bool(fight_legion_boss), bool(auto_world_boss), bool(auto_team_dungeon),
             bool(do_daily), bool(do_van_tieu),
             bool(buy_hp), hp_qty, hp_thresh, bool(buy_sp), sp_qty, sp_thresh,
             bool(use_phuc_than), bool(use_digioi_ho_phu),
             bool(auto_event_exchange),
             len(config.PARTY_CONFIG[pidx].get("event_exchange_items") or ()),
             bool(auto_open_boxes), bool(auto_cat_do), bool(auto_sell_noi_dat),
             bool(auto_bag_clean), bool(auto_discard_junk), bool(auto_decompose_scrolls),
             bool(auto_donate_materials),
             auto_buy_shop, bool(buy_thien_chau), bool(buy_bao_hop),
             bool(auto_bag_expand), bool(auto_bank_expand),
             bool(death_return_town), bool(pet_death_return_town))


def party_idx_of(username):
    """pidx cua account (de map lenh thu cong username -> pidx). None neu khong biet."""
    return getattr(config, "ACCOUNT_PARTY", {}).get(username)


def _start_party_accounts(pidx, accounts, generation, stagger, skip_running):
    """Khoi dong tung acc cua party. Tach rieng de goi duoc CA khi KHONG reset state chung."""
    started = 0
    for u, p, is_leader, is_picker in accounts:
        if generation != _start_cancel_generation:
            log.info(">>> PARTY %s: huy khoi dong cac acc con lai do STOP TAT CA", pidx + 1)
            break
        if skip_running and is_account_running(u):
            continue      # START TAT CA: acc dang chay -> de yen, khong dung roi chay lai
        account_exit_reason.pop(u, None)   # xoa ly do cu
        if start_account(u, p, pidx, is_leader, is_picker):
            started += 1
            time.sleep(stagger)
    return started


def _tim_server_moi_nen():
    """TU PHAT HIEN SERVER MOI tu CDN tai nguyen cua game (chay NEN, chi mot lan moi phien).

    Ban PC goi som hon o `gui.py` (de ve lai dropdown ngay); day la cho cho ban APK - khong co noi
    nao khac chay Python luc mo app. `cap_nhat_nen` co guard nen goi hai lan cung chi hoi mot lan.

    CDN CO SERVER MOI TRUOC CA KHI SERVER GAME MO LAI (user 17/09: "dang bao tri de mo server moi,
    server chua mo lai nhung client thay update roi").

    DE RIENG MOT HAM, khong viet thang trong `start_party`: cau `import` trong do bi
    `tools/sync_apk_python.py` doi dang cho ban APK (`from bot import` -> `from . import`), ma
    `tests/test_party_restart.py` so AST cua `start_party` giua hai ban - lech mot node la do.
    """
    try:
        from . import servers_cdn as _scdn
        _scdn.cap_nhat_nen(config.SERVERS, config._base_dir())
    except Exception as _e:
        log.debug("khong hoi duoc server moi tu CDN: %s", _e)


def start_party(pidx, stagger=1.5, skip_running=False):
    """Khoi dong tat ca acc trong 1 party.

    skip_running=True (START TAT CA goi): acc DANG CHAY thi BO QUA, khong dung-roi-chay-lai.
    Mac dinh False cho nut "Start party" rieng: van restart de ap config moi (doi map/mode).
    """
    generation = _start_cancel_generation
    started = 0
    accounts = party_accounts(pidx)
    # TRUOC MOI THU: dam bao luong dieu phoi CHUNG con song. Dat o day (khong phai duoi nhanh
    # `if started`) vi nhanh `not _fresh` THOAT SOM - do la ly do party 53 chay khong co dieu
    # phoi suot 16 phut (06/09). Xem bao_dam_dieu_phoi.
    # TU PHAT HIEN SERVER MOI tu CDN tai nguyen cua game (chay NEN, chi mot lan moi phien).
    #
    # Dat o day de CA HAI ban cung chay: ban PC goi som hon o `gui.py` (de ve lai dropdown ngay),
    # con APK khong co cho nao khac chay Python luc mo app. `cap_nhat_nen` co guard nen goi hai
    # lan cung chi hoi CDN mot lan.
    #
    # CDN CO SERVER MOI TRUOC CA KHI SERVER GAME MO LAI (user 17/09: "dang bao tri de mo server
    # moi, server chua mo lai nhung client thay update roi").
    _tim_server_moi_nen()
    # Party da tat han -> tao session state MOI. Reset tung field nhu truoc de sot route_plan/
    # reform_gen cua map cu, member co the doc plan cu truoc khi leader ghi plan map moi.
    _fresh = not any(is_account_running(u) for u, *_ in accounts)   # party bat dau PHIEN MOI
    if _fresh:
        _party_state.pop(pidx, None)
        reset_party_joined(pidx)
        for u, *_ in accounts:
            account_forced_reconnect.discard(u)
            account_forced_reconnect_reason.pop(u, None)
    st = _pstate(pidx)
    # RESET state dung chung (tranh sot tu lan chay truoc: leader_bad cu -> member quit oan).
    # CHI khi party bat dau phien MOI. Party dang co acc CHAY (START TAT CA them acc con thieu,
    # hoac start lai 1 acc) ma xoa channel/team_dungeon_state/dailies_done... la PHA acc dang chay:
    # chung dang dua vao chinh nhung state do de phoi hop voi nhau.
    if not _fresh:
        return _start_party_accounts(pidx, accounts, generation, stagger, skip_running)
    for k in ("leader_ok", "leader_bad", "leader_gone", "invited", "channel_ready",
              "stop_leader_done", "route_party_ready", "route_done", "rally_ready",
              "path_done",
              # EVENT: "da thua/da xong" chi tinh trong mot phien -> phien moi phai danh lai.
              "go_claim", "event_battle_done"):
        st[k].clear()
    st["mob_spot"] = None
    st["rally_point"] = None
    st["mob_path"] = None
    st["channel"] = None
    with st["lock"]:
        st["started_train"] = 0
        st["dungeon_done"] = 0
        st["dailies_done"] = 0       # barrier: so acc da xong daily quest login (cho leader cho)
        st["team_dungeon_state"] = {}
        st["team_dungeon_broke"] = {}
        st["team_dungeon_need_redo"] = False
        st["summary_done"] = False   # cho phep log lai dong tong ket o lan chay nay
    started += _start_party_accounts(pidx, accounts, generation, stagger, skip_running)
    return started


# ===================== DIEU PHOI PARTY: BOT QUYET DINH =====================
# Rule user chot 05/09: "bo me cai leader quyet dinh party lam gi di, BOT la nguoi quyet dinh".
#
# VI SAO PHAI DOI: truoc day khong he co ai dieu phoi. 5 luong acc TU THUONG LUONG voi nhau qua
# mot dong co dung chung trong `st[...]` (leader_ok, channel_ready, ready_members, dt_done,
# invited, route_done...), va luong cua acc leader tinh co om nhieu quyet dinh nhat nen thanh
# "nguoi chi huy" - nhung no cung chi la mot luong dang ban login/danh/di duong nhu 4 dua kia.
# He qua tat yeu: LUONG NAO ROI VAO MOT VONG KHONG DOC DUNG CO LA CA PARTY CHET.
#
# Da xay ra that (party 19, 05/09, ket 2 GIO 42 PHUT):
#   14:05:29  4 member xong DG -> dung o 12001 cho leader bao "xong DG"
#   14:39:45  leader roi vao vong moi party tran (run_party_digioi.py:5781 cu) - vong do KHONG
#             doc gio DG, KHONG doc reform_gen, KHONG goi _resync_ck
#   ~14:59    het gio DG cua leader - KHONG AI KIEM -> khong bao gio bao "xong DG"
#   15:00:32  server da leader ve thanh 12003, member o 12001 -> leader in "lech map live
#             12001!=12003" 488 LAN roi thoi, khong lam gi
# Ep dong bo cung KHONG pha duoc vi chinh vong do khong doc sync_epoch/reform_gen.
#
# CACH LAM MOI: mot luong DIEU PHOI cho moi party. No NHIN THAY TOAN BO (ca 5 client trong
# `account_clients`: map, kenh, gio DG, dang danh khong) nen KHONG CAN barrier, KHONG CAN Event,
# KHONG CHO AI. Moi nhip no doc trang thai that roi ghi ra MOT KE HOACH; luong acc chi doc ke
# hoach ma thi hanh.
#
# Tinh chat quan trong: DEADLOCK BIEN MAT VE MAT CAU TRUC, khong phai nho va them loi thoat.
# Vi khong con cho cheo - chi co MOT cho quyet, va cho do khong bao gio cho ai.
# Bao nhieu VONG lien tiep khong vao duoc map event thi ngung han (moi vong da tu thu 5 lan).
# Luoi do cuoi cung cho event KHONG khai bao `lich` - event co lich thi da bi chan tu truoc.
EV_VAO_HONG_TOI_DA = 3

KE_HOACH_NHIP = 2.0        # nhip dieu phoi (giay). Nhanh hon watcher cu (20s) vi no ra LENH.
# Do dac 13/09 (250 acc / 50 party): quet mot vong ton 16ms, tuc 0.33ms moi party. Nen hai nguong
# duoi day KHONG phai de canh so party - chung de bat luc luong dieu phoi BI DOI CPU (GIL) hoac
# co party keo dai vong quet. Tre bao nhieu giay = ca bot mu bay nhieu giay.
DIEU_PHOI_TRE_CANH_BAO_SEC = 3.0   # nhip cach nhau qua (2s + 3s) -> khong con la dao dong binh thuong
DIEU_PHOI_QUET_LAU_SEC = 1.0       # 1 vong quet > 1s = gap 60 lan muc do dac duoc
# Party lech map/kenh LIEN TUC bao lau thi moi ra lenh GOM. Phai du dai de bao het MOT chuyen
# teleport gom (ve thanh trung gian -> thanh tap ket, tung acc lech nhip vai chuc giay): trong
# luc do lech map la BINH THUONG, ra lenh gom luc do la huy chinh viec dang lam.
KE_HOACH_LECH_MAP_SEC = 60
# LECH MAP co an han RIENG va NGAN hon lech kenh. "Khac map thi gom map" (user 09/09) - an han o
# day chi de bo qua vai giay teleport chuyen tiep, khong phai de cho acc lam xong viec rieng.
# 60 giay la han cua mot CHUYEN GOM dang chay (ve thanh trung gian -> thanh tap ket); dung no lam
# han PHAT HIEN lech thi party lech ca phut van chua duoc ra lenh.
LECH_MAP_AN_HAN_SEC = 12
# Het lech phai GIU duoc bay lau thi dong ho lech moi duoc go. Truoc day chi can MOT nhip thay
# cung map la dong ho reset ve 0 -> lech ngat quang khong bao gio dat han, tuc khong bao gio gom.
HET_LECH_CHAC_SEC = 8
KE_HOACH_DUNG_HINH_SEC = 240   # party DU nguoi, CUNG map/kenh ma khong nhuc nhich -> ket, phai pha
def _dang_danh(c):
    try:
        return bool(getattr(getattr(c, "state", None), "in_battle", False))
    except Exception:
        return False


def _dau_vet_acc(c):
    """DAU VET tien do cua MOT acc: (map, vi tri, the he tran). Doc thang client, khong ai bao cao.

    THE HE TRAN la phan bat buoc, khong phai cho co: DANH TAI CHO cung la tien do.

    Ban cu chi do (map, pos) nen coi "dung yen" = "khong lam gi". Trong Di Gioi do la phep do SAI:
    bot dung dung mot cho ban Phuc Than, danh xong lai cho con sau - map/pos KHONG BAO GIO doi.
    `_dang_danh` chi che duoc luc DANG trong tran; nghi giua hai tran vai chuc giay la dong ho chay
    tiep, 240s sau ca party bi ket luan DUNG HINH va bi `resync_gen` (= dap doi de sync kenh).

    `battle_tracker.generation` tang moi lan vao tran moi -> danh duoc tran nao la dau vet doi.
    Party dang ban ban quai vi the khong con bi ket luan la treo.
    """
    _bt = getattr(c, "battle_tracker", None)
    return (int(getattr(c, "current_map", 0) or 0),
            tuple(getattr(c, "pos", ()) or ()),
            int(getattr(_bt, "generation", 0) or 0))


def _acc_dung_hinh(st, song, han):
    """[username] cac acc KHONG nhuc nhich qua `han` giay. Tra rong = van dang chay.

    Do TUNG ACC chu khong do ca party. Ban dau ham nay do ca party (mot dau vet chung): chi can MOT
    acc dong day la coi nhu "party co tien do" -> lot luoi dung cai can bat.
    Ca that 07/09 party 23 (33 phut): leader dang DANH THAT (BATTLE ACK lien tuc) trong khi 4 member
    dung im cho no - dau vet chung doi moi nhip, dieu phoi khong thay gi bat thuong.

    Acc DANG DANH khong tinh: trong mot tran, map/vi tri dung yen la binh thuong (co tran dai vai
    phut). Acc dang relogin cung khong tinh - no khong nam trong `song`."""
    moc = st.setdefault("nhip_acc", {})
    now = time.time()
    ket = []
    _con = set()
    for u, c in song:
        _con.add(u)
        if _dang_danh(c):          # dang danh = dang lam viec -> tinh lai tu dau
            moc[u] = (None, now)
            continue
        _vet = _dau_vet_acc(c)
        _cu = moc.get(u)
        if _cu is None or _cu[0] != _vet:
            moc[u] = (_vet, now)
        elif now - _cu[1] > han:
            ket.append(u)
    for u in [u for u in moc if u not in _con]:   # acc da tat/rot -> bo moc cu
        moc.pop(u, None)
    return ket
# Hai lan dieu phoi ra lenh GOM phai cach nhau it nhat bay nhieu giay. Moi lenh gom ABORT moi acc
# dang di duong, nen ra lien tuc = ca party khong bao gio di xong buoc nao (party 17, 05/09).
KE_HOACH_GOM_COOLDOWN = 180.0
# Leader khong cong bo duong di sau bay nhieu giay -> MEMBER TU LAP. Duong di la cua PARTY, khong
# phai dac quyen leader. 20s = du cho leader binh thuong (no lap duong ngay khi vao _do_reform),
# ma khong de ca party dung 3 phut nhu party 10 (05/09 18:22-18:23).
ROUTE_PLAN_TIEP_QUAN_SEC = 20.0

# `viec` = ca party dang phai lam gi. Luong acc doc cai nay thay vi tu suy.
VIEC_LAM = "lam"      # ai vao viec nay: danh/train/DG binh thuong
VIEC_GOM = "gom"      # dang lech map/kenh -> GOM VE THANH roi keo lai (chi ngoai DG)
VIEC_MOI = "moi"      # da cung map+kenh -> leader gui loi moi, member nhan
# TRONG DI GIOI: lech kenh thi phai DONG BO TAI CHO (giai tan + sync kenh + moi lai), TUYET DOI
# khong "gom ve thanh" - tu DG ra thanh la phai DI BO RA CONG, tuc loi ca party ra khoi DG.
VIEC_DONG_BO = "dong_bo"
# CHUOI LENH DI TRAIN (user chot 11/09): "gom map -> gom kenh -> du pt thi ra lenh leader di den
# map train, toi safe gan diem duoc chon -> ra lenh leader chay ra diem quai -> trong qua trinh nay
# dieu phoi thay lech map lech kenh thi ra lenh gom lai".
#
# Truoc do hai buoc cuoi KHONG PHAI la lenh: leader tu quyet bang dong ho rieng (`last_retry >= 60`),
# so bot tu nho (`joined_member_count`) va vi tri cua rieng no. Nen no bo di ra bai ngay giua lenh
# gom (party 10, 11/09: member di gom, leader "DU 4/4 member ma KHONG DANH -> RA DIEM QUAI").
VIEC_DI_TRAIN = "di_train"   # du doi, cung map+kenh, nhung CHUA o map train -> leader keo ca party di
VIEC_RA_QUAI = "ra_quai"     # da o map train nhung leader con dung o safe -> ra diem quai roi danh


def _viec_di_train(pidx, st, song, pha):
    """DU DOI + CUNG MAP/KENH roi thi phai lam gi tiep -> (viec, ly_do).

    Hai buoc cuoi cua chuoi lenh user chot 11/09. Dieu phoi doc THANG trang thai that cua ca party
    (map hien tai, vi tri leader) - khong acc nao bao cao, khong dung so bot tu nho.

        chua o map train        -> VIEC_DI_TRAIN  (leader keo ca party di)
        o map train, con o safe -> VIEC_RA_QUAI   (leader ra diem quai roi danh)
        da o diem quai          -> VIEC_LAM       (cu danh)

    Chi ap cho pha TRAIN. DG/event co duong rieng (chay long vong / dung tang) nen giu `VIEC_LAM`.
    """
    if pha != "train":
        return VIEC_LAM, ""
    _dich = _map_train_dich(pidx, st)
    if not _dich:
        return VIEC_LAM, ""        # chua ai biet map train dich -> chua ra lenh duoc
    _ngoai = sorted({int(getattr(c, "current_map", 0) or 0) for _u, c in song
                     if getattr(c, "current_map", None)} - {_dich})
    if _ngoai:
        return VIEC_DI_TRAIN, "du doi, cung map/kenh -> DI TRAIN map %d (con o %s)" % (_dich, _ngoai)
    _spot = st.get("mob_spot")
    if _spot:
        _xa = [u for u, c in song
               if getattr(c, "pos", None) and _xa_diem_quai(c.pos, _spot)]
        if _xa:
            return VIEC_RA_QUAI, "da o map train %d -> RA DIEM QUAI %s (%s con o safe)" % (
                _dich, tuple(_spot), ", ".join(sorted(_xa)))
    return VIEC_LAM, ""


def _ke_hoach(st):
    """Ke hoach hien tai cua party (dict) hoac None neu dieu phoi chua chay lan nao."""
    with st["lock"]:
        kh = st.get("ke_hoach")
        return dict(kh) if kh else None


def _ke_hoach_gen(st):
    kh = _ke_hoach(st)
    return int(kh.get("gen", 0)) if kh else 0


def _ghi_ke_hoach(st, pidx, moi, ly_do=""):
    """Ghi ke hoach moi. Chi tang `gen` khi NOI DUNG doi -> luong acc dang thi hanh khong bi
    giat lai moi 2 giay. Tra True neu co doi."""
    with st["lock"]:
        cu = st.get("ke_hoach") or {}
        cung = all(cu.get(k) == moi.get(k) for k in ("pha", "map", "kenh", "thanh", "viec"))
        if cung and cu:
            return False
        moi = dict(moi)
        moi["gen"] = int(cu.get("gen", 0)) + 1
        moi["luc"] = time.time()
        moi["ly_do"] = ly_do
        st["ke_hoach"] = moi
    log.info("[party %d] DIEU PHOI gen %d: pha=%s map=%s kenh=%s viec=%s%s",
             pidx + 1, moi["gen"], moi.get("pha"), moi.get("map"), moi.get("kenh"),
             moi.get("viec"), (" - " + ly_do) if ly_do else "")
    _log_trang_thai(st, pidx)
    return True


def _log_trang_thai(st, pidx):
    """MOT DONG du de dung lai ca canh - in kem moi lan lenh doi.

    Truoc day muon biet "luc do party dang the nao" phai ghep 4-5 lenh grep khac nhau (log dieu
    phoi + log tung acc + roster + pha), va moi lan user bao loi la mat ca chuc phut mo nguoc.
    Cac con so o day deu la thu DIEU PHOI VUA DUNG DE QUYET - in ra de doc lai duoc quyet dinh.

    Dang:
      [party N] TRANG THAI: acc=<ten>@<map>/k<kenh><co> ... | roster leader=x/y | reform g=A thoa=B
      <co>:  ! = dang danh   * = dang lam viec le (boss QD / viec vat)
    """
    try:
        song = _acc_song(pidx)
        if not song:
            return
        _leader = config.PARTY_LEADER_ACC.get(pidx)
        _le = set(_ai_dang_lam_viec_le(song))
        _o = []
        _ros_leader = None
        for _u, c in song:
            try:
                _m = getattr(c, "current_map", None)
                _k = getattr(c, "current_channel", None)
                _n = len(getattr(c, "party_members", None) or ())
                _co = "!" if getattr(getattr(c, "state", None), "in_battle", False) else ""
                if _u in _le:
                    _co += "*"
                if _u == _leader:
                    _ros_leader = _n
                    _co += "(L)"
                _o.append("%s@%s/k%s%s" % (getattr(c, "_label", _u), _m, _k, _co))
            except Exception:
                continue
        log.info("[party %d] TRANG THAI: %s | roster leader=%s/%s | reform g=%s thoa=%s",
                 pidx + 1, " ".join(_o),
                 _ros_leader if _ros_leader is not None else "?", len(song) - 1,
                 st.get("reform_gen", 0), st.get("reform_gen_thoa", 0))
    except Exception as e:
        log.debug("[party %d] log trang thai loi (bo qua): %s", pidx + 1, e)


def _danh_dau_training(st, ok):
    """Ghi `st["training_started"]` cho luat watcher "party thieu nguoi qua lau" doc duoc.

    KHOA NAY TRUOC 05/09 KHONG AI GHI: grep ca file chi ra DUNG MOT dong, va la dong DOC
    (`if _can and _co < _can and st.get("training_started")`). `st.get(...)` luon tra None ->
    luat do chua tung chay lan nao (dem trong log ca ngay: THIEU NGUOI 0 lan, trong khi luat
    DEADLOCK chay 2227 lan). Bien `training_started` cung ten o `run_account` la bien LOCAL cua
    tung luong acc, khong lien quan gi toi `st[...]` cua party.
    """
    if ok:
        with st["lock"]:
            st["training_started"] = True
    return ok


def _acc_song(pidx):
    """[(username, client)] cua acc DANG CHAY va DA co client. Nen tang cua moi quyet dinh:
    dieu phoi doc THANG client, khong doc bao cao do chinh luong acc tu ghi (bao cao co the
    dong bang khi luong do ket - dung cai bay da lam party 19 chet)."""
    ra = []
    for u, _p, _l, _k in party_accounts(pidx):
        ev = account_stops.get(u)
        if ev is not None and ev.is_set():
            continue
        c = account_clients.get(u)
        if c is not None and getattr(c, "running", False):
            ra.append((u, c))
    return ra


def _het_gio_dg(c):
    """Acc nay HET GIO Di Gioi chua - DIEU PHOI tu ket luan, khong doi acc tu bao.

    Day la diem mau chot cua party 19: co `dt_done` nhung no do CHINH LUONG ACC ghi, ma luong do
    dang ket trong vong moi party -> khong bao gio ghi -> 4 dua kia cho mai. Dieu phoi doc thang
    dong ho nen luong acc co ket cung khong giau duoc.
    """
    try:
        con = DIGIOI_LIMIT - c.digioi_minutes_live()
    except Exception:
        return False
    if con <= 0:
        return True
    # Ra NGOAI map DG ma dong ho server cung gan het = het gio that (dong ho noi bo dung yen khi
    # o ngoai DG nen khong bao gio tu ve 0 - xem client.digioi_minutes_live).
    ngoai = (getattr(c, "current_map", None) is not None
             and c.current_map != config.DIGIOI_MAP_ID)
    if ngoai and con < 2:
        return True
    return False


def _tinh_hinh_doi(song):
    """Mo ta doi theo ROSTER SERVER cua tung acc: 'a=4 b=4 c=0'."""
    return " ".join("%s=%d" % (u, len(getattr(c, "party_members", None) or ()))
                    for u, c in sorted(song, key=lambda x: x[0]))


def _leader_dang_rot(pidx, song):
    """LEADER khong con trong danh sach acc song = no dang relogin -> DOI DA TAN, chac chan.

    User chot 07/09: "khi thang leader dis va o trang thai dang login thi chac chan tat ca deu ko
    co party, server tu giai tan party roi". Doi truong roi khoi the gioi thi server thao doi -
    khong con gi de giu.

    Bot khong the trong vao roster de biet dieu do: cac member CON SONG chi nhan duoc `0x0d` khi
    server chiu gui, va trong luc leader chua vao lai thi roster cua ho co the con giu so cu. Nen
    day la mot ket luan SUY RA TU SU KIEN, khong phai tu so dem."""
    if not song:
        return False
    _song_u = {u for u, _c in song}
    for _t in party_accounts(pidx):
        if len(_t) > 2 and _t[2] and _t[0] not in _song_u:   # _t[2] = is_leader
            return True
    return False


DOI_KENH_BIEN_DONG_SEC = 25.0   # sau khi mot acc doi kenh, roster ca party con bien dong bay lau


def _dang_doi_kenh(song):
    """CO acc nao dang do viec doi kenh khong - luc do roster KHONG DANG TIN.

    Doi kenh phai roi doi truoc (luat `Team.IsAlone`), ma DOI TRUONG roi la server giai tan ca doi.
    Nen ngay sau mot lenh doi kenh: acc do co roster 0, cac acc khac con giu SO CU chua kip cap
    nhat - ca hai deu khong phai su that. Ket luan "thieu party" luc nay la ket luan tren hau qua
    cua chinh lenh minh vua ra.

    User chot 07/09: "truoc khi bao lap lai pt thi phai thay la ko du pt thi moi lap lai chu".

    "DANG DO" = DA GUI LENH MA CHUA CO KET QUA. Khong phai "vua gui lenh trong N giay".

    `switch_channel` luon ket thuc bang MOT ket qua ro rang - `S:007-002` ma 0/1/2/3/4, hoac
    TIMEOUT - va ghi vao `_chan_switch_result` + `_chan_switch_luc`. Ban cu chi doc `_doi_kenh_tu`
    (moc BAT DAU) roi coi la "dang bay" trong tron 25 giay, ke ca khi server DA tra loi tu giay
    dau. Acc bi tu choi se thu lai lien tuc -> moc do luon moi -> "luc nao cung dang doi kenh".

    User 08/09: "giu nguyen dich cai lon me may, moi lan doi kenh phai duoc thanh cong hay fail va
    vi sao fail chu". Dung: co ket qua roi thi PHAI XU LY theo ma do (ma 2/4 -> so den, ma 3 -> ca
    party roi doi, ma 0/1 -> xong), khong duoc treo lo lung."""
    _bay = time.time()
    for _u, _c in song:
        _tu = float(getattr(_c, "_doi_kenh_tu", 0.0) or 0.0)
        if not _tu or _bay - _tu >= DOI_KENH_BIEN_DONG_SEC:
            continue
        # DA CO ket qua cho chinh lan doi nay -> lenh XONG, khong con "dang do".
        _luc = float(getattr(_c, "_chan_switch_luc", 0.0) or 0.0)
        if getattr(_c, "_chan_switch_result", None) is not None and _luc >= _tu:
            continue
        return True
    return False


# Roster vua tang trong bay nhieu giay = party DANG DUOC LAP, chua duoc dap di lap lai.
DOI_DANG_LAP_SEC = 25.0


def _doi_dang_lap(st, song):
    """Party co DANG DUOC LAP DO DANG khong (roster vua tang trong `DOI_DANG_LAP_SEC` giay).

    `_thieu_doi` chi tra loi "du chua". Do la cau hoi SAI o nhanh ra lenh lap lai party: mot party
    dang moi tung nguoi thi LUC NAO cung "chua du", nen no bi dap dung luc sap xong.

    Ca that party 3, 11/09 (user: "t bao xem truoc do co ma, doan dang di ra map train ay"):
        08:43:30 [party 3] REFORM gen -> 25 - chung kenh roi ma doi khong du -> lap lai party
        08:43:30 [party 3] DOI chua du (sga005=4 sga007=4 sga008=2 sga009=3 sga010=1)
    Bon con so do la roster DANG LEN (4,4,2,3,1) - leader moi duoc gan het doi thi bi giai tan.
    Sau do moi den man di train -> lech map -> gom -> ve thanh -> lap lai... Party 19, 6, 7, 24
    deu chet o dung cho nay.

    Do TONG roster ca party: no chi tang khi co nguoi THAT SU vao doi, va tut ve 0 khi doi tan -
    tuc phan biet duoc "dang moi" voi "dung im khong ai vao".
    """
    _tong = 0
    for _u, c in song:
        try:
            _tong += len(getattr(c, "party_members", None) or ())
        except Exception:
            pass
    _cu, _luc = st.get("roster_tong", (0, 0.0))
    if _tong > _cu:
        st["roster_tong"] = (_tong, time.time())
        return True
    if _tong < _cu:
        st["roster_tong"] = (_tong, 0.0)     # doi tut/tan -> khong con la "dang lap"
        return False
    return bool(_luc) and time.time() - float(_luc) < DOI_DANG_LAP_SEC


# Viec LE hop le: KHONG duoc keo acc dang lam do vao party roi loi di.
#   boss_qd     - boss Quan Doan la instance SOLO, BAT BUOC roi party moi vao duoc
#   login_chore - viec vat luc login (qua, van tieu, shop, thu cuoi...). User 14/09: "dang lam may
#                 cai viec vat do ko vao pt la dung, dang lam do ma vao pt roi bi keo di luon thi
#                 no hong viec vat".
# Trung `_PHASE_SOLO` cua watcher - cung mot khai niem.
VIEC_LE_HOP_LE = ("boss_qd", "login_chore")

def _ai_dang_lam_viec_le(song):
    """Acc dang lam viec LE - CHI DE IN LOG (`_log_trang_thai` danh dau `*`). KHONG quyet dinh gi.

    DIEU PHOI KHONG DUOC CHO AI CA, va cung khong can:

        leader cu MOI lien tuc
        acc dang viec vat GIU LOI MOI lai (`_pending_party_invites`), xong viec thi nhan
        neu doi dang THIEU, loi moi tu acc cung party duoc NHAN NGAY (L0 - xem `_on_party_invite`)

    Tuc chuyen "dang lam do thi chua vao party" DA duoc giai o tang acc tu truoc, dung cach: khong
    ai bi keo di giua chung, ma party van hinh thanh.

    T tung them mot bac chan o dieu phoi de lam lai chinh viec nay ("thieu nguoi vi co acc dang lam
    viec le -> CHO, khong gom"). Hau qua: viec vat thi acc nao cung lam lien tuc, nen LUC NAO cung
    co nguoi ban -> dieu phoi khong bao gio ra lenh -> ca party dung o thanh voi roster 0/4.
    Ca that 14/09 (user: "bon no lai ket o thanh deo di dau kia") - 204 lan:
        14:25:30 [party 36] gen 6: viec=lam - doi thieu nguoi vi ['taot12','taot13','taot14',
                                   'taot15'] dang lam viec LE hop le -> CHO, khong gom
        14:26:52 [party 24] TRANG THAI: daimot@12001/k2! ... | roster leader=0/4
    Va dat han cho cung khong cuu duoc: het han thi hoac keo acc di (hong viec vat) hoac cho tiep
    (ket o thanh) - ca hai deu sai. Cach dung la KHONG CHO, vi tang acc da lo roi.
    """
    out = []
    for _u, _c in song:
        try:
            d = get_account_task(_u)
        except Exception:
            continue
        if d and d.get("phase") in VIEC_LE_HOP_LE:
            out.append(_u)
    return out


# Goi roster `0x0d` toi nam acc KHONG cung luc. Bay nhieu giay la thua de no lan het.
ROSTER_LAN_SEC = 30.0


def _roster_dang_lan(st, song):
    """Cac ban sao roster CHUA NHAT TRI - tuc goi `0x0d` chua toi du moi acc.

    Roster tren SERVER la MOT su that duy nhat; `c.party_members` cua nam acc chi la nam ban sao,
    va chung toi KHONG CUNG LUC. `_thieu_doi` lay ban sao CHAM NHAT lam chuan (mot acc thieu la ket
    luan "doi chua du"), nen doi VUA DU van bi doc thanh "doi hong" trong vai giay dau.

    Day khong phai chuyen nho: ket luan do sinh ra lenh LAP LAI PARTY, ma lenh do bat leader
    `leave_party()` - tuc PHA DUNG CAI DOI VUA HINH THANH.

    Ca that party 17, 14/09 (user: 'thay log "chua ra bai, dieu phoi ra lenh moi" la sao'):
        11:49:21 [party 17] LAP LAI PARTY (chu706=4 chu707=3 chu708=4 chu709=2 chu710=1)
        11:49:31 [party 17] RUT lenh reform gen 3 - da du doi (chu706=4 ... chu710=4)
        11:49:36 [chusau] (LEADER) reform gen 3: ... -> moi lai party
        11:49:36 [chusau] Roi/giai tan party cu -> roster 3 -> 2 -> 1 -> 0
        11:49:37 [party 17] gen 25: viec=moi - DOI chua du (tat ca = 0)
    Luc 11:49:21 chu706 va chu708 DA thay du 4 nguoi - doi that su DA DU tren server, chi la
    chu710 chua nhan kip goi. Muoi giay sau moi acc deu thay 4/4. Lenh ra luc do la lenh SAI, va
    no chay tiep den tan buoc pha doi. Chu ky lap lai y het luc 11:51:34.

    Phan biet voi doi HONG THAT (party 1, 07/09: roster (4,0,0,0,0) DUNG IM 44 phut):
      - dang lan  : co acc DA thay du, acc khac chua -> lech nay TU HET trong vai giay
      - hong that : lech dung im qua `ROSTER_LAN_SEC` -> het han, doc theo ban sao cham nhat nhu cu
    """
    if len(song) < 2:
        return False
    _can = len(song) - 1
    _ros = []
    for _u, c in song:
        try:
            _ros.append(len(getattr(c, "party_members", None) or ()))
        except Exception:
            _ros.append(0)
    if not (max(_ros) >= _can > min(_ros)):
        st.pop("roster_lech_tu", None)      # nhat tri roi (du hoac hong deu the) -> quen moc
        return False
    _tu = float(st.get("roster_lech_tu", 0.0) or 0.0)
    if not _tu:
        st["roster_lech_tu"] = _tu = time.time()
    return time.time() - _tu < ROSTER_LAN_SEC


def _thieu_doi(pidx, song):
    """DOI da du chua - theo SU THAT CUA SERVER, khong theo bo dem trong cua bot.

    `joined_member_count()` doc `_PARTY_JOINED` - bang do CHINH BOT ghi khi thay acc accept. No la
    so nho, va no OM STALE: party tan ma khong ai unmark thi bot van tuong con du.

    Ca that 07/09 party 1: ca nam acc dung o Truong Sa 44 phut, dieu phoi ket luan "du doi" nen ra
    `VIEC_LAM` va im - trong khi log cua chinh leader lap lai lien tuc:
        13:26:49 [xGAx] KHONG o party nao (roster server + local deu rong)
    User: "du doi cai lon, bon no co cung party deo dau".

    `c.party_members` la roster SERVER gui ve (`0x0d`), tuc su that.

    NHUNG DOC CUA AI? LEADER - no la NGUOI MOI, roster cua no CHINH LA roster cua doi. Member chi
    nhan ban sao, va ban sao do den muon / khong day du.

    Ban cu doi MOI acc phai thay du ("chi can MOT acc thieu la doi chua du"), nen doi DA DU van bi
    doc thanh thieu - vinh vien, vi ban sao cua member khong bao gio bang leader.

    Ca that party 1, 14/09 (user: "p1, party xong deo ra cho quai"):
        13:29:01 [batbat] (LEADER) MAT PARTY giua chung (0/4) -> MOI LAI
        13:29:01..04 PARTY: ... vao doi -> roster 1 -> 2 -> 3 -> 4 nguoi      <- DU 4/4
        13:29:10 [batbat] (LEADER) chua ra bai: dieu phoi dang ra lenh 'moi'
        13:29:15/20/25 pos=(1140, 360) dung im
    Luc do roster dung im o (chihao188=2 sga008=4 sga018=4 sga019=3 sga020=1) suot 33 giay - KHONG
    phai dang lan, ma la member vinh vien khong co ban sao day du. Leader (sga008) thay 4 = du.
    Dieu phoi van ket luan "thieu" -> `viec=moi` -> cua "chua ra bai" chan leader -> ca party dung
    im giua bai train.

    Leader khong chay (dang relogin) -> KHONG doan bua: lay ban sao DAY DU NHAT con lai. Doi tan
    that thi moi ban sao deu tut, nen van bat duoc (ca 07/09 party 1 o tren: leader `xGAx` roster
    RONG -> van ket luan thieu, dung).
    """
    can = len(song) - 1          # roster khong ke chinh minh
    if can <= 0:
        return False
    _leader = config.PARTY_LEADER_ACC.get(pidx)
    for _u, c in song:
        if _u == _leader:
            return len(getattr(c, "party_members", None) or ()) < can
    # Leader khong con trong danh sach acc song -> doc ban sao day du nhat.
    _max = 0
    for _u, c in song:
        try:
            _max = max(_max, len(getattr(c, "party_members", None) or ()))
        except Exception:
            pass
    return _max < can


def _ly_do_lech(maps, kenhs, lech_kenh_that, tien_to="", mot_minh=()):
    """Cau ly do NOI DUNG SU THAT - doc thang tu client, khong qua bao cao cua ai."""
    if mot_minh:
        return "party %sco %d acc DUNG MOT MINH (cung map ma khong ai thay -> khac instance): %s" % (
            tien_to, len(mot_minh), [l for _u, l in mot_minh])
    if lech_kenh_that:
        return "party %slech kenh (%d acc dung mot minh)" % (tien_to, lech_kenh_that)
    if len(maps) > 1:
        return "party %sdang o %d MAP khac nhau %s" % (tien_to, len(maps), sorted(maps))
    return "party %slech kenh %s" % (tien_to, sorted(kenhs))




def _chup_anh_cap_party(pidx, st, song, lech_tu):
    """Doc trang thai THAT cua ca party -> `party_engine.AnhCapParty`.

    Day la phan DOC (can client + state + helper cua file nay). Phan QUYET DINH da chuyen han
    vao `party_engine.quyet_dinh_cap_party` - user 21/09: "thread biet het tat ca thong tin roi
    thi no phai nam vai tro dieu phoi luon".
    """
    pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
    raw_mode = pcfg.get("mode")
    pha = st.get("dt_phase", "digioi") if raw_mode == "digioi_train" else (raw_mode or "train")

    try:
        _xong_event = bool(st.get("go_claim") and st["go_claim"].is_set()) or any(
            getattr(c, "_npc40_done", False) for _u, c in song)
    except Exception:
        _xong_event = False

    # ACC DANG LAM VIEC VAT KHONG TINH VAO PHEP DO LECH MAP: viec vat PHAI o map khac (ban Noi Dat
    # o Nghiep Thanh, cat tien trang, danh boss the gioi). Dem no vao thi party LUC NAO cung "lech
    # map" -> lenh gom lien tuc -> pha doi (party 13, 14/09).
    _ban_viec_vat = set(_ai_dang_lam_viec_le(song))
    maps, _chua_biet_map = {}, []
    for u, c in song:
        if u in _ban_viec_vat:
            continue
        m = getattr(c, "current_map", None)
        if m is not None:
            maps.setdefault(int(m), []).append(u)
        else:
            _chua_biet_map.append(u)
    # CHI DEM KENH DO SERVER XAC NHAN: so kenh cua acc vua co lenh doi kenh HONG la so NHO LAI,
    # khong phai bang chung (party 24, 11/09 - "p24 dang o kenh 5 het, co lech kenh deo dau").
    kenhs, _kenh_mo_ho = set(), []
    for _u, c in song:
        if _u in _ban_viec_vat:
            continue
        ch = getattr(c, "current_channel", None)
        if not ch:
            continue
        if hasattr(c, "kenh_dang_chac") and not c.kenh_dang_chac():
            _kenh_mo_ho.append(_u)
            continue
        kenhs.add(int(ch))
    if _kenh_mo_ho:
        log.debug("[party %d] bo qua kenh cua %s khi dem lech: lenh doi kenh gan nhat hong nen so "
                  "dang nho khong con dang tin", pidx + 1, sorted(_kenh_mo_ho))

    # BAO CAO DOI CHIEU TUNG CAP tu leader: tap `kenhs` chi noi "co bao nhieu gia tri kenh khac
    # nhau", con leader doi chieu tung cap nen biet CHINH XAC bao nhieu member lech va la ai.
    _lech_kenh_that, _mot_minh = 0, ()
    for _u, c in song:
        _bq = getattr(c, "_moi_bo_qua", None)
        if _bq and time.time() - float(_bq.get("luc") or 0) < 30 and _bq.get("lech_kenh"):
            _lech_kenh_that = max(_lech_kenh_that, len(_bq["lech_kenh"]))

    _du_doi = not _thieu_doi(pidx, song)
    if _du_doi and len(kenhs) > 1:
        log.debug("[party %d] du party (%s) nhung so kenh nho lai lech %s -> TIN ROSTER, bo qua",
                  pidx + 1, _tinh_hinh_doi(song), sorted(kenhs))

    _viec_train, _ly_train = (VIEC_LAM, "")
    if _du_doi:
        try:
            _viec_train, _ly_train = _viec_di_train(pidx, st, song, pha)
        except Exception:
            _viec_train, _ly_train = VIEC_LAM, ""

    _noi = next(iter(maps)) if len(maps) == 1 else None
    _o_thanh_di_ngang = bool(_noi is not None and not _du_doi and _o_thanh_di_qua(pidx, st, _noi))

    try:
        _o_thanh = bool(song) and all(
            getattr(config, "is_teleport_city", lambda _c: False)(
                int(getattr(c, "current_map", 0) or 0))
            for _u, c in song)
    except Exception:
        _o_thanh = False

    return party_engine.AnhCapParty(
        bay_gio=time.time(),
        so_acc_song=len(song),
        so_acc_cau_hinh=len(party_accounts(pidx)),
        raw_mode=raw_mode,
        pha=pha,
        can_lap_doi=_mode_can_lap_doi(pidx),
        ngoai_gio_40npc=_party_40npc_ngoai_gio(pidx, pcfg),
        event_xong=_xong_event,
        # HET GIO ma VAN CON DI GIOI HO PHU (0xff8c) trong tui thi CHUA phai "het gio Di Gioi":
        # dung ho phu de vao tiep. User chot 22/09: "phai la pha DG ket thuc khi het time VA ko
        # con DG phu". Doc THANG tui (`bag_counts`), khong nho so rieng.
        ca_party_het_gio_dg=bool(song and not [
            u for u, c in song
            if not _het_gio_dg(c)
            or int((getattr(c, "bag_counts", None) or {}).get(0xff8c, 0) or 0) > 0]),
        maps=maps, kenhs=kenhs, chua_biet_map=_chua_biet_map,
        lech_kenh_that=_lech_kenh_that, mot_minh=_mot_minh,
        du_doi=_du_doi,
        leader_dang_rot=bool(song and _leader_dang_rot(pidx, song)),
        dang_doi_kenh=bool(song and _dang_doi_kenh(song)),
        thieu_acc_song=bool(song and _thieu_acc_song(pidx, song)),
        ai_lech_instance=(_ai_lech_instance(pidx, song) if song and not _du_doi else []),
        o_thanh_di_qua=_o_thanh_di_ngang,
        thanh_tap_ket=_thanh_tap_ket_dich(pidx, st),
        ca_party_o_thanh=_o_thanh,
        acc_dung_hinh=_acc_dung_hinh(st, song, KE_HOACH_DUNG_HINH_SEC) if song else [],
        viec_di_train=_viec_train, ly_do_di_train=_ly_train,
        tinh_hinh_doi=_tinh_hinh_doi(song),
        ly_do_lech=_ly_do_lech(maps, kenhs, _lech_kenh_that, "", _mot_minh),
        ly_do_lech_dg=_ly_do_lech(maps, kenhs, _lech_kenh_that, "trong DG ", _mot_minh),
        kenh_hien_tai=st.get("channel"),
        lech_tu=lech_tu, het_lech_tu=st.get("het_lech_tu"), o_thanh_tu=st.get("o_thanh_tu"),
        reform_gen=int(st.get("reform_gen", 0) or 0),
        reform_gen_thoa=int(st.get("reform_gen_thoa", 0) or 0),
        leader_acc=config.PARTY_LEADER_ACC.get(pidx),
        co_leader_dang_song=any(u == config.PARTY_LEADER_ACC.get(pidx) for u, _c in song),
        thanh_cu=(_ke_hoach(st) or {}).get("thanh"),
        han_lech_map=LECH_MAP_AN_HAN_SEC, han_lech_chung=KE_HOACH_LECH_MAP_SEC,
        han_het_lech=HET_LECH_CHAC_SEC, han_dung_hinh=KE_HOACH_DUNG_HINH_SEC,
    )


def _thi_hanh_hieu_ung(pidx, st, song, hu, viec, anh):
    """Thi hanh `HieuUng` ma `quyet_dinh_cap_party` tra ve. Ham quyet dinh la THUAN nen moi thay
    doi trang thai deu don ve day."""
    with st["lock"]:
        st["het_lech_tu"] = hu.het_lech_tu
        if hu.o_thanh_tu is not None:
            st["o_thanh_tu"] = hu.o_thanh_tu
        if hu.doi_pha_train:
            st["dt_phase"] = "train"
        if hu.xoa_nhip_acc:
            st["nhip_acc"] = {}      # ra lenh roi thi moi acc tinh lai tu dau
        if hu.rut_reform:
            _rg = int(st.get("reform_gen", 0) or 0)
            if _rg and int(st.get("reform_gen_thoa", 0) or 0) < _rg:
                st["reform_gen_thoa"] = _rg
                log.info("[party %d] DIEU PHOI: RUT lenh reform gen %d - da du doi (%s), cung map "
                         "%s kenh %s -> khong thi hanh lai (lam lai la pha party vua lap)",
                         pidx + 1, _rg, anh.tinh_hinh_doi, sorted(anh.maps), sorted(anh.kenhs))
    if hu.reset_joined:
        reset_party_joined(pidx)     # so nho khong duoc giu nguoi cua party da tan (L2d)
    dat_party_dang_gom(pidx, hu.dang_gom)
    if hu.nguoi_keo == "*" and anh.leader_acc and not anh.co_leader_dang_song:
        log.info("[party %d] DIEU PHOI: nguoi keo '%s' khong con chay -> tam giao cho tat ca",
                 pidx + 1, anh.leader_acc)
    dat_nguoi_keo(pidx, hu.nguoi_keo)


def _engine_chot_2k_xong(pidx, st, song):
    """DIEU PHOI la nguoi DUY NHAT chot "2K da het" -> bat `event_exit_now` (ra thap + tat acc).

    Truoc day luong LEADER tu bam co nay trong `_on_crawl_done`, ma ham do chay o `finally` nen
    no bat len CA KHI leader chi bi ROT MANG. Party 12 (06/09): leader dinh ma 13 o tang 5, ca
    party bi keo nguoc xuong 8 tang roi tat game giua chung.

    Dieu phoi nhin trang thai THAT:
      - "thua" / "xong"  -> het that, cho thoat.
      - "het_duong" (da danh HET tang ma khong co cong len) -> khong con gi lam o tang do nua.
        Coi nhu xong: ra khoi thap + tat acc. KHONG duoc dung im - party 1 va party 11 (06/09)
        danh xong tang 11 roi dung yen o (650,430) hang phut (user: "danh thua roi m dung do an va
        a"). Thieu du lieu world_nav thi ghi log de bo sung, chu khong bat acc dung cho.
      - "ket"  (ket o cong / danh thieu tran) -> CHUA het. Party 15 (06/09): leader
        dung 10 phut o tang 9 vi party chi con 0/4 nguoi, cong khong qua duoc. Viec can lam la
        GOM + MOI LAI roi thu cong tiep, khong phai bo ca vong 2K.
      - "dut" (client chet) -> CHUA het. Supervisor relogin, `_decide_2k_resume` leo tiep.
    """
    kq = st.get("2k_ket_qua")
    if not kq or st["event_exit_now"].is_set():
        return
    if kq in ("ket", "dut"):
        return              # chua het - de vong keepalive/dieu phoi gom & moi lai roi leo tiep
    st["event_exit_now"].set()
    log.info("[party %d] DIEU PHOI: 2K %s -> CA DOI ra khoi thap roi thoat game", pidx + 1,
             {"thua": "THUA", "xong": "da xong",
              "het_duong": "da danh het tang ma khong co cong len (thieu du lieu world_nav)"}
             .get(kq, kq))


# Da chot TANG GOM thi giu bay lau - di bo xuong vai tang mat hang chuc giay.
TANG_GOM_KIEN_NHAN_SEC = 180.0


def _chot_tang_gom(pidx, st, song):
    """Chot TANG GOM va GIU (L6) - dung tinh lai moi nhip.

    `_tang_gom_2k` lay `min(map)` cua ca doi. Tinh lai moi 2 giay thi trong luc member DANG DI
    XUONG, `min` tut theo tung buoc chan cua chinh no -> dich chay truoc mat, ca doi tut toi day
    thap, mat het tang da leo.

    Log that party 8 (06/09):
        17:47:08 gom [12932, 12934] -> dich 12932
        17:47:19 gom [12931, 12934] -> dich 12931   (member vua xuong 12931)
        17:51:05 gom [12922, 12934] -> dich 12922   (tut toi DAY thap)

    Giu dich cho toi khi: CA DOI da toi dich (het lech) · qua han · hoac khong con o trong thap.
    """
    moi = _tang_gom_2k(pidx, song)
    if moi is None:
        with st["lock"]:
            st["tang_gom"] = None
            st["tang_gom_luc"] = 0.0
        return None
    cu = st.get("tang_gom")
    if cu:
        _luc = float(st.get("tang_gom_luc", 0.0) or 0.0)
        _con = {int(getattr(c, "current_map", 0) or 0) for _u, c in song}
        if len(_con) <= 1:
            with st["lock"]:                      # da gom xong -> xoa dich
                st["tang_gom"] = None
                st["tang_gom_luc"] = 0.0
            return None
        if time.time() - _luc < TANG_GOM_KIEN_NHAN_SEC:
            return int(cu)                        # dang di xuong -> GIU, dung tut theo
        log.info("[party %d] DIEU PHOI: tang gom %s qua %.0fs van chua gom xong -> chot lai",
                 pidx + 1, cu, TANG_GOM_KIEN_NHAN_SEC)
    with st["lock"]:
        st["tang_gom"] = moi
        st["tang_gom_luc"] = time.time()
    if cu != moi:
        log.info("[party %d] DIEU PHOI: CHOT tang gom = %s (tang thap nhat ca doi toi duoc)",
                 pidx + 1, config.scene_name(int(moi)))
    return moi


def _tang_gom_2k(pidx, song):
    """Tang GOM DOI cho 2K nhi kieu: TANG THAP NHAT ma ca doi dang o. None = khong phai 2K.

    Doc THANG `current_map` cua tung client thay vi bang event_start_map cu (bang do chi duoc
    dien luc LOGIN) - nho vay bat duoc ca lech tang GIUA CHUNG, dung ca party 1 (06/09): leader
    len 12925 con 4 member o 12924, khong ai kiem.

    Co acc dang o NGOAI thap -> ve CUA VAO (`dest_map`): acc ngoai tele vao binh thuong, acc
    trong thap di bo xuong day.
    """
    pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
    try:
        ev = config.event_hom_nay(pcfg.get("event_key") or "")
    except Exception:
        ev = None
    if ((ev or {}).get("party_battle") or {}).get("kind") != "floor_crawl":
        return None
    trong, ngoai = [], 0
    for _u, c in song:
        m = int(getattr(c, "current_map", 0) or 0)
        if m and _inside_floor_crawl_tower(ev, m):
            trong.append(m)
        else:
            ngoai += 1
    if not trong:
        # KHONG AI trong thap -> khong co viec "gom tang" nao ca (ca party dang o thanh, dang di
        # toi, hoac da ra xong). Tra None, dung tra `dest_map`: cho goi dung ket qua nay de biet
        # "co dang trong thap khong", tra so la chan nham moi thu o moi noi.
        return None
    if ngoai:
        # Co dua trong thap, co dua ngoai -> ve CUA VAO: dua ngoai tele vao binh thuong, dua trong
        # thap di bo xuong day.
        return int((ev or {}).get("dest_map") or 0) or None
    return min(trong)


def _thi_hanh_gom(c, st, label, role, kh, do_reform):
    """Thi hanh lenh GOM cua dieu phoi. TRONG THAP 2K thi DI BO xuong tang, ngoai ra thi reform.

    `_do_reform` di theo route VE THANH. Trong thap 2K khong co route nao ca, nen no chi in
    "reform: khong co smart/legacy route -> bo qua" roi tra ve NGAY - lenh gom cua dieu phoi
    KHONG BAO GIO duoc thi hanh, ma vong goi thi lap lai. Party 5 (06/09) quay 201.495 vong,
    party 1 thi leader len tang 12925 mot minh ma khong ai keo xuong.

    Tang dich do DIEU PHOI chot (`kh["tang_gom"]`), khong phai acc tu tinh - moi acc doc cung
    mot so nen ca party xuong cung mot tang.
    """
    _tang = kh.get("tang_gom")
    if _tang:
        pcfg = getattr(config, "PARTY_CONFIG", {}).get(getattr(c, "party_idx", -1), {})
        try:
            ev = config.event_hom_nay(pcfg.get("event_key") or "")
        except Exception:
            ev = None
        if ev is not None:
            if int(getattr(c, "current_map", 0) or 0) == int(_tang):
                return True          # da o dung tang gom -> dung yen cho ca doi xuong
            log.warning("[%s] (%s) DIEU PHOI gom 2K: di bo xuong %s (%s)",
                        label, role, config.scene_name(int(_tang)), kh.get("ly_do") or "lech tang")
            return bool(c.regroup_to_event_start(ev, dest=int(_tang)))
    do_reform()
    return True







# ------------------------------------------------------------------ ENGINE MOI: dang ky acc
def _pb_doi_levels_engine_moi(pidx):
    """Cac level PB to doi user BAT cho party nay, theo dung thu tu engine cu chay.

    Doc `_team_dungeon_flags` + `TEAM_DUNGEON_LEVELS` - dung nguon engine cu van dung, khong che
    ra danh sach rieng (lech mot cai la party engine moi danh thieu/thua pho ban ma khong ai biet).
    """
    _pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    if not _pcfg.get("auto_team_dungeon", True):
        return ()
    try:
        _flags = _team_dungeon_flags(_pcfg)
    except Exception:
        return ()
    return tuple(int(lv) for lv in getattr(config, "TEAM_DUNGEON_LEVELS", (20, 50, 80))
                 if _flags.get(int(lv), False))


def _chuan_bi_bai_train(c, st, pidx, label):
    """LEADER chot MAP TRAIN + TAM BAI QUAI cho engine moi. Goi lai dung ham engine cu van dung.

    `_engine_chot_map` la ham THUAN DU LIEU (khong can ai di dau ca) nen goi duoc ngay tu giay
    dau. `_resolve_train_mob_centers` thi can client dang o dung map train.

    Chay o vong giu song cua leader (khong phai trong nhip engine): no CO THE CHAN vai giay, ma
    nhip quyet dinh thi tuyet doi khong duoc chan.
    """
    _engine_chot_map(pidx, st)           # -> st["auto_train"] (map train) / st["auto_dg_level"]
    if st.get("mob_spot"):
        return                              # da co bai roi
    sc = _map_train_dich(pidx, st)
    if not sc or int(getattr(c, "current_map", 0) or 0) != int(sc):
        return                              # chua toi map train -> chua doc duoc tam quai
    tm = getattr(config, "TRAIN_MAPS", {}).get(int(sc))
    if not tm:
        return
    mobs = [tuple(point) for point in tm.get("mobs", ())]
    if not mobs:
        observed = getattr(c, "_pe_mob_scan", None)
        if observed and observed[0] == int(sc):
            mobs = observed[1]
    if not mobs:
        return
    _mi = int((getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}).get("mob_index", -1))
    spot = random.choice(mobs) if _mi < 0 else (mobs[_mi] if 0 <= _mi < len(mobs) else mobs[0])
    with st["lock"]:
        st["mob_spot"] = spot
        st["train_map_dich"] = int(sc)
    log.info("[%s] ENGINE: chot bai train map %s tam quai %s", label, sc, spot)


HO_PHU_NGUONG_PHUT = 15      # engine cu: chi dung Ho Phu khi con DUOI 15 phut


STOP_CHO_LEADER_SEC = 60.0   # engine cu: member cho leader ve safe toi da 60s


def _safe_map_dich_engine_moi(pidx):
    """Danh sach safe cua MAP DICH (map train) - `build_smart_route` can diem den cu the.

    Y `route_safe` cua flow cu: doc `TRAIN_MAPS[sc]["safe"]`. Khong co thi tra None, luc do
    `build_smart_route` chi dung duong toi map chu khong nham diem nao.
    """
    _sc = _map_train_dich(pidx, _pstate(pidx))
    if not _sc:
        return None
    _safes = [tuple(p) for p in
              ((getattr(config, "TRAIN_MAPS", {}) or {}).get(int(_sc), {}) or {}).get("safe", [])
              if len(p) == 2]
    return _safes or None


# NAV_TOI_NOI (60) + jitter fits within 80; the nearby diem quai stays outside.
RALLY_BAN_KINH = 80


def _ra_safe_engine_moi(c, pidx, ly_do="", con_lam=lambda: True):
    """RA DIEM AN TOAN truoc khi doi kenh - ban cua ENGINE MOI.

    Engine cu dung closure `_ra_safe_truoc_khi_doi_kenh` (an trong `run_account`, doc bien cuc bo
    `train_on_map`/`sc`/`train_safes`) nen goi tu ngoai khong duoc. Day la ban dung duoc dung
    LUAT do, chi doc tu `st` + `config.TRAIN_MAPS`.

    Vi sao KHONG doi kenh ngay tai cho (user chot 27/08, va chot lai 21/09 khi ra flow day du):
    doi kenh KHONG doi map/toa do - sang kenh moi la dung Y NGUYEN cho cu, ma o kenh moi cho do
    co the day quai VA party vua tan (giai tan truoc khi doi) -> tung acc dung le giua bai, an dan
    ngay khi vua vao kenh.

    Tra True = da o safe (hoac khong can ra: dang khong o map train).
    """
    st = _pstate(pidx)
    _sc = _map_train_dich(pidx, st)
    _cur = int(getattr(c, "current_map", 0) or 0)
    if not _sc or _cur != int(_sc):
        return True                     # khong o map train -> khong co bay quai nao de tranh
    # GIU NGUYEN diem da chon o lan goi TRUOC trong cung mot lenh doi kenh. User chot 21/09:
    # "chuyen sang kenh duoc chon -> chay ve safe duoc chon luc nay (de phong truoc do di chuyen
    # fail)". Neu moi lan lai chon lai thi `rally_point` co the da doi (vong gom chot diem khac)
    # -> lan sau ve MOT CHO KHAC, dung y dinh "ve lai dung cho vua roi".
    diem = st.get("safe_doi_kenh")
    if not diem:
        diem = st.get("rally_point")
        if not diem:
            _safes = _safe_map_dich_engine_moi(pidx) or []
            diem = _safes[0] if _safes else None
        if diem:
            with st["lock"]:
                st["safe_doi_kenh"] = tuple(diem)
    if not diem:
        return True                     # map nay khong khai safe -> khong biet ra dau, di tiep
    label = getattr(c, "_label", "?")
    log.info("[%s] %s: ra diem an toan %s truoc khi doi kenh", label, ly_do or "doi kenh", diem)
    try:
        # CHUA GIAI TAN PARTY (party con DU) thi KHONG bo chay: du party thi viec gi phai chay,
        # dinh quai cu danh cho xong roi di tiep (user chot 30/08).
        _con_party = bool(getattr(c, "party_members", None))
        c.flee_mode = bool(not _con_party)
        if not c._wait_combat_clear(idle=2.0, cap=120.0):
            return False
        if not con_lam():
            return False
        c._theo_leader_sua_pos()
        _p = getattr(c, "pos", None)
        if _p and math.dist(_p, diem) <= RALLY_BAN_KINH:
            return True
        c.navigate_to(int(diem[0]), int(diem[1]), flee=not _con_party,
                      abort=lambda: not con_lam())
        # XAC NHAN da toi - `navigate_to` khong tu kiem (user chot 30/08: "chuyen sau thi phai
        # check lai da o safe chua"). Cho phep lech 120 don vi (mot buoc di).
        _p = getattr(c, "pos", None)
        if not _p or math.dist(_p, diem) > RALLY_BAN_KINH:
            log.warning("[%s] %s: CHUA ra toi diem an toan %s (dang o %s) -> chua doi kenh",
                        label, ly_do or "doi kenh", diem, _p)
            return False
        return con_lam()
    except Exception as e:
        log.warning("[%s] %s: loi ra safe truoc khi doi kenh: %s", label, ly_do or "doi kenh", e)
        return False


_ENGINE_LECH_TU = {}     # pidx -> moc "bat dau lech" (tham so trang thai cua `_dieu_phoi_quyet`)


def _ghi_thong_ke_engine_moi(pidx, spot, bat):
    """Bat/tat ghi nhan THONG KE CHAN o tam quai - y `_set_train_block_stats_spot` cua engine cu.

    Ham cu la closure trong `run_account` (dung `sc` / `is_leader` / `train_on_map`) nen khong goi
    tu ngoai duoc; day la ban dung cho engine moi, GIU DUNG hai dieu kien cua no:
        * chi bat cho LEADER (`enabled and is_leader`)
        * khong co spot / khong phai map train -> tat han
    """
    _sc = _map_train_dich(pidx, _pstate(pidx))
    _lead = config.PARTY_LEADER_ACC.get(pidx)
    for _u, _p, _l, _k in party_accounts(pidx):
        _c = account_clients.get(_u)
        if _c is None:
            continue
        try:
            if spot and _sc:
                _c.set_train_block_stats_context(int(_sc), spot, enabled=bool(bat) and _u == _lead)
            else:
                _c.set_train_block_stats_context(enabled=False)
        except Exception:
            pass


def _event_cua_party(pidx):
    """Event dang cau hinh cho party (`events.json` theo `event_key`)."""
    _pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    _evs = getattr(config, "EVENTS", {}) or {}
    return _evs.get(_pcfg.get("event_key")) or (next(iter(_evs.values())) if _evs else None)


def _map_event_engine_moi(pidx):
    """Cac map cua event (`staging_map` / `dest_map`) - de biet acc DA VAO map event chua.

    2K (`floor_crawl`) la CA DAI TANG `dest_map..top_map`, khong phai mot map: leo len tang 2 la
    doi map. Chi ke `dest_map` thi engine tuong acc vua "ra khoi map event" ngay sau tran dau ->
    giao `VIEC_VAO_EVENT` -> `go_to_event` -> `leave_party()` + keo ca doi ve 12921 = MAT HET
    tang da leo.
    """
    ev = _event_cua_party(pidx)
    if not ev:
        return ()
    _pb = (ev.get("party_battle") or {})
    if _pb.get("kind") == "floor_crawl":
        _dest = int(ev.get("dest_map") or 0)
        _top = int(_pb.get("top_map") or 0)
        if _dest and _top and _dest <= _top:
            # CHI dai tang, KHONG ke `staging_map` (12921): acc con o san cho thi van phai
            # `go_to_event` di tiep vao 12922 - luc do party chua lap nen `leave_party()` trong
            # do vo hai. Ke staging vao day = engine coi no "da vao roi" va bo mac o san cho.
            return tuple(range(_dest, _top + 1))
    return tuple(int(m) for m in (ev.get("staging_map"), ev.get("dest_map")) if m)


def _event_xong_engine_moi(pidx):
    """Event da XONG (hoac ngoai gio) -> ca party di doi thuong roi thoat.

    Ba nguon, y flow cu:
      `go_claim`            - `_ket_thuc` cua npc40 set khi het gio / thua 2 tran / thua sach
      `event_battle_done`   - party da THUA -> khong mo lai battle
      `in_40npc_window()`   - NGOAI GIO event (dong 5723): "40NPC NGOAI GIO event -> huy party +
                              di doi thuong + thoat game"
    """
    st = _pstate(pidx)
    _ev = _event_cua_party(pidx)
    if (_ev or {}).get("party_battle", {}).get("kind") == "floor_crawl":
        # 2K: NGUOI DUY NHAT chot "2K da het" la DIEU PHOI (`_engine_chot_2k_xong` bat
        # `event_exit_now`), va no phan biet "thua/xong/het_duong" = HET that voi "ket/dut" =
        # CHUA het (ket o cong / client rot mang -> con gom & leo tiep).
        #
        # TUYET DOI khong hoi `in_40npc_window()` o day: do la khung gio cua 40NPC, con 2K
        # (`nhi_kieu`) de `lich: null`. Ngoai khung 40NPC la no tra "event xong" NGAY -> ca party
        # di `claim_40npc_reward` = ve Trac Quan (Quang Truong) roi thoat game, du 2K chua danh
        # phut nao. User 20/09: "lam lon gi ma bon no chay ve quang truong roi out het".
        return bool(st["event_exit_now"].is_set())
    if st["go_claim"].is_set() or st["event_battle_done"].is_set():
        return True
    _lead = config.PARTY_LEADER_ACC.get(pidx)
    _c = account_clients.get(_lead) if _lead else None
    if _c is None:
        return False
    try:
        return not _c.in_40npc_window()
    except Exception:
        return False


def _vao_event_engine_moi(c, pidx):
    """VAO MAP EVENT - `go_to_event(ev)` cua engine cu (no lo ca cinematic + thoat cutscene)."""
    ev = _event_cua_party(pidx)
    if ev is None:
        return False
    return bool(c.go_to_event(ev))


def _lenh_tay_engine_moi(c, pidx):
    """Thi hanh LENH TAY cua GUI (`st["cmd"]`) cho engine moi. True = da xong.

    Truoc 21/09 engine moi KHONG doc `cmd_gen`: `party_teleport_city` / `party_route_maps` chi dat
    `st["cmd"]` roi tang gen, ma NOI DUY NHAT doc gen do la vong keepalive cua `run_account`
    (engine cu). Party tu 21 tro len chay engine moi -> lenh roi vao hu khong.
    User 21/09: "P21 dang train -> chon map -> chon thanh thi ko co gi xay ra ca".

    Giu DUNG THU TU cua engine cu (`run_account`, khoi "LENH THU CONG"):
        flee_mode -> CHO HET TRAN (cap 60s) -> LEADER roi party -> teleport -> tra flee_mode
    Doi kenh (`channel`) KHONG di qua day: no co thu tu rieng do user chot 30/08 (leader ra safe
    TRUOC roi moi giai tan), va dieu phoi da lo duong do bang `kenh_dich`.
    """
    st = _pstate(pidx)
    with st["lock"]:
        gen = int(st.get("cmd_gen", 0) or 0)
        cmd = st.get("cmd")
    if not gen:
        return True
    label = getattr(c, "_label", "?")
    _lam_xong = lambda: setattr(c, "_pe_lenh_tay_gen", gen) or True
    if not cmd:
        return _lam_xong()
    kind = cmd[0]
    if kind == "channel":
        # TRUOC 21/09 cho nay chi `return _lam_xong()` voi ly do "dieu phoi lo bang `kenh_dich`
        # (`_engine_chot_kenh` + `kenh_ghim`)". NHUNG `_engine_chot_kenh` nam trong
        # `_dieu_phoi_loop`, ma vong do BO QUA party dung engine moi (cua chan so 1) -> khong ai
        # lo ca. Lenh bi danh dau "da xong" roi vut di.
        # Khong ai thay cho toi khi `PARTY_ENGINE_MOI_TU` ha xuong 1: luc do MOI party chay engine
        # moi va nut doi kenh chet han (user 21/09: "party 1, t bam doi kenh ma no deo doi").
        #
        _la_leader = bool(getattr(c, "_pe_la_leader", False))
        _stop_ev = account_stops.get(getattr(c, "_username", None) or "")
        doi_kenh_theo_lenh_tay(
            c, pidx, cmd[1], gen, label=label,
            role="LEADER" if _la_leader else "member",
            is_leader=_la_leader,
            has_leader=bool(config.PARTY_LEADER_ACC.get(pidx)),
            ra_safe=lambda _ly=" ": _ra_safe_engine_moi(c, pidx, _ly),
            con_chay=lambda: not (_stop_ev is not None and _stop_ev.is_set()))
        return _lam_xong()
    if kind == "route":
        return False  # Whole-party arrival is acknowledged by the controller.
    c.flee_mode = True
    _t0 = time.time()
    while c.in_combat(idle_secs=3.0):
        if not c.running or time.time() - _t0 > 60:
            break
        time.sleep(0.5)
    if getattr(c, "_pe_la_leader", False):
        # Teleport bat buoc ROI DOI truoc (client chan khi con trong doi) - va party se duoc lap
        # lai ngay sau do theo chuoi binh thuong cua dieu phoi.
        try:
            c.leave_party()
            reset_party_joined(pidx)
        except Exception as e:
            log.warning("[%s] manual: loi huy party truoc khi teleport: %s", label, e)
    if kind == "city":
        cid, flag = int(cmd[1]), int(cmd[2])
        try:
            c.go_to_town(cid, flag)
            log.info("[%s] manual: da teleport ve thanh %s (lenh tay gen %d)", label, cid, gen)
        except Exception as e:
            log.warning("[%s] manual: loi teleport thanh: %s", label, e)
    c.flee_mode = False
    return _lam_xong()


def _tang_gom_engine_moi(pidx):
    """TANG GOM cua 2K cho engine moi - goi THANG `_tang_gom_2k` cua engine cu.

    Tang THAP NHAT ca doi dang o (khong phai day thap - tut ve day la mat sach tang da leo), hoac
    `dest_map` (12922, cua vao) khi con dua o NGOAI thap. None = khong phai 2K / khong ai trong thap.
    """
    song = [(u, cl) for u, cl in _clients_cua_party(pidx) if cl is not None]
    if not song:
        return None
    try:
        return _tang_gom_2k(pidx, song)
    except Exception:
        return None


def _fc_gom_engine_moi(c, pidx):
    """2K LECH TANG: DI BO ve tang gom - `regroup_to_event_start` cua engine cu.

    Trong map event KHONG teleport duoc nen day la duong DUY NHAT de xe nhau trong thap.
    """
    ev = _event_cua_party(pidx)
    _tg = _tang_gom_engine_moi(pidx)
    if ev is None or not _tg:
        return False
    if int(getattr(c, "current_map", 0) or 0) == int(_tg):
        return True
    return bool(c.regroup_to_event_start(ev, dest=int(_tg)))


def _fc_tien_do(st, scene):
    """Tien do leo thap cua party: da danh xong may DIEM o tang `scene`.

    Doi tang thi dem lai tu 0. Giu o state party (khong phai o client) vi no la tien do CUA CA
    PARTY - leader rot mang, acc khac len thay thi van doc tiep duoc.
    """
    td = st.get("2k_tien_do")
    if not isinstance(td, dict) or int(td.get("scene") or 0) != int(scene or 0):
        td = {"scene": int(scene or 0), "k": 0, "thang": 0}
        st["2k_tien_do"] = td
    td.setdefault("thang", 0)
    return td


def _fc_buoc_engine_moi(pidx):
    """BUOC KE TIEP cua 2K - goi `floor_crawl.tinh_buoc()` (ham thuan) cho tang LEADER dang o.

    Tra "danh" | "len_tang" | None. None = khong phai 2K / chua co leader / da xong / het duong
    (hai truong hop cuoi tu ghi `2k_ket_qua` de dieu phoi chot "2K het" theo dung duong cu).
    """
    ev = _event_cua_party(pidx)
    if ev is None or (ev.get("party_battle") or {}).get("kind") != "floor_crawl":
        return None
    _lead = config.PARTY_LEADER_ACC.get(pidx)
    c = account_clients.get(_lead) if _lead else None
    if c is None:
        return None
    scene = int(getattr(c, "current_map", 0) or 0)
    if not _inside_floor_crawl_tower(ev, scene):
        return None
    st = _pstate(pidx)
    td = _fc_tien_do(st, scene)
    try:
        buoc = floor_crawl.tinh_buoc(ev, scene, int(td.get("k") or 0))[0]
    except Exception as e:
        log.warning("[party %d] 2K: loi tinh buoc ke tiep: %s", pidx + 1, e)
        return None
    if buoc == "len_tang":
        # KHONG duoc lay "phien nay chua thang tran nao" lam cua chan bam cong: LOGIN LAI GIUA
        # CHUNG thi tang da clear tu truoc ma `thang` van = 0 -> chan la ket VINH VIEN o tang do.
        # Flow cu cung khong chan, no chi ghi "chi danh duoc %d/%d tran -> van thu qua cong".
        # Cai phai chan la THU LIEN TUC, khong phai thu lan dau (xem `2k_cong_ket_den` ngay duoi).
        #
        # VUA KET O CONG -> nghi mot nhip, de dieu phoi gom + moi lai. Tra None = engine khong
        # giao `2k_len_tang` nua, party roi xuong nhanh `dp_viec` cua dieu phoi nhu flow cu.
        _den = float(st.get("2k_cong_ket_den") or 0.0)
        if _den and time.time() < _den:
            return None
    if buoc in ("xong", "het_duong"):
        # KHONG tu bat co thoat o day - `_engine_chot_2k_xong` la NOI DUY NHAT chot "2K het"
        # (no phan biet het that voi ket/dut). Chi bao su that len cho no doc.
        with st["lock"]:
            st["event_battle_active"] = False
            st["2k_ket_qua"] = buoc
        return None
    return buoc


def _fc_lam_buoc_engine_moi(c, pidx, len_tang):
    """LEADER lam MOT buoc leo thap roi tra ve - engine quyet buoc ke tiep o nhip sau."""
    ev = _event_cua_party(pidx)
    if ev is None:
        return False
    st = _pstate(pidx)
    label = getattr(c, "_label", "?")
    scene = int(getattr(c, "current_map", 0) or 0)
    td = _fc_tien_do(st, scene)
    _stop_ev = account_stops.get(getattr(c, "_username", None) or "")

    class _Stop:                       # `floor_crawl` nhan mot Event-like co `.is_set()`
        @staticmethod
        def is_set():
            return _stop_ev is not None and _stop_ev.is_set()

    try:
        buoc, a, b, d = floor_crawl.tinh_buoc(ev, scene, int(td.get("k") or 0))
    except Exception as e:
        log.warning("[%s] 2K: loi tinh buoc: %s", label, e)
        return False
    with st["lock"]:
        st["event_battle_active"] = True
    c.flee_mode = False
    _set_party_quest_mode(pidx, True, label, quiet=True)
    if len_tang and buoc == "len_tang":
        nxt, door, center = a, b, d
        # Y flow cu: thang thieu tran thi VAN THU qua cong (tang co the da clear tu phien truoc,
        # vd login lai giua chung), chi ghi lai de con biet ma lan.
        _thang = int(td.get("thang") or 0)
        if _thang < int(td.get("k") or 0):
            log.warning("[%s] (LEADER) 2K: %s chi thang %d/%d diem -> van thu qua cong",
                        label, config.scene_name(scene), _thang, int(td.get("k") or 0))
        log.info("[%s] (LEADER) 2K: danh het diem o %s -> qua cong len %s",
                 label, config.scene_name(scene), config.scene_name(nxt))
        # L0 lop hai, ngay truoc cong: engine da chi giao viec nay khi ANH CHUP thay du doi, nhung
        # tu luc chup den luc toi cong co the mat ca phut di bo - doi tan giua chung la chuyen
        # binh thuong trong thap (doi kenh phai roi doi truoc). Hoi MOT PHAT, khong nam cho.
        if floor_crawl.qua_cong_len_tang(
                c, nxt, door, center, _Stop,
                du_party=lambda: joined_member_count(pidx) >= st["n_members"]):
            _fc_tien_do(st, int(getattr(c, "current_map", 0) or 0))   # tang moi -> dem lai tu 0
            return True
        log.warning("[%s] (LEADER) 2K: KET o cong %s -> de dieu phoi gom & moi lai roi thu tiep",
                    label, config.scene_name(scene))
        with st["lock"]:
            st["2k_ket_qua"] = "ket"
            # NGHI mot nhip truoc khi thu cong lai. Engine cu THOAT HAN vong leo khi ket o cong,
            # nhuong cho dieu phoi gom + moi lai roi moi resume - tuc co khoang lang. Engine moi
            # nhip 1 giay ma khong co cho nay thi no bam cong lien tuc:
            #   16:07:44 [party 7] ENGINE: '2k_len_tang' giao lai 200 lan lien tiep cho taot006
            # Bam cong 200 lan/3 phut vua vo ich vua la duong dan toi ma 13 (gui goi qua nhanh).
            st["2k_cong_ket_den"] = time.time() + FC_KET_CONG_NGHI_SEC
        return False
    if buoc != "danh":
        return False
    idx, point = a, b

    def _heal_party_2k():
        _set_party_quest_mode(pidx, True, label, quiet=True)
        clients = [account_clients.get(u) for u in _active_party_usernames(pidx)]
        clients = [x for x in clients if x is not None and x.running]

        def _heal_one(cli):
            if cli.running and not cli.state.in_battle:
                cli.heal_full(force=True)

        workers = [threading.Thread(target=_heal_one, args=(cli,), daemon=True) for cli in clients]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=10)

    res = floor_crawl.danh_mot_diem(c, ev, scene, idx, point, _Stop, _heal_party_2k,
                                    lambda: _party_left_tower(pidx, ev) or _party_chet_het(pidx))
    # `k` tang theo TUNG LAN THU chu khong theo tran THANG - diem da het quai (login lai giua
    # tang) van phai tinh la da di qua, khong thi quay lai diem 1 mai.
    td["k"] = int(td.get("k") or 0) + 1
    if res == "won":
        td["thang"] = int(td.get("thang") or 0) + 1
    if res == "lost":
        log.warning("[%s] (LEADER) 2K: PARTY THUA o %s (idx=%d) -> KET THUC 2K",
                    label, config.scene_name(scene), idx)
        with st["lock"]:
            st["event_battle_active"] = False
            st["2k_ket_qua"] = "thua"
        _set_party_quest_mode(pidx, False, label)
    return True


def chay_leo_thap_2k(c, pidx, st, ev, label, stopped):
    """LEADER 2K: du party roi leo thap. TACH tu `_start_training` ra cap module - CA HAI ENGINE
    dung CHUNG mot ham (y het cach `chot_thanh_tap_ket` da tach tu `_do_reform`).

    Tra True = caller nen `return True` ngay (2K da xong/dung, khong leo lai).

    2K (Nhi Kieu): DU PARTY roi moi bat dau leo thap. Moi acc tu di 12921->12922 rieng le (khong
    party - vao event dinh party la tele loi), toi map event moi sync kenh + lap party.
    """
    if st["event_battle_done"].is_set():
        c.flee_mode = False
        log.info("[%s] (LEADER) 2K da xong/dung -> khong leo lai", label)
        return True

    def _on_crawl_done(lost=False, ly_do="ket"):
        # CHI BAO SU THAT, KHONG TU QUYET. Vong leo thap ket thuc vi NHIEU ly do, va `finally`
        # cua `run_floor_crawl` goi ham nay o CA BA:
        #   - thua tran            -> 2K het that
        #   - leo het thap / ket   -> 2K het that
        #   - CLIENT CHET GIUA CHUNG (bi da / user Stop) -> 2K CHUA het gi ca
        # Ban cu bam thang `event_exit_now` o day nen ca ba deu thanh "2K xong".
        # Bug that party 12 (06/09): leader tonmot dang o tang 5 (12928) thi dinh `SERVER NGAT
        # KET NOI: gui goi lien tuc qua nhanh (ma 13)` luc 13:50:50 -> vong leo thap dut -> co
        # "xong" bat len -> relogin xong doc co do va keo CA 5 ACC di bo nguoc 12928->...->12003
        # roi TAT GAME. User: "danh deo danh, tu dung chay het ra ngoai roi thoat".
        # `ly_do` do chinh vong leo bao len: xong | thua | ket | dut. KET (ket o cong / het cong
        # len / danh thieu) va DUT (client chet) deu KHONG phai "2K het".
        _het = ly_do in ("xong", "thua")
        with st["lock"]:
            st["event_battle_active"] = False
            if _het:
                st["event_battle_done"].set()
            st["2k_ket_qua"] = ly_do
        if _het:
            _set_party_quest_mode(pidx, False, label)
        log.info("[%s] (LEADER) 2K: vong leo thap ket thuc (%s) -> bao DIEU PHOI", label, ly_do)

    def _heal_party_2k():
        # Gia han quest_mode + cua so dungeon cho CA party sau moi tran (member khong tu gia han
        # duoc - xem chu thich `_set_party_quest_mode`).
        _set_party_quest_mode(pidx, True, label, quiet=True)
        # HOI FULL HP/SP CA PARTY sau moi tran (song song, giong 40NPC). Leader tu hoi thi khong
        # du: member cung an don, ma quest_mode=True lam `_heal_after_battle()` thoat som.
        clients = [account_clients.get(u) for u in _active_party_usernames(pidx)]
        clients = [x for x in clients if x is not None and x.running]

        def _heal_one(cli):
            if cli.running and not cli.state.in_battle:
                cli.heal_full(force=True)

        workers = [threading.Thread(target=_heal_one, args=(cli,), daemon=True) for cli in clients]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=10)
        log.info("[%s] (LEADER) 2K: ca party (%d acc) da hoi FULL HP/SP", label, len(clients))

    def _du_party_2k():
        """Truoc khi LEN TANG: party con du khong? Chua du thi MOI LAI ngay tai cho, khong du
        trong han thi THOI leo (de dieu phoi xu ly).

        Party tan giua chung la chuyen BINH THUONG trong thap: server CAM doi kenh khi dang trong
        doi (`result=3`), nen muon doi kenh la PHAI roi doi truoc. Party 5 (06/09):
            16:34:14  4 member: Doi kenh 2 THAT BAI: DANG TO DOI (result=3)
            16:34:15  4 member: Doi kenh OK -> 2      <- da ra khoi doi
            16:34:53  leader:   qua cong idx=2 -> map 12929   <- DI MOT MINH
        Ra lenh doi kenh ma khong lap lai doi la loi cua NGUOI RA LENH.
        """
        if joined_member_count(pidx) >= st["n_members"]:
            return True
        log.warning("[%s] (LEADER) 2K: party chi con %d/%d truoc khi len tang -> MOI LAI truoc "
                    "khi di", label, joined_member_count(pidx), st["n_members"])
        _t0 = time.time()
        # CHO-HOP-LE: leader CHU DONG moi lai moi vong (khong nam cho), co han
        # `DU_PARTY_TRUOC_CONG_SEC`. Khong phai cho acc khac bao cao.
        while c.running and not stopped() and time.time() - _t0 < DU_PARTY_TRUOC_CONG_SEC:
            if joined_member_count(pidx) >= st["n_members"]:
                log.info("[%s] (LEADER) 2K: da du %d/%d -> len tang tiep", label,
                         joined_member_count(pidx), st["n_members"])
                return True
            try:
                _invite_party_participants(c, True, gap=1.0)
            except Exception:
                pass
            time.sleep(2)
        return joined_member_count(pidx) >= st["n_members"]

    with st["lock"]:
        st["event_battle_active"] = True
    c.flee_mode = False
    _set_party_quest_mode(pidx, True, label)
    if c.start_floor_crawl(ev, _on_crawl_done, _heal_party_2k,
                           lambda: _party_left_tower(pidx, ev) or _party_chet_het(pidx),
                           _du_party_2k):
        log.info("[%s] (LEADER) 2K: du party -> bat dau leo thap tu map %s", label, c.current_map)
    return False


def _danh_event_engine_moi(c, pidx):
    """LEADER mo vong battle 40NPC - Y FLOW CU (`_start_training`, nhanh `elif event_party_mode`).

    Giu nguyen hai callback cua ban cu:
      `_on_npc40_loss`      - THUA -> ha `event_battle_active`, set `event_battle_done`, tat
                              quest-mode ca party, DUNG (khong mo lai battle)
      `_before_npc40_repeat`- truoc tran ke: gia han quest-mode, roi HOI MAU CA PARTY song song
                              (`heal_npc40_between_battles`) - va chi duoc dung item SAU khi
                              npc40.run_loop da dong dialog, khong thi server tra 080001 va kick
    """
    ev = _event_cua_party(pidx)
    if ev is None:
        return False
    st = _pstate(pidx)
    label = getattr(c, "_label", "?")
    # VONG BATTLE DA CHAY ROI -> KHONG DUNG VAO NUA.
    #
    # `start_npc40_loop` / `start_floor_crawl` deu DE THREAD RIENG roi tra ve NGAY, va lan goi thu
    # hai chung tra False vi `_npc40_started` / `_floor_crawl_started` da bat. Nhung engine moi
    # nhip 1 GIAY: no thay "viec chay xong ngay" nen giao lai lien tuc, va moi lan goi lai deu
    # chay `_set_party_quest_mode(pidx, True, ...)` = gui goi gia han cho CA PARTY moi giay.
    #
    # Ca that 20/09 party 7 (user: "party xong roi, deo thay di danh, 1 luc sau leader dis"):
    #   15:29:45 -> 15:30:15  ENGINE: taot006 -> danh_event      <- 30 lan lien tiep, moi giay
    #   15:29:58 ENGINE: 'danh_event' giao lai 40 lan lien tiep cho taot006 - viec chay xong ngay
    #   15:30:16 [taot006] RECONNECT: server rot -> login lai sau 5s (lan 1)
    #   15:30:16 [party 7] DIEU PHOI: nguoi keo 'taot006' khong con chay -> tam giao cho tat ca
    # Leader rot -> 4 member quay vong `lap_party` mai. Engine cu khong dinh vi no goi
    # `_start_training` DUNG MOT LAN, khong co nhip 1 giay nao dap len.
    #
    # Hai co `_started` chi bat MOT LAN cho moi client (relogin tao client moi -> tu reset), nen
    # cua nay khong bao gio ket: vong chet that thi acc cung da la client khac.
    if getattr(c, "_npc40_started", False) or getattr(c, "_floor_crawl_started", False):
        return True
    if (ev.get("party_battle") or {}).get("kind") == "floor_crawl":
        # 2K: engine moi KHONG dung duong nay nua - no giao TUNG BUOC (`VIEC_2K_DANH` /
        # `VIEC_2K_LEN_TANG`). Toi day nghia la `tinh_buoc` khong ra buoc nao (da xong / het
        # duong / leader chua vao thap) -> DUNG YEN cho dieu phoi quyet, tuyet doi khong khoi
        # dong `chay_leo_thap_2k`: ham do de THREAD RIENG cam lai ca thap, dung lai dung cai
        # da bo. `chay_leo_thap_2k` van con nguyen cho ENGINE CU goi.
        return True
    if not (ev.get("party_battle") or {}).get("point"):
        return False
    if st["event_battle_done"].is_set():
        c.flee_mode = False
        return True                     # da THUA -> dung yen, khong mo lai battle
    point = tuple(ev["party_battle"]["point"])

    def _on_npc40_loss():
        with st["lock"]:
            st["event_battle_active"] = False
            st["event_battle_done"].set()
        _set_party_quest_mode(pidx, False, label)
        log.warning("[%s] (LEADER) ENGINE: 40NPC PARTY THUA -> chon KHONG va DUNG", label)

    def _before_npc40_repeat():
        _set_party_quest_mode(pidx, True, label, quiet=True)
        clients = [account_clients.get(u) for u in _active_party_usernames(pidx)]
        clients = [x for x in clients if x is not None and x.running]

        def _heal_one(cli):
            if cli.running and not cli.state.in_battle:
                cli.heal_npc40_between_battles()

        workers = [threading.Thread(target=_heal_one, args=(cli,), daemon=True) for cli in clients]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=8)
        time.sleep(0.5)     # cho server xu ly item cuoi truoc khi xac nhan dialog
        log.info("[%s] (LEADER) ENGINE: 40NPC ca party da hoi phuc -> mo tran tiep", label)

    with st["lock"]:
        st["event_battle_active"] = True
    c.flee_mode = False
    _set_party_quest_mode(pidx, True, label)
    if c.start_npc40_loop(point, _on_npc40_loss, _before_npc40_repeat):
        log.info("[%s] (LEADER) ENGINE: 40NPC du party -> den %s va bat dau lap battle",
                 label, point)
    return True


def _doi_thuong_engine_moi(c, pidx):
    """EVENT XONG / NGOAI GIO -> huy party, di doi thuong, THOAT GAME.

    Y flow cu (`run_account` nhanh event, dong 5723-5731): "40NPC NGOAI GIO event -> huy party +
    di doi thuong + thoat game", va user 14/09: "event thi danh xong out, train deo gi o day".
    """
    ev = _event_cua_party(pidx)
    label = getattr(c, "_label", "?")
    try:
        c.leave_party()
    except Exception:
        pass
    if ev is not None and (ev.get("party_battle") or {}).get("kind") == "floor_crawl":
        # 2K KHONG co NPC doi thuong - Y FLOW CU (`run_account` dong 5748): "2K da ket thuc ->
        # ra khoi thap roi THOAT GAME". Goi `claim_40npc_reward` o day la sai hoan toan: no keo
        # acc ve Trac Quan (Quang Truong) roi ra NPC 12003 cua 40NPC.
        # User 20/09: "lam lon gi ma bon no chay ve quang truong roi out het".
        if _inside_floor_crawl_tower(ev, c.current_map):
            try:
                c.exit_event(ev)
            except Exception as e:
                log.warning("[%s] ENGINE: 2K loi di ra khoi thap: %s", label, e)
        log.info("[%s] ENGINE: 2K ket thuc -> ra khoi thap -> THOAT GAME", label)
        stop_account(getattr(c, "_username", "") or label, "2K ket thuc -> ra khoi thap")
        return True
    if ev is not None and not getattr(c, "_npc40_bo_thuong", False):
        try:
            c.claim_40npc_reward(ev)
        except Exception as e:
            log.warning("[%s] ENGINE: loi doi thuong 40NPC: %s", label, e)
    log.info("[%s] ENGINE: event xong -> THOAT GAME", label)
    stop_account(getattr(c, "_username", "") or label, "event xong (mode event)")
    return True


# ------------------------------------------------- THANH TAP KET (dung chung hai engine)
def chot_thanh_tap_ket(pidx, st, c, sc, route_safe, gen, vi_la_leader,
                       label="", role="", route2=None):
    """Chot THANH TAP KET cho ca party roi cong bo vao st["route_plan"].

    MEMBER KHONG CAN BIET DUONG DI - no vao party roi bi leader KEO theo. Xem chinh
    dong ngay duoi khoi nay:
        smart_route2 = plan.get("route") if is_leader else None
    tuc member NEM LUON cai route vua cho. Thu duy nhat member can la `city`/`flag`:
    ca party phai gom o CUNG MOT THANH thi leader moi moi duoc (server chan invite
    khac map).

    Vay ma truoc 05/09 chi `is_leader` duoc chot, member ngoi cho VO HAN. Luong leader
    ban viec khac la ca party dung. Da xay ra that (party 10, 05/09 18:22-18:23):
    leader luumot bi `ABORT di duong reform: reform_gen 1 -> 5` roi di lam dungeon +
    sync kenh, KHONG he cong bo cho gen moi; 3 member spam "cho leader lap duong toi
    map 21812" khong dut - de cho mot thu chung no se xoa.

    VI SAO VAN CHOT MOT CHO (khong de moi acc tu tinh): danh sach thanh DA MO khac
    nhau theo acc -> moi dua tu chon la party toe ra hai thanh, leader dung o A member
    dung o B, moi mai khong ai vao doi. Cho nen: mot ban chot dung chung, ai cong bo
    truoc thi thang, va leader duoc uu tien `ROUTE_PLAN_TIEP_QUAN_SEC` giay.

    MEMBER CONG BO THI KHONG KEM ROUTE (`route: None`): route la duong LEADER SE DI BO,
    ma duong di phu thuoc thanh DA MO cua tung acc - duong cua member co the leader di
    khong duoc. Leader tu dung duong cua minh toi cung thanh do.
    """
    _sr = None
    try:
        if getattr(config, "SMART_WORLD_ROUTING", True):
            _sr = c.build_smart_route(sc, route_safe)
    except Exception as e:
        log.warning("[%s] reform: loi build smart route: %s", label, e)
        _sr = None
    if _sr:
        _p = {"gen": gen, "city": int(_sr["city"]), "flag": int(_sr["flag"]),
              "route": _sr if vi_la_leader else None}
    elif route2:
        _p = {"gen": gen, "city": int(route2.get("from_city", 0)),
              "flag": int(route2.get("city_flag", 0)), "route": None}
    else:
        # KHONG CO ROUTE VAN PHAI GOM (L0). Route la duong DI BO toi bai train; gom ve
        # cung mot THANH thi khong can duong nao ca - chi can teleport. Bo qua o day =
        # lenh gom cua dieu phoi khong bao gio duoc thi hanh, va vong goi thi lap lai.
        #
        # Ca that 08/09 party 1 (user: "van deo them ve cung kenh") - vong 18 giay,
        # leader xGAx dung mot minh o Trac Quan 12001, bon member o Truong Sa 23001:
        #   00:53:58 (LEADER) MODE=train start_city=0
        #   00:54:22 (LEADER) reform: khong co smart/legacy route -> bo qua
        #   00:54:24 (LEADER) party dang o 2 MAP KHAC NHAU [12001, 23001] -> se gom
        #   00:54:40 (LEADER) reform: khong co smart/legacy route -> bo qua
        #   00:54:42 (LEADER) party dang o 2 MAP KHAC NHAU [12001, 23001] -> se gom
        # `start_city=0` nen khong co `fc`, khong co route - the la no NHAN RA phai gom
        # roi TU CHOI gom. Bug nay da duoc sua RIENG cho thap 2K (`_thi_hanh_gom`);
        # ngoai thap thi van con nguyen.
        #
        # Diem gom = THANH DANG CO NHIEU ACC NHAT (it phai di chuyen nhat, va thuong la
        # da so party da tu ve day roi); khong ai o thanh thi roi ve `_gather_city`.
        _tg = _thanh_dong_acc_nhat(pidx) or _gather_city(pidx, sc or 0, gen)
        log.warning("[%s] (%s) reform: khong co smart/legacy route -> VAN GOM, "
                    "diem gom = thanh %s", label, role, _tg)
        _p = {"gen": gen, "city": int(_tg), "flag": 0, "route": None}
    with st["lock"]:
        _cu = st.get("route_plan")
        if _cu and _cu.get("gen") == gen:
            # Acc khac chot truoc roi -> THEO no (ca party phai cung mot thanh).
            # Route cua minh chi dung duoc neu no dan toi DUNG thanh do; khac thanh
            # ma van di theo la leader di mot noi, party gom mot noi.
            _theo = _sr if (vi_la_leader and _sr
                            and int(_sr.get("city", 0)) == int(_cu.get("city", 0))
                            ) else None
            return dict(_cu), _theo
        st["route_plan"] = _p
    st["route_plan_ready"].set()
    if not vi_la_leader:
        log.warning("[%s] (%s) reform: leader KHONG chot thanh tap ket sau %ds -> TU CHOT "
                    "thanh %s cho ca party (member khong can duong di, chi can cung thanh)",
                    label, role, int(ROUTE_PLAN_TIEP_QUAN_SEC), _p.get("city"))
    return _p, _sr


def _thanh_dich_engine_moi(pidx):
    """(city_id, flag) cua THANH TAP KET. None = chua biet.

    GOI THANG `chot_thanh_tap_ket` - dung MOT ham voi engine cu (truoc day la closure
    `_chot_thanh_tap_ket` trong `_do_reform`, nay da tach ra cap module). Ham do da lo:
        thanh cua CHINH ROUTE (`build_smart_route(sc, route_safe)["city"]`) - phai gom ve dung
            thanh ma duong di xuat phat, khong thi gom xong leader lai teleport di noi khac ma
            teleport bat buoc ROI DOI -> party vua du lai tan
        fallback `TRAIN_ROUTES[sc].from_city`
        fallback "KHONG CO ROUTE VAN PHAI GOM" -> `_thanh_dong_acc_nhat` / `_gather_city`
        mot ban chot DUNG CHUNG trong `st["route_plan"]` theo gen: ai cong bo truoc thi thang

    Chep lai la de ra ban thu hai cho cung cau hoi. Da tra gia dung the:
    `_pick_start_city` (loc theo "thanh CA PARTY deu da mo") ra thanh KHAC voi thanh router dung,
    nen party gom o thanh A con leader di duong tu thanh B.
    Ca that 17/09 party 45 (user: "p45 van moi dua 1 thanh"):
        09:01:45 >>> PARTY 45: thanh xuat phat = Hoi Ke (id 18021, 9 cong toi 15457)
        09:02:06 TRANG THAI: chdumot@12061(L) chduhai@18021 chduba@18021 chdubon@18021 chdunam@18021
    Party 44 cung the, quay 101 lan (`reform g=101`).

    FLAG LA BAT BUOC: moi thanh mot flag rieng trong `config.TELEPORT_CITIES`. Truyen thieu la bay
    ve NHAM THANH (user 16/09: "deo gi ma tele lien tuc lai con bi sai flag") - `route_plan` da
    mang san `flag` di kem `city`.
    """
    _st = _pstate(pidx)
    _sc = _map_train_dich(pidx, _st)
    _c = next((account_clients[u] for u, *_ in party_accounts(pidx)
               if account_clients.get(u) is not None), None)
    if _sc and _c is not None:
        _safes = _safe_map_dich_engine_moi(pidx)
        try:
            _p, _ = chot_thanh_tap_ket(
                pidx, _st, _c, int(_sc), _safes[0] if _safes else None,
                int(_st.get("reform_gen") or 0), True,
                label=getattr(_c, "_label", ""), role="ENGINE",
                route2=(getattr(config, "TRAIN_ROUTES", {}) or {}).get(int(_sc)))
        except Exception as e:
            log.debug("[party %d] ENGINE: chot thanh tap ket loi: %s", pidx + 1, e)
            _p = None
        if _p and _p.get("city"):
            _fc = int(_p["city"])
            # THANH GAN BAI CHUA MO -> GOM O THANH KHAC roi leader KEO DI BO (flow cu:
            # `_activate_nghiep_fallback` + `_reform_via_nghiep`):
            #     elif fc and c.city_unlocked(fc) is False:
            #         _activate_nghiep_fallback("thanh %s CHUA MO tele voi acc nay" % fc)
            # Bat acc chua mo `go_to_town(fc)` la no KHONG BAO GIO toi: `go_to_town` bo cuoc ngay
            # ("thanh %s CHUA MO tele -> bo qua ngay") va acc nam lai thanh cu.
            # Ca that 17/09 party 45 (user: "day la truong hop thanh gan bai train chua duoc mo nen
            # can phai di mo thanh do truoc"):
            #   09:44:00 chdumot@15021(L) chduhai@18021 chduba@18021 chdubon@18021 chdunam@18021
            # Leader mo Tho Xuan nen toi duoc, bon member chua mo nen ket o Hoi Ke.
            _chua_mo, _ = _party_city_unlocked(pidx, _fc)
            if _chua_mo:
                _gc = _gather_city(pidx, int(_sc), int(_st.get("reform_gen") or 0))
                if _gc and int(_gc) != _fc:
                    if _st.get("fc_chua_mo_log") != (_fc, int(_gc)):
                        _st["fc_chua_mo_log"] = (_fc, int(_gc))
                        log.warning("[party %d] ENGINE: thanh %s CHUA MO voi %s -> CA PARTY gom o "
                                    "thanh %s roi leader KEO DI BO toi %s",
                                    pidx + 1, _fc, sorted(_chua_mo), _gc, _fc)
                    _st["diem_gom_hien_tai"] = int(_gc)
                    return (int(_gc), int(((getattr(config, "TELEPORT_CITIES", None) or {})
                                           .get(int(_gc), {}) or {}).get("flag", 0)))
            _st["diem_gom_hien_tai"] = _fc
            return (_fc, int(_p.get("flag") or 0))
    # Chua co map train dich / chua co client nao -> chua ket luan duoc (L13).
    return None

def _fc_di_bo_engine_moi(pidx):
    """THANH CUA ROUTE ma party phai DI BO toi (None = khong can di bo).

    Chi khac None khi thanh do CHUA MO voi it nhat mot acc: luc do `_thanh_dich_engine_moi` da
    chuyen diem gom sang `_gather_city`, va buoc tiep theo la leader KEO CA PARTY DI BO tu thanh
    gom toi thanh nay - y `_reform_via_nghiep` cua flow cu:
        c.follow_smart_scene_route(c.current_map, fc, None, abort=_ab, flee=not _full)
    """
    _st = _pstate(pidx)
    _sc = _map_train_dich(pidx, _st)
    if not _sc:
        return None
    _rp = _st.get("route_plan") or {}
    _fc = int(_rp.get("city") or 0)
    if not _fc:
        return None
    _chua_mo, _ = _party_city_unlocked(pidx, _fc)
    return _fc if _chua_mo else None


def _login_chores_engine_moi(c, pidx):
    if not _ra_safe_engine_moi(c, pidx, "viec vat sau login"):
        return False
    pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    lam_login_chores(c, getattr(c, "_username", ""), getattr(c, "_label", ""),
                     "LEADER" if getattr(c, "_pe_la_leader", False) else "member",
                     pcfg, mode=pcfg.get("mode", ""))
    return True


def _nhiem_vu_ngay_engine_moi(c, pidx):
    """NHIEM VU NGAY cho engine moi - LAM Y khoi "viec hang ngay" cua `run_account`.

    Engine moi khong chay `run_account` nen mat sach khoi do:
        `c.do_daily_dungeon()`        - o 1 (pho ban don 2 luot)
        `c.claim_daily_quests(heavy)` - claim 9 o, keo theo o2 (boss the gioi) va o5 (PB to doi)
    Do tren log 17/09: 60 acc thuoc party 41-56 (engine moi) KHONG co MOT DONG `Nhiem vu hang
    ngay` nao ca ngay, trong khi party engine cu deu 8-9/9 o.

    `heavy` lay y nguyen luat cua flow cu (`_do_startup_daily`, user chot 27/08: "chi can tele neu
    can danh world boss thoi"): dang o BAI TRAIN ma KHONG bat boss the gioi -> chi lam phan NHE
    (gacha, hop, claim - khong roi cho). Bat boss hoac khong o bai -> heavy.

    Tat bang chinh o user van dung: `do_daily` (checkbox "Danh daily dungeon" cua party).
    """
    _pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    if not _pcfg.get("do_daily", _pcfg.get("do_dungeon", True)):
        return
    _label = getattr(c, "_label", "?")
    _sc = _map_train_dich(pidx, _pstate(pidx))
    _o_bai = bool(_sc) and int(getattr(c, "current_map", 0) or 0) == int(_sc)
    _heavy = bool(_pcfg.get("auto_world_boss", True)) or not _o_bai
    if not _heavy:
        log.info("[%s] ENGINE: o bai train + KHONG bat boss the gioi -> nhiem vu ngay lam phan "
                 "NHE thoi, khong teleport di dau", _label)
    # BOSS THE GIOI: danh HET LUOT, khong phai mot luot.
    #
    # `claim_daily_quests` co goi `do_world_boss()` cho o 2, nhung do la MOT luot - du de tick o 2
    # chu khong lay het luot trong ngay. Flow cu goi `do_world_boss_all()` rieng
    # (`_maybe_auto_world_boss`). Engine moi truoc day khong co duong nay.
    if _pcfg.get("auto_world_boss", True):
        try:
            log.info("[%s] ENGINE: Boss the gioi - auto danh het luot", _label)
            c.do_world_boss_all()
        except Exception as e:
            log.warning("[%s] ENGINE: loi auto world boss (bo qua): %s", _label, e)
    try:
        c.do_daily_dungeon()
    except Exception as e:
        log.warning("[%s] ENGINE: loi daily dungeon (bo qua): %s", _label, e)
    # TAT HOOK O5 khi claim: engine moi co viec RIENG cho pho ban to doi (`VIEC_PB_DOI` ->
    # `do_team_dungeon`), goi THANG, khong qua lop cho-bao-cao.
    #
    # `claim_daily_quests` goi `_o5_team_fn` -> `_handle_o5_team`, ma ham do chay tren BARRIER BAO
    # CAO: moi acc phai tu gan `_o5_da_xong` len client cua no, leader doc dau vet do. Engine moi
    # KHONG chay `_run_auto_team_dungeons_if_needed` nen khong acc nao co dau vet => leader "coi
    # nhu DA XONG" va bo PB - vua thua vua sai.
    # Ca that 17/09 party 45 (user: "p45 van ko danh PB doi" -> "con can phai bao nua sao"):
    #   23:49:19 [chdumot] (LEADER) o5: 5/5 acc chua bao ([cd701..cd705]) -> coi nhu DA XONG
    #   23:49:32 [party 45] ENGINE: cd701 -> pb_doi     <- duong DUNG cua engine moi, chay song song
    _o5_cu = getattr(c, "_o5_team_fn", None)
    try:
        c._o5_team_fn = None
        c.claim_daily_quests(heavy=_heavy)
    except Exception as e:
        log.warning("[%s] ENGINE: loi claim daily quest (bo qua): %s", _label, e)
    finally:
        c._o5_team_fn = _o5_cu


def _nhip_acc_engine_moi(c, pidx):
    """NHIP KEEPALIVE cua tung acc - khoi ma engine moi KHONG CO gi tuong duong.

    `run_account` co mot vong keepalive 1080 dong chay lien tuc ben canh viec chinh. Engine moi
    bo han vong do (acc chi thi hanh viec duoc giao), nen MAT SACH nhung viec chay dinh ky trong
    do. Soi bang AST 20/09 (user: "t da bao tu soi code xem cai nao flow cu co ma engine moi ko
    co"): vong keepalive goi 34 method cua client, engine moi thieu 18.

    Ham nay chay MOI NHIP worker, gom nhung viec RE va khong roi cho:
        `reset_daily_counters_if_needed` + `claim_online_gifts` - qua online 10/20/30/60/90/180'
        `sync_machinebox_flags` - co "chet ve thanh" cua Hop May doi theo PHA (chet giua PB ma bi
            keo ve thanh la vo luot PB ca party)
        `ensure_pet_role` - tra pet ve vai thuong sau PB/quest

    Cac ham tren deu TU KIEM truoc khi gui goi (`ensure_pet_role` khong gui gi neu dang dung dung
    pet, `sync_machinebox_flags` chi gui KHI THUC SU DOI) nen goi moi nhip la re.
    """
    _pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    _mode = _pcfg.get("mode") or ""
    _bt_now = bool(getattr(getattr(c, "state", None), "in_battle", False))
    _bt_truoc = bool(getattr(c, "_pe_battle_before", False))
    if _bt_now and not _bt_truoc:
        pos = getattr(c, "pos", None)
        st = _pstate(pidx)
        safe = st.get("rally_point") or _nearest_safe(pos, _safe_map_dich_engine_moi(pidx) or [])
        current_map = getattr(c, "current_map", None)
        trusted = current_map is not None and getattr(c, "_pos_valid_for_map", None) == current_map
        username = getattr(c, "_username", "")
        _ghi_nhan_tran_tai_safe(username, current_map, pos, safe, pos_dang_tin=trusted)
    c._pe_battle_before = _bt_now
    try:
        c.reset_daily_counters_if_needed()
        c.claim_online_gifts()
    except Exception as e:
        log.debug("[%s] ENGINE: loi reset/qua online (bo qua): %s", getattr(c, "_label", "?"), e)
    try:
        c.sync_machinebox_flags()
    except Exception:
        pass
    try:
        c.ensure_pet_role("quest" if _mode == "event" else "train")
    except Exception as e:
        log.debug("[%s] ENGINE: tra pet ve vai thuong loi: %s", getattr(c, "_label", "?"), e)

def _pb_vo_thi_keo_ca_party_ra(pidx):
    """PB TO DOI dang chay ma co acc ROT -> keo CA PARTY ra khoi pho ban, lam lai tu dau.

    User chot 21/09: "trong qua trinh di ma co dua vang thi thoat het PB lam lai tu dau", ap tu
    luc MO PHONG den khi danh xong.

    Engine CU co duong nay (`st["reconnecting"]` / `team_dungeon_need_redo` -> `_thoat_pb_ca_party`);
    engine MOI truoc day KHONG goi `_thoat_pb_ca_party` lan nao - ma gio moi party deu chay engine
    moi. PB vo thi server KHONG gui goi ket thuc (`S:047-012`) nen khong acc nao tu biet duong ra:
    leader dung ngoai thanh con member ket trong map 62xxx, va `go_to_town` cua ho BAIL vi "dang
    trong pho ban to doi" (ca that 07/09 p42).

    Chi keo khi CO acc dang lam PB - khong thi moi lan mot acc relogin la ca party bi loi ra oan.
    """
    eng = _party_engines.get(pidx)
    if eng is None:
        return
    try:
        _viec = dict(getattr(eng, "viec_hien_tai", {}) or {})
    except Exception:
        return
    _dang_pb = [u for u, v in _viec.items()
                if v in (party_engine.VIEC_PB_DOI, party_engine.VIEC_PB_DOI_THEO)]
    if not _dang_pb:
        return
    _chet = [u for u, _p, _l, _k in party_accounts(pidx) if not is_account_running(u)]
    if not _chet:
        return
    log.warning("[party %d] PB TO DOI: co acc ROT (%s) trong luc dang lam PB -> keo CA PARTY ra, "
                "lam lai tu dau", pidx + 1, ", ".join(_chet[:3]))
    try:
        _thoat_pb_ca_party(pidx, "co acc rot giua PB (engine moi)")
    except Exception as e:
        log.warning("[party %d] PB TO DOI: loi keo ca party ra: %s", pidx + 1, e)


def _engine_doc_party(pidx):
    """Read the shared game state; the party engine owns the decision."""
    st = _pstate(pidx)
    return _chup_anh_cap_party(pidx, st, _acc_song(pidx), _ENGINE_LECH_TU.get(pidx))


def _engine_recheck_unseen_channels(pidx, anh, song):
    """Invalidate cached DG channels only for isolated, unjoined accounts.

    ai_lech_instance already requires a visible majority and a 30-second grace.
    The normal engine channel action then verifies the channel on its worker.
    """
    if getattr(anh, "pha", None) != party_engine.PHA_DG or getattr(anh, "du_doi", True):
        return
    unseen = set(getattr(anh, "ai_lech_instance", None) or ())
    if not unseen or not song:
        return
    maps = {getattr(c, "current_map", None) for _, c in song}
    channels = {getattr(c, "current_channel", None) for _, c in song}
    if len(maps) != 1 or not all(maps) or len(channels) != 1 or not all(channels):
        return
    now = time.time()
    checked = _pstate(pidx).setdefault("engine_unseen_channel_checked", {})
    for user, client in song:
        if user not in unseen or getattr(client, "party_members", None):
            continue
        if now - checked.get(user, 0.0) < 30.0:
            continue
        checked[user] = now
        client.kenh_dang_nghi_ngo = True
        log.warning("[party %d] ENGINE: %s chua vao doi va khong thay dong doi qua 30s "
                    "-> kiem tra lai kenh %s tren worker cua acc nay",
                    pidx + 1, user, client.current_channel)


def _engine_ap_dung_party(pidx, anh, viec, ly_do, hu):
    """Apply the decision from this party's engine without creating another controller."""
    st = _pstate(pidx)
    song = _acc_song(pidx)
    cmd = st.get("cmd")
    if cmd and cmd[0] == "route" and any(
            int(getattr(c, "_pe_lenh_tay_gen", 0) or 0) < int(st.get("cmd_gen", 0) or 0)
            for _, c in song):
        return
    _thi_hanh_hieu_ung(pidx, st, song, hu, viec, anh)
    _ENGINE_LECH_TU[pidx] = hu.lech_tu
    kh = {"pha": anh.pha if not hu.doi_pha_train else "train",
          "map": (sorted(anh.maps, key=lambda m: -len(anh.maps[m]))[0] if anh.maps else None),
          "kenh": (sorted(anh.kenhs)[0] if len(anh.kenhs) == 1 else None),
          "thanh": anh.thanh_cu, "viec": viec}
    if hu.chot_tang_gom:
        kh["tang_gom"] = _chot_tang_gom(pidx, st, song)
    if hu.chot_2k_xong:
        _engine_chot_2k_xong(pidx, st, song)
    _ghi_ke_hoach(st, pidx, kh, ly_do)
    _engine_chot_map(pidx, st)
    _engine_chot_kenh(pidx, st, song, kh)
    _engine_recheck_unseen_channels(pidx, anh, song)



def _chua_nen_ra_lenh_engine_moi(pidx):
    """KHONG CO CUA CHAN NAO O DAY - luon tra "" (ra lenh duoc).

    Giu ham de cho goi khong phai doi, nhung than no da bo HET.

    Ban dau ham nay goi `_leader_dang_rot` / `_dang_doi_kenh` / `_thieu_acc_song` /
    `_ai_lech_instance` lam "bon cua chan truoc khi ra lenh". DO LA BIA: ca bon phep thu do nam
    BEN TRONG `_dieu_phoi_quyet` (dong 10280/10287/10312/10346) va chinh no da ra lenh xu ly:
        leader rot      -> VIEC_MOI (reset roster, moi lai ngay khi leader vao)
        dang doi kenh   -> VIEC_LAM (cho roster on dinh)
        thieu acc song  -> VIEC_LAM
        lech instance   -> VIEC_DONG_BO (doi kenh cho lech instance vao)
    Goi lai chung o ngoai = tang chan DE LEN dung cai lenh giai quyet tinh huong do. Vi `cho_ly_do`
    lam `quyet_dinh` GIU NGUYEN viec dang lam, party ket cung vinh vien.

    Ca that 16/09 party 43 (user: "p43 bi lech kenh ma ko dong bo lai"):
      21:21:19 dieu phoi chot 'dong_bo' - ['tq405'] KHONG THAY duoc dong doi (khac instance du
               cung so kenh) -> dong bo kenh truoc khi moi
      21:21:36 'lap_party' giao lai 40 lan lien tiep ...   <- cua chan nuot mat lenh `dong_bo`
      21:22:57 'lap_party' giao lai 120 lan lien tiep ...
    """
    return ""


def _ve_safe_khi_stop_engine_moi(c, pidx):
    """STOP -> chay ve safe roi moi dong. LAM Y `run_account` (dong 7207-7229):

        LEADER train : chay ve safe GAN NHAT roi bao `stop_leader_done`
        member train : CHO leader ve safe (toi da 60s) roi moi thoat

    De acc dung ngay tai bai quai thi lan login sau vao la bi quai danh ngay. Chi ap dung khi
    dang o MAP TRAIN - trong Di Gioi / thanh thi dung dau cung duoc.
    """
    st = _pstate(pidx)
    _u = getattr(c, "_username", "") or ""
    _lab = getattr(c, "_label", _u)
    _la_leader = (_u == config.PARTY_LEADER_ACC.get(pidx))
    _sc = _map_train_dich(pidx, st)
    _tren_bai = bool(_sc) and int(getattr(c, "current_map", 0) or 0) == int(_sc)
    if _la_leader:
        if _tren_bai:
            _safes = [tuple(p) for p in
                      ((getattr(config, "TRAIN_MAPS", {}) or {}).get(int(_sc), {}) or {}).get("safe", [])
                      if len(p) == 2]
            _dest = _nearest_safe(getattr(c, "pos", None), _safes) if _safes else None
            if _dest:
                log.info("[%s] (LEADER) ENGINE: STOP -> chay ve safe gan nhat %s truoc khi thoat",
                         _lab, _dest)
                try:
                    c.navigate_to(*_dest)
                except Exception as e:
                    log.warning("[%s] ENGINE: loi chay ve safe (bo qua): %s", _lab, e)
        st["stop_leader_done"].set()     # leader da ve safe -> ca party duoc thoat
        log.info("[%s] (LEADER) ENGINE: da ve safe -> bao member thoat", _lab)
        return
    if config.PARTY_LEADER_ACC.get(pidx) and _tren_bai:
        log.info("[%s] (member) ENGINE: STOP -> cho leader ve safe roi thoat...", _lab)
        if not st["stop_leader_done"].wait(STOP_CHO_LEADER_SEC):
            log.warning("[%s] (member) ENGINE: cho leader ve safe qua %.0fs -> thoat luon",
                        _lab, STOP_CHO_LEADER_SEC)


def _ho_phu_engine_moi(c):
    """Dung Di Gioi Ho Phu - y dieu kien cua `_maybe_use_di_gioi_ho_phu` trong engine cu:
    chi dung khi con DUOI 15 phut va KHONG dang trong tran."""
    _con = max(0, int(DIGIOI_LIMIT - c.digioi_minutes_live()))
    if _con >= HO_PHU_NGUONG_PHUT or c.in_combat():
        return False
    _truoc = int(getattr(c, "digioi_minutes", 0) or 0)
    if not c.use_di_gioi_ho_phu():
        return False
    log.info("[%s] ENGINE: Di Gioi Ho Phu - con %d phut (<%d), da gui lenh dung",
             getattr(c, "_label", "?"), _con, HO_PHU_NGUONG_PHUT)
    _han = time.time() + 8.0
    while time.time() < _han and int(getattr(c, "digioi_minutes", 0) or 0) == _truoc:
        time.sleep(0.5)
    return True


def _chay_pb_doi_engine_moi(c, pidx, level):
    """LEADER danh PB to doi - engine moi DOC THANG, KHONG qua lop cho-bao-cao cua engine cu.

    `_handle_auto_team_dungeon` co mot barrier dua tren BAO CAO: moi acc phai tu gan `_o5_da_xong`
    len client cua no, leader doc dau vet do de biet ai chua xong. Acc nao chua bao thi leader
    "coi nhu DA XONG" va BO pho ban.

    Voi engine moi co che do vua thua vua HONG:
      * thua - mot luong nam ca 5 client, doc thang la biet, khong ai phai bao ai (L2)
      * hong - engine moi khong chay `_run_auto_team_dungeons_if_needed` nen KHONG acc nao co dau
        vet => leader BO PB moi luot, con member thi dung o `pb_doi_theo` cho duoc keo vao phong.
        Ca that 16/09 party 41, quay vong 6 giay/lan tu 09:34:
            09:37:27 [dtsau] (LEADER) o5: 5/5 acc chua bao (['dt806'..'dt810']) -> coi nhu DA XONG
            09:37:33  ... y het ...   (lap lien tuc, khong danh tran nao)

    Nen o day goi THANG kich ban danh PB (`do_team_dungeon` -> lv20/50/80/110). Con "con luot hay
    khong" thi engine da doc DONG HO SERVER (`team_dungeon_remaining` <- `mission_steps`), chinh
    xac hon bao cao giua cac acc.
    """
    return bool(c.do_team_dungeon(int(level)))

def _duong_ra_spot_engine_moi(pidx):
    """Duong capture tu rally toi tam quai (`MOB_PATHS`), None = khong co -> navigate thang.

    Dung dung nguon engine cu doc: `config.MOB_PATHS[map][spot]`.
    """
    st = _pstate(pidx)
    spot = st.get("mob_spot")
    sc = _map_train_dich(pidx, st)
    if not spot or not sc:
        return None
    return (getattr(config, "MOB_PATHS", {}) or {}).get(int(sc), {}).get(tuple(spot))


def _engine_mode_decisions(pidx, anh, decisions):
    st = _pstate(pidx)
    cmd = st.get("cmd")
    if (cmd and cmd[0] == "route" and anh.lenh_tay_gen
            and any(a.lenh_tay_da_lam < anh.lenh_tay_gen for a in anh.accs if a.song)):
        return _engine_route_decisions(pidx, anh, cmd)
    pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    mode = pcfg.get("mode") or "stand"
    ev = _event_cua_party(pidx) if mode == "event" else {}
    kind = ((ev or {}).get("party_battle") or {}).get("kind")
    no_leader = mode == "event" and kind != "chaos_vs" and not config.PARTY_LEADER_ACC.get(pidx)
    if no_leader and not st.get("engine_no_leader_log"):
        log.warning("[party %d] ENGINE: event KHONG CO LEADER -> dung yen, cho cau hinh leader", pidx + 1)
    st["engine_no_leader_log"] = no_leader
    done = {u for u, c in _clients_cua_party(pidx)
            if c is not None and getattr(c, "_loandau_done", False)} if kind == "chaos_vs" else ()
    pending = {a.username for a in anh.accs
               if anh.lenh_tay_gen and a.lenh_tay_da_lam < anh.lenh_tay_gen}
    result = party_modes.decide_mode(
        mode, decisions, anh.accs,
        target_map=int(pcfg.get("start_city_id") or 0) or None,
        event_kind=kind, event_map=(ev or {}).get("dest_map"),
        event_open=loandau.in_event_window(ev=ev) if kind == "chaos_vs" else True,
        event_done=done, manual_pending=pending,
        has_leader=bool(config.PARTY_LEADER_ACC.get(pidx)))

    result = _engine_routine_decisions(pidx, anh, result, pcfg)
    return _engine_rally_decisions(pidx, anh, result)


def _engine_rally_decisions(pidx, anh, decisions):
    if not any(v in ("lap_party", "doi_kenh") for v in decisions.values()):
        return decisions
    st = _pstate(pidx)
    target = _map_train_dich(pidx, st)
    accounts = [a for a in anh.accs if a.song and decisions.get(a.username)
                in ("lap_party", "doi_kenh", "nghi")]
    if not target or not accounts or any(a.map_id != target for a in accounts):
        return decisions
    safes = _safe_map_dich_engine_moi(pidx) or []
    point = st.get("safe_doi_kenh") or st.get("rally_point") or (safes[0] if safes else None)
    if not point:
        return decisions
    st["safe_doi_kenh"] = tuple(point)
    waiting = dict(decisions)
    for account in accounts:
        client = account_clients.get(account.username)
        correct_position = getattr(client, "_theo_leader_sua_pos", None)
        if correct_position:
            correct_position()
        pos = getattr(client, "pos", None)
        waiting[account.username] = ("nghi" if pos and math.dist(pos, point) <= RALLY_BAN_KINH
                                     else "ve_safe")
    return waiting if "ve_safe" in waiting.values() else decisions


def _engine_routine_decisions(pidx, anh, decisions, pcfg):
    result = dict(decisions)
    st = _pstate(pidx)
    lead = config.PARTY_LEADER_ACC.get(pidx)
    leader = account_clients.get(lead)
    leader_entity = getattr(leader, "self_entity", None)
    for account in anh.accs:
        user = account.username
        client = account_clients.get(user)
        action = result.get(user)
        if client is None or not account.song or action not in ("nghi", "train", "lap_party", "ra_spot"):
            continue
        previous = getattr(account, "viec_dang_lam", None)
        if getattr(account, "dang_ban", False) and previous in ("boss_quan_doan", "quet_bai_train"):
            result[user] = previous
            continue
        if account.dang_danh or getattr(account, "dang_ban", False):
            continue
        if action == "lap_party":
            captain = client._doi_truong_dang_ket()
            own = getattr(client, "self_entity", None)
            if captain and captain not in (own, leader_entity):
                result[user] = "roi_party_la"
                continue
        if (action in ("nghi", "train")
                and getattr(anh, "dp_viec", None) in (None, party_engine.DP_LAM)
                and pcfg.get("mode") not in ("event", "digioi")
                and getattr(anh, "pha", None) == party_engine.PHA_TRAIN
                and pcfg.get("fight_legion_boss", True)
                and client.legion_boss_available()):
            result[user] = "boss_quan_doan"
            continue
        target = _map_train_dich(pidx, st)
        train_map = (getattr(config, "TRAIN_MAPS", {}) or {}).get(int(target or 0))
        if (user == lead and pcfg.get("mode") in ("train", "digioi_train")
                and getattr(anh, "pha", None) == party_engine.PHA_TRAIN
                and target and account.map_id == target and train_map is not None
                and not st.get("mob_spot") and getattr(config, "MOB_SCAN_ENABLED", True)):
            result[user] = "quet_bai_train"
    return result



def _engine_route_decisions(pidx, anh, cmd):
    st = _pstate(pidx)
    plan = st.get("manual_route_plan")
    if not plan:
        users = [a.username for a in anh.accs]
        leader = config.PARTY_LEADER_ACC.get(pidx) or next(iter(users), None)
        client = account_clients.get(leader)
        if client is None or not getattr(client, "running", False):
            return {a.username: "nghi" for a in anh.accs if a.song}
        source, dest = int(cmd[1] or 0), int(cmd[2])
        if not source:
            picked = client.nearest_smart_city(dest, exclude_map=dest)
            if not picked:
                return {a.username: "nghi" for a in anh.accs if a.song}
            source = int(picked["city"])
        gather = client.nearest_smart_city(source)
        if not gather:
            return {a.username: "nghi" for a in anh.accs if a.song}
        plan = {"source": source, "dest": dest, "city": int(gather["city"]),
                "flag": int(gather["flag"]), "users": users, "leader": leader,
                "phase": "gather", "temporary_party": not config.PARTY_LEADER_ACC.get(pidx)}
        with st["lock"]:
            st["manual_route_plan"] = plan
        log.info("[party %d] ENGINE: di map %s -> %s, tap ket %s", pidx + 1,
                 source, dest, plan["city"])
    leader = plan["leader"]
    lead = next((a for a in anh.accs if a.username == leader and a.song), None)
    if plan["phase"] in ("gather", "sync_city", "sync_source"):
        _engine_chot_kenh(pidx, st, _acc_song(pidx),
                          {"viec": VIEC_DONG_BO}, manual_route=True)
    result = party_route.decide_route(
        plan, anh.accs, leader, channel_target=st.get("kenh_dich"),
        joined_members=lead.so_member if lead else None)
    with st["lock"]:
        plan["phase"], plan["lag_since"] = result.phase, result.lag_since
        plan["leader_map"] = lead.map_id if lead else None
    if plan.get("temporary_party"):
        for user in plan["users"]:
            client = account_clients.get(user)
            if client is not None:
                client._pe_la_leader = user == leader
    if result.complete:
        for user in plan["users"]:
            client = account_clients.get(user)
            if client is not None:
                client._pe_lenh_tay_gen = anh.lenh_tay_gen
                client._pe_la_leader = user == config.PARTY_LEADER_ACC.get(pidx)
        st["manual_route_done"].set()
        dat_nguoi_keo(pidx, config.PARTY_LEADER_ACC.get(pidx) or "*")
    elif result.phase in ("source", "dest"):
        dat_nguoi_keo(pidx, leader)
    else:
        dat_nguoi_keo(pidx, "*")
    return result.actions


class _EngineAbortEvent:
    def __init__(self, abort):
        self._abort = abort

    def is_set(self):
        return bool(self._abort())


def _engine_run_chaos(c, point, abort, before_repeat, one_battle, event):
    c._loandau_started = True
    try:
        loandau.run_loop(c, point, _EngineAbortEvent(abort),
                         before_repeat=before_repeat, mot_tran=one_battle, ev=event)
        return bool(getattr(c, "_loandau_done", False))
    finally:
        c._loandau_started = False


def _engine_mode_action(pidx, c, action, con_lam):
    if not con_lam():
        return False
    if action == "ve_safe":
        return _ra_safe_engine_moi(c, pidx, "tap ket party", con_lam=con_lam)
    if action == "roi_party_la":
        c.leave_party()
        return True
    if action == "boss_quan_doan":
        c.flee_mode = True
        try:
            c._wait_combat_clear(idle=2.0, cap=20.0)
            if not con_lam():
                return False
            c.leave_party()
            if getattr(c, "_pe_la_leader", False):
                reset_party_joined(pidx)
            else:
                unmark_joined(pidx, c.self_entity)
            return c.do_legion_boss()
        finally:
            c.flee_mode = False
    if action == "quet_bai_train":
        target = _map_train_dich(pidx, _pstate(pidx))
        train_map = (getattr(config, "TRAIN_MAPS", {}) or {}).get(int(target or 0))
        if not target or c.current_map != target or train_map is None:
            return False
        centers = _resolve_train_mob_centers(c, target, train_map, stop=lambda: not con_lam())
        if con_lam():
            c._pe_mob_scan = (target, centers)
        return bool(centers)
    if action.startswith("route_"):
        plan = dict(_pstate(pidx).get("manual_route_plan") or {})
        return party_route.execute_route_action(
            action, c, plan, abort=lambda: not con_lam(), finish=lambda cli: cli.leave_party())
    pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    label = getattr(c, "_label", "?")

    def heal_before_repeat():
        if c.running and not c.state.in_battle:
            c.heal_npc40_between_battles()

    return party_modes.execute_mode_action(
        action, c, target_map=int(pcfg.get("start_city_id") or 0) or None,
        city_flag=int(pcfg.get("city_flag") or 0), event=_event_cua_party(pidx),
        abort=lambda: not con_lam(),
        go_to_city=lambda cli, dest, flag: _ve_thanh_tap_trung(cli, pidx, label, dest, flag),
        run_chaos=_engine_run_chaos,
        leave_solo_event=lambda cli, ev: _loandau_ra_khoi_map(cli, ev, label),
        stop=lambda cli: stop_account(getattr(cli, "_username", ""),
                                      reason="Loan dau ket thuc"),
        one_battle=bool(pcfg.get("loandau_mot_tran")), before_repeat=heal_before_repeat)


def _cap_nhat_tuy_chon_client(c, pcfg):
    mode = pcfg.get("mode", "")
    c._pe_pcfg = pcfg
    c.auto_bag_clean = bool(pcfg.get("auto_bag_clean", True))
    c.auto_discard_junk = bool(pcfg.get("auto_discard_junk", True))
    c.auto_decompose_scrolls = bool(pcfg.get("auto_decompose_scrolls", False))
    c.scroll_modes = _scroll_modes_map(pcfg.get("scroll_modes"))
    c.auto_donate_materials = bool(pcfg.get("auto_donate_materials", True))
    c.material_modes = _scroll_modes_map(pcfg.get("material_modes"))
    c.auto_event_exchange = bool(pcfg.get("auto_event_exchange", False))
    c.event_exchange_items = list(pcfg.get("event_exchange_items") or [])
    c.event_exchange_sig = pcfg.get("event_exchange_sig", "") or ""
    c.fight_legion_boss = pcfg.get("fight_legion_boss", True)
    c.di_gioi_level = int(pcfg.get("di_gioi_level", 2))
    c.auto_sell_noi_dat = bool(pcfg.get("auto_sell_noi_dat", True) and mode in ("train", "city"))
    c.auto_cat_do = bool(pcfg.get("auto_cat_do", False) and mode in ("train", "city"))
    c.bank_expand_gold = int(pcfg.get("bank_expand_gold", 0) or 0) if pcfg.get("auto_bank_expand", False) else 0


def _cap_nhat_engine(eng, pidx):
    """Chay MOI NHIP trong thread cua engine: doc lai cau hinh + chot map train/bai quai.

    Dat o day (khong phai thread cua tung acc) vi: (a) day la viec CAP PARTY, lam mot lan la du;
    (b) tranh de ra thread rieng - do that 15/09 tren may user: 799 thread, 798 cai ngoi tranh
    GIL, main thread Tk doi -> GUI "not responding".
    """
    st = _pstate(pidx)
    eng.pha = _pha_engine_moi(pidx, st)
    eng.can_bao_nhieu = int(st.get("n_members") or 0)
    eng.map_dich = _map_train_dich(pidx, st)
    eng.pb_doi_levels = _pb_doi_levels_engine_moi(pidx)
    eng.pcfg = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}
    eng.map_event = _map_event_engine_moi(pidx)
    eng.co_pha_train = eng.pcfg.get("mode") == "digioi_train"
    # Chot MAP TRAIN + BAI QUAI: hai so nay do `_engine_chot_map` va `run_account` ghi - ca hai
    # deu KHONG chay voi party engine moi (cua chan 1 va 2). Thieu chung thi party gom du xong se
    # DUNG IM o thanh: khong biet di map nao, khong biet ra bai nao.
    _lead = config.PARTY_LEADER_ACC.get(pidx)
    _cli = account_clients.get(_lead) if _lead else None
    if _cli is not None and getattr(_cli, "running", False):
        _chuan_bi_bai_train(_cli, st, pidx, getattr(_cli, "_label", _lead))
    # BAO `stop_account` DUNG DONG SOCKET NGAY - y `run_account` dong 7150-7153.
    #
    # Thieu hai co nay thi STOP dong socket lap tuc va worker KHONG KIP chay ve safe: acc dung
    # ngay tai bai quai, lan login sau vao la bi quai danh ngay.
    # Chi bat khi party DANG O MAP TRAIN; trong Di Gioi / thanh thi dung dau cung duoc, va bat
    # bua thi STOP phai cho watchdog 25s moi dut.
    _sc = _map_train_dich(pidx, st)
    _safes = [tuple(p) for p in
              ((getattr(config, "TRAIN_MAPS", {}) or {}).get(int(_sc or 0), {}) or {}).get("safe", [])
              if len(p) == 2]
    for _u, _p, _l, _k in party_accounts(pidx):
        _c2 = account_clients.get(_u)
        if _c2 is None:
            continue
        _cap_nhat_tuy_chon_client(_c2, eng.pcfg)
        _tren_bai = bool(_sc) and int(getattr(_c2, "current_map", 0) or 0) == int(_sc)
        if _u == _lead:
            _c2._return_safe_on_stop = _safes if (_tren_bai and _safes) else None
        elif _lead:
            _c2._wait_leader_on_stop = bool(_tren_bai)


def _ghi_pha_engine_moi(pidx, pha):
    _st = _pstate(pidx)
    with _st["lock"]:
        _st["dt_phase"] = "train" if pha == party_engine.PHA_TRAIN else "digioi"


def _pha_engine_moi(pidx, st):
    """PHA hien tai cua party cho engine moi: con gio Di Gioi -> PHA_DG, het -> PHA_TRAIN.

    Doc `dt_phase` cua state party (nguon engine cu van dung) chu khong tu nho mot con so rieng -
    hai nguon su that ve cung mot thu la benh da giet party 11.
    """
    _mode = (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}).get("mode", "")
    if _mode == "event":
        return party_engine.PHA_EVENT
    if _mode not in ("digioi", "digioi_train"):
        return party_engine.PHA_TRAIN
    if _mode == "digioi":
        return party_engine.PHA_DG
    return (party_engine.PHA_DG if st.get("dt_phase", "digioi") != "train"
            else party_engine.PHA_TRAIN)


def _dang_ky_engine_moi(username, c, pidx, is_leader, label, stopped_fn, is_reconnect=False):
    """Acc da login xong -> giao han cho `PartyEngine` cua party, roi NGOI LAM WORKER.

    Khac engine cu o dung mot cho, va do la ca diem: acc KHONG con kich ban rieng. No khong tu
    quyet dinh di dau, cung khong con vong cho nao de ma diec lenh - moi viec do engine giao, va
    lenh moi CAT NGANG viec dang lam (`abort=`) chu khong cho acc "nghe thay".

    Ham nay chan toi khi acc bi dung/rot: supervisor (`_run_account_supervised`) dang o tren, thoat
    ra la no relogin - giu nguyen duong cuu acc cua engine cu (L0).
    """
    st = _pstate(pidx)
    _cap_nhat_tuy_chon_client(c, (getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {})
    # PHIEN LOGIN MOI -> XOA CO "da thua / da xong" cua phien truoc (y engine cu, dong 5914-5919).
    #
    # `go_claim` / `event_battle_done` song trong `_party_state[pidx]` = state theo TIEN TRINH,
    # khong phai theo lan login. Khong xoa thi acc VUA LOGIN da doc thay "event xong" -> di doi
    # thuong + thoat ngay, KHONG DANH TRAN NAO. Ghi chu trong ban cu: "`go_claim` set mot lan la
    # moi acc login sau do doc thay -> LOG VAO XONG OUT LUON".
    #
    # `is_reconnect` = server da giua chung -> GIU nguyen quyet dinh cua party (dung de mot acc rot
    # roi vao lai lam ca party danh tiep trong khi bon kia da bo cuoc).
    if not is_reconnect and ((getattr(config, "PARTY_CONFIG", {}) or {})
                             .get(pidx, {}) or {}).get("mode") == "event":
        if st["go_claim"].is_set() or st["event_battle_done"].is_set():
            log.info("[%s] ENGINE: phien login MOI -> xoa co 'da thua/da xong' cua phien truoc",
                     label)
        st["go_claim"].clear()
        st["event_battle_done"].clear()
    # LEADER VAO LAI (client MOI) -> HA CO "dang danh event".
    #
    # `event_battle_active` bat khi leader mo `start_npc40_loop`, va vong do song TREN CHINH
    # CLIENT cua leader. Leader rot la vong chet theo, nhung co thi nam trong `_party_state` nen
    # con bat mai - ngoai nhanh THUA ra khong ai ha no xuong.
    #
    # Engine cu khong lo vi leader vao lai chay lai `run_account` mode event: no tu `do_channel_sync()`
    # bang duong RIENG cua acc, khong di qua dieu phoi nen khong dinh cua chan nay. Engine moi
    # khong co duong do - lenh doi kenh di qua `_engine_gui_lenh_kenh`, ma ham do hoi
    # `_vi_sao_chua_doi_kenh` -> "CA PARTY dang danh event" -> KHONG BAO GIO gui.
    #
    # Ca that 16/09 party 45 (user: "p45 moi dua 1 kenh"):
    #   21:52:55 roster 4/4, ca party kenh 1
    #   21:53:10 leader cd701 rot
    #   21:53:18 leader vao lai o KENH 9 -> dieu phoi CHOT kenh dich = 1 (dung)
    #   21:53:18 CHUA gui lenh doi kenh 1 cho chdumot - CA PARTY dang danh event   <- ket tu day
    #   21:54:19 y het, roster van 0/4
    if (is_reconnect and username == config.PARTY_LEADER_ACC.get(pidx)
            and ((getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}).get("mode") == "event"):
        with st["lock"]:
            if st.get("event_battle_active"):
                log.info("[%s] ENGINE: LEADER vao lai -> vong battle cu da chet cung client cu, "
                         "ha co 'dang danh event'", label)
            st["event_battle_active"] = False
    # IN TUI + ARM QUET QUAI - hai viec `run_account` lam NGAY SAU LOGIN ma engine moi bo mat.
    #
    #   `log_bag_delayed()`      - in tui khi snapshot ve + on dinh, de DINH DANH item (bang thong
    #                              ke / tu mo ruong doc ten tu day)
    #   `arm_mob_packet_capture` - LEADER bat quet goi quai cua map train khi map do CHUA co diem
    #                              nao. Thieu no thi map moi KHONG BAO GIO duoc quet, va
    #                              `train_pick` phai tra "map CHUA QUET quai -> den quet truoc" mai.
    try:
        c.log_bag_delayed()
    except Exception as e:
        log.debug("[%s] ENGINE: log_bag_delayed loi (bo qua): %s", label, e)
    if is_leader:
        try:
            _sc_arm = _map_train_dich(pidx, st)
            _tm_arm = (getattr(config, "TRAIN_MAPS", {}) or {}).get(int(_sc_arm or 0))
            if _sc_arm and _tm_arm and _needs_train_mob_probe(c, int(_sc_arm), _tm_arm):
                c.arm_mob_packet_capture(
                    int(_sc_arm),
                    max_packets=getattr(config, "MOB_PACKET_CAPTURE_MAX_PACKETS", 50000))
                log.info("[%s] ENGINE: bat quet goi quai map train %s", label, _sc_arm)
        except Exception as e:
            log.warning("[%s] ENGINE: khong arm duoc packet capture: %s", label, e)
    with _party_engines_lock:
        eng = _party_engines.get(pidx)
        if eng is None:
            eng = party_engine.PartyEngine(
                pidx,
                lambda _p=pidx: [(u, cl, u == config.PARTY_LEADER_ACC.get(_p))
                                 for u, cl in _clients_cua_party(_p)],
                can_bao_nhieu=int(st.get("n_members") or 0),
                log=log,
                bao_gui=lambda u, mo_ta, pha: set_account_activity(u, mo_ta, phase=pha),
                gio_dg_toi_da=DIGIOI_LIMIT,
                # Tam bai quai va PHA doc THANG tu state party (`mob_spot` / `dt_phase`) - dung
                # nguon engine cu van dung, khong de ra nguon-su-that thu hai.
                doc_spot=lambda _p=pidx: _pstate(_p).get("mob_spot"),
                pb_doi_levels=_pb_doi_levels_engine_moi(pidx),
                # Ghi NGUOC `dt_phase` ra state party: engine moi la nguoi DUY NHAT doi pha cho
                # party nay (hai cho doi pha cua engine cu deu bi cua chan 1+2 khoa lai).
                ghi_pha=lambda _pha, _p=pidx: _ghi_pha_engine_moi(_p, _pha),
                # Cap nhat cau hinh + chuan bi bai train chay TRONG NHIP ENGINE (1 thread/party),
                # khong de ra thread rieng cho tung acc.
                cap_nhat=lambda _e, _p=pidx: _cap_nhat_engine(_e, _p),
                mode_fn=lambda _anh, _viec, _p=pidx: _engine_mode_decisions(_p, _anh, _viec),
                mode_action_fn=lambda _c, _v, _con_lam, _p=pidx:
                    _engine_mode_action(_p, _c, _v, _con_lam),
                # DUNG LAI duong moi party cua engine cu, khong chep lai: ham do da lo whitelist
                # truoc + hai duong train/khac + `_leader_tu_kiem_kenh`.
                # HAI GEN cua dieu phoi (`reform_gen` tu `gom`, `resync_gen` tu `dong_bo`) - day
                # moi la LENH THAT, `kh["viec"]` chi la trang thai. Xem chu thich o `DICH_VIEC`.
                doc_gen=lambda _p=pidx: (int(_pstate(_p).get("reform_gen") or 0),
                                         int(_pstate(_p).get("resync_gen") or 0)),
                # AI DUOC DI DUONG - doc THANG `nguoi_keo` cua dieu phoi (`dat_nguoi_keo`), khong
                # tu nghi ra. Xem chu thich `AnhParty.nguoi_keo`.
                doc_keo=lambda _p=pidx: nguoi_keo(_p),
                # THANH CUA ROUTE phai DI BO toi khi no chua mo (`_reform_via_nghiep` cua flow cu).
                doc_fc_di_bo=lambda _p=pidx: _fc_di_bo_engine_moi(_p),
                # Co phai THANH TELEPORT khong - de biet acc dang o giua duong hay dang o thanh.
                # Dung THANG `config.is_teleport_city`, khong tu che danh sach.
                la_thanh=lambda _m: bool(config.is_teleport_city(int(_m))),
                # CA PARTY du cap danh PB to doi chua - dung THANG `_thieu_level` cua flow cu.
                # Server khong cho acc duoi cap ready, co tao phong cung chi ra "ready 0/4".
                # NHIP KEEPALIVE per-acc: qua online, co Hop May, tra pet ve vai thuong, boss
                # quan doan - khoi ma vong keepalive cua `run_account` van chay, engine moi mat.
                nhip_acc=lambda _cli, _p=pidx: _nhip_acc_engine_moi(_cli, _p),
                hoi_du_cap=lambda _lv, _p=pidx: not _thieu_level(
                    _pstate(_p), [u for u, *_ in party_accounts(_p)], int(_lv)),
                moi_party=_invite_party_participants,
                co_pha_train=((getattr(config, "PARTY_CONFIG", {}) or {})
                              .get(pidx, {}).get("mode") == "digioi_train"),
                # Mode `digioi` thuan xong DG -> THOAT GAME. Dung `stop_account` cua engine cu:
                # no set stop-event VA chan cung relogin.
                thoat_acc=stop_account,
                pcfg=(getattr(config, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {},
                doc_duong=lambda _p=pidx: _duong_ra_spot_engine_moi(_p),
                # DUNG LAI `_handle_auto_team_dungeon` (ham nam NGOAI run_account nen goi duoc):
                # no lo retry, `team_dungeon_skip_all`, dong doi rot giua PB, doi qua su kien
                # truoc PB. Goi `do_team_dungeon` tho la vut het nhung cai do.
                chay_pb_doi=lambda _cli, _lv, _p=pidx: _chay_pb_doi_engine_moi(_cli, _p, _lv),
                # Y FLOW CU nhanh `elif is_digioi`: Ho Phu khi con <15 phut, va CAP QUAI DG do
                # dieu phoi chot (`_doc_cap_dg`) - acc chi DOC con so do (L1).
                ho_phu=_ho_phu_engine_moi,
                doc_cap_dg=lambda _p=pidx: _doc_cap_dg(_p),
                # VIEC VAT SAU LOGIN: goi THANG khoi cua engine cu (hon hai chuc muc, trong do co
                # ba nguon cua bang "Chu y": tu cong diem, Ba Dau, lo hoang kim). Tu che danh sach
                # la mat hang chuc muc ma khong mot dong log nao bao.
                # STOP -> VE SAFE ROI MOI DONG (y `run_account` dong 7207-7229).
                ve_safe_khi_stop=lambda _cli, _p=pidx: _ve_safe_khi_stop_engine_moi(_cli, _p),
                # CHI LAP PARTY O THANH TAP KET HOAC MAP TRAIN (luat cu, user chot 13/09). Hoi
                # THANG `_o_thanh_di_qua`, khong tu viet lai phep thu.
                hoi_thanh=lambda _noi, _p=pidx: _o_thanh_di_qua(_p, _pstate(_p), _noi),
                # CHUA NEN RA LENH? - goi THANG cac phep thu cua engine cu.
                hoi_cho=lambda _p=pidx: _chua_nen_ra_lenh_engine_moi(_p),
                # QUYET DINH CAP PARTY: goi THANG `_dieu_phoi_quyet` cua engine cu.
                # Engine moi KHONG tu nghi ra chuoi lenh nua - do la nguon cua gan het loi hai ngay
                # qua (user 16/09: "sao may ko tham khao cai cu da co ma cu thich bia ra cai moi").
                doc_party=lambda _p=pidx: _engine_doc_party(_p),
                ap_dung_party=lambda _anh, _v, _ly, _hu, _p=pidx:
                    _engine_ap_dung_party(_p, _anh, _v, _ly, _hu),
                doc_kenh_dich=lambda _p=pidx: _pstate(_p).get("kenh_dich"),
                # GOM = teleport ve THANH TAP KET (`_thanh_tap_ket_dich` cua engine cu), khong
                # phai di bo toi "map dong nguoi nhat".
                doc_thanh=lambda _p=pidx: _thanh_dich_engine_moi(_p),
                # BA MOC AN TOAN truoc khi doi kenh (event dang danh / trong tran / grace ket tran).
                # Gui giua tran la DUT KET NOI (ma 47).
                kenh_doi_duoc=lambda _cli, _p=pidx: _kenh_doi_duoc_ngay(_cli, _pstate(_p)),
                # XE DICH toa do +-10: ca party navigate y het mot diem thi chung chong len nhau.
                xe_dich=_jitter,
                # Bat ghi nhan THONG KE CHAN o tam quai (engine cu lam ngay truoc `combat_ready`).
                ghi_thong_ke=lambda _spot, _bat, _p=pidx: _ghi_thong_ke_engine_moi(_p, _spot, _bat),
                # MODE EVENT - ba viec, deu goi lai duong cua engine cu.
                vao_event=lambda _cli, _p=pidx: _vao_event_engine_moi(_cli, _p),
                danh_event=lambda _cli, _p=pidx: _danh_event_engine_moi(_cli, _p),
                doi_thuong=lambda _cli, _p=pidx: _doi_thuong_engine_moi(_cli, _p),
                map_event=_map_event_engine_moi(pidx),
                hoi_event_xong=lambda _p=pidx: _event_xong_engine_moi(_p),
                fc_gom=lambda _cli, _p=pidx: _fc_gom_engine_moi(_cli, _p),
                doc_tang_gom=lambda _p=pidx: _tang_gom_engine_moi(_p),
                doc_fc_buoc=lambda _p=pidx: _fc_buoc_engine_moi(_p),
                fc_buoc_fn=lambda _cli, _lt, _p=pidx: _fc_lam_buoc_engine_moi(_cli, _p, _lt),
                # LENH TAY cua GUI (teleport thanh). Truoc 21/09 engine moi khong doc `cmd_gen`
                # nen lenh roi vao hu khong voi party tu 21 tro len (user: "P21 ... chon thanh
                # thi ko co gi xay ra ca").
                doc_lenh_tay=lambda _p=pidx: int(_pstate(_p).get("cmd_gen", 0) or 0),
                lenh_tay_fn=lambda _cli, _p=pidx: _lenh_tay_engine_moi(_cli, _p),
                # SAFE cua map dich - `build_smart_route` can no (y `route_safe` cua flow cu).
                doc_safe=lambda _p=pidx: _safe_map_dich_engine_moi(_p),
                # NHIEM VU NGAY (PB don o1 + claim 9 o) - khoi "viec hang ngay" cua engine cu.
                daily_fn=lambda _cli, _p=pidx: _nhiem_vu_ngay_engine_moi(_cli, _p),
                chore_fn=lambda _cli, _p=pidx: _login_chores_engine_moi(_cli, _p),
            )
            _party_engines[pidx] = eng
            log.warning("[party %d] ENGINE MOI: khoi dong (1 luong quyet dinh/party)", pidx + 1)
        # CHI BA THU NAY duoc cap nhat khi dung lai engine da co. `map_event` thi KHONG - no chi
        # duoc chup MOT LAN luc tao engine (xem `map_event=_map_event_engine_moi(pidx)` o tren).
        #
        # HE QUA (da xay ra that, party 13 ngay 21/09): engine khoi dong luc 20:15 khi party con
        # mode train -> `event_key` chua co -> `_event_cua_party` roi vao fallback "lay event DAU
        # TIEN" -> `map_event` la dai map cua MOT EVENT KHAC. Den khi user doi sang 40NPC thi
        # `go_to_event` di DUNG (no doc lai event moi lan goi) nhung `eng.map_event` van om gia
        # tri cu -> `trong_event` VINH VIEN False -> `vao_event` giao lai 380 lan lien tiep, moi
        # giay mot lan, acc dung san o map 10991 ma khong ai cong nhan.
        #
        # CACH TRANH (user chot 21/09, chua sua vi se sua mot the luc chuyen han sang engine moi):
        # DOI EVENT / DOI MODE thi TAT BOT BAT LAI - relogin mot acc KHONG du, vi duong nay chi
        # cap nhat ba dong duoi. Restart thi `_party_engines` rong -> engine tao moi -> doc dung.
        eng.can_bao_nhieu = int(st.get("n_members") or 0)
        eng.map_dich = _map_train_dich(pidx, st)
        eng.pha = _pha_engine_moi(pidx, st)
    eng.start()
    log.info("[%s] (%s) ENGINE MOI: da giao cho engine party %d", label, "LEADER" if is_leader
             else "member", pidx + 1)
    # THREAD NAY LAM WORKER LUON, khong ngoi khong.
    #
    # Truoc day no chi ngu 1 giay/vong cho acc chet, con viec thi giao cho mot thread worker RIENG
    # => moi acc 4 thread (supervisor + recv + heartbeat + worker) thay vi 3. Do tren may that
    # 15/09: 799 thread, 798 cai dang ngoi TRANH GIL, main thread Tk doi -> GUI "not responding".
    # Engine moi de ra them thread la di nguoc chinh cai no phai chua.
    _w = eng.workers.get(username)
    if _w is None:
        log.warning("[%s] ENGINE MOI: khong tao duoc worker -> tra quyen cho supervisor", label)
        return
    # CHAN o day toi khi acc chet/stop - DUNG LAI thread dang co (khong de ra thread worker).
    # `nen_dung`: acc bi STOP (vd mode `digioi` thuan xong DG goi `stop_account`) hoac rot ->
    # nha thread ra cho supervisor, khong thi worker cu quay tiep va acc khong bao gio dung han.
    _w.chay_o_day(nen_dung=lambda: stopped_fn() or not getattr(c, "running", False))
    log.info("[%s] ENGINE MOI: acc dung/rot -> tra quyen cho supervisor", label)


def _clients_cua_party(pidx):
    """[(username, client)] cua party. `client = None` = acc CON KHA NANG VAO nhung CHUA vao world.

    Doc thang `account_clients` (cung tien trinh), khong doi ai bao cao (L2).

    VI SAO TRA CA ACC CHUA CO CLIENT: engine moi la MOT luong nam ca party, no phai TU BIET party
    da du acc chua - khong the chi nhin acc da vao world roi ket luan "ca party cung map/kenh".
    Acc dang login (thread con song, chua co client) van thuoc party va co the vao o kenh khac han.
    Ca that 20/09 party 55 (user: "ca party chua cung map cung kenh ma da lap party"):
        12:31:20 ENGINE: tik901/903/904/905 -> lap_party   <- tik902 con dang bi chan toc do login
        12:33:17 [tik902] chua vao world - SERVER CHAN TOC DO DANG NHAP (lan 1)

    Acc DA TAT HAN (user Stop / thread chet) thi KHONG tra ve: cho mot acc da tat la cho vinh vien.
    """
    ra = []
    for u, _p, _lead, _pick in party_accounts(pidx):
        cl = account_clients.get(u)
        if cl is not None:
            ra.append((u, cl))
        elif is_account_running(u):
            ra.append((u, None))      # dang login - van tinh la nguoi cua party
    return ra








# Dieu phoi gui lai lenh doi kenh cho CUNG mot acc sau bay lau. `switch_channel` tu no da co
# wait+retries; gui day hon la chong goi len nhau chu khong nhanh hon.
DIEU_PHOI_GUI_LAI_KENH_SEC = 12.0


def _kenh_chac(c):
    """So kenh cua acc nay co phai do SERVER xac nhan khong (khong phai so nho lai tu truoc).

    `bot/client.py::kenh_dang_chac()`. Tach ra day de cho goi khong phai lap `hasattr`. Client cu
    (hoac doi tuong gia trong test) khong co ham nay -> coi nhu CHAC, giu nguyen hanh vi cu.
    """
    try:
        return bool(c.kenh_dang_chac())
    except Exception:
        return True


def _kenh_doi_duoc_ngay(c, st):
    """Acc nay co doi kenh duoc NGAY BAY GIO khong (doc thang client, khong hoi acc).

    Doi kenh = doi INSTANCE. Gui giua tran thi server bo qua ma bot tuong da doi; gui giua event
    thi keo theo `scene_resume` -> `C:020-006` luc server chua giai xong tran -> `S:000-000` ma 47
    `<戰鬥未結束事件先結束>` -> DUT KET NOI (07/09: thsau/thmo/tonba/lbumot/xGAx dis trong 32 giay).

    Ba moc, tu chac den long: `state.in_battle` (0x35/0x34 len, `0x14 sub0700` END ha) · grace ket
    tran · `in_combat()` (idle-based, ngay sau khi tran vua mo con False nen KHONG dung mot minh).
    """
    if c is None or not getattr(c, "running", False):
        return False
    try:
        if st is not None and st.get("event_battle_active"):
            return False
    except Exception:
        pass
    try:
        if getattr(c.state, "in_battle", False) or c._in_battle_end_grace():
            return False
    except Exception:
        pass
    try:
        if c.in_combat():
            return False
    except Exception:
        pass
    return True


def _vi_sao_chua_doi_kenh(c, st):
    """Cua nao trong `_kenh_doi_duoc_ngay` dang chan - de log noi duoc LY DO, khong im lang.

    Giu DUNG THU TU voi `_kenh_doi_duoc_ngay`: lech nhau la log chi sai cho.
    """
    if c is None or not getattr(c, "running", False):
        return "acc da tat"
    try:
        if st is not None and st.get("event_battle_active"):
            return "CA PARTY dang danh event (doi kenh giua event -> ma 47 -> dut ket noi)"
    except Exception:
        pass
    try:
        if getattr(c.state, "in_battle", False):
            return "dang TRONG TRAN"
        if c._in_battle_end_grace():
            return "vua ket tran (grace) - cho server giai tran xong"
    except Exception:
        pass
    try:
        if c.in_combat():
            return "con dinh combat (idle ngan)"
    except Exception:
        pass
    return "khong ro"








def _engine_chot_kenh(pidx, st, song, kh=None, *, manual_route=False):
    """DIEU PHOI tu chon KENH DICH cho ca party. Khong cho acc nao bao cao.

    `kh` = ke hoach VUA quyet xong o cung nhip (`_dieu_phoi_quyet`). Ham nay KHONG duoc tu ket
    luan lai tinh hinh party - mot party mot ket luan (L1).

    Kenh dich la TRANG THAI (`st["kenh_dich"]`), khong phai cai bat tay tung vong. Vong bat tay
    cu (`do_channel_sync`) chi bao ve duoc acc DANG DUNG TRONG vong cho: acc nao lam xong roi
    `break` ra la khong ai theo doi nua, doi dich sau do thi no khong bao gio biet.
    Da xay ra that (party 53, 06/09):
        02:09:11 vumba/vumsau doc dich = kenh 4 -> xong -> ROI vong dong bo
        02:09:12 picker mo vong MOI, dich = kenh 2
        02:09:22 sync kenh: 3/5 da sang kenh 2, CHUA sang: {qv813: 4, qv816: 4}
    Hai dua do KHONG HE nhan duoc lenh moi.

    CHON KENH NAO: kenh dang co NHIEU acc nhat (it phai di chuyen nhat). Khong hoi danh sach
    kenh - khong can, va hoi thi lai roi vao bay "kenh minh dang o trong co ve dong".

    CHON KENH NAO: kenh dang co NHIEU acc nhat (it phai di chuyen nhat). Roi DOC THANG ket qua
    doi kenh cua tung client (`_doc_ket_qua_doi_kenh`) de biet kenh nao vua bao DAY ma tranh, va
    de biet co phai lap lai party sau khi doi xong khong. Khong acc nao phai bao cao gi.

    DIEU PHOI LA NGUOI QUYET, khong nhuong ai: khong con nhanh "co vong bat tay chay thi thoi".
    Vong bat tay cu (`do_channel_sync`) gio chi con la CANH TAY thi hanh, khong tu chot kenh.
    """
    # MODE KHONG CAN LAP DOI -> khong chot kenh, khong lap lai doi (xem `_mode_can_lap_doi`).
    #
    # Guard nay TUNG NAM O CUOI HAM, sau ca nhanh "chung kenh ma doi khong du -> LAP LAI PARTY" -
    # cua chan dat SAU dung cai viec no phai chan (L3h). Party 21, 10/09:
    #   21:09:30 [party 21] ca party da chung kenh 1 nhung DOI chua du
    #                       (dieu906=4 dieu907=1 dieu908=2 dieu909=3 dieu910=4) -> LAP LAI PARTY
    #   21:11:31 ... 21:13:31 ... 21:15:31 ... 21:17:32   (moi 2 phut, dung bang cooldown)
    # DANG GOM MAP -> CHUA DEN LUOT KENH. Thu tu user chot: map truoc, kenh sau, roi moi lap doi.
    #
    # Ham nay co san phep "khac map thi so kenh vo nghia" (`return None` trong vong dem ben duoi),
    # nhung do la phep do cua RIENG no tren mot anh chup `song` khac - con `kh` la ket luan cua
    # dieu phoi trong CUNG nhip. Hai anh chup lech nhau vai tram ms la du de no chot kenh giua luc
    # ca party dang duoc keo ve mot map (party 7, 11/09).
    # Con `kenh_dich` cu thi GIU NGUYEN, khong xoa: gom map xong ma van lech kenh thi dung lai no.
    if kh is not None and kh.get("viec") == VIEC_GOM:
        log.debug("[party %d] chot kenh: dang gom MAP (viec=%s) -> chua den luot kenh",
                  pidx + 1, kh.get("viec"))
        return st.get("kenh_dich")
    if not manual_route and not _mode_can_lap_doi(pidx):
        with st["lock"]:
            if st.get("kenh_dich"):
                log.info("[party %d] DIEU PHOI: mode KHONG CAN LAP DOI -> thoi lenh doi kenh "
                         "(kenh_dich %s)", pidx + 1, st.get("kenh_dich"))
            st["kenh_dich"] = None
            st["kenh_dich_luc"] = 0.0
        return None
    # 40NPC ngoai gio: acc di doi thuong SOLO roi thoat - dung chung kenh khong de lam gi, ma lenh
    # doi kenh thi keo no ra khoi viec dang lam (xem `_party_40npc_ngoai_gio`).
    if not manual_route and _party_40npc_ngoai_gio(pidx, getattr(config, "PARTY_CONFIG", {}).get(pidx, {})):
        if st.get("kenh_dich"):
            log.info("[party %d] DIEU PHOI: 40NPC ngoai gio -> BO kenh dich %s (acc chi di doi "
                     "thuong roi thoat)", pidx + 1, st.get("kenh_dich"))
        with st["lock"]:
            st["kenh_dich"] = None
            st["kenh_dich_luc"] = 0.0
        return None
    # CON LECH MAP -> KHONG DUNG TOI KENH, ke ca khi chua co ke hoach (`kh is None`).
    #
    # User chot (14/09): "logic t noi tu dau: lech map thi dong bo map, lech kenh thi dong bo kenh
    # -> dang lech map thi di dong bo map di, may lay kenh lam lon gi luc do".
    #
    # MOI MAP MOT DANH SACH KENH KHAC NHAU, nen luc con lech map thi moi con so kenh deu vo nghia:
    # so `current_channel` cua acc o map khac la kenh CUA MAP DO, va bang suc chua no dang giu cung
    # la cua map do. Chot dich bang nhung so ay = chot mot kenh khong ton tai o map se toi.
    #
    # Ca that party 3, 14/09 (user: "thay chot kenh 7, ma tuong duong deo co kenh 7"):
    #   15:50:31 [party 3] gen 3: con lech map [12001, 21001] ... baybay@12001/k2 minh@12001/k7
    #   15:50:35 [party 3] party lech kenh {1:1, 2:1, 3:1, 7:2} -> CHOT kenh dich = 7
    # Cua cu chi chay khi `kh is not None`; `kh` rong la lot thang xuong.
    _maps_now = {int(getattr(c, "current_map", 0) or 0) for _u, c in song
                 if getattr(c, "current_map", None)}
    if len(_maps_now) > 1:
        # XOA DICH CU, khong phai giu lai. Ban dau cho nay `return st.get("kenh_dich")` - dieu phoi
        # thoi khong chot dich MOI, nhung dich CU van nam do va acc van doc duoc no roi tu chuyen.
        # Dich cu la kenh cua MAP CU -> o map moi no khong ton tai.
        #
        # Ca that party 4, 14/09 (user: "chua gom map da gom kenh"):
        #   16:49:53 [party 4] gen 10: viec=gom - party dang o 2 MAP khac nhau [12061, 21001]
        #   16:50:00 [thmo] (LEADER) DIEU PHOI chot kenh 5, minh dang o 2 -> tu chuyen
        #   16:50:00 [thmo] Doi kenh 5 THAT BAI: khong co khu do de doi (result=2)
        # Kenh 5 la dich chot hoi ca party con o 12001. Sang 21001 thi khong co kenh do.
        _cu = st.get("kenh_dich")
        if _cu:
            with st["lock"]:
                st["kenh_dich"] = None
                st["kenh_dich_luc"] = 0.0
            log.info("[party %d] DIEU PHOI: XOA kenh dich %s - party con o %d MAP khac nhau %s "
                     "(dich cu la kenh cua map cu; dong bo map truoc roi chot lai)",
                     pidx + 1, _cu, len(_maps_now), sorted(_maps_now))
        elif time.time() - float(st.get("chot_kenh_lech_map_log", 0.0) or 0.0) > 60.0:
            st["chot_kenh_lech_map_log"] = time.time()
            log.info("[party %d] DIEU PHOI: chua dung toi kenh - party con o %d MAP khac nhau %s "
                     "(moi map mot danh sach kenh; dong bo map truoc)",
                     pidx + 1, len(_maps_now), sorted(_maps_now))
        return None
    dem = {}
    map_chung = None
    for _u, c in song:
        m = getattr(c, "current_map", None)
        ch = getattr(c, "current_channel", None)
        if m is None or not ch:
            # IM LANG O DAY la cach party 9 ket 7 phut: dieu phoi ket luan 'dong_bo' moi nhip
            # nhung khong bao gio chot duoc dich, nen khong co lenh nao duoc gui.
            # (Bac map o `_dieu_phoi_quyet` gio da giu lai truong hop nay, day chi la luoi do.)
            if time.time() - float(st.get("chot_kenh_thieu_log", 0.0) or 0.0) > 60.0:
                st["chot_kenh_thieu_log"] = time.time()
                log.info("[party %d] DIEU PHOI: chua chot duoc kenh dich - %s chua biet %s",
                         pidx + 1, getattr(c, "_label", _u),
                         "map" if m is None else "kenh")
            return None
        if map_chung is None:
            map_chung = int(m)
        elif int(m) != map_chung:
            if time.time() - float(st.get("chot_kenh_thieu_log", 0.0) or 0.0) > 60.0:
                st["chot_kenh_thieu_log"] = time.time()
                log.info("[party %d] DIEU PHOI: chua chot kenh dich - con lech map (%s o %s, "
                         "nguoi khac o %s)", pidx + 1, getattr(c, "_label", _u), m, map_chung)
            return None                      # khac map thi so kenh vo nghia
        dem[int(ch)] = dem.get(int(ch), 0) + 1
    pinned = st.get("kenh_ghim")
    if pinned and dem:
        with st["lock"]:
            if st.get("kenh_dich") != int(pinned):
                st["kenh_dich_luc"] = time.time()
            st["kenh_dich"] = int(pinned)
        return int(pinned)
    if len(dem) <= 1:
        with st["lock"]:
            st["kenh_dich"] = None           # dang chung kenh -> khong co viec gi
            st["kenh_dich_luc"] = 0.0
        # DA CHUNG KENH MA DOI KHONG CON DU -> LAP LAI PARTY.
        # Server CAM doi kenh khi dang trong doi (`result=3`) nen member buoc phai ROI DOI moi doi
        # duoc kenh - do la luat game, member lam dung. Ra lenh doi kenh ma khong lam not phan hai
        # la loi cua NGUOI RA LENH: party 5 (06/09) tan doi luc 16:34:14 vi lenh doi kenh, roi
        # leader qua cong len tang MOT MINH luc 16:34:53.
        # KHONG dung co "no": doc THANG roster that (`joined_member_count`) la biet, va biet ca
        # khi doi tan vi ly do khac.
        # CO COOLDOWN (L6 + L7). Ham nay chay MOI 2 GIAY, ma MOI lan `_bump_reform` la ABORT moi
        # acc dang di duong (`_ab()`). Bump lien tuc = huy chinh viec lap party ma minh vua ra
        # lenh -> ca party dung im o thanh vinh vien.
        # Log that (06/09, 18:00-23:08): p28 `REFORM gen -> 8541`, p39 -> 8614, p23 -> 8035 - tam
        # NGHIN lan bump trong 5 tieng, "rat nhieu party ket o thanh ma khong di danh".
        # Chinh toi viet nhanh nay sang nay roi quen dat han - dung cai L6/L7 vua viet ra de cam.
        # DEM DOI BANG ROSTER SERVER (L2d), khong bang `joined_member_count` - so nho cua bot om
        # stale: party tan ma khong ai unmark thi no van bao du, va the la KHONG AI ra lenh lap lai
        # (ca that 07/09 party 1: 44 phut, leader lap lai "KHONG o party nao" moi phut).
        # BEN QUYET DA NOI GI THI NGHE NAY, khong tu ket luan lai (L1: mot party mot ket luan).
        #
        # Ham nay chup `song` rieng va TU di kiem map lai. Hai anh chup lech nhau vai tram ms la
        # ra hai ket luan trai nguoc - trong CUNG MOT GIAY:
        #   23:45:34 [party 6] gen 12: viec=moi ...
        #   23:45:46 [party 6] DIEU PHOI: ca party da chung kenh 1 nhung DOI chua du -> LAP LAI
        #   23:46:34 [party 6] gen 15: viec=gom - party dang o 3 MAP khac nhau [12001,23001,23811]
        # Ben quyet biet thua la dang lech map ("con lech map ... -> chua lap party, cho gom xong")
        # con ben nay thi "chung kenh roi" -> bump reform -> ABORT chinh vong gom vua ra lenh.
        # p6/p7 dem 10/09 quay nhu vay tu 23:43 den 23:47: gom -> lap lai -> lech map -> gom lai,
        # roster khong bao gio qua noi 4/5 (`taot001=4 ... taot005=1` = dang moi DO DANG thi bi cat).
        #
        # `VIEC_MOI` la lenh DUY NHAT co nghia "da cung map/kenh, gio lap doi di". Moi viec khac
        # (`gom` / `dong_bo` / `lam`) deu co nghia CHUA den luot lap party.
        _viec = (kh or {}).get("viec")
        if kh is not None and _viec != VIEC_MOI:
            log.debug("[party %d] chot kenh: dieu phoi dang bao viec=%s -> chua den luot lap "
                      "party, khong bump", pidx + 1, _viec)
            return None
        # DANG LAP DO DANG -> DE NO LAP NOT. Xem `_doi_dang_lap`: dap party dang hinh thanh la
        # cach chac chan nhat de no khong bao gio du.
        if _thieu_doi(pidx, song) and _doi_dang_lap(st, song):
            log.info("[party %d] DIEU PHOI: doi chua du (%s) nhung roster DANG LEN -> de no lap "
                     "not, khong dap di lap lai", pidx + 1, _tinh_hinh_doi(song))
            return None
        # CAC BAN SAO ROSTER CHUA NHAT TRI -> goi `0x0d` dang lan, chua doc duoc gi. Ra lenh luc
        # nay la pha dung cai doi vua hinh thanh (party 17, 14/09) - xem `_roster_dang_lan`.
        if _thieu_doi(pidx, song) and _roster_dang_lan(st, song):
            log.info("[party %d] DIEU PHOI: doi chua du (%s) nhung co acc DA thay du - goi roster "
                     "dang lan, CHO no nhat tri roi moi ket luan", pidx + 1, _tinh_hinh_doi(song))
            return None
        # THIEU NGUOI VI CO ACC DANG LAM VIEC VAT -> KHONG PHA DOI.
        #
        # Acc dang viec vat GIU loi moi lai, xong viec thi nhan (`account_task.__exit__`). Tuc doi
        # se tu du - chi cham vai giay. Bump reform luc nay la `leave_party()` ca party dang lanh
        # de "lap lai", trong khi thu duy nhat con thieu la mot dua sap xong viec vat.
        #
        # DIEU PHOI VAN RA LENH MOI nhu thuong (leader cu moi, loi moi duoc giu lai) - chi KHONG
        # bump reform. Lan truoc t cho dieu phoi NGUNG RA LENH khi co acc ban: viec vat thi acc nao
        # cung lam lien tuc nen luc nao cung co nguoi ban -> khong bao gio ra lenh -> ca party dung
        # o thanh voi roster 0/4 (14/09, 204 lan: "bon no lai ket o thanh deo di dau kia").
        #
        # Dieu phoi DOC THANG bao cao pha, khong doi acc xin phep - y het doc `current_map`.
        _ban = _ai_dang_lam_viec_le(song)
        if _thieu_doi(pidx, song) and _ban:
            if time.time() - float(st.get("viec_vat_log", 0.0) or 0.0) > 60.0:
                st["viec_vat_log"] = time.time()
                log.info("[party %d] DIEU PHOI: doi chua du (%s) nhung %s dang lam VIEC VAT - loi "
                         "moi da duoc giu lai, xong viec se vao. KHONG bump reform (pha doi dang "
                         "lanh de cho mot dua sap xong)", pidx + 1, _tinh_hinh_doi(song),
                         sorted(_ban))
            return None
        if _thieu_doi(pidx, song) and not _dang_doi_kenh(song):
            with st["lock"]:
                _luc = float(st.get("lap_party_luc", 0.0) or 0.0)
                _con_som = time.time() - _luc < LAP_LAI_PARTY_COOLDOWN
                if not _con_som:
                    st["lap_party_luc"] = time.time()
                    _bump_reform(st, "chung kenh roi ma doi khong du -> lap lai party")
            if not _con_som:
                log.info("[party %d] DIEU PHOI: ca party da chung kenh %s nhung DOI chua du (%s) "
                         "-> LAP LAI PARTY", pidx + 1, next(iter(dem), "?"),
                         _tinh_hinh_doi(song))
        return None
    # DA CHUNG KENH thi tren kia da xoa dich va tra ve roi - guard duoi day CHI danh cho
    # truong hop party CON LECH kenh. Dat no o TREN la sai: acc bi tu choi doi kenh se thu
    # lai lien tuc, tuc LUC NAO CUNG "dang doi kenh", nen ham thoat o guard va KHONG BAO
    # GIO chay toi cho xoa dich - ca party da ve chung kenh 1 tu lau ma van bam dich 27.
    # (user 08/09: "m ko thay ca lu da cung kenh 1 roi a, tim kenh khac lam cai lon gi nua")
    # DANG CO ACC BAY GIUA HAI KENH -> GIU NGUYEN DICH, khong tinh lai gi het. `current_channel`
    # cua acc do la so DO DANG (da roi doi, chua vao kenh moi) nen moi phep dem duoi day deu la
    # RAC: no vua co the ve "chung kenh" gia (-> xoa `kenh_dich`, mat luon han 45s), vua co the ve
    # mot phan bo lech khac (-> chot dich moi). Ra lenh moi trong khi lenh cu chua thi hanh xong,
    # va MOI lenh bat leader `leave_party()` them mot lan.
    #
    # Ca that 08/09 party 1 (user: "leader deo tap trung") - BA dich trong TAM giay:
    #   00:42:40  party lech kenh {5: 2, 7: 1} -> CHOT kenh dich = 5
    #   00:42:46  party lech kenh {5: 2, 7: 3} -> CHOT kenh dich = 7
    #   00:42:48  party lech kenh {5: 2, 7: 3} -> CHOT kenh dich = 3
    # Hai dong cuoi CUNG mot phan bo ma hai ket luan trai nguoc. Cung luc do ban quyet viec DA biet
    # phai dung ("gen 3 ... co acc dang doi kenh -> cho roster on dinh roi moi quyet") - chi rieng
    # ham chot kenh khong ai bao.
    if song and _dang_doi_kenh(song):
        _cu = st.get("kenh_dich")
        # ... TRU KHI chinh kenh dich do bi server bao DAY (ma 4). Acc khong vao duoc thi no retry
        # lien tuc, va retry lien tuc = LUC NAO CUNG "dang doi kenh" -> giu dich vinh vien. Day la
        # loi cua chinh guard nay khi moi them (08/09): party 3 ket 6 phut ruoi khong mot lenh moi
        #   04:21:11 [party 3] kenh dich 27 qua han nhung DA GOM DUOC 3/5 -> GIA HAN  <- lenh cuoi
        #   04:27:04 [batbat]  Doi kenh 27 THAT BAI: khu da day nguoi (result=4)
        #   04:27:14 [hoathap] Doi kenh 27 THAT BAI: khu da day nguoi (result=4)
        # User: "neu thay co dua ko ve duoc kenh do kenh day -> chon lai kenh di".
        if _cu and int(_cu) not in _doc_ket_qua_doi_kenh(song)[0]:
            return int(_cu)
        # CHUA CO DICH thi KHONG CO GI DE GIU - phai chot, khong duoc thoat.
        #
        # Guard nay sinh ra de "dang co acc bay giua hai kenh -> giu nguyen dich, khong tinh lai".
        # No chi co nghia khi DA CO dich. Chua co ma van thoat thi khong bao gio chot noi dich DAU
        # TIEN, tuc khong mot lenh doi kenh nao duoc gui - party lech kenh vinh vien.
        #
        # Ca that party 2, 13/09 (user: "p2 van ko dong bo kenh"):
        #   15:18:25 [party 2] gen 2: pha=event map=12932 kenh=None viec=dong_bo
        #                      - cung map nhung LECH KENH [1, 2] -> gom kenh truoc khi moi
        #   15:19:27 / 15:20:28 / 15:21:58 ... van 'dong_bo' ... CHO them Ns
        # sga001-004 o kenh 1, sga006 o kenh 2, CUNG map 12932, cung toa do (510,330). Khong mot
        # dong `CHOT kenh dich` nao, cung khong mot dong `Chuyen kenh ->` nao.
        #
        # So kenh cua acc dang bay co the la rac, nhung chot mot dich con hon treo: dich co han
        # (`kenh_dich_luc`) va duoc chot lai khi qua han hoac khi kenh do bao DAY.
    # LOAN DAU THI KHONG RA LENH DOI KENH. Loan dau la SOLO - khong lap party, khong can cung
    # kenh - nen viec gom kenh o day khong duoc gi ma MAT TAT CA: cho xep hang ghep tran nam o
    # kenh acc DA DANG KY, doi kenh la mat cho, roi acc dung cho toi het gio ma khong mot tran nao.
    #
    # Ca that 08/09 (user: "co acc vao roi ma ko dang ky danh") - sga003 = haba:
    #   20:23:14 [haba] Loan dau: da dang ky, cho ghep tran (thang=0)   <- dang ky o KENH 4
    #   20:23:19 [haba] Doi kenh OK -> 2                                <- dieu phoi keo sang kenh 2
    #   20:38:14 [haba] Loan dau: cho ghep tran qua 900s khong vao -> dung
    # Ba dong do cach nhau 15 phut - mat tron mot luot loan dau.
    # (Guard LOAN DAU da chuyen len DAU HAM - phai chan TRUOC ca nhanh "lap lai party", xem o do.)
    # (XOA 13/09 cua "TRONG THAP 2K THI KHONG RA LENH DOI KENH".)
    #
    # Cua do xoa luon `kenh_dich` va tra None cho MOI truong hop dang o trong thap. Nhung toi day
    # thi `len(dem) > 1` roi - tuc party DANG LECH KENH that. Xoa dich luc do = ben quyet bao
    # "dong bo kenh" con ben nay bao "khong co dich", lenh ra ma khong ai thi hanh duoc (L1: mot
    # party mot ket luan).
    #
    # Ca that party 52, 13/09 (user: "biet khac kenh roi ma van deo xu ly duoc"):
    #   15:41:04 [party 52] gen 3: pha=event map=12922 viec=dong_bo - cung map nhung LECH KENH
    #                       [1, 2] -> gom kenh truoc khi moi
    #   15:42:07 / 15:43:07 / 15:44:09 / 15:45:11 / 15:46:11 / 15:47:12  lap mai, khong mot dong
    #   `CHOT kenh dich` nao.
    #
    # LUAT CHUNG, KHONG CO NGOAI LE (user 13/09: "logic co ban o moi noi: lech map thi dong bo
    # map, lech kenh thi dong bo kenh, roi den lap party"). Con "cung kenh roi ma khac TANG" thi
    # da duoc lo o nhanh `len(dem) <= 1` ben tren (gom tang), khong dinh gi toi day.
    # DU PARTY ROI -> KHONG DUNG VAO KENH NUA (user chot 07/09: "du pt va di danh roi van di doi
    # kenh tiep, m co can code ngu the ko").
    #
    # DU PARTY = DA CUNG INSTANCE. Server khong cho o chung doi ma khac phan khu, nen chinh cai
    # roster day la bang chung manh hon moi con so bot tu nho - `current_channel` thi SAI duoc (sot
    # lai qua reconnect, ack cu; user kiem chung 30/08: bot hien ca 5 nick kenh 12, vao game xem la
    # 12/12/12/2/1), va do moi la thu khien dieu phoi tuong la "lech".
    #
    # Doi kenh luc nay khong duoc gi ma mat tat ca: `switch_channel` phai ROI DOI truoc (luat
    # `Team.IsAlone`), tuc TU TAY pha cai party vua gom xong; con doi scene giua tran thi dinh
    # `S:000-000` ma 47 (`戰鬥未結束事件先結束`).
    #
    # VONG LAP THAT 07/09 party 52 (user: "p52 nay gio co di train dc ko" - 38 phut duoc 14 tran,
    # quay qua lai bai train 12831 <-> Cu Loc 12011 moi 1-2 phut):
    #   23:37:27 DOI chua du (qv804=0 qv808=4 qv809=4 qv810=4 qv811=4)
    # `qv804` la LEADER va roster cua no = 0 vi no vua `leave_party()` DE DOI KENH; bon member con
    # thay `4` chi vi chua kip nhan goi cap nhat - doi truong roi la server giai tan CA DOI, nen so
    # 4 do la so CU. Ket qua: `_thieu_doi` bao thieu -> VIEC_MOI -> lap lai party -> chot kenh ->
    # roi doi -> ... gen 130 -> 137 trong hai phut, party bi da qua lai thanh <-> bai.
    # DANG CO DOI (du la do dang) -> THOI DOI KENH.
    #
    # Doi kenh BAT BUOC phai roi doi truoc (luat `Team.IsAlone`), ma doi truong roi la SERVER GIAI
    # TAN CA DOI. Nen ra lenh doi kenh luc dang co doi = tu tay pha cai vua gom. Chi duoc doi kenh
    # khi CHUA AI o trong doi nao - dung thu tu: gom kenh TRUOC, moi party SAU.
    # ...NHUNG CHI KHI DOI DA DU. Party DO DANG (vai nguoi vao duoc, may nguoi ket kenh khac) thi
    # no la PARTY HONG - L0 bat phai gom lai BANG DUOC, khong duoc lay "co doi" lam co de dung im.
    #
    # Ca that 09/09 party 1 (user: "p1"): ca 5 acc o map DG 49942 nhung MOI DUA MOT KENH; chihao +
    # sieugaaa vao duoc doi (roster 1) -> co `_co_party` bat -> dieu phoi IM 35 PHUT:
    #   01:45:51 [party 1] DANG CO DOI (brubb46677=0 chihao188=1 minhminhmq=0 sieugaaa=1
    #                      tuyetdo=0) -> thoi lenh doi kenh (kenh_dich 52)
    #   ... khong mot dong DIEU PHOI nao nua ...
    #   02:20:51 [xGAx] (LEADER) chua moi 3 member vi chua xac nhan live dung map/kenh:
    #                   ['c853d3f8:lech kenh live 52!=12', '38d0d2f8:lech kenh live 44!=12', ...]
    # Doi 2/5 khong danh duoc gi, ma giu no thi ba acc kia ket vinh vien. Thu tu dung van la cai
    # comment tren da ghi: gom kenh TRUOC, moi party SAU - nen party do dang phai giai tan de gom.
    # `_dang_doi_kenh` la cho phan biet HAI ca nhin giong nhau:
    #   - party 52 (07/09): leader VUA `leave_party()` DE DOI KENH -> roster no = 0 trong vai giay,
    #     `_thieu_doi` bao thieu. Do la HAU QUA cua lenh minh vua ra, khong phai party hong ->
    #     phai im (day chinh la ca sinh ra guard nay).
    #   - party 1 (09/09): 35 phut khong ai doi kenh, doi ket 2/5 -> party hong that -> phai gom.
    _co_party = any(len(getattr(_c, "party_members", None) or ()) > 0 for _u, _c in song)
    # DANG THI HANH thi GIU LENH, khong phai VUT LENH.
    #
    # Hai ca duoi day can hai hanh dong KHAC HAN, ban cu tra ve cung mot thu (`kenh_dich = None`):
    #   - doi DA DU        -> het viec that -> XOA dich.
    #   - dang doi kenh    -> lenh dang CHAY -> phai GIU dich, chi la khong quyet lai luc nay.
    # Xoa dich o ca thu hai = bo lenh giua chung. Nhip sau acc do bay xong, `_dang_doi_kenh` tat,
    # `cu` da thanh None nen cua "DA CHOT ROI THI GIU" ben duoi khong con gi de giu -> chot lai tu
    # dau bang phan bo VUA DOI -> ra dich khac -> ca party quay dau -> lap lai.
    # Ca that party 24, 00:21:26 -> 00:22:38 (72 giay, MUOI lenh doi kenh):
    #   {1:1, 2:4}        -> CHOT 5      {2:2, 4:1, 5:2} -> CHOT 4
    #   {2:2, 5:3}        -> CHOT 4      {2:2, 4:1, 5:2} -> CHOT 5
    #   {2:2, 4:3}        -> CHOT 5      {2:2, 4:1, 5:2} -> CHOT 7
    #   {2:2, 4:3}        -> CHOT 3      {2:2, 5:3}      -> CHOT 5 ...
    # Moi lenh bat acc `leave_party()` roi nhay kenh, nen party 5 dua dang DU bi xe ra va khong lan
    # nao gom xong. Sau do no dung chet 40 phut - "5/5 acc DUNG HINH" chi la HAU QUA cuoi chuoi.
    # (user 11/09: "truoc do da du party 5 dua va dang danh roi, sau do tu nhien dieu phoi lam cai
    #  gi ma no hong pt")
    if _co_party and _thieu_doi(pidx, song) and _dang_doi_kenh(song) and st.get("kenh_dich"):
        log.debug("[party %d] chot kenh: dang thi hanh lenh doi kenh -> GIU dich %s, khong quyet "
                  "lai (%s)", pidx + 1, st.get("kenh_dich"), _tinh_hinh_doi(song))
        return int(st["kenh_dich"])
    if _co_party and (not _thieu_doi(pidx, song) or _dang_doi_kenh(song)):
        with st["lock"]:
            if st.get("kenh_dich"):
                log.info("[party %d] DIEU PHOI: DA DU DOI (%s) -> thoi lenh doi kenh "
                         "(kenh_dich %s)", pidx + 1, _tinh_hinh_doi(song), st.get("kenh_dich"))
            st["kenh_dich"] = None
            st["kenh_dich_luc"] = 0.0
        return None
    # VUA HOI DANH SACH KENH -> CHO GOI VE ROI HAY CHOT. `request_channel_list` XOA `c.channels`
    # va goi `S:007-001` mat vai giay moi ve; chot trong khoang do la chot bang bang RONG hoac bang
    # cu, tuc chot bua.
    #
    # User chi ra 08/09 (party 8): "thay bot yeu cau danh sach kenh, nhung sau do deo thay chot lai
    # kenh" -> "danh sach kenh ve cham, phai cho may giay, ma may di nhanh qua truoc khi danh sach
    # ve". Log: leader xin danh sach 91 lan trong 4 phut ma dich khong doi.
    if song and any(
            float(getattr(_c, "_ds_kenh_hoi_luc", 0.0) or 0.0)
            > float(getattr(_c, "_ds_kenh_nhan_luc", 0.0) or 0.0)
            and time.time() - float(getattr(_c, "_ds_kenh_hoi_luc", 0.0) or 0.0) < DS_KENH_CHO_SEC
            for _u, _c in song):
        _cu2 = st.get("kenh_dich")
        return int(_cu2) if _cu2 else None
    hong, _ma3, _ma2 = _doc_ket_qua_doi_kenh(song)
    # (XOA 22/09) truoc day cho nay them mot so kenh nua vao so den: kenh ma party "cung so ma
    # khong thay nhau", tuc bot coi la kenh HU. User chot: instance voi kenh la MOT, nen khong co
    # kenh hu - so den chi duoc chua kenh SERVER TU CHOI (ma 2 = khong co khu, ma 4 = day).
    # Xem `documents/CORE_FLOW.md` muc "Su that ve game".
    if hong:
        # Server bao DAY tuc bang `c.channels` dang SAI (no noi kenh 27 con 12 cho, server tu choi).
        # Ep hoi lai `S:007-001` ngay thay vi doi het `DS_KENH_LAM_MOI_SEC` - chot tiep bang so cu
        # thi rat de lai chon dung mot kenh da day.
        st["ds_kenh_luc"] = 0.0
    if _ma3:
        # MA 3 <組隊不可換分區>: server noi acc DANG TO DOI nen khong doi kenh duoc. Mot acc tu roi
        # party roi thu lai la VO ICH - party la cua CA LU, con ai con trong doi thi server van coi
        # la dang to doi. Log 31/08 party 7 (14:45-14:55): leader tu xoay mot minh -> 67 luot ma 3,
        # quet het kenh 2,3,4,... trong 10 phut ma khong thoat.
        #
        # Truoc 07/09 chinh ACC gap ma 3 tu `_bump_reform`. Gio acc khong ra lenh cap party nua
        # (L1) - dieu phoi DOC THANG `_chan_switch_result` cua tung client (`_doc_ket_qua_doi_kenh`)
        # nen no thay ma 3 khong kem gi acc, va no la cho DUY NHAT duoc quyet.
        with st["lock"]:
            _luc3 = float(st.get("ma3_gom_luc", 0.0) or 0.0)
            _som3 = time.time() - _luc3 < LAP_LAI_PARTY_COOLDOWN
            if not _som3:
                st["ma3_gom_luc"] = time.time()
                _bump_reform(st, "co acc bi ma 3 (dang to doi) -> ca party roi doi + dong bo lai")
        if not _som3:
            log.warning("[party %d] DIEU PHOI: server chan doi kenh vi DANG TO DOI (ma 3) -> ra "
                        "lenh CA PARTY roi doi roi dong bo lai", pidx + 1)
        return None
    if _ma2:
        # `result=2` <沒有該分區> = dang trong INSTANCE cua event (thap 2K): khong co khai niem
        # "khu" de doi. Ra lenh doi kenh o day la ra lenh SAI LOAI - muon cung instance thi phai
        # DI CUNG NHAU QUA CONG. Party 5 (06/09) dinh dung cho nay luc 16:34:04.
        with st["lock"]:
            st["kenh_dich"] = None
            st["kenh_dich_luc"] = 0.0
        log.info("[party %d] DIEU PHOI: server bao KHONG CO KHU do (ma 2) -> dang trong instance "
                 "event, doi kenh vo nghia -> khong ra lenh doi kenh nua", pidx + 1)
        return None
    # DA CHOT ROI THI GIU - de nguoi ta THI HANH XONG cai lenh vua ra.
    #
    # Ham nay chay MOI 2 GIAY. Chot lai tu dau moi nhip = acc vua bat dau chuyen sang kenh A thi
    # phan bo doi -> chot kenh B -> ca lu quay dau -> phan bo lai doi -> chot A... Dung kieu thrash
    # da chua cho `gom`/`reform` bang grace + cooldown, ma ham nay lai khong co.
    # Log that party 3 (06/09), 4 phut moi dong bo xong:
    #   15:38:28 {1: 1, 2: 1}       -> CHOT 1
    #   15:38:38 {1: 1, 2: 2}       -> CHOT 2      (doi y sau 10 giay)
    #   15:41:27 {1: 2, 2: 2, 4: 1} -> CHOT 1
    #   15:41:39 {1: 3, 2: 1, 4: 1} -> CHOT 2
    # Dich chi duoc doi khi: kenh do VAO SO DEN (day), hoac qua han ma van chua ai toi noi.
    cu = st.get("kenh_dich")
    # MOI KENH DEU DAY -> GIU DICH, CHO CHO TRONG. Khong lat qua lat lai.
    #
    # `hong` chua kenh vua bi server tra ma 4. Khi ca party dang o toan kenh day, MOI acc thu mot
    # kenh la kenh do vao `hong` -> dich cu luon bi loai -> chot lai -> kenh moi cung day -> ...
    # Moi lan doi dich la mot lan acc ROI DOI + doi kenh, tuc tu tay pha cai dang gom.
    #
    # Ca that 09/09 party 1 (user: "p1") - CUNG mot phan bo ma ba ket qua, moi 2 giay mot lan:
    #   01:44:47 {12: 1, 44: 1, 52: 2, 66: 1} -> CHOT 12
    #   01:44:49 {12: 1, 44: 1, 52: 2, 66: 1} -> CHOT 52
    #   01:44:51 {12: 2, 44: 1, 52: 2}        -> CHOT 52
    #   01:44:53 {12: 2, 44: 1, 52: 2}        -> CHOT 44
    # Ca nam acc deu `S:007-002 ma 4`. User chot: het kenh trong thi cu cho, dung nhay lung tung.
    if cu and dem and all(int(_ch) in hong for _ch in dem):
        # "HET KENH TRONG THI CU CHO" (user 09/09) phai hieu la MOI KENH CUA MAP deu day, chu
        # KHONG phai "moi kenh party dang dung deu day" - party moi dung co 2 kenh trong ca chuc
        # kenh cua map. Truoc day cho nay `return` thang, nen `_kenh_trong_cho_ca_party` - dung
        # cai ham BIET kenh nao con cho - khong bao gio duoc goi o dung luc can no nhat.
        #
        # Ca that 21/09 party 34 (user: "moi dua 1 kenh"): leader o kenh 10, 2 member o kenh 8,
        # ca hai vao so den. Suot tu 02:05 den 02:11 (va con tiep):
        #   02:11:44 [party 34] DIEU PHOI: MOI kenh party dang dung deu DAY [8, 10] -> GIU kenh
        #            dich 10, cho co cho trong (khong doi y)
        #   02:11:56 [dvhai]   Doi kenh 10 TIMEOUT sau 4.0s ... -> ket qua -1
        #   02:11:57 [dvinnam] Doi kenh 10 TIMEOUT sau 4.0s ... -> ket qua -1
        # `lap_party` quay vong 400 lan vi khong bao gio co ai cung kenh de moi.
        _lam_moi_ds_kenh(pidx, st, song)
        _kenh_moi = _kenh_trong_cho_ca_party(pidx, st, song, hong)
        if _kenh_moi:
            with st["lock"]:
                st["kenh_dich"] = int(_kenh_moi)
                st["kenh_dich_luc"] = time.time()
            return int(_kenh_moi)
        with st["lock"]:
            st["kenh_dich_luc"] = time.time()      # gia han de khong roi vao nhanh "qua han"
        log.info("[party %d] DIEU PHOI: MOI kenh party dang dung deu DAY %s va KHONG kenh nao "
                 "khac du %d cho -> GIU kenh dich %s, cho co cho trong (khong doi y)",
                 pidx + 1, sorted(hong), len(song), cu)
        return int(cu)
    if cu and int(cu) not in hong:
        _luc = float(st.get("kenh_dich_luc", 0.0) or 0.0)
        if time.time() - _luc < KENH_DICH_KIEN_NHAN_SEC:
            return int(cu)                   # dang thi hanh -> GIU, dung doi y
        # QUA HAN NHUNG DANG TIEN TRIEN -> GIA HAN, dung chot lai. Chot lai luc gan xong la bat
        # ca party quay dau: log 07/09 party 1 luc 20:40:06 - `kenh dich 45 qua 45s van chua gom
        # xong ({6: 1, 45: 4})` - 4/5 acc DA sang 45, chi con mot dua, the ma no doi dich.
        if int(dem.get(int(cu), 0)) > len(song) // 2:
            with st["lock"]:
                st["kenh_dich_luc"] = time.time()
            log.info("[party %d] DIEU PHOI: kenh dich %s qua han nhung DA GOM DUOC %d/%d -> GIA "
                     "HAN, khong doi dich (%s)", pidx + 1, cu, int(dem.get(int(cu), 0)), len(song),
                     dict(sorted(dem.items())))
            return int(cu)
        # LENH CHUA GUI DUOC THI KHONG PHAI "KENH NAY KHONG GOM DUOC" -> GIA HAN, dung chot lai.
        #
        # `_engine_gui_lenh_kenh` khong gui `0x07` cho acc dang trong tran (doi instance giua
        # tran -> `S:000-000` ma 47 -> dut ket noi). Nhung dong ho `kenh_dich_luc` van chay, nen
        # het KENH_DICH_KIEN_NHAN_SEC la chot mot kenh KHAC - trong khi kenh cu chua he duoc thu.
        # Chot bao nhieu lan cung the: acc van dang trong tran.
        #
        # Ca that 22/09 party 3 (user: "danh boss the gioi xong no dung o Trac Quan lam lon gi
        # the"), ca party dang danh boss the gioi TAI Trac Quan 12001:
        #   12:54:14 CHOT kenh dich = 10
        #   12:54:14 CHUA gui lenh doi kenh 10 cho laochin - dang TRONG TRAN
        #   12:54:14 CHUA gui lenh doi kenh 10 cho xGAx    - dang TRONG TRAN
        #   12:54:59 kenh dich 10 qua 45s van chua gom xong -> chot lai -> CHOT kenh dich = 9
        #   12:54:59 CHUA gui lenh doi kenh 9 cho thmo/thha - dang TRONG TRAN
        #   12:56:10 ... KHONG THAY duoc dong doi -> (ban cu) danh dau kenh 9 la HONG, chot kenh KHAC
        #   13:15:22 van 'dong_bo' (... y het ...)                 <- 19 phut khong di dau
        _ban_tran = [getattr(_c, "_label", _u) for _u, _c in song
                     if int(getattr(_c, "current_channel", 0) or 0) != int(cu)
                     and not _kenh_doi_duoc_ngay(_c, st)]
        if _ban_tran:
            with st["lock"]:
                st["kenh_dich_luc"] = time.time()
            if time.time() - float(st.get("kenh_ban_tran_log", 0.0) or 0.0) > 60.0:
                st["kenh_ban_tran_log"] = time.time()
                log.info("[party %d] DIEU PHOI: kenh dich %s qua han nhung %s CHUA NHAN duoc lenh "
                         "(dang ban) -> GIA HAN, khong chot kenh khac (%s)",
                         pidx + 1, cu, _ban_tran, dict(sorted(dem.items())))
            return int(cu)
        log.info("[party %d] DIEU PHOI: kenh dich %s qua %.0fs van chua gom xong (%s) -> chot lai",
                 pidx + 1, cu, KENH_DICH_KIEN_NHAN_SEC, dict(sorted(dem.items())))
    # CHON KENH PHAI XET CON CHO. Ban cu chi lay "kenh dong nguoi nhat trong party" roi moi phat
    # hien no DAY (server tra ma 4) -> kenh do vao `hong` -> chot lai kenh khac -> lai day -> ...
    # Log that 40NPC (07/09), CUNG mot phan bo ma chot ba kenh khac nhau trong 12 giay:
    #   20:24:38 {5: 3, 12: 1, 13: 1} -> CHOT 13
    #   20:24:40 {5: 3, 12: 1, 13: 1} -> CHOT 5
    #   20:24:46 {5: 3, 12: 1, 13: 1} -> CHOT 13
    #   20:24:50 {5: 3, 12: 1, 13: 1} -> CHOT 12
    # Moi lan doi y la ca party quay dau -> khong bao gio gom xong (user: "phai gom bang duoc kenh
    # chu"). Va `_kenh_trong_cho_ca_party` - dung cai ham BIET kenh nao con cho - thi truoc day chi
    # chay khi MOI kenh party dang dung deu hong, tuc gan nhu khong bao gio (user: "sao cai tim
    # kenh it nguoi nhat chi chay 1 lan").
    _can = len(song)
    # LUAT CHON KENH (user chot 07/09):
    #   1. Kenh IT NGUOI NHAT ma DU CHO ca team  -> sang do.
    #   2. Khong kenh nao du cho                 -> kenh dang co NHIEU MEMBER NHAT.
    #
    # Ban cu bo qua han buoc 1: no chi lay "kenh dong member nhat" roi moi phat hien kenh do DAY
    # (server tra ma 4) -> vao `hong` -> chot lai -> lai day -> ... Log 40NPC (07/09), CUNG mot
    # phan bo ma chot ba kenh khac nhau trong 12 giay:
    #   20:24:38 {5: 3, 12: 1, 13: 1} -> CHOT 13
    #   20:24:40 {5: 3, 12: 1, 13: 1} -> CHOT 5
    #   20:24:46 {5: 3, 12: 1, 13: 1} -> CHOT 13
    #   20:24:50 {5: 3, 12: 1, 13: 1} -> CHOT 12
    # Moi lan doi y la ca party quay dau -> khong bao gio gom xong.
    #
    # `c.channels` truoc day chi nap MOT LAN trong `pick_best_channel` roi khong ai cap nhat, ma so
    # nguoi/kenh thi doi lien tuc -> phai hoi lai (cach quang, tranh spam `0x07 0100` -> ma 13).
    _lam_moi_ds_kenh(pidx, st, song)
    # CHI LAY DANH SACH KENH CUA MAP DANG DUNG (`map_chung` - toi day thi ca party da cung map,
    # vong dem o tren da `return None` neu con lech). Moi map mot danh sach kenh khac nhau.
    _bang = _bang_kenh(song, map_id=map_chung)     # {kenh: (dang_o, con_trong)}
    def _con_cho(ch):
        _c = _bang.get(int(ch))
        return None if _c is None else _c[1]      # None = chua biet suc chua

    # (a) KENH IT NGUOI NHAT MA DU CHO CA TEAM. Day la buoc DAU TIEN, khong phai duong lui.
    #
    #     User chot 07/09 va nhac lai 08/09: "phai tim kenh it nguoi nhat truoc chu, ko co kenh nao
    #     du cho ca team thi moi chon kenh nhieu member nhat".
    #
    #     TUNG co mot buoc dung TRUOC buoc nay - "uu tien kenh party dang dung cho do di lai" - do
    #     la thu TOI TU THEM VAO, khong phai luat user ra, va no de ra dung cai no dinh tranh:
    #       06:57:48 [party 15] party lech kenh {3: 4, 4: 1} -> CHOT kenh dich = 3
    #       06:58:02 [party 15] party lech kenh {3: 4, 4: 1} -> CHOT kenh dich = 4
    #     Kenh 3 (4 acc) bi bao DAY nen vao so den, the la no chot kenh 4 - noi dung MOT acc le -
    #     roi bat 4 nguoi kia di theo mot kenh cung sap day.
    #
    #     Lo "nhay kenh lien tuc" khong phai chan bang cach uu tien kenh dang dung, ma bang HAN
    #     KIEN NHAN (`KENH_DICH_KIEN_NHAN_SEC` + gia han khi da gom duoc da so) o dau ham nay.
    _ung = [(dang, ch) for ch, (dang, con) in _bang.items()
            if ch not in hong and con >= _can]
    if not _ung and getattr(hong, "doan", None):
        # Het ung vien, ma mot phan so den chi la SUY DOAN tu timeout (khong phai server noi).
        # Bo phan doan ra roi tim lai - ton nhat la them mot lan doi kenh, con giu thi ca party
        # phai chot bua vao kenh dang DAY (party 2, 10/09). Xem `_SoDen`.
        _chac = hong.chac()
        _ung = [(dang, ch) for ch, (dang, con) in _bang.items()
                if ch not in _chac and con >= _can]
        if _ung:
            log.info("[party %d] DIEU PHOI: so den co %d kenh chi TIMEOUT (khong phai server bao "
                     "day) -> bo qua chung, tim lai duoc %d kenh du cho",
                     pidx + 1, len(hong.doan), len(_ung))
    if _ung:
        dich = min(_ung)[1]
        _vi_sao = "kenh IT NGUOI NHAT ma du cho ca team (con %d cho)" % (_bang[dich][1],)
    else:
        # (b) Khong kenh nao du cho ca team -> kenh dang co NHIEU MEMBER NHAT.
        #
        # `dem` dem `current_channel` cua tung acc - va so do KHONG PHAI LUC NAO CUNG LA KENH THE
        # GIOI: trong instance (Di Gioi, thap 2K, boss quan doan) no la instanceId. Chot vao mot
        # instanceId roi ra lenh doi kenh = server tra ma 2 <沒有該分區> cho ca party.
        #
        # Ca that 08/09 party 11 (user: "no bia kenh 27 o dau ra day") - 5 acc o map 49951, moi
        # dua mot so LIEN TIEP, hoa nhau nen bot lay so nho nhat:
        #   14:05:57 [party 11] party lech kenh {27: 1, 28: 1, 29: 1, 30: 1, 31: 1}
        #                       -> CHOT kenh dich = 27 (khong kenh nao du cho -> NHIEU MEMBER NHAT)
        #   14:09:44..14:10:08  ca NAM acc: "Doi kenh 27 THAT BAI: khong co khu do (result=2)"
        #
        # Nen chi chon so nao CO MAT trong danh sach kenh that (`S:007-001`). Bang rong (chua nhan
        # duoc goi) thi moi dung tam `dem` nhu cu - khong co gi khac de dua vao.
        # NOI RO VI SAO khong co ung vien - dung de nguoi doc log phai doan.
        #
        # Ca that 10/09 party 2 (user: "sao lai chot kenh 8 bi full trong khi rat nhieu kenh khac
        # trong"): bang co 57 kenh, ma moi nhip deu roi xuong nhanh nay. Nhin log cu KHONG the biet
        # 57 kenh do deu day that, hay bi so den nuot, hay suc chua doc sai - ba nguyen nhan khac
        # han nhau. Gio in thang: bao nhieu kenh trong bang, bao nhieu bi so den, va kenh RONG NHAT
        # con may cho.
        _rong_nhat = max((con for _ch, (_d, con) in _bang.items()), default=None)
        _bi_den = sum(1 for _ch in _bang if _ch in hong)
        log.info("[party %d] DIEU PHOI: khong kenh nao du %d cho - bang %d kenh, so den %d kenh, "
                 "kenh rong nhat con %s cho", pidx + 1, _can, len(_bang), _bi_den,
                 _rong_nhat if _rong_nhat is not None else "?")
        _co_that = [ch for ch in dem if ch in _bang]
        _nguon = {ch: _n for ch, _n in dem.items() if ch in _bang} if (_bang and _co_that) else dem
        xep = [ch for ch, _n in sorted(_nguon.items(), key=lambda kv: (-kv[1], kv[0]))
               if ch not in hong]
        dich = xep[0] if xep else _kenh_trong_cho_ca_party(pidx, st, song, hong)
        _vi_sao = "khong kenh nao du cho ca team -> lay kenh dang NHIEU MEMBER NHAT"
    if not dich:
        return None                          # moi kenh party dang dung deu day -> cho nhip sau
    with st["lock"]:
        st["kenh_dich"] = dich
        st["kenh_dich_luc"] = time.time()
    if cu != dich:
        log.info("[party %d] DIEU PHOI: party lech kenh %s -> CHOT kenh dich = %d (%s)",
                 pidx + 1, dict(sorted(dem.items())), dich, _vi_sao)
    return dich


# Ra lenh LAP LAI PARTY roi thi phai cho no lam xong. Moi `_bump_reform` la abort moi acc dang
# di duong, nen bump lien tuc = tu huy viec minh vua sai. Mot vong gom + moi lai mat vai chuc giay.
LAP_LAI_PARTY_COOLDOWN = 120.0
# `gom_dich` chi dang tin bay nhieu giay. Mot vong gom ve thanh + moi lai mat vai chuc giay; qua
# han ma van con dich = vong do da thoat bang duong khong xoa duoc dich (abort/timeout/bo cuoc).
GOM_DICH_HAN_SEC = 180.0

# Da chot kenh dich thi GIU bay lau truoc khi duoc chot lai. Doi kenh mat ~1 giay, nhung acc
# dang danh/dang di duong phai cho xong viec moi chuyen duoc -> cho rong rai.
KENH_DICH_KIEN_NHAN_SEC = 45.0

# Truoc khi len tang 2K: cho bay lau de moi lai cho du party. Doi kenh xong -> member phai
# accept loi moi; 4 dua thi vai giay. Cho rong rai vi ho co the dang doi kenh do.
DU_PARTY_TRUOC_CONG_SEC = 60.0
# KET o cong 2K -> nghi bao lau truoc khi thu lai. Engine cu thoat han vong leo (dieu phoi gom +
# moi lai roi resume), engine moi nhip 1 giay nen phai co cho nghi nay - khong thi bam cong 200
# lan/3 phut (party 7, 20/09) va di thang toi ma 13 "gui goi lien tuc qua nhanh".
FC_KET_CONG_NGHI_SEC = 30.0

# Ma doi kenh cu hon the thi coi nhu da lac hau (nguoi ra vao lien tuc, kenh day roi lai trong).
KENH_MA_CON_MOI_SEC = 120.0


class _SoDen(set):
    """So den kenh, co phan biet BANG CHUNG CHAC voi SUY DOAN.

    Server tra ma 2 `<沒有該分區>` / ma 4 `<分區人數已滿>` la NOI RO. Con `-1` la bot tu dat khi
    `switch_channel` het luot ma server im lang - do la KHONG BIET, khong phai "kenh day".

    Ca that 10/09 party 2 (user: "sao lai chot kenh 8 bi full trong khi rat nhieu kenh khac trong"):
    hai duong cung gui lenh doi kenh cho mot acc -> server tra MOT ket qua, luong kia timeout ->
    `-1` -> kenh do vao so den. Timeout hang loat thi so den nuot sach ung vien, nhanh "kenh it
    nguoi nhat ma du cho ca team" khong con gi de chon -> roi xuong nhanh cuoi va chot bua vao mot
    trong ba kenh party dang dung, ca ba deu DAY.

    Nguyen tac: thong tin YEU chi duoc dung khi no khong tuoc mat lua chon. Het ung vien thi bo qua
    phan suy doan va thu lai - cung lam la ton them mot lan doi kenh.
    """

    def __new__(cls, chac_va_doan, doan):
        ra = super().__new__(cls, chac_va_doan)
        return ra

    def __init__(self, chac_va_doan, doan):
        super().__init__(chac_va_doan)
        self.doan = set(doan)

    def chac(self):
        """Chi cac kenh server NOI RO la khong vao duoc."""
        return {ch for ch in self if ch not in self.doan}


def _doc_ket_qua_doi_kenh(song):
    """DOC THANG ket qua doi kenh cua tung client - KHONG bat acc nao bao cao.

    Ca 5 acc nam trong MOT tien trinh, moi client tu giu `_chan_switch_result` (ma server tra),
    `_chan_switch_target` (nham kenh nao) va `_chan_switch_luc` (luc nao). Dieu phoi chi viec doc.

    Ban dau toi bat acc goi `bao_kenh_day()` de bao len - vi pham dung luat user chot 06/09:
    "bot la nguoi dieu phoi, deo phai cho dua nao bao cao". Bot BIET HET, khong co gi phai bao.

    Ma server (`client._on_channel_switch_result`): 0 OK · 1 trung khu dang o ·
    2 KHONG CO KHU DO · 3 DANG TO DOI · 4 KENH DAY.

    -> (kenh_day, co_ma3, co_ma2)
       kenh_day = cac kenh KHONG VAO DUOC (ma con moi) -> dung chot vao do nua
       co_ma3   = co acc bi chan vi dang to doi -> doi kenh se lam TAN DOI, xong phai lap lai
       co_ma2   = server bao khong co khu do -> dang trong INSTANCE event, doi kenh vo nghia

    `kenh_day` co them thuoc tinh `.doan` = tap con CHI DUA TREN TIMEOUT. Timeout la KHONG BIET,
    khong phai bang chung kenh day - xem `_hong_chac`.
    """
    bay = time.time()
    day, ma3, ma2 = set(), False, False
    doan, chac = set(), set()
    for _u, c in song:
        r = getattr(c, "_chan_switch_result", None)
        if r is None:
            continue
        if bay - float(getattr(c, "_chan_switch_luc", 0.0) or 0.0) > KENH_MA_CON_MOI_SEC:
            continue                      # ma cu roi (nguoi ra vao lien tuc) -> bo qua
        if r in (4, -1):
            (doan if r == -1 else chac).add(int(getattr(c, "_chan_switch_target", None) or 0))
            # 4 = kenh DAY. -1 = `switch_channel` het luot ma server IM LANG (timeout).
            #
            # Timeout truoc day bi BO QUA hoan toan o day: acc thu mai khong vao duoc, con dieu
            # phoi thi khong thay ma nao nen cu giu nguyen dich - "check ket qua ma khong dung"
            # (user 08/09). Ca hai deu la KHONG VAO DUOC kenh do, nen doi xu nhu nhau: cam chot
            # vao no. `hong` chi song `KENH_MA_CON_MOI_SEC` roi tu het han, nen neu timeout chi vi
            # mang chap chon thi vai phut sau van thu lai duoc.
            t = getattr(c, "_chan_switch_target", None)
            if t:
                day.add(int(t))
        elif r == 3:
            ma3 = True
        elif r == 2:
            ma2 = True
            # MA 2 <沒有該分區> noi thang: KENH DO KHONG TON TAI. Truoc day no chi bat mot co CHUNG
            # (`ma2`) con so kenh thi khong ai ghi lai -> nhip sau chot lai DUNG kenh do, ca party
            # lai dam dau vao. Cam chot vao no y het kenh DAY.
            #
            # Ca that 08/09 party 11 (user: "server da bao ko co kenh do roi ma van co") - ca NAM
            # acc cung mot ma, cung mot kenh:
            #   14:05:57 [party 11] party lech kenh {27: 1, 28: 1, 29: 1, 30: 1, 31: 1}
            #                       -> CHOT kenh dich = 27
            #   14:09:44 [luuchin] Doi kenh 27 THAT BAI: khong co khu do de doi (result=2)
            #   14:09:47 [luumuoi] Doi kenh 27 THAT BAI: khong co khu do de doi (result=2)
            #   14:09:48 [luubay]  Doi kenh 27 THAT BAI: khong co khu do de doi (result=2)
            #   14:09:48 [luutam]  Doi kenh 27 THAT BAI: khong co khu do de doi (result=2)
            #   14:10:08 [luusau]  Doi kenh 27 THAT BAI: khong co khu do de doi (result=2)
            t = getattr(c, "_chan_switch_target", None)
            if t:
                day.add(int(t))
                chac.add(int(t))
    # `doan` chi giu kenh KHONG co bang chung chac nao. Mot acc timeout ma acc khac nhan ma 4 thi
    # kenh do la CHAC - bang chung manh thang.
    return _SoDen(day, (doan - chac) - {0}), ma3, ma2


DS_KENH_LAM_MOI_SEC = 20.0   # khoang cach toi thieu giua hai lan hoi lai danh sach kenh
# Ban danh sach kenh cu hon the thi bo (nguoi ra vao lien tuc -> so cho khong con dung). Rong rai
# hon `DS_KENH_LAM_MOI_SEC` vai lan de luon con ban dung duoc giua hai lan hoi.
DS_KENH_QUA_CU_SEC = 120.0
DS_KENH_CHO_SEC = 5.0        # hoi xong thi cho toi ngan nay cho `S:007-001` ve roi moi chot kenh


def _lam_moi_ds_kenh(pidx, st, song):
    """Hoi lai `S:007-001 <分區列表>` cho MOT acc trong party (cach quang).

    Chi can mot acc hoi la ca party co du lieu (`_suc_chua_kenh` hop tu moi client). Hoi tung acc
    moi nhip la spam `0x07 0100` -> nguy co `ma 13` (gui goi qua nhanh)."""
    if time.time() - float(st.get("ds_kenh_luc", 0.0) or 0.0) < DS_KENH_LAM_MOI_SEC:
        return
    st["ds_kenh_luc"] = time.time()
    for _u, c in song:
        if not getattr(c, "running", False):
            continue
        try:
            if c.in_combat():          # dang danh -> de acc khac hoi
                continue
            c.request_channel_list()
        except Exception as e:
            log.debug("[%s] hoi danh sach kenh loi (bo qua): %s", _u, e)
        return


def _bang_kenh(song, map_id=None):
    """{kenh: (dang_o, con_trong)} - danh sach kenh CUA MAP `map_id`, hop tu cac client trong party.

    `c.channels` = {kenh: (dang_o, suc_chua)} tu `S:007-001 <分區列表>`. Moi acc co the giu mot ban
    lay o thoi diem khac nhau -> lay ban BI QUAN NHAT (it cho nhat) cho chac.

    BO BAN QUA CU: nguoi ra vao kenh lien tuc nen so cho cua ban vai phut truoc la vo nghia. Nhung
    "cu" khac han "rong" - bang cu vai chuc giay van chon duoc kenh, con bang rong thi bat dieu phoi
    chot bua (xem `request_channel_list`).

    BO BAN CUA MAP KHAC: MOI MAP MOT DANH SACH KENH. Ban cu gop bang cua moi acc bat ke no dang o
    dau, nen acc con o map cu dem theo kenh cua map cu vao bang - va dieu phoi co the chot vao mot
    so KHONG TON TAI o map dang dung.

    Ca that party 3, 14/09 (user: "thay chot kenh 7, ma tuong duong deo co kenh 7" -> "no deo phai
    kenh rac ma la kenh khi no o map khac, phai la khi ca pt cung map can lap pt thi moi lay danh
    sach kenh chu"):
        15:50:31 [party 3] con lech map [12001, 21001] ... baybay@12001/k2 minh@12001/k7
        15:50:35 [party 3] party lech kenh {1:1, 2:1, 3:1, 7:2} -> CHOT kenh dich = 7
    """
    ra = {}
    bay = time.time()
    for _u, c in song:
        if bay - float(getattr(c, "_ds_kenh_nhan_luc", 0.0) or 0.0) > DS_KENH_QUA_CU_SEC:
            continue
        if map_id is not None:
            _m = int(getattr(c, "_ds_kenh_map", 0) or 0)
            if _m and _m != int(map_id):
                continue        # bang nay lay o MAP KHAC -> kenh trong do khong dung cho map nay
        for ch, cap in (getattr(c, "channels", None) or {}).items():
            try:
                dang, toi_da = int(cap[0]), int(cap[1])
            except Exception:
                continue
            ch = int(ch)
            con = max(0, toi_da - dang)
            if ch not in ra or con < ra[ch][1]:
                ra[ch] = (dang, con)
    return ra


def _kenh_trong_cho_ca_party(pidx, st, song, hong):
    """Moi kenh party dang dung deu trong so den -> tim kenh MOI du cho CA party.

    Dung danh sach kenh acc nao do vua nhan duoc (`c.channels` = {ch: (dang, toi_da)}).
    Khong hoi lai server o day: dieu phoi chay moi 2 giay, hoi moi nhip la spam.
    """
    can = len(song)
    tot = None
    for _u, c in song:
        for ch, cap in (getattr(c, "channels", None) or {}).items():
            try:
                dang, toi_da = int(cap[0]), int(cap[1])
            except Exception:
                continue
            if int(ch) in hong or toi_da - dang < can:
                continue
            if tot is None or dang < tot[1]:
                tot = (int(ch), dang)
    if tot:
        log.info("[party %d] DIEU PHOI: moi kenh party dang dung deu DAY %s -> doi ca party sang "
                 "kenh trong %d (%d cho dang dung)", pidx + 1, sorted(hong), tot[0], tot[1])
        return tot[0]
    return None


def _engine_chot_map(pidx, st):
    """DIEU PHOI chot cap quai DG / map train - KHONG de luong acc nao tu chot.

    Hai ham `_auto_*` tu tra None khi chua du level ca party, ma dieu phoi goi lai moi 2 giay,
    nen no chot NGAY GIAY dau tien du du lieu. Luong acc chi doc `st["auto_dg_level"]` /
    `st["auto_train"]`.
    """
    pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
    raw_mode = pcfg.get("mode")
    try:
        _dgp = pcfg.get("di_gioi_pick") or ""
        if _dgp in train_pick.PICK_KEYS and not st.get("auto_dg_level"):
            _auto_dg_level(pidx, _dgp)
        if (raw_mode in ("train", "digioi_train") and pcfg.get("train_pick")
                and not st.get("auto_train")):
            _auto_train_target(pidx, pcfg)
    except Exception as e:
        log.warning("[party %d] DIEU PHOI chot map loi (bo qua nhip nay): %s", pidx + 1, e)


# ===================== WATCHER: QUAN SAT VIEC CUA CA PARTY =====================
# Doc bao cao "dang lam gi" cua tung acc (bot/client.py: account_task/get_account_task) roi ket
# luan o MOT CHO, thay vi de moi vong cho tu phan doan.
WATCH_EVERY_SEC = 20        # nhip quet
WATCH_STUCK_AGE = 180       # acc khong cap nhat tien do qua lau -> nghi TREO
WATCH_MISMATCH_SEC = 300    # ca party lech viec lien tuc qua lau -> ep dong bo
WATCH_SOLO_MAX = 1800       # viec le chay qua 30' -> bat thuong, bao (khong tu ep)

_PHASE_SOLO = ("login_chore", "boss_qd")     # viec LE: dong doi phai CHO, khong phai lech viec
_PHASE_TEAM = ("train", "reform", "team_dungeon", "digioi")
_PHASE_WAIT = "wait"                        # dang CHO dong doi - KHONG phai treo (xem duoi)
WATCH_ALLWAIT_SEC = 120                     # CA PARTY cung cho qua lau = deadlock that
# Bao cao "dang cho" phai con TUOI thi moi tinh la CHO THAT. Acc cho that lam moi bao cao MOI VONG
# LAP (~1-2s: reform route, reform ve thanh, PB cho leader, PB cho report) -> tuoi luon ~1s.
# Bao cao GIA = acc DA di lam viec khac ma khong ai doi pha -> tuoi tang vo han.
WATCH_WAIT_FRESH_SEC = 15                   # bien rong gap ~7 lan nhip lam moi
# Party o map train ma THIEU NGUOI lien tuc qua lau -> ep dong bo. Doc THANG so nguoi da join,
# khong qua bao cao pha, nen khong bi cac la chan "co nguoi dang lam" che mat.
WATCH_THIEU_NGUOI_SEC = 300





def start_all():
    """START TAT CA = khoi dong nhung gi CHUA chay, KHONG dung-roi-chay-lai cai dang chay.

    Truoc day goi start_party() thang -> start_account() giet thread cu (join toi 12s) roi login
    lai tu dau, nen party dang chay ngon bi pha (user bao: "start rieng vai party roi start all
    thi party da chay van bi chay lai").
    """
    n = 0
    skipped = 0
    for pidx in range(len(config.PARTIES)):
        accs = [u for u, _p, _l, _k in party_accounts(pidx)]
        run = sum(1 for u in accs if is_account_running(u))
        if accs and run == len(accs):
            skipped += 1
            continue                    # ca party dang chay du -> khong dung toi
        n += start_party(pidx, skip_running=True)
    if skipped:
        log.info(">>> START TAT CA: bo qua %d party dang chay, khoi dong %d acc", skipped, n)
    return n


def redeem_giftcode_party(pidx, code):
    """Nhap GIFTCODE cho TAT CA acc DANG CHAY cua party pidx (moi acc 1 luong song song).
    Qua giftcode ve mail -> acc tu claim_mail trong redeem_giftcode."""
    code = (code or "").strip()
    targets = [u for u, _p, _l, _pk in party_accounts(pidx)
               if is_account_running(u) and account_clients.get(u) is not None]
    if not code:
        log.warning(">>> PARTY %s: giftcode rong -> bo qua", pidx + 1)
        return 0
    if not targets:
        log.warning(">>> PARTY %s: KHONG co acc nao dang chay -> khong nhap giftcode '%s'",
                    pidx + 1, code)
        return 0
    log.info(">>> PARTY %s: nhap giftcode '%s' cho %d acc dang chay...", pidx + 1, code, len(targets))
    def _one(u):
        c = account_clients.get(u)
        if c is None:
            return
        try:
            c.redeem_giftcode(code)
        except Exception as e:
            log.warning("[%s] loi nhap giftcode: %s", u, e)
    ths = [threading.Thread(target=_one, args=(u,), daemon=True) for u in targets]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=15)
    log.info(">>> PARTY %s: da gui giftcode '%s' cho %d acc", pidx + 1, code, len(targets))
    return len(targets)


def get_channel_list(pidx):
    """Hoi server danh sach kenh (co so nguoi) cho party pidx -> dict {ch: (cur, cap)}.
    Dung 1 acc DANG CHAY cua party de hoi. Tra {} neu khong co acc chay / khong lay duoc."""
    targets = [u for u, _p, _l, _pk in party_accounts(pidx)
               if is_account_running(u) and account_clients.get(u) is not None]
    if not targets:
        return {}
    c = account_clients.get(targets[0])
    try:
        c.request_channel_list()
        if c._chan_event.wait(3.0):
            return dict(c.channels)
    except Exception as e:
        log.warning(">>> PARTY %s: loi lay list kenh: %s", pidx + 1, e)
    return {}


def party_set_di_gioi_level(pidx, idx):
    """GUI ra lenh: CA party pidx doi CAP QUAI Di Gioi -> idx (1..15). Gui THANG toi cac acc dang
    chay (fire-and-forget, khong huy party/khong vao lai DG - gói 0x61 02 00 idx doi live). Cung
    luu vao PARTY_CONFIG de acc vao DG sau nay dung dung cap."""
    idx = max(1, min(int(idx), 15))
    try:
        config.PARTY_CONFIG.setdefault(int(pidx), {})["di_gioi_level"] = idx
    except Exception:
        pass
    n = 0
    for u, _p, _l, _pk in party_accounts(pidx):
        c = account_clients.get(u)
        if c is not None and getattr(c, "running", False):
            try:
                c.set_di_gioi_level(idx); n += 1
            except Exception as e:
                log.warning(">>> PARTY %s: loi doi cap DG cho %s: %s", pidx + 1, u, e)
    log.info(">>> PARTY %s: lenh DOI CAP QUAI DI GIOI -> idx %d (da gui %d acc dang chay)",
             pidx + 1, idx, n)


def party_switch_channel(pidx, channel):
    """GUI ra lenh: CA party pidx huy party + chuyen sang KENH 'channel' -> roi tiep tuc che do
    da setup (xu ly trong vong keepalive qua cmd_gen)."""
    st = _pstate(pidx)
    with st["lock"]:
        st["cmd"] = ("channel", int(channel))
        st["cmd_gen"] += 1
    log.info(">>> PARTY %s: lenh DOI KENH -> %d (huy party + ca lu chuyen + tiep tuc che do)",
             pidx + 1, channel)


def party_teleport_city(pidx, city_id, flag=0):
    """GUI ra lenh: CA party pidx huy party + teleport ve THANH (city_id, flag) -> roi tiep tuc
    che do da setup (xu ly trong vong keepalive qua cmd_gen)."""
    st = _pstate(pidx)
    with st["lock"]:
        st["cmd"] = ("city", int(city_id), int(flag))
        st["cmd_gen"] += 1
    log.info(">>> PARTY %s: lenh TELEPORT ve thanh %s (flag %s) (huy party + ca lu teleport)",
             pidx + 1, city_id, flag)


def party_route_maps(pidx, source_map=0, dest_map=0):
    """GUI ra lenh: lap/keo party di tu map source_map toi dest_map bang smart world route.
    source_map=0 -> leader tu chon thanh gan dest_map nhat lam diem bat dau."""
    mode = (config.PARTY_CONFIG.get(int(pidx), {}) or {}).get("mode")
    if mode not in ("city", "stand"):
        log.warning(">>> PARTY %s: bo qua lenh DI MAP vi mode=%s khong phai city/stand",
                    int(pidx) + 1, mode)
        return
    source_map = int(source_map or 0)
    dest_map = int(dest_map or 0)
    if dest_map <= 0:
        log.warning(">>> PARTY %s: route map bi bo qua vi BBB khong hop le: %s",
                    pidx + 1, dest_map)
        return
    if not _active_party_usernames(pidx):
        log.warning(">>> PARTY %s: KHONG co acc nao dang chay -> khong route map %s -> %s",
                    pidx + 1, source_map or "AUTO", dest_map)
        return
    st = _pstate(pidx)
    with st["lock"]:
        new_gen = st["cmd_gen"] + 1
        st["cmd"] = ("route", source_map, dest_map)
        st["cmd_gen"] = new_gen
        # Reset NGAY khi GUI phat lenh, khong doi thread dau tien bat duoc lenh moi reset.
        # Acc dang reconnect/login sau lenh se thay route active va van xu ly cmd_gen nay.
        st["manual_route_gen"] = new_gen
        st["manual_route_plan"] = None
        st["manual_route_source_results"] = {}
        st["manual_route_city_arrived"] = {}
        st["manual_route_plan_ready"].clear()
        st["manual_route_source_done"].clear()
        st["manual_route_party_ready"].clear()
        st["manual_route_done"].clear()
    log.info(">>> PARTY %s: lenh DI MAP %s -> %s (AAA=0 la tu chon thanh gan BBB)",
             pidx + 1, source_map or "AUTO", dest_map)


def stop_account(username, reason="GUI Stop acc"):
    """Dung 1 acc: set event + dong ket noi -> thread tu ket thuc."""
    try:
        import inspect
        fr = inspect.stack()[1]
        caller = "%s:%s:%s" % (os.path.basename(fr.filename), fr.lineno, fr.function)
    except Exception:
        caller = "?"
    ev = account_stops.get(username)
    if ev is not None:
        ev.set()
    # CHAN CUNG relogin sau STOP: supervisor break neu _st() HOAC account_reconnect False. Set
    # False ngay (khong doi finally cua run_account) -> du acc dang giua chu ky login/daily, khi
    # run_account tra ve la supervisor thoat, KHONG relogin. Log ro de thay Python co nhan lenh.
    account_reconnect[username] = False
    account_stop_reasons[username] = reason
    log.info("[%s] STOP: %s (caller=%s, set stop_ev + chan relogin)", username, reason, caller)
    c = account_clients.get(username)
    if c is not None:
        # KHONG dong socket ngay neu thread tu xu ly viec thoat:
        #  - leader map-train: tu chay ve safe roi dong.
        #  - member train: cho leader ve safe (stop_leader_done) roi moi dong.
        if getattr(c, "_return_safe_on_stop", None) or getattr(c, "_wait_leader_on_stop", None):
            if getattr(c, "_return_safe_on_stop", None):
                log.info("[%s] STOP -> cho thread chay ve safe roi dong", username)
            else:
                log.info("[%s] STOP -> cho leader ve safe roi member thoat theo", username)
            # WATCHDOG: thread co the KET o blocking call (navigate ve safe khong toi, dang reform/
            # danh boss, hoac member cho leader qua lau) -> STOP "khong an". Sau 25s chua thoat thi
            # FORCE dong socket -> unblock recv -> thread chac chan chet (STOP luon co tac dung).
            def _force_close_watchdog(_u=username, _c=c):
                t = account_threads.get(_u)
                for _ in range(25):
                    if t is None or not t.is_alive():
                        return
                    time.sleep(1)
                log.warning("[%s] STOP: thread chua thoat sau 25s -> FORCE dong socket", _u)
                try: _c.close()
                except Exception: pass
            threading.Thread(target=_force_close_watchdog, daemon=True).start()
        else:
            try: c.close()
            except Exception: pass
    return True


def stop_party(pidx, reason="GUI Stop party"):
    for u, p, _, _ in party_accounts(pidx):
        stop_account(u, reason=reason)


def stop_all(reason="GUI Stop tat ca"):
    global _start_cancel_generation
    _start_cancel_generation += 1
    us = list(account_stops.keys())
    log.info("STOP TAT CA: %s: %d acc -> %s", reason, len(us), us)
    for u in us:
        stop_account(u, reason=reason)


def is_account_running(username):
    t = account_threads.get(username)
    return t is not None and t.is_alive()


def furnace_notify_items(pidx):
    """[{user, tab, id, name, bag, slot, kind, new}] - thong bao lo cua CA party pidx.

    Cau noi cho UI (GUI PC dung truc tiep account_furnace_notify; APK goi ham nay qua Chaquopy).
    Tra du lieu THO - ben UI tu dung cau chu (APK da co equip_stats.json de hien chi so trang bi).
    """
    out = []
    try:
        accs = party_accounts(pidx)
    except Exception:
        return out
    for tpl in accs:
        u = tpl[0] if isinstance(tpl, (tuple, list)) else tpl
        for it in list(account_furnace_notify.get(u) or []):
            d = {"user": u}
            for k in ("tab", "id", "name", "bag", "slot", "kind", "new", "quant"):
                if k in it:
                    d[k] = it[k]
            out.append(d)
    return out


# Acc da bam "Bo qua" thong bao KHONG CO QUAN DOAN (an trong phien nay).
legion_notify_dismissed = set()


DIEM_DE_DANH_MAC_DINH = 999
# Diem skill DE DANH mac dinh - giong o Point: khong tick gi thi bot KHONG tieu diem cua user.
SKILL_DE_DANH_MAC_DINH = 999        # acc chua config -> KHONG tieu diem nao


def diem_rules_mac_dinh():
    """Cau hinh tang diem cua acc MOI: dung 1 dong "de danh 999" -> bot khong cong gi ca.

    User chot 31/08: "acc moi se mac dinh chi co dung 1 dong 'point de danh: 999', nguoi dung se
    phai tu config". Diem la thu KHONG LAY LAI DUOC (muon reset phai mua item), nen mac dinh phai
    la KHONG LAM GI.
    """
    return {"reserve": DIEM_DE_DANH_MAC_DINH, "rules": []}


def _diem_doc_cfg(cfg):
    """Chuan hoa cau hinh tang diem -> (so_de_danh, [(ma_chi_so, muc_dich)])."""
    cfg = cfg if isinstance(cfg, dict) else {}
    try:
        reserve = max(0, int(cfg.get("reserve", DIEM_DE_DANH_MAC_DINH)))
    except (TypeError, ValueError):
        reserve = DIEM_DE_DANH_MAC_DINH
    dong = []
    for r in (cfg.get("rules") or []):
        if not isinstance(r, dict):
            continue
        ma = ATTR_KEY_TO_CODE.get(str(r.get("stat") or "").strip().lower())
        try:
            dich = int(r.get("target"))
        except (TypeError, ValueError):
            continue
        if ma and dich > 0:
            dong.append((ma, dich))
    return reserve, dong


def auto_cong_diem(client, cfg, label=""):
    """Tu cong diem tiem nang theo bang rule. -> (so_diem_da_cong, so_diem_du_THUA).

    Luat user chot 31/08:
      - Dong dau CO DINH "Point de danh: N" -> LUON giu lai N diem, chi tieu phan VUOT qua N.
      - Cac dong sau la MUC DICH cua tung chi so, duyet TU TREN XUONG: dong nao chi so GOC chua
        dat thi cong cho du roi moi xuong dong tiep; dat roi thi bo qua.
      - Duyet het bang ma van con du hon so de danh -> BAO cho user (mau "Chu y"), khong tu tieu.

    Rule chot theo DIEM GOC (`char_diem_goc`), KHONG phai tong co trang bi: cong diem lam tang
    diem goc, va tong thi thao/deo do la doi - chot theo tong se lam bot do diem theo bo do.
    """
    con = client.attr_point_left()
    if con is None:
        return 0, 0
    reserve, dong = _diem_doc_cfg(cfg)
    dung_duoc = con - reserve
    if dung_duoc <= 0:
        return 0, 0
    goc = client.char_diem_goc()
    if not goc:
        return 0, 0        # chua co goi login -> chua biet diem goc, dung doan
    da_cong = 0
    for ma, dich in dong:
        if dung_duoc <= 0:
            break
        hien = int(goc.get(ma, 0))
        thieu = dich - hien
        if thieu <= 0:
            continue                       # dat muc roi -> dong tiep theo
        # DONG AGI: DEN LUOT no thi BO QUA so de danh (user chot 11/09).
        #
        # "De danh" sinh ra de giu diem cho cac dong PHIA SAU chua toi luot. Nhung AGI la dong
        # quyet dinh luot danh, va khi da toi luot no thi khong con dong nao phai giu cho nua ->
        # giu tiep la giu mai mai.
        # Vi du user dua ra: de danh 33, hpx 22, int 55, agi 44.
        #   int moi 50  -> chua toi dong agi -> VAN giu 33 (chi tieu phan vuot)
        #   int du 55   -> toi dong agi      -> tang agi len 44, khong quan tam 33 nua
        # Thu tu van nguyen: cac dong TREN phai xong het roi moi den luot agi.
        if ma == ATTR_KEY_TO_CODE.get("agi") and reserve > 0:
            _truoc = dung_duoc
            dung_duoc = max(dung_duoc, con - da_cong)     # tra lai phan dang giu
            if dung_duoc > _truoc:
                log.info("[%s] Tang diem: den dong AGI -> BO QUA %d diem de danh (khong con dong "
                         "nao phia sau phai giu cho), dung duoc %d -> %d",
                         label or getattr(client, "_label", ""), reserve, _truoc, dung_duoc)
        them = min(thieu, dung_duoc)
        if not client.add_attr_point(ma, them):
            break                          # dang trong tran / gui loi -> de vong sau
        goc[ma] = hien + them
        dung_duoc -= them
        da_cong += them
        log.info("[%s] Tang diem: %s %d -> %d (muc %d), con dung duoc %d",
                 label or getattr(client, "_label", ""), ATTR_CODE_TO_TEN.get(ma, ma),
                 hien, hien + them, dich, dung_duoc)
    return da_cong, max(0, dung_duoc)


# Acc con du diem sau khi duyet het bang rule: username -> so diem du. Hien o man "Chu y".
diem_du_notify = {}
diem_du_notify_dismissed = set()


def _tu_cong_diem(client, username, label=""):
    """Chay bang TU CONG DIEM cua acc. Goi luc login (sau khi da ra safe) va dinh ky khi train.

    Con du hon so "de danh" sau khi duyet het bang -> ghi vao `diem_du_notify` de hien o man
    "Chu y" (user chot 31/08: "bao 1 cai thong bao len chu y la 'acc xxx con du yyy diem chua
    dung'"). Cong het roi thi xoa thong bao di.
    """
    try:
        cfg = (getattr(config, "ACCOUNT_POINT", None) or {}).get(username)
        if cfg is None:
            cfg = diem_rules_mac_dinh()      # acc chua config -> chi co "de danh 999" = khong cong
        _da, _du = auto_cong_diem(client, cfg, label=label)
        if _du > 0:
            diem_du_notify[username] = _du
            log.info("[%s] Tang diem: duyet het bang ma con DU %d diem chua dung -> bao o man Chu y",
                     label or username, _du)
        else:
            diem_du_notify.pop(username, None)
        return _da
    except Exception as e:
        log.warning("[%s] tu cong diem loi (bo qua): %s", label or username, e)
        return 0


def diem_du_notify_items(pidx):
    """[{user, kind:'diem_du', diem}] - acc con du diem chua dung (da duyet het bang rule)."""
    out = []
    try:
        accs = party_accounts(pidx)
    except Exception:
        return out
    for tpl in accs:
        u = tpl[0] if isinstance(tpl, (tuple, list)) else tpl
        if u in diem_du_notify_dismissed:
            continue
        n = int(diem_du_notify.get(u) or 0)
        if n > 0:
            out.append({"user": u, "kind": "diem_du", "diem": str(n)})
    return out


def save_cat_do_items_str(items_str):
    r"""ANDROID: luu list cat vao tien trang. Nhan CHUOI noi bang "\n", KHONG phai List<String>.

    Chaquopy khong convert dung List<String> qua callAttr (ban release bi R8 rut gon ten lop ->
    "TypeError: 't' object is not iterable") - moi cho khac trong BotForegroundService cung noi
    chuoi y het.
    """
    ds = {}
    for dong in str(items_str or "").split("\n"):
        dong = dong.strip().lower()
        if not dong:
            continue
        # Dang "tid=cat" / "tid=lay". Dang CU chi co "tid" tron -> hieu la "cat".
        k, _sep, v = dong.partition("=")
        ds[k.strip()] = v.strip() or CAT_DO_CAT
    return bool(save_cat_do_items(ds))


def load_cat_do_items_str():
    r"""ANDROID: doc list cat -> chuoi cac dong "tid=cat" / "tid=lay", noi bang "\n".

    Chaquopy tra dict/list khong on dinh qua callAttr (xem save_cat_do_items_str) nen quy ve
    chuoi y het moi cho khac.
    """
    return "\n".join("%s=%s" % (k, v) for k, v in sorted(load_cat_do_items().items()))


def apply_point_config(username, point_config):
    """GUI/APK luu bang tu cong diem -> ap NGAY cho acc dang chay (khong doi restart)."""
    if isinstance(point_config, str):
        try:
            import json
            point_config = json.loads(point_config) if point_config else {}
        except Exception:
            point_config = {}
    cfg = point_config if isinstance(point_config, dict) else {}
    if not isinstance(getattr(config, "ACCOUNT_POINT", None), dict):
        config.ACCOUNT_POINT = {}
    if cfg:
        config.ACCOUNT_POINT[username] = cfg
    else:
        config.ACCOUNT_POINT.pop(username, None)
    log.info("[%s] da apply bang TU CONG DIEM moi (live)", username)
    return True


def point_info(username):
    """Bang diem cua 1 acc cho UI: goc / tong / diem du.

    KHONG quan tam pet (user chot 31/08). `char_base` = diem GOC (thu ma cong diem tac dong toi),
    `char_stat_full()` = TONG da cong trang bi/thu cuoi/the/suu tap.

    ACC DANG CHAY -> doc live va GHI CACHE. ACC DA TAT -> doc CACHE de van XEM duoc bang diem
    (them khoa `cache: True` + `ts`). CONG diem thi van phai bat acc len - phai gui goi len server.
    """
    c = account_clients.get(username)
    goc = {}
    if c is not None:
        try:
            goc = c.char_diem_goc()
        except Exception as e:
            log.debug("[%s] doc bang diem loi: %s", username, e)
            goc = {}
    if not goc:
        _cache, _ts = load_point_cache(username)
        if _cache:
            return dict(_cache, cache=True, ts=_ts)
        return {}
    try:
        tong = c.char_stat_full() or {}
        out = {
            "left": c.attr_point_left(),
            "stats": [{"key": k, "ten": t, "ma": ma,
                       "goc": int(goc.get(ma, 0)), "tong": int(tong.get(ma, goc.get(ma, 0)))}
                      for ma, k, t in ATTR_KINDS],
        }
    except Exception as e:
        log.debug("[%s] doc bang diem loi: %s", username, e)
        return {}
    try:
        save_point_cache(username, out)
    except Exception as e:
        log.debug("[%s] ghi cache bang diem loi (bo qua): %s", username, e)
    return out


def skill_char_info(username):
    """Bang SKILL NHAN VAT cua 1 acc cho UI: he + diem skill con lai + cap tung skill.

    ACC DANG CHAY -> doc live va GHI CACHE. ACC DA TAT -> doc CACHE de van XEM duoc cay skill
    (them khoa `cache: True` + `ts`). NANG skill thi van phai bat acc len (phai gui goi len server).
    """
    c = account_clients.get(username)
    if c is not None and (getattr(c, "char_skill_lv", None) or c.he_nhan_vat()):
        out = {
            # He lay tu `char_attrs[24]` khi `S:008-013` chua toi - dialog can biet mo tab he nao.
            "element": c.he_nhan_vat(),
            "left": c.skill_point_left(),
            "lv": {"0x%04x" % int(k): int(v) for k, v in (c.char_skill_lv or {}).items()},
            "char_level": getattr(c, "char_level", None),
        }
        try:
            save_skill_char_cache(username, out)
        except Exception as e:
            log.debug("[%s] ghi cache skill nhan vat loi (bo qua): %s", username, e)
        return out
    _cache, _ts = load_skill_char_cache(username)
    if _cache:
        return dict(_cache, cache=True, ts=_ts)
    return {}


def nang_skill_ngay(username, skill_id, cap_dich):
    """Hoc/nang TAY mot skill nhan vat tu dialog.

    -> True = da gui | "queued" = dang trong tran, DA XEP HANG | (False, ly_do) = khong lam duoc.

    DANG TRONG TRAN thi XEP HANG y het cong diem (`add_point`) / lenh tui do: client that chan
    thao tac bang skill khi dang danh, gui bua la server nuot.
    `de_danh=0`: day la lenh TAY cua user, khong dinh gi toi o "de danh" cua bang tu nang.
    """
    c = account_clients.get(username)
    if c is None:
        return False, "acc chưa chạy"
    sid, cap = int(skill_id), int(cap_dich)
    ten = "Nâng skill %s -> cấp %d" % (c._ten_skill(sid), cap)
    try:
        if c.queue_bag_cmd(ten, lambda: c.nang_skill_char([[sid, cap]], 0)):
            return "queued"
    except Exception as e:
        log.debug("[%s] xep hang nang skill loi (gui thang): %s", username, e)
    try:
        da, ly_do = c.nang_skill_char([[sid, cap]], 0)
    except Exception as e:
        return False, str(e)
    return (True if da else (False, ly_do or "không nâng được"))


def apply_skill_config_json(username, cfg_json):
    """ANDROID: nhu apply_skill_config nhung nhan CHUOI JSON.

    Ban PC truyen thang dict; Kotlin chi truyen duoc chuoi (giong apply_point_config, ham do tu
    json.loads o dau). Tach ham rieng de KHONG doi kieu tham so cua apply_skill_config - no la
    code DUNG CHUNG voi PC.
    """
    cfg = cfg_json
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg) if cfg else {}
        except Exception:
            cfg = {}
    return apply_skill_config(username, cfg if isinstance(cfg, dict) else {})


def apply_skill_config(username, cfg):
    """GUI luu bang tu nang skill -> ap NGAY vao config dang chay (khong phai restart acc)."""
    if not username:
        return False
    cu = dict((getattr(config, "ACCOUNT_SKILL", None) or {}).get(username) or {})
    cu.update(cfg or {})
    if not hasattr(config, "ACCOUNT_SKILL"):
        config.ACCOUNT_SKILL = {}
    config.ACCOUNT_SKILL[username] = cu
    return True


def _tu_nang_skill(client, username, label):
    """Viec vat luc login: tu nang skill nhan vat theo bang rule cua acc."""
    cfg = (getattr(config, "ACCOUNT_SKILL", None) or {}).get(username) or {}
    rules = cfg.get("rules") or []
    if not rules:
        return
    de_danh = cfg.get("reserve")
    de_danh = SKILL_DE_DANH_MAC_DINH if de_danh is None else de_danh
    try:
        da, ly_do = client.nang_skill_char(rules, de_danh)
    except Exception as e:
        log.warning("[%s] loi tu nang skill: %s", label, e)
        return
    if not da and ly_do:
        log.info("[%s] Tu nang skill: %s", label, ly_do)


def add_point(username, stat_key, add):
    """Cong TAY `add` diem vao chi so `stat_key` ('int'/'atk'/...).

    -> True = da gui | "queued" = dang trong tran, DA XEP HANG (het tran tu gui) | False = loi.

    DANG TRONG TRAN thi XEP HANG y het lenh tui do (`queue_bag_cmd`): client that cung chan doi
    do/cong diem giua tran (`UI/UIStatus.lua:2009` - `war` phai la None/Guest), gui bua la server
    nuot. User 31/08: "lam nhu cai doi trang bi ay, de khi het tran moi gui len cong di".
    """
    c = account_clients.get(username)
    ma = ATTR_KEY_TO_CODE.get(str(stat_key or "").strip().lower())
    if c is None or not ma:
        return False
    ten = "Cộng %d %s" % (int(add), ATTR_CODE_TO_TEN.get(ma, ma))
    try:
        if c.queue_bag_cmd(ten, lambda: c.add_attr_point(ma, add)):
            return "queued"
    except Exception as e:
        log.debug("[%s] xep hang cong diem loi (gui thang): %s", username, e)
    return bool(c.add_attr_point(ma, add))


def diem_du_notify_skip(username):
    diem_du_notify_dismissed.add(username)
    return True


# Ba Dau SAP HET HAN: username -> chuoi mo ta moc het han. Chi ghi LUC LOGIN (user chot 01/09).
ba_dau_notify = {}
ba_dau_notify_dismissed = set()
BA_DAU_BAO_TRUOC = 86400.0      # con duoi 1 NGAY thi bao


def _kiem_han_ba_dau(client, username, label=""):
    """Luc LOGIN: con >0 va <1 ngay thi ghi thong bao "Ba Dau sap het han" cho man Chu y.

    User chot 01/09: "nho la gan het moi bao, khi time =0 roi thi ko bao nua" -> `han_dung_con_lai`
    da tra None khi da het han / khong co, nen chi can chot can tren.
    Chi kiem MOT LAN luc login, khong theo doi lien tuc.
    """
    try:
        con = client.han_dung_con_lai("ba_dau")
        if con is None or con.total_seconds() >= BA_DAU_BAO_TRUOC:
            ba_dau_notify.pop(username, None)      # khong co / con nhieu -> khong bao
            return
        het = (getattr(client, "han_dung", None) or {}).get("ba_dau")
        ba_dau_notify[username] = het.strftime("%H giờ %M phút ngày %d/%m/%Y")
        log.warning("[%s] Ba Dau SAP HET HAN: con %.1f gio (het luc %s) -> bao o man Chu y",
                    label or username, con.total_seconds() / 3600.0, ba_dau_notify[username])
    except Exception as e:
        log.debug("[%s] kiem han Ba Dau loi (bo qua): %s", label or username, e)


def ba_dau_notify_items(pidx):
    """[{user, kind:'ba_dau', luc}] - acc co Ba Dau sap het han (con duoi 1 ngay)."""
    out = []
    try:
        accs = party_accounts(pidx)
    except Exception:
        return out
    for tpl in accs:
        u = tpl[0] if isinstance(tpl, (tuple, list)) else tpl
        if u in ba_dau_notify_dismissed:
            continue
        luc = ba_dau_notify.get(u)
        if luc:
            out.append({"user": u, "kind": "ba_dau", "luc": luc})
    return out


def ba_dau_notify_skip(username):
    ba_dau_notify_dismissed.add(username)
    return True


def legion_notify_items(pidx):
    """[{user, kind:'legion'}] - acc KHONG o quan doan nao.

    Dung chung PC/APK (GUI PC va Chaquopy deu goi ham nay) de hai ban khong lech luat.

    `org_id` den tu `0x05 sub03` luc login (client `_on_org_id`): 0 = khong co quan doan. CHI bao
    khi DA CHAC CHAN (`_no_legion_confirmed`) - chua nhan goi thi `org_id` con None, bao luc do la
    bao lao ca luot dau cua moi acc.
    """
    out = []
    try:
        accs = party_accounts(pidx)
    except Exception:
        return out
    for tpl in accs:
        u = tpl[0] if isinstance(tpl, (tuple, list)) else tpl
        if u in legion_notify_dismissed:
            continue
        c = account_clients.get(u)
        if c is None or not getattr(c, "running", False):
            continue
        if not getattr(c, "_no_legion_confirmed", False):
            continue
        out.append({"user": u, "kind": "legion"})
    return out


# username da bam "Bo qua" thong bao tui gan day (an trong phien nay)
bag_notify_dismissed = set()
# Slot tui con it hon nguong nay -> canh bao. User chot 01/09 nang tu 5 len 10: tui gan day thi
# nhieu viec HONG AM THAM truoc khi day han - nhan qua mail that bai (xem `claim_mail`), khong
# nhat duoc do roi trong tran, khong mua duoc do o lo.
BAG_CANH_BAO_SLOT_TRONG = 10


def bag_info(username):
    """TUI DO cua 1 acc cho UI (APK). {} = chua co du lieu nao (chua chay VA chua tung cache).

    Acc TAT thi tra ban CACHE kem `"live": False` (user 06/09: "tui do la de xem lai khi
    offline"). Ban cache la CHI XEM: UI PHAI khoa moi nut khi `live` False - bam "phan giai"
    theo so cu la mat nham do. Do dung la ly do truoc day ham nay tu choi cache han; gio cache
    nhung tra kem co `live` de cho goi biet duong khoa nut.

    Moi o kem san cac co CHO PHEP (use/equip/dis/fashion) tinh bang `bot.bag_tabs` - dung luat
    cua client. De Kotlin tu suy tu items_gamedata la se lech, vi luat that nam o bag_tabs
    (vd `can_use` doc btnState NGUOC voi truc giac - xem chu thich trong file do).
    """
    c = account_clients.get(username)
    from . import bag_tabs as _bt
    from .client import _load_gamedata_items, load_bag_cache
    if c is None:
        _tui, _ts = load_bag_cache(username)
        if not _tui:
            return {}
        _slots = {int(s): v for s, v in (_tui.get("slots") or {}).items()}
        return dict(_bag_info_slots(_slots, None), live=False, ts=int(_ts),
                    cap=int(_tui.get("cap") or 0), used=int(_tui.get("used") or len(_slots)),
                    maxed=False)
    return dict(_bag_info_slots({int(s): v for s, v in (getattr(c, "bag_slots", None) or {}).items()}, c),
                live=True, ts=int(time.time()),
                cap=c.bag_capacity(), used=c.bag_used_slots(), maxed=bool(c.bag_slot_maxed()))


def bank_info(username):
    """TIEN TRANG cua 1 acc cho UI. LUON tu cache, ke ca khi acc dang chay.

    Server KHONG BAO GIO tu gui kho: bot chi thay no dung luc di NPC Trac Quan mo kho. Nen day
    la anh chup cua LAN MO KHO GAN NHAT, va acc chua tung mo kho thi coi nhu KHONG CO GI (user
    chot 06/09 - khong lam nut "doc lai kho" vi ton mot chuyen di).

    Kho LUON chi xem: khong co lenh nao cua UI tac dong vao no.
    """
    from .client import load_bank_cache
    c = account_clients.get(username)
    kho, ts = load_bank_cache(username)
    slots = {int(i): v for i, v in ((kho or {}).get("slots") or {}).items()}
    if c is not None and getattr(c, "bank_slots", None):
        slots = {int(i): v for i, v in c.bank_slots.items()}   # dang mo kho -> ban SONG moi hon
        ts = int(time.time())
    if not slots and not ts:
        return {}          # chua tung mo kho -> coi nhu khong co gi (giong bag_info khi chua cache)
    return dict(_bag_info_slots(slots, None), live=False, ts=int(ts or 0),
                used=len(slots), cap=0, maxed=False)


def _bag_info_slots(slots, c):
    """Dung `{"slots": [...]}` cho ca tui do lan tien trang. `c=None` = ban CHI XEM (acc tat /
    kho) -> cac co can client song (`fashion`, `bank`) de False, UI khoa nut theo `live`."""
    from . import bag_tabs as _bt
    from .client import _load_gamedata_items, GameClient
    _BANK_RESTRICT_CAM = GameClient.BANK_RESTRICT_CAM
    gd = _load_gamedata_items()
    o = []
    for slot, val in sorted((slots or {}).items()):
        try:
            tid, cnt = int(val[0]), int(val[1])
        except Exception:
            continue
        if cnt <= 0:
            continue
        d = gd.get(tid) or {}
        o.append({
            "slot": int(slot), "id": tid, "cnt": cnt,
            "name": d.get("name") or ("0x%04x" % tid),
            "q": int(d.get("q", 0) or 0),
            "st": int(d.get("st", 999) or 999),
            "ft": int(d.get("ft", 0) or 0),
            "kd": int(d.get("kd", 0) or 0),
            "tab": [t for t, _ten in _bt.TAB_NAMES
                    if _bt.matches_tab(t, d.get("ft"), d.get("kd"))],
            "use": bool(_bt.can_use(d.get("bs"))),
            "equip": bool(_bt.can_equip(d.get("ft"), d.get("kd"))),
            "dis": bool(_bt.can_dismantle(d.get("fc"))),
            "fashion": bool(c.is_fashion_item(tid)) if c is not None else False,
            # Mon game CAM gui ngan hang -> khong cho them vao list cat (them cung vo ich).
            # Day la co DUY NHAT con dung o ban cache: nut "Tu cat vao Tien trang" ghi thang
            # accounts.json, khong can client song (user chot 06/09).
            "bank": not (int(d.get("restrict", 0) or 0) & _BANK_RESTRICT_CAM),
        })
    return {"slots": o}


# Lenh tui do UI duoc phep goi. Khoa -> (ten hien thi, ham chay).
# Danh sach TRANG (allowlist) co chu y: UI khong duoc goi bua bat ky method nao cua client.
_BAG_LENH = {
    "use": ("Dùng", lambda c, s, a: c.use_slot(s, target=a)),
    "equip": ("Trang bị", lambda c, s, a: c.use_slot(s, target=a)),
    "decompose": ("Phân giải", lambda c, s, a: c.decompose_slot(s)),
    "discard": ("Bỏ", lambda c, s, a: c.discard_item(s, a or 1)),
    "fashion": ("Thả vào sưu tầm", lambda c, s, a: c.deposit_fashion_slot(s)),
}


def bag_cmd(username, action, slot, arg=0):
    """Chay mot lenh tui do tu UI. -> "True" | "queued" | "False: ly do".

    DANG TRONG TRAN thi XEP HANG (`queue_bag_cmd`) y het lenh cong diem / nang skill: client that
    chan thao tac tui do khi dang danh, gui bua la server nuot im lang.
    """
    c = account_clients.get(username)
    if c is None:
        return "False: acc chưa chạy"
    lenh = _BAG_LENH.get(str(action or ""))
    if lenh is None:
        return "False: lệnh không hợp lệ"
    ten, fn = lenh
    s, a = int(slot), int(arg or 0)
    try:
        if c.queue_bag_cmd("%s (ô #%d)" % (ten, s), lambda: fn(c, s, a)):
            return "queued"
        return "True" if fn(c, s, a) else "False: server không nhận"
    except Exception as e:
        return "False: %s" % e


def bag_notify_items(pidx):
    """[{user, kind:'bag', used, cap, free, maxed}] - acc con DUOI 10 slot tui trong.

    Dung chung PC/APK. Truoc day luat nay chi nam trong `gui.py` nen ban APK KHONG he co muc canh
    bao tui - dung cai bay "chep tay o dau la lech o do" trong CLAUDE.md.
    """
    out = []
    try:
        accs = party_accounts(pidx)
    except Exception:
        return out
    for tpl in accs:
        u = tpl[0] if isinstance(tpl, (tuple, list)) else tpl
        if u in bag_notify_dismissed:
            continue
        c = account_clients.get(u)
        if c is None or not getattr(c, "running", False):
            continue
        try:
            if not getattr(c, "bag_slots", None):   # chua co snapshot tui -> chua tinh duoc
                continue
            free = c.bag_free_slots()
            if free >= BAG_CANH_BAO_SLOT_TRONG:
                continue
            out.append({"user": u, "kind": "bag", "used": c.bag_used_slots(),
                        "cap": c.bag_capacity(), "free": free, "maxed": c.bag_slot_maxed()})
        except Exception:
            continue
    return out


def bag_notify_skip(username):
    """Bo qua thong bao tui cua 1 acc (an trong phien nay)."""
    if username:
        bag_notify_dismissed.add(username)
    return True


def legion_notify_skip(username):
    """Bo qua thong bao quan doan cua 1 acc (an trong phien nay)."""
    legion_notify_dismissed.add(username)
    return True


def furnace_notify_count(pidx):
    """So thong bao lo dang cho cua party (de hien badge tren nut 'Chu y')."""
    return len(furnace_notify_items(pidx))


def _furnace_notify_drop(username, tid):
    lst = account_furnace_notify.get(username)
    if not lst:
        return False
    for i, it in enumerate(list(lst)):
        if int(it.get("id", -1)) == int(tid):
            lst.pop(i)
            return True
    return False


def furnace_notify_buy(username, tid):
    """MUA item lo dang cho o acc `username`. Tra True neu server nhan lenh mua."""
    it = None
    for x in list(account_furnace_notify.get(username) or []):
        if int(x.get("id", -1)) == int(tid):
            it = x
            break
    if it is None:
        return False
    c = account_clients.get(username)
    if c is None or not getattr(c, "running", False):
        return False
    try:
        ok = bool(c.buy_furnace_item(it["kind"], it["slot"], it["id"]))
    except Exception as e:
        log.warning("[%s] mua item lo tu UI loi: %s", username, e)
        return False
    if ok:
        _furnace_notify_drop(username, tid)
    return ok


def furnace_notify_skip(username, tid):
    """BO QUA: go khoi danh sach cho, khong mua."""
    return _furnace_notify_drop(username, tid)


def account_status(username):
    """Dict trang thai live cua acc (cho GUI). running, char, map, channel, in_party, dg_remain..."""
    c = account_clients.get(username)
    running = is_account_running(username)
    pidx = getattr(c, "party_idx", None) if c is not None else party_idx_of(username)
    party_avg_level = (_party_average_level(pidx)
                       if config.PARTY_LEADER_ACC.get(pidx) == username else None)
    if c is None:
        # da tat/thoat -> GIU map + nhan vat LUC CUOI (de biet thoat o dau, dung map khong)
        # THREAD CON SONG ma chua co client = DANG LOGIN (supervisor da dong socket cu, chua kip
        # tao client moi). Truoc day tinh la "chay" -> user tuong dang danh trong khi no dang
        # login lai sau khi bi server dut.
        last = account_last.get(username, {})
        return {"running": running, "logging_in": running,
                "state": "logging_in" if running else "stopped",
                "char": last.get("char", ""), "map": last.get("map"),
                "in_party": False, "dg_remain": None, "combat": False, "channel": None,
                "strategist": False, "char_level": last.get("char_level"),
                "char_agi": last.get("char_agi"),
                "pet_name": last.get("pet_name") or "", "pet_level": last.get("pet_level"),
                "pet_agi": last.get("pet_agi"),
                "party_avg_level": party_avg_level}
    from .client import is_joined, is_strategist
    st = _party_state.get(pidx, {})
    dg_remain = None
    if c.current_map == config.DIGIOI_MAP_ID:
        dg_remain = max(0, int(DIGIOI_LIMIT - c.digioi_minutes_live()))
    account_last[username] = {"map": c.current_map, "char": c.char_name or "",
                              "char_level": getattr(c, "char_level", None),
                              "char_agi": getattr(c, "char_agi", None),
                              "pet_name": c.pet_name_out(),
                              "pet_level": getattr(c, "pet_level", None),
                              "pet_agi": getattr(c, "pet_agi", None),
                              "pet_faith": _trung_thanh_pet_dang_dung(c)}  # luu lai luc cuoi
    _ch = getattr(getattr(c, "state", None), "char", None)   # hp/sp cho UI APK (PC GUI bo qua)
    return {
        "running": running,
        "char": c.char_name or "",
        # NHAN LOG that su in ra dau dong: bang ten nhan vat, TRU khi trung ten voi acc khac thi la
        # 'ten~username' (xem `_NHAN_CHU` trong bot/client.py). APK phai mask/loc theo cai nay,
        # khong duoc theo "char" - trung ten la mask nham dong log cua acc khac.
        "log_label": getattr(c, "_label", "") or "",
        "map": c.current_map,
        # Kenh THAT cua chinh acc nay (c.current_channel - bot doc tu 0x03/0x0c), khong phai
        # st["channel"] la kenh party CHON: cai do bi clear moi vong sync nen cot "Kenh" gan nhu
        # luon rong, va giong het nhau moi acc -> nhin khong ra vu lech kenh (log 17:25: leader
        # kenh 2, member kenh 1). Con st["channel"] chi dung khi chua doc duoc kenh that.
        "channel": getattr(c, "current_channel", None) or st.get("channel"),
        # False = so kenh tren KHONG duoc server xac nhan (lenh doi kenh gan nhat hong) - UI hien
        # dau `?` de nguoi nhin biet ngay, thay vi tin mot so ao. Xem `Client.kenh_dang_chac`.
        "channel_chac": (c.kenh_dang_chac() if hasattr(c, "kenh_dang_chac") else True),
        # DOC TRANG THAI THAT tu roster server (`party_members`/`party_leader`, cap nhat theo goi
        # 0x0d), KHONG doc `is_joined` - cai do la SO TU GHI cua bot ("acc nay da bam accept"), va
        # so thi khong tu xoa khi server da da acc ra khoi doi.
        #
        # Ca that 21/09 party 34 (user: "moi dua 1 kenh, nhung vi sao lai bao dang o trong pt"):
        # bang hien kenh 5/10/14/8/10 - moi acc mot kenh - ma cot "Trong PT" van tich xanh 4 dua.
        # Doi kenh la PHAI roi doi truoc (server tra result=3 neu con trong doi), nen khac kenh
        # thi chac chan KHONG con chung doi. Cot do dang noi nguoc lai su that.
        #
        # Cung mot bai hoc voi cot "Kenh" ngay tren, va voi `in_team_dungeon()` (14/09): hoi
        # TRANG THAI THAT, dung hoi cai moc/so do chinh bot ghi ra.
        "in_party": bool(getattr(c, "party_members", None)
                         or getattr(c, "party_leader", None)) if running else False,
        "dg_remain": dg_remain,
        "combat": c.in_combat() if running else False,
        "strategist": is_strategist(pidx, c.self_entity),
        "char_level": getattr(c, "char_level", None),
        "char_agi": getattr(c, "char_agi", None),
        "pet_name": c.pet_name_out() or "",
        "pet_level": getattr(c, "pet_level", None),
        "pet_agi": getattr(c, "pet_agi", None),
        "pet_faith": _trung_thanh_pet_dang_dung(c),
        "party_avg_level": party_avg_level,
        # --- them cho UI APK (poll qua account_status thay callback on_status) ---
        # DANG LOGIN = thread song nhung CHUA vao world. Moc "vao world xong" dung y het luc
        # connect() cho o run_account: self_entity va current_map deu phai co.
        "logging_in": bool(running and (c.self_entity is None or c.current_map is None)),
        "state": ("logging_in" if (running and (c.self_entity is None or c.current_map is None))
                  else ("running" if running else "stopped")),
        "hp": getattr(_ch, "hp", None), "sp": getattr(_ch, "sp", None),
        "hp_max": getattr(_ch, "hp_max", None), "sp_max": getattr(_ch, "sp_max", None),
    }


# Trung thanh pet duoi nguong nay -> canh bao CAM giong khi lech AGI. User chot 05/09.
# CHAT DUOI: 40 chua canh bao, 39 moi canh bao.
TRUNG_THANH_CANH_BAO = 40


def _trung_thanh_pet_dang_dung(c):
    """Trung thanh (0..100) cua pet DANG XUAT CHIEN, None neu chua biet.

    `client.pet_faith` khoa theo pet_id (doc tu goi 0x0f, offset +27) - phai tra dung con
    ACTIVE, khong duoc lay bua con dau danh sach. Chua xac nhan pet nao dang ra tran
    (`pet_name_out()` tra None) thi coi nhu chua biet, de khong canh bao oan.
    """
    try:
        if not c.pet_name_out():
            return None
        pid = getattr(getattr(c, "state", None), "active_pet_id", None)
        if not pid:
            return None
        v = (getattr(c, "pet_faith", None) or {}).get(int(pid))
        return int(v) if isinstance(v, int) else None
    except Exception:
        return None


def party_agi_report(pidx):
    """Chi tiet AGI char + pet active cua mot party; canh bao khi do lech > 10."""
    rows = []
    values = []
    for username, _password, _leader, _picker in party_accounts(pidx):
        status = account_status(username)
        char_agi = status.get("char_agi")
        pet_agi = status.get("pet_agi") if status.get("pet_name") else None
        if isinstance(char_agi, int):
            values.append(char_agi)
        if isinstance(pet_agi, int):
            values.append(pet_agi)
        faith = status.get("pet_faith") if status.get("pet_name") else None
        rows.append({
            "username": username,
            "char": status.get("char") or username,
            "char_agi": char_agi,
            "pet": status.get("pet_name") or "",
            "pet_agi": pet_agi,
            "pet_faith": faith,
        })
    low = min(values) if values else None
    high = max(values) if values else None
    spread = high - low if low is not None else None
    # TACH HAI loai canh bao, khong gop lam mot: nut hien "⚠ Check AGI (9)" - so 9 do la DO LECH
    # AGI. AGI on ma chi trung thanh thap thi hien so do la NOI DOI.
    faith_thap = [r["username"] for r in rows
                  if isinstance(r["pet_faith"], int) and r["pet_faith"] < TRUNG_THANH_CANH_BAO]
    lech_agi = spread is not None and spread > 10
    return {"rows": rows, "min": low, "max": high, "spread": spread,
            "warning": lech_agi,          # GIU nguyen nghia cu (chi lech AGI)
            "faith_thap": faith_thap,     # username co pet trung thanh < 40
            "canh_bao": lech_agi or bool(faith_thap)}   # -> to CAM cai nut


# ---- CACHE skill/pet theo account (de dialog Kich ban Skill dung duoc khi acc DA TAT) ----
# Chi phuc vu HIEN THI. Bot chay van doc du lieu THAT tu server (0x0f/0x13) - cache khong bao
# gio anh huong hanh vi. File nam canh accounts.json (PC) / files dir cua app (Android).
# ---- BO DO (outfit) theo ACCOUNT: luu file rieng canh accounts.json ----
# KHONG nhet vao accounts.json: bo do la du lieu do TUI DO quan ly (BagDialog chi co username +
# client, khong voi toi duoc hang cau hinh acc ben dialog party). Tach file thi ca GUI lan runner
# deu doc duoc, va sua bo do khong dung vao file chua mat khau.
def _outfits_path():
    try:
        from ._appdir import app_dir as _ad
        return os.path.join(_ad(), "outfits.json")
    except Exception:
        return "outfits.json"


def _migrate_outfits(row):
    """Bo do CU (chung ca char + pet) -> tach ra MOI DOI TUONG mot danh sach rieng.

    User chot 26/08: "moi con co save bo rieng". Ban cu luu {ten: {char:.., pets:{slot:..}}};
    ban moi luu {doi_tuong: {ten: {fit: tid}}} voi doi_tuong = "char" | "pet<slot>".
    Chuyen ngay khi doc de khong ai mat bo da luu.
    """
    if not row or all(k in ("char",) or str(k).startswith("pet") for k in row):
        return row or {}
    moi = {}
    for ten, bo in row.items():
        if not isinstance(bo, dict):
            continue
        if bo.get("char"):
            moi.setdefault("char", {})[str(ten)] = dict(bo["char"])
        for p, m in (bo.get("pets") or {}).items():
            if m:
                moi.setdefault("pet%s" % p, {})[str(ten)] = dict(m)
    return moi


def load_outfits(username=None, doi_tuong=None):
    """Bo do da luu.

    - khong username: {username: {doi_tuong: {ten: {fit: tid}}}}
    - co username: {doi_tuong: {ten: ...}}; them doi_tuong -> {ten: {fit: tid}}
    `doi_tuong` = "char" hoac "pet<slot>" (moi con mot danh sach rieng).
    """
    try:
        with open(_outfits_path(), encoding="utf-8") as fh:
            data = json.load(fh) or {}
    except Exception:
        data = {}
    out = {k: _migrate_outfits(v) for k, v in (data.get("accounts") or {}).items()}
    if username is None:
        return out
    row = out.get(str(username)) or {}
    if doi_tuong is None:
        return row
    return row.get(str(doi_tuong)) or {}


def save_outfit(username, doi_tuong, ten, bo):
    """Luu/ghi de mot bo do CUA MOT DOI TUONG. bo = None -> XOA bo do."""
    try:
        with open(_outfits_path(), encoding="utf-8") as fh:
            data = json.load(fh) or {}
    except Exception:
        data = {}
    accs = data.setdefault("accounts", {})
    accs[str(username)] = _migrate_outfits(accs.get(str(username)) or {})
    row = accs[str(username)]
    ds = row.setdefault(str(doi_tuong), {})
    if bo is None:
        ds.pop(str(ten), None)
    else:
        # Khoa JSON phai la CHUOI. fitType dang int -> json.dump tu doi thanh chuoi, nhung doc lai
        # se ra chuoi -> so sanh int(fit) o apply_outfit se lech neu khong ep. Ep ngay day.
        ds[str(ten)] = {str(k): int(v) for k, v in (bo or {}).items()}
    if not ds:
        row.pop(str(doi_tuong), None)
    if not row:
        accs.pop(str(username), None)
    tmp = _outfits_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _outfits_path())
    return True


def _skill_cache_path():
    try:
        from ._appdir import app_dir as _ad
        return os.path.join(_ad(), "account_skills_cache.json")
    except Exception:
        return "account_skills_cache.json"


def _load_skill_cache():
    try:
        with open(_skill_cache_path(), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


# Ghi cache nam trong bot/client.py (cho chac chan chay: _on_pet_list luc login + moi lan doi
# pet). O day chi DOC lai + dung chung ham dung snapshot de khong co 2 ban code.
from .client import save_skill_cache as save_account_skills_cache   # noqa: E402
from .client import skills_snapshot as _skills_snapshot             # noqa: E402


def account_inn_pets(username):
    """GUI/API: list pet trong NHA TRO cua acc, de render dialog chon pet van tieu.

    Tra {"pets": [[pet_id, ten], ...], "cached": 0/1}. Acc DANG CHAY -> lay LIVE tu roster server
    gui luc login; acc DA TAT -> lay CACHE lan chay gan nhat (user van tick duoc khi offline).
    Acc chua chay bao gio / khong co pet trong nha tro -> pets rong (caller hien thong bao).
    Thu tu = thu tu index nha tro; nhung KHOA la pet_id vi index xe dich khi them/bot pet."""
    username = str(username or "").strip()
    c = account_clients.get(username)
    roster = getattr(c, "vantieu_roster", None) if c is not None else None
    if roster:
        ids = getattr(c, "vantieu_roster_ids", {}) or {}
        return {"pets": [[int(ids.get(i, 0)), roster[i]] for i in sorted(roster)], "cached": 0}
    cached = _load_skill_cache().get(username)
    if isinstance(cached, dict) and cached.get("inn"):
        return {"pets": [[int(p), n] for p, n in cached["inn"]], "cached": 1}
    return {"pets": [], "cached": 1}


def account_skills(username):
    """GUI/API: skill + pet cua acc de render dialog Kich ban Skill.

    Acc DANG CHAY -> du lieu LIVE. Acc DA TAT -> lay CACHE cua lan chay gan nhat (kem "ts") de
    user van sua duoc config, khoi phai bat acc len chi de mo dialog. Cache CHI de hien thi.
    "pets": [[pid, ten, [choice...]], ...] cho tab per-pet; "active" = pet dang dung (dung de
    migrate config "pet" chung cu -> gan cho pet dang dung, pet khac auto).
    """
    c = account_clients.get(username)
    st = c.state if (c is not None and getattr(c, "state", None)) else None
    if st is not None:
        data = _skills_snapshot(st)
        save_account_skills_cache(username, data)   # tuoi -> cap nhat cache luon
        return data
    cached = _load_skill_cache().get(str(username or "").strip())
    if isinstance(cached, dict):
        return dict(cached, cached=1)
    return {"char": [], "pet": [], "pets": [], "active": 0}


def apply_account_battle(username, battle_config=None):
    """GUI/API: apply battle rule rieng acc NGAY cho acc dang chay, khong can relog.

    battle_config={} / None = ve mac dinh. Ham nay chi cap nhat runtime; GUI/Android van tu luu
    accounts.json/parties.json rieng nhu cu.
    """
    username = str(username or "").strip()
    if not username:
        return False
    if isinstance(battle_config, str):
        try:
            import json
            battle_config = json.loads(battle_config) if battle_config else {}
        except Exception:
            battle_config = {}
    cfg = battle_config if isinstance(battle_config, dict) else {}
    if not isinstance(getattr(config, "ACCOUNT_BATTLE", None), dict):
        config.ACCOUNT_BATTLE = {}
    if cfg:
        config.ACCOUNT_BATTLE[username] = cfg
    else:
        config.ACCOUNT_BATTLE.pop(username, None)
    config.ACCOUNT_CHAR_DEFEND.pop(username, None)
    c = account_clients.get(username)
    if c is not None and getattr(c, "state", None) is not None:
        c.state.battle_config = dict(cfg)
        c.state.char_defend = False
        log.info("[%s] da apply cau hinh skill/chien dau moi (live)", username)
        return True
    return False


def dangerous_npc_names():
    """GUI/API: danh sach NPC nguy hiem dung cho target battle `dangerous_npc`."""
    return list(getattr(config, "DANGEROUS_NPC_NAMES", []) or [])


def save_dangerous_npc_names(names):
    """GUI/API: luu danh sach NPC nguy hiem vao dangerous_npcs.json."""
    if isinstance(names, str):
        try:
            import json
            data = json.loads(names)
            if isinstance(data, dict):
                names = data.get("names", [])
            else:
                names = data
        except Exception:
            names = names.splitlines()
    try:
        saved = config.save_dangerous_npc_names(names)
        log.info("Da luu %d NPC nguy hiem vao dangerous_npcs.json", len(saved))
        return True
    except Exception as e:
        log.warning("Luu dangerous_npcs.json loi: %s", e)
        return False


def apply_account_heal(username, heal_config=None):
    """GUI/API: apply nguong hoi HP/SP rieng acc NGAY cho acc dang chay."""
    username = str(username or "").strip()
    if not username:
        return False
    if isinstance(heal_config, str):
        try:
            import json
            heal_config = json.loads(heal_config) if heal_config else {}
        except Exception:
            heal_config = {}
    cfg = {}
    if isinstance(heal_config, dict):
        for key in ("hp_char", "sp_char", "hp_pet", "sp_pet"):
            if key not in heal_config:
                continue
            try:
                cfg[key] = max(0.0, min(1.0, float(heal_config[key])))
            except Exception:
                pass
    if not isinstance(getattr(config, "ACCOUNT_HEAL", None), dict):
        config.ACCOUNT_HEAL = {}
    if cfg:
        config.ACCOUNT_HEAL[username] = cfg
    else:
        config.ACCOUNT_HEAL.pop(username, None)
    # VAN TIEU di chung heal_json vi cung mot dialog (bang setting Hoi HP/SP cua acc) VA vi duong
    # heal_json da duoc noi san o CA PC lan APK -> khong phai them tham so vi tri moi cho
    # setup_party_runtime (Kotlin goi theo VI TRI, them tham so giua chung la vo).
    vt = (heal_config or {}).get("vantieu") if isinstance(heal_config, dict) else None
    if not isinstance(getattr(config, "ACCOUNT_VANTIEU", None), dict):
        config.ACCOUNT_VANTIEU = {}
    if isinstance(vt, dict):
        pets = []
        for x in (vt.get("pets") or []):
            try:
                pets.append(int(x))
            except Exception:
                pass
        config.ACCOUNT_VANTIEU[username] = {"on": bool(vt.get("on", True)), "pets": pets}
    else:
        config.ACCOUNT_VANTIEU.pop(username, None)
    c = account_clients.get(username)
    if c is not None:
        _vt = config.ACCOUNT_VANTIEU.get(username) or {}
        c.vantieu_enable = bool(_vt.get("on", getattr(config, "VANTIEU_ENABLE", True)))
        c.vantieu_pick_ids = tuple(_vt.get("pets") or ())
    if username in account_clients:
        log.info("[%s] da apply nguong hoi HP/SP moi (live): %s | van tieu: %s",
                 username, cfg or "mac dinh", config.ACCOUNT_VANTIEU.get(username) or "mac dinh")
    return True


def apply_account_furnace(username, furnace_config=None):
    """GUI/API: apply config SOI LO rieng acc. furnace_config = {tab: {"on": bool, "items":
    {tid_hex/int: "auto"/"notify"}}} voi tab in vo_tuong/trang_bi/chuyen_sinh."""
    username = str(username or "").strip()
    if not username:
        return False
    if isinstance(furnace_config, str):
        try:
            import json
            furnace_config = json.loads(furnace_config) if furnace_config else {}
        except Exception:
            furnace_config = {}
    cfg = {}
    if isinstance(furnace_config, dict):
        for tab in ("vo_tuong", "trang_bi", "chuyen_sinh"):
            t = furnace_config.get(tab)
            if not isinstance(t, dict):
                continue
            items = {}
            for k, v in (t.get("items") or {}).items():
                if v not in ("auto", "notify"):
                    continue
                try:
                    tid = int(k, 16) if isinstance(k, str) and k.lower().startswith("0x") else int(k)
                    items[tid] = v
                except Exception:
                    pass
            if items:
                cfg[tab] = {"on": bool(t.get("on", True)), "items": items}
    if not isinstance(getattr(config, "ACCOUNT_FURNACE", None), dict):
        config.ACCOUNT_FURNACE = {}
    if cfg:
        config.ACCOUNT_FURNACE[username] = cfg
    else:
        config.ACCOUNT_FURNACE.pop(username, None)
    return True


def get_account_log(username, max_lines=500):
    """ANDROID: doc party.log -> loc rieng cac dong cua 1 acc, cho UI hien "log cua acc nay".
    QUAN TRONG: nhan log trong client.py (self._label) DOI TU username SANG TEN NHAN VAT ngay
    khi server tra ve (vd 'taot11' -> 'ttmot') - loc CHI theo username se BO SOT toan bo log
    sau thoi diem do (bug that: user thay log "dung lai" ngay sau dong "Ten nhan vat = ...").
    Loc theo CA username LAN char_name hien tai (qua account_status) de khong bo sot."""
    try:
        _st = account_status(username) or {}
        # NHAN LOG that su, KHONG phai char_name: hai acc khac server co the trung ten nhan vat,
        # luc do nhan la 'ten~username' con loc theo '[ten]' se HUT ca log cua acc kia (user 01/09:
        # "party 48 dung o quang truong ma cu bao battle"). Trung ten thi CHI loc theo nhan day du.
        nhan = _st.get("log_label") or _st.get("char") or ""
        tags = ["[%s]" % username]
        if nhan and nhan != username:
            tags.append("[%s]" % nhan)
        if not os.path.exists(_log_path):
            return "(chua co log - acc chua chay lan nao tren may nay)"
        # TAIL-READ: chi doc ~2MB CUOI file (khong quet ca file) -> mo log NHANH bat ke file to.
        # 2MB thua chua 500 dong cua 1 acc. Doc binary + seek de khoi nap ca file vao RAM.
        _tail = 2 * 1024 * 1024
        with open(_log_path, "rb") as f:
            f.seek(0, 2)
            _size = f.tell()
            _start = max(0, _size - _tail)
            f.seek(_start)
            _data = f.read()
        _text = _data.decode("utf-8", errors="replace")
        if _start > 0 and "\n" in _text:
            _text = _text.split("\n", 1)[1]   # bo dong dau bi cat giua chung
        lines = [ln for ln in _text.splitlines() if any(t in ln for t in tags)]
        if not lines:
            return "(chua co dong log nao cho '%s')" % username
        return "\n".join(lines[-max_lines:])
    except Exception as e:
        return "Loi doc log: %s" % e


def _run_cli():
    """Chay CLI nhu cu: khoi dong tat ca party roi cho den khi het acc / het gio."""
    import datetime as _dt
    n = start_all()
    log.info(">>> Party train dang chay (%d acc). %s",
             n, "vo han" if MINUTES == 0 else f"{MINUTES} phut")
    deadline = None if MINUTES == 0 else time.time() + MINUTES * 60
    try:
        # MIEN TRU vong cho diec: vong main: dem thread con song, khong cho acc nao ca.
        while True:
            time.sleep(5)
            if sum(1 for t in _threads if t.is_alive()) == 0:
                log.warning("=" * 60)
                log.warning(">>> TAT CA ACC DA THOAT GAME (%s). Khong con acc nao chay.",
                            _dt.datetime.now().strftime("%H:%M:%S"))
                log.warning(">>> Ly do thuong gap: sai map train / het gio DG / rot ket noi.")
                log.warning("=" * 60)
                break
            if deadline and time.time() >= deadline:
                log.info(">>> Het %d phut -> dong tat ca.", MINUTES)
                break
    except KeyboardInterrupt:
        log.info(">>> Nguoi dung dung (Ctrl+C).")
    stop_all(reason="CLI ket thuc / Ctrl+C")
    log.info(">>> Ket thuc.")


if __name__ == "__main__":
    _run_cli()
