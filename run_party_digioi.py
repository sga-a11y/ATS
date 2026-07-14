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
from bot.client import (GameClient, check_duplicate_accounts, joined_member_count, is_joined,
                        is_strategist, reset_party_joined)

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
account_reconnect = {}    # username -> True neu lan thoat vua roi la SERVER ROT (supervisor login lai)


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
                              "o5_done_by": {},          # username -> o5 (pho ban to doi) da xong? Leader chi chay khi CA party chua xong
                              "o5_state": "idle",        # "idle"|"running"|"done" - member PHAI cho != "idle" (xem _handle_o5_team)
                              "o5_broke": False,         # team dungeon VO do co dis giua chung -> CA party relogin thoat instance
                              "o5_need_redo": False,     # team dungeon VO -> reconnect xong lam LAI daily (team dungeon)
                              "leader_ok": threading.Event(),   # leader DUNG map train -> tiep tuc
                              "leader_bad": threading.Event(),  # leader SAI map -> huy ca party
                              "leader_gone": threading.Event(),  # leader da THOAT -> member ngung retry vao party
                              "stop_leader_done": threading.Event(),  # STOP: leader DA ve safe -> member duoc thoat
                              "route_party_ready": threading.Event(),  # ROUTE: party da lap xong o thanh -> sap keo di
                              "route_done": threading.Event(),         # ROUTE: leader da keo xong (toi train map)
                              "map_results": {},     # ROUTE barrier: username -> dang o train map? (de quyet dinh ca party)
                              "member_maps": {},     # username -> current_map (member report lien tuc; leader check ai bi bo lai khi keo)
                              "mob_spot": None,      # diem quai leader chon (de _start_training dung lai)
                              "rally_point": None,   # safe GAN diem quai nhat -> CA PARTY ve day (gan leader)
                              "rally_ready": threading.Event(),  # leader da chon diem quai + rally_point
                              "path_done": threading.Event(),    # leader da di xong follow_path toi diem quai (member bi keo theo)
                              "reform_gen": 0,       # +1 moi khi co acc van map (chet) -> CA party reform tai cho
                              "cmd_gen": 0,          # +1 moi khi GUI ra lenh thu cong (doi kenh/teleport thanh)
                              "cmd": None,           # ("channel", ch) | ("city", city_id, flag)
                              "reconnecting": set(),  # username dang ROT + login lai (cho reconnect resync)
                              "disc_gen": 0,          # +1 moi khi co acc rot (bao cac nick khac phan ung)
                              "summary_done": False}  # da log dong tong ket "party thoat het" chua
    return _party_state[pidx]


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
    er = {"r": "ket thuc binh thuong (het gio hoac GUI dung)"}  # ly do thoat (de tong ket party)
    def _reason(msg):
        er["r"] = msg
    # Server (IP) theo config rieng cua party
    _pc0 = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
    server_ip = _pc0.get("server_ip") or config.GAME_HOST
    server_name = _pc0.get("server", "?")
    server_id = _pc0.get("server_id", 1)
    _login_failed = False   # True neu login/vao world that bai 6 lan -> supervisor van thu lai (backoff)
    try:
        # --- Login + cho vao world THUC SU (co self_entity VA co current_map) ---
        c = None
        ok = False
        for attempt in range(6):
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
                c.close(); time.sleep(5)
            except Exception as e:
                # login() (auth HTTP) / connect() LOI (server lom, mang chap) -> KHONG de nick CHET:
                # coi nhu 1 lan thu that bai, backoff 5s roi thu lai; het 6 lan -> _login_failed ben
                # duoi (supervisor reconnect vo han). Truoc day login() raise -> thoat ca vong -> thread
                # chet han (bug: nick "tat" khi server lom lam login HTTP fail).
                log.warning("[%s] login/connect loi (lan %d): %s -> thu lai", label, attempt + 1, e)
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
        c.log_bag_delayed()   # In tui khi snapshot ve + on dinh (adaptive, toi da 8s) -> dinh danh item
        # MAP-TRAIN: bat flee NGAY tu login -> moi tran (truoc khi lap party) deu BO CHAY,
        # khong danh lung tung; chi tat flee khi da vao diem train.
        if config.TRAIN_MAPS.get(getattr(config, "START_CITY_ID", 0)) is not None:
            c.flee_mode = True
        next_vantieu = None
        next_phuc_than = 0.0   # 0.0 -> kiem tra NGAY lan dau (khong cho 30p roi moi dung lan dau)
        # pcfg doc SOM (truoc day chi doc o duoi, SAU khoi chores nay) - can ngay o day de biet
        # "Danh boss QD" co bat hay khong TRUOC khi goi do_legion_boss() lan dau luc login.
        pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
        c.fight_legion_boss = pcfg.get("fight_legion_boss", True)
        if not is_reconnect:    # RECONNECT nhe: bo qua exp/qua/gacha/mail/vantieu (da lam phien truoc)
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
            next_vantieu = c.do_van_tieu()   # van tieu: nhan qua xong + gui pet; tra ve gio check tiep
            # BOSS QUAN DOAN ngay sau van tieu: danh solo neu con luot (server count 0x55/0x2a) + het
            # cooldown. KHONG lien quan daily quest (tick hay ko van danh). Luc login char SOLO (chua
            # lap party) -> danh duoc. Trong phien: keepalive trigger REFORM khi con luot (xem duoi).
            # BUG THAT: neu acc login SAN TRONG Di Gioi (map=DIGIOI_MAP_ID ngay tu dau, vd server
            # giu nguyen phien cu) - goi boss QD (vao instance/map KHAC) lam RIENG khoi DG, khien
            # current_map bi lech (thay vi quay lai DIGIOI_MAP_ID, ket thuc o map thanh sai) -> cac
            # buoc enter_di_gioi_safe() sau do THAT BAI lien tuc du acc dang dung san trong DG.
            # Bo qua HOAN TOAN boss QD trong truong hop nay - de sau, khi da chac chan roi DG an toan.
            if c.in_di_gioi():
                log.info("[%s] Dang o san trong Di Gioi luc login -> BO QUA boss QD (tranh lam lech map)",
                          label)
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
        tm = config.TRAIN_MAPS.get(sc)          # dict {safe, mobs} neu la map train
        # mode: digioi | train | city (tap trung ve thanh) | stand (dung yen) | cleanbag
        mode = pcfg.get("mode")
        if not mode:
            mode = ("train" if tm else ("digioi" if sc == config.DIGIOI_MAP_ID
                    else ("stand" if sc == 0 else "city")))
        train_on_map = (mode == "train") and (tm is not None)
        is_digioi = (mode == "digioi")
        log.info("[%s] (%s) MODE=%s start_city=%s", label, role, mode, sc)

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
        if not is_digioi and do_daily and (not is_reconnect or _o5_redo):
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
        elif is_reconnect and train_on_map and tm and tm.get("safe"):
            if login_map == sc:
                c.navigate_to(*_nearest_safe(c.pos, tm["safe"]))   # reconnect + dang o bai -> ra safe cho keo
            else:
                # RECONNECT login lai o MAP KHAC train map (truoc khi rot member da teleport di lam
                # daily dungeon -> login = vi tri logout, van o thanh do). KHONG duoc THOAT oan.
                _rt = getattr(config, "TRAIN_ROUTES", {}).get(sc)
                if _rt:
                    # sc la TRAIN MAP di bang ROUTE (qua cong) - KHONG phai thanh, teleport thang toi
                    # sc se FAIL (bug cu: go_to_town(20821) spam 60s roi hut). De khoi reform ben
                    # duoi (barrier + _do_reform) keo qua route; member cho leader keo (khong THOAT).
                    log.info("[%s] (%s) RECONNECT o map %s, train map %s di bang ROUTE -> de reform keo",
                             label, role, login_map, sc)
                else:
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
                        c.navigate_to(*_nearest_safe(c.pos, tm["safe"]))

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
            if not route2:
                log.warning("[%s] (%s) reform: khong co route -> bo qua", label, role)
                return
            fc = int(route2.get("from_city", 0)); ff = int(route2.get("city_flag", 0))
            spot = st.get("mob_spot")
            _g0 = st["reform_gen"]   # gen reform DANG xu; co gen MOI hon (acc khac van) -> abort keo, quay lai xu
            _ab = lambda: _stopped() or (not c.running) or st["reform_gen"] > _g0
            c.flee_mode = True
            if is_leader:
                st["route_party_ready"].clear(); st["route_done"].clear()  # reset handshake cho lan nay
                c.leave_party()                  # GIAI TAN party cu (neu co) -> member duoc tha
                reset_party_joined(pidx)
            if fc:
                # CHI ve thanh gom nhau. KHONG lam boss/dungeon o day nua (truoc day lam MOI VONG
                # reform cho ca member -> churn teleport + keo dai reform -> member de MAT KET NOI
                # giua chung (server chap chon) -> ca party ket reconnect-reform loop, "member khong
                # ve theo leader" (xem log party 3). Boss/dungeon da chay 1 lan o login chores roi.
                # Khop ban APK _reform_to_spot (da cat phan nay). LUU Y: mat tinh nang danh boss QD
                # mid-session-train qua reform (train mode) - danh doi lay reform gon + on dinh.
                try: c.go_to_town(fc, ff)        # CA party (leader+member) tu teleport ve thanh gom nhau
                except Exception as e: log.warning("[%s] reform: loi ve thanh: %s", label, e)
            # LUON re-sync kenh (khong chi switch ve kenh cu da luu) - vua ve thanh sau khi CO THE
            # da danh dungeon (solo o1 hoac team o5) -> server co the da day acc sang kenh KHAC (ngau
            # nhien). Chi switch ve kenh CU (st["channel"]) KHONG du: kenh do co the da DAY (full,
            # acc khac dang chiem) sau 1 hoi, hoac ban than viec dung 1 kenh CU thieu kiem tra lai
            # suc chua -> can PICK LAI qua do_channel_sync() (picker tu kiem tra du cho ca party
            # truoc khi chot, xem pick_best_channel) moi chac chan CA PARTY vao chung duoc 1 kenh.
            do_channel_sync()
            if is_leader:
                # LAP LAI party TAI THANH: CHO VO HAN toi khi DU member join (khong gioi han 8 lan).
                # Member dang reconnect -> bump reform_gen -> _ab() -> thoat de keepalive reform lai khi
                # no vao. Van hoan toan -> ca party dung o thanh cho (an toan).
                while joined_member_count(pidx) < st["n_members"]:
                    if _ab(): return   # stop / reform moi hon -> thoat de keepalive xu lai
                    try: c.invite_members(gap=1.0)
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
                # KEO DI THU CONG qua tung cong/buoc -> member TRONG PARTY tu theo leader KE CA QUA
                # CONG. KHONG dung follow_route (no tu teleport -> khong keo).
                for stp in route2.get("steps", []):
                    if _ab(): break   # reform moi / stop -> dung keo, quay lai keepalive xu
                    t1 = time.time()   # DANG DANH -> cho HET TRAN roi moi di buoc/qua cong
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
                    rally2 = st.get("rally_point") or (tm["safe"][0] if tm and tm.get("safe") else None)
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
            self_map_ok = (login_map == sc)
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
            if route and has_leader:
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
                    if not route:   # route-less: KHONG keo ve map train duoc -> TAT CA PARTY
                        st["leader_bad"].set()   # member thoat het
                        _reason("route-less train + leader sai map (o %s, can %s) -> tat ca party"
                                % (c.current_map, sc))
                        log.warning("[%s] (LEADER) route-less + SAI MAP (o %s, can %s) -> TAT CA PARTY",
                                    label, c.current_map, sc)
                        stop_party(pidx); _quit(); return
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
                        if not c.running and not getattr(c, "server_closed", False):
                            st["leader_bad"].set()   # rot han (khong reconnectable) -> member thoat
                        _quit(); return
                st["leader_ok"].set()   # leader ok -> member duoc tiep tuc
            else:
                if not self_map_ok and not c.running:
                    _reason("member MAT KET NOI khi dang route (map cuoi %s)" % c.current_map)
                    log.warning("[%s] (member) MAT KET NOI khi dang di chuyen toi train map -> thoat.", label)
                    _quit(); return
                if not self_map_ok:
                    if not route:   # route-less: khong keo ve map train duoc -> TAT CA PARTY (theo yeu cau)
                        _reason("route-less train + member sai map (o %s, can %s) -> tat ca party"
                                % (c.current_map, sc))
                        log.warning("[%s] (member) route-less + SAI MAP (o %s, can %s) -> TAT CA PARTY",
                                    label, c.current_map, sc)
                        stop_party(pidx); _quit(); return
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
                # NGUYEN TAC TOI THUONG: DU FULL PARTY MOI LAM -> KHONG tru n_members (het gio DG cung
                # ko tru; leader dung cho, ca party dung yen neu thieu - theo yeu cau).
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
            # --- EVENT: SYNC KENH (ca party cung 1 kenh -> moi party TAY duoc) roi tele toi map event
            #     (Nhi Kieu / 40 NPC...) va DUNG YEN, cho moi tay. KHONG tu lap party. ---
            do_channel_sync()   # ca party ve cung kenh TRUOC khi vao event (khong thi moi party tay khong duoc)
            _evs = getattr(config, "EVENTS", {}) or {}
            ev = _evs.get(pcfg.get("event_key") or "")
            if ev is None and _evs:
                # event_key thieu/None/sai (vd config luu truoc khi co picker) -> fallback event DAU
                # TIEN (tien khi chi co 1 event). User chon dung event trong GUI + luu lai la het.
                _k = next(iter(_evs)); ev = _evs[_k]
                log.info("[%s] (%s) mode event: event_key='%s' khong hop le -> dung event dau '%s' (%s)",
                         label, role, pcfg.get("event_key"), _k, ev.get("label"))
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

        # training_started duoc gan trong nhanh "elif is_leader" (o duoi) - PHAI khoi tao truoc o
        # DAY vi vong keepalive (should_fight = training_started if is_leader else ...) doc bien
        # nay bat ke mode nao. Thieu dong nay -> Di Gioi SOLO (re vao nhanh rieng, KHONG chay qua
        # "elif is_leader") crash NGAY: "cannot access local variable 'training_started'".
        training_started = False
        # Di Gioi SOLO: moi acc chay rieng le hoan toan - khong lap party, khong dong bo kenh (da
        # bo qua o buoc dong bo kenh o tren), khong cho leader/member gi ca. Ai vao duoc DG thi tu
        # chay long vong luon (xem buoc 1-2 o tren: da vao DG + lam nhiem vu nhe).
        digioi_solo = is_digioi and pcfg.get("digioi_mode") == "solo"
        event_mode = (mode == "event")
        if event_mode:
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
                # ve diem tap ket) roi moi + train. Member khong tham gia duoc (het gio DG / thoat / sai
                # map) da TU TRU n_members -> muc tieu "du" luon dat duoc, KHONG cho bong ma. KHONG bo
                # cuoc sau 180s nhu truoc (do la nguyen nhan train thieu party khi co dua login cham).
                _t0 = time.time()
                while len(st["ready_members"]) < st["n_members"]:
                    if _stopped(): st["stop_leader_done"].set(); c.close(); return
                    if not c.running: c.close(); return
                    if time.time() - _t0 > 30:
                        log.info("[%s] (LEADER) CHO du member san sang (%d/%d)...",
                                 label, len(st["ready_members"]), st["n_members"])
                        _t0 = time.time()
                    time.sleep(2)
                log.info("[%s] (LEADER) DU %d/%d member san sang -> MOI (theo entity)",
                         label, len(st["ready_members"]), st["n_members"])
                # MOI toi khi DU PARTY join (khong gioi han 6 lan): member da san sang, invite se toi.
                _t0 = time.time()
                while joined_member_count(pidx) < st["n_members"]:
                    if _stopped(): st["stop_leader_done"].set(); c.close(); return
                    if not c.running: c.close(); return
                    c.invite_members(gap=1.0)
                    st["invited"].set()
                    time.sleep(4)
                    if time.time() - _t0 > 30:
                        log.info("[%s] (LEADER) dang moi... joined=%d/%d",
                                 label, joined_member_count(pidx), st["n_members"])
                        _t0 = time.time()
                st["invited"].set()
                log.info("[%s] (LEADER) DU PARTY (%d/%d member join)",
                         label, joined_member_count(pidx), st["n_members"])
            # Bat dau train (set QS + ra cho danh). Goi khi DA co >=1 member (du quan su).
            training_started = False
            def _start_training():
                c.set_party_strategist()    # set member INT cao nhat lam quan su (hoi SP)
                if train_on_map:
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
                    if not spot and tm["mobs"]:
                        import random
                        spot = random.choice(tm["mobs"])
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
                # CHO VO HAN leader moi vao party (khong timeout 120s -> tranh member tuong da join
                # roi danh le). Leader dang reconnect -> chua moi -> member dung cho o safe.
                while not st["invited"].is_set():
                    if _stopped() or not c.running: break
                    st["invited"].wait(2)
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
        reform_gen_handled = 0      # gen reform da xu ly. Init=0 (KHONG = st["reform_gen"]) de neu
        # co acc bi DUMP luc setup (da bump reform_gen) thi keepalive thay ngay -> reform don no
        cmd_gen_handled = st["cmd_gen"]   # lenh thu cong (GUI) da xu ly
        disc_gen_handled = st["disc_gen"] # RECONNECT: gen disconnect da xu ly (init = hien tai)

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
            # CHU PARTY da thoat (leader_gone) -> member cung THOAT theo (party tan, member o lai vo
            # nghia). TRU Di Gioi SOLO: KHONG lap party thuc su (moi acc chay doc lap hoan toan) ->
            # "leader" chi la vai tro danh nhan trong config, KHONG lien quan gi den viec cac acc
            # khac co chay duoc hay khong -> KHONG duoc thoat theo (da xac nhan bug thuc te: leader
            # out la ca party solo out theo, vo ly vi solo dung y la doc lap).
            if (not is_leader) and has_leader and st["leader_gone"].is_set() and not digioi_solo and not event_mode:
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
            # ==== RECONNECT reaction: co dong doi ROT (dang login lai) -> TAM DUNG + cho tat ca ve
            # -> restart mode. CHI khi party co bot-leader (khong thi nick rot da chet). Di Gioi SOLO
            # bo qua (moi acc doc lap). Team dungeon xu o phase daily rieng (relogin ca party). ====
            if has_leader and not digioi_solo and not event_mode and st["disc_gen"] > disc_gen_handled:
                disc_gen_handled = st["disc_gen"]
                if st["reconnecting"]:
                    log.warning("[%s] (%s) dong doi ROT %s -> TAM DUNG cho reconnect",
                                label, role, list(st["reconnecting"]))
                    c.flee_mode = True
                    if train_on_map and tm and tm.get("safe"):   # train: ve rally dung cho
                        rally = st.get("rally_point") or _nearest_safe(c.pos, tm["safe"]) or tm["safe"][0]
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
                        _route_r = getattr(config, "TRAIN_ROUTES", {}).get(sc)
                        if _route_r:                             # CO route: reform day du (ve thanh/sync kenh/keo)
                            try: _do_reform()
                            except Exception as e: log.warning("[%s] reconnect reform loi: %s", label, e)
                        elif c.current_map != sc:                # route-less + MINH lech map -> TAT CA PARTY
                            log.warning("[%s] (%s) route-less + minh KHAC map train (%s != %s) -> TAT CA PARTY",
                                        label, role, c.current_map, sc)
                            _reason("route-less train + sai map -> tat ca party")
                            stop_party(pidx); continue
                        else:                                    # route-less + CA PARTY o map -> regroup TAI CHO
                            do_channel_sync()                    # (nick lech map da tu stop_party o startup cua no)
                            if is_leader:
                                c.flee_mode = True               # ne quai trong luc CHO du party
                                while joined_member_count(pidx) < st["n_members"]:   # CHO VO HAN: du party moi danh
                                    if not c.running or _stopped(): break
                                    try: c.invite_members(gap=1.0)
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
                c.claim_online_gifts()   # nhan qua online khi du gio (10/20/30/60/90/180 phut)
            except Exception as e:
                log.warning("[%s] loi qua online (bo qua): %s", label, e)
            # Phuc Than: dinh ky 30p/lan (KHONG phai 1 lan luc login) - CHI khi party bat cong tac
            # "Su dung Phuc Than". Danh gia moi tick (nhu claim_online_gifts) thay vi tach thread rieng.
            if pcfg.get("use_phuc_than") and time.time() >= next_phuc_than:
                try:
                    c.use_phuc_than_items()
                except Exception as e:
                    log.warning("[%s] loi dung item phuc than (bo qua): %s", label, e)
                next_phuc_than = time.time() + 1800   # 30 phut
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
        # RECONNECT: server ROT (server_closed) + co bot-leader + khong phai GUI-STOP -> supervisor se
        # login lai. Khi do KHONG set leader_gone (member phai CHO, dung thoat theo) + KHONG tong ket.
        reconnectable = (has_leader and not _stopped()
                         and (_login_failed
                              or (c is not None and getattr(c, "server_closed", False))))
        account_reconnect[username] = reconnectable
        if is_leader and not reconnectable:
            st["leader_gone"].set()   # leader thoat that su -> member ngung co vao party
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
                c._phoban_until = 0.0
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
                c._phoban_until = 0.0
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
            # CASE 3: co dong doi ROT trong luc danh team dungeon -> leader cung RELOGIN thoat instance
            # (giong member) truoc khi ve flow. reform_gen (finally) + train reaction se gom lai sau.
            if st["disc_gen"] > _dg0 or st["reconnecting"]:
                log.warning("[%s] (LEADER) dong doi ROT trong team dungeon -> RELOGIN thoat instance", label)
                try: c.relogin()
                except Exception: pass
        finally:
            with st["lock"]:
                # VO do co dis (chinh leader rot = not c.running, HOAC co member rot = disc_gen/
                # reconnecting): bao member -> CA party relogin thoat instance (trong dungeon KHONG
                # teleport ra duoc -> truoc day member spam go_to_town vo tan, xem log party xGAx).
                if (not c.running) or st["disc_gen"] > _dg0 or st["reconnecting"]:
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
    """Bọc run_account: SERVER ROT (server_closed) + party CO bot-leader -> login lai (backoff
    5s x3 -> 30s x10 -> 60s), VO HAN toi khi duoc (chi dung khi GUI Stop). KHONG co bot-leader ->
    nick rot CHET luon (giu hanh vi cu). run_account bao lai qua account_reconnect[username]."""
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
        with st["lock"]:
            st["reconnecting"].add(username)
            st["disc_gen"] += 1
        attempt += 1
        wait = 5 if attempt <= 3 else (30 if attempt <= 13 else 60)
        log.warning("[%s] RECONNECT: server rot -> login lai sau %ds (lan %d)", username, wait, attempt)
        for _ in range(wait):
            if _st():
                break
            time.sleep(1)
        if _st():
            break
    st["reconnecting"].discard(username)
    if is_leader:
        st["leader_gone"].set()   # thoat that su (het reconnect) -> member thoat theo


def start_account(username, password, pidx, is_leader, is_picker):
    """Khoi dong 1 acc (thread). Bo qua neu dang chay."""
    t = account_threads.get(username)
    if t is not None and t.is_alive():
        return False
    st = _pstate(pidx)
    st["n_members"] = sum(1 for u, p, lead, _ in party_accounts(pidx) if not lead)
    account_stops[username] = threading.Event()
    t = threading.Thread(target=_run_account_supervised, args=(username, password, pidx, is_leader, is_picker),
                         daemon=True)
    account_threads[username] = t
    _threads.append(t)
    t.start()
    return True


def setup_party_runtime(pidx, mode, server_ip, server_id, accounts,
                        city_flag=0, start_city_id=0, mob_index=-1, do_daily=True,
                        digioi_mode="party", event_key="", leaders=None, has_leader=True):
    """ANDROID: Kotlin goi de POPULATE config cho 1 party luc runtime (thay vi doc accounts.json
    nhu PC). accounts = list cac (username, password). Goi XONG roi goi start_party(pidx).
    Cau truc PARTY_CONFIG/PARTIES/PARTY_LEADER_ACC GIONG HET config._load_accounts_json ban PC ->
    tu do run_party_digioi (coordinator CHUNG) chay y het PC."""
    pidx = int(pidx)
    config.PARTY_CONFIG[pidx] = {
        "mode": mode, "start_city_id": int(start_city_id), "mob_index": int(mob_index),
        "city_flag": int(city_flag), "server": "", "server_ip": server_ip,
        "server_id": int(server_id), "do_daily": bool(do_daily),
        "digioi_mode": digioi_mode, "event_key": event_key or "",
    }
    accs = [(str(a[0]), str(a[1])) for a in accounts if a and a[0]]
    while len(config.PARTIES) <= pidx:
        config.PARTIES.append([])
    config.PARTIES[pidx] = accs
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
        "pet_name": getattr(c, "pet_name", None),
        "pet_level": getattr(c, "pet_level", None),
        # --- them cho UI APK (poll qua account_status thay callback on_status) ---
        "state": "running" if running else "stopped",
        "hp": getattr(_ch, "hp", None), "sp": getattr(_ch, "sp", None),
        "hp_max": getattr(_ch, "hp_max", None), "sp_max": getattr(_ch, "sp_max", None),
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
