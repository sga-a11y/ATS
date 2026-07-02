"""Xac nhan THU CONG (khong chay trong CI): mo socket that toi server game, gui goi auth qua
protocol-native, doc phan hoi dau tien, in ra Logcat. Sua GAME_HOST/PORT/USER_ID/TOKEN thanh gia
tri that (tu bot PC, xem bot/config.py + dang nhap qua bot/login.py de lay access_token) truoc
khi chay tay - KHONG commit gia tri that vao file nay."""
import socket
import bot_native_bridge as bridge

GAME_HOST = "CHANGE_ME"   # vd 103.82.28.98 - dien tay, khong commit
GAME_PORT = 6614
USER_ID = 0                # dien tay tu ket qua bot/login.py
ACCESS_TOKEN = "CHANGE_ME"  # dien tay


def build_auth_payload(user_id: int, access_token: str, server_id: int) -> bytes:
    # Port dung logic tu bot/auth.py:build_auth_packet - xem file do de doi chieu format that.
    import struct
    tok = access_token.encode("utf-8")
    return struct.pack("<I", user_id) + struct.pack("<H", len(tok)) + tok + struct.pack("<H", server_id)


def run_smoke_test():
    sock = socket.create_connection((GAME_HOST, GAME_PORT), timeout=15)
    payload = build_auth_payload(USER_ID, ACCESS_TOKEN, server_id=1)
    frame = bridge.encode_frame(0x01, payload)   # 0x01 = OP_LOGIN, xem bot/protocol.py
    sock.sendall(frame)
    raw = sock.recv(4096)
    frames = bridge.decode_stream(raw)
    print(f"[smoke_login] nhan {len(frames)} frame, frame dau: {frames[0].hex() if frames else None}")
    sock.close()
    return len(frames) > 0
