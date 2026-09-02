"""Protocol and bounded battle loop for the 40 NPC event."""

import datetime
import logging
import time


log = logging.getLogger("bot")


def in_event_window(now=None):
    """Event 40NPC mo: Thu 2 / Thu 4 / Thu 6 (weekday 0,2,4), 20:00 <= gio < 22:00."""
    now = now or datetime.datetime.now()
    return now.weekday() in (0, 2, 4) and 20 <= now.hour < 22


def _end_npc_dialog(client, sleep_fn):
    """Thoat dialog NPC 40 sach se (chon KHONG + 2 advance) truoc khi roi di doi thuong."""
    client.send(OP_DIALOG, CHOOSE_NO)
    sleep_fn(0.5)
    client.send(OP_DIALOG, ADVANCE)
    sleep_fn(0.5)
    client.send(OP_DIALOG, ADVANCE)
    sleep_fn(0.5)

OP_DIALOG = 0x14
OP_EVENT = 0x20
OPEN_EVENT = b"\x02\x00\x08"
OPEN_NPC = b"\x01\x00\x05\x00"
ADVANCE = b"\x06\x00"
CHOOSE_YES = b"\x09\x00\x1e"
CHOOSE_NO = b"\x09\x00\x1f"


def is_repeat_prompt(opcode, packet):
    return opcode == 0x41 and len(packet) >= 10 and packet[7:10] == b"\x0a\x00\x01"


def is_repeat_dialog(opcode, packet):
    return (
        opcode == OP_DIALOG
        and len(packet) >= 11
        and packet[7:9] == b"\x01\x00"
        and packet.endswith(b"\x03\x00")
    )


def party_defeated(units):
    known = [u for u in units.values() if getattr(u, "hp_max", 0) > 0]
    alive = sum(1 for u in known if getattr(u, "hp", 0) > 0)
    return bool(known) and alive == 0, alive, len(known)


def _active(client, stop_event):
    return client.running and not stop_event.is_set()


# So lan poll cho prompt "danh tiep?" sau tran (x poll_interval=0.4s = 180s). Vong cho nay om CA
# TRAN KE TIEP chu khong chi cai prompt, ma 1 tran 40NPC chay ~100s (do P42 02/09: tran 10 tu
# 20:31:42 den 20:33:15) -> de ngan qua thi tran dai binh thuong bi ket luan nham la thua.
CHECK_CHO_PROMPT = 450

# So lan thu MO LAI NPC khi khong vao duoc tran / khong thay prompt ma KHONG co bang chung thua.
# Bo cuoc ngay tu lan dau la keo ca party ra khoi event vi mot cai truc trac thoang qua.
MAX_THU_LAI = 3


def _da_thua_that(client):
    """CO bang chung thua: chot HP cuoi doc duoc trong tran cho thay quan nha da nam het.

    `_npc40_hp_snap` = `(defeated, alive, total)`, do `client` chot lien tuc trong tran (xem
    `client.py`: `state.allies` bi `clear()` moi `0x34` nen doc o thoi diem sau tran la rong).
    Reset ve None moi khi tran MOI bat dau -> khong an nham chot cua tran truoc.
    """
    snap = getattr(client, "_npc40_hp_snap", None)
    return bool(snap and snap[0])


def _ket_thuc(client, on_loss, sleep_fn, lbl, ly_do):
    """Ngung danh: bao party, dong dialog NPC, bat co di doi thuong. Tra True (da xu ly xong).

    Dung chung cho 3 loi ra: het gio (qua 22h) / thua 2 tran lien tiep / thua sach (khong co prompt).
    Truoc day moi loi ra tu lam mot kieu, va loi ra "thua sach" thi KHONG lam gi ca.
    """
    on_loss()   # bao party ngung mo battle + tan hang
    if in_event_window():
        # Server chi cho doi thuong sau 22h. Thoat som KHONG mat gi: chay lai bot sau 22h van nhan
        # binh thuong (user xac nhan 31/08).
        client._npc40_bo_thuong = True
        log.warning("[%s] 40NPC: %s -> THOAT LUON. Chua toi 22h nen chua doi thuong duoc; "
                    "chay lai bot sau 22h la nhan (khong mat gi)", lbl, ly_do)
    else:
        log.warning("[%s] 40NPC: %s -> doi thuong roi thoat", lbl, ly_do)
    _end_npc_dialog(client, sleep_fn)
    client._npc40_done = True
    return True


def _wait_counter(client, name, previous, stop_event, sleep_fn, poll_interval, checks):
    for _ in range(checks):
        if not _active(client, stop_event):
            return False
        if getattr(client, name) > previous:
            return True
        sleep_fn(poll_interval)
    return getattr(client, name) > previous


def _advance_to_battle(client, previous, stop_event, sleep_fn, poll_interval, max_advances):
    for _ in range(max_advances):
        if not _active(client, stop_event):
            return False
        if client._battle_start_seq > previous:
            return True
        client.send(OP_DIALOG, ADVANCE)
        # Poll SAT (0.1s) sau moi advance -> DUNG NGAY khi tran bat dau (0x34 -> _battle_start_seq++).
        # KHONG ngu ca poll_interval roi moi check: tran sau chi can 1 advance, ngu lau se gui THEM 1
        # advance LOT VAO tran vua spawn -> server tra 0x14 08 03 roi 0x00 KICK (bug leader rot sau
        # vai tran, 40NPC 2026-07-29). Poll toi da ~poll_interval, buoc 0.1s.
        waited = 0.0
        while waited < max(0.1, poll_interval):
            if not _active(client, stop_event):
                return False
            if client._battle_start_seq > previous:
                return True
            sleep_fn(0.1)
            waited += 0.1
    return client._battle_start_seq > previous


def _open_event_battle(client, previous, stop_event, sleep_fn, poll_interval, max_advances):
    """Mo NPC va vao battle tu trang thai ngoai dialog (fresh hoac dang giua event)."""
    client._npc40_last_dialog = ""
    client.send(OP_EVENT, OPEN_EVENT)
    sleep_fn(0.6)
    client.send(OP_DIALOG, OPEN_NPC)
    sleep_fn(0.8)
    dialog = getattr(client, "_npc40_last_dialog", "") or ""
    if not (dialog.endswith("0200") or dialog.endswith("0300")):
        client.send(OP_DIALOG, ADVANCE)
        sleep_fn(0.8)
    client.send(OP_DIALOG, CHOOSE_YES)
    return _advance_to_battle(
        client, previous, stop_event, sleep_fn, poll_interval, max_advances,
    )


def run_loop(client, point, stop_event, on_loss, before_repeat=None, sleep_fn=time.sleep,
             poll_interval=0.4, max_advances=30):
    """Run the leader-only 40 NPC loop. Returns only when stopped, lost, or timed out."""
    # DI TOI NPC: thu lai vai lan (dinh quai chan duong, lenh move roi...) truoc khi bo.
    for _lan in range(1, MAX_THU_LAI + 1):
        if client.navigate_to(int(point[0]), int(point[1]), flee=False):
            break
        if not _active(client, stop_event):
            return False
        log.warning("[%s] 40NPC: khong toi duoc NPC %s (lan %d/%d)",
                    getattr(client, "_label", "?"), tuple(point), _lan, MAX_THU_LAI)
        sleep_fn(2.0)
    else:
        return False
    if not _active(client, stop_event):
        return False
    # CHO SCENE SETTLE sau khi toi NPC truoc khi mo dialog: leader vua di toi (910,290) -> mo NPC
    # NGAY (1s sau) trong khi scene chua on (goi 0x14 08 2a scene-ack VE SAU khi da mo) -> server
    # nhan tuong tac luc scene chua settle -> 0x14 08 01 -> 0x00 KICK (xac nhan gui-cuoi/nhan-cuoi
    # 2026-07-29: mo 0x20 020008 luc 21:28:27, scene-ack 08 2a MOI ve 21:28:28, kick 21:28:29).
    # Ban nguoi that dung SAN o NPC (scene da on) nen mo la an.
    client._wait_combat_clear(idle=1.0, cap=20.0)
    sleep_fn(3.0)
    if not _active(client, stop_event):
        return False
    # CHI rearm (0x41 san sang) - KHONG combat_ready() (= full _login_setup gom 0x57/0x01/0x62
    # nhan-thuong-ngay/0x7c len thuyen). Gui lai chuoi login NGAY truoc khi mo NPC event -> server
    # loan state luc tran spawn -> 0x14 08 01 -> 0x00 KICK leader (xac nhan tu gui-cuoi/nhan-cuoi
    # luc rot 2026-07-29; ban nguoi that KHONG he gui chuoi login truoc NPC).
    client.rearm_ready()

    battle_seq = client._battle_start_seq
    prompt_seq = client._npc40_prompt_seq
    # ADVANCE THICH UNG theo page dialog server tra (event 40NPC TICH LUY 40 tran -> account co the
    # dang GIUA event, KHONG phai luon fresh):
    #  - FRESH: OPEN_NPC -> page1 (chua choice, hex ket thuc bang counter ...4e) -> CAN advance 1 lan
    #    de ra page2-choice (...0200) roi moi chon.
    #  - GIUA-EVENT: OPEN_NPC -> prompt "danh tiep?" (...0300) = DA la choice -> chon LUON, advance
    #    THUA se lech state -> server 0x14 08 01 -> 0x00 KICK (xac nhan capture: bot gui advance thua
    #    luc page 0300 -> rot 2026-07-29). Phan biet: page choice-ready ket thuc bang '0200'/'0300'.
    # MO TRAN DAU: thu lai vai lan truoc khi bo. Bo ngay lan dau la ca party mat nguyen van event vi
    # mot lan hut goi (goi 0x41/0x14 den muon, scene chua on...).
    for _lan in range(1, MAX_THU_LAI + 1):
        if _open_event_battle(
                client, client._battle_start_seq, stop_event, sleep_fn, poll_interval, max_advances):
            break
        if not _active(client, stop_event):
            return False
        log.warning("[%s] 40NPC: mo tran dau timeout (lan %d/%d)",
                    getattr(client, "_label", "?"), _lan, MAX_THU_LAI)
        client._wait_combat_clear(idle=1.0, cap=20.0)
        _end_npc_dialog(client, sleep_fn)
    else:
        return False

    consec_loss = 0
    thu_lai = 0     # so lan lien tiep khong vao duoc tran (KHONG co dau hieu thua)
    while _active(client, stop_event):
        lbl = getattr(client, "_label", "?")
        if not _wait_counter(
                client, "_npc40_prompt_seq", prompt_seq, stop_event,
                sleep_fn, poll_interval, CHECK_CHO_PROMPT):
            # `_wait_counter` tra False o HAI tinh huong khac han nhau:
            #   a) HET SO LAN CHO   -> that su khong co prompt -> THUA sach.
            #   b) `not _active()`  -> acc BI ROT / GUI Stop -> tra False NGAY LAP TUC.
            # (b) KHONG phai thua. Coi nham (b) la thua thi leader dat `_npc40_done` -> coordinator
            # bat `go_claim` -> CA 4 MEMBER dang khoe manh lap tuc "40NPC xong -> di doi thuong +
            # thoat game" du chua danh tran nao.
            # Da xay ra that (party 6 tao_thao, 02/09): leader bi kick ma 47 luc 21:43:26 (17s sau
            # khi vao tran DAU), 21:43:31 ca 4 member bo chay sang map 12003; leader login lai luc
            # 21:43:35 tu chon kenh 10 trong khi member con o kenh 5 -> nhin ra la "party loan kenh".
            if not _active(client, stop_event):
                return False        # rot/Stop -> de supervisor login lai, KHONG phai thua
            # THUA SACH = server KHONG gui prompt "danh tiep?" -> `_npc40_last_defeated` khong bao gio
            # duoc set -> `consec_loss` khong tang -> luat "thua 2 tran" khong chay. Truoc day cho
            # het gio roi `return False` CAM: `on_loss()` khong duoc goi nen member khong biet ma tan
            # hang -> ca party dung chet di (P42 02/09: leader dung (910,290), 4 member (370,680) tu
            # 20:37 tro di).
            #
            # Nhung "khong co prompt" MOT MINH no KHONG du de ket luan thua - phai co BANG CHUNG
            # (chot HP cho thay quan nha nam het). Khong co bang chung thi coi la truc trac va THU
            # MO LAI, dung keo ca party ra khoi event vi mot lan hut goi.
            _thoi_gian = CHECK_CHO_PROMPT * poll_interval
            if _da_thua_that(client):
                log.warning("[%s] 40NPC: khong co prompt sau %.0fs VA chot HP cho thay quan nha da "
                            "nam het -> THUA", lbl, _thoi_gian)
                return _ket_thuc(client, on_loss, sleep_fn, lbl, "thua sach (khong co prompt)")
            thu_lai += 1
            if thu_lai > MAX_THU_LAI:
                log.warning("[%s] 40NPC: %d lan lien tiep khong vao lai duoc tran ma cung khong co "
                            "dau hieu thua -> bo cuoc", lbl, thu_lai)
                return _ket_thuc(client, on_loss, sleep_fn, lbl, "khong vao lai duoc tran")
            log.warning("[%s] 40NPC: khong co prompt sau %.0fs nhung quan nha VAN SONG -> thu mo lai "
                        "NPC (lan %d/%d)", lbl, _thoi_gian, thu_lai, MAX_THU_LAI)
            client._wait_combat_clear(idle=1.0, cap=20.0)
            _end_npc_dialog(client, sleep_fn)
            _open_event_battle(client, client._battle_start_seq, stop_event,
                               sleep_fn, poll_interval, max_advances)
            continue

        thu_lai = 0     # co prompt = van thong -> xoa bo dem truc trac

        consec_loss = (consec_loss + 1) if client._npc40_last_defeated else 0
        past_window = not in_event_window()   # sau MOI tran: check qua 22h chua

        # THUA 2 TRAN LIEN TIEP -> THOAT LUON (user chot 31/08: "thua 2 lan cu thoat di"). Truoc day
        # dung yen trong map cho toi 22h -> nhin tu ngoai khong phan biet duoc voi treo (user:
        # "dung yen tai cho thi t cha biet the nao ma lan"). Xem `_ket_thuc` ve chuyen doi thuong.
        if consec_loss >= 2:
            return _ket_thuc(client, on_loss, sleep_fn, lbl, "THUA 2 tran lien tiep")
        if past_window:
            return _ket_thuc(client, on_loss, sleep_fn, lbl, "het gio event (qua 22h)")

        if client._npc40_last_defeated:
            log.warning("[%s] 40NPC: thua 1 tran (lien tiep=%d) -> danh tiep", lbl, consec_loss)

        prompt_seq = client._npc40_prompt_seq
        battle_seq = client._battle_start_seq
        # HOI FULL HP/SP ca party sau MOI tran roi moi danh tiep (user chot 02/09) - GIONG 2K
        # (`floor_crawl._fight_one`) va Loan dau (`loandau.run_loop`). KHONG duoc gac sau dieu kien
        # nao het.
        #
        # Truoc day gac sau `casualties = alive < total` (t tu them 03/08 de tiet kiem ~5s/tran bang
        # duong tat CHOOSE_YES+advance). Hai cai sai:
        #   1. Con song nhung THOI THOP thi khong hoi -> vao tran sau chac chet.
        #   2. `alive/total` doc tu `state.allies` chi dem char CUA CHINH LEADER (log P42 02/09:
        #      `alive=1/1` du party 5 acc + pet) -> ke ca y dinh "hoi khi co dua chet" cung chi dung
        #      khi dung char leader chet.
        # Hau qua that (P42, luu_bi, 02/09): het tran 10 leader con 27/796 HP -> `casualties=False`
        # -> vao thang tran 11 -> char + pet chet sach tu luot 4.
        #
        # PHAI dong dialog TRUOC khi dung item: dung item luc prompt con mo -> server tra `08 0001`
        # roi KICK (xem `_before_npc40_repeat` trong run_party_digioi).
        alive = getattr(client, "_npc40_last_alive", 0)
        total = getattr(client, "_npc40_last_total", 0)
        log.info("[%s] 40NPC: het tran (con %d/%d) -> dong dialog, hoi FULL party roi mo lai NPC",
                 lbl, alive, total)
        _end_npc_dialog(client, sleep_fn)
        if before_repeat is not None:
            try:
                before_repeat()
            except Exception as exc:
                log.warning("[%s] 40NPC: loi cho party hoi phuc: %s", lbl, exc)
        # THU LAI NGAY tai cho khi khong vao duoc tran ke tiep. Truoc day `return False` ngay lan
        # dau -> mot lan hut goi la ca party mat phan con lai cua event.
        ok = False
        for _lan in range(1, MAX_THU_LAI + 1):
            ok = _open_event_battle(
                client, client._battle_start_seq, stop_event, sleep_fn, poll_interval, max_advances,
            )
            if ok or not _active(client, stop_event):
                break
            log.warning("[%s] 40NPC: vao tran tiep theo timeout (lan %d/%d) -> thu mo lai NPC",
                        lbl, _lan, MAX_THU_LAI)
            client._wait_combat_clear(idle=1.0, cap=20.0)
            _end_npc_dialog(client, sleep_fn)
        if not ok:
            if not _active(client, stop_event):
                return False        # rot/Stop giua chung -> KHONG phai thua
            return _ket_thuc(client, on_loss, sleep_fn, lbl, "khong vao lai duoc tran")
    return False
