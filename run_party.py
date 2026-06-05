"""Chay nhieu bot member cung luc. Moi bot: login -> connect -> auto-accept party -> auto-fight.

Leader (haba) do user dieu khien. Bots = member, tu accept + danh.
"""
import sys, time, logging, threading
from bot.login import login
from bot.client import GameClient

import os as _os
_lvl = logging.DEBUG if _os.environ.get("DEBUG") else logging.INFO
logging.basicConfig(level=_lvl, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[logging.FileHandler("party.log", "w", "utf-8"), logging.StreamHandler()])
log = logging.getLogger("party")

from bot import config
# Danh sach account lay tu bot/config.py (gitignored - khong commit secret)
ACCOUNTS = config.ACCOUNTS
MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 30

clients = []

def run_account(username, password, idx=0):
    try:
        cred = login(username, password)
        log.info("[%s] login OK user_id=%s", username, cred["user_id"])
        c = GameClient(cred["user_id"], cred["access_token"])
        c._label = username
        c.submit_delay = 1.0 + 6.0 * idx   # stagger ro: sga001=1s, sga002=7s (trong 20s)
        c.connect()
        clients.append(c)
        time.sleep(4)
        c.teleport(12001, 0)   # Trac Quan
        time.sleep(3)
        c.switch_channel(6)    # cung kenh voi haba
        log.info("[%s] da connect + Trac Quan + kenh 6, cho moi party + danh", username)
    except Exception as e:
        log.error("[%s] LOI: %s", username, e)

# Login + connect tat ca (cach nhau 1s tranh dồn)
for i, (u, p) in enumerate(ACCOUNTS):
    threading.Thread(target=run_account, args=(u, p, i), daemon=True).start()
    time.sleep(1.5)

log.info(">>> %d bot member dang chay. Haba moi sga001+sga002 vao party + danh. Giu %d phut.", len(ACCOUNTS), MINUTES)

# Console-file: ghi lenh vao command.txt de dieu khien live (khong can restart)
#   vd:  tp 12061 2   |  channel 38  |  quit
import os
CMD_FILE = "command.txt"
open(CMD_FILE, "w").close()
def poll_commands():
    while True:
        time.sleep(1)
        try:
            txt = open(CMD_FILE).read().strip()
        except FileNotFoundError:
            continue
        if not txt:
            continue
        open(CMD_FILE, "w").close()  # clear sau khi doc
        parts = txt.split()
        cmd = parts[0].lower()
        try:
            if cmd == "tp" and len(parts) >= 3:
                for c in clients: c.teleport(int(parts[1]), int(parts[2]))
            elif cmd == "channel" and len(parts) >= 2:
                for c in clients: c.switch_channel(int(parts[1]))
            elif cmd == "digioi":
                for c in clients: c.enter_di_gioi()
            elif cmd == "quit":
                for c in clients: c.close()
            else:
                log.info("Lenh la: %s", txt)
        except Exception as e:
            log.error("Loi lenh '%s': %s", txt, e)
threading.Thread(target=poll_commands, daemon=True).start()

try:
    time.sleep(MINUTES * 60)
except KeyboardInterrupt:
    pass
for c in clients:
    c.close()
log.info(">>> Ket thuc.")
