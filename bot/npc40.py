"""Protocol and bounded battle loop for the 40 NPC event."""

import logging
import time


log = logging.getLogger("bot")

OP_DIALOG = 0x14
OP_EVENT = 0x20
OPEN_EVENT = b"\x02\x00\x08"
OPEN_NPC = b"\x01\x00\x05\x00"
ADVANCE = b"\x06\x00"
CHOOSE_YES = b"\x09\x00\x1e"
CHOOSE_NO = b"\x09\x00\x1f"


def is_repeat_prompt(opcode, packet):
    return opcode == 0x41 and len(packet) >= 10 and packet[7:10] == b"\x0a\x00\x01"


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
        sleep_fn(max(0.05, poll_interval))
    return client._battle_start_seq > previous


def run_loop(client, point, stop_event, on_loss, sleep_fn=time.sleep,
             poll_interval=0.4, max_advances=30):
    """Run the leader-only 40 NPC loop. Returns only when stopped, lost, or timed out."""
    if not client.navigate_to(int(point[0]), int(point[1]), flee=False):
        return False
    if not _active(client, stop_event):
        return False
    client.combat_ready()

    battle_seq = client._battle_start_seq
    prompt_seq = client._npc40_prompt_seq
    client.send(OP_EVENT, OPEN_EVENT)
    sleep_fn(0.5)
    client.send(OP_DIALOG, OPEN_NPC)
    sleep_fn(0.6)
    client.send(OP_DIALOG, ADVANCE)
    sleep_fn(0.6)
    client.send(OP_DIALOG, CHOOSE_YES)
    if not _advance_to_battle(
            client, battle_seq, stop_event, sleep_fn, poll_interval, max_advances):
        log.warning("[%s] 40NPC: mo tran dau timeout", getattr(client, "_label", "?"))
        return False

    while _active(client, stop_event):
        if not _wait_counter(
                client, "_npc40_prompt_seq", prompt_seq, stop_event,
                sleep_fn, poll_interval, max_advances * 20):
            log.warning("[%s] 40NPC: cho dialog sau tran timeout", getattr(client, "_label", "?"))
            return False

        if client._npc40_last_defeated:
            client.send(OP_DIALOG, CHOOSE_NO)
            sleep_fn(0.5)
            client.send(OP_DIALOG, ADVANCE)
            sleep_fn(0.5)
            client.send(OP_DIALOG, ADVANCE)
            on_loss()
            return False

        prompt_seq = client._npc40_prompt_seq
        battle_seq = client._battle_start_seq
        client.send(OP_DIALOG, CHOOSE_YES)
        if not _advance_to_battle(
                client, battle_seq, stop_event, sleep_fn, poll_interval, max_advances):
            log.warning("[%s] 40NPC: vao tran tiep theo timeout", getattr(client, "_label", "?"))
            return False
    return False
