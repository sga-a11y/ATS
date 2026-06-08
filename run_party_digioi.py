"""PARTY TRAIN DI GIOI - flow tu dong day du.

Flow moi party (slot 0 = chu party / leader, slot 1-4 = member):
  1. Login het cac acc trong party + ket noi game.
  2. Moi acc VAO DI GIOI (solo - KHONG vao duoc khi dang trong party).
  3. Leader chon KENH IT NGUOI nhat -> chia se -> ca party chuyen sang kenh do.
  4. Leader MOI 4 member (quet index nguoi gan; member tu accept qua entity cung party).
  5. Leader CHAY LONG VONG (run-around) den het gio; member tu follow + tu danh.

Chay:  python run_party_digioi.py [so_phut]   (mac dinh chay vo han)
"""
import sys, time, logging, threading
try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
from bot import config
from bot.login import login
from bot.client import GameClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[logging.FileHandler("party.log", "w", "utf-8"), logging.StreamHandler()])
log = logging.getLogger("partydg")

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
                              "n_members": 0}            # tong so member can cho
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
        log.info("[%s] (%s) vao world. map=%s", label, role, c.current_map)
        c.claim_checkin()   # diem danh hang ngay (tu dem so lan)

        # --- Vao Di Gioi (solo) - ne battle/chua login xong, retry ---
        # Neu DA o trong DG (login lai khi con ket DG) -> CHAY LUON, KHONG thoat/vao lai
        # (thoat = di bo ra cong, de dinh combat + rot mang). Chi vao moi neu chua o DG.
        if c.in_di_gioi():
            log.info("[%s] (%s) da o trong DG san -> chay luon (khong vao lai)", label, role)
        elif not c.enter_di_gioi_safe():
            log.error("[%s] (%s) khong vao duoc DG -> bo qua acc nay", label, role)
            return

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
            # bao hieu: minh da SAN SANG (vao DG + dung kenh leader)
            with st["lock"]:
                st["ready_members"].add(username)
            log.info("[%s] (member) SAN SANG (%d/%d) - cho leader moi",
                     label, len(st["ready_members"]), st["n_members"])
        time.sleep(2)

        # --- Leader: CHO du member san sang roi MOI, roi CHAY ---
        if is_leader:
            # cho tat ca member vao DG + cung kenh (toi da 90s)
            for _ in range(45):
                if len(st["ready_members"]) >= st["n_members"]:
                    break
                time.sleep(2)
            log.info("[%s] (LEADER) %d/%d member san sang -> MOI (theo entity)",
                     label, len(st["ready_members"]), st["n_members"])
            # moi LAP LAI (theo entity) den khi du member JOIN. Neu member het gio DG (khong
            # vao duoc) -> moi vai lan roi CHAY 1 MINH (khong cho mai).
            from bot.client import joined_member_count
            for r in range(6):
                c.invite_members(gap=1.0)
                st["invited"].set()             # member biet da bat dau moi
                time.sleep(4)
                njoined = joined_member_count(pidx)
                log.info("[%s] (LEADER) sau moi lan %d: joined=%d/%d",
                         label, r + 1, njoined, st["n_members"])
                if njoined >= st["n_members"]:
                    log.info("[%s] (LEADER) DU PARTY (%d member join)", label, njoined)
                    break
                time.sleep(2)
            else:
                log.warning("[%s] (LEADER) chua du member (%d/%d) - co the member het gio DG",
                            label, joined_member_count(pidx), st["n_members"])
            # Set quan su neu co IT NHAT 1 member da join (du party day hay le)
            if joined_member_count(pidx) >= 1:
                time.sleep(1)
                c.set_party_strategist()        # set 1 member da join lam quan su -> SP regen
            else:
                log.info("[%s] (LEADER) khong co member join -> CHAY 1 MINH (khong quan su)", label)
            c.start_run_around()                # chay long vong (party / le / solo)
            log.info("[%s] (LEADER) bat dau chay long vong.", label)
        else:
            st["invited"].wait(120)             # cho leader moi xong
            log.info("[%s] (member) da vao party - tu follow leader + tu danh", label)

        # --- Giu song ---
        while c.running:
            time.sleep(5)
            log.info("[%s] (%s) pos=%s map=%s combat=%s",
                     label, role, c.pos, c.current_map, c.in_combat())
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
