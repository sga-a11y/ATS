"""Protocol and bounded battle loop for the 40 NPC event."""

import datetime
import logging
import time


log = logging.getLogger("bot")


def in_event_window(now=None):
    """Event 40NPC mo: Thu 2 / Thu 4 / Thu 6 (weekday 0,2,4), 20:00 <= gio < 22:00."""
    now = now or datetime.datetime.now()
    return now.weekday() in (0, 2, 4) and 20 <= now.hour < 22


def _wait_until_after_window(client, stop_event, sleep_fn):
    """Cho toi khi HET gio event (qua 22h) hoac bi STOP/rot. Dung khi thua 2 tran lien tiep ->
    dung yen trong map event, cho qua 22h roi moi di doi thuong."""
    while _active(client, stop_event) and in_event_window():
        sleep_fn(15)


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


def _confirm_repeat_battle(client, previous, stop_event, sleep_fn, poll_interval, checks):
    """Prompt sau tran chi can YES + 1 advance; cho server nap battle, tuyet doi khong spam advance."""
    client.send(OP_DIALOG, CHOOSE_YES)
    client.send(OP_DIALOG, ADVANCE)
    return _wait_counter(
        client, "_battle_start_seq", previous, stop_event,
        sleep_fn, poll_interval, checks,
    )


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
    if not client.navigate_to(int(point[0]), int(point[1]), flee=False):
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
    if not _open_event_battle(
            client, battle_seq, stop_event, sleep_fn, poll_interval, max_advances):
        log.warning("[%s] 40NPC: mo tran dau timeout", getattr(client, "_label", "?"))
        return False

    consec_loss = 0
    while _active(client, stop_event):
        if not _wait_counter(
                client, "_npc40_prompt_seq", prompt_seq, stop_event,
                sleep_fn, poll_interval, max_advances * 20):
            log.warning("[%s] 40NPC: cho dialog sau tran timeout", getattr(client, "_label", "?"))
            return False

        lbl = getattr(client, "_label", "?")
        consec_loss = (consec_loss + 1) if client._npc40_last_defeated else 0
        past_window = not in_event_window()   # sau MOI tran: check qua 22h chua

        # THUA 2 TRAN LIEN TIEP (con trong gio) -> dung yen trong map event, cho qua 22h.
        if consec_loss >= 2 and not past_window:
            log.warning("[%s] 40NPC: THUA 2 tran lien tiep -> dung yen trong map, cho qua 22h", lbl)
            on_loss()   # bao party ngung mo battle
            _wait_until_after_window(client, stop_event, sleep_fn)
            past_window = True

        # QUA 22H (het gio event) -> ket dialog + BAO di doi thuong (client._npc40_done).
        if past_window:
            log.info("[%s] 40NPC: het gio event (qua 22h) -> ket + di doi thuong", lbl)
            _end_npc_dialog(client, sleep_fn)
            client._npc40_done = True
            return True

        if client._npc40_last_defeated:
            log.warning("[%s] 40NPC: thua 1 tran (lien tiep=%d) -> danh tiep", lbl, consec_loss)

        prompt_seq = client._npc40_prompt_seq
        battle_seq = client._battle_start_seq
        alive = getattr(client, "_npc40_last_alive", 0)
        total = getattr(client, "_npc40_last_total", 0)
        casualties = total > 0 and alive < total
        if casualties:
            log.info("[%s] 40NPC: con %d/%d -> dong dialog, hoi party roi mo lai NPC",
                     lbl, alive, total)
            _end_npc_dialog(client, sleep_fn)
            if before_repeat is not None:
                try:
                    before_repeat()
                except Exception as exc:
                    log.warning("[%s] 40NPC: loi cho party hoi phuc: %s", lbl, exc)
            ok = _open_event_battle(
                client, battle_seq, stop_event, sleep_fn, poll_interval, max_advances,
            )
        else:
            ok = _confirm_repeat_battle(
                client, battle_seq, stop_event, sleep_fn, poll_interval, max_advances,
            )
        if not ok:
            log.warning("[%s] 40NPC: vao tran tiep theo timeout", getattr(client, "_label", "?"))
            return False
    return False
