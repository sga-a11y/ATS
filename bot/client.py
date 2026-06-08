"""TCP client TS Online: ket noi, auth, heartbeat, recv loop, dispatch + combat."""
import socket
import struct
import threading
import time
import logging

from . import config, protocol, combat


from .auth import build_auth_packet
from .state import BattleState

log = logging.getLogger("bot")

# Registry entity cac bot cung party (chia se trong process). party_idx -> set(entity bytes).
# Bot dang ky self_entity luc login -> khi nhan loi moi, accept neu nguoi moi cung party.
_PARTY_ENTITIES = {}
_PARTY_LOCK = threading.Lock()

def _register_party_entity(party_idx, entity):
    if party_idx is None or not entity:
        return
    with _PARTY_LOCK:
        _PARTY_ENTITIES.setdefault(party_idx, set()).add(bytes(entity))

def _is_party_member(party_idx, entity):
    if party_idx is None:
        return False
    with _PARTY_LOCK:
        return bytes(entity) in _PARTY_ENTITIES.get(party_idx, set())


# Khung gio nhan mail (gio bat dau, moi khung 2h): 12-14, 16-18, 22-24.
MAIL_WINDOWS = [12, 16, 22]


def mail_window_now():
    """Tra ve gio bat dau cua khung mail hien tai (12/16/22), hoac None neu ngoai khung."""
    import datetime
    h = datetime.datetime.now().hour
    for ws in MAIL_WINDOWS:
        if ws <= h < ws + 2:
            return ws
    return None


_GIFT_FILE = "gift_state.json"
_gift_lock = threading.Lock()


def _gift_key(label: str) -> str:
    import datetime
    return f"{label}:{datetime.date.today().isoformat()}"


def _load_gift_state(label: str) -> dict:
    """Load state qua online HOM NAY: {'online_sec': float, 'claimed': set}."""
    import json, os
    default = {"online_sec": 0.0, "claimed": set()}
    if not os.path.exists(_GIFT_FILE):
        return default
    try:
        with open(_GIFT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        rec = data.get(_gift_key(label))
        if not rec:
            return default
        return {"online_sec": float(rec.get("online_sec", 0)),
                "claimed": set(rec.get("claimed", []))}
    except Exception:
        return default


def _save_gift_state(label: str, online_sec: float, claimed: set):
    """Luu online_sec + claimed cho hom nay; don key ngay cu."""
    import json, os, datetime
    today = datetime.date.today().isoformat()
    with _gift_lock:
        data = {}
        if os.path.exists(_GIFT_FILE):
            try:
                with open(_GIFT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data = {k: v for k, v in data.items() if k.endswith(today)}
        data[_gift_key(label)] = {"online_sec": round(online_sec, 1),
                                  "claimed": sorted(claimed)}
        try:
            with open(_GIFT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass


class GameClient:
    def __init__(self, user_id: str, access_token: str):
        self.user_id = user_id
        self.access_token = access_token
        self.sock = None
        self.recv_buf = b""
        self.running = False
        self.state = BattleState()

        # combat turn handling
        self.available = {}          # unit -> list (atype, target)
        self._acted_turn = False
        self._decision_timer = None
        self.auto_combat = True
        self.auto_accept_party = True
        self.self_entity = None      # entity 8 byte cua nhan vat minh
        self.last_turn_time = 0.0    # thoi diem nhan luot/battle gan nhat
        self._label = ""             # nhan log: username luc dau, doi sang TEN NHAN VAT khi biet
        self._username = ""          # username login (giu lai de tham chieu)
        self.char_name = None        # ten nhan vat trong game (tu 0x27 theo self_entity)
        self.submit_delay = 0.5      # delay truoc khi gui combat
        self._first_turn = True      # luot dau tran -> atype=2, sau -> atype=3
        self._battle_entered = False # da gui 0x41 "vao tran" chua
        self.channels = {}           # {so_kenh: (so_nguoi, suc_chua)} - tu S2C 0x07 list
        self._chan_event = threading.Event()
        self.current_map = None      # map_id hien tai (doc tu broadcast 0x0c/0x07/0x03)
        self._pending_0b = []        # buffer 0x0b den TRUOC khi co self_entity (race login)
        self.party_leader = None     # entity chu party (tu 0x0d sub=06)
        self.party_members = []      # list entity cac member theo thu tu (= slot B2)
        self.party_idx = None        # chi so party cua bot (tu config.ACCOUNT_PARTY) - de nhan moi cung party
        self.entity_names = {}       # entity(bytes) -> set(str) - TAT CA strings tim duoc tu 0x27
        self.digioi_minutes = 0      # so phut DI GIOI hom nay (tu S2C 0x55 id=0x1b)
        self._last_digioi_ts = 0.0   # thoi diem nhan timer 0x1b gan nhat (0 = chua bao gio)
        self._connect_time = None    # thoi diem connect phien nay
        self._online_base = 0.0      # giay online TICH LUY hom nay (load tu file, truoc phien nay)
        self.claimed_gifts = set()   # cac moc qua online da nhan hom nay (load tu file)
        self._mail_ids = []          # mail_id thu thap tu S2C 0x53 (de nhan + xoa)

    # ---- ket noi + auth ----
    def connect(self):
        self.state.label = self._label
        self._connect_time = time.time()
        st = _load_gift_state(self._label)
        self._online_base = st["online_sec"]   # online tich luy truoc phien nay (hom nay)
        self.claimed_gifts = st["claimed"]
        self.sock = socket.create_connection((config.GAME_HOST, config.GAME_PORT), timeout=15)
        log.info("Da ket noi %s:%s", config.GAME_HOST, config.GAME_PORT)
        self.sock.sendall(build_auth_packet(self.user_id, self.access_token))
        log.info("Da gui auth (user_id=%s)", self.user_id)
        self.running = True
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    def send(self, opcode: int, payload: bytes):
        if opcode != protocol.OP_HEARTBEAT:
            log.debug("[%s] SEND op=0x%02x: %s", self._label, opcode, payload.hex())
        self.sock.sendall(protocol.encode(opcode, payload))

    def close(self):
        self.running = False
        if self.sock:
            self.sock.close()

    def in_combat(self, idle_secs: float = 4.0) -> bool:
        """Dang trong tran neu vua nhan luot/battle trong vong idle_secs giay."""
        busy = (time.time() - self.last_turn_time) < idle_secs
        if not busy:
            self.state.in_battle = False
        # KHONG reset _battle_entered/_first_turn: client THAT gui 0x41 + atype=2
        # chi 1 LAN/phien (join he thong battle), 6 tran sau van atype=3, khong gui lai 0x41
        return busy

    # ---- heartbeat ----
    def _heartbeat_loop(self):
        while self.running:
            time.sleep(15)
            try:
                self.send(protocol.OP_HEARTBEAT, b"\x00\x00")
            except OSError:
                break

    # ---- recv ----
    def _recv_loop(self):
        while self.running:
            try:
                data = self.sock.recv(8192)
            except OSError:
                break
            if not data:
                log.warning("Server dong ket noi")
                break
            self.recv_buf += protocol.xor(data)
            pkts, consumed = protocol.parse_stream(self.recv_buf)
            self.recv_buf = self.recv_buf[consumed:]
            for opcode, pkt in pkts:
                self._dispatch(opcode, pkt)

    def _dispatch(self, opcode: int, pkt: bytes):
        log.debug("[%s] RECV op=0x%02x len=%d %s", self._label, opcode, len(pkt), pkt.hex())
        # Track map_id hien tai: broadcast 0x0c/0x07 = [00 00][entity 8B][map_id 2B]...
        # (KHONG dung 0x03: goi stat, offset 10 la field khac -> doc nham 0x0202/0x0301)
        if opcode in (0x0c, 0x07) and len(pkt) >= 19 and pkt[7:9] == b"\x00\x00":
            mid = int.from_bytes(pkt[17:19], "little")
            if mid > 1000:   # loc gia tri rac (map_id that >1000)
                self.current_map = mid
        if opcode == protocol.OP_STAT_UPD:        # 0x33
            self.state.update_0x33(pkt)
        elif opcode == protocol.OP_FULLSTAT:      # 0x0b
            if self.self_entity is None:
                # chua biet self_entity -> buffer lai de xu khi co (tranh mat goi stat luc login)
                self._pending_0b.append(pkt)
                if len(self._pending_0b) > 20:
                    self._pending_0b.pop(0)
            # 0x0b battle (full stat): [entity][10x00][03][SLOT] -> vi tri tran cua minh.
            # Entity-based, dang tin (khong dua HP). Cap nhat moi tran (vi tri co the doi).
            if self.self_entity and len(pkt) > 100:
                idx = pkt.find(self.self_entity)
                if idx >= 0 and idx + 19 < len(pkt) and pkt[idx + 18] == 0x03:
                    slot = pkt[idx + 19]
                    if slot < 10 and slot != self.state.self_slot:
                        self.state.self_slot = slot
                        self.state.my_atype = slot
                        log.info("[%s] self_slot=%d (tu 0x0b battle, entity)", self._label, slot)
            self.state.update_0x0b(pkt)
        elif opcode == 0x53:                      # mail: S2C sub=01 = 1 mail (co mail_id)
            if pkt[7:9] == b"\x01\x00" and len(pkt) >= 17:
                mid = pkt[13:17]   # mail_id 4B LE (sau [01 00][01000000])
                if mid not in self._mail_ids:
                    self._mail_ids.append(mid)
        elif opcode == protocol.OP_ACTIONS:       # 0x35
            self._on_actions(pkt)
        elif opcode == 0x13 and len(pkt) >= 11 and pkt[7:9] in (b"\x04\x00", b"\x01\x00"):
            # pet dang dung: [04 00] luc login, [01 00] khi doi pet. id = 2B LE
            pid = int.from_bytes(pkt[9:11], "little")
            self.state.active_pet_id = pid
            self.state.pet_skills = getattr(config, "PET_SKILLS", {}).get(pid, set())
            name = getattr(config, "PET_NAMES", {}).get(pid, "?")
            log.info("[%s] Pet id=0x%x '%s' -> skills=%s",
                     self._label, pid, name, [hex(s) for s in sorted(self.state.pet_skills)])
        elif opcode == 0x2f:                      # party PHO BAN (dungeon)
            self._on_dungeon(pkt)
        elif opcode == 0x54:                      # exp offline
            self._on_offline_exp(pkt)
        elif opcode == 0x55 and len(pkt) >= 19 and pkt[13] == 0x1b:  # so phut Di Gioi
            self.digioi_minutes = int.from_bytes(pkt[15:17], "little")
            self._last_digioi_ts = time.time()
        elif opcode == 0x57:                      # qua online
            self._on_gift(pkt)
        elif opcode == 0x28:                      # skill bar char/pet
            self._on_skill_bar(pkt)
        elif opcode == 0x27:                      # player info co ten (entity + UTF-16LE name)
            self._on_player_info(pkt)
        elif opcode == 0x69:                      # chua self_entity
            if self.self_entity is None and len(pkt) >= 17:
                self.self_entity = pkt[9:17]
                self.state.self_entity = self.self_entity
                log.info("[%s] self_entity = %s", self._label, self.self_entity.hex())
                _register_party_entity(self.party_idx, self.self_entity)  # chia se cho cung party
                # xu lai cac goi 0x0b da buffer (co the chua stat cua minh den truoc 0x69)
                for p in self._pending_0b:
                    self.state.update_0x0b(p)
                self._pending_0b = []
        elif opcode == 0x07 and pkt[7:9] == b"\x01\x00" and len(pkt) >= 16:
            # danh sach kenh (channel list): payload bat dau '01 00 [count]'
            # (phan biet voi 0x07 broadcast di chuyen bat dau '00 00 [entity]')
            self._on_channel_list(pkt)
        # DEBUG kenh: log 0x07 (tru broadcast di chuyen 00 00) de tim "kenh hien tai"
        if __import__("os").environ.get("CHANDBG") and opcode == 0x07 and pkt[7:9] != b"\x00\x00":
            log.info("[%s] CHANDBG 0x07 %s", self._label, pkt.hex())
        elif opcode == protocol.OP_PLAYER_STATE:  # 0x0d - party
            self._on_party(pkt)
        elif opcode == protocol.OP_BATTLE_START:   # 0x34 - mốc battle that (KHONG dung 0x41!)
            self.state.in_battle = True
            self.state.reset_enemies()   # tran moi -> xoa HP quai tran cu
            self.last_turn_time = time.time()
            # KHONG reset _first_turn: atype=2 chi cho tran DAU TIEN ca phien, sau do=3
            # (moi tran chi 1 turn; client that dung 2 cho tran dau, 3 cac tran sau)
        # 0x41 (OP_BATTLE_ENTER) KHONG dung: fire ca luc login -> false positive
        # cac opcode khac: bo qua

    def _on_party(self, pkt: bytes):
        """S2C 0x0d. sub=09 = loi moi -> accept. sub=06 = roster [leader][count][members]."""
        if len(pkt) < 9:
            return
        sub = pkt[7]
        if sub == 0x09 and self.auto_accept_party and len(pkt) >= 17:
            entity = pkt[9:17]   # entity nguoi MOI (leader), KHONG set lam self_entity
            # --- Uu tien: nguoi moi la THANH VIEN CUNG PARTY (theo entity chia se) -> accept luon ---
            if _is_party_member(self.party_idx, entity):
                self.send(protocol.OP_PLAYER_STATE, b"\x08\x00\x01" + entity)
                log.info("[%s] Loi moi tu THANH VIEN CUNG PARTY -> ACCEPT", self._label)
                return
            # --- Loc theo whitelist PARTY_LEADERS (nguoi ngoai/leader nguoi that) ---
            leaders = getattr(config, "PARTY_LEADERS", [])
            if leaders:
                known = self.entity_names.get(entity, set())
                if known:
                    # Biet strings cua entity nay: accept neu BAT KY string nao khop
                    if not any(s in leaders for s in known):
                        log.info("[%s] TU CHOI loi moi tu entity=%s strings=%s (khong trong PARTY_LEADERS=%s)",
                                 self._label, entity.hex()[:12], known, leaders)
                        return
                else:
                    # Chua biet ten -> cho qua, log canh bao
                    log.info("[%s] Chua biet ten entity=%s -> CHAP NHAN (chua co 0x27)",
                             self._label, entity.hex()[:12])
            self.send(protocol.OP_PLAYER_STATE, b"\x08\x00\x01" + entity)
            log.info("[%s] Nhan loi moi party -> da gui ACCEPT", self._label)
        elif sub == 0x06 and len(pkt) >= 18:
            # roster: [sub 06][00][leader 8B][count 1B][member 8B]*count
            leader = pkt[9:17]
            count = pkt[17]
            members = []
            for i in range(count):
                off = 18 + i * 8
                if off + 8 <= len(pkt):
                    members.append(pkt[off:off + 8])
            if members:
                self.party_leader = leader
                self.party_members = members
                # slot cua minh = vi tri trong danh sach member (1-based) -> map B2 trong 0x33
                if self.self_entity in members:
                    idx = members.index(self.self_entity)
                    # atype = VI TRI BATTLE (0-4, leader LUON o giua=2). Member dien [1,3,0,4] theo thu tu.
                    FILL = [1, 3, 0, 4]
                    self.state.my_atype = FILL[idx] if idx < len(FILL) else idx
                    # slot stats trong 0x33 = VI TRI BATTLE (= atype), KHONG phai idx+1
                    self.state.self_slot = self.state.my_atype
                    log.info("[%s] Party roster: %d member, minh slot=atype=%d",
                             self._label, count, self.state.my_atype)
                else:
                    log.warning("[%s] self_entity %s KHONG co trong roster %s",
                                self._label, self.self_entity.hex() if self.self_entity else None,
                                [m.hex()[:8] for m in members])

    def _on_dungeon(self, pkt: bytes):
        """S2C 0x2f - party PHO BAN.
        sub=0x0f: loi moi [0f 00][id 4B][01 00][leader entity 8B][namelen][ten UTF-16LE]
          -> ten leader trong PARTY_LEADERS thi DONG Y: C2S 0x2f [03 00][id 4B][00]
          -> sau do tu an CHUAN BI: C2S 0x2f [0b 00]
        """
        if len(pkt) < 9:
            return
        body = pkt[7:]
        sub = int.from_bytes(body[0:2], "little")
        if sub == 0x0f and self.auto_accept_party and len(body) >= 17:
            invite_id = body[2:6]
            nl = body[16]
            name = ""
            try:
                name = body[17:17 + nl].decode("utf-16-le")
            except Exception:
                pass
            leaders = getattr(config, "PARTY_LEADERS", [])
            if leaders and name and name not in leaders:
                log.info("[%s] TU CHOI moi pho ban tu '%s' (khong trong PARTY_LEADERS)",
                         self._label, name)
                return
            # Dong y vao pho ban
            self.send(0x2f, b"\x03\x00" + invite_id + b"\x00")
            log.info("[%s] Nhan moi PHO BAN tu '%s' -> da DONG Y", self._label, name or "?")
            # Tu an CHUAN BI sau 2.5s (cho load scene pho ban)
            threading.Timer(2.5, self._dungeon_ready).start()

    def _dungeon_ready(self):
        if not self.running:
            return
        self.send(0x2f, b"\x0b\x00")
        log.info("[%s] Pho ban: da an CHUAN BI", self._label)

    # ---- xu ly available actions (0x35) ----
    def _on_actions(self, pkt: bytes):
        """0x35 (>=20B): liet ke cac combo [unit][atype][target] hop le cho luot nay."""
        if len(pkt) < 20:
            return  # 11-byte = confirmation, bo qua
        # 0x35 34-byte = toi luot minh -> dang trong tran
        self.state.in_battle = True
        self.last_turn_time = time.time()
        body = pkt[7:]
        # bo 2 byte dau (01 00), moi entry 5 byte: unit atype target 00 00
        i = 2
        while i + 3 <= len(body):
            unit, atype, target = body[i], body[i + 1], body[i + 2]
            if unit in (config.UNIT_CHAR, config.UNIT_PET):
                self.available.setdefault(unit, [])
                if (atype, target) not in self.available[unit]:
                    self.available[unit].append((atype, target))
            i += 5
        # KHONG lay atype tu 0x35 (no liet ke ca 5 vi tri party -> khong on dinh).
        # self_slot xac dinh qua roster (FILL) hoac khop char maxHP trong update_0x33.
        # debounce: quyet dinh 0.4s sau goi 0x35 cuoi cung
        if self.auto_combat:
            self._arm_decision()

    def _arm_decision(self):
        if self._decision_timer:
            self._decision_timer.cancel()
        self._decision_timer = threading.Timer(self.submit_delay, self._make_decisions)
        self._decision_timer.start()

    def _make_decisions(self):
        if self._acted_turn:
            return
        # Neu stats chua load (hp_max=0) -> doi toi da 1s cho 0x0b kip den
        if self.state.char.hp_max == 0 and self.state.pet.hp_max == 0:
            for _ in range(10):
                time.sleep(0.1)
                if self.state.char.hp_max != 0 or self.state.pet.hp_max != 0:
                    break
            else:
                log.warning("[%s] Stats chua load sau 1s -> bo qua luot", self._label)
                self.available = {}
                threading.Timer(1.5, self._reset_turn).start()
                return
        self._acted_turn = True
        try:
            char_opts = self.available.get(config.UNIT_CHAR, [])
            pet_opts = self.available.get(config.UNIT_PET, [])
            ft = self._first_turn
            if char_opts:
                d = combat.decide_char(self.state, char_opts, ft)
                self._send_combat(d)
                log.info("[%s] CHAR %s | %s | skills=%s | quai@%s",
                         self._label, d, self.state.char,
                         [hex(s) for s in sorted(self.state.skills_char)],
                         self.state.enemy_slots)
            if pet_opts:
                d = combat.decide_pet(self.state, pet_opts, ft)
                self._send_combat(d)
                log.info("[%s] PET  %s | %s", self._label, d, self.state.pet)
            self._first_turn = False
        finally:
            # reset cho luot sau
            self.available = {}
            threading.Timer(1.5, self._reset_turn).start()

    def _reset_turn(self):
        self._acted_turn = False

    def _send_combat(self, d: combat.Decision, tail: bytes = None):
        """0x32: 01 00 [unit][atype][b11=00][target][skill LE][tail].
        tail = 2 byte nonce; client THAT gui gia tri thay doi moi goi. TEST: random."""
        import os, random
        if tail is None:
            if os.environ.get("RAND_TAIL"):
                tail = struct.pack("<H", random.randint(1, 0xFFFF))
            else:
                tail = b"\x00\x00"
        payload = (b"\x01\x00"
                   + bytes([d.unit, d.atype, getattr(d, "b", 0), d.target])
                   + struct.pack("<H", d.skill)
                   + tail)
        self.send(protocol.OP_COMBAT, payload)

    # ---- qua online (0x57) ----
    def request_offline_exp(self, exp_type: int = 0x1c):
        """Hoi info exp offline (type 0x1c). Neu co exp -> tu nhan (xu ly o _on_offline_exp)."""
        self.send(0x54, b"\x01\x00" + struct.pack("<H", exp_type))

    def claim_mail(self):
        """Mail (opcode 0x53): mo mail list -> voi MOI mail: nhan qua + xoa.
        mail_id la account-specific (doc tu S2C 0x53 sub=01), KHONG hardcode."""
        # mo/refresh mail list (server push tung mail S2C 0x53 sub=01 -> _mail_ids).
        # KHONG xoa _mail_ids o dau (server push luc login truoc khi ham nay chay).
        self.send(0x53, b"\x03\x00\x01\x00\x00\x00\x05\x00\x00\x00")
        time.sleep(2.0)                          # cho mail list ve
        ids = list(self._mail_ids)
        self._mail_ids = []                      # consume sau khi gom
        if not ids:
            return
        for mid in ids:
            self.send(0x53, b"\x01\x00\x01\x00\x00\x00" + mid)   # nhan qua mail nay
            time.sleep(0.3)
            self.send(0x53, b"\x02\x00\x01\x00\x00\x00" + mid)   # xoa mail nay
            time.sleep(0.3)
        log.info("[%s] Mail: da nhan qua + xoa %d mail", self._label, len(ids))

    def _on_offline_exp(self, pkt: bytes):
        """S2C 0x54.
        sub=1: [01 00][type 2B][flag 1B][exp 4B LE] -> neu exp>0 thi gui nhan.
        sub=2: [02 00][type 2B][status 1B] -> status=1: nhan thanh cong.
        """
        if len(pkt) < 11:
            return
        body = pkt[7:]
        sub = int.from_bytes(body[0:2], "little")
        if sub == 0x01 and len(body) >= 9:
            exp_type = int.from_bytes(body[2:4], "little")
            exp = int.from_bytes(body[5:9], "little")
            if exp > 0:
                log.info("[%s] Co %d exp offline (type=0x%x) -> nhan", self._label, exp, exp_type)
                self.send(0x54, b"\x02\x00\x02" + struct.pack("<H", exp_type))
        elif sub == 0x02 and len(body) >= 5:
            status = body[4]
            if status:
                log.info("[%s] Nhan exp offline THANH CONG", self._label)

    def claim_online_gifts(self):
        """Nhan qua online GIONG client that: chi claim moc da DU GIO online.
        Thoi gian online TICH LUY hom nay = online_base (luu tu cac phien truoc) +
        uptime phien hien tai. Tich luy nay <= online time that nen khi >= moc thi qua
        CHAC CHAN da san sang (khong claim som -> khong bi nghi bot). Luu lai moi lan goi
        de reconnect khong mat tien do.
        Tra ve True neu da nhan het tat ca moc.
        """
        milestones = getattr(config, "GIFT_MILESTONES", [])
        if not milestones or self._connect_time is None:
            return False
        online_sec = self._online_base + (time.time() - self._connect_time)
        online_min = online_sec / 60.0
        for m in milestones:
            if m in self.claimed_gifts:
                continue
            if online_min >= m:
                self.send(0x57, b"\x02\x00\x03" + struct.pack("<I", m) + b"\x01")
                self.claimed_gifts.add(m)
                log.info("[%s] Nhan qua online moc %d phut (online=%.1f phut)",
                         self._label, m, online_min)
        # luu online tich luy + claimed (de reconnect tiep tuc dung)
        _save_gift_state(self._label, online_sec, self.claimed_gifts)
        return all(m in self.claimed_gifts for m in milestones)

    def _on_gift(self, pkt: bytes):
        """S2C 0x57 sub=2: [02 00][type 1B][status 1B] — status=0: nhan thanh cong."""
        if len(pkt) < 11:
            return
        if int.from_bytes(pkt[7:9], "little") == 0x02:
            status = pkt[10]
            if status == 0:
                log.info("[%s] Qua online: nhan THANH CONG", self._label)
            else:
                log.info("[%s] Qua online: status=%d", self._label, status)

    # ---- parse skill bar (0x28) ----
    def _on_skill_bar(self, pkt: bytes):
        """S2C 0x28: skill bar cua char/pet.
        Format: [01 00][unit 1B][count 1B][skill_id 2B LE * count]...
        unit=3: CHAR, unit=2: PET. 0x0000 = slot trong.
        """
        if len(pkt) < 12:
            return
        payload = pkt[7:]
        i = 2  # bo prefix 01 00
        while i + 2 <= len(payload):
            unit  = payload[i]
            count = payload[i + 1]
            i += 2
            if unit not in (2, 3) or count == 0 or count > 20:
                break
            skills = set()
            for _ in range(count):
                if i + 2 > len(payload):
                    break
                sid = int.from_bytes(payload[i:i+2], 'little')
                if sid != 0:
                    skills.add(sid)
                i += 2
            if unit == 3:
                self.state.skills_char = skills
                log.info("[%s] Char skills: %s", self._label,
                         [hex(s) for s in sorted(skills)])
            elif unit == 2:
                self.state.skills_pet = skills
                log.info("[%s] Pet skills: %s", self._label,
                         [hex(s) for s in sorted(skills)])

    # ---- parse player info (0x27) ----
    def _on_player_info(self, pkt: bytes):
        """S2C 0x27 sub=0x02: danh sach thanh vien guild.
        Format: [sub 2B=0200][guild_len 1B][guild_name UTF-16LE][01][count 1B]
                [entry: entity(8B) + name_len(1B) + name(UTF-16LE name_len B) + 32B extra] x count
        Chi xu ly sub=0x02; bo qua cac sub khac (0x09 la guild-join notify, khong co ten nhan vat).
        """
        if len(pkt) < 14:
            return
        payload = pkt[7:]
        sub = int.from_bytes(payload[0:2], 'little')
        if sub != 0x02:
            return
        guild_len = payload[2]
        # entries bat dau sau: 2B(sub) + 1B(guild_len) + guild_len + 1B(unknown) + 1B(count) = guild_len+5
        entries_off = 3 + guild_len + 2
        if entries_off > len(payload):
            return
        off = entries_off
        parsed = 0
        while off + 9 <= len(payload):
            entity = payload[off:off + 8]
            name_len = payload[off + 8]
            if name_len == 0 or off + 9 + name_len > len(payload):
                break
            try:
                name = payload[off + 9:off + 9 + name_len].decode('utf-16-le')
            except Exception:
                name = ''
            if name:
                self.entity_names.setdefault(entity, set()).add(name)
                # Neu la entity CUA MINH -> dung lam ten nhan vat trong log
                if self.self_entity and entity == self.self_entity and self.char_name != name:
                    self.char_name = name
                    self._label = name
                    log.info("[%s] Ten nhan vat = '%s'", self._username, name)
                log.debug("[%s] guild member: %s -> '%s'", self._label, entity.hex()[:12], name)
            off += 9 + name_len + 32
            parsed += 1
        if parsed:
            log.info("[%s] 0x27 parsed %d guild members (entity_names cap nhat)", self._label, parsed)

    # ---- lenh tien ich ----
    def switch_channel(self, channel: int):
        """Chuyen sang sub-channel (vd Di Gioi dong nguoi). C2S 0x07 = 02 00 [ch LE]."""
        self.send(0x07, b"\x02\x00" + struct.pack("<H", channel))
        log.info("Chuyen kenh -> %d", channel)

    def _on_channel_list(self, pkt: bytes):
        """S2C 0x07 list: payload = [01 00][count 1B][ block 6B: ch2 cur2 cap2 ]*count."""
        data = pkt[10:]   # bo header(6)+op(1)+ '01 00 count'(3)
        chans = {}
        for i in range(0, len(data) - 5, 6):
            ch, cur, cap = struct.unpack_from("<HHH", data, i)
            if 0 < ch < 1000 and cap > 0:
                chans[ch] = (cur, cap)
        if chans:
            self.channels = chans
            self._chan_event.set()
            log.info("[%s] Nhan danh sach %d kenh", self._label, len(chans))

    def request_channel_list(self):
        """Gui 0x07 0100 de server tra ve danh sach kenh + so nguoi."""
        self._chan_event.clear()
        self.channels = {}
        self.send(0x07, b"\x01\x00")

    def pick_best_channel(self, wait: float = 2.0, exclude=(1,)):
        """Hoi danh sach kenh -> chuyen sang kenh IT NGUOI nhat (con cho trong).
        exclude: bo qua kenh nao (vd kenh 1 thuong dong/mac dinh)."""
        self.request_channel_list()
        if not self._chan_event.wait(wait):
            log.warning("[%s] Khong nhan duoc danh sach kenh", self._label)
            return None
        # uu tien kenh con cho (cur<cap), it nguoi nhat
        cand = [(ch, cur, cap) for ch, (cur, cap) in self.channels.items()
                if ch not in exclude]
        if not cand:
            return None
        open_ch = [c for c in cand if c[1] < c[2]] or cand
        best = min(open_ch, key=lambda c: c[1])
        log.info("[%s] Kenh it nguoi nhat: kenh %d (%d/%d) -> chuyen sang",
                 self._label, best[0], best[1], best[2])
        self.switch_channel(best[0])
        return best[0]

    def move_to(self, x: int, y: int):
        """C2S 0x06: di chuyen nhan vat toi (x,y). Server tu di toi do."""
        self.send(0x06, b"\x01\x00\x01" + struct.pack("<HH", x, y))

    def in_di_gioi(self) -> bool:
        """Dang o map Di Gioi? Doc map_id thuc te (khong dua vao so kenh)."""
        return self.current_map == config.DIGIOI_MAP_ID

    def _left_di_gioi(self) -> bool:
        """Da ra khoi Di Gioi chua (map_id da khac Di Gioi)."""
        return self.current_map is not None and self.current_map != config.DIGIOI_MAP_ID

    def exit_di_gioi(self, step_wait: float = 2.0):
        """Di Gioi KHONG co lenh thoat: phai DI BO tung buoc nho toi CONG (270,210).
        Replay DUNG chuoi buoc THAT tu capture (cac buoc ~50-110px, da chung minh hop le)
        + cho step_wait giay moi buoc cho nhan vat di toi noi. Toi cong -> map tu doi.
        Kiem tra thoat bang map_id THAT (khong dua so kenh)."""
        log.info("[%s] Thoat Di Gioi: di bo tung buoc toi cong (270,210)...", self._label)
        # chuoi buoc THAT tu exit_new.pcap (x,y)
        steps = [(738, 648), (682, 609), (625, 569), (570, 530),
                 (462, 411), (417, 360), (390, 330)]
        for _ in range(3):   # lap lai vai vong neu chua ra
            for x, y in steps:
                self.move_to(x, y)
                time.sleep(step_wait)
            self.send(0x14, bytes.fromhex("04000100")); time.sleep(0.8)
            self.move_to(270, 210);                     time.sleep(step_wait)
            self.send(0x14, bytes.fromhex("08000100")); time.sleep(0.8)
            self.send(0x0c, bytes.fromhex("0100"));     time.sleep(0.5)
            self.send(0x14, bytes.fromhex("0600"));     time.sleep(1.5)
            if self._left_di_gioi():
                log.info("[%s] Da THOAT Di Gioi -> map %s", self._label, self.current_map)
                return True
        log.warning("[%s] Van chua thoat duoc Di Gioi (map %s)", self._label, self.current_map)
        return False

    def enter_di_gioi(self):
        """Vao map Di Gioi (map train chinh). Chi 2 goi co dinh: 0x61 010001 -> 0x61 020002.
        LUU Y: KHONG vao duoc khi dang trong party."""
        self.send(0x61, bytes.fromhex("010001"))   # mo/load zone Di Gioi
        log.info("[%s] Vao Di Gioi: gui 0x61 010001", self._label)
        time.sleep(1.5)                              # cho server load zone
        self.send(0x61, bytes.fromhex("020002"))   # xac nhan vao
        log.info("[%s] Vao Di Gioi: gui 0x61 020002 (xong)", self._label)

    def go_to_town(self, city_id: int, flag: int = 0, tries: int = 30, wait: float = 2.0):
        """Teleport ve thanh, LAP LAI cho toi khi RA KHOI map hien tai (neu dang o bai quai/
        battle thi teleport bi chan, phai cho khoang trong giua 2 tran). Xac nhan = map da doi
        (city_id != map_id voi 1 so thanh nhu Ng.Thanh, nen check 'da roi map cu')."""
        log.info("[%s] Ve thanh %d (lap lai neu con battle chan teleport)...", self._label, city_id)
        ok = 0
        for _ in range(tries):
            self.teleport(city_id, flag)
            time.sleep(wait)
            if self.current_map == city_id:
                ok += 1
                if ok >= 2:   # 2 lan lien tiep == city_id -> on dinh (tranh nhieu luc chuyen map)
                    log.info("[%s] Da ve thanh %d", self._label, city_id)
                    return True
            else:
                ok = 0
        log.warning("[%s] Chua ve duoc thanh %d (map=%s)", self._label, city_id, self.current_map)
        return False

    def teleport(self, city_id: int, flag: int = 0):
        """flag bat buoc dung dung cho tung thanh (xem cities.json)."""
        payload = b"\x01\x00" + struct.pack("<H", city_id) + bytes([flag])
        self.send(protocol.OP_TELEPORT, payload)
        log.info("Teleport -> city %s (flag %s)", city_id, flag)
