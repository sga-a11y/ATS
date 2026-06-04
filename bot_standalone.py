"""TS Online - TOOL TREO MAY DOC LAP (khong can Claude).

Cach dung:
  1. Copy bot/config.example.py -> bot/config.py, dien USERNAME / PASSWORD / API_KEY...
     va danh sach ACCOUNTS (1 hoac nhieu acc), LEADER_NAME (ten chu party).
  2. Chay:  python bot_standalone.py
     (hoac double-click  run_bot.bat)

Bot se:
  - Login + ket noi game
  - Teleport ve thanh xuat phat + dung kenh (de chu party moi)
  - Tu dong nhan loi moi party va danh theo chu party (AI target thong minh)
  - CHAY VO HAN: bi rot mang -> tu dong dang nhap & ket noi lai
  - Chi dung khi Anh tat (dong cua so / Ctrl+C)
"""
import sys
import time
import logging
import threading

from bot import config
from bot.login import login
from bot.client import GameClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler("bot.log", "a", "utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("tool")

_stop = threading.Event()


def run_account(username: str, password: str, idx: int = 0):
    """Vong lap vo han cho 1 account: login -> danh -> rot thi ket noi lai."""
    label = username
    while not _stop.is_set():
        client = None
        try:
            cred = login(username, password)
            log.info("[%s] Login OK (user_id=%s)", label, cred["user_id"])

            client = GameClient(cred["user_id"], cred["access_token"])
            client._label = label
            # stagger nhe giua cac acc (tranh dong loat trong 20s quyet dinh)
            client.submit_delay = 1.0 + 1.5 * idx
            client.connect()

            time.sleep(4)
            client.teleport(config.START_CITY_ID, config.START_CITY_FLAG)
            if config.CHANNEL:
                time.sleep(3)
                client.switch_channel(config.CHANNEL)
            log.info("[%s] San sang - cho chu party '%s' moi + tu dong danh",
                     label, config.LEADER_NAME)

            # giu song den khi rot ket noi hoac duoc yeu cau dung
            while client.running and not _stop.is_set():
                time.sleep(2)

        except Exception as e:
            log.error("[%s] Loi: %s", label, e)
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

        if _stop.is_set():
            break
        log.warning("[%s] Mat ket noi -> ket noi lai sau %ds...",
                    label, config.RECONNECT_DELAY)
        _stop.wait(config.RECONNECT_DELAY)

    log.info("[%s] Da dung.", label)


def main():
    accounts = getattr(config, "ACCOUNTS", None) or [(config.USERNAME, config.PASSWORD)]
    log.info("=== TS Online Bot - treo may %d account. Nhan Ctrl+C de dung. ===",
             len(accounts))

    threads = []
    for i, (u, p) in enumerate(accounts):
        t = threading.Thread(target=run_account, args=(u, p, i), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(1.5)

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        log.info(">>> Dang dung bot (Ctrl+C)...")
        _stop.set()
        for t in threads:
            t.join(timeout=5)
        log.info(">>> Da dung toan bo bot.")


if __name__ == "__main__":
    main()
