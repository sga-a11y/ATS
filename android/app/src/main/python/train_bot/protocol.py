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
    """KHONG con dung truc tiep trong client.py (parse_stream thay the), giu lai
    chi de tuong thich neu co cho nao goi rieng le - danh dau loi neu that su goi toi."""
    raise NotImplementedError("protocol.xor() da thay bang native decode_stream - kiem tra cho goi ham nay")


def parse_stream(raw_wire_buf: bytes):
    """KHAC bot/protocol.py goc: ham nay nhan RAW WIRE (chua xor) thay vi da-xor,
    vi native decode_stream tu lam xor ben trong. Neu client.py goc truyen 'decoded'
    (da xor roi) vao day, PHAI sua lai diem goi trong client.py de truyen raw wire
    truc tiep - xem Task 3 Step ve _recv_loop."""
    frames, consumed = _bridge.decode_stream(raw_wire_buf)
    return [(f[6], f) for f in frames], consumed
