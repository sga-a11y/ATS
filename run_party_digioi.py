"""PARTY TRAIN DI GIOI - flow tu dong day du.

Flow moi party (slot 0 = chu party / leader, slot 1-4 = member):
  1. Login het cac acc trong party + ket noi game.
  2. Moi acc VAO DI GIOI (solo - KHONG vao duoc khi dang trong party).
  3. Leader chon KENH IT NGUOI nhat -> chia se -> ca party chuyen sang kenh do.
  4. Leader MOI 4 member (quet index nguoi gan; member tu accept qua entity cung party).
  5. Leader CHAY LONG VONG (run-around) den het gio; member tu follow + tu danh.

Chay:  python run_party_digioi.py [so_phut]   (mac dinh chay vo han)
"""
import os, sys, time, logging, threading, random
try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
from bot import config
from bot import mob_spots
from bot.mob_scanner import MobScanSession, compute_regions, scan_full_map
from bot.scene_fight import get_scene_fight_seed
from bot.train_maps_store import save_learned_regions
from bot.login import login
from bot.client import (GameClient, check_duplicate_accounts, joined_member_count, is_joined,
                        is_strategist, reset_party_joined, unmark_joined)

_lvl = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
try:
    # Android: "party.log" (duong dan tuong doi) ghi vao "/" - READ-ONLY tren Android (BUG THAT:
    # OSError Errno 30). Phai ghi vao thu muc rieng cua app (Context.getFilesDir(), xem _appdir.py
    # ben APK). Tren PC import nay FAIL (bot/ khong co _appdir) -> fallback "party.log" nhu cu.
    from bot._appdir import app_dir as _app_dir
    _log_path = os.path.join(_app_dir(), "party.log")
except Exception:
    _log_path = "party.log"
logging.basicConfig(level=_lvl, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[logging.FileHandler(_log_path, "w", "utf-8"), logging.StreamHandler()])
log = logging.getLogger("partydg")

check_duplicate_accounts(config.PARTIES)   # bao loi neu 1 user dien trung nhieu noi

MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 0   # 0 = vo han

# Trang thai chia se theo tung party: kenh leader chon + co hieu cac buoc
_party_state = {}   # party_idx -> {"channel": ch, "channel_ready": Event, "invited": Event}
_clients = []
_threads = []   # thread tung acc - de biet khi nao TAT CA da thoat
DIGIOI_LIMIT = 120   # so phut Di Gioi/ngay (de tinh "con lai")


def _jitter(pt):
    """Xê dịch tọa độ ±10 ngẫu nhiên (9 khả năng) để bot không đứng cùng 1 điểm."""
    dx, dy = random.choice([-10, 0, 10]), random.choice([-10, 0, 10])
    return (pt[0] + dx, pt[1] + dy)


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


def _travel_to_train_map(client, map_id, safe, legacy_route, abort=None):
    """Prefer generated navigation; retain handwritten routes as validation fallback."""
    if client.follow_smart_route(map_id, safe, abort=abort):
        return True
    if getattr(config, "SMART_ROUTE_FALLBACK", True) and legacy_route:
        return client.follow_route(legacy_route)
    log.error("[%s] khong co smart route toi map %s", client._label, map_id)
    return False


def _train_route_available(smart_route, legacy_route, has_leader):
    return bool(
        smart_route
        or legacy_route
        or (has_leader and getattr(config, "SMART_WORLD_ROUTING", True))
    )


def _needs_train_mob_probe(client, map_id, train_map):
    return not bool(train_map.get("mobs"))


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
        from bot import scan_image
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


def _wait_for_rally(event, stopped, running):
    """Wait without a scan-duration timeout, but remain stop/disconnect aware."""
    while not event.wait(2.0):
        if stopped() or not running():
            return False
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
account_stop_reasons = {}  # username -> ai/nhanh nao set stop_ev gan nhat
account_reconnect = {}    # username -> True neu lan thoat vua roi la SERVER ROT (supervisor login lai)
account_forced_reconnect = set()  # survivor 40NPC bi dong de relogin cung party; KHONG tang disc_gen
account_forced_reconnect_reason = {}
_start_cancel_generation = 0  # STOP ALL tang so nay de huy chuoi START dang do
LOGIN_ERR1_RETRY_MIN_SEC = 60
LOGIN_ERR1_RETRY_MAX_SEC = 120


def _running_party_usernames(pidx):
    return [u for u, _p, _l, _pk in party_accounts(pidx)
            if is_account_running(u) and account_clients.get(u) is not None]


def _set_party_quest_mode(pidx, on, label=""):
    """Bat/tat quest_mode cho CA party (leader + member).

    Event danh theo party (40NPC, 2K) phai EP quest_mode thay vi de auto-latch quyet dinh:
    latch chi bat khi quai > 6 luc vao tran (state.py) -> tran it quai la mat skill toan man.
    Member KHONG chay vong dieu khien nao ca (bi keo vao tran cua leader) nen phai set ho.
    """
    n = 0
    for u in _active_party_usernames(pidx):
        cli = account_clients.get(u)
        if cli is not None and cli.running:
            cli.state.quest_mode = bool(on)
            n += 1
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


def _party_map_barrier(st, username, self_ok, expected, stopped):
    """BARRIER cap party: moi acc bao 'minh co o train map khong', cho ca party quyet dinh.
    Tra True neu MOI acc bao cao deu o train map; False neu CO >=1 acc sai map
    (-> ca party ve thanh don nhau). CHO VO HAN cho du bao cao (member reconnecting -> cong
    vao coi nhu se catch up); thoat som khi da co dua sai map, hoac Stop."""
    with st["lock"]:
        st["map_results"][username] = bool(self_ok)
    while True:
        if stopped():
            break
        with st["lock"]:
            done = len(st["map_results"]) + len(st["reconnecting"]) >= expected
            any_bad = not all(st["map_results"].values())
        if done or any_bad:
            break
        time.sleep(1)
    with st["lock"]:
        return all(st["map_results"].values())


def _record_channel_map_report(st, username, current_map, sync_gen, expected_map, label=None):
    """Ghi map vao dung generation sync, ke ca member da thoat startup sync va dang retry."""
    map_ok = expected_map is None or current_map == expected_map
    with st["lock"]:
        if st.get("channel_sync_gen") != sync_gen:
            return False
        st["channel_map_reports"][username] = (bool(map_ok), current_map)
        if not map_ok:
            who = label or username
            st["channel_failed_reason"] = "%s map=%s, can=%s" % (
                who, current_map, expected_map,
            )
            st["channel_failed"].set()
    return map_ok


def _prepare_reform_channel_sync(st):
    """Khong cho member dung channel_ready cua generation truoc khi leader mo sync reform moi."""
    with st["lock"]:
        st["channel_ready"].clear()
        st["channel"] = None


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


def _should_restart_event_party(event_party_mode, battle_active, disc_gen, handled_gen):
    return bool(event_party_mode and battle_active and disc_gen > handled_gen)


def _should_restart_mode_after_disconnect(train_on_map, reconnecting):
    """Train must regroup even when the disconnected account relogs between keepalive ticks."""
    return bool(train_on_map or reconnecting)


def _should_reform_incomplete_party(train_on_map, joined, needed, elapsed, threshold=20.0):
    return bool(train_on_map and needed > 0 and joined < needed and elapsed >= threshold)


def _should_resync_incomplete_digioi_party(
        is_digioi, digioi_solo, joined, needed, elapsed, threshold=20.0):
    return bool(is_digioi and not digioi_solo and needed > 0
                and joined < needed and elapsed >= threshold)


def _invite_party_participants(c, train_on_map, gap=1.0):
    if train_on_map:
        return c.invite_train_party_participants(gap=gap)
    return c.invite_members(gap=gap)


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


def _party_average_level(pidx):
    if pidx is None:
        return None
    rows = []
    for username, *_ in party_accounts(pidx):
        c = account_clients.get(username)
        if c is not None:
            rows.append({
                "char_level": getattr(c, "char_level", None),
                "pet_name": getattr(c, "pet_name", None),
                "pet_level": getattr(c, "pet_level", None),
            })
        else:
            rows.append(account_last.get(username, {}))
    return _average_party_levels(rows)


def _pstate(pidx):
    if pidx not in _party_state:
        _party_state[pidx] = {"channel": None,
                              "channel_ready": threading.Event(),
                              "channel_failed": threading.Event(),
                              "channel_failed_reason": "",
                              "channel_expected_map": None,
                              "channel_sync_gen": 0,
                              "channel_map_reports": {},
                              "invited": threading.Event(),
                              "lock": threading.Lock(),
                              "ready_members": set(),   # member da vao DG + dung kenh leader
                              "n_members": 0,            # tong so member can cho
                              "started_train": 0,        # so acc da qua check map -> vao train (de barrier dungeon)
                              "dungeon_done": 0,         # so acc da danh xong dungeon (barrier)
                              "dailies_done": 0,         # so acc da xong daily login (barrier cho leader)
                              "o5_done_by": {},          # username -> o5 (pho ban to doi) da xong? Leader chi chay khi CA party chua xong
                              "o5_state": "idle",        # "idle"|"running"|"done" - member PHAI cho != "idle" (xem _handle_o5_team)
                              "o5_broke": False,         # team dungeon VO do co dis giua chung -> CA party relogin thoat instance
                              "o5_need_redo": False,     # team dungeon VO -> reconnect xong lam LAI daily (team dungeon)
                              "team_dungeon_done_by": {},     # level -> {username -> remaining}; auto team dungeon theo 0x18 mission step
                              "team_dungeon_state": {},       # level -> "idle"|"running"|"done"
                              "team_dungeon_broke": {},       # level -> co dis/fail can relogin thoat instance
                              "team_dungeon_need_redo": False,
                              "team_dungeon_recover_seen": set(),
                              "team_dungeon_recover_ready": threading.Event(),
                              "leader_ok": threading.Event(),   # leader DUNG map train -> tiep tuc
                              "leader_bad": threading.Event(),  # leader SAI map -> huy ca party
                              "leader_gone": threading.Event(),  # leader da THOAT -> member ngung retry vao party
                              "stop_leader_done": threading.Event(),  # STOP: leader DA ve safe -> member duoc thoat
                              "route_party_ready": threading.Event(),  # ROUTE: party da lap xong o thanh -> sap keo di
                              "route_done": threading.Event(),         # ROUTE: leader da keo xong (toi train map)
                              "route_plan_ready": threading.Event(),   # ROUTE: leader da build smart/legacy plan cho ca party
                              "route_plan": None,                      # {"gen", "city", "flag", "route"|None, "missing"?}
                              "map_results": {},     # ROUTE barrier: username -> dang o train map? (de quyet dinh ca party)
                              "member_maps": {},     # username -> current_map (member report lien tuc; leader check ai bi bo lai khi keo)
                              "mob_spot": None,      # diem quai leader chon (de _start_training dung lai)
                              "rally_point": None,   # safe GAN diem quai nhat -> CA PARTY ve day (gan leader)
                              "rally_ready": threading.Event(),  # leader da chon diem quai + rally_point
                              "path_done": threading.Event(),    # leader da di xong follow_path toi diem quai (member bi keo theo)
                              "reform_gen": 0,       # +1 moi khi co acc van map (chet) -> CA party reform tai cho
                              "resync_gen": 0,       # +1 khi leader moi 1p khong du party -> CA party giai tan + sync kenh lai + moi lai (event 40NPC)
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
                              "dt_phase": "digioi",
                              "dt_done": set(),
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


def _dt_wait_all_digioi_done(pidx, username, label, stopped_fn):
    """MODE digioi_train: acc nay DA XONG DG -> danh dau + DUNG YEN cho CA PARTY xong DG.
    Du het -> doi pha party sang "train" (moi acc relogin se chay mode train). Tra True neu
    da san sang di train, False neu bi Stop.
    CHO KHONG GIOI HAN (theo yeu cau user): chi thoat khi CA PARTY xong DG hoac bam Stop -> acc xong
    SOM khong bi tat game oan trong luc acc khac con dang DG (DG toi 2h). Acc da tat/rot han khong
    tinh vao (users = acc DANG CHAY) nen 1 acc chet cung khong ket ca party mai mai."""
    st = _pstate(pidx)
    with st["lock"]:
        st["dt_done"].add(username)

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
                st["channel_map_reports"] = {}
                st["mob_spot"] = None
                st["rally_point"] = None
                st["mob_path"] = None
                st["route_plan"] = None
                st["map_results"] = {}
                st["o5_done_by"].clear()
                st["o5_state"] = "idle"
                st["o5_broke"] = False
                st["o5_need_redo"] = False
                st["team_dungeon_done_by"] = {}
                st["team_dungeon_state"] = {}
                st["team_dungeon_broke"] = {}
                st["team_dungeon_need_redo"] = False
                st["team_dungeon_recover_seen"].clear()
                st["team_dungeon_recover_ready"].clear()
                st["ready_members"].clear()
                st["started_train"] = 0
                st["dungeon_done"] = 0
                st["dailies_done"] = 0
                prepared = True
        if prepared:
            reset_party_joined(pidx)
        return prepared

    last_log = 0.0
    while True:
        if stopped_fn():
            return False
        users = set(_dt_party_usernames(pidx))
        switch_to_train = False
        n_users = 0
        with st["lock"]:
            done = set(st["dt_done"])
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
            log.info("[%s] DG+Train: xong DG, DUNG YEN cho party (%d/%d acc xong) - cho khong gioi han",
                     label, len(done & users), len(users))
        time.sleep(5)


def run_account(username, password, pidx, is_leader, is_picker=False, is_reconnect=False):
    # is_reconnect=True (supervisor goi lai sau khi rot): RECONNECT NHE - bo qua daily/gacha/mail/
    # vantieu (da lam phien truoc) -> vao world la di THANG toi sync kenh + gom party + keo ra bai,
    # KHONG teleport ve Trac Quan lam daily (truoc day: reconnect chay full startup -> lech nhip leader
    # -> ve thanh khong duoc keo -> "SAI MAP -> THOAT" chet luon).
    label = username
    role = "LEADER" if is_leader else "member"
    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    st = _pstate(pidx)
    stop_ev = account_stops.get(username)   # GUI yeu cau STOP -> thoat moi giai doan
    def _stopped():
        return stop_ev is not None and stop_ev.is_set()
    def _leader_thread_active():
        leader_acc = config.PARTY_LEADER_ACC.get(pidx)
        if not leader_acc:
            return False
        t = account_threads.get(leader_acc)
        ev = account_stops.get(leader_acc)
        return t is not None and t.is_alive() and not (ev is not None and ev.is_set())
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
        while attempt < 6:
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
                c.connect()
                # cho self_entity + map (map=None = chua vao world xong)
                for _ in range(15):
                    if c.self_entity is not None and c.current_map is not None:
                        ok = True; break
                    time.sleep(1)
                if ok:
                    break
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
        label = c.char_name or username   # log theo TEN NHAN VAT (neu da resolve), fallback username
        if is_leader and c.char_name:
            # Tu dong them ten nhan vat leader vao whitelist "leaders" cua party - user da cau hinh
            # account nay la leader trong Party roi thi khong can go tay lai ten o whitelist rieng.
            config.record_leader_name(pidx, c.char_name)
        login_map = c.current_map         # map LUC LOGIN (doc som, it bi pollution) - dung de check train
        log.info("[%s] (%s) vao world.", label, role)
        log.info("[%s] >>> MAP HIEN TAI = %s <<<  (dung ID nay de setup START_CITY_ID/TRAIN)",
                 label, login_map)
        # Doc party config SOM de biet mode/map ngay sau login. Neu dang login o map train thi
        # chay ve safe TRUOC cac viec login chores (qua, van tieu, shop...) de khoi dung giua bai
        # quai lau roi bi keo tran.
        pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
        _early_sc = pcfg.get("start_city_id", getattr(config, "START_CITY_ID", 0))
        _early_raw_mode = pcfg.get("mode")
        _early_dt_mode = (_early_raw_mode == "digioi_train")
        _early_tm = config.TRAIN_MAPS.get(_early_sc)
        if _early_dt_mode:
            _early_mode = "digioi" if _pstate(pidx).get("dt_phase", "digioi") == "digioi" else "train"
        else:
            _early_mode = _early_raw_mode or ("train" if _early_tm else (
                "digioi" if _early_sc == config.DIGIOI_MAP_ID else ("stand" if _early_sc == 0 else "city")
            ))
        _early_train_safes = []
        if _early_tm is not None:
            _rs = _resolve_train_safe(c, _early_sc, _early_tm.get("safe", []))
            if _rs is not None:
                _early_train_safes.append(_rs)
        _login_safe_done = False
        if _early_mode == "train" and _early_tm is not None:
            c.flee_mode = True
            if login_map == _early_sc and _early_train_safes:
                _safe0 = _nearest_safe(c.pos, _early_train_safes)
                try:
                    log.info("[%s] (%s) login o map train -> ve safe %s truoc login chores",
                             label, role, _safe0)
                    c.navigate_to(*_safe0, flee=True)
                    login_map = c.current_map
                    _login_safe_done = True
                except Exception as e:
                    log.warning("[%s] loi ve safe ngay sau login (bo qua): %s", label, e)
        c.log_bag_delayed()   # In tui khi snapshot ve + on dinh (adaptive, toi da 8s) -> dinh danh item
        next_vantieu = None
        next_phuc_than = 0.0   # 0.0 -> kiem tra NGAY lan dau (khong cho 30p roi moi dung lan dau)
        next_ho_phu = 0.0      # Di Gioi Ho Phu: check login + moi 5p, chi khi mode Di Gioi
        c.fight_legion_boss = pcfg.get("fight_legion_boss", True)
        c.di_gioi_level = int(pcfg.get("di_gioi_level", 2))   # idx 1..15 cap quai DG (mac dinh 2=cap25)
        if not is_reconnect:    # RECONNECT nhe: bo qua exp/qua/gacha/mail/vantieu (da lam phien truoc)
            if pcfg.get("claim_offline_exp", True):
                c.request_offline_exp() # NHAN EXP OFFLINE (treo may) - tu nhan neu co
            c.claim_mail()          # nhan qua mail + xoa mail da doc (qua bao tri,...)
            c.claim_checkin()       # diem danh hang ngay (tu dem so lan)
            c.claim_14day_gift()    # qua 14 ngay user moi (0x57)
            c.claim_event_14day()   # event tang qua 14 ngay (0x7c) - khac cai tren
            c.claim_legion_gift()   # nhan qua quan doan hang ngay
            c.claim_friend_gifts()  # tang qua tat ca ban + nhan qua ban tang (hang ngay)
            c.decompose_junk_scrolls()  # phan giai cuon goi pet RAC (junk_scrolls.json) -> nhan xu
            c.donate_legion()           # donate nguyen lieu rac (donate_items.json) cho quan doan -> don tui
            c.use_login_items()         # tu dung item trong list (use_items.json) -> vd tui vat lieu su kien
            # Phuc Than NGAY SAU use_login_items() - luc nay con dung an toan o thanh/diem login
            # (chua di ra bai quai) -> tranh bug dung/deo Phuc Than GIUA luc dang combat ngoai bai
            # (da tung xay ra vi next_phuc_than=0.0 chi trigger o tick dau cua vong lap chinh, co
            # the roi vao luc dang di ra spot/dang danh).
            if pcfg.get("use_phuc_than"):
                try: c.use_phuc_than_items()
                except Exception as e: log.warning("[%s] loi dung phuc than luc login: %s", label, e)
                next_phuc_than = time.time() + 1800
            # Van tieu: nhan qua xong + gui pet; tra ve gio check tiep. Cong tac "Van tieu" trong
            # Cai dat nang cao (mac dinh CO tick - giu hanh vi cu); tat -> khong lam + khong hen gio.
            next_vantieu = c.do_van_tieu() if pcfg.get("do_van_tieu", True) else None
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

        # MODE theo CONFIG RIENG cua party (PARTY_CONFIG[pidx]). Fallback: suy tu START_CITY_ID.
        # (pcfg da doc o tren, giu nguyen bien - khong doc lai)
        sc = pcfg.get("start_city_id", getattr(config, "START_CITY_ID", 0))
        mob_index = pcfg.get("mob_index", 0)
        city_flag = pcfg.get("city_flag", 0)
        # checkbox "Lam nhiem vu hang ngay" (bingo 9 o + dungeon). Fallback key cu "do_dungeon".
        do_daily = pcfg.get("do_daily", pcfg.get("do_dungeon", True))
        auto_world_boss = pcfg.get("auto_world_boss", True)
        auto_team_dungeon = pcfg.get("auto_team_dungeon", True)
        # Mode EVENT (40NPC): mac dinh KHONG lam daily quest (acc event chuyen tam vao event ngay,
        # khong di lang thang lam bingo/pho ban -> vao event nhanh, khong bi dump khoi map event).
        if pcfg.get("mode") == "event":
            do_daily = False
            auto_world_boss = False
            auto_team_dungeon = False
        # mode: digioi | train | city (tap trung ve thanh) | stand (dung yen) | cleanbag
        #       | digioi_train (DG TRUOC, ca party xong DG -> TRAIN map)
        raw_mode = pcfg.get("mode")
        dt_mode = (raw_mode == "digioi_train")
        if dt_mode:
            # Pha DG: chay y het mode "digioi" tren map DG. Pha train: mode "train" tren map da
            # chon (start_city_id). Pha luu o party state -> ca party cung pha.
            if _pstate(pidx).get("dt_phase", "digioi") == "digioi":
                mode, sc = "digioi", config.DIGIOI_MAP_ID
            else:
                mode = "train"
        tm = config.TRAIN_MAPS.get(sc)          # dict {safe, mobs} neu la map train
        if not dt_mode:
            mode = raw_mode
            if not mode:
                mode = ("train" if tm else ("digioi" if sc == config.DIGIOI_MAP_ID
                        else ("stand" if sc == 0 else "city")))
        train_on_map = (mode == "train") and (tm is not None)
        is_digioi = (mode == "digioi")
        dt_dg_finished = False   # mode digioi_train: vua HET GIO DG -> cho party roi sang train
        c.auto_sell_noi_dat = bool(pcfg.get("auto_sell_noi_dat", True) and mode in ("train", "city"))
        ev = None
        train_safes = []
        if tm is not None:
            resolved_safe = _resolve_train_safe(c, sc, tm.get("safe", []))
            if resolved_safe is not None:
                train_safes.append(resolved_safe)
        if train_on_map and is_leader and _needs_train_mob_probe(c, sc, tm):
            try:
                c.arm_mob_packet_capture(
                    sc,
                    max_packets=getattr(config, "MOB_PACKET_CAPTURE_MAX_PACKETS", 50000),
                )
            except Exception as exc:
                log.warning("[%s] khong arm duoc packet capture map %s: %s", label, sc, exc)
        log.info("[%s] (%s) MODE=%s start_city=%s", label, role, mode, sc)

        def _dg_remain_minutes():
            return max(0, DIGIOI_LIMIT - getattr(c, "digioi_minutes", 0))

        def _maybe_use_di_gioi_ho_phu(reason: str) -> bool:
            if not (is_digioi and pcfg.get("use_digioi_ho_phu")):
                return False
            remain = _dg_remain_minutes()
            if remain >= 15:
                return False
            if c.in_combat():
                return False
            before = getattr(c, "digioi_minutes", 0)
            ok = c.use_di_gioi_ho_phu()
            if not ok:
                return False
            log.info("[%s] Di Gioi Ho Phu (%s): con %d phut (<15), da gui lenh dung; "
                     "doi server cap nhat timer", label, reason, remain)
            deadline = time.time() + 8.0
            while time.time() < deadline and getattr(c, "digioi_minutes", 0) == before:
                time.sleep(0.5)
            after = getattr(c, "digioi_minutes", 0)
            after_remain = _dg_remain_minutes()
            if after != before:
                log.info("[%s] Timer Di Gioi sau Ho Phu: used %d -> %d, con %d phut",
                         label, before, after, after_remain)
            else:
                log.info("[%s] Da dung Ho Phu, chua thay 0x55/0x1b doi (used=%d, con %d phut)",
                         label, before, after_remain)
            return True

        def _maybe_auto_world_boss(reason: str):
            if not auto_world_boss:
                return
            try:
                log.info("[%s] Boss the gioi: auto danh het luot (%s)", label, reason)
                c.do_world_boss_all()
            except Exception as e:
                log.warning("[%s] loi auto world boss (%s): %s", label, reason, e)

        def _finish_digioi_train_after_dg():
            _go_town_safe(c, label)
            if not _dt_wait_all_digioi_done(pidx, username, label, _stopped):
                return False
            # Daily/team dungeon can require the whole party. Run it only after every account
            # has finished DG, otherwise an early member can wait for leader while leader is
            # still trying to form the DG party.
            _maybe_auto_world_boss("sau DG, truoc pho ban doi")
            if auto_team_dungeon:
                if not _run_auto_team_dungeons_if_needed(c, st, username, label, pidx,
                                                         is_leader, _stopped, pcfg):
                    return False
            if do_daily:
                try:
                    c.do_daily_dungeon()
                except Exception as e:
                    log.warning("[%s] loi daily dungeon (bo qua): %s", label, e)
                try:
                    c.claim_daily_quests(heavy=True)
                except Exception as e:
                    log.warning("[%s] loi claim daily quest (bo qua): %s", label, e)
            _dt["relogin_train"] = True   # supervisor chay lai -> pha TRAIN
            return True

        def _finish_digioi_train_if_time_over(reason: str) -> bool:
            if not (dt_mode and is_digioi):
                return False
            remain = max(0, DIGIOI_LIMIT - getattr(c, "digioi_minutes", 0))
            out_of_dg = (c.current_map is not None and c.current_map != config.DIGIOI_MAP_ID
                         and not c.in_combat())
            if remain <= 0 or (out_of_dg and remain < 2):
                log.warning("[%s] (%s) DG da het trong luc %s (map=%s, con %d phut) -> "
                            "chuyen sang cho ca party xong DG",
                            label, role, reason, c.current_map, remain)
                _reason("het gio Di Gioi trong luc %s" % reason)
                _finish_digioi_train_after_dg()
                try:
                    c.close()
                except Exception:
                    pass
                if c in _clients:
                    _clients.remove(c)
                return True
            if out_of_dg:
                log.warning("[%s] (%s) dang cho party DG nhung bi ra ngoai DG (map=%s, con %d phut) "
                            "-> vao lai DG", label, role, c.current_map, remain)
                try:
                    c.enter_di_gioi_safe()
                except Exception as e:
                    log.warning("[%s] loi vao lai DG luc cho party: %s", label, e)
            return False

        def _set_train_block_stats_spot(spot, enabled=False):
            if not train_on_map:
                c.set_train_block_stats_context(enabled=False)
                return
            if spot:
                c.set_train_block_stats_context(sc, spot, enabled=(enabled and is_leader))
            else:
                c.set_train_block_stats_context(enabled=False)

        # RA KHOI MAP EVENT truoc: neu login o map event (Nhi Kieu 12922 / 40 NPC 10991...) MA mode
        # KHAC event -> event map KHONG teleport thang duoc -> phai di bo ra cong ve map thuong roi moi
        # lam mode. Tim event co staging_map/dest_map == login_map -> dung 'exit' cua no.
        # TRU mode 'stand' (Login dau dung yen do) -> DUNG YEN TUYET DOI, KHONG tu chay ra.
        if mode not in ("event", "stand") and login_map is not None:
            _evx = next((_e for _e in (getattr(config, "EVENTS", {}) or {}).values()
                         if login_map in (_e.get("staging_map"), _e.get("dest_map")) and _e.get("exit")), None)
            if _evx is not None:
                try:
                    c.exit_event(_evx)
                    login_map = c.current_map   # cap nhat map sau khi ra -> teleport/route ben duoi dung
                    log.info("[%s] (%s) da ra khoi map event -> gio o map %s", label, role, login_map)
                except Exception as e:
                    log.warning("[%s] loi exit_event: %s", label, e)

        # NHIEM VU BINGO (mode KHAC digioi): VE CHO AN TOAN TRUOC roi moi lam dailies (tranh dung
        # giua o quai lam dailies; world boss tu teleport di roi ve Trac Quan; mode positioning ben
        # duoi se dua ve dung cho). Mode DIGIOI lam rieng (vao DG truoc - xem nhanh ben duoi).
        # RECONNECT thi thuong BO QUA daily (da lam phien truoc). NGOAI TRU: team dungeon VO giua chung
        # (o5_need_redo) -> ca party relogin cung nhau -> lam LAI daily (team dungeon can ca party, gio
        # deu dang reconnect nen barrier du nguoi). claim_daily_quests server-guarded -> chi lam phan
        # CHUA xong (team dungeon), cac o da xong tu skip.
        _o5_redo = bool(st.get("o5_need_redo"))
        if _o5_redo and is_reconnect:
            with st["lock"]:
                st["o5_need_redo"] = False   # lam lai 1 lan; neu vo tiep, _handle_o5_team se set lai
            log.info("[%s] (%s) reconnect do team dungeon VO -> lam LAI daily (team dungeon)", label, role)
        _td_redo = bool(st.get("team_dungeon_need_redo"))
        if _td_redo and is_reconnect:
            if not _prepare_team_dungeon_redo_after_reconnect(st, username, label, pidx, _stopped):
                try:
                    c.close()
                except Exception:
                    pass
                return
            log.info("[%s] (%s) reconnect do auto phó bản đội VỠ -> check/chạy lại auto phó bản",
                     label, role)
        _do_startup_world_boss = bool(auto_world_boss and not is_digioi and not is_reconnect)
        _do_startup_team = bool(auto_team_dungeon and not is_digioi and (not is_reconnect or _td_redo))
        _do_startup_daily = bool(not is_digioi and do_daily and (not is_reconnect or _o5_redo))
        if _do_startup_world_boss or _do_startup_team or _do_startup_daily:
            if mode == "city":
                try:
                    if c.go_to_town(sc, city_flag) and c.current_map == getattr(c, "NOI_DAT_SELL_CITY", 12061):
                        c.sell_noi_dat()
                except Exception: pass
            elif train_on_map:
                if login_map == sc and train_safes:
                    if not _login_safe_done:
                        c.navigate_to(*_nearest_safe(c.pos, train_safes))   # dang o bai -> ra diem safe
                else:
                    try: c.teleport(12001, 0)                          # sai map -> ve Trac Quan (route keo ra sau)
                    except Exception: pass
            elif mode == "stand" and train_safes and login_map == sc:
                c.navigate_to(*_nearest_safe(c.pos, train_safes))       # stand map co safe -> ra safe
            # stand map la / khong co safe -> lam tai cho (ke me)
            if _do_startup_world_boss:
                _maybe_auto_world_boss("login, truoc pho ban doi")
            if _do_startup_team:
                if not _run_auto_team_dungeons_if_needed(c, st, username, label, pidx,
                                                         is_leader, _stopped, pcfg):
                    try: c.close()
                    except Exception: pass
                    return
            if _do_startup_daily:
                c.claim_daily_quests()
        elif is_reconnect and train_on_map and train_safes:
            if login_map == sc:
                c.navigate_to(*_nearest_safe(c.pos, train_safes))   # reconnect + dang o bai -> ra safe cho keo
            else:
                # RECONNECT login lai o MAP KHAC train map (truoc khi rot member da teleport di lam
                # daily dungeon -> login = vi tri logout, van o thanh do). KHONG duoc THOAT oan.
                _rt = getattr(config, "TRAIN_ROUTES", {}).get(sc)
                _route_safe = _nearest_safe(c.pos, train_safes)
                _smart_rt = None
                if is_leader:
                    try:
                        if getattr(config, "SMART_WORLD_ROUTING", True):
                            _smart_rt = c.build_smart_route(sc, _route_safe)
                    except Exception as e:
                        log.warning("[%s] reconnect: loi build smart route: %s", label, e)
                if _train_route_available(_smart_rt, _rt, has_leader):
                    # sc la TRAIN MAP di bang ROUTE (qua cong) - KHONG phai thanh, teleport thang toi
                    # sc se FAIL (bug cu: go_to_town(20821) spam 60s roi hut). De khoi reform ben
                    # duoi (barrier + _do_reform) keo qua route; member cho leader keo (khong THOAT).
                    log.info("[%s] (%s) RECONNECT o map %s, train map %s di bang ROUTE -> de reform keo",
                             label, role, login_map, sc)
                else:
                    if getattr(config, "is_teleport_city", lambda _city: True)(sc):
                        # sc la thanh teleport TRUC TIEP -> ve thang sc roi ra safe.
                        log.info("[%s] (%s) RECONNECT o map %s != train map %s -> teleport ve train map roi ra safe",
                                 label, role, login_map, sc)
                        try: c.go_to_town(sc, city_flag)
                        except Exception as e:
                            log.warning("[%s] reconnect: teleport ve train map %s loi: %s", label, sc, e)
                        for _ in range(15):                     # cho map cap nhat sau teleport
                            if c.current_map == sc or not c.running: break
                            time.sleep(1)
                        if c.current_map == sc:
                            login_map = sc                       # -> self_map_ok=True ben duoi, khong THOAT
                            c.navigate_to(*_nearest_safe(c.pos, train_safes))
                    else:
                        log.warning("[%s] (%s) RECONNECT map train %s khong phai thanh teleport -> khong teleport thang",
                                    label, role, sc)

        # BARRIER login-dailies (mode KHAC digioi): CHO CA PARTY xong daily quest (world boss cham
        # + teleport ve Trac Quan) TRUOC khi sync kenh + lap party. Tranh leader sync kenh/moi khi
        # member dang lam daily -> member sai kenh / leader train 1 minh. (digioi: heavy hoan toi
        # cuoi DG nen khong can.)
        if not is_digioi and not is_reconnect and mode != "event":   # event: doc lap, khong cho barrier party
            with st["lock"]:
                st["dailies_done"] += 1
            expected = len(party_accounts(pidx))
            _t0 = time.time()
            while True:   # CHO VO HAN: du party moi sync kenh + lap party. Member dang reconnect ->
                # cong vao (se catch up qua reform); van hoan toan -> ca party dung cho o day.
                if _stopped() or not c.running:
                    break
                with st["lock"]:
                    if st["dailies_done"] + len(st["reconnecting"]) >= expected:
                        break
                if time.time() - _t0 > 30:
                    log.info("[%s] (%s) CHO ca party xong daily (%d/%d, reconnecting=%d)...",
                             label, role, st["dailies_done"], expected, len(st["reconnecting"]))
                    _t0 = time.time()
                time.sleep(1)
            log.info("[%s] (%s) xong daily login (%d/%d acc) -> sync kenh + lap party",
                     label, role, st["dailies_done"], expected)
            with st["lock"]:
                _o5_done = st.get("o5_state") == "done"
            if _o5_done and _clear_o5_client_flags(c):
                log.info("[%s] (%s) o5 da xong -> mo khoa teleport/reform sau pho ban", label, role)

        # Dong bo kenh: 1 dua (picker) chon kenh it nguoi -> ca lu sang cung.
        # Map-train: goi sau khi ve safe (doi kenh tren map thuong khong sao).
        def do_channel_sync():
            current_channel = c.refresh_current_channel(wait=1.5)
            log.info("[%s] (%s) cap nhat kenh hien tai truoc sync: %s",
                     label, role, current_channel if current_channel is not None else "chua biet")

            def _prepare_channel_switch():
                # Client that khong cho doi kenh khi dang trong party; server tra result=3.
                # Roi party cu truoc khi sync de bot khong tuong doi kenh OK trong khi server tu choi.
                try:
                    in_party = bool(getattr(c, "party_members", None) or getattr(c, "party_leader", None)
                                    or is_joined(pidx, c.self_entity))
                except Exception:
                    in_party = bool(getattr(c, "party_members", None) or getattr(c, "party_leader", None))
                if not in_party:
                    return
                try:
                    c.leave_party()
                    if is_leader:
                        reset_party_joined(pidx)
                    else:
                        unmark_joined(pidx, c.self_entity)
                    time.sleep(0.8)
                except Exception as e:
                    log.warning("[%s] (%s) sync kenh: loi roi party cu: %s", label, role, e)

            def _report_channel_map(sync_gen, expected_map):
                ok = _record_channel_map_report(
                    st, username, c.current_map, sync_gen, expected_map, label=label,
                )
                if not ok:
                    log.warning("[%s] (%s) sync kenh: doi kenh xong SAI MAP (%s != %s)",
                                label, role, c.current_map, expected_map)
                return ok

            def _wait_channel_map_reports(sync_gen, expected_map, expected):
                _last = 0
                _t0 = time.time()   # SAFETY: co acc khong tham gia vong sync (da tan ra sau reform)
                while c.running and not _stopped():
                    # -> KHONG cho vo han (deadlock "1/5"): het 60s coi nhu vong sync fail, thoat ra
                    # de leader moi/reform lai (member se dong bo o vong sau) thay vi treo mai.
                    if time.time() - _t0 > 60:
                        with st["lock"]:
                            _n = len(dict(st.get("channel_map_reports") or {}))
                        log.warning("[%s] (%s) sync kenh/map TIMEOUT 60s (%d/%d) -> thoat, moi/reform lai",
                                    label, role, _n, expected)
                        return False
                    with st["lock"]:
                        if st.get("channel_sync_gen") != sync_gen:
                            return False
                        fail = st["channel_failed"].is_set()
                        reason = st.get("channel_failed_reason") or "co acc khong ve dung map/kenh"
                        reports = dict(st.get("channel_map_reports") or {})
                        done = len(reports) + len(st["reconnecting"]) >= expected
                    if fail:
                        log.warning("[%s] (%s) sync kenh/map FAIL (%s) -> pick lai",
                                    label, role, reason)
                        return False
                    if done:
                        bad = {u: mp for u, (ok, mp) in reports.items() if not ok}
                        if bad:
                            log.warning("[%s] (%s) sync kenh/map FAIL, acc sai map: %s",
                                        label, role, bad)
                            return False
                        log.info("[%s] (%s) sync kenh/map OK: %d/%d acc o map %s",
                                 label, role, len(reports), expected, expected_map)
                        return True
                    if time.time() - _last > 15:
                        _last = time.time()
                        log.info("[%s] (%s) cho acc bao cao map sau sync kenh (%d/%d, map yeu cau=%s)...",
                                 label, role, len(reports), expected, expected_map)
                    time.sleep(1)
                return False

            _prepare_channel_switch()
            if is_picker:
                # MOI VONG SYNC: clear channel_ready + channel cu -> member CHO pick MOI (tranh dung
                # kenh cu vong truoc). channel_ready chi clear o start_party -> vong 2+ member ko cho
                # -> kenh ko sync lai. Clear o day de moi vong deu re-sync that su.
                # need = so acc cua party -> chi chon kenh con DU CHO cho CA PARTY (tranh ket instance).
                # pick tra: 0=chi 1 kenh (giu nguyen) | None=co kenh nhung khong du cho (RETRY) | int=da chuyen.
                # KIEN TRI: 30s dau thu lien tuc (3s/lan), sau do 60s/lan, cho toi khi gom du ve 1 kenh.
                need = len(party_accounts(pidx))
                t0 = time.time()
                while c.running and not _stopped():
                    expected_map = c.current_map
                    with st["lock"]:
                        st["channel_ready"].clear()
                        st["channel_failed"].clear()
                        st["channel_failed_reason"] = ""
                        st["channel"] = None
                        st["channel_expected_map"] = expected_map
                        st["channel_map_reports"] = {}
                        st["channel_sync_gen"] = int(st.get("channel_sync_gen", 0)) + 1
                        sync_gen = st["channel_sync_gen"]
                    r = c.pick_best_channel(need=need)
                    if r is None:   # co kenh nhung khong kenh nao du cho ca party -> CHO kenh trong
                        if time.time() - t0 <= 30:
                            time.sleep(3)          # 30s dau: thu lien tuc
                        else:
                            log.info("[%s] (%s) chua co kenh du cho ca party (%d acc) -> cho 60s thu lai...",
                                     label, role, need)
                            time.sleep(60)         # sau do: 1 phut/lan
                        continue
                    ch = r          # 0 (giu nguyen) hoac int (da chuyen) -> chot tam
                    if ch == 0:
                        # KHONG lay duoc danh sach kenh (0x07/0100 game KHONG ho tro - KNOWLEDGE 7e:
                        # chi co SWITCH 0x07/0200 + current_channel tu 0x03/0x0c). "Giu nguyen" mu
                        # quang lam member reconnect vao kenh khac bi BO ROI (bug that 20:55: leader
                        # kenh 1, 2 member kenh 2 -> loop moi vo han "lech kenh live 2!=1"). -> GOM ca
                        # party ve KENH LEADER: set channel = current_channel cua leader; member lech
                        # se switch ve (0x07/0200 verified), member dung kenh thi switch_channel no-op.
                        ch = c.current_channel or 0
                    if not _report_channel_map(sync_gen, expected_map):
                        log.warning("[%s] (%s) picker doi kenh xong sai map -> pick lai", label, role)
                        time.sleep(2)
                        continue
                    with st["lock"]:
                        st["channel"] = ch
                        st["channel_ready"].set()
                    if ch:
                        log.info("[%s] (%s) chon kenh %s cho ca party (%d acc)", label, role, ch, need)
                    else:
                        log.info("[%s] (%s) ca party giu nguyen 1 kenh (khong tach)", label, role)
                    if not _wait_channel_map_reports(sync_gen, expected_map, need):
                        continue
                    break
            else:
                # cho picker CHOT kenh (co the lau neu dang doi kenh trong) -> cho toi khi ready/stop
                while c.running and not _stopped():
                    while not st["channel_ready"].wait(5):
                        if not c.running or _stopped():
                            return
                    with st["lock"]:
                        ch = st["channel"]
                        expected_map = st.get("channel_expected_map")
                        sync_gen = st.get("channel_sync_gen", 0)
                    if not ch:
                        _report_channel_map(sync_gen, expected_map)
                        break
                    if c.switch_channel(ch, wait=4.0, retries=1):
                        if _report_channel_map(sync_gen, expected_map):
                            log.info("[%s] (member) da chuyen sang kenh chung = %s, map=%s",
                                     label, ch, c.current_map)
                            break
                        while (c.running and not _stopped() and st["channel_ready"].is_set()
                               and st.get("channel") == ch):
                            time.sleep(0.5)
                        continue
                    _prepare_channel_switch()
                    if c.switch_channel(ch, wait=4.0, retries=1):
                        if _report_channel_map(sync_gen, expected_map):
                            log.info("[%s] (member) da chuyen sang kenh chung = %s sau khi roi party cu, map=%s",
                                     label, ch, c.current_map)
                            break
                        while (c.running and not _stopped() and st["channel_ready"].is_set()
                               and st.get("channel") == ch):
                            time.sleep(0.5)
                        continue
                    reason = "result=%s" % getattr(c, "_chan_switch_result", None)
                    with st["lock"]:
                        st["channel_failed_reason"] = "%s %s" % (label, reason)
                        st["channel_failed"].set()
                    log.warning("[%s] (member) khong doi duoc sang kenh chung %s (%s) -> bao leader pick lai",
                                label, ch, reason)
                    while (c.running and not _stopped() and st["channel_ready"].is_set()
                           and st.get("channel") == ch):
                        time.sleep(0.5)
                time.sleep(2)

        def _do_reform(to_spot=True):
            """CA party REFORM: ve thanh gom nhau -> leader GIAI TAN party cu + lap lai + KEO ca
            party qua route toi train map (member bi keo theo) -> RA SAFE gan quai TRUOC -> (neu
            to_spot) di tiep ra spot. Dung CHUNG cho 2 tinh huong (truoc day 2 noi code RIENG, trung
            logic nhau -> sua 1 cho quen cho kia, sinh bug "di thang xuyen tuong" o 1 nhanh):
              - LOGIN co acc sai map (goi voi to_spot=False - dung lai rally, de flow chung ben duoi
                lap party/di spot nhu binh thuong neu chua tung lap).
              - DANG CHAY co acc lech map (chet/dump/mat ket noi) - goi tu keepalive, to_spot=True
                (di thang ra spot luon vi khong con buoc nao khac lo tiep)."""
            route2 = getattr(config, "TRAIN_ROUTES", {}).get(sc)
            route_safe = st.get("rally_point") or (
                train_safes[0] if train_safes else None
            )
            spot = st.get("mob_spot")
            _g0 = st["reform_gen"]   # gen reform DANG xu; co gen MOI hon (acc khac van) -> abort keo, quay lai xu
            _ab = lambda: _stopped() or (not c.running) or st["reform_gen"] > _g0
            plan_ready = st.setdefault("route_plan_ready", threading.Event())
            plan = None
            smart_route2 = None
            if is_leader:
                st["route_party_ready"].clear(); st["route_done"].clear()
                plan_ready.clear()
                with st["lock"]:
                    st["route_plan"] = None
                try:
                    if getattr(config, "SMART_WORLD_ROUTING", True):
                        smart_route2 = c.build_smart_route(sc, route_safe)
                except Exception as e:
                    log.warning("[%s] reform: loi build smart route: %s", label, e)
                    smart_route2 = None
                if smart_route2:
                    plan = {"gen": _g0, "city": int(smart_route2["city"]),
                            "flag": int(smart_route2["flag"]), "route": smart_route2}
                elif route2:
                    plan = {"gen": _g0, "city": int(route2.get("from_city", 0)),
                            "flag": int(route2.get("city_flag", 0)), "route": None}
                else:
                    log.warning("[%s] (%s) reform: khong co smart/legacy route -> bo qua", label, role)
                    plan = {"gen": _g0, "missing": True}
                with st["lock"]:
                    st["route_plan"] = plan
                plan_ready.set()
                if plan.get("missing"):
                    return
            else:
                _last_plan_log = 0
                while not _ab():
                    with st["lock"]:
                        _p = st.get("route_plan")
                        if _p and _p.get("gen") == _g0:
                            plan = dict(_p)
                            break
                    if time.time() - _last_plan_log > 15:
                        log.info("[%s] (%s) reform: cho leader lap duong toi map %s...", label, role, sc)
                        _last_plan_log = time.time()
                    plan_ready.wait(1.0)
                    time.sleep(0.2)
                if not plan:
                    return
                if plan.get("missing"):
                    log.warning("[%s] (%s) reform: leader khong co smart/legacy route -> bo qua",
                                label, role)
                    return
            fc = int(plan.get("city", 0)); ff = int(plan.get("flag", 0))
            smart_route2 = plan.get("route") if is_leader else None
            fc_is_city = (not fc) or getattr(config, "is_teleport_city", lambda _city: True)(fc)
            c.flee_mode = True
            if is_leader:
                c.leave_party()                  # GIAI TAN party cu (neu co) -> member duoc tha
                reset_party_joined(pidx)
            if fc:
                # CHI ve thanh gom nhau. KHONG lam boss/dungeon o day nua (truoc day lam MOI VONG
                # reform cho ca member -> churn teleport + keo dai reform -> member de MAT KET NOI
                # giua chung (server chap chon) -> ca party ket reconnect-reform loop, "member khong
                # ve theo leader" (xem log party 3). Boss/dungeon da chay 1 lan o login chores roi.
                # Khop ban APK _reform_to_spot (da cat phan nay). LUU Y: mat tinh nang danh boss QD
                # mid-session-train qua reform (train mode) - danh doi lay reform gon + on dinh.
                # LAP toi khi VE DUOC thanh: go_to_town co the FAIL het ca luot (tra False, vd server
                # cham/ket map la) - truoc day BO QUA ket qua -> acc ket map khac van di tiep xuong
                # sync kenh, leader moi vo tan ma member join khong duoc (server chan invite cross-map,
                # bug thuc te log 18:22). Chua ve duoc thi KHONG duoc di tiep.
                # Fallback thanh CHUA MO phai la QUYET DINH CHUNG PARTY: chi can 1 acc tele fc fail
                # du nguong -> ca reform-gen doi diem gom sang NGHIEP THANH. Neu de tung acc tu fallback
                # rieng, leader co the dung o fc con member dung o Nghiep -> invite ket cross-map.
                def _nghiep_fallback_active():
                    with st["lock"]:
                        return st.get("reform_gather_nghiep_gen") == _g0

                def _activate_nghiep_fallback(reason=None):
                    first = False
                    with st["lock"]:
                        if st.get("reform_gather_nghiep_gen") != _g0:
                            st["reform_gather_nghiep_gen"] = _g0
                            first = True
                    if first:
                        if reason:
                            log.warning("[%s] (%s) %s -> CA PARTY gom o NGHIEP THANH roi leader keo di bo toi %s",
                                        label, role, reason, fc)
                        else:
                            log.warning("[%s] (%s) tele thanh %s FAIL nhieu lan -> CA PARTY gom o "
                                        "NGHIEP THANH roi leader keo di bo toi %s",
                                        label, role, fc, fc)

                if fc and not fc_is_city:
                    _activate_nghiep_fallback(
                        "route-plan city %s KHONG phai thanh teleport" % fc
                    )

                # _town_fail BEN tren client (KHONG reset moi vong _do_reform): reform_gen la bien
                # CHUNG party -> acc khac bump -> _ab() True -> _do_reform BI ABORT + goi lai lien tuc.
                # Chi reset khi VE DUOC dung diem gom cua gen nay.
                _expected = len(party_accounts(pidx))
                _arrival_done = False
                while not _ab() and not _arrival_done:
                    _target_city = 12061 if _nghiep_fallback_active() else fc
                    _target_name = "Nghiep Thanh" if _target_city == 12061 else f"thanh {fc}"
                    while not _ab() and c.current_map != _target_city:
                        _town_ok = False
                        try:
                            if _target_city == fc:
                                # Tele TRUNG GIAN Trac Quan/Ng.Thanh (50-50) truoc roi moi ve thanh route.
                                c.pre_route_town_hop()
                                # budget NGAN (tries=6, battle_grace=0 -> ~12s/lan) de FAIL NHANH:
                                # fc chua mo thi 3 lan ~1 phut la chuyen sang gom o Nghiep Thanh.
                                _town_ok = c.go_to_town(fc, ff, tries=6, wait=2.0, battle_grace=0.0)
                            else:
                                _town_ok = c.go_to_town(12061, 2)
                        except Exception as e:
                            log.warning("[%s] reform: loi ve %s: %s", label, _target_name, e)
                        if _town_ok or c.current_map == _target_city:
                            break
                        if _target_city == fc:
                            c._reform_town_fail = getattr(c, "_reform_town_fail", 0) + 1
                            if getattr(c, "_reform_town_fail", 0) >= 3:
                                c._reform_town_fail = 0
                                _activate_nghiep_fallback()
                                break
                        log.warning("[%s] (%s) reform: CHUA ve duoc %s (map=%s) -> nghi 10s thu lai",
                                    label, role, _target_name, c.current_map)
                        time.sleep(10)
                    if _ab():
                        return
                    # Co acc khac vua bat fallback trong luc minh da toi fc -> quay lai outer loop
                    # de cung ve Nghiep, khong cho barrier dem nham "toi noi" khac map nhau.
                    if _nghiep_fallback_active() and _target_city != 12061:
                        continue
                    if c.current_map != _target_city:
                        continue
                    c._reform_town_fail = 0
                    c._reform_via_nghiep = (_target_city == 12061)
                    # BOSS QUAN DOAN mid-session: reform nay CO THE do boss QD toi luot (train mode
                    # khong danh trong party -> keepalive bump reform_gen ve thanh). Dang SOLO o thanh
                    # (party da giai tan o dau reform) -> DANH LUON, TRUOC khi mark "da toi" -> barrier
                    # ben duoi cho CA PARTY danh xong moi sync kenh + moi lai (khong bi keo vao party
                    # giua chung boss). Gate legion_boss_available() -> reform THUONG (displaced/startup/
                    # dungeon) KHONG chay -> tranh churn town-chore. Danh xong -> available False -> het
                    # trigger -> PHA loop "toi bai -> ve thanh" vo han (bug that: log 10:08). Truoc day
                    # dong bo PC theo APK da CAT phan nay -> mat boss QD mid-train + sinh loop.
                    if not _ab() and getattr(c, "fight_legion_boss", True):
                        try:
                            if c.legion_boss_available():
                                log.info("[%s] (%s) reform: boss QD toi luot -> danh solo o thanh",
                                         label, role)
                                c.do_legion_boss()
                        except Exception as e:
                            log.warning("[%s] reform: loi danh boss QD (bo qua): %s", label, e)
                    # BARRIER: CHO CA PARTY VE DEN CUNG diem gom TRUOC khi sync kenh + moi party.
                    # Bug thuc te (log 10:08): chubon con dang di bo ra khoi DG thi leader da sync kenh
                    # + moi -> chubon accept dung luc dang teleport -> server KHONG ghi nhan (roster chi
                    # 3 member) nhung _mark_joined van dem -> leader tuong du 4/4, keo ca party di train
                    # BO chubon lai. Phai du mat CA PARTY o thanh roi moi di tiep (reconnecting cong vao
                    # de khoi deadlock - acc rot se duoc reform lai khi quay ve).
                    if is_leader:
                        # Member co the ve thanh truoc leader. Clear generation kenh CU truoc khi
                        # leader mark arrived lam barrier du nguoi; sau khi barrier nha, member se
                        # buoc phai cho picker mo generation MOI thay vi an channel_ready stale.
                        _prepare_reform_channel_sync(st)
                    with st["lock"]:
                        _arr = st.setdefault("reform_arrived", {})
                        for _gk in [k for k in _arr if k < _g0]:
                            _arr.pop(_gk, None)   # don gen cu
                        _arr.setdefault(_g0, {})[username] = _target_city
                    _t0 = time.time()
                    while not _ab():
                        if _nghiep_fallback_active() and _target_city != 12061:
                            with st["lock"]:
                                st.get("reform_arrived", {}).get(_g0, {}).pop(username, None)
                            break
                        with st["lock"]:
                            _arr_gen = st.get("reform_arrived", {}).get(_g0, {})
                            _n_arr = sum(1 for _m in _arr_gen.values() if _m == _target_city)
                            _n_rec = len(st["reconnecting"])
                        if _n_arr + _n_rec >= _expected:
                            _arrival_done = True
                            break
                        if time.time() - _t0 > 30:
                            log.info("[%s] (%s) reform: CHO ca party ve %s (%d/%d, reconnecting=%d)...",
                                     label, role, _target_name, _n_arr, _expected, _n_rec)
                            _t0 = time.time()
                        time.sleep(1)
                if _ab():
                    return
            # LUON re-sync kenh (khong chi switch ve kenh cu da luu) - vua ve thanh sau khi CO THE
            # da danh dungeon (solo o1 hoac team o5) -> server co the da day acc sang kenh KHAC (ngau
            # nhien). Chi switch ve kenh CU (st["channel"]) KHONG du: kenh do co the da DAY (full,
            # acc khac dang chiem) sau 1 hoi, hoac ban than viec dung 1 kenh CU thieu kiem tra lai
            # suc chua -> can PICK LAI qua do_channel_sync() (picker tu kiem tra du cho ca party
            # truoc khi chot, xem pick_best_channel) moi chac chan CA PARTY vao chung duoc 1 kenh.
            do_channel_sync()
            if not is_leader:
                # Reform da xong viec rieng + ve diem gom + sync map/kenh. Tu day member moi duoc
                # accept loi moi party thuong; loi moi den som da duoc GameClient giu lai.
                c.set_party_invite_ready(True)
            if is_leader:
                # LAP LAI party TAI THANH: CHO VO HAN toi khi DU member join (khong gioi han 8 lan).
                # Member dang reconnect -> bump reform_gen -> _ab() -> thoat de keepalive reform lai khi
                # no vao. Van hoan toan -> ca party dung o thanh cho (an toan).
                while joined_member_count(pidx) < st["n_members"]:
                    if _ab(): return   # stop / reform moi hon -> thoat de keepalive xu lai
                    try: _invite_party_participants(c, True, gap=1.0)
                    except Exception: pass
                    time.sleep(4)
                log.info("[%s] (LEADER) reform: %d/%d member join lai -> KEO qua cong ra train map",
                         label, joined_member_count(pidx), st["n_members"])
                try: c.set_party_strategist()
                except Exception: pass
                st["route_party_ready"].set()    # bao member: party lap xong, sap keo
                time.sleep(1.5)
                _full = st.get("n_members", 0) > 0 and joined_member_count(pidx) >= st["n_members"]
                c.flee_mode = not _full   # du party -> DANH bat chap khi keo
                if getattr(c, "_reform_via_nghiep", False) and c.current_map != fc:
                    # fc chua mo -> gom o Nghiep Thanh -> KEO ca party DI BO tu Nghiep Thanh toi THANH
                    # fc (gan bai). Member trong party TU FOLLOW qua cong (game keo theo leader). flee=
                    # not _full: du party -> DANH cong NPC. Toi fc roi -> keo fc->bai binh thuong ben duoi.
                    log.info("[%s] (LEADER) fc chua mo -> KEO party DI BO tu Nghiep Thanh -> thanh %s", label, fc)
                    try:
                        _walk_ok = c.follow_smart_scene_route(c.current_map, fc, None, abort=_ab, flee=not _full)
                    except Exception as e:
                        _walk_ok = False
                        log.warning("[%s] (LEADER) loi keo di bo Nghiep->fc: %s", label, e)
                    if not _walk_ok or c.current_map != fc:
                        log.warning("[%s] (LEADER) keo di bo Nghiep->%s that bai (map=%s) -> reform lai",
                                    label, fc, c.current_map)
                        with st["lock"]:
                            st["reform_gen"] += 1
                        c._reform_via_nghiep = False
                        c.flee_mode = True
                        st["route_done"].set()
                        return
                    c._reform_via_nghiep = False
                if smart_route2:
                    c.follow_smart_route(
                        sc, route_safe, abort=_ab, flee=not _full
                    )
                else:
                    # Legacy fallback: member trong party tu theo leader qua tung cong.
                    for stp in route2.get("steps", []):
                        if _ab(): break
                        t1 = time.time()
                        while c.in_combat(idle_secs=3.0) and not _ab() and time.time() - t1 < 60:
                            time.sleep(0.5)
                        if "gate" in stp:
                            if not c._enter_gate(int(stp["x"]), int(stp["y"]), int(stp["gate"])):
                                break
                        else:
                            c.move_to(int(stp["move"][0]), int(stp["move"][1])); time.sleep(0.5)
                # toi train map -> RA SAFE GAN QUAI TRUOC (KHONG di thang tu cong ra spot - duong do
                # CHUA duoc dam bao khong xuyen tuong, chi co safe/mob_path la nguoi dung da tu do
                # tinh toan de an toan). to_spot=False (goi tu login sai map) -> DUNG o day, de flow
                # chung ben duoi (lap party binh thuong + _start_training) tu di tiep ra spot.
                if c.current_map == sc and not _ab():
                    rally2 = st.get("rally_point") or (
                        train_safes[0] if train_safes else None
                    )
                    if rally2:
                        c.navigate_to(*_jitter(rally2), flee=False, abort=_ab)
                    if to_spot and not _ab():
                        path = st.get("mob_path")
                        if path:
                            c.follow_path(path, flee=False, abort=_ab)
                        elif spot:
                            c.navigate_to(*_jitter(spot), flee=False, abort=_ab)
                # Xac nhan THAT SU dang o dung map train (sc) truoc khi coi reform la thanh cong -
                # cung 1 loai bug voi _start_training (xem ghi chu o do): tran chien xen giua co the
                # day leader sang map khac ma cac buoc tren van "thanh cong" (khong bi abort).
                if c.current_map != sc:
                    # KHONG re-bump reform_gen neu drag bi abort do CO reform MOI dang cho (reform_gen
                    # da > _g0 vi acc khac bump) HOAC stop/disconnect (_ab). Truoc day bump lai ->
                    # keepalive reform lai -> drag lai abort NGAY (reform_gen van > _g0) -> "vua lap
                    # party xong da reform" lap vo tan. Reform dang cho se tu xu; chi bump khi THAT SU
                    # ket giua duong (khong phai do reform moi/stop/rot).
                    if _ab():
                        log.info("[%s] (LEADER) drag abort do co reform moi/stop -> return, KHONG re-bump", label)
                        c.flee_mode = True
                        st["route_done"].set()
                        return
                    log.warning("[%s] (LEADER) reform xong NHUNG dang o SAI MAP (%s != %s) -> "
                                "yeu cau REFORM lai ngay, khong cho watchdog", label, c.current_map, sc)
                    with st["lock"]:
                        st["reform_gen"] += 1
                    c.flee_mode = True
                    st["route_done"].set()   # tha member (keepalive se reform lai tu dau)
                    return
                c.combat_ready(); c.flee_mode = False
                st["route_done"].set()
            else:
                # member: cho leader bao party lap xong (route_party_ready) -> roi cho keo xong (route_done).
                # Dang trong party nen tu bi keo qua cong theo leader (giong startup via_route).
                while not st["route_party_ready"].is_set():   # CHO VO HAN leader lap xong party
                    if _ab(): return   # tu rot / stop / reform moi hon -> keepalive xu lai
                    time.sleep(2)
                _full = st.get("n_members", 0) > 0 and joined_member_count(pidx) >= st["n_members"]
                c.flee_mode = not _full   # du party -> DANH bat chap khi bi keo
                while not st["route_done"].is_set():           # CHO VO HAN leader keo xong qua route
                    if _ab(): return
                    time.sleep(2)
                for _ in range(15):                # cho map cap nhat sau khi bi keo
                    if c.current_map == sc or _stopped(): break
                    time.sleep(1)
                c.combat_ready(); c.flee_mode = False

        via_route = False   # True neu toi train map bang KEO PARTY -> da cung kenh + da danh dungeon o thanh
        if train_on_map:
            # PHAI dung map login (toa do safe/mobs chi dung tren map do).
            self_map_ok = (
                login_map == sc
                and not _needs_train_safe_bootstrap(login_map, sc, train_safes)
            )
            def _quit():
                # NGUYEN TAC TOI THUONG: DU FULL PARTY MOI TRAIN -> n_members KHONG BAO GIO tru. Member
                # thoat (rot server / van / het gio) thi leader DUNG CHO no ve, KHONG keo le. Truoc day
                # tru n_members khi thoat -> rot server tru -> n_members ve 0 -> leader keo 1 minh (bug).
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
            # Sai map train -> KHONG train, nhung VAN lam not viec hang ngay (check-in da xong
            # o tren; con solo dungeon) roi moi quit.
            def _daily_then_quit():
                if do_daily:
                    try:
                        c.do_daily_dungeon()
                    except Exception as e:
                        log.warning("[%s] loi daily dungeon (sai map, bo qua): %s", label, e)
                _quit()
            # PARTY-LEVEL: chi can 1 acc sai map -> CA PARTY (ke ca dua DANG O BAI) ve thanh don nhau,
            # lap party du, KEO ca party toi train map + ra safe gan quai (member tu theo). Dung
            # CHUNG _do_reform(to_spot=False) voi nhanh "dang chay lech map" (keepalive) - truoc day
            # la 1 khoi code RIENG, DUOC ~150 dong trung logic voi _do_reform -> khi sua 1 cho (rally
            # truoc khi ra spot) de sot cho kia, gay bug "di thang xuyen tuong tu cong ra spot".
            route = getattr(config, "TRAIN_ROUTES", {}).get(sc)
            _startup_safe = st.get("rally_point") or (
                train_safes[0] if train_safes else None
            )
            smart_route = None
            if is_leader:
                try:
                    if getattr(config, "SMART_WORLD_ROUTING", True):
                        smart_route = c.build_smart_route(sc, _startup_safe)
                except Exception as e:
                    log.warning("[%s] startup: loi build smart route: %s", label, e)
            route_available = _train_route_available(smart_route, route, has_leader)
            if route_available and has_leader:
                expected = len(party_accounts(pidx))
                all_on_map = _party_map_barrier(st, username, self_map_ok, expected, _stopped)
                if not all_on_map:
                    log.info("[%s] (%s) PARTY co acc sai map -> CA PARTY ve thanh don nhau roi KEO toi %s"
                             " (dung _do_reform, dung o safe - chua ra spot)", label, role, sc)
                    _do_reform(to_spot=False)
                    with st["lock"]: st["ready_members"].discard(username)
                    if c.current_map == sc:
                        self_map_ok = True; login_map = sc; via_route = True
                        log.info("[%s] (%s) da toi train map %s qua reform (dang o safe)", label, role, sc)
            if is_leader:
                if not self_map_ok and not c.running:
                    # LEADER MAT KET NOI (vd disconnect giua route) -> KHONG phai "sai map".
                    # Neu SERVER ROT (server_closed) -> supervisor SE reconnect leader -> KHONG set
                    # leader_bad (set = giet het member ngay); member CHO trong vong 150s ben duoi,
                    # leader reconnect + route lai + set leader_ok -> member tiep tuc. Chi set
                    # leader_bad khi KHONG reconnectable (bo cuoc that su).
                    if not _stopped() and not getattr(c, "server_closed", False):
                        c.server_closed = True
                    _srv_drop = getattr(c, "server_closed", False)
                    _reason("leader MAT KET NOI khi dang route toi train map (map cuoi %s)" % c.current_map)
                    log.warning("[%s] (LEADER) MAT KET NOI khi route toi train map %s -> %s",
                                label, sc, "supervisor reconnect, member CHO" if _srv_drop else "ca party thoat")
                    if not _srv_drop:
                        st["leader_bad"].set()
                    try: c.close()
                    except Exception: pass
                    if c in _clients: _clients.remove(c)
                    return
                if not self_map_ok:
                    if not route_available:   # khong co auto/legacy route -> TAT CA PARTY
                        st["leader_bad"].set()   # member thoat het
                        _reason("route-less train + leader sai map (o %s, can %s) -> tat ca party"
                                % (c.current_map, sc))
                        log.warning("[%s] (LEADER) route-less + SAI MAP (o %s, can %s) -> TAT CA PARTY",
                                    label, c.current_map, sc)
                        stop_party(pidx, reason="route-less train + leader sai map")
                        _quit(); return
                    # LEADER sai map + CO route -> KHONG HUY PARTY. LAP reform toi khi len train map
                    # (dung tinh than "cho vo han, du party moi train" - giong nhanh member ben duoi).
                    # Truoc day: _daily_then_quit() -> huy ca party -> 5 nick relogin -> route lai ket
                    # dung cong do (vd cong ket aggro) -> huy... = chinh la canh "party 3 cu vang khi
                    # login". Gio giu party, reform lai; moi lan reform tu lam daily/boss o thanh (xem
                    # _do_reform) nen khong mat viec hang ngay. KHONG set leader_bad (leader dang co,
                    # chua hong) -> member CHO tiep thay vi thoat.
                    _reason("leader sai map (o %s, can %s) - route -> LAP REFORM (khong huy party)"
                            % (c.current_map, sc))
                    log.warning("[%s] (LEADER) SAI MAP (o %s, can train map %s) - KHONG HUY PARTY, "
                                "lap reform toi khi len train map...", label, c.current_map, sc)
                    while c.running and not _stopped():
                        _do_reform(to_spot=False)
                        with st["lock"]: st["ready_members"].discard(username)
                        if c.current_map == sc:
                            self_map_ok = True; login_map = sc; via_route = True
                            log.info("[%s] (LEADER) da len train map %s qua reform (lap)", label, sc)
                            break
                        time.sleep(5)   # chua len duoc -> nghi ngan roi reform lai (khong spam)
                    if not self_map_ok:
                        # thoat vong = stop / mat ket noi (KHONG phai "sai map bo cuoc")
                        if not _stopped() and not c.running and not getattr(c, "server_closed", False):
                            c.server_closed = True
                            log.warning("[%s] (LEADER) MAT KET NOI trong luc reform toi train map "
                                        "-> supervisor reconnect, member CHO", label)
                        _quit(); return
                st["leader_ok"].set()   # leader ok -> member duoc tiep tuc
            else:
                if not self_map_ok and not c.running:
                    _reason("member MAT KET NOI khi dang route (map cuoi %s)" % c.current_map)
                    log.warning("[%s] (member) MAT KET NOI khi dang di chuyen toi train map -> thoat.", label)
                    _quit(); return
                if not self_map_ok:
                    if not route_available:   # khong co auto/legacy route -> TAT CA PARTY
                        _reason("route-less train + member sai map (o %s, can %s) -> tat ca party"
                                % (c.current_map, sc))
                        log.warning("[%s] (member) route-less + SAI MAP (o %s, can %s) -> TAT CA PARTY",
                                    label, c.current_map, sc)
                        stop_party(pidx, reason="route-less train + member sai map")
                        _quit(); return
                    # route-based member sai map (vd reconnect landed sai thanh, hoac reform lan dau
                    # chua hoi tu vi leader dang chap chon). KHONG THOAT oan -> CHO leader keo qua
                    # route (dung tinh than "cho vo han, du party moi train"). Lap _do_reform toi khi:
                    #  - len train map (sc) -> tiep tuc binh thuong
                    #  - leader gone/bad (leader chet han) -> THOAT theo party
                    #  - user stop / mat ket noi -> thoat
                    _reason("member sai map (o %s, can %s) - route -> CHO leader keo (retry reform)"
                            % (c.current_map, sc))
                    log.warning("[%s] (member) SAI MAP (o %s, can %s) - KHONG THOAT, cho leader keo "
                                "qua route (retry reform)...", label, c.current_map, sc)
                    while c.running and not _stopped():
                        if st["leader_gone"].is_set() or st["leader_bad"].is_set():
                            _reason("leader gone/bad khi member cho reform -> THOAT theo party")
                            log.warning("[%s] (member) leader gone/bad khi cho reform -> THOAT", label)
                            _quit(); return
                        _do_reform(to_spot=False)
                        if c.current_map == sc:
                            self_map_ok = True; login_map = sc; via_route = True
                            log.info("[%s] (member) da toi train map %s qua reform (cho leader keo)", label, sc)
                            break
                        time.sleep(5)
                    if not self_map_ok:
                        _quit(); return   # ra vong lap do stop / mat ket noi
                # CO bot-leader -> doi leader quyet dinh (ok/huy). KHONG co leader -> tu di tiep.
                if has_leader:
                    # CHO VO HAN leader quyet dinh (ok/bad). Leader dang reconnect -> chua set ->
                    # member DUNG CHO an toan tai safe (KHONG THOAT nhu truoc - timeout 150s). Thoat
                    # khi Stop / tu rot (-> reconnect). Van hoan toan thi member dung cho o day.
                    _t0 = time.time()
                    while not (st["leader_ok"].is_set() or st["leader_bad"].is_set()):
                        if _stopped() or not c.running: _quit(); return
                        if time.time() - _t0 > 30:
                            log.info("[%s] (member) CHO leader quyet dinh (leader co the dang reconnect)...", label)
                            _t0 = time.time()
                        time.sleep(0.5)
                    if st["leader_bad"].is_set():
                        _reason("leader party loi (sai map hoac mat ket noi) -> ca party bi huy")
                        log.warning("[%s] (member) LEADER party LOI (sai map / mat ket noi - xem dong "
                                    "LEADER o tren) -> ca party huy -> THOAT.", label)
                        _quit(); return
            # --- MAP-TRAIN: CA PARTY ve cung 1 SAFE = safe GAN diem quai leader chon (de gan nhau
            #     -> member vao tran chung voi leader). Leader chon diem quai SOM + bao rally_point. ---
            configured_mobs = [tuple(point) for point in tm.get("mobs", [])]
            mobs = configured_mobs
            if is_leader:
                learned_safe = _capture_arrival_safe(
                    c, sc, came_from_other_map=via_route
                )
                if learned_safe is not None:
                    train_safes[:] = [learned_safe]
                if not train_safes:
                    st["leader_bad"].set()
                    _reason("khong lay duoc safe sau warp vao map %s" % sc)
                    log.warning("[%s] (LEADER) khong lay duoc safe sau warp vao map %s -> TAT PARTY",
                                label, sc)
                    stop_party(pidx, reason="leader khong lay duoc safe sau warp")
                    _quit(); return
                mobs = _resolve_train_mob_centers(c, sc, tm, stop=_stopped)
                learned_safes = [tuple(map(int, point)) for point in
                                 (tm.get("safe", []) or []) if len(point) == 2]
                if learned_safes:
                    train_safes[:] = learned_safes
                if mob_index < 0 and mobs:
                    import random
                    spot = random.choice(mobs)
                else:
                    spot = mobs[mob_index] if (mobs and 0 <= mob_index < len(mobs)) else (mobs[0] if mobs else None)
                st["mob_spot"] = spot
                _set_train_block_stats_spot(spot, enabled=False)
                # CO PATH capture (diem quai XA) -> sau khi lap party leader follow_path keo ca party
                # ra spot; KHONG path -> navigate thang. DU CO PATH HAY KHONG, rally LUON la SAFE gan
                # spot (tap trung + lap party o day TRUOC), KHONG phai spot (truoc set =spot -> ca party
                # navigate thang ra spot luc chua co party -> vo ich, roi lai quay ve safe).
                path = (getattr(config, "MOB_PATHS", {}).get(sc, {}).get(tuple(spot))
                        if spot and tuple(spot) in configured_mobs else None)
                st["mob_path"] = path
                st["rally_point"] = (
                    _nearest_safe(spot, train_safes) if spot else train_safes[0]
                )
                st["rally_ready"].set()
            # member: cho leader chon (rally_point/path); khong co leader -> safe[0]
            if has_leader and not is_leader:
                if not _wait_for_rally(st["rally_ready"], _stopped,
                                       lambda: c.running):
                    _quit(); return
                _set_train_block_stats_spot(st.get("mob_spot"), enabled=False)
            # MAP-TRAIN: CA party (leader+member) ve RALLY = safe GAN spot TRUOC. KHONG follow_path
            # ngay luc nay - vi party CHUA lap (member chua join) -> keo cung vo ich (member khong bi
            # keo theo, leader chay ra spot 1 minh roi quay ve). Sau khi LAP PARTY xong, _start_training
            # moi cho leader follow_path KEO CA PARTY (da join, dang o rally) ra spot.
            rally = st.get("rally_point") or (
                train_safes[0] if train_safes else None
            )
            if rally is None:
                _reason("khong co safe de tap ket tren map %s" % sc)
                _quit(); return
            log.info("[%s] (%s) MAP-TRAIN map=%s -> ve safe tap ket chung %s (lap party TRUOC, keo ra spot SAU)",
                     label, role, sc, rally)
            c.navigate_to(*_jitter(rally))
            # SOLO daily dungeon o MAP-TRAIN: TAM TAT (het luot -> bi dump ve 12000, pha map-train;
            # Bat/tat bang checkbox "Danh daily dungeon" cua party (do_daily).
            # via_route -> da danh dungeon o thanh roi, BO QUA (khoi pha map-train + cho barrier).
            _rg_base = st["reform_gen"]   # moc reform_gen TRUOC dungeon: bi DUMP trong dungeon -> tang -> skip keo ra spot
            if do_daily and not via_route:
                with st["lock"]:
                    st["started_train"] += 1
                try:
                    c.do_daily_dungeon()
                except Exception as e:
                    log.warning("[%s] loi daily dungeon (bo qua): %s", label, e)
                for _ in range(15):
                    if c.current_map == sc:
                        break
                    time.sleep(1)
                if c.current_map != sc:
                    # Bi dungeon DUMP ra sanh (12000)/thanh -> KHONG bo roi, KHONG bat no chay le 1
                    # minh ve. Bump reform_gen -> CA PARTY se reform (ve thanh DON no) o keepalive
                    # ben duoi. Van +dungeon_done de barrier dungeon khong treo cho member nay.
                    log.warning("[%s] (%s) sau dungeon BI DUMP ra %s -> yeu cau CA PARTY reform (ve thanh don)",
                                label, role, c.current_map)
                    with st["lock"]:
                        st["reform_gen"] += 1
                        st["dungeon_done"] += 1
                else:
                    # VE RALLY (safe GAN mob spot leader chon), KHONG phai safe[0] co dinh: truoc day
                    # ve tm["safe"][0] -> member ket o safe[0] xa mob spot -> KHONG bi keo vao tran
                    # party cua leader -> leader danh 1 minh, member dung yen (bug thuc te: map co
                    # nhieu safe/mob, safe[0] khong gan mob leader dang danh).
                    c.navigate_to(*_jitter(rally))
                    with st["lock"]:
                        st["dungeon_done"] += 1
                log.info("[%s] (%s) xong dungeon -> cho ca party (%d/%d)...",
                         label, role, st["dungeon_done"], st["started_train"])
                _t0 = time.time()
                while True:   # CHO VO HAN cho ca party xong dungeon (reconnecting cong vao, khoi deadlock)
                    if _stopped() or not c.running: _quit(); return
                    with st["lock"]:
                        if (st["started_train"] > 0 and
                                st["dungeon_done"] + len(st["reconnecting"]) >= st["started_train"]):
                            break
                    if time.time() - _t0 > 30:
                        log.info("[%s] (%s) CHO ca party xong dungeon (%d/%d, reconnecting=%d)...",
                                 label, role, st["dungeon_done"], st["started_train"], len(st["reconnecting"]))
                        _t0 = time.time()
                    time.sleep(1)
                log.info("[%s] (%s) ca party xong dungeon", label, role)
            if not via_route:   # via_route -> ca party da cung kenh (di theo) -> khoi sync lai
                do_channel_sync()   # map-train: dong bo kenh sau khi ve safe (tren map thuong)
        elif is_digioi:
            # --- DI GIOI ---
            _used_ho_phu_at_login = False
            if pcfg.get("use_digioi_ho_phu"):
                _ho_phu_busy = c.in_combat()
                try:
                    _used_ho_phu_at_login = _maybe_use_di_gioi_ho_phu("login")
                except Exception as e:
                    log.warning("[%s] loi dung Di Gioi Ho Phu luc login (bo qua): %s", label, e)
                if not _ho_phu_busy:
                    next_ho_phu = time.time() + 300   # check lai moi 5 phut
            # 0) PRE-CHECK: doc so phut DG hom nay tu BANG STAT login (0x55 id=0x1b).
            #    Da du gio (>= DIGIOI_LIMIT) -> KHOI vao (truoc day phai vao -> cho 150s moi biet).
            if (_used_ho_phu_at_login and not c.in_di_gioi()
                    and c.digioi_minutes >= DIGIOI_LIMIT):
                log.info("[%s] Da gui Di Gioi Ho Phu luc login nhung timer van %d/%d -> doi them",
                         label, c.digioi_minutes, DIGIOI_LIMIT)
                deadline = time.time() + 8.0
                while time.time() < deadline and c.digioi_minutes >= DIGIOI_LIMIT:
                    time.sleep(0.5)
            if not c.in_di_gioi() and c.digioi_minutes >= DIGIOI_LIMIT:
                log.info("[%s] (%s) DG da HET GIO hom nay (%d/%d phut, doc tu login) -> khong vao",
                         label, role, c.digioi_minutes, DIGIOI_LIMIT)
                _reason("het gio Di Gioi hom nay (doc tu login)")
                if dt_mode:
                    _finish_digioi_train_after_dg()
                    try: c.close()
                    except Exception: pass
                    if c in _clients: _clients.remove(c)
                    return
                # HET GIO DG -> BAY VE THANH (Trac Quan) TRUOC: login co the o map quai (12831...) ->
                # ket tran lien tuc -> teleport boss/dungeon luc dang danh bi server KICK. Ve thanh
                # an toan roi moi lam dailies.
                _go_town_safe(c, label)
                _maybe_auto_world_boss("het gio DG luc login, truoc pho ban doi")
                if auto_team_dungeon:
                    if not _run_auto_team_dungeons_if_needed(c, st, username, label, pidx,
                                                             is_leader, _stopped, pcfg):
                        try: c.close()
                        except Exception: pass
                        if c in _clients: _clients.remove(c)
                        return
                if do_daily:
                    try: c.do_daily_dungeon()
                    except Exception as e:
                        log.warning("[%s] loi daily dungeon (bo qua): %s", label, e)
                # khong vao DG -> lam FULL nhiem vu (nhe + boss) tai cho roi dong
                if do_daily:
                    try: c.claim_daily_quests(heavy=True)
                    except Exception as e:
                        log.warning("[%s] loi claim daily quest (bo qua): %s", label, e)
                # NGUYEN TAC TOI THUONG: DU FULL PARTY MOI LAM -> KHONG tru n_members (het gio DG cung
                # ko tru; leader dung cho, ca party dung yen neu thieu - theo yeu cau).
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
                return
            # 1) PHAI VAO DUOC DG TRUOC (xac nhan in_di_gioi) roi MOI chuyen kenh.
            if not c.in_di_gioi() and not c.enter_di_gioi_safe():
                log.warning("[%s] (%s) khong vao duoc DG (het gio?) -> TAT acc nay", label, role)
                if dt_mode:
                    _finish_digioi_train_after_dg()
                    try: c.close()
                    except Exception: pass
                    if c in _clients: _clients.remove(c)
                    return
                _go_town_safe(c, label)   # ve thanh truoc (thoat o quai) roi lam dailies
                _maybe_auto_world_boss("khong vao duoc DG, truoc pho ban doi")
                if auto_team_dungeon:
                    if not _run_auto_team_dungeons_if_needed(c, st, username, label, pidx,
                                                             is_leader, _stopped, pcfg):
                        try: c.close()
                        except Exception: pass
                        if c in _clients: _clients.remove(c)
                        return
                if do_daily:
                    try: c.claim_daily_quests(heavy=True)   # khong vao DG -> lam full quest roi dong
                    except Exception as e:
                        log.warning("[%s] loi claim daily quest (bo qua): %s", label, e)
                # NGUYEN TAC TOI THUONG: DU FULL PARTY MOI LAM -> KHONG tru n_members.
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
                return
            # 2) DA o trong DG an toan -> lam nhiem vu NHE (gacha/hop + claim hang/cot du) TRUOC khi
            #    dong bo kenh. Gacha/hop KHONG di chuyen nen an toan trong DG; lam xong moi sync kenh
            #    + lap party. KHONG lam o NANG (boss teleport se van ra khoi DG) -> de SAU khi het gio DG.
            if do_daily:
                c.claim_daily_quests(heavy=False)
            # 3) Dong bo kenh (gom ca party ve cung instance DG). Doi kenh trong DG VAN o trong DG.
            #    SOLO -> moi acc chay rieng, KHONG can chung kenh voi ai -> bo qua.
            if pcfg.get("digioi_mode") != "solo":
                do_channel_sync()
        elif mode == "event":
            # --- EVENT: moi nick vao map rieng khi chua co party. Event 40NPC co bot leader se
            # lap party SAU KHI tat ca da vao map; event khac/no-leader van dung yen cho moi tay. ---
            _evs = getattr(config, "EVENTS", {}) or {}
            ev = _evs.get(pcfg.get("event_key") or "")
            if ev is None and _evs:
                # event_key thieu/None/sai (vd config luu truoc khi co picker) -> fallback event DAU
                # TIEN (tien khi chi co 1 event). User chon dung event trong GUI + luu lai la het.
                _k = next(iter(_evs)); ev = _evs[_k]
                log.info("[%s] (%s) mode event: event_key='%s' khong hop le -> dung event dau '%s' (%s)",
                         label, role, pcfg.get("event_key"), _k, ev.get("label"))
            # Sync kenh TRUOC go_to_event: CHI cho event STAND (moi tay). Event PARTY (40NPC) sync
            # LAI SAU khi vao map event (xem duoi) -> KHONG sync o day nua de tranh doi kenh 2 LAN
            # moi vong -> giam churn (leader nhay kenh lien tuc + relogin ca party -> server kick).
            if not _is_party_event(mode, has_leader, ev):
                do_channel_sync()
            if ev is None:
                log.warning("[%s] (%s) mode event nhung KHONG co event nao trong events.json -> dung yen tai cho",
                            label, role)
            else:
                try:
                    c.go_to_event(ev)   # tu day het cinematic (9x 0x14 0600) roi thoat cutscene
                except Exception as e:
                    log.warning("[%s] loi go_to_event: %s", label, e)
            c.flee_mode = False   # dung yen; bi danh thi tu danh, KHONG chu dong (cho moi tay)
        else:
            # --- CITY (tap trung ve thanh) / STAND (dung yen) / CLEANBAG ---
            # SOLO daily dungeon TRUOC (neu bat). Dungeon co the bi DUMP ve 12000 -> lam truoc
            # roi MOI ve thanh -> dam bao dung dung thanh tap trung du co bi dump.
            if do_daily:
                try:
                    c.do_daily_dungeon()
                except Exception as e:
                    log.warning("[%s] loi daily dungeon (bo qua): %s", label, e)
            if mode == "city":
                # Ve thanh SAU dungeon: neu dungeon dump ve 12000 thi teleport ve thanh lan nua.
                log.info("[%s] (%s) TAP TRUNG ve thanh %s (flag %s)%s", label, role, sc, city_flag,
                         " (dung o %s -> ve lai)" % c.current_map if c.current_map != sc else "")
                try:
                    if c.go_to_town(sc, city_flag) and c.current_map == getattr(c, "NOI_DAT_SELL_CITY", 12061):
                        c.sell_noi_dat()
                except Exception as e:
                    log.warning("[%s] loi ve thanh: %s", label, e)
            elif mode == "cleanbag":
                log.info("[%s] (%s) DON TUI DO - chua lam, tam dung yen", label, role)
            else:
                log.info("[%s] (%s) DUNG YEN tai cho login (map=%s)", label, role, c.current_map)
            c.flee_mode = False   # bi danh thi tu danh, KHONG chay
            do_channel_sync()

        _defer_party_invite_for_event = _is_party_event(mode, has_leader, ev)
        _solo_without_party = is_digioi and pcfg.get("digioi_mode") == "solo"
        if not is_leader and not _defer_party_invite_for_event and not _solo_without_party:
            # Da xong login chores + di toi map/diem tap ket + sync kenh. Bay gio moi mo gate
            # party thuong va xu ly loi moi da den tu truoc. Dungeon invite co gate rieng, van
            # hoat dong trong login chores de daily team dungeon khong bi khoa.
            c.set_party_invite_ready(True)
        if not is_leader:
            with st["lock"]:
                st["ready_members"].add(username)
        time.sleep(2)

        # training_started duoc gan trong nhanh "elif is_leader" (o duoi) - PHAI khoi tao truoc o
        # DAY vi vong keepalive (should_fight = training_started if is_leader else ...) doc bien
        # nay bat ke mode nao. Thieu dong nay -> Di Gioi SOLO (re vao nhanh rieng, KHONG chay qua
        # "elif is_leader") crash NGAY: "cannot access local variable 'training_started'".
        training_started = False
        startup_reform_gen_handled = 0
        # Di Gioi SOLO: moi acc chay rieng le hoan toan - khong lap party, khong dong bo kenh (da
        # bo qua o buoc dong bo kenh o tren), khong cho leader/member gi ca. Ai vao duoc DG thi tu
        # chay long vong luon (xem buoc 1-2 o tren: da vao DG + lam nhiem vu nhe).
        digioi_solo = is_digioi and pcfg.get("digioi_mode") == "solo"
        event_mode = (mode == "event")
        # EVENT 40NPC NGOAI GIO (event mo Thu 2/4/6 20-22h): KHONG quan tam co leader hay khong ->
        # HUY party, moi acc TU di doi 'qua chien dau 40NPC' (NPC map 12003) roi THOAT game.
        if (event_mode and _is_npc_repeat_party_event(mode, has_leader, ev)
                and not c.in_40npc_window()):
            log.info("[%s] (%s) 40NPC NGOAI GIO event -> huy party + di doi thuong + thoat game", label, role)
            try: c.leave_party()
            except Exception: pass
            try: c.claim_40npc_reward(ev)
            except Exception as e: log.warning("[%s] loi doi thuong 40NPC (ngoai gio): %s", label, e)
            _reason("40NPC ngoai gio -> doi thuong xong -> thoat game")
            c.close(); return
        event_party_mode = _is_party_event(mode, has_leader, ev)
        event_stand_mode = event_mode and not event_party_mode
        # EVENT PARTY (40NPC): kenh/instance cua MAP EVENT (vd 10991) DOC LAP voi kenh thanh -> sync
        # kenh o tren (luc con o thanh, truoc go_to_event) KHONG dam bao cung instance tren map event.
        # PHAI sync LAI SAU khi ca party da vao map event, TRUOC khi leader moi. Thieu buoc nay: moi
        # acc vao 1 instance khac nhau (vi tri spawn khac) -> moi entity khong toi -> joined=0/4 mai,
        # leader spam moi ma khong ai join -> khong danh duoc (bug user 40NPC 2026-07-29).
        if event_party_mode:
            do_channel_sync()
            if not is_leader:
                # 40NPC chi ready party sau khi DA vao map event va sync instance tai map event.
                c.set_party_invite_ready(True)
        if event_stand_mode:
            # EVENT: da tele toi map event o tren -> DUNG YEN HOAN TOAN, cho moi tay. Moi nick doc lap,
            # KHONG lap party/sync kenh (bo qua het nhanh leader/member ben duoi). Auto-accept moi tay
            # xu ly o client (0x2f). training_started=False -> keepalive KHONG danh chu dong.
            c.flee_mode = False
            log.info("[%s] (%s) EVENT -> dung yen tai map event, cho moi tay (auto-accept)", label, role)
        elif digioi_solo:
            # Di Gioi SOLO cho mang toi 4 pet ra tran CUNG LUC (khac han 1 pet binh thuong) - moi
            # con 1 atype rieng (0,1,3,4), can nhanh combat rieng (combat.decide_multipet, xem
            # state.solo_multipet trong bot/state.py + bot/client.py _make_decisions).
            c.state.solo_multipet = True
            # BAO HIEM: SOLO khong co ai cuu (khac party co quan su hoi SP + dong doi hoi mau ho) ->
            # thieu 1 trong 2 loai thuoc (HP hoac SP) trong tui thi DUNG YEN, KHONG chay long vong
            # danh quai lien tuc -> de het mau chet hoac can SP giua chung ma khong tu hoi duoc.
            if c.has_hp_and_sp_items():
                c.flee_mode = False
                c.combat_ready()
                c.start_run_around()
                log.info("[%s] Di Gioi SOLO -> tu chay long vong (khong lap party, khong dong bo kenh)", label)
            else:
                c.flee_mode = True
                log.warning("[%s] Di Gioi SOLO -> THIEU thuoc hoi HP hoac SP trong tui -> DUNG YEN "
                            "(khong chay long vong, tranh chet/can SP khong ai cuu)", label)
        # --- Leader: CHO du member san sang roi MOI, roi CAY ---
        elif is_leader:
            if via_route:
                # toi train map THEO PARTY (da lap party + cung kenh o thanh) -> KHOI moi lai
                st["invited"].set()   # bao member khoi cho moi
                log.info("[%s] (LEADER) toi train map theo party (da partied) -> bo qua moi lai", label)
            else:
                # PHAI DU PARTY MOI LAM (yeu cau user): leader CHO TAT CA member san sang (da vao DG /
                # ve diem tap ket) roi moi + train. KHONG tru n_members. Rieng DG+Train: neu leader
                # het gio DG ngay trong luc cho/moi party thi thoat vong cho, danh dau xong DG va cho
                # ca party cung xong DG roi moi sang phase train.
                _t0 = time.time()
                while len(st["ready_members"]) < st["n_members"]:
                    if _stopped(): st["stop_leader_done"].set(); c.close(); return
                    if not c.running: c.close(); return
                    if _finish_digioi_train_if_time_over("cho member san sang"):
                        return
                    if time.time() - _t0 > 30:
                        log.info("[%s] (LEADER) CHO du member san sang (%d/%d)...",
                                 label, len(st["ready_members"]), st["n_members"])
                        _t0 = time.time()
                    time.sleep(2)
                log.info("[%s] (LEADER) DU %d/%d member san sang -> MOI (theo entity)",
                         label, len(st["ready_members"]), st["n_members"])
                # MOI toi khi DU PARTY join (khong gioi han 6 lan): member da san sang, invite se toi.
                _t0 = time.time()
                _resync_t0 = time.time()
                while joined_member_count(pidx) < st["n_members"]:
                    if _stopped(): st["stop_leader_done"].set(); c.close(); return
                    if not c.running: c.close(); return
                    if _finish_digioi_train_if_time_over("moi member vao party DG"):
                        return
                    _joined_now = joined_member_count(pidx)
                    _invite_elapsed = time.time() - _resync_t0
                    if _should_resync_incomplete_digioi_party(
                            is_digioi, digioi_solo, _joined_now,
                            st["n_members"], _invite_elapsed):
                        log.warning("[%s] (LEADER) Di Gioi moi %.0fs chua du party (%d/%d) -> "
                                    "giai tan + sync lai kenh + moi lai", label,
                                    _invite_elapsed, _joined_now, st["n_members"])
                        c.flee_mode = True
                        c.leave_party(); reset_party_joined(pidx)
                        st["invited"].clear()
                        do_channel_sync()
                        with st["lock"]:
                            st["resync_gen"] += 1
                        st["invited"].set()
                        _resync_t0 = time.time(); _t0 = time.time()
                        continue
                    if _should_reform_incomplete_party(
                            train_on_map, _joined_now, st["n_members"], _invite_elapsed):
                        log.warning("[%s] (LEADER) moi %.0fs chua du party (%d/%d) -> REFORM "
                                    "dong bo lai map + kenh", label, _invite_elapsed,
                                    _joined_now, st["n_members"])
                        st["invited"].set()   # tha member khoi startup de cung nhan reform_gen
                        with st["lock"]:
                            st["reform_gen"] += 1
                            _startup_gen = st["reform_gen"]
                        c.flee_mode = True
                        try:
                            _do_reform()
                        except Exception as e:
                            log.warning("[%s] startup reform party loi: %s", label, e)
                        startup_reform_gen_handled = max(
                            startup_reform_gen_handled, _startup_gen
                        )
                        _resync_t0 = time.time(); _t0 = time.time()
                        continue
                    # MOI 60s van chua du party -> member co the da troi sang kenh khac (invite khong
                    # toi) -> GIAI TAN party + SYNC KENH lai (keo ca party ve cung kenh) + MOI lai.
                    # Member trong keepalive theo doi resync_gen -> cung roi party + sync kenh theo.
                    if event_party_mode and time.time() - _resync_t0 > 60:
                        log.warning("[%s] (LEADER) moi 60s chua du party (%d/%d) -> GIAI TAN + sync "
                                    "kenh + moi lai", label, joined_member_count(pidx), st["n_members"])
                        c.leave_party(); reset_party_joined(pidx)
                        st["invited"].clear()
                        do_channel_sync()               # picker: chon kenh lai + set channel_ready
                        with st["lock"]: st["resync_gen"] += 1   # bao member cung roi party + sync kenh
                        st["invited"].set()
                        _resync_t0 = time.time(); _t0 = time.time()
                        continue
                    _invite_party_participants(c, train_on_map, gap=1.0)
                    st["invited"].set()
                    time.sleep(4)
                    if time.time() - _t0 > 30:
                        log.info("[%s] (LEADER) dang moi... joined=%d/%d",
                                 label, joined_member_count(pidx), st["n_members"])
                        _t0 = time.time()
                st["invited"].set()
                log.info("[%s] (LEADER) DU PARTY (%d/%d member join)",
                         label, joined_member_count(pidx), st["n_members"])
                if not train_on_map:
                    _invite_whitelist_followers_if_bot_party_ready(
                        c, st, pidx, label, force=True
                    )
            # Bat dau train (set QS + ra cho danh). Goi khi DA co >=1 member (du quan su).
            training_started = False
            def _start_training():
                c.set_party_strategist()    # set member INT cao nhat lam quan su (hoi SP)
                if event_party_mode and _event_battle_kind(mode, has_leader, ev) == "floor_crawl":
                    # 2K (Nhi Kieu): DU PARTY roi moi bat dau leo thap. Moi acc tu di 12921->12922
                    # rieng le (khong party - vao event dinh party la tele loi), toi map event moi
                    # sync kenh + lap party (nhanh _defer_party_invite_for_event o tren lo).
                    if st["event_battle_done"].is_set():
                        c.flee_mode = False
                        log.info("[%s] (LEADER) 2K da xong/dung -> khong leo lai", label)
                        return
                    def _on_crawl_done(lost=False):
                        with st["lock"]:
                            st["event_battle_active"] = False
                            st["event_battle_done"].set()   # THUA -> KHONG mo lai, ket thuc 2K
                        _set_party_quest_mode(pidx, False, label)
                        log.info("[%s] (LEADER) 2K: ket thuc leo thap (%s)",
                                 label, "THUA" if lost else "xong/dung")
                    def _heal_party_2k():
                        # HOI FULL HP/SP CA PARTY sau moi tran (song song, giong 40NPC). Leader tu
                        # hoi thi khong du: member cung an don, ma quest_mode=True lam
                        # _heal_after_battle() cua tung acc thoat som.
                        clients = [account_clients.get(u) for u in _active_party_usernames(pidx)]
                        clients = [x for x in clients if x is not None and x.running]
                        def _heal_one(cli):
                            if cli.running and not cli.state.in_battle:
                                cli.heal_full(force=True)
                        workers = [threading.Thread(target=_heal_one, args=(cli,), daemon=True)
                                   for cli in clients]
                        for w in workers: w.start()
                        for w in workers: w.join(timeout=10)
                        log.info("[%s] (LEADER) 2K: ca party (%d acc) da hoi FULL HP/SP",
                                 label, len(clients))
                    with st["lock"]:
                        st["event_battle_active"] = True
                    c.flee_mode = False
                    _set_party_quest_mode(pidx, True, label)
                    if c.start_floor_crawl(ev, _on_crawl_done, _heal_party_2k):
                        log.info("[%s] (LEADER) 2K: du party -> bat dau leo thap tu map %s",
                                 label, c.current_map)
                elif event_party_mode:
                    if st["event_battle_done"].is_set():
                        c.flee_mode = False
                        log.info("[%s] (LEADER) 40NPC da THUA -> dung yen, khong mo lai battle", label)
                        return
                    point = tuple(ev["party_battle"]["point"])
                    def _on_npc40_loss():
                        with st["lock"]:
                            st["event_battle_active"] = False
                            st["event_battle_done"].set()
                        _set_party_quest_mode(pidx, False, label)
                        log.warning("[%s] (LEADER) 40NPC: PARTY THUA -> chon KHONG va DUNG", label)
                    def _before_npc40_repeat():
                        # npc40.run_loop da chon NO + dong dialog truoc khi vao day. Luc nay moi duoc
                        # dung item; dung item khi prompt dang mo lam server tra 080001 va kick.
                        clients = [account_clients.get(u) for u in _active_party_usernames(pidx)]
                        clients = [x for x in clients if x is not None and x.running]
                        def _heal_one(cli):
                            if cli.running and not cli.state.in_battle:
                                cli.heal_npc40_between_battles()
                        workers = [threading.Thread(target=_heal_one, args=(cli,), daemon=True)
                                   for cli in clients]
                        for worker in workers: worker.start()
                        for worker in workers: worker.join(timeout=8)
                        time.sleep(0.5)  # cho server xu ly item cuoi truoc khi xac nhan dialog
                        log.info("[%s] (LEADER) 40NPC: ca party da hoi phuc -> mo tran tiep", label)
                    with st["lock"]:
                        st["event_battle_active"] = True
                    c.flee_mode = False
                    _set_party_quest_mode(pidx, True, label)
                    if c.start_npc40_loop(point, _on_npc40_loss, _before_npc40_repeat):
                        log.info("[%s] (LEADER) 40NPC: du party -> den %s va bat dau lap battle", label, point)
                elif train_on_map:
                    # CO acc bi DUMP khoi dungeon (reform_gen tang so voi truoc dungeon) -> KHONG keo ra
                    # spot (phi cong: keo xong keepalive lai reform ve thanh). De keepalive REFORM luon.
                    if st["reform_gen"] > _rg_base:
                        log.info("[%s] (LEADER) reform pending (acc bi dump dungeon) -> BO QUA keo ra spot, de keepalive REFORM (ve thanh gom nhau)", label)
                        c.flee_mode = True   # ne quai trong luc cho reform
                        return
                    # diem quai DA chon som (st["mob_spot"]) - ca party da ve safe GAN diem do roi,
                    # va DA LAP PARTY xong (goi tu day) -> gio moi keo ca party ra spot:
                    #   - CO mob_path: leader follow_path KEO ca party (da join, dang o rally) ra spot.
                    #     flee=False de gap quai danh luon (party da du, flee party-battle bi treo).
                    #   - khong path: navigate thang ra spot.
                    spot = st.get("mob_spot")
                    if not spot:
                        c.flee_mode = True
                        log.warning("[%s] (LEADER) map %s khong co tam bai quai -> dung yen, "
                                    "KHONG bat combat o diem bat ky", label, sc)
                        return
                    _set_train_block_stats_spot(spot, enabled=False)
                    path = st.get("mob_path")
                    _gs = st["reform_gen"]   # dang keo ra spot ma co dua VAN MAP (bump reform_gen) -> abort -> reform
                    _abs = lambda: _stopped() or (not c.running) or st["reform_gen"] > _gs
                    if path:
                        log.info("[%s] (LEADER) party da lap -> follow_path KEO ca party ra spot (%d buoc)",
                                 label, len(path))
                        c.follow_path(path, flee=False, abort=_abs)   # party du -> danh; van map -> abort -> reform
                    elif spot:
                        c.navigate_to(*_jitter(spot), flee=False, abort=_abs)
                    if _abs():   # bi abort (co dua van map) -> KHONG tat flee, de keepalive reform
                        log.info("[%s] (LEADER) dang keo ra spot thi co dua van map -> abort, de keepalive REFORM", label)
                        c.flee_mode = True; return
                    # XAC NHAN THAT SU dang o dung map train (sc) TRUOC KHI coi la "toi noi". BUG THAT
                    # (xac nhan qua log thuc te): follow_path/navigate_to KHONG tu kiem tra map dich -
                    # neu 1 tran chien xen giua (vd boss the gioi) day leader ve map khac (vd thanh)
                    # NGAY SAU KHI ham tren "thanh cong" (khong bi abort), code truoc day van coi la
                    # da toi diem quai roi dung yen danh, du thuc te dang o SAI MAP - watchdog displaced
                    # (ben duoi, trong vong giu song) co grace 60s sau reform nen KHONG bat kip ngay,
                    # phai cho ~90s (watchdog relogin khac) moi phat hien. Kiem tra ngay tai day, KHONG
                    # cho watchdog, de phan ung tuc thi.
                    if c.current_map != sc:
                        log.warning("[%s] (LEADER) toi diem quai NHUNG dang o SAI MAP (%s != %s, co the bi "
                                    "tran chien xen giua day di) -> yeu cau REFORM ngay, khong cho watchdog",
                                    label, c.current_map, sc)
                        with st["lock"]:
                            st["reform_gen"] += 1
                        c.flee_mode = True
                        return
                    _set_train_block_stats_spot(spot, enabled=True)
                    c.combat_ready(); c.flee_mode = False   # toi noi -> TAT flee -> dung cay danh
                    log.info("[%s] (LEADER) ra diem quai %s -> dung cay danh.", label, spot)
                elif is_digioi:
                    c.combat_ready(); c.flee_mode = False
                    c.start_run_around()        # DG: chay long vong tim quai
                    log.info("[%s] (LEADER) bat dau chay long vong.", label)
                else:
                    # city/stand: chi set QS, DUNG YEN (cho ban dieu khien tay di nhiem vu)
                    c.flee_mode = False
                    log.info("[%s] (LEADER) %s -> party da tu, DUNG YEN cho dieu khien tay", label, mode)
            _joined = joined_member_count(pidx)
            _can_start = (_joined >= st["n_members"] if event_party_mode else _joined >= 1)
            if _can_start:
                time.sleep(1)
                _start_training(); training_started = True
            else:
                # 0 member -> KHONG co quan su -> DUNG YEN ngam canh, KHONG danh (vo nghia, het SP).
                # Vong keepalive moi 60s se MOI LAI; co member join thi moi bat dau train.
                c.flee_mode = True   # ne battle neu lo dinh -> khong danh khi chua co QS
                log.info("[%s] (LEADER) chua co member (0 quan su) -> DUNG YEN cho member join...",
                         label)
        else:
            if has_leader:
                # CHO VO HAN leader moi vao party (khong timeout 120s -> tranh member tuong da join
                # roi danh le). Leader dang reconnect -> chua moi -> member dung cho o safe.
                while not st["invited"].is_set():
                    if _stopped() or not c.running: break
                    st["invited"].wait(2)
            # DA vao party -> NGUNG flee, DANH tran chung (ca map-train LAN Di Gioi).
            # FLEE trong tran party bi server KICK (vd Tao Thao: member flee -> dis ngay).
            c.flee_mode = False
            if event_party_mode:
                c.combat_ready()
                log.info("[%s] (member) 40NPC: da vao du party -> dung theo leader va tu danh", label)
            elif train_on_map:
                if st.get("mob_spot"):
                    c.combat_ready()   # map thuong: combat-active de quai aggro (DG khong can)
                else:
                    c.flee_mode = True
                    log.warning("[%s] (member) map %s khong co tam bai quai -> khong bat combat",
                                label, sc)
            if has_leader:
                log.info("[%s] (member) da vao party - dung yen tai safe, tu danh", label)
            else:
                log.info("[%s] (member) KHONG co bot-leader -> dung yen tai safe (kenh %s), "
                         "auto-accept - CHO ban moi party tay", label, st.get("channel"))

        # --- Giu song ---
        out_cnt = 0
        last_remove = time.time()
        last_retry = time.time()
        last_dg = 0.0
        last_combat = time.time()   # lan cuoi thay in_combat -> de RE-ARM combat khi ket
        last_rearm = 0.0
        last_relogin = time.time()  # lan cuoi RELOGIN-recovery (ket o bai 90s khong battle)
        relogin_cnt = 0
        displaced_cnt = 0           # so lan lien tiep thay KHAC map train (chet/hoi sinh/bi dump)
        last_reform = time.time()   # lan cuoi REFORM party (grace de khong trigger lien tuc o thanh)
        boss_reform_pending = False # da trigger reform de danh boss QD (chua) - tranh spam reform_gen
        # MUA HP/SP giua phien TRAIN: login da check 1 lan; sau do 2h check lai. buy_hp_sp tu doc
        # kho, du nguong -> khong di (khong roi map). Khi thieu -> acc DI TRAC QUAN mua -> off-map ->
        # reform san co keo CA PARTY ve thanh cho -> xong re-form train tiep (theo yeu cau user).
        next_buy_hpsp = time.time() + 7200
        # reform_gen tang dan trong qua trinh toi-map/reconnect/keo qua cong (moi displaced/sai-map
        # += 1). Neu init handled=0 thi ngay khi bat dau train, keepalive thay reform_gen (cao) >
        # handled(0) -> REFORM NGAY du party VUA lap xong + moi acc dang dung dung map (bug that:
        # log 15:42 - party vua "da vao party" la bi xe "REFORM gen 5" tu rac reform cu).
        #  - Acc DANG dung dung train map (sc): moi reform_gen truoc do da resolved -> lay CURRENT
        #    de KHONG replay (tranh xe party vua lap).
        #  - Acc con LECH map (bi DUMP that luc setup): giu 0 de keepalive reform don no NGAY.
        with st["lock"]:
            reform_gen_handled = (max(startup_reform_gen_handled, st["reform_gen"])
                                  if c.current_map == sc else startup_reform_gen_handled)
        with st["lock"]:
            cmd_gen_handled = st["cmd_gen"]   # lenh thu cong (GUI) da xu ly
            _pending_cmd = st.get("cmd")
            # Neu acc reconnect/login dung luc GUI vua phat lenh DI MAP, thread moi khong duoc coi
            # cmd_gen hien tai la "da xu ly". Khong thi acc do khong report AAA, ca party cho thieu
            # nguoi roi tuong sai map -> teleport/relogin lung tung.
            if (_pending_cmd and _pending_cmd[0] == "route"
                    and not st["manual_route_done"].is_set()):
                cmd_gen_handled = max(0, cmd_gen_handled - 1)
        disc_gen_handled = st["disc_gen"] # RECONNECT: gen disconnect da xu ly (init = hien tai)
        resync_gen_handled = st["resync_gen"]  # RESYNC party (event 40NPC): gen da xu ly

        def _do_manual_cmd(cmd):
            """Thuc thi LENH THU CONG tu GUI (doi kenh / teleport thanh) -> roi TIEP TUC che do da
            setup. Huy party cu truoc, lam hanh dong, roi resume theo mode."""
            kind = cmd[0]

            def _manual_route_reset(gen):
                with st["lock"]:
                    if st.get("manual_route_gen") == gen:
                        return
                    st["manual_route_gen"] = gen
                    st["manual_route_plan"] = None
                    st["manual_route_source_results"] = {}
                    st["manual_route_city_arrived"] = {}
                    st["manual_route_plan_ready"].clear()
                    st["manual_route_source_done"].clear()
                    st["manual_route_party_ready"].clear()
                    st["manual_route_done"].clear()

            def _wait_event(event, desc, timeout=None, gate_follow=False):
                t0 = time.time()
                saw_route_battle = False
                continue_until = 0.0
                last_continue = 0.0
                logged_continue = False
                while not event.wait(0.5 if gate_follow else 1.0):
                    if not c.running or _stopped():
                        return False
                    if timeout is not None and time.time() - t0 > timeout:
                        log.warning("[%s] manual route: cho %s qua %.0fs -> bo qua",
                                    label, desc, timeout)
                        return False
                    if gate_follow:
                        now = time.time()
                        if c.state.in_battle or c.in_combat(idle_secs=1.0):
                            saw_route_battle = True
                            continue_until = 0.0
                            continue
                        if saw_route_battle:
                            grace_until = max(
                                getattr(c, "_battle_end_grace_until", 0.0),
                                getattr(c, "_genuine_end_seen", 0.0) + 4.0,
                            )
                            if now < grace_until:
                                continue
                            if continue_until <= 0:
                                continue_until = now + 12.0
                            if now > continue_until:
                                saw_route_battle = False
                                continue
                            if now - last_continue >= 1.0:
                                if not logged_continue:
                                    log.info("[%s] manual route: member vua xong battle cong -> bam tiep thoai de theo leader",
                                             label)
                                    logged_continue = True
                                try:
                                    c.send(0x14, b"\x06\x00")
                                except Exception:
                                    return False
                                last_continue = now
                return True

            def _wait_manual_city_arrived(expected, timeout=150):
                t0 = time.time()
                while True:
                    if not c.running or _stopped():
                        return False
                    with st["lock"]:
                        n = len(st.get("manual_route_city_arrived", {}))
                    if n >= expected:
                        return True
                    if time.time() - t0 > timeout:
                        log.warning("[%s] manual route: cho ca party ve thanh tap ket (%d/%d) qua %.0fs",
                                    label, n, expected, timeout)
                        return False
                    time.sleep(1)

            def _manual_route_all_at_source(source, expected, timeout=30):
                with st["lock"]:
                    st.setdefault("manual_route_source_results", {})[username] = (
                        c.current_map == source
                    )
                t0 = time.time()
                while True:
                    if not c.running or _stopped():
                        return None
                    with st["lock"]:
                        results = dict(st.get("manual_route_source_results", {}))
                    any_bad = any(v is False for v in results.values())
                    enough = len(results) >= expected
                    if any_bad or enough:
                        return enough and not any_bad and all(results.values())
                    if time.time() - t0 > timeout:
                        log.warning("[%s] manual route: chua du acc report AAA=%s (%d/%d), "
                                    "cho tiep de tranh teleport tap ket oan",
                                    label, source, len(results), expected)
                        t0 = time.time()
                    time.sleep(0.5)

            def _do_manual_route():
                gen = cmd_gen_handled
                source_req = int(cmd[1] or 0)
                dest = int(cmd[2])
                _manual_route_reset(gen)
                # LENH "di map AAA->BBB" LUON can 1 nguoi KEO. Party setting "khong co chu PT"
                # (has_leader=False) thi khong ai la leader -> khong ai lap plan -> ca lu dung im.
                # -> cho PICKER dong vai leader RIENG cho lenh nay (lap party, keo di), den noi
                # thi GIAI TAN party + dung yen o map dich (dung nhu setting khong-chu-PT).
                route_leader = is_leader or (not has_leader and is_picker)
                if route_leader:
                    source = source_req
                    if not source:
                        picked = c.nearest_smart_city(dest, exclude_map=dest)
                        if not picked:
                            log.warning("[%s] manual route: khong tim duoc thanh gan map dich %s",
                                        label, dest)
                            st["manual_route_plan_ready"].set()
                            st["manual_route_done"].set()
                            return
                        source = int(picked["city"])
                    gather = c.nearest_smart_city(source)
                    if not gather:
                        log.warning("[%s] manual route: khong tim duoc thanh gan map bat dau %s",
                                    label, source)
                        st["manual_route_plan_ready"].set()
                        st["manual_route_done"].set()
                        return
                    users = _active_party_usernames(pidx)
                    expected = max(1, len(users))
                    plan = {
                        "source": int(source),
                        "dest": int(dest),
                        "city": int(gather["city"]),
                        "flag": int(gather["flag"]),
                        "expected": int(expected),
                        "users": list(users),
                    }
                    with st["lock"]:
                        st["manual_route_plan"] = plan
                    st["manual_route_plan_ready"].set()
                    log.info("[%s] manual route plan: source=%s dest=%s gather_city=%s flag=%s expected=%s",
                             label, source, dest, gather["city"], gather["flag"], expected)
                if not _wait_event(st["manual_route_plan_ready"], "leader lap route plan", timeout=60):
                    return
                with st["lock"]:
                    plan = dict(st.get("manual_route_plan") or {})
                if not plan:
                    return

                source = int(plan["source"])
                dest = int(plan["dest"])
                gather_city = int(plan["city"])
                gather_flag = int(plan["flag"])
                expected = max(1, int(plan.get("expected", 1)))
                users = list(plan.get("users") or _running_party_usernames(pidx))
                all_at_source = _manual_route_all_at_source(source, expected)
                if all_at_source is None:
                    return
                if not all_at_source:
                    c.flee_mode = True
                    try:
                        c.pre_route_town_hop()
                        c.go_to_town(gather_city, gather_flag)
                    except Exception as e:
                        log.warning("[%s] manual route: loi ve thanh tap ket %s: %s",
                                    label, gather_city, e)
                    with st["lock"]:
                        st.setdefault("manual_route_city_arrived", {})[username] = True
                    _wait_manual_city_arrived(expected)
                else:
                    log.info("[%s] manual route: ca party da o map AAA=%s -> lap party tai cho",
                             label, source)

                do_channel_sync()
                if route_leader:
                    log.info("[%s] manual route: xong sync kenh -> lap party tam de keo map",
                             label)
                if expected > 1:
                    if route_leader:
                        reset_party_joined(pidx)
                        log.info("[%s] manual route: bat dau moi party tam, can %d member join",
                                 label, expected - 1)
                        last_inv_log = 0.0
                        while joined_member_count(pidx) < expected - 1:
                            if not c.running or _stopped():
                                return
                            try:
                                c.invite_members(gap=1.0)
                            except Exception:
                                pass
                            if time.time() - last_inv_log > 10:
                                log.info("[%s] manual route: CHO DU PARTY roi moi keo, joined=%d/%d",
                                         label, joined_member_count(pidx), expected - 1)
                                last_inv_log = time.time()
                            time.sleep(4)
                        _invite_whitelist_followers_if_bot_party_ready(c, st, pidx, label, force=True)
                        try:
                            c.set_party_strategist()
                        except Exception:
                            pass
                        st["manual_route_party_ready"].set()
                        log.info("[%s] manual route: party joined=%d/%d",
                                 label, joined_member_count(pidx), expected - 1)
                    else:
                        _wait_event(st["manual_route_party_ready"], "leader lap party", timeout=None)

                route_completed = False
                if route_leader:
                    route_restart = {"needed": False, "reason": ""}

                    def _route_retry(reason):
                        route_restart["needed"] = True
                        route_restart["reason"] = reason
                        with st["lock"]:
                            st["cmd"] = ("route", source_req, dest)
                            st["cmd_gen"] += 1
                        log.warning("[%s] manual route: %s -> keo lai tu dau (gen %d)",
                                    label, reason, st["cmd_gen"])

                    def _party_maps_bad():
                        if expected <= 1:
                            return None
                        leader_map = c.current_map
                        if leader_map is None:
                            return None
                        bad = []
                        for u in users:
                            cc = account_clients.get(u)
                            if cc is None or not getattr(cc, "running", False):
                                bad.append(f"{u}:off")
                                continue
                            cm = getattr(cc, "current_map", None)
                            if cm is not None and cm != leader_map:
                                bad.append(f"{u}:{cm}")
                        return ", ".join(bad) if bad else None

                    bad_since = {}

                    def abort():
                        if _stopped() or not c.running:
                            return True
                        bad = _party_maps_bad()
                        now = time.time()
                        if _route_mismatch_timed_out(
                            bad_since, c.current_map, bad, now, timeout=30.0
                        ):
                            _route_retry(
                                f"co acc lech map khi dang keo (leader map={c.current_map}, {bad})"
                            )
                            return True
                        return False

                    def _wait_party_map(target_map, timeout=20.0):
                        if expected <= 1:
                            return True
                        t_wait = time.time()
                        while time.time() - t_wait < timeout:
                            bad = _party_maps_bad()
                            if not bad and c.current_map == target_map:
                                return True
                            time.sleep(1)
                        _route_retry(
                            f"party chua cung map {target_map} sau khi keo (leader map={c.current_map}, {bad or 'unknown'})"
                        )
                        return False

                    route_flee = expected <= 1
                    if not route_flee:
                        c.flee_mode = False
                        try:
                            c.combat_ready()
                        except Exception:
                            pass
                    if c.current_map != source:
                        log.info("[%s] manual route: keo party toi AAA=%s truoc", label, source)
                        ok_source = c.follow_smart_route(source, None, abort=abort, flee=route_flee)
                    else:
                        ok_source = True
                    if not route_restart["needed"] and ok_source and c.current_map == source:
                        _wait_party_map(source)
                    st["manual_route_source_done"].set()
                    if (not route_restart["needed"]) and c.current_map == source:
                        log.info("[%s] manual route: keo party AAA=%s -> BBB=%s",
                                 label, source, dest)
                        ok_dest = c.follow_smart_scene_route(source, dest, None, abort=abort, flee=route_flee)
                        if not route_restart["needed"] and ok_dest and c.current_map == dest:
                            _wait_party_map(dest)
                            route_completed = not route_restart["needed"] and c.current_map == dest
                        elif not route_restart["needed"]:
                            _route_retry(f"leader chua toi BBB={dest} (dang map {c.current_map})")
                    elif not route_restart["needed"]:
                        log.warning("[%s] manual route: chua toi AAA=%s (dang map %s) -> khong keo BBB",
                                    label, source, c.current_map)
                        _route_retry(f"leader chua toi AAA={source} (dang map {c.current_map})")
                    st["manual_route_done"].set()
                else:
                    _wait_event(st["manual_route_source_done"], "leader keo toi AAA", timeout=None, gate_follow=True)
                    _wait_event(st["manual_route_done"], "leader keo toi BBB", timeout=None, gate_follow=True)
                    route_completed = c.current_map == dest
                c.flee_mode = False
                # Party "khong co chu PT" chi lap party TAM de keo -> den noi thi GIAI TAN,
                # moi acc dung yen tai map dich (dung nhu setting).
                if not has_leader:
                    try:
                        c.leave_party()
                        if route_leader:
                            reset_party_joined(pidx)
                        if route_completed:
                            log.info("[%s] manual route: den BBB -> giai tan party tam (khong chu PT), dung yen", label)
                        else:
                            log.info("[%s] manual route: chua den BBB -> giai tan party tam de retry/dung yen", label)
                    except Exception as e:
                        log.warning("[%s] manual route: loi giai tan party tam: %s", label, e)

            # KET BATTLE: dang trong tran thi BO CHAY + cho thoat tran TRUOC khi doi kenh/teleport
            # (switch_channel/leave_party giua battle de bi server bo qua/loi). cap 60s.
            c.flee_mode = True
            t0 = time.time()
            while c.in_combat(idle_secs=3.0):
                if not c.running or _stopped() or time.time() - t0 > 60:
                    break
                time.sleep(0.5)
            if is_leader or (kind == "route" and not has_leader):
                c.leave_party(); reset_party_joined(pidx)   # huy party cu
            if kind == "channel":
                ch = cmd[1]
                ok = False
                try:
                    ok = c.switch_channel(ch)
                    time.sleep(1.5)
                except Exception as e:
                    log.warning("[%s] manual: loi doi kenh: %s", label, e)
                if ok:
                    with st["lock"]:
                        st["channel"] = int(ch)
                    log.info("[%s] (%s) manual: da doi kenh -> %d", label, role, ch)
                else:
                    log.warning("[%s] (%s) manual: doi kenh %d THAT BAI", label, role, ch)
            elif kind == "city":
                cid, flag = cmd[1], cmd[2]
                c.flee_mode = True
                try: c.go_to_town(cid, flag)
                except Exception as e: log.warning("[%s] manual: loi teleport thanh: %s", label, e)
                log.info("[%s] (%s) manual: da teleport ve thanh %s", label, role, cid)
            elif kind == "route":
                if mode not in ("stand", "city"):
                    log.warning("[%s] manual route: bo qua vi mode=%s khong phai city/stand",
                                label, mode)
                else:
                    _do_manual_route()
            # --- TIEP TUC che do da setup ---
            if mode in ("stand", "city"):
                # stand: dung yen. city ('ve thanh dung yen'): KHONG teleport ve thanh setting nua,
                # O LAI thanh/kenh vua chuyen (ngang voi stand). -> chi dung yen.
                c.flee_mode = False
            elif is_digioi:
                # train DG: vao lai DG -> lap party. (kenh da chuyen o tren neu la lenh channel)
                c.flee_mode = True
                try:
                    if not c.in_di_gioi():
                        c.enter_di_gioi_safe()
                except Exception as e: log.warning("[%s] manual: loi vao lai DG: %s", label, e)
                if is_leader:
                    for _ in range(6):
                        if not c.running or _stopped(): break
                        try: c.invite_members(gap=1.0)
                        except Exception: pass
                        time.sleep(4)
                        if joined_member_count(pidx) >= st["n_members"]: break
                    _invite_whitelist_followers_if_bot_party_ready(c, st, pidx, label, force=True)
                    try: c.set_party_strategist()
                    except Exception: pass
                c.combat_ready(); c.flee_mode = False
            elif train_on_map:
                # train map: dua CA party ve bai + lap lai (dung lai flow reform). _do_reform ve thanh
                # gom nhau -> switch dung st['channel'] (da set kenh moi neu lenh channel) -> keo ra spot.
                _do_reform()

        stop_ev = account_stops.get(username)
        # Bao stop_account: ACC NAY khi STOP -> thread TU xu ly (KHONG dong socket ngay).
        #  - leader train: tu chay ve safe gan nhat roi dong.
        #  - member train co bot-leader: CHO leader ve safe (stop_leader_done) roi moi dong
        #    -> ca party thoat cung luc, KHONG bi member thoat truoc.
        if is_leader and train_on_map:
            c._return_safe_on_stop = train_safes
        elif (not is_leader) and train_on_map and has_leader:
            c._wait_leader_on_stop = True
        while c.running:
            with st["lock"]:
                st["member_maps"][username] = c.current_map
            # CHU PARTY da thoat (leader_gone) -> member cung THOAT theo (party tan, member o lai vo
            # nghia). TRU Di Gioi SOLO: KHONG lap party thuc su (moi acc chay doc lap hoan toan) ->
            # "leader" chi la vai tro danh nhan trong config, KHONG lien quan gi den viec cac acc
            # khac co chay duoc hay khong -> KHONG duoc thoat theo (da xac nhan bug thuc te: leader
            # out la ca party solo out theo, vo ly vi solo dung y la doc lap).
            if (not is_leader) and has_leader and st["leader_gone"].is_set() and not digioi_solo and not event_stand_mode:
                if _leader_thread_active():
                    log.warning("[%s] (member) leader_gone stale (leader thread van chay) -> clear, KHONG thoat",
                                label)
                    st["leader_gone"].clear()
                else:
                    log.info("[%s] (member) CHU PARTY da thoat -> member thoat theo", label)
                    _reason("chu party thoat -> member theo")
                    break
            if stop_ev is not None and stop_ev.is_set():
                log.info("[%s] (%s) -> STOP tu GUI", label, role)
                if is_leader:
                    # LEADER dang cay ngoai diem quai -> chay ve diem safe GAN NHAT TRUOC,
                    # roi BAO HIEU (stop_leader_done) de member moi thoat theo.
                    if train_on_map:
                        dest = _nearest_safe(c.pos, train_safes)
                        if dest:
                            log.info("[%s] (LEADER) STOP -> chay ve safe gan nhat %s truoc khi thoat",
                                     label, dest)
                            try:
                                c.navigate_to(*dest)
                            except Exception as e:
                                log.warning("[%s] loi chay ve safe (bo qua): %s", label, e)
                    st["stop_leader_done"].set()   # leader da ve safe -> ca party duoc thoat
                    log.info("[%s] (LEADER) da ve safe -> bao member thoat", label)
                elif has_leader:
                    # MEMBER: CHO leader chay ve safe xong (stop_leader_done) roi MOI thoat
                    # -> ca lu thoat cung luc, leader khong bi bo lai ngoai diem quai.
                    log.info("[%s] (member) STOP -> cho leader ve safe roi thoat...", label)
                    if not st["stop_leader_done"].wait(60):
                        log.warning("[%s] (member) cho leader ve safe qua 60s -> thoat luon", label)
                break
            time.sleep(5)
            log.info("[%s] (%s) pos=%s map=%s combat=%s",
                     label, role, c.pos, c.current_map, c.in_combat())
            # ==== 40NPC: run_loop (leader) bao HET GIO / THUA 2 TRAN (c._npc40_done) -> leader phat
            # tin hieu go_claim -> CA party (leader + member) di doi thuong + THOAT game. ====
            if event_party_mode:
                if is_leader and getattr(c, "_npc40_done", False):
                    st["go_claim"].set()
                if st["go_claim"].is_set():
                    log.info("[%s] (%s) 40NPC xong -> di doi thuong + thoat game", label, role)
                    try: c.leave_party()
                    except Exception: pass
                    try: c.claim_40npc_reward(ev)
                    except Exception as e: log.warning("[%s] loi doi thuong 40NPC: %s", label, e)
                    _reason("40NPC het gio/thua 2 -> doi thuong xong -> thoat game")
                    c.close(); break
            # ==== RESYNC party (40NPC / Di Gioi): leader moi khong du -> giai tan + sync kenh lai.
            # Member roi party cu + sync kenh (chuyen sang kenh moi cua leader) -> auto-accept se
            # re-join khi leader moi lai. (Leader tu xu ly trong vong moi, khong vao day.) ====
            if ((not is_leader) and has_leader
                    and (event_party_mode or (is_digioi and not digioi_solo))
                    and st["resync_gen"] > resync_gen_handled):
                resync_gen_handled = st["resync_gen"]
                log.info("[%s] (member) leader RE-SYNC party -> roi party + sync kenh lai", label)
                try: c.leave_party()
                except Exception: pass
                do_channel_sync()   # cho channel_ready (leader da set) + chuyen kenh moi
                c.flee_mode = False
                continue
            # ==== RECONNECT reaction: co dong doi ROT (dang login lai) -> TAM DUNG + cho tat ca ve
            # -> restart mode. CHI khi party co bot-leader (khong thi nick rot da chet). Di Gioi SOLO
            # bo qua (moi acc doc lap). Team dungeon xu o phase daily rieng (relogin ca party). ====
            if (has_leader and not digioi_solo and
                    (not event_mode or event_party_mode) and st["disc_gen"] > disc_gen_handled):
                disc_gen_handled = st["disc_gen"]
                if event_party_mode:
                    if _should_restart_event_party(
                            event_party_mode, st["event_battle_active"],
                            st["disc_gen"], disc_gen_handled - 1):
                        account_forced_reconnect.add(username)
                        _reason("40NPC dang battle co dong doi rot -> relogin ca party")
                        log.warning("[%s] (%s) 40NPC dang battle co dong doi ROT -> RELOGIN cung ca party",
                                    label, role)
                        c.close()
                        break
                    continue
                # Train phai regroup theo disc_gen ke ca khi nick rot da relogin xong. Truoc day
                # ca nhanh nay phu thuoc st["reconnecting"] con phan tu; reconnect nhanh xoa marker
                # truoc nhip keepalive -> survivors nuot disc_gen, khong reform, moi nick mot noi.
                if _should_restart_mode_after_disconnect(train_on_map, st["reconnecting"]):
                    log.warning("[%s] (%s) dong doi ROT %s -> TAM DUNG cho reconnect",
                                label, role, list(st["reconnecting"]))
                    c.flee_mode = True
                    if train_on_map and train_safes:   # train: ve rally dung cho
                        rally = st.get("rally_point") or _nearest_safe(c.pos, train_safes)
                        if rally:
                            try: c.navigate_to(*_jitter(rally))
                            except Exception: pass
                    elif is_digioi:                              # digioi: dung chay long vong
                        try: c.stop_run_around()
                        except Exception: pass
                    if is_leader:                                # giai tan de sau sync kenh duoc
                        try: c.leave_party(); reset_party_joined(pidx)
                        except Exception: pass
                    while st["reconnecting"] and c.running and not _stopped():   # CHO tat ca ve (vo han)
                        time.sleep(3)
                        try:
                            if not c.in_combat(): _use_consumables(c)
                        except Exception: pass
                    if not c.running or _stopped():
                        continue
                    log.info("[%s] (%s) tat ca da reconnect -> restart mode", label, role)
                    if train_on_map:
                        # Supervisor da phat cung reform_gen ngay luc disconnect. Danh dau gen nay
                        # dang duoc xu tai nhanh reconnect de keepalive khong reform trung them 1 lan.
                        reform_gen_handled = max(reform_gen_handled, st["reform_gen"])
                        _route_r = getattr(config, "TRAIN_ROUTES", {}).get(sc)
                        _reconnect_safe = st.get("rally_point") or (
                            train_safes[0] if train_safes else None
                        )
                        _smart_r = None
                        if is_leader:
                            try:
                                if getattr(config, "SMART_WORLD_ROUTING", True):
                                    _smart_r = c.build_smart_route(sc, _reconnect_safe)
                            except Exception as e:
                                log.warning("[%s] reconnect: loi build smart route: %s", label, e)
                        if _train_route_available(_smart_r, _route_r, has_leader):
                            try: _do_reform()
                            except Exception as e: log.warning("[%s] reconnect reform loi: %s", label, e)
                        elif c.current_map != sc:                # route-less + MINH lech map -> TAT CA PARTY
                            log.warning("[%s] (%s) route-less + minh KHAC map train (%s != %s) -> TAT CA PARTY",
                                        label, role, c.current_map, sc)
                            _reason("route-less train + sai map -> tat ca party")
                            stop_party(pidx, reason="route-less train reconnect sai map")
                            continue
                        else:                                    # route-less + CA PARTY o map -> regroup TAI CHO
                            do_channel_sync()                    # (nick lech map da tu stop_party o startup cua no)
                            if is_leader:
                                c.flee_mode = True               # ne quai trong luc CHO du party
                                while joined_member_count(pidx) < st["n_members"]:   # CHO VO HAN: du party moi danh
                                    if not c.running or _stopped(): break
                                    try: _invite_party_participants(c, True, gap=1.0)
                                    except Exception: pass
                                    time.sleep(4)
                                try: c.set_party_strategist()
                                except Exception: pass
                            c.combat_ready(); c.flee_mode = False
                    elif is_digioi:                              # digioi: vao lai DG + leader re-invite
                        c.flee_mode = True
                        try:
                            if not c.in_di_gioi(): c.enter_di_gioi_safe()
                        except Exception: pass
                        if is_leader:
                            while joined_member_count(pidx) < st["n_members"]:   # CHO VO HAN: du party moi danh
                                if not c.running or _stopped(): break
                                try: c.invite_members(gap=1.0)
                                except Exception: pass
                                time.sleep(4)
                            _invite_whitelist_followers_if_bot_party_ready(c, st, pidx, label, force=True)
                            try: c.set_party_strategist()
                            except Exception: pass
                        c.combat_ready(); c.flee_mode = False
                    last_reform = time.time(); last_combat = time.time()
                    continue
            # EVENT: luon TAT flee khi rảnh -> nguoi choi keo bot vao battle (moi tay) thi bot DANH,
            # khong bo chay (flee_mode co the con True tu go_to_event/di chuyen truoc do).
            if event_mode and not c.in_combat() and getattr(c, "flee_mode", False):
                c.flee_mode = False
            # Hoi mau MOI MODE (train/digioi/city/stand...) - chi can ngoai combat.
            # Tu lọc theo nguong HP/SP nen dung yen/ve thanh khong thua mau thi khong dung item.
            if not c.in_combat():
                _use_consumables(c)
            # KET o bai train >40s KHONG vao tran -> co the diem quai xau (khong co quai) HOAC
            # mat combat-active sau khi keo qua cong. LEADER -> DOI diem quai khac + re-arm;
            # member -> chi re-arm (member theo tran cua leader). Tu phuc hoi, khoi restart.
            if c.in_combat():
                last_combat = time.time()
            should_fight = (training_started if is_leader else is_joined(pidx, c.self_entity))
            if (train_on_map and should_fight and not getattr(c, "flee_mode", False)
                    and time.time() - last_combat > 18 and time.time() - last_rearm > 18):
                last_rearm = time.time()
                # 18s khong vao tran -> chi RE-ARM combat-active (mat sau khi qua cong) - KHONG
                # di long vong (vo ich, khong giai quyet duoc gi). Ket that su -> relogin o duoi (90s).
                try: c.combat_ready()
                except Exception: pass
            # KET o bai: >90s KHONG battle du da di long vong (re-arm 18s khong cuu) -> RELOGIN.
            # login=cho logout + goi 0x03 self-spawn -> self.pos RESYNC ve toa do THAT (het drift
            # dead-reckoning lam move_to nham huong). Chay ve rally (safe da chon) TRUOC roi relogin
            # -> tu safe (pos chuan) di lai toi spot. KHONG gioi han so lan (theo yeu cau Anh).
            # CHI leader (leader dieu huong; member theo tran leader + duoc moi lai qua vong 60s).
            if (train_on_map and is_leader and should_fight and not getattr(c, "flee_mode", False)
                    and time.time() - last_combat > 60 and time.time() - last_relogin > 60):
                last_relogin = time.time()
                relogin_cnt += 1
                rally = st.get("rally_point") or _nearest_safe(c.pos, train_safes)
                spot = st.get("mob_spot")
                log.warning("[%s] (LEADER) >90s KHONG battle -> ve safe %s + RELOGIN (lan %d) de resync vi tri",
                            label, rally, relogin_cnt)
                try:
                    c.flee_mode = True
                    if rally:
                        c.navigate_to(*_jitter(rally))   # ve safe da chon truoc khi thoat
                    # GIAI TAN party cu TRUOC khi relogin: leader van dang la leader -> 0x0d sub=04
                    # tan ca party -> 4 member duoc THA khoi party cu. Khong tan thi member van ket
                    # trong party cu -> moi lai KHONG vao (dang trong party roi) -> leader danh 1 minh.
                    c.leave_party(); time.sleep(0.8)
                    reset_party_joined(pidx)         # quen member cu -> leader tinh lai tu dau, retry 60s moi lai
                    if c.relogin():                  # thoat + login lai -> 0x03 resync pos ve dung safe
                        # MOI LAI member NGAY TAI SAFE (leader+member gan nhau) roi CHO ho join
                        # TRUOC khi keo ra spot -> member duoc keo theo. Moi truoc khi di (neu di
                        # spot truoc roi moi moi thi member ket o safe, khong duoc keo).
                        c.combat_ready(); c.flee_mode = False
                        for _ in range(4):           # moi lap lai, cho member (gio da tu do) accept
                            if not c.running or _stopped(): break
                            try: _invite_party_participants(c, True, gap=1.0)
                            except Exception: pass
                            time.sleep(3)
                            if joined_member_count(pidx) >= st["n_members"]:
                                break
                        log.info("[%s] (LEADER) sau relogin: %d/%d member join lai -> keo ra spot",
                                 label, joined_member_count(pidx), st["n_members"])
                        path = st.get("mob_path")
                        _gr = st["reform_gen"]   # dang keo (sau relogin) ma co dua van map -> abort -> reform
                        _abr = lambda: _stopped() or (not c.running) or st["reform_gen"] > _gr
                        if path:
                            c.follow_path(path, flee=False, abort=_abr)   # keo ca party ra spot (path tranh tuong)
                        elif spot:
                            c.navigate_to(*spot, abort=_abr)     # tu safe (pos CHUAN) keo party ra spot
                        c.combat_ready(); c.flee_mode = False
                        last_combat = time.time()    # cho them 90s nua truoc khi relogin tiep
                except Exception as e:
                    log.warning("[%s] loi relogin recovery (bo qua): %s", label, e)
            # DISPLACED: dang train ma BI VAN khoi train map (99% = quai danh chet -> hoi sinh ve
            # thanh). KHONG tu ve lai le loi (party da vo) -> YEU CAU CA PARTY REFORM: acc nao tu
            # thay minh van map thi bump reform_gen -> ca party ve thanh, leader giai tan + lap lai
            # + keo ra bai. grace 60s sau reform de khong trigger lien tuc khi dang o thanh (!=sc).
            if (train_on_map and c.current_map is not None and c.current_map != sc
                    and time.time() - last_reform > 60):
                displaced_cnt += 1
                if displaced_cnt >= 2:   # 2 lan lien tiep (~10s) khac map train -> chac chan displaced
                    displaced_cnt = 0
                    with st["lock"]:
                        st["reform_gen"] += 1
                    log.warning("[%s] (%s) BI VAN khoi train map (dang o %s, vd chet) -> yeu cau CA PARTY reform (gen %d)",
                                label, role, c.current_map, st["reform_gen"])
            else:
                displaced_cnt = 0
            # Bat ky acc nao thay reform_gen TANG (co dua van map) -> CA PARTY cung reform tai cho.
            if train_on_map and st["reform_gen"] > reform_gen_handled:
                reform_gen_handled = st["reform_gen"]
                log.warning("[%s] (%s) -> REFORM party (gen %d)", label, role, reform_gen_handled)
                try: _do_reform()
                except Exception as e:
                    log.warning("[%s] loi reform (bo qua): %s", label, e)
                last_reform = time.time()
                last_combat = time.time()   # reset watchdog relogin sau reform
                continue
            # LENH THU CONG tu GUI (doi kenh / teleport thanh) -> ca party thuc thi roi tiep tuc mode
            if st["cmd_gen"] > cmd_gen_handled:
                cmd_gen_handled = st["cmd_gen"]
                cmd = st.get("cmd")
                log.info("[%s] (%s) -> LENH THU CONG %s", label, role, cmd)
                try:
                    if cmd: _do_manual_cmd(cmd)
                except Exception as e:
                    log.warning("[%s] loi thuc thi lenh thu cong (bo qua): %s", label, e)
                last_reform = time.time()   # grace: khong trigger displaced ngay sau teleport/doi kenh
                last_combat = time.time()
                continue
            try:
                c.reset_daily_counters_if_needed()
                c.claim_online_gifts()   # nhan qua online khi du gio (10/20/30/60/90/180 phut)
            except Exception as e:
                log.warning("[%s] loi reset/qua online (bo qua): %s", label, e)
            # Phuc Than: dinh ky 30p/lan (KHONG phai 1 lan luc login) - CHI khi party bat cong tac
            # "Su dung Phuc Than". Danh gia moi tick (nhu claim_online_gifts) thay vi tach thread rieng.
            # BAT BUOC khong dang combat (dung/deo giua luc danh trong bai quai la vo ly + bug thuc te).
            if pcfg.get("use_phuc_than") and time.time() >= next_phuc_than and not c.in_combat():
                try:
                    c.use_phuc_than_items()
                except Exception as e:
                    log.warning("[%s] loi dung item phuc than (bo qua): %s", label, e)
                next_phuc_than = time.time() + 1800   # 30 phut
            # MUA HP/SP giua phien (chi MODE TRAIN, moi 2h): kho thap -> di Trac Quan mua. buy_hp_sp
            # tu check nguong (du -> khong di). Acc di mua -> off-map -> reform keo party ve thanh cho.
            if (train_on_map and (pcfg.get("buy_hp") or pcfg.get("buy_sp"))
                    and time.time() >= next_buy_hpsp and not c.in_combat()):
                next_buy_hpsp = time.time() + 7200   # 2h (set TRUOC de loi cung khong spam)
                try:
                    _still_low = c.buy_hp_sp(
                        pcfg.get("buy_hp", False), int(pcfg.get("hp_qty", 9999)),
                        int(pcfg.get("hp_thresh", 500000)),
                        pcfg.get("buy_sp", False), int(pcfg.get("sp_qty", 9999)),
                        int(pcfg.get("sp_thresh", 500000)),
                    )
                    # Mua xong VAN THIEU (het xu): co PARTY (nhieu acc) -> train tiep, 2h sau check
                    # lai; SOLO 1 minh -> OUT game (khong tru xu vo ich, dung dam den party khac).
                    if _still_low:
                        if len(party_accounts(pidx)) > 1:
                            log.info("[%s] Mua HP/SP van thieu (het xu) - CO party -> train tiep, "
                                     "2h sau check lai", label)
                        else:
                            log.warning("[%s] Mua HP/SP van thieu (het xu) - SOLO 1 minh -> OUT game", label)
                            _quit(); return
                except Exception as e:
                    log.warning("[%s] loi mua HP/SP giua phien (bo qua): %s", label, e)
            # Di Gioi Ho Phu: chi mode Di Gioi, tick rieng, check moi 5p va chi dung khi con <15p.
            # Server se tu gui 0x55/id=0x1b sau khi dung; khong cong timer thu cong.
            if is_digioi and pcfg.get("use_digioi_ho_phu") and time.time() >= next_ho_phu:
                if not c.in_combat():
                    try:
                        _maybe_use_di_gioi_ho_phu("5p")
                    except Exception as e:
                        log.warning("[%s] loi dung Di Gioi Ho Phu (bo qua): %s", label, e)
                    next_ho_phu = time.time() + 300
            # Van tieu: chi goi lai DUNG GIO escort xong (next_vantieu), KHONG check mu.
            if next_vantieu is not None and time.time() >= next_vantieu:
                try:
                    next_vantieu = c.do_van_tieu()
                except Exception as e:
                    log.warning("[%s] loi van tieu (bo qua): %s", label, e)
                    next_vantieu = time.time() + 600   # loi -> thu lai sau 10p
            # BOSS QUAN DOAN: con luot + het cooldown -> danh. Dang trong battle-party (train) KHONG
            # danh duoc -> TRIGGER REFORM (bump reform_gen) cho ca party ve thanh; luc reform (solo o
            # thanh) moi nick tu danh (xem _do_reform). Solo mode (event/city/stand) -> danh thang.
            if not pcfg.get("fight_legion_boss", True):
                pass   # setting tat -> bo qua hoan toan, KHONG trigger reform vo ich de danh boss
            elif not c.legion_boss_available():
                boss_reform_pending = False   # da danh xong / het luot / dang cooldown -> reset
            elif not c.in_combat():
                if train_on_map:
                    if not boss_reform_pending:   # chi trigger 1 lan / dot con luot (tranh spam reform)
                        with st["lock"]: st["reform_gen"] += 1
                        boss_reform_pending = True
                        log.info("[%s] (%s) boss QD den luot -> TRIGGER REFORM party ve thanh de danh",
                                 label, role)
                elif mode in ("city", "stand"):   # city/stand: nick dung yen SOLO -> danh thang (event
                    try: c.do_legion_boss()       # KHONG danh mid-session vi se roi khoi map event;
                    except Exception as e:        # digioi mid-session bo qua - login da danh)
                        log.warning("[%s] loi boss QD: %s", label, e)
            # --- RETRY KENH + RE-MOI moi 60s (ca DG lan map-train) ---
            # Kenh it nguoi nhat co the KHONG du cho ca party -> co dua ket lai kenh cu.
            # Leader cu train; dua chua join thi 1p chuyen lai kenh chung 1 lan; leader 1p moi lai.
            if has_leader and time.time() - last_retry >= 60:
                last_retry = time.time()
                if is_leader:
                    nj = joined_member_count(pidx)
                    if nj < st["n_members"]:
                        log.info("[%s] (LEADER) chua du member (%d/%d) -> MOI LAI",
                                 label, nj, st["n_members"])
                        try:
                            _invite_party_participants(c, train_on_map, gap=1.0)
                        except Exception: pass
                    # co member join ma chua train (truoc do 0 QS dung yen) -> BAT DAU TRAIN
                    if nj >= 1 and not training_started:
                        log.info("[%s] (LEADER) da co %d member -> SET QS + bat dau train", label, nj)
                        try:
                            _start_training(); training_started = True
                        except Exception as e:
                            log.warning("[%s] loi start training: %s", label, e)
                elif not is_joined(pidx, c.self_entity):
                    if st["leader_gone"].is_set():
                        pass   # chu pt da out -> KHONG retry vao party nua (vo nghia)
                    else:
                        ch = st.get("channel")
                        if ch:
                            log.info("[%s] (member) chua vao party -> retry chuyen kenh %d", label, ch)
                            try:
                                ok = c.switch_channel(ch)
                                if ok:
                                    with st["lock"]:
                                        sync_gen = st.get("channel_sync_gen", 0)
                                        expected_map = st.get("channel_expected_map")
                                    if _record_channel_map_report(
                                            st, username, c.current_map, sync_gen,
                                            expected_map, label=label):
                                        log.info("[%s] (member) retry kenh %d -> da bao cao map=%s "
                                                 "cho sync gen=%s", label, ch,
                                                 c.current_map, sync_gen)
                                time.sleep(1); c.combat_ready()
                                if not ok:
                                    log.warning("[%s] (member) retry chuyen kenh %d THAT BAI", label, ch)
                            except Exception:
                                pass
            if train_on_map:
                pass   # leader da chay long vong (run-around) tu dong tim quai
            elif not is_digioi:
                pass   # city/stand: DUNG YEN, khong lam gi them
            else:
                # DG: dem nguoc thoi gian con lai (digioi_minutes tu S2C 0x55), 30s/lan
                if c.current_map == config.DIGIOI_MAP_ID and time.time() - last_dg >= 30:
                    last_dg = time.time()
                    if digioi_solo:
                        # BAO HIEM: het thuoc GIUA CHUNG (da dung dan) -> DUNG YEN lai; co thuoc
                        # tro lai (nhat item/mua them tay) -> tu chay tiep, KHONG can restart bot.
                        _ok = c.has_hp_and_sp_items()
                        if _ok and c.flee_mode:
                            c.flee_mode = False; c.combat_ready(); c.start_run_around()
                            log.info("[%s] Di Gioi SOLO: da co du thuoc HP+SP tro lai -> chay tiep", label)
                        elif not _ok and not c.flee_mode:
                            c.flee_mode = True
                            log.warning("[%s] Di Gioi SOLO: HET thuoc HP hoac SP -> DUNG YEN", label)
                    remain = max(0, DIGIOI_LIMIT - c.digioi_minutes)
                    h, m = divmod(remain, 60)
                    log.info("[%s] Di Gioi con lai: %dh%dm (da o %d phut)",
                             label, h, m, c.digioi_minutes)
                    if remain <= 5:
                        log.warning("[%s] SAP HET GIO DI GIOI (%d phut)!", label, remain)
                    # HET GIO DG ma VAN CON TRONG map DG (server khong kick) -> CHU DONG thoat +
                    # danh solo daily dungeon roi dong acc. Truoc day chi danh dungeon khi BI DAY RA
                    # khoi DG -> con o trong DG thi ngoi i, khong bao gio danh dungeon.
                    if remain <= 0:
                        log.warning("[%s] (%s) HET GIO DG (van trong DG) -> thoat + solo daily dungeon%s",
                                    label, role, "" if (do_daily and not dt_mode) else " (doi DG+Train/tat dungeon)")
                        if not dt_mode:
                            _go_town_safe(c, label)
                            _maybe_auto_world_boss("het gio DG, truoc pho ban doi")
                            if auto_team_dungeon:
                                _run_auto_team_dungeons_if_needed(c, st, username, label, pidx,
                                                                  is_leader, _stopped, pcfg)
                        if do_daily and not dt_mode:
                            try: c.do_daily_dungeon()
                            except Exception as e:
                                log.warning("[%s] loi daily dungeon sau DG: %s", label, e)
                        dt_dg_finished = dt_mode
                        break
                # KHONG con dung map DG (chet bi day ra town / loi) lien tuc ~10s. Phan biet TIMER:
                #   - con gio (>=2 phut) -> bi day ra SOM -> VAO LAI DG ngay
                #   - het gio that -> thoat party + danh solo daily dungeon roi dong acc
                if c.current_map is not None and c.current_map != config.DIGIOI_MAP_ID and not c.in_combat():
                    out_cnt += 1
                    if out_cnt >= 2:   # ~10s lien tuc ngoai DG
                        remain = max(0, DIGIOI_LIMIT - c.digioi_minutes)
                        if remain >= 2:
                            log.warning("[%s] (%s) KHONG o trong DG (map=%s, chet/bi day ra?) "
                                        "con %d phut -> VAO LAI DG", label, role, c.current_map, remain)
                            try: c.enter_di_gioi_safe()
                            except Exception: pass
                            out_cnt = 0
                        else:
                            log.warning("[%s] (%s) HET GIO DG that -> thoat party%s",
                                        label, role, " + solo daily dungeon" if (do_daily and not dt_mode) else "")
                            if not dt_mode:
                                _go_town_safe(c, label)
                                _maybe_auto_world_boss("het gio DG, truoc pho ban doi")
                                if auto_team_dungeon:
                                    _run_auto_team_dungeons_if_needed(c, st, username, label, pidx,
                                                                      is_leader, _stopped, pcfg)
                            if do_daily and not dt_mode:
                                c.do_daily_dungeon()
                                # XONG DG -> nhiem vu NANG (boss o2 + claim not hang/cot + tong ket).
                                # o1 dungeon vua danh o tren; o5 team dungeon chua co.
                                try: c.claim_daily_quests(heavy=True)
                                except Exception as e:
                                    log.warning("[%s] loi claim daily quest (bo qua): %s", label, e)
                            dt_dg_finished = dt_mode
                            break
                else:
                    out_cnt = 0
        # MODE DG+Train: xong DG -> ve thanh DUNG YEN cho CA PARTY xong roi relogin sang pha train.
        if dt_dg_finished:
            _finish_digioi_train_after_dg()
        try: c.close()
        except Exception: pass
        if c in _clients: _clients.remove(c)
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
                                      "pet_name": getattr(c, "pet_name", None),
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
def party_accounts(pidx):
    """List (username, password, is_leader, is_picker) cua party pidx (bo slot trong)."""
    party = config.PARTIES[pidx]
    leader_acc = config.PARTY_LEADER_ACC.get(pidx)
    valid = [(u, p) for u, p in party if u and u.strip()]
    picker_acc = leader_acc if leader_acc else (valid[0][0] if valid else None)
    return [(u, p, u == leader_acc, u == picker_acc) for u, p in valid]


def _clear_o5_client_flags(c):
    active = (
        time.time() < getattr(c, "_phoban_until", 0.0)
        or time.time() < getattr(c, "_team_dungeon_until", 0.0)
        or getattr(c.state, "quest_mode", False)
    )
    c._phoban_until = 0.0
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


def _mark_team_dungeon_broken(st, level):
    st.setdefault("team_dungeon_broke", {})[level] = True
    st["team_dungeon_need_redo"] = True
    st.setdefault("team_dungeon_state", {})[level] = "done"
    st.setdefault("team_dungeon_recover_seen", set()).clear()
    ev = st.setdefault("team_dungeon_recover_ready", threading.Event())
    ev.clear()


def _prepare_team_dungeon_redo_after_reconnect(st, username, label, pidx, stopped_fn):
    members = [t[0] for t in party_accounts(pidx)]
    if not members:
        return True
    ev = st.setdefault("team_dungeon_recover_ready", threading.Event())
    ready_now = False
    with st["lock"]:
        seen = st.setdefault("team_dungeon_recover_seen", set())
        seen.add(username)
        if len(seen) >= len(members):
            st["team_dungeon_done_by"] = {}
            st["team_dungeon_state"] = {}
            st["team_dungeon_broke"] = {}
            st["team_dungeon_need_redo"] = False
            seen.clear()
            ev.set()
            ready_now = True
    if ready_now:
        log.info("[%s] auto phó bản đội: cả party đã relogin sau PB vỡ -> chạy lại từ đầu", label)
        return True
    last_log = 0.0
    while not ev.is_set():
        if stopped_fn():
            return False
        if time.time() - last_log > 30:
            with st["lock"]:
                n_seen = len(st.setdefault("team_dungeon_recover_seen", set()))
            log.info("[%s] auto phó bản đội: chờ cả party relogin sau PB vỡ (%d/%d)...",
                     label, n_seen, len(members))
            last_log = time.time()
        time.sleep(1)
    return True


def _handle_auto_team_dungeon(c, st, username, label, pidx, is_leader, stopped_fn, level):
    level = int(level)
    if not c.wait_team_dungeon_status(timeout=6.0):
        remaining = None
        log.warning("[%s] (%s) phó bản đội lv%d: chưa có status 0x18 -> bỏ qua level này",
                    label, "LEADER" if is_leader else "member", level)
    else:
        remaining = c.team_dungeon_remaining(level)
    with st["lock"]:
        reports = st.setdefault("team_dungeon_done_by", {}).setdefault(level, {})
        reports[username] = remaining
    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    if not has_leader:
        return True
    if not is_leader:
        last_log = 0.0
        while True:
            if stopped_fn() or not c.running:
                return False
            if time.time() - last_log > 60:
                log.info("[%s] (member) chờ leader xử lý phó bản đội lv%d...", label, level)
                last_log = time.time()
            if st["reconnecting"]:
                log.warning("[%s] (member) đồng đội rớt trong phó bản đội lv%d -> relogin thoát instance",
                            label, level)
                with st["lock"]:
                    _mark_team_dungeon_broken(st, level)
                    st["reform_gen"] += 1
                _clear_o5_client_flags(c)
                return _force_supervisor_reconnect(
                    username, c, "phó bản đội vỡ do đồng đội rớt"
                )
            with st["lock"]:
                state = st.setdefault("team_dungeon_state", {}).get(level, "idle")
                broke = bool(st.setdefault("team_dungeon_broke", {}).get(level, False))
            if state == "done":
                if broke:
                    log.warning("[%s] (member) phó bản đội lv%d vỡ -> relogin thoát instance",
                                label, level)
                    _clear_o5_client_flags(c)
                    return _force_supervisor_reconnect(
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
    while True:
        if stopped_fn() or not c.running:
            return False
        # Dong doi rot / PB can danh lai TRONG luc leader dang cho report: truoc day leader KHONG
        # co check nay -> member da _mark_team_dungeon_broken + relogin vao hang recover, con leader
        # ket o vong cho report vo han (bug that: leader "cho report 1/5", member "cho relogin 4/5",
        # 2 hang khac nhau khong bao gio gap). -> leader cung relogin vao hang recover de CA PARTY
        # dong bo roi DANH LAI tu dau (giong het nhanh member o tren).
        with st["lock"]:
            _need_redo = bool(st.get("team_dungeon_need_redo"))
            _recon = bool(st["reconnecting"])
        if _recon or _need_redo:
            log.warning("[%s] (LEADER) dong doi rot/PB vo khi cho report lv%d -> relogin vao hang "
                        "recover de ca party danh lai", label, level)
            with st["lock"]:
                _mark_team_dungeon_broken(st, level)
                st["reform_gen"] += 1
            _clear_o5_client_flags(c)
            return _force_supervisor_reconnect(
                username, c, "phó bản đội vỡ (leader đồng bộ lại để đánh lại)"
            )
        with st["lock"]:
            reports = dict(st.setdefault("team_dungeon_done_by", {}).setdefault(level, {}))
            reported = all(m in reports or m in st["reconnecting"] for m in members)
        if reported:
            break
        if time.time() - last_log > 30:
            log.info("[%s] (LEADER) chờ cả party report lượt phó bản đội lv%d (%d/%d)...",
                     label, level, len(reports), len(members))
            last_log = time.time()
        time.sleep(2)

    with st["lock"]:
        reports = dict(st.setdefault("team_dungeon_done_by", {}).setdefault(level, {}))
    if level not in (20, 50, 80, 110):
        log.warning("[%s] (LEADER) phó bản đội lv%d: đã biết trạng thái lượt nhưng chưa có script "
                    "đường đi/trận an toàn -> bỏ qua", label, level)
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
        try:
            ok = bool(c.do_team_dungeon(level))
            if not ok:
                log.warning("[%s] (LEADER) phó bản đội lv%d trả FAIL", label, level)
            if st["disc_gen"] > dg0 or st["reconnecting"]:
                log.warning("[%s] (LEADER) đồng đội rớt trong phó bản đội lv%d -> relogin thoát instance",
                            label, level)
        finally:
            active = _clear_o5_client_flags(c)
            with st["lock"]:
                broken = ((not ok) or (not c.running)
                          or st["disc_gen"] > dg0 or bool(st["reconnecting"]))
                if broken:
                    _mark_team_dungeon_broken(st, level)
                st.setdefault("team_dungeon_state", {})[level] = "done"
                st["reform_gen"] += 1
        if broken:
            return _force_supervisor_reconnect(
                username, c, "phó bản đội vỡ" if active else "phó bản đội fail"
            )
        return c.running
    with st["lock"]:
        st.setdefault("team_dungeon_state", {})[level] = "done"
    log.info("[%s] (LEADER) phó bản đội lv%d: không phải cả party đều còn lượt (đã hết: %s) -> bỏ qua",
             label, level, done)
    return True


def _run_auto_team_dungeons_if_needed(c, st, username, label, pidx, is_leader, stopped_fn, pcfg):
    if not pcfg.get("auto_team_dungeon", True):
        return True
    flags = _team_dungeon_flags(pcfg)
    levels = getattr(config, "TEAM_DUNGEON_LEVELS", (20, 50, 80))
    for level in levels:
        if not flags.get(int(level), False):
            continue
        if not _handle_auto_team_dungeon(c, st, username, label, pidx, is_leader,
                                         stopped_fn, int(level)):
            return False
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
    with st["lock"]:
        st["o5_done_by"][username] = bool(o5_done)
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
        while True:
            if stopped_fn() or not c.running:
                return
            if time.time() - _t0log > 60:
                log.info("[%s] (member) CHO leader danh xong team dungeon...", label)
                _t0log = time.time()
            # CASE 3: dong doi ROT trong luc dang danh team dungeon -> RELOGIN de bi day ra ngoai
            # instance (trong dungeon teleport/ve thanh bi chan -> chi relogin moi thoat -> chay tiep).
            if st["reconnecting"]:
                log.warning("[%s] (member) dong doi ROT trong team dungeon -> RELOGIN thoat instance", label)
                try: c.relogin()
                except Exception: pass
                _clear_o5_client_flags(c)
                return
            with st["lock"]:
                state = st["o5_state"]
                _broke = st["o5_broke"]
            if state == "done":
                if _broke:
                    # team dungeon VO do co dis -> member CON KET trong instance (map dungeon),
                    # go_to_town KHONG thoat duoc -> RELOGIN moi ra (dung nguyen tac "du party thi
                    # cung nhau"). Truoc day chi return -> spam go_to_town vo tan.
                    log.warning("[%s] (member) team dungeon VO (co dis) -> RELOGIN thoat instance", label)
                    try: c.relogin()
                    except Exception: pass
                # Leader da xong (thanh cong hay fail deu vay) -> HA NGAY _phoban_until (thay vi
                # cho het 600s co dinh dat luc accept moi pho ban). Khong ha som -> go_to_town() cua
                # member van BAIL ("dang vao pho ban -> ngung teleport") ngay sau khi flow rieng
                # (sync kenh + lap party) goi toi, roi rot vao nhanh "map mismatch -> lam dungeon
                # roi THOAT" sai cho (member tuong minh dang o pho ban solo o1).
                _clear_o5_client_flags(c)
                return
            if not c.in_combat():   # xong 1 tran team dungeon (member auto-danh) -> hoi HP/SP
                try: c.do_heal()
                except Exception: pass
            time.sleep(2)
    members = [t[0] for t in party_accounts(pidx)]
    if len(members) < 2:
        return   # khong du party de danh pho ban to doi
    # CHO VO HAN tat ca member (gom leader) report o5. Member dang reconnect -> coi nhu se report
    # (khoi deadlock); van hoan toan -> leader dung cho, khong quyet dinh voi report thieu.
    _t0log = time.time()
    while True:
        if stopped_fn() or not c.running:
            return
        with st["lock"]:
            reported = all(m in st["o5_done_by"] or m in st["reconnecting"] for m in members)
        if reported:
            break
        if time.time() - _t0log > 30:
            log.info("[%s] (LEADER) CHO ca party report o5 (%d/%d)...",
                     label, len(st["o5_done_by"]), len(members))
            _t0log = time.time()
        time.sleep(2)
    with st["lock"]:
        statuses = dict(st["o5_done_by"])
    if all(not statuses.get(m, True) for m in members):       # MOI nguoi deu chua xong
        log.info("[%s] (LEADER) CA party (%d nguoi) chua xong o5 -> PHO BAN TO DOI LV20", label, len(members))
        with st["lock"]:
            st["o5_state"] = "running"   # member biet ma CHO, khong chay tiep
            st["o5_broke"] = False       # reset moi lan danh (co set True o finally neu co dis)
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
                log.warning("[%s] (LEADER) phong pho ban THIEU nguoi -> relogin ca party, danh lai", label)
                try: c.relogin()
                except Exception: pass
            # CASE 3: co dong doi ROT trong luc danh team dungeon -> leader cung RELOGIN thoat instance
            # (giong member) truoc khi ve flow. reform_gen (finally) + train reaction se gom lai sau.
            if st["disc_gen"] > _dg0 or st["reconnecting"]:
                log.warning("[%s] (LEADER) dong doi ROT trong team dungeon -> RELOGIN thoat instance", label)
                try: c.relogin()
                except Exception: pass
        finally:
            _clear_o5_client_flags(c)
            with st["lock"]:
                # VO do co dis (chinh leader rot = not c.running, HOAC co member rot = disc_gen/
                # reconnecting): bao member -> CA party relogin thoat instance (trong dungeon KHONG
                # teleport ra duoc -> truoc day member spam go_to_town vo tan, xem log party xGAx).
                if ((not c.running) or st["disc_gen"] > _dg0 or st["reconnecting"]
                        or getattr(c, "_td_incomplete", False)):
                    st["o5_broke"] = True
                    st["o5_need_redo"] = True   # team dungeon CHUA xong -> reconnect xong lam LAI
                st["o5_state"] = "done"   # bao member (thanh cong hay fail deu THA member ra)
                # do_team_dungeon_lv20 tu goi leave_party() (giai tan party de vao pho ban) - DAY LA
                # PARTY CHUNG voi party train, nhung KHONG co gi bao cho vong lap chinh biet can lap
                # lai -> truoc day member out het, leader chay ra bai TRAIN MOT MINH (khong reform).
                # Bump reform_gen -> co che reform co san (_do_reform, dung cho cac truong hop
                # "bi dump khoi dungeon" khac) se tu dong keo ca party tap hop + lap lai.
                st["reform_gen"] += 1
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
        run_account(username, password, pidx, is_leader, is_picker, is_reconnect=not first)
        first = False
        if _st() or not account_reconnect.get(username):
            break   # GUI Stop / thoat binh thuong / khong reconnectable -> dung han
        forced = username in account_forced_reconnect
        account_forced_reconnect.discard(username)
        forced_reason = account_forced_reconnect_reason.pop(username, None)
        pcfg = (getattr(config, "PARTY_CONFIG", {}).get(pidx, {}) or {})
        ev = (getattr(config, "EVENTS", {}) or {}).get(pcfg.get("event_key") or "")
        event_reset = (not forced and _is_party_event(
            pcfg.get("mode"), config.PARTY_LEADER_ACC.get(pidx) is not None, ev
        ) and st.get("event_battle_active", False))
        train_reform = (not forced and config.PARTY_LEADER_ACC.get(pidx) is not None
                        and _party_is_in_train_phase(pcfg, st))
        with st["lock"]:
            st["reconnecting"].add(username)
            if not forced:
                st["disc_gen"] += 1
            if train_reform:
                # Mot gen chung bat buoc ca survivors LAN acc vua login lai cung ve thanh,
                # sync kenh va lap party. Khong phu thuoc marker reconnect con ton tai bao lau.
                st["reform_gen"] += 1
            if event_reset:
                st["ready_members"].clear()
                st["invited"].clear()
                st["event_battle_done"].clear()
        if event_reset:
            reset_party_joined(pidx)
        attempt += 1
        wait = 1 if forced else (5 if attempt <= 3 else (30 if attempt <= 13 else 60))
        log.warning("[%s] RECONNECT: %s -> login lai sau %ds (lan %d)", username,
                    forced_reason or ("bat buoc relogin ca party" if forced else "server rot"),
                    wait, attempt)
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
    st["n_members"] = sum(1 for u, p, lead, _ in party_accounts(pidx) if not lead)
    # MODE digioi_train: party khoi dong LAI tu dau (chua acc nao chay) -> reset pha ve "digioi",
    # khong thi lan chay sau se bo qua DG (pha con ket o "train" tu phien truoc).
    if not _running_party_usernames(pidx):
        with st["lock"]:
            st["dt_phase"] = "digioi"
            st["dt_done"].clear()
            st["dt_train_prepared"] = False
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
                        auto_world_boss=True):
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
        "mode": mode, "start_city_id": int(start_city_id), "mob_index": int(mob_index),
        "city_flag": int(city_flag), "server": "", "server_ip": server_ip,
        "server_id": int(server_id), "do_daily": bool(do_daily),
        "claim_offline_exp": bool(claim_offline_exp),
        "auto_world_boss": bool(auto_world_boss),
        "auto_team_dungeon": bool(auto_team_dungeon),
        "team_dungeons": config.normalize_team_dungeons(team_dungeons),
        "digioi_mode": digioi_mode, "event_key": event_key or "",
        "use_phuc_than": bool(use_phuc_than), "use_digioi_ho_phu": bool(use_digioi_ho_phu),
        "fight_legion_boss": bool(fight_legion_boss),
        "do_van_tieu": bool(do_van_tieu),
        "auto_sell_noi_dat": bool(auto_sell_noi_dat),
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
    if len(_flat) >= 4 and len(_flat) % 4 == 0:
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


def party_idx_of(username):
    """pidx cua account (de map lenh thu cong username -> pidx). None neu khong biet."""
    return getattr(config, "ACCOUNT_PARTY", {}).get(username)


def start_party(pidx, stagger=1.5):
    """Khoi dong tat ca acc trong 1 party."""
    generation = _start_cancel_generation
    started = 0
    accounts = party_accounts(pidx)
    # Party da tat han -> tao session state MOI. Reset tung field nhu truoc de sot route_plan/
    # reform_gen cua map cu, member co the doc plan cu truoc khi leader ghi plan map moi.
    if not any(is_account_running(u) for u, *_ in accounts):
        _party_state.pop(pidx, None)
        reset_party_joined(pidx)
        for u, *_ in accounts:
            account_forced_reconnect.discard(u)
            account_forced_reconnect_reason.pop(u, None)
    st = _pstate(pidx)
    # RESET state dung chung (tranh sot tu lan chay truoc: leader_bad cu -> member quit oan)
    for k in ("leader_ok", "leader_bad", "leader_gone", "invited", "channel_ready",
              "stop_leader_done", "route_party_ready", "route_done", "rally_ready",
              "path_done"):
        st[k].clear()
    st["mob_spot"] = None
    st["rally_point"] = None
    st["mob_path"] = None
    st["channel"] = None
    with st["lock"]:
        st["ready_members"].clear()
        st["started_train"] = 0
        st["dungeon_done"] = 0
        st["dailies_done"] = 0       # barrier: so acc da xong daily quest login (cho leader cho)
        st["team_dungeon_done_by"] = {}
        st["team_dungeon_state"] = {}
        st["team_dungeon_broke"] = {}
        st["team_dungeon_need_redo"] = False
        st["team_dungeon_recover_seen"].clear()
        st["team_dungeon_recover_ready"].clear()
        st["map_results"] = {}       # reset barrier map cho lan chay nay
        st["summary_done"] = False   # cho phep log lai dong tong ket o lan chay nay
    for u, p, is_leader, is_picker in accounts:
        if generation != _start_cancel_generation:
            log.info(">>> PARTY %s: huy khoi dong cac acc con lai do STOP TAT CA", pidx + 1)
            break
        account_exit_reason.pop(u, None)   # xoa ly do cu
        if start_account(u, p, pidx, is_leader, is_picker):
            started += 1
            time.sleep(stagger)
    return started


def start_all():
    n = 0
    for pidx in range(len(config.PARTIES)):
        n += start_party(pidx)
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


def account_status(username):
    """Dict trang thai live cua acc (cho GUI). running, char, map, channel, in_party, dg_remain..."""
    c = account_clients.get(username)
    running = is_account_running(username)
    pidx = getattr(c, "party_idx", None) if c is not None else party_idx_of(username)
    party_avg_level = (_party_average_level(pidx)
                       if config.PARTY_LEADER_ACC.get(pidx) == username else None)
    if c is None:
        # da tat/thoat -> GIU map + nhan vat LUC CUOI (de biet thoat o dau, dung map khong)
        last = account_last.get(username, {})
        return {"running": running, "char": last.get("char", ""), "map": last.get("map"),
                "in_party": False, "dg_remain": None, "combat": False, "channel": None,
                "strategist": False, "char_level": last.get("char_level"),
                "char_agi": last.get("char_agi"),
                "pet_name": last.get("pet_name") or "", "pet_level": last.get("pet_level"),
                "pet_agi": last.get("pet_agi"),
                "party_avg_level": party_avg_level}
    from bot.client import is_joined, is_strategist
    st = _party_state.get(pidx, {})
    dg_remain = None
    if c.current_map == config.DIGIOI_MAP_ID:
        dg_remain = max(0, DIGIOI_LIMIT - getattr(c, "digioi_minutes", 0))
    account_last[username] = {"map": c.current_map, "char": c.char_name or "",
                              "char_level": getattr(c, "char_level", None),
                              "char_agi": getattr(c, "char_agi", None),
                              "pet_name": getattr(c, "pet_name", None),
                              "pet_level": getattr(c, "pet_level", None),
                              "pet_agi": getattr(c, "pet_agi", None)}  # luu lai luc cuoi
    _ch = getattr(getattr(c, "state", None), "char", None)   # hp/sp cho UI APK (PC GUI bo qua)
    return {
        "running": running,
        "char": c.char_name or "",
        "map": c.current_map,
        "channel": st.get("channel"),
        "in_party": is_joined(pidx, c.self_entity),
        "dg_remain": dg_remain,
        "combat": c.in_combat() if running else False,
        "strategist": is_strategist(pidx, c.self_entity),
        "char_level": getattr(c, "char_level", None),
        "char_agi": getattr(c, "char_agi", None),
        "pet_name": getattr(c, "pet_name", None) or "",
        "pet_level": getattr(c, "pet_level", None),
        "pet_agi": getattr(c, "pet_agi", None),
        "party_avg_level": party_avg_level,
        # --- them cho UI APK (poll qua account_status thay callback on_status) ---
        "state": "running" if running else "stopped",
        "hp": getattr(_ch, "hp", None), "sp": getattr(_ch, "sp", None),
        "hp_max": getattr(_ch, "hp_max", None), "sp_max": getattr(_ch, "sp_max", None),
    }


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
        rows.append({
            "username": username,
            "char": status.get("char") or username,
            "char_agi": char_agi,
            "pet": status.get("pet_name") or "",
            "pet_agi": pet_agi,
        })
    low = min(values) if values else None
    high = max(values) if values else None
    spread = high - low if low is not None else None
    return {"rows": rows, "min": low, "max": high, "spread": spread,
            "warning": spread is not None and spread > 10}


def account_skills(username):
    """GUI/API: tra skill live cua acc dang online de render dropdown cau hinh battle."""
    def _skill_choice(sid):
        sid = int(sid)
        info = getattr(config, "SKILL_INFO", {}).get(sid, {}) or {}
        return [sid, info.get("name") or ("Skill %d" % sid), info.get("cost"), info.get("cat")]

    c = account_clients.get(username)
    st = c.state if (c is not None and getattr(c, "state", None)) else None
    if st is None:
        return {"char": [], "pet": []}
    pet_skills = list(getattr(st, "pet_skills", []) or [])
    if not pet_skills:
        pet_skills = list(getattr(st, "skills_pet", []) or [])
    return {
        "char": [_skill_choice(s) for s in sorted(list(getattr(st, "skills_char", []) or []))],
        "pet": [_skill_choice(s) for s in sorted(set(pet_skills))],
    }


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
    if username in account_clients:
        log.info("[%s] da apply nguong hoi HP/SP moi (live): %s", username, cfg or "mac dinh")
    return True


def get_account_log(username, max_lines=500):
    """ANDROID: doc party.log -> loc rieng cac dong cua 1 acc, cho UI hien "log cua acc nay".
    QUAN TRONG: nhan log trong client.py (self._label) DOI TU username SANG TEN NHAN VAT ngay
    khi server tra ve (vd 'taot11' -> 'ttmot') - loc CHI theo username se BO SOT toan bo log
    sau thoi diem do (bug that: user thay log "dung lai" ngay sau dong "Ten nhan vat = ...").
    Loc theo CA username LAN char_name hien tai (qua account_status) de khong bo sot."""
    try:
        char_name = (account_status(username) or {}).get("char") or ""
        tags = ["[%s]" % username]
        if char_name and char_name != username:
            tags.append("[%s]" % char_name)
        if not os.path.exists(_log_path):
            return "(chua co log - acc chua chay lan nao tren may nay)"
        with open(_log_path, encoding="utf-8", errors="replace") as f:
            lines = [ln.rstrip("\n") for ln in f if any(t in ln for t in tags)]
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
