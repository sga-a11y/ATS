"""Entry point bot TS Online.

Chay:  python run_bot.py
Cac giai doan test (--stage):
  login   : chi test HTTP login
  connect : login + ket noi TCP + auth + heartbeat (quan sat goi tin)
  full    : day du - login, connect, teleport Trac Quan, cho party, auto combat
"""
import sys
import time
import logging

from bot import config
from bot.login import login
from bot.client import GameClient

import os
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "full"

    log.info("Login %s ...", config.USERNAME)
    cred = login()
    log.info("OK: user_id=%s username=%s", cred["user_id"], cred["username"])
    if stage == "login":
        return

    client = GameClient(cred["user_id"], cred["access_token"])
    client.connect()

    if stage == "connect":
        log.info("Stage connect: quan sat 60s...")
        time.sleep(60)
        client.close()
        return

    # full
    time.sleep(3)
    client.teleport(config.START_CITY_ID)
    log.info("Cho nhan loi moi party + auto combat. Ctrl+C de dung.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.close()


if __name__ == "__main__":
    main()
