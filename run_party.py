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
_chosen_channel = {"ch": None}   # bot dau chon kenh it nguoi -> bot sau theo cung kenh

def run_account(username, password, idx=0):
    try:
        c = None
        # Login + dam bao VAO WORLD (co self_entity). Chua duoc -> thu lai.
        for attempt in range(5):
            cred = login(username, password)
            log.info("[%s] login OK user_id=%s (lan %d)", username, cred["user_id"], attempt + 1)
            c = GameClient(cred["user_id"], cred["access_token"])
            c._label = username
            c.state.has_fire = username not in getattr(config, "NO_FIRE_ACCOUNTS", set())
            c.submit_delay = 1.0 + 1.5 * idx
            c.connect()
            time.sleep(5)
            if c.self_entity is not None:
                break   # da vao world
            log.warning("[%s] CHUA vao world (no self_entity) -> login lai sau 5s...", username)
            c.close()
            time.sleep(5)
        if not c.state.has_fire:
            log.info("[%s] Account KHONG co Hoa Tien -> chi danh thuong + ho tro", username)
        clients.append(c)
        time.sleep(2)   # cho broadcast cap nhat map_id hien tai
        log.info("[%s] map_id hien tai = %s (Di Gioi=%s)", username, c.current_map, config.DIGIOI_MAP_ID)
        # neu dang KET trong Di Gioi (map_id = Di Gioi) -> thoat truoc khi teleport
        if c.in_di_gioi():
            log.info("[%s] Dang trong Di Gioi (map %s) -> thoat...", username, c.current_map)
            c.exit_di_gioi()
        c.teleport(config.START_CITY_ID, config.START_CITY_FLAG)   # mac dinh Ng.Thanh (config)
        time.sleep(3)
        if idx == 0:
            ch = c.pick_best_channel()         # bot dau: chon kenh it nguoi nhat
            _chosen_channel["ch"] = ch
        else:
            # cho bot dau chon xong roi vao CUNG kenh (de cung party)
            for _ in range(20):
                if _chosen_channel["ch"]:
                    break
                time.sleep(0.5)
            ch = _chosen_channel["ch"]
            if ch:
                c.switch_channel(ch)
        log.info("[%s] da connect + Trac Quan + KENH %s (it nguoi nhat), cho moi party + danh",
                 username, ch)
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
            elif cmd == "bestchannel":
                for c in clients: c.pick_best_channel()
            elif cmd == "outdigioi":
                # thoat Di Gioi -> teleport ve Trac Quan -> chon kenh it nguoi
                for c in clients:
                    c.exit_di_gioi()
                    c.teleport(12001, 0)
                    time.sleep(3)
                    c.pick_best_channel()
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
