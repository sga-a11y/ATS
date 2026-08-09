"""Event kieu LEO THAP nhieu tang (vd Nhi Kieu / '2K': map 12922 -> 12959).

KHAC event 40NPC (`kind: npc_repeat`, dung yen 1 cho mo lai tran cung diem): tang nao cung la
"di toi diem co dinh -> NPC hien thoai -> vao tran -> danh xong -> di tiep toi cong -> len tang".

DUONG DI: KHONG chep cung toa do tung buoc. Toa do tam cong + door index cua TUNG TANG da co
san trong `world_nav.json` (edges + gates) -> doc tu do, roi de TIM DUONG THONG MINH
(`navigate_to` -> Ground.mmg find_world_path) tu lo duong di. Door len tang KHONG co dinh
(thay 1/2/3/5 tuy tang) -> tuyet doi khong hardcode.

CONG: cong TRONG thap la cong THUONG -> `_enter_gate`. Chi rieng cong VAO event (12921->12922)
moi co cinematic (va chi o LAN DAU) -> do `go_to_event`/`_event_gate` lo, khong phai viec o day.

DIEM NPC: khong can biet toa do. NPC nam tren duong len cong; bot cu di ve phia cong, cham NPC
thi thoai bat len va CHAN di chuyen -> phat hien bang "di ma khong nhuc nhich" roi bam thoai
(`_dialog_until_battle`) de vao tran.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger("bot")

_MAX_FLOOR_SECONDS = 600.0     # tran/tang ket qua lau -> bo tang, khoi treo vo han
_ARRIVE_TOL = 60               # coi nhu da toi cong khi cach tam cong <= 60px
_STUCK_TRIES = 3               # so lan di ma khong nhuc nhich -> coi la dang bi thoai chan


def _nav():
    from .client import _smart_world_router

    router = _smart_world_router()
    return None if router is None else router.nav


def _up_gate(scene: int):
    """(next_scene, door, (x,y)) cua cong LEN TANG, suy tu world_nav.json.

    KHONG gia dinh `scene + 1`: thap co lo hong (12940 khong ton tai, 12939 noi thang len
    12944). Lay canh co target_scene LON HON scene va gan nhat.

    Tra None neu world_nav khong co canh len (tang 12934/12939/12943/12949/12954 chi co cong
    di xuong - nghi la cong len chi hien sau khi don sach tang).
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


def _probe_gates(scene: int):
    """Cong con lai cua tang (loai cac cong DI XUONG) - de do khi world_nav thieu canh len."""
    nav = _nav()
    if nav is None:
        return []
    down = {
        int(e["door"]) for e in nav.data.get("edges", [])
        if int(e["scene"]) == int(scene) and int(e["target_scene"]) < int(scene)
    }
    out = []
    for door, gate in (nav.gates.get(str(int(scene)), {}) or {}).items():
        if int(door) in down or not gate.get("center"):
            continue
        out.append((int(door), tuple(gate["center"])))
    return sorted(out)


def _finish_battle(client, stop_event):
    """Cho HET tran THAT SU (0x14 sub0700/0800) roi moi di tiep - di giua tran thi server nuot lenh."""
    client._wait_combat_clear(idle=3.0)
    return client.running and not stop_event.is_set()


def _walk_to_gate(client, center, stop_event) -> bool:
    """Di toi tam cong bang TIM DUONG THONG MINH, danh moi tran chan duong.

    `navigate_to(flee=False)` tu di tung chang theo Ground.mmg va cho het tran neu dinh tran.
    Nhung THOAI NPC (chua thanh tran) thi no khong biet - thoai chan di chuyen nen nhan vat dung
    yen. Phat hien bang vi tri khong doi qua `_STUCK_TRIES` vong -> bam thoai de vao tran.
    """
    t0 = time.time()
    stuck = 0
    last_pos = None
    while client.running and not stop_event.is_set():
        if time.time() - t0 > _MAX_FLOOR_SECONDS:
            log.warning("[%s] 2K: qua %.0fs chua toi cong %s -> bo tang nay",
                        client._label, _MAX_FLOOR_SECONDS, center)
            return False
        client.navigate_to(*center, flee=False, abort=lambda: stop_event.is_set())
        if client.state.in_battle:
            if not _finish_battle(client, stop_event):
                return False
            stuck = 0
            last_pos = None
            continue
        pos = client.pos
        if pos and abs(pos[0] - center[0]) <= _ARRIVE_TOL and abs(pos[1] - center[1]) <= _ARRIVE_TOL:
            return True
        if pos is not None and pos == last_pos:
            stuck += 1
        else:
            stuck = 0
        last_pos = pos
        if stuck >= _STUCK_TRIES:
            # Dung yen du da goi navigate_to -> gan nhu chac chan dang bi THOAI NPC chan.
            log.info("[%s] 2K: dung yen tai %s -> bam thoai NPC de vao tran", client._label, pos)
            client._dialog_until_battle(cap_n=12, gap=0.8)
            if not _finish_battle(client, stop_event):
                return False
            stuck = 0
            last_pos = None
    return False


def run_floor_crawl(client, ev, stop_event, on_done=None):
    """Leo tu tang hien tai len `top_map`. Chay trong thread rieng (giong npc40.run_loop)."""
    label = client._label
    top = int((ev.get("party_battle") or {}).get("top_map") or 0)
    if not top:
        log.warning("[%s] 2K: thieu top_map trong events.json -> khong leo", label)
        return
    client.flee_mode = False   # VAO LA DANH, khong bo chay (khac go_to_event dat flee_mode=True)
    try:
        while client.running and not stop_event.is_set():
            scene = int(client.current_map or 0)
            if scene >= top:
                log.info("[%s] 2K: da toi tang cao nhat %s -> XONG", label, scene)
                break
            up = _up_gate(scene)
            if up is None:
                cands = _probe_gates(scene)
                if not cands:
                    log.warning("[%s] 2K: tang %s KHONG co cong len trong world_nav va khong con "
                                "cong nao de do -> DUNG o day. Nghi la tang chot: cong len chi hien "
                                "sau khi don sach tang. Gui log nay de bo sung du lieu.", label, scene)
                    break
                log.warning("[%s] 2K: tang %s thieu canh len trong world_nav -> DO cong con lai %s",
                            label, scene, [d for d, _ in cands])
                nxt, (door, center) = 0, cands[0]
            else:
                nxt, door, center = up
            log.info("[%s] 2K: tang %s -> %s, cong door=%s tai %s",
                     label, scene, nxt or "?", door, center)
            if not _walk_to_gate(client, center, stop_event):
                break
            if not client.running or stop_event.is_set():
                break
            # Cong trong thap = cong THUONG (khong cinematic) -> _enter_gate. Dat _in_scene_gate de
            # tran phuc kich luc qua cong duoc xu ly rieng tung acc (xem chu thich trong client).
            client._in_scene_gate = True
            try:
                # nxt=0 khi DO cong (chua biet tang dich) -> khong ep expected_map, chi can DOI map
                ok = client._enter_gate(center[0], center[1], door,
                                        expected_map=(nxt or None))
                if ok and not nxt and int(client.current_map or 0) <= scene:
                    ok = False   # do trung cong DI XUONG -> coi nhu that bai, dung leo
            finally:
                client._in_scene_gate = False
            if not ok:
                log.warning("[%s] 2K: ket o cong tang %s (door=%s) -> dung leo", label, scene, door)
                break
            log.info("[%s] 2K: da len tang %s", label, client.current_map)
    finally:
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass
