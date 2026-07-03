"""Thay the bot/protocol.py ban goc (XOR thuan Python) - o Android moi XOR/frame
di qua protocol-native (C++/JNI) qua bot_native_bridge, giu dung API cu (encode/
parse_stream/xor) de train_bot/client.py (copy tu bot/client.py) khong can sua gi."""
import bot_native_bridge as _bridge

MAGIC = b"\xc0\x91"

# ---- Opcodes (giong het bot/protocol.py goc - xem E:\Claude\ATS\bot\protocol.py) ----
OP_LOGIN = 0x01          # C2S auth / S2C "your turn"
OP_HEARTBEAT = 0x0A
OP_FULLSTAT = 0x0B
OP_MOB_INFO = 0x0C
OP_PLAYER_STATE = 0x0D   # party commands
OP_TELEPORT = 0x44
OP_INVITE = 0x52
OP_COMBAT = 0x32
OP_STAT_UPD = 0x33
OP_BATTLE_START = 0x34   # party battle start
OP_ACTIONS = 0x35        # available actions / confirmation
OP_BATTLE_ENTER = 0x41


def encode(opcode: int, payload: bytes) -> bytes:
    return _bridge.encode_frame(opcode, payload)


def xor(data: bytes) -> bytes:
    """XAC NHAN: bot/client.py (goc, dong 701) CO goi protocol.xor(data) truoc khi
    dua vao recv_buf ("self.recv_buf += protocol.xor(data)") - khi copy client.py o
    Task 3, dong nay PHAI doi thanh "self.recv_buf += data" (KHONG xor nua, vi
    parse_stream() ben duoi tu lam xor). Ham nay raise loi CHU DINH de bat ngay tai
    runtime neu Task 3 quen sua dong 701, thay vi de recv_buf bi xor 2 lan ->
    hong du lieu am tham (bug rat kho tim vi socket van nhan duoc byte, chi la
    sai noi dung)."""
    raise NotImplementedError(
        "protocol.xor() da thay bang native decode_stream. Neu ban thay loi nay khi "
        "chay train_bot.client - kiem tra dong tuong duong bot/client.py:701 "
        "('self.recv_buf += protocol.xor(data)') da duoc sua thanh 'self.recv_buf += data' chua."
    )


def parse_stream(raw_wire_buf: bytes):
    """KHAC bot/protocol.py goc: ham nay nhan RAW WIRE (chua xor) thay vi da-xor,
    vi native decode_stream tu lam xor ben trong.

    XAC NHAN diem goi CAN SUA khi copy bot/client.py o Task 3 (doc bot/client.py
    dong 701-702 de doi chieu):
        # BAN GOC (bot/client.py:701-702):
        self.recv_buf += protocol.xor(data)
        pkts, consumed = protocol.parse_stream(self.recv_buf)
        # PHAI SUA THANH (train_bot/client.py):
        self.recv_buf += data                      # KHONG xor - parse_stream tu xor
        pkts, consumed = protocol.parse_stream(self.recv_buf)
    Neu quen sua (van goi protocol.xor(data) truoc) -> ham xor() o tren se raise
    NotImplementedError ngay lap tuc (fail loud), KHONG am tham xor 2 lan."""
    frames, consumed = _bridge.decode_stream(raw_wire_buf)
    return [(f[6], f) for f in frames], consumed
