"""Smoke test dang nhap THAT (Phase 1): nhan username/password/server tu UI, tu goi HTTP login
(port dung logic tu bot/login.py) roi mo socket TCP that toi server game, gui goi auth qua
protocol-native (JNI), doc phan hoi dau tien. KHONG can dien tay user_id/access_token nua - app
tu lam het, giong trai nghiem nguoi dung that."""
import hashlib
import json
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request

import bot_native_bridge as bridge

# --- Hang so game (khop dung bot/config.py + servers.json ban PC) ---
API_KEY = "17ade453e0892461edb01969b6e17e3a"
LOGIN_URL = f"https://graph.mobiplay.vn/accountapiv4/server/login?api_key={API_KEY}"
GAME_PORT = 6614
OP_LOGIN = 0x01

# key -> (label, ip, server_id) - khop servers.json ban PC
SERVERS = {
    "trieu_van":     ("Triệu Vân",     "103.82.28.98",  1),
    "tao_thao":      ("Tào Tháo",      "103.82.28.99",  2),
    "lu_bo":         ("Lữ Bố",         "103.82.28.100", 3),
    "luu_bi":        ("Lưu Bị",        "103.82.28.126", 4),
    "ton_quyen":     ("Tôn Quyền",     "103.82.28.140", 5),
    "truong_phi":    ("Trương Phi",    "103.82.28.143", 6),
    "chu_du":        ("Chu Du",        "103.82.28.144", 7),
    "quan_vu":       ("Quan Vũ",       "103.82.28.146", 8),
    "dieu_thuyen":   ("Điêu Thuyền",   "103.190.202.43", 9),
    "gia_cat_luong": ("Gia Cát Lượng", "103.190.202.44", 10),
    "dai_kieu":      ("Đại Kiều",      "103.190.202.45", 11),
    "manh_hoach":    ("Mạnh Hoạch",    "103.190.202.46", 12),
    "hoang_trung":   ("Hoàng Trung",   "103.190.202.47", 13),
}


def server_labels():
    """Danh sach (key, label) de UI hien dropdown chon server."""
    return [(k, v[0]) for k, v in SERVERS.items()]


def _device_id_for(username: str) -> str:
    return hashlib.md5(("dev_" + username).encode()).hexdigest()


def _tracking_id_for(username: str) -> str:
    h = hashlib.md5(("trk_" + username).encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def http_login(username: str, password: str) -> dict:
    """Goi API login that (port dung tu bot/login.py). Tra {user_id, access_token}."""
    params = {
        "username": username,
        "password": password,
        "device_id": _device_id_for(username),
        "agency_id": "1",
        "device_os_version": "Samsung SM-A528B 12",
        "client_version": "1.1",
        "lang": "vi",
        "device_os": "android",
        "local_agency_id": "1",
        "tracking_id": _tracking_id_for(username),
        "carrier": "",
    }
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        LOGIN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "okhttp/4.12.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if not data.get("status"):
        raise RuntimeError(f"Login that bai: {data}")
    d = data["data"]
    return {"user_id": d["user_id"], "access_token": d["access_token"]}


def build_auth_payload(user_id, access_token: str, server_id: int) -> bytes:
    """Dung DUNG format that (khop bot/auth.py:build_auth_packet):
    prefix(13B) + UTF16LE(user_id + 'f' + access_token). Chi tra ve PAYLOAD (chua co header/XOR) -
    header + XOR do protocol-native (bridge.encode_frame) lam, tranh code trung logic 2 noi."""
    prefix = bytes([0x00, 0x00, 0x02, 0x01, server_id & 0xFF,
                     0x00, 0x00, 0x00, 0x00, 0x00, 0x19, 0x14, 0x00])
    cred = (str(user_id) + "f" + access_token).encode("utf-16-le")
    return prefix + cred


def run_smoke_test(username: str, password: str, server_key: str):
    """Luong day du: HTTP login那 -> mo socket -> gui auth qua protocol-native -> doc phan hoi.
    Tra (True, thong_bao) hoac (False, thong_bao_loi) - KHONG raise de UI de hien thi."""
    if server_key not in SERVERS:
        return False, f"Server khong hop le: {server_key}"
    label, ip, server_id = SERVERS[server_key]
    try:
        cred = http_login(username, password)
    except Exception as e:
        return False, f"HTTP login that bai: {e}"

    try:
        sock = socket.create_connection((ip, GAME_PORT), timeout=15)
        payload = build_auth_payload(cred["user_id"], cred["access_token"], server_id)
        frame = bridge.encode_frame(OP_LOGIN, payload)
        sock.sendall(frame)
        raw = sock.recv(4096)
        frames, _consumed = bridge.decode_stream(raw)
        sock.close()
    except Exception as e:
        return False, f"Ket noi TCP that bai: {e}"

    if not frames:
        return False, "Khong nhan duoc phan hoi tu server (0 frame)"
    return True, f"OK - server {label}, nhan {len(frames)} frame, frame dau: {frames[0].hex()[:40]}..."
