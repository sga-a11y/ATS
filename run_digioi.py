"""Vao Di Gioi ngam canh - khong combat.
Login nhieu acc, vao Di Gioi, dung yen (chi heartbeat).
Chay: python run_digioi.py [phut]  (mac dinh: vo han)

Dung chung ACCOUNTS tu bot/config.py.
"""
import sys
import time
import logging
import threading

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import datetime
from bot import config
from bot.login import login
from bot.client import GameClient, mail_window_now

MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 0   # 0 = vo han

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler("digioi.log", "a", "utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("digioi")

_stop = threading.Event()
_active = threading.Event()   # set khi con acc dang chay
_active.set()


def run_account(username: str, password: str, idx: int = 0):
    label = username
    digioi_done = False   # True = het gio Di Gioi hom nay -> khong reconnect
    while not _stop.is_set() and not digioi_done:
        client = None
        try:
            cred = login(username, password)
            log.info("[%s] Login OK (user_id=%s)", label, cred["user_id"])

            client = GameClient(cred["user_id"], cred["access_token"])
            client._label = label
            client.auto_combat = True           # tu danh neu vao battle
            client.auto_accept_party = True     # nhan invite party + pho ban
            DIGIOI_LIMIT = 120

            client.connect()

            # Cho vao world
            for _ in range(10):
                if client.self_entity:
                    break
                time.sleep(1)

            # Stagger giua cac acc
            time.sleep(2 + idx * 3)

            client.request_offline_exp()   # nhan exp offline neu co
            client.claim_mail()            # nhan qua mail + xoa mail da doc

            if client.in_di_gioi():
                # Da o Di Gioi roi -> dung yen luon
                log.info("[%s] Da o Di Gioi (map=%s) -> giu nguyen", label, client.current_map)
                ch = None
            else:
                # Ve thanh -> vao Di Gioi
                log.info("[%s] Ve thanh %d...", label, config.START_CITY_ID)
                client.go_to_town(config.START_CITY_ID, config.START_CITY_FLAG)
                log.info("[%s] Vao Di Gioi...", label)
                client.enter_di_gioi()
                time.sleep(5)
                ch = client.pick_best_channel()

            log.info("[%s] Di Gioi - kenh %s - ngam canh...", label, ch)

            # Giu song, kiem tra moi 60s: nhan qua online + theo doi timer Di Gioi
            # Het gio Di Gioi = server NGUNG gui timer 0x1b (digioi_done).
            t_end = time.time() + MINUTES * 60 if MINUTES else float('inf')
            gifts_done = False
            no_timer_count = 0
            mail_done = None
            while client.running and not _stop.is_set() and time.time() < t_end:
                time.sleep(60)
                if not gifts_done:
                    gifts_done = client.claim_online_gifts()
                w = mail_window_now()
                if w is not None and (datetime.date.today(), w) != mail_done:
                    client.claim_mail()
                    mail_done = (datetime.date.today(), w)

                # Da ROI map Di Gioi (vd bi keo vao party/pho ban) -> KHONG xet het gio,
                # khong tu ngat. Chi xet timeout khi VAN CON trong map Di Gioi.
                if not client.in_di_gioi():
                    no_timer_count = 0
                    continue

                # Timer "cu" hoac chua bao gio nhan -> server ngung gui = het gio Di Gioi
                stale = (client._last_digioi_ts == 0
                         or time.time() - client._last_digioi_ts > 150)
                if stale:
                    no_timer_count += 1
                    log.info("[%s] Khong co timer Di Gioi (%d/2)", label, no_timer_count)
                    if no_timer_count >= 2:
                        log.warning("[%s] Da het gio Di Gioi -> di ra ngoai roi thoat", label)
                        digioi_done = True
                        break
                    continue
                no_timer_count = 0

                # Co timer -> tinh thoi gian con lai
                remain = max(0, DIGIOI_LIMIT - client.digioi_minutes)
                h, m = divmod(remain, 60)
                log.info("[%s] Di Gioi con lai: %dh%dm", label, h, m)
                if remain == 0:
                    log.warning("[%s] HET GIO DI GIOI -> di ra ngoai roi thoat", label)
                    digioi_done = True
                    break
                if remain <= 5:
                    log.warning("[%s] SAP HET GIO (%d phut)!", label, remain)

            # Het gio Di Gioi -> di ra ngoai truoc khi thoat
            if digioi_done and client.running and client.in_di_gioi():
                log.info("[%s] Di ra khoi Di Gioi...", label)
                try:
                    client.exit_di_gioi()
                except Exception as e:
                    log.warning("[%s] Loi khi ra khoi Di Gioi: %s", label, e)

        except Exception as e:
            log.error("[%s] Loi: %s", label, e)
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

        if _stop.is_set() or digioi_done:
            break
        log.warning("[%s] Mat ket noi -> thu lai sau %ds...", label, config.RECONNECT_DELAY)
        _stop.wait(config.RECONNECT_DELAY)

    if digioi_done:
        log.info("[%s] Het gio Di Gioi hom nay.", label)
    else:
        log.info("[%s] Da dung.", label)


def main():
    accounts = getattr(config, "ACCOUNTS", None) or [(config.USERNAME, config.PASSWORD)]
    log.info("=== Di Gioi bot - %d acc%s. Ctrl+C de dung. ===",
             len(accounts), f" - {MINUTES} phut" if MINUTES else " - vo han")

    threads = []
    for i, (u, p) in enumerate(accounts):
        t = threading.Thread(target=run_account, args=(u, p, i), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(2)

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
        log.info(">>> Tat ca acc da het gio Di Gioi. Bot tu dong tat.")
    except KeyboardInterrupt:
        log.info(">>> Dang dung (Ctrl+C)...")
        _stop.set()
        for t in threads:
            t.join(timeout=5)
        log.info(">>> Da dung.")


if __name__ == "__main__":
    main()
