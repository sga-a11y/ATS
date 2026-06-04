"""Bot treo cay solo trong Di Gioi: wander -> gap quai -> danh -> lap lai.

Chay: python run_grind.py [phut]   (mac dinh 60 phut)
"""
import sys, time, logging, struct, random, threading
from bot.login import login
from bot.client import GameClient

MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[logging.FileHandler("grind.log", "w", "utf-8"), logging.StreamHandler()])
log = logging.getLogger("grind")

cred = login()
c = GameClient(cred["user_id"], cred["access_token"])

import struct as _st
stats = {"battles": 0, "last_level_hp": 0}
counters = {}   # id 0x55 -> value moi nhat

orig = c._dispatch
def hook(op, pkt):
    if op == 0x34 and len(pkt) == 9:
        stats["battles"] += 1
    elif op == 0x55 and len(pkt) >= 19:
        counters[pkt[13]] = _st.unpack_from("<H", pkt, 15)[0]
    return orig(op, pkt)
c._dispatch = hook

c.connect()
time.sleep(4)
log.info(">>> Bat dau treo cay Di Gioi %d phut", MINUTES)

# Wander: chi di chuyen khi KHONG trong tran
def wander():
    pts = [(300,250),(500,400),(700,500),(450,300),(250,200),(600,450),(400,550),(650,300)]
    while c.running:
        if not c.in_combat():
            x, y = random.choice(pts)
            try:
                c.send(0x06, b"\x01\x00\x01" + struct.pack("<H", x) + struct.pack("<H", y))
            except OSError:
                break
        time.sleep(2)
threading.Thread(target=wander, daemon=True).start()

# Log tien do moi 30s
t_end = time.time() + MINUTES * 60
while time.time() < t_end and c.running:
    time.sleep(30)
    ch = c.state.char
    if ch.hp_max and ch.hp_max != stats["last_level_hp"]:
        stats["last_level_hp"] = ch.hp_max
    cstr = " ".join(f"0x{k:02x}={v}" for k, v in sorted(counters.items()))
    log.info("Tran: %d | char HP=%s/%s SP=%s/%s | counters: %s",
             stats["battles"], ch.hp, ch.hp_max, ch.sp, ch.sp_max, cstr)

c.close()
log.info(">>> Ket thuc. Tong %d tran.", stats["battles"])
