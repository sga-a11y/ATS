"""Keo bao loi cua user ve bug_reports/<ma>/ de doc (documents/BAO_LOI.md).

Bot Telegram KHONG doc lai duoc tin chinh no gui (getUpdates chi co tin gui TOI bot), NHUNG forward
duoc tin do: `forwardMessage` tra ve Message co ca `document.file_id`. Nen script tu quet chat
cua dev: forward IM LANG tung tin moi -> tin nao la BL-*.zip thi tai -> XOA ngay ban forward.
Nho message_id da quet trong bug_reports/.da_quet. Dev khong phai lam gi.

    python tools/bug_inbox.py                  # quet chat bot (+ thu muc tai Telegram Desktop)
    python tools/bug_inbox.py BL-1007-4F2A.zip # hoac chi dinh file / thu muc zip
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICH = os.path.join(ROOT, "bug_reports")
ZIP_DIR = os.path.join(DICH, "_zip")
MOC_QUET = os.path.join(DICH, ".da_quet")
NGUON_MAC_DINH = os.path.join(os.path.expanduser("~"), "Downloads", "Telegram Desktop")


# ---------------------------------------------------------------- Telegram

def _bot():
    sys.path.insert(0, ROOT)
    from bot import bug_report
    bot = bug_report.doc_bot(None, ROOT)
    if not bot:
        raise RuntimeError("thieu %s" % bug_report.TEN_FILE_BOT)
    return bot


def _goi(bot, method, **params):
    """Bot API. 429 (gui qua nhanh vao cung chat) -> cho dung retry_after roi thu lai."""
    data = json.dumps(params).encode("utf-8")
    url = "https://api.telegram.org/bot%s/%s" % (bot["token"], method)
    for _ in range(5):
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))["result"]
        except urllib.error.HTTPError as e:
            body = json.loads(e.read().decode("utf-8", "replace") or "{}")
            cho = (body.get("parameters") or {}).get("retry_after")
            if e.code == 429 and cho:
                time.sleep(cho + 0.5)
                continue
            raise RuntimeError(body.get("description") or str(e))
    raise RuntimeError("%s: bi gioi han toc do qua lau" % method)


def _tai_file(bot, file_id, path):
    info = _goi(bot, "getFile", file_id=file_id)
    url = "https://api.telegram.org/file/bot%s/%s" % (bot["token"], info["file_path"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as fh:
        fh.write(r.read())


def quet_chat_bot():
    """-> [zip moi tai]. Quet message_id (da_quet, tin moi nhat) trong chat dev."""
    bot = _bot()
    chat = bot["chat_id"]
    try:
        with open(MOC_QUET, encoding="utf-8") as fh:
            da_quet = int(fh.read().strip() or 0)
    except (OSError, ValueError):
        da_quet = 0
    # Tran tren = message_id cua mot tin thu im lang (xoa ngay).
    tin = _goi(bot, "sendMessage", chat_id=chat, text="…", disable_notification=True)
    tran = tin["message_id"]
    _goi(bot, "deleteMessage", chat_id=chat, message_id=tran)
    out = []
    for k in range(da_quet + 1, tran):
        try:
            ban = _goi(bot, "forwardMessage", chat_id=chat, from_chat_id=chat, message_id=k,
                       disable_notification=True)
        except RuntimeError:
            continue   # id da xoa / khong forward duoc
        try:
            doc = ban.get("document") or {}
            ten = doc.get("file_name") or ""
            if ten.startswith("BL-") and ten.endswith(".zip"):
                path = os.path.join(ZIP_DIR, ten)
                if not os.path.isfile(path):
                    _tai_file(bot, doc["file_id"], path)
                    out.append(path)
        finally:
            _goi(bot, "deleteMessage", chat_id=chat, message_id=ban["message_id"])
    os.makedirs(DICH, exist_ok=True)
    with open(MOC_QUET, "w", encoding="utf-8") as fh:
        fh.write(str(tran))
    return out


# ---------------------------------------------------------------- zip

def tim_zip(nguon):
    out = []
    for n in nguon:
        if os.path.isdir(n):
            out += glob.glob(os.path.join(n, "BL-*.zip"))
        elif os.path.isfile(n):
            out.append(n)
        else:
            print("!! khong thay: %s" % n)
    return out


def giai_nen(zip_path, dich=DICH):
    """-> (ma, thu muc, info) ; da giai nen roi thi info=None."""
    # Telegram Desktop tai trung ten thi them " (1)" -> cat di de ve dung ma
    ma = os.path.splitext(os.path.basename(zip_path))[0].split(" ")[0]
    thu_muc = os.path.join(dich, ma)
    if os.path.isfile(os.path.join(thu_muc, "info.json")):
        return ma, thu_muc, None
    os.makedirs(thu_muc, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for ten in z.namelist():
            if ten not in ("info.json", "config.json", "party.log"):
                continue   # chi 3 file biet truoc - khong giai nen duong dan la
            with open(os.path.join(thu_muc, ten), "wb") as fh:
                fh.write(z.read(ten))
    with open(os.path.join(thu_muc, "info.json"), encoding="utf-8") as fh:
        return ma, thu_muc, json.load(fh)


def main(argv):
    if argv:
        zips = tim_zip(argv)
    else:
        zips = tim_zip([NGUON_MAC_DINH]) if os.path.isdir(NGUON_MAC_DINH) else []
        try:
            zips += quet_chat_bot()
        except Exception as e:
            print("!! quet chat bot loi: %s" % e)
        zips += glob.glob(os.path.join(ZIP_DIR, "BL-*.zip"))
    zips = sorted(set(zips), key=os.path.getmtime)
    if not zips:
        print("Khong co bao loi nao.")
        return 1
    for z in zips:
        ma, thu_muc, info = giai_nen(z)
        if info is None:
            print("= %s da co (%s)" % (ma, os.path.relpath(thu_muc, ROOT)))
            continue
        with open(os.path.join(thu_muc, "party.log"), encoding="utf-8", errors="replace") as fh:
            so_dong = sum(1 for _ in fh)
        print("+ %s  party %s · %s · %s v%s (core v%s) · %s · %d dong log" % (
            ma, info.get("party"), info.get("mode"), info.get("nen_tang"), info.get("app_version"),
            info.get("core_version"), info.get("gio_gui"), so_dong))
        print("    %s" % info.get("mo_ta"))
        print("    -> %s" % os.path.relpath(thu_muc, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
