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
        self._label = ""             # nhan account (de log multi-account)
        self.submit_delay = 0.5      # delay truoc khi gui combat
        self._first_turn = True      # luot dau tran -> atype=2, sau -> atype=3
        self._battle_entered = False # da gui 0x41 "vao tran" chua
        self.channels = {}           # {so_kenh: (so_nguoi, suc_chua)} - tu S2C 0x07 list
        self._chan_event = threading.Event()
        self.current_map = None      # map_id hien tai (doc tu broadcast 0x0c/0x07/0x03)

    # ---- ket noi + auth ----
    def connect(self):
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
            self.state.update_0x0b(pkt)
        elif opcode == protocol.OP_ACTIONS:       # 0x35
            self._on_actions(pkt)
        elif opcode == 0x69:                      # chua self_entity
            if self.self_entity is None and len(pkt) >= 17:
                self.self_entity = pkt[9:17]
                self.state.self_entity = self.self_entity
                log.info("self_entity = %s", self.self_entity.hex())
        elif opcode == 0x07 and pkt[7:9] == b"\x01\x00" and len(pkt) >= 16:
            # danh sach kenh (channel list): payload bat dau '01 00 [count]'
            # (phan biet voi 0x07 broadcast di chuyen bat dau '00 00 [entity]')
            self._on_channel_list(pkt)
        elif opcode == protocol.OP_PLAYER_STATE:  # 0x0d - party
            self._on_party(pkt)
        elif opcode == protocol.OP_BATTLE_START:   # 0x34 - mốc battle that (KHONG dung 0x41!)
            self.state.in_battle = True
            self.last_turn_time = time.time()
            # KHONG reset _first_turn: atype=2 chi cho tran DAU TIEN ca phien, sau do=3
            # (moi tran chi 1 turn; client that dung 2 cho tran dau, 3 cac tran sau)
        # 0x41 (OP_BATTLE_ENTER) KHONG dung: fire ca luc login -> false positive
        # cac opcode khac: bo qua

    def _on_party(self, pkt: bytes):
        """S2C 0x0d. sub=09 = co loi moi -> tu accept."""
        if len(pkt) < 9:
            return
        sub = pkt[7]
        if sub == 0x09 and self.auto_accept_party and len(pkt) >= 17:
            entity = pkt[9:17]
            if self.self_entity is None:
                self.self_entity = entity
            self.send(protocol.OP_PLAYER_STATE, b"\x08\x00\x01" + entity)
            log.info("[%s] Nhan loi moi party -> da gui ACCEPT", self._label)

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
        self._acted_turn = True
        try:
            char_opts = self.available.get(config.UNIT_CHAR, [])
            pet_opts = self.available.get(config.UNIT_PET, [])
            ft = self._first_turn
            if char_opts:
                d = combat.decide_char(self.state, char_opts, ft)
                self._send_combat(d)
                log.info("[%s] CHAR %s | %s | quai@%s hp=%s",
                         self._label, d, self.state.char,
                         self.state.enemy_slots, self.state.enemy_hp)
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
                   + bytes([d.unit, d.atype, 0x00, d.target])
                   + struct.pack("<H", d.skill)
                   + tail)
        self.send(protocol.OP_COMBAT, payload)

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

    def teleport(self, city_id: int, flag: int = 0):
        """flag bat buoc dung dung cho tung thanh (xem cities.json)."""
        payload = b"\x01\x00" + struct.pack("<H", city_id) + bytes([flag])
        self.send(protocol.OP_TELEPORT, payload)
        log.info("Teleport -> city %s (flag %s)", city_id, flag)
