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


def _pstate(pidx):
    if pidx not in _party_state:
        _party_state[pidx] = {"channel": None,
                              "channel_ready": threading.Event(),
                              "invited": threading.Event(),
                              "lock": threading.Lock(),
                              "ready_members": set(),   # member da vao DG + dung kenh leader
                              "n_members": 0,            # tong so member can cho
                              "leader_ok": threading.Event(),   # leader DUNG map train -> tiep tuc
                              "leader_bad": threading.Event()}  # leader SAI map -> huy ca party
    return _party_state[pidx]


def run_account(username, password, pidx, is_leader):
    label = username
    role = "LEADER" if is_leader else "member"
    st = _pstate(pidx)
    try:
        # --- Login + cho vao world THUC SU (co self_entity VA co current_map) ---
        c = None
        for attempt in range(6):
            cred = login(username, password)
            c = GameClient(cred["user_id"], cred["access_token"])
            c._label = label; c._username = username
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
        _clients.append(c)
        label = c.char_name or username   # log theo TEN NHAN VAT (neu da resolve), fallback username
        login_map = c.current_map         # map LUC LOGIN (doc som, it bi pollution) - dung de check train
        log.info("[%s] (%s) vao world.", label, role)
        log.info("[%s] >>> MAP HIEN TAI = %s <<<  (dung ID nay de setup START_CITY_ID/TRAIN)",
                 label, login_map)
        c.claim_checkin()       # diem danh hang ngay (tu dem so lan)
        c.claim_14day_gift()    # qua 14 ngay user moi
        c.claim_legion_gift()   # nhan qua quan doan hang ngay

        # MODE theo START_CITY_ID: CO trong train_maps.json -> MAP-TRAIN; con lai (0 / DG / bat ky)
        # -> DI GIOI. (Muon login dung yen thi dung bot_standalone.py.)
        sc = getattr(config, "START_CITY_ID", 0)
        tm = config.TRAIN_MAPS.get(sc)          # dict {safe, mobs} neu la map train
        train_on_map = tm is not None

        if train_on_map:
            # PHAI dung map login (toa do safe/mobs chi dung tren map do).
            self_map_ok = (login_map == sc)
            def _quit():
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
            if is_leader:
                if not self_map_ok:
                    # LEADER sai map -> HUY ca party (bao member thoat het)
                    log.warning("[%s] (LEADER) KHONG o map train %s (dang o %s) -> HUY CA PARTY",
                                label, sc, c.current_map)
                    st["leader_bad"].set()
                    _quit(); return
                st["leader_ok"].set()   # leader ok -> member duoc tiep tuc
            else:
                if not self_map_ok:
                    log.warning("[%s] (member) KHONG o map train %s (dang o %s) -> THOAT GAME acc nay",
                                label, sc, c.current_map)
                    _quit(); return
                # doi leader quyet dinh (ok / huy), toi da 150s
                t0 = time.time()
                while not (st["leader_ok"].is_set() or st["leader_bad"].is_set()):
                    if time.time() - t0 > 150:
                        log.warning("[%s] (member) khong thay leader quyet dinh -> THOAT", label)
                        _quit(); return
                    time.sleep(0.5)
                if st["leader_bad"].is_set():
                    log.warning("[%s] (member) leader sai map -> ca party huy -> THOAT", label)
                    _quit(); return
            # --- MAP-TRAIN: chay toi diem AN TOAN (dinh battle -> flee) ---
            log.info("[%s] (%s) MAP-TRAIN map=%s -> chay toi diem an toan %s",
                     label, role, sc, tm["safe"])
            c.navigate_to(*tm["safe"])
        else:
            # --- DI GIOI (solo) - ne battle/chua login xong, retry ---
            if c.in_di_gioi():
                log.info("[%s] (%s) da o trong DG san -> chay luon (khong vao lai)", label, role)
            elif not c.enter_di_gioi_safe():
                log.warning("[%s] (%s) khong vao duoc DG (het gio?) -> TAT acc nay", label, role)
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
                return

        # ===== LAP PARTY + CAY (map-train hoac DI GIOI deu lap party) =====
        # --- Chon / dong bo KENH ---
        if is_leader:
            ch = c.pick_best_channel()
            st["channel"] = ch
            st["channel_ready"].set()
            log.info("[%s] (LEADER) chon kenh %s cho ca party", label, ch)
        else:
            st["channel_ready"].wait(60)
            ch = st["channel"]
            if ch:
                c.switch_channel(ch)
                log.info("[%s] (member) chuyen sang kenh leader = %s", label, ch)
            time.sleep(2)
            with st["lock"]:
                st["ready_members"].add(username)
            log.info("[%s] (member) SAN SANG (%d/%d) - cho leader moi",
                     label, len(st["ready_members"]), st["n_members"])
        time.sleep(2)

        # --- Leader: CHO du member san sang roi MOI, roi CAY ---
        if is_leader:
            for _ in range(45):
                if len(st["ready_members"]) >= st["n_members"]:
                    break
                time.sleep(2)
            log.info("[%s] (LEADER) %d/%d member san sang -> MOI (theo entity)",
                     label, len(st["ready_members"]), st["n_members"])
            from bot.client import joined_member_count
            for r in range(6):
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
            if joined_member_count(pidx) >= 1:
                time.sleep(1)
                c.set_party_strategist()    # set member INT cao nhat lam quan su
            elif train_on_map:
                # map-train CAN >=1 member (de set quan su hoi SP) -> 0 member thi THOAT
                log.warning("[%s] (LEADER) 0 member dung map -> khong du quan su -> THOAT", label)
                try: c.close()
                except Exception: pass
                if c in _clients: _clients.remove(c)
                return
            else:
                log.info("[%s] (LEADER) khong co member join -> CAY 1 MINH (DG)", label)
            # --- VI TRI CAY ---
            if train_on_map:
                c.move_to(*tm["mobs"][0])   # ra diem quai, dung yen cho quai toi (toa do == UI)
                c.combat_ready()            # combat-active lai (doi kenh da reset) -> quai aggro
                log.info("[%s] (LEADER) ra diem quai %s dung cay.", label, tm["mobs"][0])
            else:
                c.start_run_around()        # DG: chay long vong tim quai
                log.info("[%s] (LEADER) bat dau chay long vong.", label)
        else:
            st["invited"].wait(120)
            if train_on_map:
                c.combat_ready()   # combat-active de join tran chung; KHONG chay (dung yen tai safe)
            log.info("[%s] (member) da vao party - dung yen, tu danh (chung tran voi leader)", label)

        # --- Giu song ---
        out_cnt = 0
        last_remove = time.time()
        while c.running:
            time.sleep(5)
            log.info("[%s] (%s) pos=%s map=%s combat=%s",
                     label, role, c.pos, c.current_map, c.in_combat())
            if train_on_map:
                pass   # leader da chay long vong (run-around) tu dong tim quai
            else:
                # DG: roi DG (map biet & khac DG) lien tuc -> het gio DG -> dong acc
                if c.current_map is not None and c.current_map != config.DIGIOI_MAP_ID and not c.in_combat():
                    out_cnt += 1
                    if out_cnt >= 4:   # ~20s lien tuc ngoai DG
                        log.warning("[%s] (%s) het gio DG (ra thanh map=%s) -> TAT acc",
                                    label, role, c.current_map)
                        break
                else:
                    out_cnt = 0
        try: c.close()
        except Exception: pass
        if c in _clients: _clients.remove(c)
    except Exception as e:
        log.error("[%s] LOI: %s", label, e)


# Gom acc theo party. Leader = slot 0 (PARTY_LEADER_ACC). Khoi dong tung party.
for pidx, party in enumerate(config.PARTIES):
    leader_acc = config.PARTY_LEADER_ACC.get(pidx)
    valid = [(u, p) for u, p in party if u and u.strip()]
    st = _pstate(pidx)
    st["n_members"] = sum(1 for u, p in valid if u != leader_acc)   # so member (khong tinh leader)
    for u, p in valid:
        is_leader = (u == leader_acc)
        threading.Thread(target=run_account, args=(u, p, pidx, is_leader), daemon=True).start()
        time.sleep(1.5)

log.info(">>> Party train Di Gioi dang chay. %s", "vo han" if MINUTES == 0 else f"{MINUTES} phut")
try:
    if MINUTES == 0:
        while True:
            time.sleep(10)
    else:
        time.sleep(MINUTES * 60)
except KeyboardInterrupt:
    pass
for c in _clients:
    try: c.close()
    except Exception: pass
log.info(">>> Ket thuc.")
