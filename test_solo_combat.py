"""Test combat SOLO trong Di Gioi: bot tu di chuyen -> gap quai -> danh.
Muc dich: kiem tra packet 0x32 (atype=1, tail=0000) co duoc server chap nhan khong.
"""
import time, logging, struct, random, threading
from bot.login import login
from bot.client import GameClient
from bot import protocol

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
                    handlers=[logging.FileHandler("solo_combat.log", "w", "utf-8"), logging.StreamHandler()])
log = logging.getLogger("solo")

cred = login()
c = GameClient(cred["user_id"], cred["access_token"])

# theo doi vi tri self tu S2C 0x06
c.self_pos = None
orig = c._dispatch
def hook(op, pkt):
    if op == 0x06 and c.self_entity and c.self_entity in pkt:
        i = pkt.find(c.self_entity) + 8
        if i + 4 <= len(pkt):
            c.self_pos = (struct.unpack_from("<H", pkt, i)[0], struct.unpack_from("<H", pkt, i+2)[0])
    return orig(op, pkt)
c._dispatch = hook

c.connect()
time.sleep(4)
log.info("self_pos ban dau: %s", c.self_pos)

# Wander: gui move toi cac toa do ngau nhien trong Di Gioi de gap quai
def wander():
    pts = [(300,250),(500,400),(700,500),(450,300),(250,200),(600,450)]
    while c.running:
        if not c.in_combat():        # chi di chuyen khi KHONG trong tran
            x, y = random.choice(pts)
            payload = b"\x01\x00\x01" + struct.pack("<H", x) + struct.pack("<H", y)
            try:
                c.send(0x06, payload)
            except OSError:
                break
            log.info("WANDER -> (%d,%d) | char HP=%s SP=%s", x, y, c.state.char.hp, c.state.char.sp)
        time.sleep(2)

threading.Thread(target=wander, daemon=True).start()
log.info(">>> Bot dang wander trong Di Gioi tim quai. Giu 180s.")
time.sleep(180)
c.close()
