"""Login 1 account, dump het S2C packet ra file de phan tich pet.
Chay: python dump_login.py <username> <outfile>"""
import sys, time
from bot import config
from bot.login import login
from bot.client import GameClient

user = sys.argv[1]
out = sys.argv[2]
# Lay password tu config.ACCOUNTS (neu co), khong thi mac dinh
pw = dict(config.ACCOUNTS).get(user, "s112233")

cred = login(user, pw)
c = GameClient(cred["user_id"], cred["access_token"])
c._label = user

lines = []
orig = c._dispatch
def hook(op, pkt):
    lines.append(f"{op:02x} {pkt.hex()}")
    return orig(op, pkt)
c._dispatch = hook

c.connect()
time.sleep(8)
c.close()

with open(out, "w") as f:
    f.write(f"self_entity={c.self_entity.hex() if c.self_entity else None}\n")
    f.write("\n".join(lines))
print(f"Dumped {len(lines)} packets -> {out}, self={c.self_entity.hex() if c.self_entity else None}")
