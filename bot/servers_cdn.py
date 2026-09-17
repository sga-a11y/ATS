# -*- coding: utf-8 -*-
"""TU PHAT HIEN SERVER MOI tu CDN tai nguyen cua game.

Client lay danh sach server tu CDN chu khong nhet trong APK (`_lua_dec/Logic/Network.lua`):

    function Network.Initialize()
      this.servers = json.decode(CGResourceManager.DownloadText("ServerList.dat", true));

Duong dan that (moi ra tu `global-metadata.dat` + logcat Unity luc app khoi dong, 17/09):

    https://cdn-gz06.mobigame.vn/tsr/ResourcePath_ANDROID.dat   -> {"ExeVer":..,"DataVer":"1.0.9"}
    https://cdn-gz06.mobigame.vn/tsr/<DataVer>/Android/ServerList.dat

Ca hai deu la HTTP TINH, khong can token, va CDN CO SERVER MOI TRUOC CA KHI SERVER GAME MO LAI
(user 17/09: "dang bao tri de mo server moi, server chua mo lai nhung client thay update roi").
Nho vay bot biet server moi ngay ngay dau, khong phai cho ai do sua tay `servers.json`.

KHONG GHI DE `servers.json`: file do dung chung PC/APK va `Servers.kt` co bang FALLBACK chep tay
voi CONG CHAN BUILD bat hai ben phai khop (xem CLAUDE.md muc "Sau cong chan tu dong"). Tu ghi vao
do thi moi lan CDN them server la build DO cho toi khi sua tay Kotlin. Nen server moi duoc luu
rieng ra `servers_cdn.json` va NHAP THEM vao `config.SERVERS` luc chay - `servers.json` van la
nguon su that cho bang khai bao.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import unicodedata

log = logging.getLogger("bot")

CDN_GOC = "https://cdn-gz06.mobigame.vn/tsr/"
CDN_VERSION_FILE = "ResourcePath_ANDROID.dat"
CDN_TIMEOUT = 8.0
OVERLAY_FILE = "servers_cdn.json"       # server CDN co ma `servers.json` chua khai


def _tai(url, timeout=CDN_TIMEOUT):
    """Tai mot file text tu CDN. Nem loi de nguoi goi quyet dinh."""
    import ssl
    import urllib.request
    # CDN game dung chung mot chung chi cho nhieu ten mien; xac thuc that bai thi ca tinh nang
    # chet trong khi du lieu van dung. Day la danh sach server CONG KHAI, khong co bi mat gi.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # Query `?<timestamp>` giong het client (xem logcat: "Load ...ServerList.dat?46282,4887...")
    # - CDN cache rat lau, thieu no thi tai ve ban cu.
    req = urllib.request.Request("%s?%d" % (url, int(time.time())),
                                 headers={"User-Agent": "UnityPlayer/2021 (TSOnline)"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read().decode("utf-8", "replace")


def data_ver():
    """`DataVer` hien tai cua client (vd "1.0.9"). None = khong hoi duoc."""
    try:
        d = json.loads(_tai(CDN_GOC + CDN_VERSION_FILE))
    except Exception as e:
        log.debug("SERVER CDN: khong doc duoc %s: %s", CDN_VERSION_FILE, e)
        return None
    if isinstance(d, list):
        d = d[0] if d else {}
    v = (d or {}).get("DataVer")
    return str(v) if v else None


def tai_danh_sach(ver=None):
    """[{"id", "name", "host", "port"}] tu CDN. `[]` = khong hoi duoc (KHONG phai "khong co server").

    Tra rong khi loi chu khong nem: mat mang / CDN doi duong dan KHONG duoc lam bot chet luc khoi
    dong - `servers.json` van du de chay.
    """
    ver = ver or data_ver()
    if not ver:
        return []
    try:
        raw = _tai("%s%s/Android/ServerList.dat" % (CDN_GOC, ver))
    except Exception as e:
        log.debug("SERVER CDN: khong doc duoc ServerList.dat (ver=%s): %s", ver, e)
        return []
    try:
        ds = json.loads(raw)
    except Exception as e:
        log.debug("SERVER CDN: ServerList.dat khong phai JSON: %s", e)
        return []
    out = []
    for s in ds if isinstance(ds, list) else ():
        try:
            out.append({"id": int(s["id"]), "name": str(s.get("name") or "").strip(),
                        "host": str(s["host"]).strip(), "port": int(s.get("port") or 6614)})
        except Exception:
            continue
    return out


def khoa_noi_bo(ten, da_co=()):
    """Ten hien thi -> khoa noi bo kieu `trieu_van` (giong cach `servers.json` dat tu truoc).

    Trung khoa thi them hau to so: hai server co the trung ten sau khi bo dau (vd "Đại Kiều" va
    "Tiểu Kiều - New" thi khong, nhung "Mã Siêu"/"Ma Sieu" thi co).
    """
    s = unicodedata.normalize("NFD", ten or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    s = re.sub(r"_+", "_", s) or "server"
    if s not in da_co:
        return s
    i = 2
    while "%s_%d" % (s, i) in da_co:
        i += 1
    return "%s_%d" % (s, i)


def _duong_overlay(thu_muc):
    return os.path.join(thu_muc, OVERLAY_FILE)


def doc_overlay(thu_muc):
    """Server CDN da phat hien o lan chay truoc. {} = chua co."""
    try:
        with open(_duong_overlay(thu_muc), encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("servers", {}) or {}
    except Exception:
        return {}


def _ghi_overlay(thu_muc, servers):
    _tam = _duong_overlay(thu_muc) + ".tam"
    with open(_tam, "w", encoding="utf-8") as fh:
        json.dump({"_note": "SERVER MOI do bot tu phat hien tu CDN (bot/servers_cdn.py). "
                            "File nay do BOT ghi - dung sua tay; muon khai chinh thuc thi them vao "
                            "servers.json VA Servers.kt (co cong chan build).",
                   "servers": servers}, fh, ensure_ascii=False, indent=2)
    os.replace(_tam, _duong_overlay(thu_muc))


def tim_server_moi(da_khai, tren_cdn):
    """{khoa: {label, ip, id}} cho nhung server CDN co ma `da_khai` chua co.

    So theo **id**, khong theo ten: ten hien thi doi duoc (vd "Tiểu Kiều - New" roi bo chu New),
    con id la thu di trong goi auth.
    """
    _id_da_co = set()
    for v in (da_khai or {}).values():
        try:
            _id_da_co.add(int(v.get("id")))
        except Exception:
            continue
    _khoa_da_co = set(da_khai or {})
    moi = {}
    for s in sorted(tren_cdn, key=lambda x: x["id"]):
        if s["id"] in _id_da_co:
            continue
        k = khoa_noi_bo(s["name"] or ("server_%d" % s["id"]), _khoa_da_co)
        _khoa_da_co.add(k)
        moi[k] = {"label": s["name"], "ip": s["host"], "id": s["id"]}
    return moi


def cap_nhat(servers, thu_muc, tai=None):
    """NHAP server moi vao `servers` (sua TAI CHO) + luu overlay. Tra {khoa: info} vua them.

    `servers` = `config.SERVERS`. `thu_muc` = noi ghi overlay (PC: canh exe; APK: thu muc du lieu
    app - assets read-only nen khong ghi vao do duoc).
    """
    them = {}
    # 1. Ban da phat hien o lan chay TRUOC - dung duoc ngay ca khi lan nay mat mang.
    for k, v in (doc_overlay(thu_muc) or {}).items():
        if k not in servers:
            servers[k] = v
            them[k] = v
    # 2. Hoi CDN xem co gi moi hon khong.
    try:
        tren_cdn = (tai or tai_danh_sach)()
    except Exception as e:
        log.debug("SERVER CDN: loi hoi CDN: %s", e)
        tren_cdn = []
    if not tren_cdn:
        return them
    moi = tim_server_moi(servers, tren_cdn)
    if not moi:
        return them
    for k, v in moi.items():
        servers[k] = v
        them[k] = v
        log.warning("SERVER MOI tu CDN: id=%s %s (%s) -> khoa '%s'",
                    v["id"], v["label"], v["ip"], k)
    try:
        _cu = doc_overlay(thu_muc)
        _cu.update(moi)
        _ghi_overlay(thu_muc, _cu)
    except Exception as e:
        log.debug("SERVER CDN: khong ghi duoc overlay: %s", e)
    return them


_da_hoi = False
_khoa_hoi = threading.Lock()


def cap_nhat_nen(servers, thu_muc, xong=None):
    """Nhu `cap_nhat` nhung chay o THREAD NEN - khoi dong bot KHONG duoc cho mang.

    `xong(them)` goi sau khi chay xong (de GUI ve lai danh sach server neu co thay doi).
    """
    global _da_hoi
    with _khoa_hoi:
        if _da_hoi:
            return          # GUI va luong khoi dong bot deu goi - chi hoi CDN MOT lan moi phien
        _da_hoi = True

    def _vong():
        try:
            them = cap_nhat(servers, thu_muc)
        except Exception as e:
            log.debug("SERVER CDN: loi cap nhat nen: %s", e)
            them = {}
        if xong is not None:
            try:
                xong(them)
            except Exception:
                pass
    threading.Thread(target=_vong, name="server-cdn", daemon=True).start()
