"""HTTP login -> lay user_id + access_token."""
import urllib.parse
import urllib.request
import json
from . import config


import hashlib

def _device_id_for(username: str) -> str:
    """Tao device_id DUY NHAT cho moi account (32 hex) - tranh server coi 2 acc chung device."""
    return hashlib.md5(("dev_" + username).encode()).hexdigest()


def _tracking_id_for(username: str) -> str:
    """tracking_id dang UUID duy nhat moi account."""
    h = hashlib.md5(("trk_" + username).encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def login(username: str = None, password: str = None, device_id: str = None) -> dict:
    """Goi API login, tra ve {user_id, access_token, username}.

    Raise RuntimeError neu that bai.
    """
    username = username or config.USERNAME
    password = password or config.PASSWORD
    device_id = device_id or _device_id_for(username)

    params = {
        "username": username,
        "password": password,
        "device_id": device_id,
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
        config.LOGIN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "okhttp/4.12.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    if not data.get("status"):
        raise RuntimeError(f"Login that bai: {data}")

    d = data["data"]
    return {
        "user_id": d["user_id"],
        "access_token": d["access_token"],
        "username": d["username"],
    }


if __name__ == "__main__":
    print(login())
