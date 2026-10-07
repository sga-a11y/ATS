"""BAO LOI: dong goi version + config + log CUA MOT PARTY roi gui ve Telegram cua dev.

Thiet ke + ly do tung quyet dinh: documents/BAO_LOI.md. Dung chung PC/APK (SHARED).

Luong: `tao_bao_loi(...)` -> chup config (bo password) -> loc log 2 phien gan nhat cua party
-> zip -> `gui_telegram` -> tra {"ok", "ma", ...}. Gui hong thi zip VAN nam lai trong thu muc
`bao_loi/` canh exe/app de user gui tay.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import platform
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile

log = logging.getLogger("bot")

# Bot Telegram cua dev (@atsbotrpbot). Token KHONG nam trong source: doc tu `bao_loi_bot.json`
# ({"token": "...", "chat_id": "..."}) - xem `doc_bot`. Thieu file -> chi luu zip de gui tay.
TEN_FILE_BOT = "bao_loi_bot.json"
TELEGRAM_CHAT_ID = "689905584"
TELEGRAM_FILE_TOI_DA = 49 * 1024 * 1024   # Bot API nhan toi 50 MB/file
TELEGRAM_CAPTION_TOI_DA = 1000            # Bot API: caption <= 1024 ky tu

SO_PHIEN = 2                       # user thay loi hay Stop/Start lai roi moi bao -> lay ca phien truoc
TRAN_LOG_BYTE = 200 * 1024 * 1024  # doc nguoc toi da chung nay log tho (~20 MB sau khi zip)
CACH_NHAU_SEC = 120                # chong spam: moi may cach nhau >= 2 phut
MO_TA_TOI_THIEU = 10
THU_MUC_LUU = "bao_loi"
_KHOI_DOC = 4 * 1024 * 1024

MOC_PHIEN = ">>> PARTY %d BAT DAU PHIEN MOI"
_GIO_RE = re.compile(r"^\d\d:\d\d:\d\d ")
_NHAN_RE = re.compile(r"^\d\d:\d\d:\d\d \[([^\]]+)\]")
_NHAN_PARTY_RE = re.compile(r"^(?:party |P)(\d+)(?:\s|$)")
_DONG_PARTY_RE = re.compile(r"^\d\d:\d\d:\d\d >>> PARTY (\d+)\b")
_DOI_NHAN_RE = re.compile(r"^\d\d:\d\d:\d\d \[([^\]]+)\] NHAN LOG -> '(.+)'\s*$")
_KHOA_MAT_KHAU = {"p", "password", "pass", "pwd", "passwd", "access_token", "token"}

_lan_gui_cuoi = 0.0
_khoa_gui = threading.Lock()


def phien_ban():
    """Version core dang chay. PC: bot/_version.py (build ghi de). APK: sys.__ats_core_loaded__."""
    try:
        from ._version import VERSION
        return str(VERSION)
    except Exception:
        return str(getattr(sys, "__ats_core_loaded__", "") or "?")


def dong_moc(pidx, users, now=None):
    """Dong log danh dau party bat dau phien MOI. Log chi co gio, dong nay mang ca ngay."""
    now = now or datetime.datetime.now()
    return "%s %s v%s acc=[%s]" % (MOC_PHIEN % (pidx + 1), now.strftime("%Y-%m-%d %H:%M:%S"),
                                   phien_ban(), ", ".join(users))


def tao_ma(now=None, rnd=None):
    now = now or datetime.datetime.now()
    rnd = rnd or random.SystemRandom()
    return "BL-%s-%04X" % (now.strftime("%m%d"), rnd.randrange(0x10000))


def doc_bot(cfg=None, thu_muc=None):
    """{"token", "chat_id"}. Ban build: module `_bao_loi_bot.py` do build_product.py sinh tu
    `bao_loi_bot.json` (nam TRONG exe/APK). Chay tu source: doc thang file json."""
    try:
        from ._bao_loi_bot import BOT
        if BOT.get("token"):
            return {"token": BOT["token"], "chat_id": str(BOT.get("chat_id") or TELEGRAM_CHAT_ID)}
    except Exception:
        pass
    cho = []
    if thu_muc:
        cho.append(os.path.join(thu_muc, TEN_FILE_BOT))
    base = getattr(cfg, "_base_dir", None)
    if callable(base):
        try:
            cho.append(os.path.join(base(), TEN_FILE_BOT))
        except Exception:
            pass
    for f in cho:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            if d.get("token"):
                return {"token": d["token"], "chat_id": str(d.get("chat_id") or TELEGRAM_CHAT_ID)}
        except Exception:
            continue
    doc_asset = getattr(cfg, "_read_asset", None)
    if callable(doc_asset):
        try:
            d = json.loads(doc_asset(TEN_FILE_BOT))
            if d.get("token"):
                return {"token": d["token"], "chat_id": str(d.get("chat_id") or TELEGRAM_CHAT_ID)}
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- config

def bo_mat_khau(obj, mat_khau=()):
    """Ban sao cua obj: bo moi khoa kieu password, chuoi trung password thi thay '***'."""
    mk = {m for m in mat_khau if m}
    if isinstance(obj, dict):
        return {k: bo_mat_khau(v, mk) for k, v in obj.items()
                if str(k).lower() not in _KHOA_MAT_KHAU}
    if isinstance(obj, (list, tuple, set)):
        return [bo_mat_khau(v, mk) for v in obj]
    if isinstance(obj, str) and obj in mk:
        return "***"
    return obj


def chup_config(pidx, accounts, cfg):
    """Config cua party `pidx` doc tu `config` LUC CHAY (PC nap tu accounts.json, APK do Kotlin
    do vao) -> giong nhau o hai ban. `accounts` = [(u, p, ...)] (ctrl.party_accounts)."""
    users = [a[0] for a in accounts]
    mat_khau = [a[1] for a in accounts if len(a) > 1]
    rieng = {}
    for u in users:
        d = {}
        for ten in sorted(n for n in dir(cfg) if n.startswith("ACCOUNT_")):
            bang = getattr(cfg, ten, None)
            if isinstance(bang, dict) and u in bang:
                d[ten[len("ACCOUNT_"):].lower()] = bang[u]
        rieng[u] = d
    snap = {
        "party": pidx + 1,
        "accounts": users,
        "party_config": dict((getattr(cfg, "PARTY_CONFIG", {}) or {}).get(pidx, {}) or {}),
        "account_config": rieng,
        "leaders_chung": list(getattr(cfg, "PARTY_LEADERS", []) or []),
        "leaders_party": list((getattr(cfg, "PARTY_LEADERS_BY_IDX", {}) or {}).get(pidx, []) or []),
        "channel": getattr(cfg, "CHANNEL", None),
    }
    return bo_mat_khau(snap, mat_khau)


# ---------------------------------------------------------------- log

def cac_file_log(log_path):
    """Cu -> moi (RotatingFileHandler backupCount=2)."""
    return [f for f in (log_path + ".2", log_path + ".1", log_path) if os.path.isfile(f)]


def tim_diem_bat_dau(files, so_party, so_phien=SO_PHIEN, tran=TRAN_LOG_BYTE):
    """Doc NGUOC tu cuoi tim dong moc thu `so_phien` cua party -> (chi so file, offset, tron_dong).

    tron_dong=False: offset roi giua dong (cham tran byte) -> bo dong dau dang do.
    """
    moc = (MOC_PHIEN % so_party).encode("utf-8") + b" "
    con_lai = tran
    gap = 0
    for fi in range(len(files) - 1, -1, -1):
        with open(files[fi], "rb") as fh:
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            duoi = b""
            while end > 0:
                if con_lai <= 0:
                    return fi, end, False
                n = min(_KHOI_DOC, end, con_lai)
                start = end - n
                fh.seek(start)
                # `duoi` < len(moc) byte -> moc bat dau trong `duoi` khong the vua -> khong dem 2 lan
                buf = fh.read(n) + duoi
                pos = len(buf)
                while True:
                    k = buf.rfind(moc, 0, pos)
                    if k < 0:
                        break
                    gap += 1
                    if gap >= so_phien:
                        return fi, _dau_dong(fh, start + k), True
                    pos = k
                duoi = buf[:len(moc) - 1]
                end = start
                con_lai -= n
    return 0, 0, True


def _dau_dong(fh, off):
    lui = max(0, off - 4096)
    fh.seek(lui)
    nl = fh.read(off - lui).rfind(b"\n")
    return lui + nl + 1 if nl >= 0 else lui


def doc_dong_tu(files, fi, off, tron_dong):
    bo_dau = not tron_dong and off > 0
    for i in range(fi, len(files)):
        with open(files[i], "rb") as fh:
            fh.seek(off if i == fi else 0)
            for raw in fh:
                if bo_dau:
                    bo_dau = False
                    continue
                yield raw.decode("utf-8", "replace")


def thuoc_party(line, so_party, nhan):
    m = _NHAN_RE.match(line)
    if m:
        tag = m.group(1)
        if tag in nhan:
            return True
        mp = _NHAN_PARTY_RE.match(tag)
        return bool(mp) and int(mp.group(1)) == so_party
    m = _DONG_PARTY_RE.match(line)
    if m:
        return int(m.group(1)) == so_party
    return True   # dong he thong khong nhan (START TAT CA, update...) - hiem, giu lai


def loc_dong(lines, so_party, nhan, mat_khau=()):
    """Giu dong cua party: [party N] / [PN ..] / nhan acc (username, ten nhan vat, ten~user).
    Dong khong co gio (traceback) di theo dong co gio ngay tren. `nhan` duoc bo sung dan tu cac
    dong "[user] NHAN LOG -> 'ten'" (acc doi nhan sang ten nhan vat luc login)."""
    mk = [m for m in mat_khau if m and len(m) >= 4]
    giu = False
    for line in lines:
        if _GIO_RE.match(line):
            m = _DOI_NHAN_RE.match(line)
            if m and m.group(1) in nhan:
                nhan.add(m.group(2))
            giu = thuoc_party(line, so_party, nhan)
        if giu:
            for p in mk:
                if p in line:
                    line = line.replace(p, "***")
            yield line


def trich_log(log_path, pidx, nhan, mat_khau=(), so_phien=SO_PHIEN, tran=TRAN_LOG_BYTE):
    files = cac_file_log(log_path)
    if not files:
        return iter(())
    fi, off, tron = tim_diem_bat_dau(files, pidx + 1, so_phien, tran)
    return loc_dong(doc_dong_tu(files, fi, off, tron), pidx + 1, set(nhan), mat_khau)


# ---------------------------------------------------------------- zip + gui

def dong_goi(zip_path, info, cfg_snap, dong_log):
    os.makedirs(os.path.dirname(zip_path) or ".", exist_ok=True)
    so_dong = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("info.json", json.dumps(info, ensure_ascii=False, indent=2, default=str))
        z.writestr("config.json", json.dumps(cfg_snap, ensure_ascii=False, indent=2, default=str))
        with z.open("party.log", "w") as f:
            for line in dong_log:
                f.write(line.encode("utf-8"))
                so_dong += 1
    return so_dong


def _multipart(fields, file_field, file_name, data):
    bien = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                    % (bien, k, v)).encode("utf-8"))
    out.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                "Content-Type: application/zip\r\n\r\n" % (bien, file_field, file_name)).encode("utf-8"))
    out.append(data)
    out.append(("\r\n--%s--\r\n" % bien).encode("utf-8"))
    return b"".join(out), "multipart/form-data; boundary=" + bien


def gui_telegram(zip_path, caption, bot, timeout=180):
    """sendDocument toi chat cua dev. Loi -> nem RuntimeError co ly do de hien cho user."""
    with open(zip_path, "rb") as fh:
        data = fh.read()
    body, ctype = _multipart({"chat_id": bot["chat_id"], "caption": caption[:TELEGRAM_CAPTION_TOI_DA]},
                             "document", os.path.basename(zip_path), data)
    url = "https://api.telegram.org/bot%s/sendDocument" % bot["token"]
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype})
    try:
        res = _mo(req, timeout)
    except urllib.error.HTTPError as e:
        try:
            ly_do = json.loads(e.read().decode("utf-8", "replace")).get("description")
        except Exception:
            ly_do = None
        raise RuntimeError("Telegram trả lỗi %s: %s" % (e.code, ly_do or e.reason))
    if not res.get("ok"):
        raise RuntimeError("Telegram từ chối: %s" % res.get("description"))
    return res


def _mo(req, timeout):
    import ssl
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        # Python nhung trong APK co the thieu kho chung chi -> thu lai khong xac thuc (noi dung
        # gui di la bao loi, khong co mat khau).
        if not isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def _caption(info):
    return "\n".join([
        "🐞 %s" % info["ma"],
        "Party %s · %s · %s" % (info["party"], info.get("mode") or "?", info.get("server") or "?"),
        "%s app v%s · core v%s" % (info.get("nen_tang"), info.get("app_version"), info.get("core_version")),
        "",
        info.get("mo_ta", ""),
    ])


def tao_bao_loi(pidx, mo_ta, accounts, nhan, cfg, log_path, thu_muc, app_info=None,
                gui=gui_telegram, bot=None, now=None):
    """Toan bo luong bao loi. KHONG nem loi - tra dict cho UI:
    {"ok": bool, "ma": str, "loi": str, "file": zip con giu lai (gui hong), "kb": int}."""
    global _lan_gui_cuoi
    mo_ta = (mo_ta or "").strip()
    if len(mo_ta) < MO_TA_TOI_THIEU:
        return {"ok": False, "ma": "", "loi": "Mô tả lỗi ít nhất %d ký tự." % MO_TA_TOI_THIEU, "file": ""}
    with _khoa_gui:
        cho = CACH_NHAU_SEC - (time.time() - _lan_gui_cuoi)
        if _lan_gui_cuoi and cho > 0:
            return {"ok": False, "ma": "", "loi": "Vừa gửi báo lỗi, chờ %d giây nữa." % int(cho + 1),
                    "file": ""}
        _lan_gui_cuoi = time.time()
    now = now or datetime.datetime.now()
    ma = tao_ma(now)
    app_info = dict(app_info or {})
    mat_khau = [a[1] for a in accounts if len(a) > 1]
    cfg_snap = chup_config(pidx, accounts, cfg)
    pc = cfg_snap.get("party_config") or {}
    info = {
        "ma": ma,
        "mo_ta": mo_ta,
        "party": pidx + 1,
        "mode": pc.get("mode"),
        "server": pc.get("server") or pc.get("server_ip"),
        "game": pc.get("game"),
        "gio_gui": now.strftime("%Y-%m-%d %H:%M:%S"),
        "core_version": app_info.pop("core_version", None) or phien_ban(),
        "app_version": app_info.pop("app_version", None) or phien_ban(),
        "nen_tang": app_info.pop("nen_tang", None) or ("Android" if hasattr(sys, "getandroidapilevel")
                                                         else "PC"),
        "he_dieu_hanh": platform.platform(),
        "python": sys.version.split()[0],
    }
    info.update(app_info)
    zip_path = os.path.join(thu_muc, THU_MUC_LUU, ma + ".zip")
    kb = 0
    try:
        so_dong = dong_goi(zip_path, info, cfg_snap,
                           trich_log(log_path, pidx, set(nhan) | {a[0] for a in accounts}, mat_khau))
        kb = os.path.getsize(zip_path) // 1024
        log.info("[party %d] BAO LOI %s: dong goi %d dong log, %d KB", pidx + 1, ma, so_dong, kb)
        if kb * 1024 > TELEGRAM_FILE_TOI_DA:
            raise RuntimeError("file %d MB quá lớn để gửi" % (kb // 1024))
        bot = bot or doc_bot(cfg, thu_muc)
        if not bot:
            raise RuntimeError("bản này chưa cấu hình kênh gửi báo lỗi (%s)" % TEN_FILE_BOT)
        gui(zip_path, _caption(info), bot)
    except Exception as e:
        log.warning("[party %d] BAO LOI %s that bai: %s", pidx + 1, ma, e)
        with _khoa_gui:
            _lan_gui_cuoi = 0.0
        giu = zip_path if os.path.isfile(zip_path) else ""
        return {"ok": False, "ma": ma, "loi": str(e), "file": giu, "kb": kb}
    try:
        os.remove(zip_path)
    except OSError:
        pass
    log.info("[party %d] BAO LOI %s: da gui", pidx + 1, ma)
    return {"ok": True, "ma": ma, "loi": "", "file": "", "kb": kb}
