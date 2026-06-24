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
from bot.login import login
from bot.client import GameClient, check_duplicate_accounts

_lvl = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
logging.basicConfig(level=_lvl, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[logging.FileHandler("party.log", "w", "utf-8"), logging.StreamHandler()])
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


def _party_map_barrier(st, username, self_ok, expected, stopped, timeout=70):
    """BARRIER cap party: moi acc bao 'minh co o train map khong', cho ca party quyet dinh.
    Tra True neu MOI acc bao cao deu o train map; False neu CO >=1 acc sai map
    (-> ca party ve thanh don nhau). Thoat som khi da co dua sai map hoac du bao cao."""
    with st["lock"]:
        st["map_results"][username] = bool(self_ok)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if stopped():
            break
        with st["lock"]:
            done = len(st["map_results"]) >= expected
            any_bad = not all(st["map_results"].values())
        if done or any_bad:
            break
        time.sleep(1)
    with st["lock"]:
        return all(st["map_results"].values())


def _pstate(pidx):
    if pidx not in _party_state:
        _party_state[pidx] = {"channel": None,
                              "channel_ready": threading.Event(),
                              "invited": threading.Event(),
                              "lock": threading.Lock(),
                              "ready_members": set(),   # member da vao DG + dung kenh leader
                              "n_members": 0,            # tong so member can cho
                              "started_train": 0,        # so acc da qua check map -> vao train (de barrier dungeon)
                              "dungeon_done": 0,         # so acc da danh xong dungeon (barrier)
                              "dailies_done": 0,         # so acc da xong daily login (barrier cho leader)
                              "leader_ok": threading.Event(),   # leader DUNG map train -> tiep tuc
                              "leader_bad": threading.Event(),  # leader SAI map -> huy ca party
                              "leader_gone": threading.Event(),  # leader da THOAT -> member ngung retry vao party
                              "stop_leader_done": threading.Event(),  # STOP: leader DA ve safe -> member duoc thoat
                              "route_party_ready": threading.Event(),  # ROUTE: party da lap xong o thanh -> sap keo di
                              "route_done": threading.Event(),         # ROUTE: leader da keo xong (toi train map)
                              "map_results": {},     # ROUTE barrier: username -> dang o train map? (de quyet dinh ca party)
                              "mob_spot": None,      # diem quai leader chon (de _start_training dung lai)
                              "rally_point": None,   # safe GAN diem quai nhat -> CA PARTY ve day (gan leader)
                              "rally_ready": threading.Event(),  # leader da chon diem quai + rally_point
                              "path_done": threading.Event(),    # leader da di xong follow_path toi diem quai (member bi keo theo)
                              "reform_gen": 0,       # +1 moi khi co acc van map (chet) -> CA party reform tai cho
                              "cmd_gen": 0,          # +1 moi khi GUI ra lenh thu cong (doi kenh/teleport thanh)
                              "cmd": None,           # ("channel", ch) | ("city", city_id, flag)
                              "summary_done": False}  # da log dong tong ket "party thoat het" chua
    return _party_state[pidx]


def run_account(username, password, pidx, is_leader, is_picker=False):
    label = username
    role = "LEADER" if is_leader else "member"
    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    st = _pstate(pidx)
    stop_ev = account_stops.get(username)   # GUI yeu cau STOP -> thoat moi giai doan
    def _stopped():
        return stop_ev is not None and stop_ev.is_set()
    er = {"r": "ket thuc binh thuong (het gio hoac GUI dung)"}  # ly do thoat (de tong ket party)
    def _reason(msg):
        er["r"] = msg
    # Server (IP) theo config rieng cua party
    _pc0 = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
    server_ip = _pc0.get("server_ip") or config.GAME_HOST
    server_name = _pc0.get("server", "?")
    server_id = _pc0.get("server_id", 1)
    try:
        # --- Login + cho vao world THUC SU (co self_entity VA co current_map) ---
        c = None
        for attempt in range(6):
            if _stopped():
                log.info("[%s] STOP truoc khi login xong", label); return
            cred = login(username, password)
            c = GameClient(cred["user_id"], cred["access_token"], host=server_ip, server_id=server_id)
            c._label = label; c._username = username
            log.info("[%s] server=%s (%s) id=%s", label, server_name, server_ip, server_id)
            c.party_idx = pidx
            c.submit_delay = 0.3
            c.connect()
            # cho self_entity + map (map=None = chua vao world xong)
            ok = False
            for _ in range(15):
                if c.self_entity is not None and c.current_map is not None:
                    ok = True; break
                time.sleep(1)
            if ok:
                break
            log.warning("[%s] chua vao world (entity=%s map=%s) -> login lai...",
                        label, c.self_entity is not None, c.current_map)
            c.close(); time.sleep(5)
        if not ok:
            _reason("login/vao world that bai (6 lan)")
            log.warning("[%s] >>> THOAT: LOGIN/VAO WORLD THAT BAI sau 6 lan "
                        "(entity=%s map=%s) <<<", label, c.self_entity is not None, c.current_map)
            try: c.close()
            except Exception: pass
            return
        _clients.append(c)
        account_clients[username] = c     # GUI doc trang thai
        label = c.char_name or username   # log theo TEN NHAN VAT (neu da resolve), fallback username
        login_map = c.current_map         # map LUC LOGIN (doc som, it bi pollution) - dung de check train
        log.info("[%s] (%s) vao world.", label, role)
        log.info("[%s] >>> MAP HIEN TAI = %s <<<  (dung ID nay de setup START_CITY_ID/TRAIN)",
                 label, login_map)
        c.log_bag_delayed()   # In tui khi snapshot ve + on dinh (adaptive, toi da 8s) -> dinh danh item
        # MAP-TRAIN: bat flee NGAY tu login -> moi tran (truoc khi lap party) deu BO CHAY,
        # khong danh lung tung; chi tat flee khi da vao diem train.
        if config.TRAIN_MAPS.get(getattr(config, "START_CITY_ID", 0)) is not None:
            c.flee_mode = True
        c.request_offline_exp() # NHAN EXP OFFLINE (treo may) - tu nhan neu co
        c.claim_mail()          # nhan qua mail + xoa mail da doc (qua bao tri,...)
        c.claim_checkin()       # diem danh hang ngay (tu dem so lan)
        c.claim_14day_gift()    # qua 14 ngay user moi (0x57)
        c.claim_event_14day()   # event tang qua 14 ngay (0x7c) - khac cai tren
        c.claim_legion_gift()   # nhan qua quan doan hang ngay
        c.claim_friend_gifts()  # tang qua tat ca ban + nhan qua ban tang (hang ngay)
        c.decompose_junk_scrolls()  # phan giai cuon goi pet RAC (junk_scrolls.json) -> nhan xu
        next_vantieu = c.do_van_tieu()   # van tieu: nhan qua xong + gui pet; tra ve gio check tiep

        # MODE theo CONFIG RIENG cua party (PARTY_CONFIG[pidx]). Fallback: suy tu START_CITY_ID.
        pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
        sc = pcfg.get("start_city_id", getattr(config, "START_CITY_ID", 0))
        mob_index = pcfg.get("mob_index", 0)
        city_flag = pcfg.get("city_flag", 0)
        # checkbox "Lam nhiem vu hang ngay" (bingo 9 o + dungeon). Fallback key cu "do_dungeon".
        do_daily = pcfg.get("do_daily", pcfg.get("do_dungeon", True))
        tm = config.TRAIN_MAPS.get(sc)          # dict {safe, mobs} neu la map train
        # mode: digioi | train | city (tap trung ve thanh) | stand (dung yen) | cleanbag
        mode = pcfg.get("mode")
        if not mode:
            mode = ("train" if tm else ("digioi" if sc == config.DIGIOI_MAP_ID
                    else ("stand" if sc == 0 else "city")))
        train_on_map = (mode == "train") and (tm is not None)
        is_digioi = (mode == "digioi")
        log.info("[%s] (%s) MODE=%s start_city=%s", label, role, mode, sc)

        # NHIEM VU BINGO (mode KHAC digioi): VE CHO AN TOAN TRUOC roi moi lam dailies (tranh dung
        # giua o quai lam dailies; world boss tu teleport di roi ve Trac Quan; mode positioning ben
        # duoi se dua ve dung cho). Mode DIGIOI lam rieng (vao DG truoc - xem nhanh ben duoi).
        if not is_digioi and do_daily:
            if mode == "city":
                try: c.go_to_town(sc, city_flag)                       # ve thanh config
                except Exception: pass
            elif train_on_map:
                if login_map == sc and tm and tm.get("safe"):
                    c.navigate_to(*_nearest_safe(c.pos, tm["safe"]))   # dang o bai -> ra diem safe
                else:
                    try: c.teleport(12001, 0)                          # sai map -> ve Trac Quan (route keo ra sau)
                    except Exception: pass
            elif mode == "stand" and tm and tm.get("safe") and login_map == sc:
                c.navigate_to(*_nearest_safe(c.pos, tm["safe"]))       # stand map co safe -> ra safe
            # stand map la / khong co safe -> lam dailies tai cho (ke me)
            c.claim_daily_quests()

        # BARRIER login-dailies (mode KHAC digioi): CHO CA PARTY xong daily quest (world boss cham
        # + teleport ve Trac Quan) TRUOC khi sync kenh + lap party. Tranh leader sync kenh/moi khi
        # member dang lam daily -> member sai kenh / leader train 1 minh. (digioi: heavy hoan toi
        # cuoi DG nen khong can.)
        if not is_digioi:
            with st["lock"]:
                st["dailies_done"] += 1
            expected = len(party_accounts(pidx))
            t0 = time.time()
            while time.time() - t0 < 300:   # cho toi 5p (world boss event ~2-3p)
                if _stopped() or not c.running:
                    break
                with st["lock"]:
                    if st["dailies_done"] >= expected:
                        break
                time.sleep(1)
            log.info("[%s] (%s) xong daily login (%d/%d acc) -> sync kenh + lap party",
                     label, role, st["dailies_done"], expected)

        # Dong bo kenh: 1 dua (picker) chon kenh it nguoi -> ca lu sang cung.
        # DG: phai goi TRUOC khi vao DG (doi kenh trong DG se DA ra khoi DG!).
        # Map-train: goi sau khi ve safe (doi kenh tren map thuong khong sao).
        def do_channel_sync():
            if is_picker:
                # MOI VONG SYNC: clear channel_ready + channel cu -> member CHO pick MOI (tranh dung
                # kenh cu vong truoc). channel_ready chi clear o start_party -> vong 2+ member ko cho
                # -> kenh ko sync lai. Clear o day de moi vong deu re-sync that su.
                st["channel_ready"].clear()
                st["channel"] = None
                # need = so acc cua party -> chi chon kenh con DU CHO cho CA PARTY (tranh ket instance).
                # pick tra: 0=chi 1 kenh (giu nguyen) | None=co kenh nhung khong du cho (RETRY) | int=da chuyen.
                # KIEN TRI: 30s dau thu lien tuc (3s/lan), sau do 60s/lan, cho toi khi gom du ve 1 kenh.
                need = len(party_accounts(pidx))
                t0 = time.time()
                ch = 0
                while c.running and not _stopped():
                    r = c.pick_best_channel(need=need)
                    if r is None:   # co kenh nhung khong kenh nao du cho ca party -> CHO kenh trong
                        if time.time() - t0 <= 30:
                            time.sleep(3)          # 30s dau: thu lien tuc
                        else:
                            log.info("[%s] (%s) chua co kenh du cho ca party (%d acc) -> cho 60s thu lai...",
                                     label, role, need)
                            time.sleep(60)         # sau do: 1 phut/lan
                        continue
                    ch = r          # 0 (giu nguyen) hoac int (da chuyen) -> chot
                    break
                st["channel"] = ch
                st["channel_ready"].set()
                if ch:
                    log.info("[%s] (%s) chon kenh %s cho ca party (%d acc)", label, role, ch, need)
                else:
                    log.info("[%s] (%s) ca party giu nguyen 1 kenh (khong tach)", label, role)
            else:
                # cho picker CHOT kenh (co the lau neu dang doi kenh trong) -> cho toi khi ready/stop
                while not st["channel_ready"].wait(5):
                    if not c.running or _stopped():
                        return
                ch = st["channel"]
                if ch:
                    c.switch_channel(ch)
                    log.info("[%s] (member) chuyen sang kenh chung = %s", label, ch)
                time.sleep(2)

        via_route = False   # True neu toi train map bang KEO PARTY -> da cung kenh + da danh dungeon o thanh
        if train_on_map:
            # PHAI dung map login (toa do safe/mobs chi dung tren map do).
            self_map_ok = (login_map == sc)
            def _quit():
                # member thoat -> giam n_members de leader khong cho phantom member (treo 180s)
                if not is_leader:
                    with st["lock"]:
                        st["n_members"] = max(0, st["n_members"] - 1)
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
            # lap party du, roi LEADER KEO ca party toi train map (member tu theo). Theo train_routes.json.
            route = getattr(config, "TRAIN_ROUTES", {}).get(sc)
            if route and has_leader:
                expected = len(party_accounts(pidx))
                all_on_map = _party_map_barrier(st, username, self_map_ok, expected, _stopped)
                if not all_on_map:
                    fc = int(route.get("from_city", 0)); ff = int(route.get("city_flag", 0))
                    log.info("[%s] (%s) PARTY co acc sai map -> CA PARTY ve thanh %s don nhau roi KEO toi %s",
                             label, role, fc, sc)
                    c.flee_mode = True
                    if fc and c.go_to_town(fc, ff):
                        # DANH DUNGEON NGAY TAI THANH (solo, khong can party) -> khoi phai keo
                        # toi bai roi moi pha party danh dungeon roi gom lai. Dungeon co the dump
                        # ve 12000 -> teleport ve thanh lai roi moi gom party.
                        if do_daily:
                            try:
                                c.do_daily_dungeon()
                            except Exception as e:
                                log.warning("[%s] loi dungeon (route, bo qua): %s", label, e)
                            if c.current_map != fc:
                                log.info("[%s] (%s) sau dungeon o map %s -> teleport ve thanh %s lai",
                                         label, role, c.current_map, fc)
                                c.go_to_town(fc, ff)
                        do_channel_sync()   # dong bo kenh TAI THANH (de moi/keo duoc)
                        from bot.client import joined_member_count
                        if is_leader:
                            # 1) cho member ve thanh + san sang (member danh dungeon truoc -> cho lau hon)
                            for _ in range(180):   # ~360s du cho member xong dungeon
                                if _stopped(): break
                                if len(st["ready_members"]) >= st["n_members"]: break
                                time.sleep(2)
                            # 2) moi + cho join + set quan su (LAP PARTY TAI THANH)
                            for _ in range(6):
                                if _stopped(): break
                                c.invite_members(gap=1.0); time.sleep(4)
                                if joined_member_count(pidx) >= st["n_members"]: break
                            try: c.set_party_strategist()
                            except Exception: pass
                            log.info("[%s] (LEADER) party lap xong tai thanh (%d member) -> bat dau KEO",
                                     label, joined_member_count(pidx))
                            st["route_party_ready"].set()
                            time.sleep(1.5)
                            # DU PARTY -> DANH bat chap khi keo (flee party-battle hay treo). Chua du
                            # -> flee cho an toan. (member cung set tuong tu o nhanh duoi.)
                            _full = st.get("n_members", 0) > 0 and joined_member_count(pidx) >= st["n_members"]
                            c.flee_mode = not _full
                            # 3) KEO DI: leader di qua cac cong/buoc; member tu theo.
                            #    DANG DANH -> DUNG DI CHUYEN, cho HET TRAN roi moi di buoc/qua cong
                            #    (di giua tran lam ket cong / pha luot danh).
                            for stp in route.get("steps", []):
                                if _stopped(): break
                                # _enter_gate / _route_move TU cho het tran truoc khi move/transit
                                # (battle nuot lenh 0x06/0x14 -> nhan vat khong toi cong -> ket / kick).
                                if "gate" in stp:
                                    if not c._enter_gate(int(stp["x"]), int(stp["y"]), int(stp["gate"])):
                                        break
                                else:
                                    c._route_move(int(stp["move"][0]), int(stp["move"][1]))
                            st["route_done"].set()
                            if c.current_map == sc:
                                self_map_ok = True; login_map = sc
                                via_route = True
                                log.info("[%s] (LEADER) da KEO party toi train map %s", label, sc)
                        else:
                            # member: bao san sang o thanh; auto-accept loi moi; roi CHO bi keo toi train map
                            with st["lock"]: st["ready_members"].add(username)
                            # cho leader gom du party (member khac con dungeon); THOAT SOM neu STOP
                            t0 = time.time()
                            while not st["route_party_ready"].is_set() and time.time() - t0 < 360:
                                if _stopped() or not c.running:
                                    break
                                time.sleep(2)
                            # party lap xong (route_party_ready) -> DU party thi DANH bat chap khi bi
                            # keo (giong leader), chua du thi flee. (flee party-battle hay treo.)
                            _full = st.get("n_members", 0) > 0 and joined_member_count(pidx) >= st["n_members"]
                            c.flee_mode = not _full
                            t0 = time.time()
                            while not st["route_done"].is_set() and time.time() - t0 < 240:
                                if _stopped(): break
                                time.sleep(2)
                            for _ in range(15):   # cho map cap nhat sau khi bi keo
                                if c.current_map == sc or _stopped(): break
                                time.sleep(1)
                            if c.current_map == sc:
                                self_map_ok = True; login_map = sc; via_route = True
                                log.info("[%s] (member) da bi KEO toi train map %s", label, sc)
                    # reset ready_members de flow train ben duoi dung lai tu dau
                    with st["lock"]: st["ready_members"].discard(username)
            if is_leader:
                if not self_map_ok and not c.running:
                    # LEADER MAT KET NOI (vd disconnect giua route) -> KHONG phai "sai map".
                    _reason("leader MAT KET NOI khi dang route toi train map (map cuoi %s)" % c.current_map)
                    log.warning("[%s] (LEADER) MAT KET NOI khi dang di chuyen toi train map %s "
                                "-> ca party thoat.", label, sc)
                    st["leader_bad"].set()
                    try: c.close()
                    except Exception: pass
                    if c in _clients: _clients.remove(c)
                    return
                if not self_map_ok:
                    # LEADER sai map + khong route/route loi -> HUY ca party (bao member thoat het)
                    _reason("leader dung SAI MAP (o %s, can train map %s) - khong route hoac route loi"
                            % (c.current_map, sc))
                    log.warning("[%s] (LEADER) NHAN VAT DANG DUNG O MAP %s, NHUNG CONFIG TRAIN MAP=%s "
                                "-> KHONG khop -> lam dungeon roi HUY CA PARTY (member thoat het). "
                                "CACH SUA: vao game dua nhan vat ve map %s roi THOAT GAME tai do, "
                                "HOAC doi train map cua party sang %s trong GUI.",
                                label, c.current_map, sc, sc, c.current_map)
                    st["leader_bad"].set()
                    _daily_then_quit(); return
                st["leader_ok"].set()   # leader ok -> member duoc tiep tuc
            else:
                if not self_map_ok and not c.running:
                    _reason("member MAT KET NOI khi dang route (map cuoi %s)" % c.current_map)
                    log.warning("[%s] (member) MAT KET NOI khi dang di chuyen toi train map -> thoat.", label)
                    _quit(); return
                if not self_map_ok:
                    _reason("member dung SAI MAP (o %s, can train map %s)" % (c.current_map, sc))
                    log.warning("[%s] (member) NHAN VAT DANG DUNG O MAP %s, NHUNG CONFIG TRAIN MAP=%s "
                                "-> KHONG khop -> lam dungeon roi THOAT. "
                                "CACH SUA: dua nhan vat ve map %s roi THOAT GAME tai do.",
                                label, c.current_map, sc, sc)
                    _daily_then_quit(); return
                # CO bot-leader -> doi leader quyet dinh (ok/huy). KHONG co leader -> tu di tiep.
                if has_leader:
                    t0 = time.time()
                    while not (st["leader_ok"].is_set() or st["leader_bad"].is_set()):
                        if _stopped(): _quit(); return
                        if time.time() - t0 > 150:
                            log.warning("[%s] (member) khong thay leader quyet dinh -> THOAT", label)
                            _quit(); return
                        time.sleep(0.5)
                    if st["leader_bad"].is_set():
                        _reason("leader party loi (sai map hoac mat ket noi) -> ca party bi huy")
                        log.warning("[%s] (member) LEADER party LOI (sai map / mat ket noi - xem dong "
                                    "LEADER o tren) -> ca party huy -> THOAT.", label)
                        _quit(); return
            # --- MAP-TRAIN: CA PARTY ve cung 1 SAFE = safe GAN diem quai leader chon (de gan nhau
            #     -> member vao tran chung voi leader). Leader chon diem quai SOM + bao rally_point. ---
            mobs = tm["mobs"]
            if is_leader:
                if mob_index < 0 and mobs:
                    import random
                    spot = random.choice(mobs)
                else:
                    spot = mobs[mob_index] if (mobs and 0 <= mob_index < len(mobs)) else (mobs[0] if mobs else None)
                st["mob_spot"] = spot
                # CO PATH capture (diem quai XA) -> sau khi lap party leader follow_path keo ca party
                # ra spot; KHONG path -> navigate thang. DU CO PATH HAY KHONG, rally LUON la SAFE gan
                # spot (tap trung + lap party o day TRUOC), KHONG phai spot (truoc set =spot -> ca party
                # navigate thang ra spot luc chua co party -> vo ich, roi lai quay ve safe).
                path = getattr(config, "MOB_PATHS", {}).get(sc, {}).get(tuple(spot)) if spot else None
                st["mob_path"] = path
                st["rally_point"] = (_nearest_safe(spot, tm["safe"]) if spot else tm["safe"][0])
                st["rally_ready"].set()
            # member: cho leader chon (rally_point/path); khong co leader -> safe[0]
            if has_leader and not is_leader:
                st["rally_ready"].wait(60)
            # MAP-TRAIN: CA party (leader+member) ve RALLY = safe GAN spot TRUOC. KHONG follow_path
            # ngay luc nay - vi party CHUA lap (member chua join) -> keo cung vo ich (member khong bi
            # keo theo, leader chay ra spot 1 minh roi quay ve). Sau khi LAP PARTY xong, _start_training
            # moi cho leader follow_path KEO CA PARTY (da join, dang o rally) ra spot.
            rally = st.get("rally_point") or tm["safe"][0]
            log.info("[%s] (%s) MAP-TRAIN map=%s -> ve safe tap ket chung %s (lap party TRUOC, keo ra spot SAU)",
                     label, role, sc, rally)
            c.navigate_to(*_jitter(rally))
            # SOLO daily dungeon o MAP-TRAIN: TAM TAT (het luot -> bi dump ve 12000, pha map-train;
            # Bat/tat bang checkbox "Danh daily dungeon" cua party (do_daily).
            # via_route -> da danh dungeon o thanh roi, BO QUA (khoi pha map-train + cho barrier).
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
                    c.navigate_to(*_jitter(tm["safe"][0]))
                    with st["lock"]:
                        st["dungeon_done"] += 1
                log.info("[%s] (%s) xong dungeon -> cho ca party (%d/%d)...",
                         label, role, st["dungeon_done"], st["started_train"])
                t0 = time.time()
                while time.time() - t0 < 300:
                    if _stopped(): _quit(); return
                    with st["lock"]:
                        if st["started_train"] > 0 and st["dungeon_done"] >= st["started_train"]:
                            break
                    time.sleep(1)
                log.info("[%s] (%s) ca party xong dungeon", label, role)
            if not via_route:   # via_route -> ca party da cung kenh (di theo) -> khoi sync lai
                do_channel_sync()   # map-train: dong bo kenh sau khi ve safe (tren map thuong)
        elif is_digioi:
            # --- DI GIOI ---
            # 0) PRE-CHECK: doc so phut DG hom nay tu BANG STAT login (0x55 id=0x1b).
            #    Da du gio (>= DIGIOI_LIMIT) -> KHOI vao (truoc day phai vao -> cho 150s moi biet).
            if not c.in_di_gioi() and c.digioi_minutes >= DIGIOI_LIMIT:
                log.info("[%s] (%s) DG da HET GIO hom nay (%d/%d phut, doc tu login) -> khong vao",
                         label, role, c.digioi_minutes, DIGIOI_LIMIT)
                _reason("het gio Di Gioi hom nay (doc tu login)")
                # HET GIO DG -> BAY VE THANH (Trac Quan) TRUOC: login co the o map quai (12831...) ->
                # ket tran lien tuc -> teleport boss/dungeon luc dang danh bi server KICK. Ve thanh
                # an toan roi moi lam dailies.
                _go_town_safe(c, label)
                if do_daily:
                    try: c.do_daily_dungeon()
                    except Exception as e:
                        log.warning("[%s] loi daily dungeon (bo qua): %s", label, e)
                # khong vao DG -> lam FULL nhiem vu (nhe + boss) tai cho roi dong
                if do_daily:
                    try: c.claim_daily_quests(heavy=True)
                    except Exception as e:
                        log.warning("[%s] loi claim daily quest (bo qua): %s", label, e)
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
                return
            # 1) PHAI VAO DUOC DG TRUOC (xac nhan in_di_gioi) roi MOI chuyen kenh.
            if not c.in_di_gioi() and not c.enter_di_gioi_safe():
                log.warning("[%s] (%s) khong vao duoc DG (het gio?) -> TAT acc nay", label, role)
                _go_town_safe(c, label)   # ve thanh truoc (thoat o quai) roi lam dailies
                if do_daily:
                    try: c.claim_daily_quests(heavy=True)   # khong vao DG -> lam full quest roi dong
                    except Exception as e:
                        log.warning("[%s] loi claim daily quest (bo qua): %s", label, e)
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
            do_channel_sync()
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
                try: c.go_to_town(sc, city_flag)
                except Exception as e:
                    log.warning("[%s] loi ve thanh: %s", label, e)
            elif mode == "cleanbag":
                log.info("[%s] (%s) DON TUI DO - chua lam, tam dung yen", label, role)
            else:
                log.info("[%s] (%s) DUNG YEN tai cho login (map=%s)", label, role, c.current_map)
            c.flee_mode = False   # bi danh thi tu danh, KHONG chay
            do_channel_sync()

        if not is_leader:
            with st["lock"]:
                st["ready_members"].add(username)
        time.sleep(2)

        # --- Leader: CHO du member san sang roi MOI, roi CAY ---
        if is_leader:
            from bot.client import joined_member_count
            if via_route:
                # toi train map THEO PARTY (da lap party + cung kenh o thanh) -> KHOI moi lai
                st["invited"].set()   # bao member khoi cho moi
                log.info("[%s] (LEADER) toi train map theo party (da partied) -> bo qua moi lai", label)
            else:
                for _ in range(90):   # ~180s: du cho member xong dungeon + ve diem tap ket
                    if _stopped(): st["stop_leader_done"].set(); c.close(); return
                    if len(st["ready_members"]) >= st["n_members"]:
                        break
                    time.sleep(2)
                log.info("[%s] (LEADER) %d/%d member san sang -> MOI (theo entity)",
                         label, len(st["ready_members"]), st["n_members"])
                for r in range(6):
                    if _stopped(): st["stop_leader_done"].set(); c.close(); return
                    c.invite_members(gap=1.0)
                    st["invited"].set()
                    time.sleep(4)
                    njoined = joined_member_count(pidx)
                    log.info("[%s] (LEADER) sau moi lan %d: joined=%d/%d",
                             label, r + 1, njoined, st["n_members"])
                    if njoined >= st["n_members"]:
                        log.info("[%s] (LEADER) DU PARTY (%d member join)", label, njoined)
                        break
                    time.sleep(2)
                else:
                    log.warning("[%s] (LEADER) chua du member (%d/%d)",
                                label, joined_member_count(pidx), st["n_members"])
            # Bat dau train (set QS + ra cho danh). Goi khi DA co >=1 member (du quan su).
            training_started = False
            def _start_training():
                c.set_party_strategist()    # set member INT cao nhat lam quan su (hoi SP)
                if train_on_map:
                    # diem quai DA chon som (st["mob_spot"]) - ca party da ve safe GAN diem do roi,
                    # va DA LAP PARTY xong (goi tu day) -> gio moi keo ca party ra spot:
                    #   - CO mob_path: leader follow_path KEO ca party (da join, dang o rally) ra spot.
                    #     flee=False de gap quai danh luon (party da du, flee party-battle bi treo).
                    #   - khong path: navigate thang ra spot.
                    spot = st.get("mob_spot")
                    if not spot and tm["mobs"]:
                        import random
                        spot = random.choice(tm["mobs"])
                    path = st.get("mob_path")
                    if path:
                        log.info("[%s] (LEADER) party da lap -> follow_path KEO ca party ra spot (%d buoc)",
                                 label, len(path))
                        c.follow_path(path, flee=False)   # party da du -> danh quai gap tren duong
                    elif spot:
                        c.navigate_to(*_jitter(spot))
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
            if joined_member_count(pidx) >= 1:
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
                st["invited"].wait(120)   # cho bot-leader moi
            # DA vao party -> NGUNG flee, DANH tran chung (ca map-train LAN Di Gioi).
            # FLEE trong tran party bi server KICK (vd Tao Thao: member flee -> dis ngay).
            c.flee_mode = False
            if train_on_map:
                c.combat_ready()   # map thuong: combat-active de quai aggro (DG khong can)
            if has_leader:
                log.info("[%s] (member) da vao party - dung yen tai safe, tu danh", label)
            else:
                log.info("[%s] (member) KHONG co bot-leader -> dung yen tai safe (kenh %s), "
                         "auto-accept - CHO ban moi party tay", label, st.get("channel"))

        # --- Giu song ---
        from bot.client import joined_member_count, is_joined, reset_party_joined
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
        reform_gen_handled = 0      # gen reform da xu ly. Init=0 (KHONG = st["reform_gen"]) de neu
        # co acc bi DUMP luc setup (da bump reform_gen) thi keepalive thay ngay -> reform don no
        cmd_gen_handled = st["cmd_gen"]   # lenh thu cong (GUI) da xu ly

        def _do_reform():
            """CA party REFORM tai cho khi co acc van map (chet). Ve thanh gom nhau -> leader GIAI
            TAN party cu + lap lai + KEO ca party ra train map/spot (member bi keo theo). Member:
            ve thanh, switch dung kenh, auto-accept loi moi roi bi keo theo. Giu nguyen thread."""
            route2 = getattr(config, "TRAIN_ROUTES", {}).get(sc)
            if not route2:
                log.warning("[%s] (%s) reform: khong co route -> bo qua", label, role)
                return
            fc = int(route2.get("from_city", 0)); ff = int(route2.get("city_flag", 0))
            spot = st.get("mob_spot")
            c.flee_mode = True
            if is_leader:
                st["route_party_ready"].clear(); st["route_done"].clear()  # reset handshake cho lan reform nay
                c.leave_party()                  # GIAI TAN party cu -> member duoc tha khoi party cu
                reset_party_joined(pidx)
            if fc:
                try: c.go_to_town(fc, ff)        # CA party (leader+member) tu teleport ve thanh gom nhau
                except Exception as e: log.warning("[%s] reform: loi ve thanh: %s", label, e)
            ch = st.get("channel")               # ve cung kenh da chon (khong re-pick, tranh tach)
            if ch:
                try: c.switch_channel(ch); time.sleep(1)
                except Exception: pass
            if is_leader:
                # LAP LAI party TAI THANH (member da tu do sau giai tan + dang o thanh) -> moi + cho join
                for _ in range(8):
                    if not c.running or _stopped(): return
                    try: c.invite_members(gap=1.0)
                    except Exception: pass
                    time.sleep(4)
                    if joined_member_count(pidx) >= st["n_members"]:
                        break
                log.info("[%s] (LEADER) reform: %d/%d member join lai -> KEO qua cong ra spot",
                         label, joined_member_count(pidx), st["n_members"])
                try: c.set_party_strategist()
                except Exception: pass
                st["route_party_ready"].set()    # bao member: party lap xong, sap keo
                time.sleep(1.5)
                _full = st.get("n_members", 0) > 0 and joined_member_count(pidx) >= st["n_members"]
                c.flee_mode = not _full   # du party -> DANH bat chap khi keo
                # KEO DI THU CONG qua tung cong/buoc (GIONG startup via_route) -> member TRONG PARTY
                # tu theo leader KE CA QUA CONG. KHONG dung follow_route (no tu teleport -> khong keo).
                for stp in route2.get("steps", []):
                    if not c.running or _stopped(): break
                    t1 = time.time()   # DANG DANH -> cho HET TRAN roi moi di buoc/qua cong
                    while c.in_combat(idle_secs=3.0) and c.running and not _stopped() \
                            and time.time() - t1 < 60:
                        time.sleep(0.5)
                    if "gate" in stp:
                        if not c._enter_gate(int(stp["x"]), int(stp["y"]), int(stp["gate"])):
                            break
                    else:
                        c.move_to(int(stp["move"][0]), int(stp["move"][1])); time.sleep(0.5)
                # toi train map -> keo tiep ra spot (di bo local, member van theo)
                if c.current_map == sc:
                    path = st.get("mob_path")
                    if path:
                        c.follow_path(path, flee=False)
                    elif spot:
                        c.navigate_to(*_jitter(spot))
                c.combat_ready(); c.flee_mode = False
                st["route_done"].set()
            else:
                # member: cho leader bao party lap xong (route_party_ready) -> roi cho keo xong (route_done).
                # Dang trong party nen tu bi keo qua cong theo leader (giong startup via_route).
                t0 = time.time()
                while not st["route_party_ready"].is_set() and time.time() - t0 < 120:
                    if not c.running or _stopped(): return
                    time.sleep(2)
                _full = st.get("n_members", 0) > 0 and joined_member_count(pidx) >= st["n_members"]
                c.flee_mode = not _full   # du party -> DANH bat chap khi bi keo
                t0 = time.time()
                while not st["route_done"].is_set() and time.time() - t0 < 240:
                    if not c.running or _stopped(): return
                    time.sleep(2)
                for _ in range(15):                # cho map cap nhat sau khi bi keo
                    if c.current_map == sc or _stopped(): break
                    time.sleep(1)
                c.combat_ready(); c.flee_mode = False

        def _do_manual_cmd(cmd):
            """Thuc thi LENH THU CONG tu GUI (doi kenh / teleport thanh) -> roi TIEP TUC che do da
            setup. Huy party cu truoc, lam hanh dong, roi resume theo mode."""
            kind = cmd[0]
            # KET BATTLE: dang trong tran thi BO CHAY + cho thoat tran TRUOC khi doi kenh/teleport
            # (switch_channel/leave_party giua battle de bi server bo qua/loi). cap 60s.
            c.flee_mode = True
            t0 = time.time()
            while c.in_combat(idle_secs=3.0):
                if not c.running or _stopped() or time.time() - t0 > 60:
                    break
                time.sleep(0.5)
            if is_leader:
                c.leave_party(); reset_party_joined(pidx)   # huy party cu
            if kind == "channel":
                ch = cmd[1]
                try: c.switch_channel(ch); time.sleep(1.5)
                except Exception as e: log.warning("[%s] manual: loi doi kenh: %s", label, e)
                log.info("[%s] (%s) manual: da doi kenh -> %d", label, role, ch)
            elif kind == "city":
                cid, flag = cmd[1], cmd[2]
                c.flee_mode = True
                try: c.go_to_town(cid, flag)
                except Exception as e: log.warning("[%s] manual: loi teleport thanh: %s", label, e)
                log.info("[%s] (%s) manual: da teleport ve thanh %s", label, role, cid)
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
            c._return_safe_on_stop = tm["safe"]
        elif (not is_leader) and train_on_map and has_leader:
            c._wait_leader_on_stop = True
        while c.running:
            # CHU PARTY da thoat (leader_gone) -> member cung THOAT theo (party tan, member o lai vo nghia)
            if (not is_leader) and has_leader and st["leader_gone"].is_set():
                log.info("[%s] (member) CHU PARTY da thoat -> member thoat theo", label)
                _reason("chu party thoat -> member theo")
                break
            if stop_ev is not None and stop_ev.is_set():
                log.info("[%s] (%s) -> STOP tu GUI", label, role)
                if is_leader:
                    # LEADER dang cay ngoai diem quai -> chay ve diem safe GAN NHAT TRUOC,
                    # roi BAO HIEU (stop_leader_done) de member moi thoat theo.
                    if train_on_map:
                        dest = _nearest_safe(c.pos, tm["safe"])
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
                rally = st.get("rally_point") or _nearest_safe(c.pos, tm["safe"]) or tm["safe"][0]
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
                    from bot.client import reset_party_joined
                    reset_party_joined(pidx)         # quen member cu -> leader tinh lai tu dau, retry 60s moi lai
                    if c.relogin():                  # thoat + login lai -> 0x03 resync pos ve dung safe
                        # MOI LAI member NGAY TAI SAFE (leader+member gan nhau) roi CHO ho join
                        # TRUOC khi keo ra spot -> member duoc keo theo. Moi truoc khi di (neu di
                        # spot truoc roi moi moi thi member ket o safe, khong duoc keo).
                        c.combat_ready(); c.flee_mode = False
                        for _ in range(4):           # moi lap lai, cho member (gio da tu do) accept
                            if not c.running or _stopped(): break
                            try: c.invite_members(gap=1.0)
                            except Exception: pass
                            time.sleep(3)
                            if joined_member_count(pidx) >= st["n_members"]:
                                break
                        log.info("[%s] (LEADER) sau relogin: %d/%d member join lai -> keo ra spot",
                                 label, joined_member_count(pidx), st["n_members"])
                        path = st.get("mob_path")
                        if path:
                            c.follow_path(path, flee=False)   # keo ca party ra spot (path tranh tuong)
                        elif spot:
                            c.navigate_to(*spot)     # tu safe (pos CHUAN) keo party ra spot
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
                c.claim_online_gifts()   # nhan qua online khi du gio (10/20/30/60/90/180 phut)
            except Exception as e:
                log.warning("[%s] loi qua online (bo qua): %s", label, e)
            # Van tieu: chi goi lai DUNG GIO escort xong (next_vantieu), KHONG check mu.
            if next_vantieu is not None and time.time() >= next_vantieu:
                try:
                    next_vantieu = c.do_van_tieu()
                except Exception as e:
                    log.warning("[%s] loi van tieu (bo qua): %s", label, e)
                    next_vantieu = time.time() + 600   # loi -> thu lai sau 10p
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
                        try: c.invite_members(gap=1.0)
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
                                c.switch_channel(ch); time.sleep(1); c.combat_ready()
                            except Exception: pass
            if train_on_map:
                pass   # leader da chay long vong (run-around) tu dong tim quai
            elif not is_digioi:
                pass   # city/stand: DUNG YEN, khong lam gi them
            else:
                # DG: dem nguoc thoi gian con lai (digioi_minutes tu S2C 0x55), 30s/lan
                if c.current_map == config.DIGIOI_MAP_ID and time.time() - last_dg >= 30:
                    last_dg = time.time()
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
                                    label, role, "" if do_daily else " (tat dungeon)")
                        if do_daily:
                            try: c.do_daily_dungeon()
                            except Exception as e:
                                log.warning("[%s] loi daily dungeon sau DG: %s", label, e)
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
                                        label, role, " + solo daily dungeon" if do_daily else "")
                            if do_daily:
                                c.do_daily_dungeon()
                                # XONG DG -> nhiem vu NANG (boss o2 + claim not hang/cot + tong ket).
                                # o1 dungeon vua danh o tren; o5 team dungeon chua co.
                                try: c.claim_daily_quests(heavy=True)
                                except Exception as e:
                                    log.warning("[%s] loi claim daily quest (bo qua): %s", label, e)
                            break
                else:
                    out_cnt = 0
        try: c.close()
        except Exception: pass
        if c in _clients: _clients.remove(c)
    except Exception as e:
        _reason("LOI ngoai le: %s" % e)
        log.error("[%s] LOI: %s", label, e)
    finally:
        if is_leader:
            st["leader_gone"].set()   # leader thoat -> member ngung co vao party
        # ghi lai ly do thoat (neu GUI bam STOP ma chua co ly do cu the -> ghi STOP)
        if _stopped() and er["r"].startswith("ket thuc binh thuong"):
            _reason("Anh bam STOP")
        # SERVER chu dong dong ket noi (rot/bao tri/kick) - KHONG phai ket thuc binh thuong/STOP
        elif (not _stopped() and er["r"].startswith("ket thuc binh thuong")
              and c is not None and getattr(c, "server_closed", False)):
            _reason("SERVER dong ket noi (rot mang/bao tri/kick) - khong phai tu thoat")
        account_exit_reason[username] = er["r"]
        # LUU map + ten nhan vat + LEVEL char/pet + ten pet LUC THOAT -> GUI van hien thong tin
        # nhu luc truoc khi tat (truoc day chi luu map+char -> tat la mat level/pet).
        if c is not None and getattr(c, "current_map", None) is not None:
            account_last[username] = {"map": c.current_map, "char": c.char_name or username,
                                      "char_level": getattr(c, "char_level", None),
                                      "pet_name": getattr(c, "pet_name", None),
                                      "pet_level": getattr(c, "pet_level", None)}
        account_clients.pop(username, None)
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


def start_account(username, password, pidx, is_leader, is_picker):
    """Khoi dong 1 acc (thread). Bo qua neu dang chay."""
    t = account_threads.get(username)
    if t is not None and t.is_alive():
        return False
    st = _pstate(pidx)
    st["n_members"] = sum(1 for u, p, lead, _ in party_accounts(pidx) if not lead)
    account_stops[username] = threading.Event()
    t = threading.Thread(target=run_account, args=(username, password, pidx, is_leader, is_picker),
                         daemon=True)
    account_threads[username] = t
    _threads.append(t)
    t.start()
    return True


def start_party(pidx, stagger=1.5):
    """Khoi dong tat ca acc trong 1 party."""
    started = 0
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
        st["map_results"] = {}       # reset barrier map cho lan chay nay
        st["summary_done"] = False   # cho phep log lai dong tong ket o lan chay nay
    for u, p, is_leader, is_picker in party_accounts(pidx):
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


def party_switch_channel(pidx, channel):
    """GUI ra lenh: CA party pidx huy party + chuyen sang KENH 'channel' -> roi tiep tuc che do
    da setup (xu ly trong vong keepalive qua cmd_gen)."""
    st = _pstate(pidx)
    with st["lock"]:
        st["channel"] = int(channel)   # de reform/setup dung dung kenh moi
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


def stop_account(username):
    """Dung 1 acc: set event + dong ket noi -> thread tu ket thuc."""
    ev = account_stops.get(username)
    if ev is not None:
        ev.set()
    c = account_clients.get(username)
    if c is not None:
        # KHONG dong socket ngay neu thread tu xu ly viec thoat:
        #  - leader map-train: tu chay ve safe roi dong.
        #  - member train: cho leader ve safe (stop_leader_done) roi moi dong.
        if getattr(c, "_return_safe_on_stop", None):
            log.info("[%s] STOP -> cho thread chay ve safe roi dong", username)
        elif getattr(c, "_wait_leader_on_stop", None):
            log.info("[%s] STOP -> cho leader ve safe roi member thoat theo", username)
        else:
            try: c.close()
            except Exception: pass
    return True


def stop_party(pidx):
    for u, p, _, _ in party_accounts(pidx):
        stop_account(u)


def stop_all():
    for u in list(account_stops.keys()):
        stop_account(u)


def is_account_running(username):
    t = account_threads.get(username)
    return t is not None and t.is_alive()


def account_status(username):
    """Dict trang thai live cua acc (cho GUI). running, char, map, channel, in_party, dg_remain..."""
    c = account_clients.get(username)
    running = is_account_running(username)
    if c is None:
        # da tat/thoat -> GIU map + nhan vat LUC CUOI (de biet thoat o dau, dung map khong)
        last = account_last.get(username, {})
        return {"running": running, "char": last.get("char", ""), "map": last.get("map"),
                "in_party": False, "dg_remain": None, "combat": False, "channel": None,
                "strategist": False, "char_level": last.get("char_level"),
                "pet_name": last.get("pet_name"), "pet_level": last.get("pet_level")}
    pidx = getattr(c, "party_idx", None)
    from bot.client import is_joined, is_strategist
    st = _party_state.get(pidx, {})
    dg_remain = None
    if c.current_map == config.DIGIOI_MAP_ID:
        dg_remain = max(0, DIGIOI_LIMIT - getattr(c, "digioi_minutes", 0))
    account_last[username] = {"map": c.current_map, "char": c.char_name or "",
                              "char_level": getattr(c, "char_level", None),
                              "pet_name": getattr(c, "pet_name", None),
                              "pet_level": getattr(c, "pet_level", None)}  # luu lai luc cuoi
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
        "pet_name": getattr(c, "pet_name", None),
        "pet_level": getattr(c, "pet_level", None),
    }


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
    stop_all()
    log.info(">>> Ket thuc.")


if __name__ == "__main__":
    _run_cli()
