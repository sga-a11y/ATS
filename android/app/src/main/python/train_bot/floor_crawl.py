"""Event kieu LEO THAP nhieu tang (Nhi Kieu / '2K': 12922 -> 12959).

Boc tu capture that `captures/nhikieu_2k_tang1_9_20260809.pcap` (leader 13e8e44c + 4 member,
di lien tuc 12921 -> 12932 roi THUA):

- Tang LIEN TIEP: 12921(cho) -> 12922 -> ... . Map id doc tu S2C 0x0c (0x03 KHONG bat moi lan
  doi tang -> dung 0x03 de theo tang se sot).
- MOI tuong tac tren tang = C2S `0x14 0800 [idx]`, DUNG CHUNG opcode cho ca danh quai lan cong:
  * idx cua CONG len tang: lay tu world_nav.json - da doi chieu capture, KHOP 10/10 tang, ke ca
    tang 12930 dung door 3 (khong phai 2).
  * idx DANH QUAI: cac idx con lai. Quan sat 11/11 tang: nam trong 3..6, tru dung idx cua cong.
    (vd 12930 gui 4,5,6 vi cong la 3; cac tang khac gui 3,4,5 vi cong la 1/2.)
- THUA: KHONG dua vao "bi day ve 12003" - do la truong hop bay hon; thua binh thuong van dung
  yen tai cho. Dung `npc40.party_defeated(state.allies)` - dung ham repo da dung cho 40NPC.
- Moc bat dau/ket thuc tran: theo KNOWLEDGE muc 5 + CLAUDE.md -> bam `state.in_battle`
  (`_wait_combat_clear`), KHONG tu che moc moi.
"""

from __future__ import annotations

import logging
import time

from . import npc40

log = logging.getLogger("bot")

_BATTLE_IDX_RANGE = range(3, 9)   # idx danh quai quan sat duoc (3..6); quet rong hon 1 chut
_BATTLE_WAIT = 6.0                # cho sau khi gui idx de biet co vao tran khong
_MAX_FLOOR_SECONDS = 900.0
_WALK_BUDGET = 45.0               # ngan sach di toi cong moi tang (best-effort)


def _nav():
    from .client import _smart_world_router

    router = _smart_world_router()
    return None if router is None else router.nav


def _up_gate(scene: int):
    """(next_scene, door, (x,y)) cua cong LEN TANG, suy tu world_nav.json.

    KHONG gia dinh `scene + 1`: thap co lo hong (12940 khong ton tai, 12939 noi thang 12944).
    Tra None neu khong co canh len (12934/12939/12943/12949/12954 chi co cong xuong).
    """
    nav = _nav()
    if nav is None:
        return None
    best = None
    for edge in nav.data.get("edges", []):
        if int(edge["scene"]) != int(scene) or int(edge["target_scene"]) <= int(scene):
            continue
        gate = nav.get_gate(scene, edge["door"])
        if not (gate and gate.get("center")):
            continue
        cand = (int(edge["target_scene"]), int(edge["door"]), tuple(gate["center"]))
        if best is None or cand[0] < best[0]:
            best = cand
    return best


def _active(client, stop_event):
    return client.running and not stop_event.is_set()


def _fight_one(client, idx: int, stop_event):
    """Gui `0x14 0800 [idx]` roi cho xem co vao tran khong.

    Tra: "won" (danh xong, con song) | "lost" (party chet het) | None (idx nay khong ra tran).
    """
    client.send(0x14, b"\x08\x00" + bytes([idx & 0xFF]) + b"\x00")
    t0 = time.time()
    while _active(client, stop_event) and time.time() - t0 < _BATTLE_WAIT:
        if client.state.in_battle:
            break
        time.sleep(0.4)
    else:
        return None   # het gio ma khong vao tran -> idx nay khong phai diem danh quai
    if not _active(client, stop_event):
        return None
    client._wait_combat_clear(idle=3.0, cap=_MAX_FLOOR_SECONDS)
    # allies bi clear() moi 0x34 -> phai doc NGAY sau khi ket tran, truoc tran ke tiep.
    defeated, alive, total = npc40.party_defeated(client.state.allies)
    log.info("[%s] 2K: xong tran idx=%d, party song %d/%d", client._label, idx, alive, total)
    return "lost" if defeated else "won"


def _floor_point(ev, scene: int):
    """Diem CHOT cua tang (noi bam cac idx con lai + cong), doc tu events.json."""
    pts = (ev.get("party_battle") or {}).get("points") or {}
    p = pts.get(str(int(scene))) or pts.get("default")
    return tuple(p) if p else None


def _floor_label(ev, scene: int):
    """'tang N (map 12932)' - N suy tu floor_base (12924 = tang 1; 12922/12923 la khu vao)."""
    base = int((ev.get("party_battle") or {}).get("floor_base") or 0)
    n = int(scene) - base if base else 0
    return "tang %d (map %s)" % (n, scene) if n >= 1 else "khu vao (map %s)" % scene


def _walk_to(client, point, stop_event):
    """Di toi diem bang TIM DUONG THONG MINH, ngan sach ngan roi thoi (best-effort)."""
    if not point:
        return
    t0 = time.time()
    try:
        client.navigate_to(*point, flee=False,
                           abort=lambda: stop_event.is_set() or time.time() - t0 > _WALK_BUDGET)
    except Exception as e:
        log.debug("[%s] 2K: di toi %s loi (bo qua): %s", client._label, point, e)


def run_floor_crawl(client, ev, stop_event, on_done=None):
    """Leo tu tang hien tai len `top_map`. Chay thread rieng (giong npc40.run_loop).

    MEMBER KHONG chay ham nay: trong party, member tu dong di theo leader va khong tu di chuyen
    duoc (KNOWLEDGE muc 'Di chuyen': 0x06 bi vo hieu khi o trong party).
    """
    label = client._label
    top = int((ev.get("party_battle") or {}).get("top_map") or 0)
    if not top:
        log.warning("[%s] 2K: thieu top_map trong events.json -> khong leo", label)
        return
    client.flee_mode = False   # VAO LA DANH (khac go_to_event dat flee_mode=True)
    lost = False
    try:
        while _active(client, stop_event):
            scene = int(client.current_map or 0)
            if scene >= top:
                log.info("[%s] 2K: da toi tang cao nhat %s -> XONG", label, scene)
                break
            up = _up_gate(scene)
            if up is None:
                log.warning("[%s] 2K: %s KHONG co cong len trong world_nav -> DUNG o day. "
                            "Nghi la tang chot (cong len chi hien sau khi don sach tang). "
                            "Gui log nay de bo sung du lieu.", label, _floor_label(ev, scene))
                break
            nxt, door, center = up
            point = _floor_point(ev, scene)
            log.info("[%s] 2K: %s -> len %s (cong door=%s), diem chot %s",
                     label, _floor_label(ev, scene), nxt, door, point)
            # Danh het cac diem quai cua tang: idx 3..8 TRU idx cua cong.
            # Theo capture: idx DAU bam ngay tai cho spawn (khong co goi move truoc no), cac idx
            # sau + cong deu bam tu DIEM CHOT -> di toi diem chot TRUOC idx thu hai.
            fought = 0
            walked = False
            for idx in _BATTLE_IDX_RANGE:
                if not _active(client, stop_event):
                    break
                if idx == door:
                    continue
                if fought and not walked:
                    _walk_to(client, point, stop_event)
                    walked = True
                res = _fight_one(client, idx, stop_event)
                if res == "lost":
                    log.warning("[%s] 2K: PARTY THUA o %s (idx=%d) -> KET THUC 2K",
                                label, _floor_label(ev, scene), idx)
                    lost = True
                    break
                if res == "won":
                    fought += 1
            if lost or not _active(client, stop_event):
                break
            if not walked:
                _walk_to(client, point, stop_event)   # cong cung bam tu diem chot
            if not fought:
                log.warning("[%s] 2K: %s khong danh duoc tran nao (idx 3..8 deu khong ra tran) "
                            "-> van thu qua cong", label, _floor_label(ev, scene))
            # Qua cong len tang: cung dang `0x14 0800 [idx]`, dung _enter_gate de cho map doi that.
            client._in_scene_gate = True
            try:
                ok = client._enter_gate(center[0], center[1], door, expected_map=nxt)
            finally:
                client._in_scene_gate = False
            if not ok:
                log.warning("[%s] 2K: ket o cong %s (door=%s) -> dung leo",
                            label, _floor_label(ev, scene), door)
                break
            log.info("[%s] 2K: da len %s", label, _floor_label(ev, client.current_map))
    finally:
        if on_done is not None:
            try:
                on_done(lost)
            except Exception:
                pass
