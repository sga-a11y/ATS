"""Vong lap chay 1 account o mode Train - phong theo run_grind.py (PC), nhan
credentials truc tiep tu tham so (khong doc config.py), goi callback Kotlin de
bao trang thai (dung cho BotForegroundService cap nhat StateFlow).

Luu y API thuc te (doi chieu train_bot/client.py, train_bot/login.py):
  - login.login(username, password) -> {"user_id", "access_token", "username"}
  - GameClient(user_id, access_token, host=None, server_id=1)  (KHONG phai server_ip=)
    host=None -> mac dinh config.GAME_HOST. Android truyen host=server_ip de override
    server IP theo tung account/party (multi-server support).
  - client.connect() khong nhan tham so, tu chay _recv_loop/_heartbeat_loop (thread rieng)
  - client.running (bool), client.in_combat(), client.close()
  - client.state.char / client.state.pet la state.Unit: .hp/.hp_max/.sp/.sp_max

QUY UOC GOI CALLBACK TU KOTLIN (quan trong cho BotForegroundService o task sau):
  Chaquopy KHONG cho Python goi truc tiep mot doi tuong Kotlin/Java bat ky bang cu
  phap obj(...) (khong tu dong proxy __call__ cho SAM/lambda). Vi vay should_stop/
  on_status o day PHAI la doi tuong co PHUONG THUC ten "call" (vd Kotlin
  `object { fun call(...) }`), va duoc goi qua .call(...) - KHONG goi truc tiep
  should_stop()/on_status(...). Day la hop dong API on dinh cho phia Kotlin khi
  wire BotForegroundService.
"""
import logging
import random
import threading
import time

from . import config
from . import login as login_mod
from . import party_state as party_state_mod
from .client import GameClient, joined_member_count, reset_party_joined

log = logging.getLogger("bot")


def _jitter(pt):
    """Xe dich toa do +-10 ngau nhien (9 kha nang) de bot khong dung cung 1 diem."""
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


def _do_daily_if_enabled(c, do_daily, label, on_status, party_name=None, is_leader=False,
                         should_stop=None):
    """Goi claim_daily_quests(heavy=True) + do_daily_dungeon() 1 LAN neu do_daily=True. Loi chi
    log, khong lam crash vong lap chinh (giong quy uoc _auto_claim_loop). Neu party_name duoc
    truyen (tuc dang chay trong 1 party THAT - Di Gioi/Train) -> set hook _o5_team_fn TRUOC khi
    goi claim_daily_quests, de _on_dungeon (client.py) goi lai _handle_o5_team lam BUOC CUOI cua
    claim_daily_quests (mirror PC's c._o5_team_fn set luc setup account)."""
    if not do_daily:
        return
    if party_name is not None and should_stop is not None:
        c._o5_team_fn = (lambda o5d: _handle_o5_team(c, party_name, label, is_leader, should_stop, o5d))
    try:
        c.claim_daily_quests(heavy=True)
    except Exception as e:
        log.warning("[%s] loi claim_daily_quests: %s", label, e)
    try:
        c.do_daily_dungeon()
    except Exception as e:
        log.warning("[%s] loi do_daily_dungeon: %s", label, e)


def _handle_o5_team(c, party_name, label, is_leader, should_stop, o5_done):
    """O5 PHO BAN TO DOI = BUOC CUOI claim_daily_quests (sau khi check + thu lam moi o khac). Mirror
    run_party_digioi.py:1405-1510 nguyen van, CHI doi khoa pidx -> party_name (+ dem so luong report
    thay vi so khop danh sach username - xem GHI CHU trong plan). Moi acc report o5 da xong chua.
    LEADER cho CA party report -> CHI khi MOI nguoi deu CHUA xong o5 -> tao + keo party vao danh
    (member auto-accept 0x2f 0f->03 + ready 0x2f 0b trong _on_dungeon, di theo leader).
    MEMBER PHAI CHO leader danh xong (o5_state != "idle" roi thanh "done") MOI duoc return - tiep
    tuc flow rieng. KHONG cho -> member tu chay tiep SONG SONG luc dang trong pho ban -> gui goi xen
    vao giua tran -> server khong nhan atk hop le -> ket cung (xac nhan qua log PC thuc te)."""
    st = party_state_mod._pstate(party_name)
    with st["lock"]:
        st["o5_done_by"][label] = bool(o5_done)
    has_leader = party_state_mod.leaders_for(party_name) != [] or is_leader
    if not is_leader and not has_leader:
        # Party KHONG CO LEADER BOT (vd "Khong co chu PT") -> KHONG AI se chay nhanh leader ben duoi
        # de set o5_state="done" -> cho vo ich toi khi timeout. Khong co leader thi khong co gi de
        # cho -> bo qua NGAY (mirror PC).
        return
    if not is_leader:
        _t0log = time.time()
        while True:
            if should_stop.call() or not c.running:
                return
            if time.time() - _t0log > 60:
                log.info("[%s] (member) CHO leader danh xong team dungeon...", label)
                _t0log = time.time()
            if st["reconnecting"]:
                log.warning("[%s] (member) dong doi ROT trong team dungeon -> RELOGIN thoat instance", label)
                try:
                    c.relogin()
                except Exception:
                    pass
                c._phoban_until = 0.0
                return
            with st["lock"]:
                state = st["o5_state"]
            if state == "done":
                c._phoban_until = 0.0
                return
            if not c.in_combat():
                try:
                    c.do_heal()
                except Exception:
                    pass
            time.sleep(2)
    # LEADER: cho CA party (gom minh) report o5. n_members KHONG tinh minh (leader) - + 1 cho tong so.
    total_members = st["n_members"] + 1
    if total_members < 2:
        return   # khong du party de danh pho ban to doi
    _t0log = time.time()
    while True:
        if should_stop.call() or not c.running:
            return
        with st["lock"]:
            reported = len(st["o5_done_by"]) + len(st["reconnecting"]) >= total_members
        if reported:
            break
        if time.time() - _t0log > 30:
            log.info("[%s] (LEADER) CHO ca party report o5 (%d/%d)...",
                     label, len(st["o5_done_by"]), total_members)
            _t0log = time.time()
        time.sleep(2)
    with st["lock"]:
        statuses = dict(st["o5_done_by"])
    if all(not v for v in statuses.values()):
        log.info("[%s] (LEADER) CA party (%d nguoi) chua xong o5 -> PHO BAN TO DOI LV20",
                 label, total_members)
        with st["lock"]:
            st["o5_state"] = "running"
        _dg0 = st["disc_gen"]
        try:
            ok = c.do_team_dungeon_lv20()
            if ok:
                c.claim_daily_quests(heavy=False)
            if st["disc_gen"] > _dg0 or st["reconnecting"]:
                log.warning("[%s] (LEADER) dong doi ROT trong team dungeon -> RELOGIN thoat instance", label)
                try:
                    c.relogin()
                except Exception:
                    pass
        finally:
            with st["lock"]:
                st["o5_state"] = "done"
                st["reform_gen"] += 1
    else:
        with st["lock"]:
            st["o5_state"] = "done"
        log.info("[%s] (LEADER) o5: KHONG phai ca party chua xong -> bo qua pho ban to doi", label)

# HAI che do hien tai:
#  - STAND_STILL ("ve thanh dung yen"): ve 1 thanh CO THAT (nguoi dung chon, xem
#    config.CITIES) roi dung yen tai do cho AN TOAN.
#  - STAY_LOGIN ("login o dau dung yen do"): KHONG teleport ve thanh - dung nguyen
#    tai vi tri luc login (mirror START_CITY_ID = 0 ben PC). Van tu danh khi vao tran,
#    van doi kenh duoc. Dung khi nick da o san 1 cho an toan, khong muon bi keo ve thanh.
# Ban dau tung dung 1 danh sach toa do CO DINH de "wander" ngau nhien, nhung toa do do
# KHONG biet ban do nao co tuong/chuong ngai gi - dung tren MOI map se khien nhan vat di
# xuyen tuong/ket ket. Cac che do "tu dong di lang thang theo map" that su can du lieu
# toa do di chuyen duoc theo TUNG map (train_maps.json/train_routes.json ben PC) - CHUA
# port sang Android, de danh cho ban sau.
RUN_MODE_STAND_STILL = "stand_still"
RUN_MODE_STAY_LOGIN = "stay_login"

# CLIENT dang chay theo username -> de UI (Kotlin) query kenh / doc kenh hien tai truc tiep.
_clients = {}


def get_channels(username):
    """Kotlin goi (background thread): query danh sach kenh tu client dang chay (~3s).
    Tra dict {"channels": [[ch, cur, cap], ...] sap xep theo ch, "current": int|None}
    hoac None neu account chua chay/khong lay duoc. request_channel_list gui 0x07 + cho
    S2C 0x07 (client._chan_event)."""
    c = _clients.get(username)
    if c is None or not getattr(c, "running", False):
        return None
    try:
        c.request_channel_list()
        c._chan_event.wait(3.0)
        chans = sorted([int(ch), int(cur), int(cap)]
                       for ch, (cur, cap) in c.channels.items())
        return {"channels": chans, "current": c.current_channel}
    except Exception:
        return None


def current_channel(username):
    """Kotlin goi: kenh dang o cua account (None neu chua switch/chua chay)."""
    c = _clients.get(username)
    return c.current_channel if c is not None else None


def _apply_cmd(c, cmd, on_status):
    """Thuc thi 1 lenh LIVE tu UI (mirror _do_manual_cmd ben PC). cmd = list/tuple
    ["channel", ch] | ["channel_auto"] | ["city", city_id, flag] | ["giftcode", code].
    Loi thi bao qua status, KHONG nem ra ngoai (giu vong lap song)."""
    try:
        kind = str(cmd[0])
        if kind == "channel":
            ch = int(cmd[1])
            c.switch_channel(ch)
            on_status.call("running", None, None, None, None, f"Da doi kenh -> {ch}")
        elif kind == "channel_auto":
            ch = c.pick_best_channel()
            on_status.call("running", None, None, None, None, f"Tu chon kenh -> {ch}")
        elif kind == "city":
            cid, flag = int(cmd[1]), int(cmd[2])
            ok = c.go_to_town(cid, flag)
            on_status.call("running", None, None, None, None,
                           f"Teleport thanh {cid}" + ("" if ok else " (chua ve duoc - co the dang ket tran)"))
        elif kind == "giftcode":
            code = str(cmd[1])
            ok = c.redeem_giftcode(code)
            on_status.call("running", None, None, None, None,
                           f"Da nhap giftcode '{code}'" if ok else f"Giftcode '{code}' khong hop le")
    except Exception as e:
        on_status.call("running", None, None, None, None, f"Loi thuc thi lenh: {e}")


def _auto_claim_loop(c, should_stop):
    """Thread phu: tu nhan mail/qua online/qua quan doan/van tieu - GIONG HET PC, KHONG co
    toggle bat-tat (VANTIEU_ENABLE=True co dinh trong config.py, khop bot/config.py). Chay
    doc lap voi vong lap combat chinh, moi loi chi log (khong lam crash run_train)."""
    # Quan doan: chi can goi 1 lan/ngay, ham tu co guard qua daily_state.json - goi som sau login.
    try:
        if not c.in_combat():
            c.claim_legion_gift()
    except Exception as e:
        log.warning("[%s] auto_claim: loi nhan qua quan doan: %s", c._label, e)
    next_vantieu_check = 0.0
    while c.running and not should_stop.call():
        time.sleep(30)   # 30s/vong - du nhanh voi mail/qua online, khong spam server
        if c.in_combat():
            continue   # giua tran de bi server bo qua/loi (giong luu y o _do_manual_cmd ben PC)
        try:
            c.claim_mail()
        except Exception as e:
            log.warning("[%s] auto_claim: loi nhan mail: %s", c._label, e)
        try:
            c.claim_online_gifts()
        except Exception as e:
            log.warning("[%s] auto_claim: loi nhan qua online: %s", c._label, e)
        if time.time() >= next_vantieu_check:
            try:
                nxt = c.do_van_tieu()
                next_vantieu_check = nxt if nxt is not None else time.time() + 1800
            except Exception as e:
                log.warning("[%s] auto_claim: loi van tieu: %s", c._label, e)
                next_vantieu_check = time.time() + 300   # loi -> thu lai sau 5p thay vi spam ngay


DIGIOI_KEEPALIVE_POLL = 3   # giay/vong keepalive (khop nhip 3s cua run_train, PC dung ~2-3s)


def _digioi_login_once(username, password, server_ip, server_id, party_name, is_reconnect):
    """1 lan login + vao world (KHONG bao reconnect - _run_digioi_supervised o duoi lo backoff).
    Tra (client, ok: bool). Mirror run_party_digioi.py:189-234 (vong 6 lan thu login/connect)."""
    c = None
    ok = False
    for attempt in range(6):
        try:
            cred = login_mod.login(username, password)
            c = GameClient(cred["user_id"], cred["access_token"], host=server_ip, server_id=server_id)
            c._label = username
            c.party_idx = party_name   # KHOA CHIA SE STATE - day la diem MAU CHOT: dung party_name (str)
                                        # thay vi pidx (int) nhu PC, moi may moc trong client.py
                                        # (_PARTY_ENTITIES/_PARTY_JOINED/invite_members/...) tu dong hoat
                                        # dong dung vi Python dict chap nhan bat ky khoa hashable nao.
            c.connect()
            for _ in range(15):
                if c.self_entity is not None and c.current_map is not None:
                    ok = True
                    break
                time.sleep(1)
            if ok:
                return c, True
            log.warning("[%s] chua vao world -> login lai...", username)
            c.close()
            time.sleep(5)
        except Exception as e:
            log.warning("[%s] login/connect loi (lan %d): %s", username, attempt + 1, e)
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
            time.sleep(5)
    return c, False


def _run_party_digioi_once(username, password, server_ip, server_id, party_name, is_leader,
                            is_picker, has_leader, do_daily, should_stop, on_status, is_reconnect):
    """1 lan chay (khong bao reconnect) - mirror run_account() nhanh is_digioi cua PC, CAT bo cac
    phan khong lien quan DG (train map/city/event/cleanbag, daily quest/dungeon/boss nang - da co
    sub-project #4 lo phan auto-claim). Tra 'reconnectable': bool (server dong dong ket noi khong
    phai do Stop -> nen thu login lai).
    has_leader: mirror PC's has_leader = config.PARTY_LEADER_ACC.get(pidx) is not None - True binh
    thuong (co 1 account duoc chi dinh leader), False khi party bat "Khong co chu PT" (moi account
    la member thuan tuy, cho leader NGOAI/tay moi - KHONG tu invite_members, KHONG cho st["invited"],
    va KHONG tu dong reconnect khi rot (giong PC: "KHONG co bot-leader -> nick rot CHET luon")."""
    st = party_state_mod._pstate(party_name)
    c, ok = _digioi_login_once(username, password, server_ip, server_id, party_name, is_reconnect)
    if not ok:
        on_status.call("error", None, None, None, None, "Login/vao world that bai (6 lan)")
        return False   # login that bai lien tuc -> supervisor van thu lai (giong PC)
    if is_leader:
        party_state_mod.set_leader_name(party_name, c.char_name or username)
    try:
        # 1) Pre-check het gio (mirror run_party_digioi.py:721-724)
        if not c.in_di_gioi() and c.digioi_minutes >= config.DIGIOI_LIMIT:
            on_status.call("stopped", None, None, None, None,
                           f"Da het gio Di Gioi hom nay ({c.digioi_minutes}/{config.DIGIOI_LIMIT} phut)")
            return False
        # 2) Vao DG that su TRUOC khi lam gi khac (mirror run_party_digioi.py:745-756)
        if not c.in_di_gioi() and not c.enter_di_gioi_safe():
            on_status.call("error", None, None, None, None, "Khong vao duoc Di Gioi (het gio?)")
            return False
        on_status.call("running", None, None, None, None, "Da vao Di Gioi")
        _do_daily_if_enabled(c, do_daily, username, on_status, party_name, is_leader, should_stop)
        # 3) Dong bo kenh (mirror run_party_digioi.py:369-409, ham noi bo do_channel_sync)
        if is_picker:
            st["channel_ready"].clear()
            st["channel"] = None
            need = st["n_members"] + 1
            ch = 0
            t0 = time.time()
            while c.running and not should_stop.call():
                r = c.pick_best_channel(need=need)
                if r is None:
                    time.sleep(3 if time.time() - t0 <= 30 else 60)
                    continue
                ch = r
                break
            st["channel"] = ch
            st["channel_ready"].set()
            on_status.call("running", None, None, None, None,
                           f"Chon kenh {ch} cho ca party" if ch else "Ca party giu nguyen 1 kenh")
        else:
            while not st["channel_ready"].wait(5):
                if not c.running or should_stop.call():
                    return False
            if st["channel"]:
                c.switch_channel(st["channel"])
                on_status.call("running", None, None, None, None, f"Da doi kenh chung -> {st['channel']}")
        # 4) Leader: moi + cho member + chay long vong. Member: cho duoc moi (hoac dung yen cho
        # leader NGOAI/tay moi neu khong co bot-leader - mirror run_party_digioi.py:935-951).
        c.flee_mode = False
        if is_leader:
            for _ in range(6):
                if not c.running or should_stop.call():
                    break
                c.invite_members(gap=1.0)
                # BAO MEMBER khoi cho moi (mirror run_party_digioi.py:875) - THIEU dong nay se khien
                # member cho vo han o "st['invited'].wait(2)" du leader da moi xong.
                st["invited"].set()
                time.sleep(4)
                if c.self_entity is not None:
                    if joined_member_count(party_name) >= st["n_members"]:
                        break
            st["invited"].set()
            try:
                c.set_party_strategist()
            except Exception:
                pass
            c.combat_ready()
            c.start_run_around()
            on_status.call("running", None, None, None, None, "(LEADER) Bat dau chay long vong")
        elif has_leader:
            on_status.call("running", None, None, None, None,
                           "(member) Cho vao party, dung yen tai safe")
            while not st["invited"].wait(2):
                if not c.running or should_stop.call() or st["leader_gone"].is_set():
                    return False
        else:
            # KHONG co bot-leader: KHONG cho st["invited"] (se khong bao gio duoc set) - dung yen
            # tai safe, auto-accept loi moi tu leader NGOAI/tay (client.py da auto-accept san qua
            # _on_party, xem _is_party_member/config.leaders_for).
            on_status.call("running", None, None, None, None,
                           "(member) KHONG co chu PT - dung yen tai safe, cho moi party tay")
        # 5) Vong giu song (mirror run_party_digioi.py:1296-1354, CHI phan DG + het gio per-account)
        out_cnt = 0
        last_dg = 0.0
        while c.running and not should_stop.call():
            time.sleep(DIGIOI_KEEPALIVE_POLL)
            if is_leader and st["leader_gone"].is_set():
                pass   # leader tu no khong tu thoat theo minh
            if (not is_leader) and st["leader_gone"].is_set():
                on_status.call("stopped", None, None, None, None, "Chu party da thoat -> member thoat theo")
                return False
            if c.current_map == config.DIGIOI_MAP_ID and time.time() - last_dg >= 30:
                last_dg = time.time()
                remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                on_status.call("running", None, None, None, None,
                               f"Di Gioi con lai {remain} phut (da o {c.digioi_minutes} phut)")
                if remain <= 0:
                    on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                    return False
                out_cnt = 0
            elif c.current_map is not None and c.current_map != config.DIGIOI_MAP_ID and not c.in_combat():
                out_cnt += 1
                if out_cnt >= 2:
                    remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                    if remain >= 2:
                        on_status.call("running", None, None, None, None,
                                       f"Bi day ra khoi Di Gioi (con {remain} phut) -> vao lai")
                        try:
                            c.enter_di_gioi_safe()
                        except Exception:
                            pass
                        out_cnt = 0
                    else:
                        on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                        return False
            else:
                out_cnt = 0
        return False   # should_stop -> khong can reconnect
    finally:
        # mirror run_party_digioi.py:1364-1367 - KHONG co bot-leader -> KHONG tu dong reconnect
        # (nick rot CHET luon, giu hanh vi cu, vi khong ai dieu phoi lai party khi vao lai).
        reconnectable = has_leader and (not should_stop.call()) and getattr(c, "server_closed", False)
        try:
            c.close()
        except Exception:
            pass
        if is_leader and not reconnectable:
            st["leader_gone"].set()
        if reconnectable:
            with st["lock"]:
                st["reconnecting"].add(username)
                st["disc_gen"] += 1
        else:
            st["reconnecting"].discard(username)


def run_party_digioi(username, password, server_ip, server_id, party_name, is_leader, is_picker,
                     has_leader, do_daily, should_stop, on_status):
    """Vong lap NGOAI CUNG: bao _run_party_digioi_once bang reconnect vo han (mirror
    _run_account_supervised, run_party_digioi.py:1512-1541). server dong ket noi (server_closed)
    va KHONG phai do Stop -> backoff 5s x3 -> 30s x10 -> 60s, thu lai VO HAN toi khi duoc hoac Stop.
    has_leader=False (party bat "Khong co chu PT") -> KHONG tu dong reconnect (mirror PC: nick rot
    CHET luon), vi khong ai dieu phoi lai party."""
    st = party_state_mod._pstate(party_name)
    st["n_members"] = max(st["n_members"], 0)
    attempt = 0
    is_reconnect = False
    while True:
        reconnectable = _run_party_digioi_once(username, password, server_ip, server_id, party_name,
                                               is_leader, is_picker, has_leader, do_daily,
                                               should_stop, on_status, is_reconnect)
        if should_stop.call() or not reconnectable:
            break
        attempt += 1
        wait = 5 if attempt <= 3 else (30 if attempt <= 13 else 60)
        on_status.call("connecting", None, None, None, None,
                       f"Server rot -> login lai sau {wait}s (lan {attempt})")
        for _ in range(wait):
            if should_stop.call():
                break
            time.sleep(1)
        if should_stop.call():
            break
        is_reconnect = True
    on_status.call("stopped", None, None, None, None, "Da dung")


def _run_digioi_solo_once(username, password, server_ip, server_id, do_daily, should_stop,
                          on_status, is_reconnect):
    """Di Gioi SOLO: KHONG lap party, KHONG dong bo kenh - moi acc doc lap hoan toan (mirror
    run_party_digioi.py:819-846,1302-1311). Tra reconnectable: bool."""
    c, ok = _digioi_login_once(username, password, server_ip, server_id, None, is_reconnect)
    if not ok:
        on_status.call("error", None, None, None, None, "Login/vao world that bai (6 lan)")
        return False
    try:
        if not c.in_di_gioi() and c.digioi_minutes >= config.DIGIOI_LIMIT:
            on_status.call("stopped", None, None, None, None,
                           f"Da het gio Di Gioi hom nay ({c.digioi_minutes}/{config.DIGIOI_LIMIT} phut)")
            return False
        if not c.in_di_gioi() and not c.enter_di_gioi_safe():
            on_status.call("error", None, None, None, None, "Khong vao duoc Di Gioi (het gio?)")
            return False
        _do_daily_if_enabled(c, do_daily, username, on_status)
        c.state.solo_multipet = True
        if c.has_hp_and_sp_items():
            c.flee_mode = False
            c.combat_ready()
            c.start_run_around()
            on_status.call("running", None, None, None, None, "Di Gioi SOLO - dang chay long vong")
        else:
            c.flee_mode = True
            on_status.call("running", None, None, None, None,
                           "Di Gioi SOLO - THIEU thuoc HP/SP, dung yen (khong chay long vong)")
        out_cnt = 0
        last_dg = 0.0
        while c.running and not should_stop.call():
            time.sleep(DIGIOI_KEEPALIVE_POLL)
            if c.current_map == config.DIGIOI_MAP_ID and time.time() - last_dg >= 30:
                last_dg = time.time()
                ok_items = c.has_hp_and_sp_items()
                if ok_items and c.flee_mode:
                    c.flee_mode = False
                    c.combat_ready()
                    c.start_run_around()
                    on_status.call("running", None, None, None, None,
                                   "Di Gioi SOLO: da co du thuoc -> chay tiep")
                elif not ok_items and not c.flee_mode:
                    c.flee_mode = True
                    on_status.call("running", None, None, None, None,
                                   "Di Gioi SOLO: HET thuoc HP/SP -> dung yen")
                remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                if remain <= 0:
                    on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                    return False
                out_cnt = 0
            elif c.current_map is not None and c.current_map != config.DIGIOI_MAP_ID and not c.in_combat():
                out_cnt += 1
                if out_cnt >= 2:
                    remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                    if remain >= 2:
                        try:
                            c.enter_di_gioi_safe()
                        except Exception:
                            pass
                        out_cnt = 0
                    else:
                        on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                        return False
            else:
                out_cnt = 0
        return False
    finally:
        reconnectable = (not should_stop.call()) and getattr(c, "server_closed", False)
        try:
            c.close()
        except Exception:
            pass


def run_digioi_solo(username, password, server_ip, server_id, do_daily, should_stop, on_status):
    """Vong ngoai reconnect vo han cho Di Gioi SOLO - cung backoff nhu run_party_digioi."""
    attempt = 0
    is_reconnect = False
    while True:
        reconnectable = _run_digioi_solo_once(username, password, server_ip, server_id,
                                              do_daily, should_stop, on_status, is_reconnect)
        if should_stop.call() or not reconnectable:
            break
        attempt += 1
        wait = 5 if attempt <= 3 else (30 if attempt <= 13 else 60)
        on_status.call("connecting", None, None, None, None,
                       f"Server rot -> login lai sau {wait}s (lan {attempt})")
        for _ in range(wait):
            if should_stop.call():
                break
            time.sleep(1)
        if should_stop.call():
            break
        is_reconnect = True
    on_status.call("stopped", None, None, None, None, "Da dung")


def _run_party_train_once(username, password, server_ip, server_id, party_name, map_key,
                          mob_index, is_leader, is_picker, has_leader, do_daily, should_stop,
                          on_status, is_reconnect):
    """1 lan chay (khong bao reconnect) - mirror run_account() nhanh train_on_map cua PC. Don gian
    hoa 1 diem CO CHU DICH so voi PC: KHONG co co che 'tam dung cho dung dong doi dang reconnect'
    (disc_gen/reconnecting) - moi account tu backoff-reconnect doc lap (giong Di Gioi), khi vao lai
    tu re-sync kenh/re-join party tu dau. Tra reconnectable: bool."""
    st = party_state_mod._pstate(party_name)
    tm = config.TRAIN_MAPS.get(map_key)
    route = config.TRAIN_ROUTES.get(map_key)
    if tm is None:
        on_status.call("error", None, None, None, None, f"Khong tim thay map train '{map_key}'")
        return False
    c, ok = _digioi_login_once(username, password, server_ip, server_id, party_name, is_reconnect)
    if not ok:
        on_status.call("error", None, None, None, None, "Login/vao world that bai (6 lan)")
        return False
    if is_leader:
        party_state_mod.set_leader_name(party_name, c.char_name or username)
    _do_daily_if_enabled(c, do_daily, username, on_status, party_name, is_leader, should_stop)
    try:
        sc = int(map_key)
        safe_list = tm.get("safe") or []
        mobs = tm.get("mobs") or []
        spot = mobs[mob_index] if (mob_index is not None and 0 <= mob_index < len(mobs)) else None
        # 1) Setup: dung map + co safe -> ra safe ngay. Sai map -> can route (xu ly o Step 4 _do_reform).
        if c.current_map == sc and safe_list:
            c.navigate_to(*_nearest_safe(c.pos, safe_list))
        need_route = c.current_map != sc
        # 2) Dong bo kenh (tai dung y het co che tu sub-project #1)
        if is_picker:
            st["channel_ready"].clear()
            st["channel"] = None
            need = st["n_members"] + (1 if has_leader else 0)
            ch = 0
            t0 = time.time()
            while c.running and not should_stop.call():
                r = c.pick_best_channel(need=need)
                if r is None:
                    time.sleep(3 if time.time() - t0 <= 30 else 60)
                    continue
                ch = r
                break
            st["channel"] = ch
            st["channel_ready"].set()
        else:
            while not st["channel_ready"].wait(5):
                if not c.running or should_stop.call():
                    return False
            if st["channel"]:
                c.switch_channel(st["channel"])
        # 3) Neu sai map (can route) hoac vua sync kenh xong -> dung ham reform chung de dua ca
        # party toi diem quai (mirror PC goi _do_reform(to_spot=False) khi login sai map, roi flow
        # thuong se lap party/di spot; o day gop lam 1 buoc luon cho gon).
        if need_route or not safe_list:
            ok_reform = _reform_to_spot(c, st, party_name, route, spot, is_leader, has_leader,
                                        do_daily, should_stop, on_status, username)
            if not ok_reform:
                return False
        else:
            # Dung map, co safe -> chi can lap party (khong can route) roi di ra spot.
            c.flee_mode = False
            if is_leader:
                for _ in range(6):
                    if not c.running or should_stop.call():
                        break
                    c.invite_members(gap=1.0)
                    st["invited"].set()
                    time.sleep(4)
                    if joined_member_count(party_name) >= st["n_members"]:
                        break
                st["invited"].set()
                try:
                    c.set_party_strategist()
                except Exception:
                    pass
                _abs = lambda: should_stop.call() or not c.running
                if spot:
                    c.navigate_to(*_jitter(spot), flee=False, abort=_abs)
                c.combat_ready()
                c.flee_mode = False
                on_status.call("running", None, None, None, None, "(LEADER) Da ra diem quai, dung cay danh")
            elif has_leader:
                on_status.call("running", None, None, None, None, "(member) Cho vao party")
                while not st["invited"].wait(2):
                    if not c.running or should_stop.call() or st["leader_gone"].is_set():
                        return False
                c.combat_ready()
                c.flee_mode = False
            else:
                on_status.call("running", None, None, None, None,
                               "(member) KHONG co chu PT - dung yen tai safe, cho moi party tay")
        # 4) Vong giu song: phat hien bi vang khoi map train -> reform.
        out_cnt = 0
        while c.running and not should_stop.call():
            time.sleep(DIGIOI_KEEPALIVE_POLL)
            if (not is_leader) and has_leader and st["leader_gone"].is_set():
                on_status.call("stopped", None, None, None, None, "Chu party da thoat -> member thoat theo")
                return False
            if c.current_map == sc:
                out_cnt = 0
            elif not c.in_combat():
                out_cnt += 1
                if out_cnt >= 2:
                    on_status.call("running", None, None, None, None,
                                   "Bi vang khoi map train -> dang reform (dua ca party ve gom lai)")
                    ok_reform = _reform_to_spot(c, st, party_name, route, spot, is_leader, has_leader,
                                                do_daily, should_stop, on_status, username)
                    if not ok_reform:
                        return False
                    out_cnt = 0
        return False
    finally:
        reconnectable = has_leader and (not should_stop.call()) and getattr(c, "server_closed", False)
        try:
            c.close()
        except Exception:
            pass
        if is_leader and not reconnectable:
            st["leader_gone"].set()
        if reconnectable:
            with st["lock"]:
                st["reconnecting"].add(username)
                st["disc_gen"] += 1
        else:
            st["reconnecting"].discard(username)


def _reform_to_spot(c, st, party_name, route, spot, is_leader, has_leader, do_daily, should_stop,
                    on_status, label):
    """Dua CA party ve thanh gom nhau -> giai tan + lap lai -> keo qua route (neu co) -> ra safe ->
    ra diem quai. Mirror _do_reform cua PC (run_party_digioi.py:411-518), CAT phan boss quan doan/
    dungeon-tai-thanh (da co _do_daily_if_enabled goi rieng, khong lap lai o day de tranh goi trung
    do_daily nhieu lan moi vong reform). Tra False neu bi should_stop/mat ket noi giua chung."""
    if route is None:
        on_status.call("error", None, None, None, None, "Khong co route cho map nay - khong the reform")
        return False
    fc = int(route.get("from_city", 0))
    ff = int(route.get("city_flag", 0))
    c.flee_mode = True
    if is_leader:
        c.leave_party()
        reset_party_joined(party_name)
    if fc:
        try:
            c.go_to_town(fc, ff)
        except Exception as e:
            log.warning("[%s] reform: loi ve thanh: %s", label, e)
    # Re-sync kenh (khong chi switch ve kenh cu - server co the da day kenh cu day/khac)
    if is_leader:
        st["channel_ready"].clear()
        st["channel"] = None
        need = st["n_members"] + (1 if has_leader else 0)
        ch = 0
        t0 = time.time()
        while c.running and not should_stop.call():
            r = c.pick_best_channel(need=need)
            if r is None:
                time.sleep(3 if time.time() - t0 <= 30 else 60)
                continue
            ch = r
            break
        st["channel"] = ch
        st["channel_ready"].set()
    else:
        while not st["channel_ready"].wait(5):
            if not c.running or should_stop.call():
                return False
        if st["channel"]:
            c.switch_channel(st["channel"])
    if is_leader:
        while joined_member_count(party_name) < st["n_members"]:
            if should_stop.call() or not c.running:
                return False
            try:
                c.invite_members(gap=1.0)
            except Exception:
                pass
            st["invited"].set()
            time.sleep(4)
        st["invited"].set()
        try:
            c.set_party_strategist()
        except Exception:
            pass
        _abs = lambda: should_stop.call() or not c.running
        for stp in route.get("steps", []):
            if _abs():
                return False
            t1 = time.time()
            while c.in_combat(idle_secs=3.0) and not _abs() and time.time() - t1 < 60:
                time.sleep(0.5)
            if "gate" in stp:
                if not c._enter_gate(int(stp["x"]), int(stp["y"]), int(stp["gate"])):
                    break
            else:
                c.move_to(int(stp["move"][0]), int(stp["move"][1]))
                time.sleep(0.5)
        dest_map = int(route.get("dest_map", 0))
        if c.current_map == dest_map and not _abs():
            tm2 = config.TRAIN_MAPS.get(str(dest_map)) or {}
            safe_list = tm2.get("safe") or []
            if safe_list:
                c.navigate_to(*_jitter(_nearest_safe(c.pos, safe_list)), flee=False, abort=_abs)
            if spot:
                c.navigate_to(*_jitter(spot), flee=False, abort=_abs)
        c.combat_ready()
        c.flee_mode = False
    else:
        while not st["invited"].wait(2):
            if not c.running or should_stop.call() or st["leader_gone"].is_set():
                return False
        for _ in range(15):
            if not c.running or should_stop.call():
                break
            time.sleep(1)
        c.combat_ready()
        c.flee_mode = False
    return True


def run_party_train(username, password, server_ip, server_id, party_name, map_key, mob_index,
                    is_leader, is_picker, has_leader, do_daily, should_stop, on_status):
    """Vong lap NGOAI CUNG: bao _run_party_train_once bang reconnect vo han (cung backoff
    5s x3 -> 30s x10 -> 60s nhu run_party_digioi/run_digioi_solo)."""
    st = party_state_mod._pstate(party_name)
    st["n_members"] = max(st["n_members"], 0)
    attempt = 0
    is_reconnect = False
    while True:
        reconnectable = _run_party_train_once(username, password, server_ip, server_id, party_name,
                                              map_key, mob_index, is_leader, is_picker, has_leader,
                                              do_daily, should_stop, on_status, is_reconnect)
        if should_stop.call() or not reconnectable:
            break
        attempt += 1
        wait = 5 if attempt <= 3 else (30 if attempt <= 13 else 60)
        on_status.call("connecting", None, None, None, None,
                       f"Server rot -> login lai sau {wait}s (lan {attempt})")
        for _ in range(wait):
            if should_stop.call():
                break
            time.sleep(1)
        if should_stop.call():
            break
        is_reconnect = True
    on_status.call("stopped", None, None, None, None, "Da dung")


def run_train(username: str, password: str, server_ip: str, server_id: int,
              run_mode: str, city_key: str, should_stop, on_status, get_cmd=None,
              do_daily: bool = True):
    """Chay den khi should_stop() tra True hoac loi khong the phuc hoi.
    on_status(state: str, hp, sp, hp_max, sp_max, message: str) goi moi khi trang
    thai doi (state: "connecting"|"running"|"error"|"stopped").
    run_mode:
      - RUN_MODE_STAND_STILL: ve thanh (city_key) roi dung yen.
      - RUN_MODE_STAY_LOGIN: KHONG ve thanh - dung nguyen tai cho login (mirror
        START_CITY_ID=0 ben PC). Van tu danh + doi kenh duoc.
    city_key: key trong config.CITIES (vd "trac_quan") - chi dung o mode STAND_STILL.
    Neu go_to_town that bai, van tiep tuc treo cay tai vi tri hien tai (KHONG return
    loi) - chi bao qua on_status de nguoi dung biet."""
    on_status.call("connecting", None, None, None, None, "Dang dang nhap...")
    try:
        cred = login_mod.login(username, password)
    except Exception as e:
        on_status.call("error", None, None, None, None, f"Login loi: {e}")
        return

    try:
        c = GameClient(cred["user_id"], cred["access_token"], host=server_ip,
                        server_id=server_id)
        c._label = username
        c.connect()
        _clients[username] = c   # de UI query kenh / doc kenh hien tai
    except Exception as e:
        on_status.call("error", None, None, None, None, f"Ket noi loi: {e}")
        return

    _do_daily_if_enabled(c, do_daily, username, on_status)

    # go_to_town (train_bot/client.py, copy nguyen tu bot PC) tu xu ly: cho het tran
    # truoc khi teleport, thoat Di Gioi neu dang o do, lap lai toi khi xac nhan da
    # doi map. Day la ham THAT da chay on dinh tren PC, KHONG tu viet lai logic teleport.
    # Neu ve thanh that bai (vd dang ket tran qua lau) -> KHONG dung han, van treo cay
    # tai vi tri hien tai, chi ghi canh bao vao message cua trang thai "running" ben
    # duoi (tranh phat 1 trang thai "error" thoang qua roi bi de ngay, mat thong tin).
    warning = ""
    if run_mode == RUN_MODE_STAY_LOGIN:
        # "login o dau dung yen do" -> KHONG teleport ve thanh (mirror START_CITY_ID=0 PC).
        warning = "(che do LOGIN O DAU DUNG YEN DO - khong ve thanh)"
    else:
        city_info = config.CITIES.get(city_key)
        if city_info is not None:
            city_id, flag = city_info
            on_status.call("connecting", None, None, None, None, "Dang ve thanh...")
            try:
                ok = c.go_to_town(city_id, flag)
                if not ok and c.running:
                    warning = "(Chua ve duoc thanh - co the dang ket tran, van treo cay tai vi tri hien tai)"
            except Exception as e:
                warning = f"(Loi ve thanh: {e} - van treo cay tai vi tri hien tai)"
        else:
            warning = f"(Khong tim thay thanh '{city_key}' - dung yen tai vi tri hien tai)"

    on_status.call("running", None, None, None, None, f"Da vao game, dang treo cay (dung yen) {warning}".strip())

    threading.Thread(target=_auto_claim_loop, args=(c, should_stop), daemon=True).start()

    while c.running and not should_stop.call():
        time.sleep(3)   # 3s giua moi lan cap nhat trang thai UI - du nhanh, khong spam callback
        # LENH LIVE tu UI (doi kenh / teleport thanh) - poll moi vong, giong cmd_gen ben PC
        if get_cmd is not None:
            try:
                cmd = get_cmd.call()
            except Exception:
                cmd = None
            if cmd is not None:
                _apply_cmd(c, cmd, on_status)
        try:
            ch = c.state.char
            if ch is not None:
                on_status.call("running", ch.hp, ch.sp, ch.hp_max, ch.sp_max, "")
        except Exception as e:
            # vd chua nhan du 0x0b/0x33 -> state chua day du. KHONG de crash ca vong lap
            # (muc tieu: moi loi bao qua callback, khong bao gio nem exception ra ngoai
            # run_train() - BotForegroundService dua vao dieu nay de khong crash Service).
            on_status.call("error", None, None, None, None, f"Loi doc trang thai: {e}")
            break

    _clients.pop(username, None)
    c.close()
    on_status.call("stopped", None, None, None, None, "Da dung")


class _CallableStub:
    """Boc 1 ham Python thanh doi tuong co .call(...) - mo phong dung HOP DONG API
    ma phia Kotlin se dung that (object { fun call(...) }), de test thuan Python
    van di qua CHINH XAC duong goi .call() nhu production, khong test rieng 1
    duong khac (goi truc tiep) roi tuong da dung."""
    def __init__(self, fn):
        self._fn = fn

    def call(self, *args):
        return self._fn(*args)


def run_train_sync_for_test(username: str, password: str, server_ip: str, server_id: int) -> str:
    """Wrapper THUAN PYTHON cho instrumented test: goi run_train() voi callback thu thap
    trang thai vao list noi bo, boc qua _CallableStub de di dung qua .call() convention
    (xem docstring module ve ly do khong goi obj(...) truc tiep).
    Tra ve state CUOI CUNG da ghi nhan ("error"/"stopped"/"running"/...). should_stop=True
    ngay lap tuc -> neu login/connect thanh cong thi vong lap chinh thoat ngay sau 1 vong,
    khong treo test that."""
    states = []

    def _on_status(state, hp, sp, hp_max, sp_max, message):
        states.append(state)

    should_stop = _CallableStub(lambda: True)
    on_status = _CallableStub(_on_status)
    run_train(username, password, server_ip, server_id, RUN_MODE_STAND_STILL, "trac_quan",
              should_stop, on_status)
    return states[-1] if states else ""


class _FakeClientForTest:
    """CHI DUNG TRONG TEST: gia lap GameClient toi thieu de kiem tra _apply_cmd dinh tuyen
    dung lenh 'giftcode' toi redeem_giftcode(), khong can ket noi mang that."""
    _label = "test"

    def __init__(self):
        self.last_giftcode = None
        self.running = True

    def redeem_giftcode(self, code):
        self.last_giftcode = code
        return True


def handle_o5_team_member_returns_when_done_for_test(party_name: str) -> bool:
    """CHI DUNG TRONG TEST: goi _handle_o5_team voi is_leader=False, xac nhan return ngay khi
    o5_state da la 'done' tu truoc (khong bi treo cho vo han)."""
    party_state_mod._pstate(party_name)["o5_state"] = "done"
    fake = _FakeClientForTest()
    fake.running = True
    should_stop = _CallableStub(lambda: False)
    _handle_o5_team(fake, party_name, "test-member", False, should_stop, False)
    return True   # khong treo -> ham tra ve duoc toi day


def apply_giftcode_cmd_for_test(code: str) -> str:
    """Wrapper THUAN PYTHON cho instrumented test: goi _apply_cmd voi lenh giftcode qua
    _FakeClientForTest, tra ve message cuoi cung ghi nhan qua on_status."""
    messages = []

    def _on_status(state, hp, sp, hp_max, sp_max, message):
        messages.append(message)

    fake = _FakeClientForTest()
    on_status = _CallableStub(_on_status)
    _apply_cmd(fake, ["giftcode", code], on_status)
    return messages[-1] if messages else ""
