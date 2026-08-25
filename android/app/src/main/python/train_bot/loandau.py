"""Loan dau loi dai (亂鬥擂台) - vong dang ky + danh, moi acc chay DOC LAP (khong party).

Nguon: `captures/loandau_20260825.pcap` + crack client. Xem `documents/LOAN_DAU.md`.

Cung map / cung NPC voi event 40 NPC (10991, diem (910,290)); khac dung 2 cho:
    chon event  `0x4d 03000300`   (40NPC la `03000400`)
    option NPC  `0x14 0100 03 00` (40NPC la `...0500`) - byte 03 = triggerID 3 = 亂鬥

KHAC 40NPC o cho quan trong: day la PvP, doi thu la NGUOI CHOI, va giua 2 tran KHONG phai
di lai (capture: lenh di chuyen cuoi cung o t=12.8s, ca 2 tran deu dang ky tu dung cho do).
"""
from __future__ import annotations

import datetime
import logging
import time


log = logging.getLogger("bot")

OP_DIALOG = 0x14
OP_EVENT = 0x20
OP_BATTLE = 0x0b
OP_VS_WIN = 0x25            # S:037-001 <團p勝場數> +玩家ID(8) +勝場數(2)

OPEN_EVENT = b"\x02\x00\x08"
OPEN_NPC = b"\x01\x00\x03\x00"
ADVANCE = b"\x06\x00"
CHOOSE_YES = b"\x09\x00\x1e"
CHOOSE_NO = b"\x09\x00\x1f"

# S:020-008 <事件結束> + kind(1). Hai kind gap trong capture:
END_REGISTERED = 0x2a       # phien dialog dong ngay sau khi chon -> DA DANG KY, bat dau cho
END_BATTLE = 0x26           # tran / phien thi dau ket thuc
BATTLE_CREATE = b"\xfa\x00"  # 0x0b sub 250 = <現行戰鬥現況> = TAO TRAN

# Cho ghep tran RAT lech nhau: capture do 336.6s (tran 1) va 0.6s (tran 2) - khong phai hang cho
# theo tung nguoi ma la cho toi luot mo man cua sanh. Nen moc dung that su la 22:00 (het gio
# event), con so duoi day chi la chot chan de khong treo vinh vien neu server im.
WAIT_BATTLE_SEC = 900.0
# So lan `0x14 0600` toi da sau khi chon. Capture can 3 lan; poll SAT sau moi lan va dung NGAY
# khi nhan `08 2a` - advance THUA lam lech state va bi server kick (bai hoc 40NPC 2026-07-29).
MAX_ADVANCE = 8


def in_event_window(now=None):
    """Loan dau mo: THU 3 (weekday 1), 20:00 <= gio < 22:00."""
    now = now or datetime.datetime.now()
    return now.weekday() == 1 and 20 <= now.hour < 22


# ---------- nhan dang goi (ham thuan, de test) ----------

def _body(pkt):
    """Than goi: header 7 byte `c0 91 [len 2B] 00 00 [opcode]`."""
    return pkt[7:]


def is_event_end(opcode, pkt, kind):
    b = _body(pkt)
    return opcode == OP_DIALOG and len(b) >= 3 and b[0] == 0x08 and b[1] == 0x00 and b[2] == kind


def is_registered(opcode, pkt):
    """Da dang ky xong, dang cho ghep tran."""
    return is_event_end(opcode, pkt, END_REGISTERED)


def is_battle_over(opcode, pkt):
    return is_event_end(opcode, pkt, END_BATTLE)


def dialog_page(opcode, pkt):
    """Hex page dialog NPC (`0x14 0100...`), None neu khong phai. Page ket bang '0200'/'0300'
    la DA o buoc chon -> chon luon, khong advance (cung quy tac 40NPC)."""
    b = _body(pkt)
    if opcode == OP_DIALOG and len(b) >= 2 and b[0] == 0x01 and b[1] == 0x00:
        return b.hex()
    return None


def is_choice_page(page):
    return bool(page) and (page.endswith("0200") or page.endswith("0300"))


def is_battle_create(opcode, pkt):
    return opcode == OP_BATTLE and _body(pkt)[:2] == BATTLE_CREATE


def o_cua_minh(pkt, self_entity):
    """(hang, cot) cua CHINH MINH trong goi TAO TRAN, None neu khong doc duoc.

    Dau truong xep char (kind=2) o hang 0 va 3, pet (kind=4) o hang 1 va 2 -> hai phe la {0,1}
    va {3,2}, va server xep minh vao phe NAO CUNG DUOC (capture 25/08: (0,1) tran 1, (0,0) tran
    2). Danh nham vao phe minh -> `S:000-000` ly do 42 `修改戰鬥封包` -> DA HAN acc.
    Dung chinh BattleTracker de doc, khong tu do offset lai.
    """
    if not self_entity:
        return None
    from .battle_tracker import BattleTracker
    tracker = BattleTracker(self_entity)
    try:
        tracker.apply(OP_BATTLE, _body(pkt))
    except Exception:
        return None
    for o, unit in tracker.units.items():
        if unit.role_id == self_entity:
            return o
    return None


def parse_vs_win(opcode, pkt, self_entity):
    """So tran THANG cua CHINH MINH tu `0x25` sub01, None neu goi cua nguoi khac.

    Server ban theo LO dung luc mot vong dau ket thuc (capture: 8 nguoi luc 338.4s, 10 nguoi
    luc 477.8s va 791.8s), trong lo co ca id cua minh.
    """
    b = _body(pkt)
    if opcode != OP_VS_WIN or len(b) < 12 or b[0] != 0x01 or b[1] != 0x00:
        return None
    if not self_entity or b[2:10] != self_entity:
        return None
    return int.from_bytes(b[10:12], "little")


# ---------- vong chay ----------

def _active(client, stop_event):
    return client.running and not stop_event.is_set()


def _cho(client, stop_event, sleep_fn, dieu_kien, han_giay, buoc=0.2):
    """Cho `dieu_kien()` thanh True. False neu het han / bi stop / rot.

    Vong nay CHI ngu - heartbeat `0x0a` chay o thread rieng (_heartbeat_loop, 15s/lan) nen cho
    lau bao nhieu cung khong lam rot ket noi. Da do: cho 336s van song.
    """
    het = time.time() + han_giay
    while time.time() < het:
        if not _active(client, stop_event):
            return False
        if dieu_kien():
            return True
        sleep_fn(buoc)
    return dieu_kien()


def dang_ky(client, stop_event, sleep_fn, poll_interval=0.4, max_advance=MAX_ADVANCE):
    """Mo NPC -> chon loan dau -> chon CO -> advance toi khi nhan `08 2a`. True = da dang ky."""
    moc = client._loandau_registered_seq
    client._loandau_dialog = ""
    client.send(OP_EVENT, OPEN_EVENT)
    sleep_fn(0.6)
    client.send(OP_DIALOG, OPEN_NPC)
    sleep_fn(0.8)
    if not is_choice_page(getattr(client, "_loandau_dialog", "")):
        client.send(OP_DIALOG, ADVANCE)
        sleep_fn(0.8)
    if not _active(client, stop_event):
        return False
    client.send(OP_DIALOG, CHOOSE_YES)
    for _ in range(max_advance):
        # Poll SAT 0.1s sau moi advance, dung NGAY khi da dang ky. Ngu ca poll_interval roi moi
        # check se gui THEM advance thua -> lech state -> server kick (bai hoc 40NPC).
        cho = 0.0
        while cho < max(0.1, poll_interval):
            if not _active(client, stop_event):
                return False
            if client._loandau_registered_seq > moc:
                return True
            sleep_fn(0.1)
            cho += 0.1
        client.send(OP_DIALOG, ADVANCE)
    return client._loandau_registered_seq > moc


def run_loop(client, point, stop_event, before_repeat=None, sleep_fn=time.sleep,
             poll_interval=0.4, wait_battle_sec=WAIT_BATTLE_SEC, window_fn=in_event_window):
    """Vong loan dau cua MOT acc. Tra ve khi het gio / bi stop / rot.

    `before_repeat` goi giua 2 tran (hoi HP/SP) - dung o day la AN TOAN vi dialog da dong
    (`08 26`); tuyet doi khong hoi luc dialog dang mo (bai hoc 40NPC: bi kick).
    """
    lbl = getattr(client, "_label", "?")
    if not client.navigate_to(int(point[0]), int(point[1]), flee=False):
        return False
    if not _active(client, stop_event):
        return False
    # Cho scene on truoc khi mo NPC: mo luc scene chua settle -> `0x14 08 01` -> `0x00` KICK
    # (su co that cua 40NPC 2026-07-29).
    client._wait_combat_clear(idle=1.0, cap=20.0)
    sleep_fn(3.0)
    if not _active(client, stop_event):
        return False
    # CHI rearm (`0x41`), KHONG combat_ready(): gui lai chuoi login ngay truoc NPC event lam
    # server loan state -> kick (40NPC).
    client.rearm_ready()

    while _active(client, stop_event) and window_fn():
        moc_tran = client._loandau_create_seq
        if not dang_ky(client, stop_event, sleep_fn, poll_interval):
            log.warning("[%s] Loan dau: dang ky that bai/timeout", lbl)
            return False
        log.info("[%s] Loan dau: da dang ky, cho ghep tran (thang=%d)",
                 lbl, getattr(client, "_loandau_wins", 0))

        # Cho vao tran. Het gio giua chung -> dung luon, khong cho tiep.
        vao = _cho(client, stop_event, sleep_fn,
                   lambda: client._loandau_create_seq > moc_tran or not window_fn(),
                   wait_battle_sec)
        if not window_fn():
            break
        if not vao or client._loandau_create_seq <= moc_tran:
            log.warning("[%s] Loan dau: cho ghep tran qua %.0fs khong vao -> dung", lbl,
                        wait_battle_sec)
            return False

        moc_ket = client._loandau_end_seq
        if not _cho(client, stop_event, sleep_fn,
                    lambda: client._loandau_end_seq > moc_ket, wait_battle_sec):
            log.warning("[%s] Loan dau: tran khong thay ket thuc -> dung", lbl)
            return False
        log.info("[%s] Loan dau: het tran (thang=%d)", lbl, getattr(client, "_loandau_wins", 0))

        if before_repeat is not None and _active(client, stop_event) and window_fn():
            try:
                before_repeat()
            except Exception as exc:
                log.warning("[%s] Loan dau: loi hoi phuc giua 2 tran: %s", lbl, exc)

    if not window_fn():
        log.info("[%s] Loan dau: het gio (qua 22h) -> di doi thuong", lbl)
        client._loandau_done = True
        return True
    return False
