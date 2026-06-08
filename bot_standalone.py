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

# Console UTF-8 (tranh loi khi log ten pet tieng Viet tren Windows)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import datetime
from bot import config
from bot.login import login
from bot.client import GameClient, mail_window_now

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
            client._username = username
            client.party_idx = config.ACCOUNT_PARTY.get(username)
            client.submit_delay = 1
            client.connect()

            # Cho vao world (co self_entity)
            for _ in range(10):
                if client.self_entity:
                    break
                time.sleep(1)
            time.sleep(2)   # cho broadcast cap nhat map_id

            client.request_offline_exp()   # nhan exp offline neu co
            client.claim_mail()            # nhan qua mail + xoa mail da doc
            client.claim_checkin()         # diem danh hang ngay (tu dem so lan)

            if config.START_CITY_ID == 0:
                # Khong teleport ve thanh, dung yen tai cho login. Vao tran thi cu danh.
                log.info("[%s] START_CITY_ID=0 -> khong ve thanh", label)
            else:
                # Neu dang ket trong Di Gioi -> di ra truoc khi teleport
                if client.in_di_gioi():
                    log.info("[%s] Dang trong Di Gioi -> di ra...", label)
                    client.exit_di_gioi()
                # Ve thanh (lap lai neu battle chan teleport)
                client.go_to_town(config.START_CITY_ID, config.START_CITY_FLAG)
                log.info("[%s] Da ve thanh %d", label, config.START_CITY_ID)

            # Chuyen kenh (lam ca khi START_CITY_ID=0) de cung kenh voi chu party
            if config.CHANNEL:
                time.sleep(2)
                client.switch_channel(config.CHANNEL)
                log.info("[%s] Da chuyen kenh %d", label, config.CHANNEL)

            if getattr(config, "ENTER_DIGIOI", False):
                time.sleep(2)
                client.enter_di_gioi()   # solo train Di Gioi (khong party)
                time.sleep(2)
                client.pick_best_channel()   # tu chuyen sang kenh it nguoi nhat
                time.sleep(2)
                client.start_run_around()   # auto-chay theo route de gap quai
                log.info("[%s] Da vao Di Gioi + chon kenh + auto-chay - tu dong danh", label)
            else:
                log.info("[%s] San sang - cho chu party '%s' moi + tu dong danh",
                         label, config.LEADER_NAME)

            # giu song, tu nhan qua online (60s) + mail theo khung gio (12-14,16-18,22-24)
            last_gift = time.time()
            mail_done = None   # (ngay, khung_gio) da nhan trong khung do
            gifts_done = False
            while client.running and not _stop.is_set():
                time.sleep(2)
                if not gifts_done and time.time() - last_gift >= 60:
                    gifts_done = client.claim_online_gifts()
                    last_gift = time.time()
                w = mail_window_now()
                if w is not None and (datetime.date.today(), w) != mail_done:
                    client.claim_mail()
                    mail_done = (datetime.date.today(), w)

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
