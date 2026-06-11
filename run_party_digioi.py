"""PARTY TRAIN DI GIOI - flow tu dong day du.

Flow moi party (slot 0 = chu party / leader, slot 1-4 = member):
  1. Login het cac acc trong party + ket noi game.
  2. Moi acc VAO DI GIOI (solo - KHONG vao duoc khi dang trong party).
  3. Leader chon KENH IT NGUOI nhat -> chia se -> ca party chuyen sang kenh do.
  4. Leader MOI 4 member (quet index nguoi gan; member tu accept qua entity cung party).
  5. Leader CHAY LONG VONG (run-around) den het gio; member tu follow + tu danh.

Chay:  python run_party_digioi.py [so_phut]   (mac dinh chay vo han)
"""
import os, sys, time, logging, threading
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


def _nearest_safe(pos, safes):
    """Diem safe gan vi tri 'pos' nhat (khoang cach binh phuong). pos=None -> diem dau."""
    if not safes:
        return None
    if not pos:
        return safes[0]
    px, py = pos
    return min(safes, key=lambda s: (s[0] - px) ** 2 + (s[1] - py) ** 2)

# ==== REGISTRY cho GUI dieu khien tung acc ====
account_clients = {}   # username -> GameClient (doc trang thai live)
account_stops = {}     # username -> threading.Event (GUI yeu cau dung acc nay)
account_threads = {}   # username -> Thread
account_last = {}      # username -> {"map","char"} luc CUOI truoc khi thoat (de biet thoat o dau)


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
                              "leader_ok": threading.Event(),   # leader DUNG map train -> tiep tuc
                              "leader_bad": threading.Event(),  # leader SAI map -> huy ca party
                              "leader_gone": threading.Event()}  # leader da THOAT -> member ngung retry vao party
    return _party_state[pidx]


def run_account(username, password, pidx, is_leader, is_picker=False):
    label = username
    role = "LEADER" if is_leader else "member"
    has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None
    st = _pstate(pidx)
    stop_ev = account_stops.get(username)   # GUI yeu cau STOP -> thoat moi giai doan
    def _stopped():
        return stop_ev is not None and stop_ev.is_set()
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
        # MAP-TRAIN: bat flee NGAY tu login -> moi tran (truoc khi lap party) deu BO CHAY,
        # khong danh lung tung; chi tat flee khi da vao diem train.
        if config.TRAIN_MAPS.get(getattr(config, "START_CITY_ID", 0)) is not None:
            c.flee_mode = True
        c.claim_checkin()       # diem danh hang ngay (tu dem so lan)
        c.claim_14day_gift()    # qua 14 ngay user moi
        c.claim_legion_gift()   # nhan qua quan doan hang ngay
        c.claim_gacha_pet()     # gacha pet hang ngay (9k xu)
        c.claim_gacha_card()    # gacha card hang ngay (9k xu)

        # MODE theo CONFIG RIENG cua party (PARTY_CONFIG[pidx]). Fallback: suy tu START_CITY_ID.
        pcfg = getattr(config, "PARTY_CONFIG", {}).get(pidx, {})
        sc = pcfg.get("start_city_id", getattr(config, "START_CITY_ID", 0))
        mob_index = pcfg.get("mob_index", 0)
        city_flag = pcfg.get("city_flag", 0)
        do_dungeon = pcfg.get("do_dungeon", True)   # checkbox "Danh daily dungeon" moi party
        tm = config.TRAIN_MAPS.get(sc)          # dict {safe, mobs} neu la map train
        # mode: digioi | train | city (tap trung ve thanh) | stand (dung yen) | cleanbag
        mode = pcfg.get("mode")
        if not mode:
            mode = ("train" if tm else ("digioi" if sc == config.DIGIOI_MAP_ID
                    else ("stand" if sc == 0 else "city")))
        train_on_map = (mode == "train") and (tm is not None)
        is_digioi = (mode == "digioi")
        log.info("[%s] (%s) MODE=%s start_city=%s", label, role, mode, sc)

        # Dong bo kenh: 1 dua (picker) chon kenh it nguoi -> ca lu sang cung.
        # DG: phai goi TRUOC khi vao DG (doi kenh trong DG se DA ra khoi DG!).
        # Map-train: goi sau khi ve safe (doi kenh tren map thuong khong sao).
        def do_channel_sync():
            if is_picker:
                ch = c.pick_best_channel()
                st["channel"] = ch
                st["channel_ready"].set()
                log.info("[%s] (%s) chon kenh %s cho ca party", label, role, ch)
            else:
                st["channel_ready"].wait(420)
                ch = st["channel"]
                if ch:
                    c.switch_channel(ch)
                    log.info("[%s] (member) chuyen sang kenh chung = %s", label, ch)
                time.sleep(2)

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
                if do_dungeon:
                    try:
                        c.do_daily_dungeon()
                    except Exception as e:
                        log.warning("[%s] loi daily dungeon (sai map, bo qua): %s", label, e)
                _quit()
            if is_leader:
                if not self_map_ok:
                    # LEADER sai map -> HUY ca party (bao member thoat het)
                    log.warning("[%s] (LEADER) KHONG o map train %s (dang o %s) -> lam dungeon roi HUY CA PARTY",
                                label, sc, c.current_map)
                    st["leader_bad"].set()
                    _daily_then_quit(); return
                st["leader_ok"].set()   # leader ok -> member duoc tiep tuc
            else:
                if not self_map_ok:
                    log.warning("[%s] (member) KHONG o map train %s (dang o %s) -> lam dungeon roi THOAT",
                                label, sc, c.current_map)
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
                        log.warning("[%s] (member) leader sai map -> ca party huy -> THOAT", label)
                        _quit(); return
            # --- MAP-TRAIN: chay toi diem TAP KET (diem safe dau tien) (dinh battle -> flee) ---
            rally = tm["safe"][0]
            log.info("[%s] (%s) MAP-TRAIN map=%s -> chay toi diem tap ket %s",
                     label, role, sc, rally)
            c.navigate_to(*rally)
            # SOLO daily dungeon o MAP-TRAIN: TAM TAT (het luot -> bi dump ve 12000, pha map-train;
            # Bat/tat bang checkbox "Danh daily dungeon" cua party (do_dungeon).
            if do_dungeon:
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
                    log.warning("[%s] (%s) sau dungeon KHONG ve map train (dang o %s) -> THOAT acc nay",
                                label, role, c.current_map)
                    with st["lock"]:
                        st["started_train"] -= 1
                    _quit(); return
                c.navigate_to(*tm["safe"][0])
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
            do_channel_sync()   # map-train: dong bo kenh sau khi ve safe (tren map thuong)
        elif is_digioi:
            # --- DI GIOI ---
            # 1) PHAI VAO DUOC DG TRUOC (xac nhan in_di_gioi) roi MOI chuyen kenh.
            if not c.in_di_gioi() and not c.enter_di_gioi_safe():
                log.warning("[%s] (%s) khong vao duoc DG (het gio?) -> TAT acc nay", label, role)
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
                return
            # 2) DA o trong DG -> dong bo kenh (gom ca party ve cung instance DG).
            #    Doi kenh trong DG VAN o trong DG (khong bi van ra).
            do_channel_sync()
        else:
            # --- CITY (tap trung ve thanh) / STAND (dung yen) / CLEANBAG ---
            # SOLO daily dungeon TRUOC (neu bat). Dungeon co the bi DUMP ve 12000 -> lam truoc
            # roi MOI ve thanh -> dam bao dung dung thanh tap trung du co bi dump.
            if do_dungeon:
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
            for _ in range(90):   # ~180s: du cho member xong dungeon + ve diem tap ket
                if _stopped(): c.close(); return
                if len(st["ready_members"]) >= st["n_members"]:
                    break
                time.sleep(2)
            log.info("[%s] (LEADER) %d/%d member san sang -> MOI (theo entity)",
                     label, len(st["ready_members"]), st["n_members"])
            from bot.client import joined_member_count
            for r in range(6):
                if _stopped(): c.close(); return
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
                    mobs = tm["mobs"]
                    if mob_index < 0 and mobs:   # "Bot tu chon" -> boc ngau nhien 1 diem (moi lan start)
                        import random
                        spot = random.choice(mobs)
                        log.info("[%s] (LEADER) BOT TU CHON diem quai (ngau nhien) -> %s", label, spot)
                    else:
                        spot = mobs[mob_index] if 0 <= mob_index < len(mobs) else mobs[0]
                    c.move_to(*spot)            # ra diem quai, dung cay (toa do == UI)
                    c.combat_ready(); c.flee_mode = False
                    log.info("[%s] (LEADER) ra diem quai %s dung cay.", label, spot)
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
        from bot.client import joined_member_count, is_joined
        out_cnt = 0
        last_remove = time.time()
        last_retry = time.time()
        last_dg = 0.0
        stop_ev = account_stops.get(username)
        # Bao stop_account: ACC NAY (leader train) khi STOP -> thread tu chay ve safe roi dong,
        # KHONG dong socket ngay (de navigate_to chay duoc).
        if is_leader and train_on_map:
            c._return_safe_on_stop = tm["safe"]
        while c.running:
            if stop_ev is not None and stop_ev.is_set():
                log.info("[%s] (%s) -> STOP tu GUI", label, role)
                # LEADER dang cay ngoai diem quai -> chay ve diem safe GAN NHAT roi moi thoat
                # (member da dung san o safe, khong can). navigate_to tu bat flee, ne tran doc duong.
                if is_leader and train_on_map:
                    dest = _nearest_safe(c.pos, tm["safe"])
                    if dest:
                        log.info("[%s] (LEADER) STOP -> chay ve safe gan nhat %s truoc khi thoat",
                                 label, dest)
                        try:
                            c.navigate_to(*dest)
                        except Exception as e:
                            log.warning("[%s] loi chay ve safe (bo qua): %s", label, e)
                break
            time.sleep(5)
            log.info("[%s] (%s) pos=%s map=%s combat=%s",
                     label, role, c.pos, c.current_map, c.in_combat())
            try:
                c.claim_online_gifts()   # nhan qua online khi du gio (10/20/30/60/90/180 phut)
            except Exception as e:
                log.warning("[%s] loi qua online (bo qua): %s", label, e)
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
                                        label, role, " + solo daily dungeon" if do_dungeon else "")
                            if do_dungeon:
                                c.do_daily_dungeon()
                            break
                else:
                    out_cnt = 0
        try: c.close()
        except Exception: pass
        if c in _clients: _clients.remove(c)
    except Exception as e:
        log.error("[%s] LOI: %s", label, e)
    finally:
        if is_leader:
            st["leader_gone"].set()   # leader thoat -> member ngung co vao party
        account_clients.pop(username, None)


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
    for k in ("leader_ok", "leader_bad", "leader_gone", "invited", "channel_ready"):
        st[k].clear()
    st["channel"] = None
    with st["lock"]:
        st["ready_members"].clear()
        st["started_train"] = 0
        st["dungeon_done"] = 0
    for u, p, is_leader, is_picker in party_accounts(pidx):
        if start_account(u, p, pidx, is_leader, is_picker):
            started += 1
            time.sleep(stagger)
    return started


def start_all():
    n = 0
    for pidx in range(len(config.PARTIES)):
        n += start_party(pidx)
    return n


def stop_account(username):
    """Dung 1 acc: set event + dong ket noi -> thread tu ket thuc."""
    ev = account_stops.get(username)
    if ev is not None:
        ev.set()
    c = account_clients.get(username)
    if c is not None:
        # Leader map-train: KHONG dong ngay -> thread tu chay ve safe gan nhat roi tu dong.
        if getattr(c, "_return_safe_on_stop", None):
            log.info("[%s] STOP -> cho thread chay ve safe roi dong", username)
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
                "strategist": False}
    pidx = getattr(c, "party_idx", None)
    from bot.client import is_joined, is_strategist
    st = _party_state.get(pidx, {})
    dg_remain = None
    if c.current_map == config.DIGIOI_MAP_ID:
        dg_remain = max(0, DIGIOI_LIMIT - getattr(c, "digioi_minutes", 0))
    account_last[username] = {"map": c.current_map, "char": c.char_name or ""}  # luu lai map cuoi
    return {
        "running": running,
        "char": c.char_name or "",
        "map": c.current_map,
        "channel": st.get("channel"),
        "in_party": is_joined(pidx, c.self_entity),
        "dg_remain": dg_remain,
        "combat": c.in_combat() if running else False,
        "strategist": is_strategist(pidx, c.self_entity),
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
