"""Vong lap chay 1 account o mode Train - phong theo run_grind.py (PC), nhan
credentials truc tiep tu tham so (khong doc config.py), goi callback Kotlin de
bao trang thai (dung cho BotForegroundService cap nhat StateFlow).

Luu y API thuc te (doi chieu train_bot/client.py, train_bot/login.py):
  - login.login(username, password) -> {"user_id", "access_token", "username"}
  - GameClient(user_id, access_token, host=None, server_id=1)  (KHONG phai server_ip=)
    host=None -> mac dinh config.GAME_HOST. Android truyen host=server_ip de override
    server IP theo tung account/party (multi-server support).
  - client.connect() khong nhan tham so, tu chay _recv_loop/_heartbeat_loop (thread rieng)
  - client.running (bool), client.in_combat(), client.close()
  - client.state.char / client.state.pet la state.Unit: .hp/.hp_max/.sp/.sp_max
"""
import threading
import random
import struct
import time

from . import login as login_mod
from .client import GameClient

WANDER_POINTS = [(300, 250), (500, 400), (700, 500), (450, 300),
                  (250, 200), (600, 450), (400, 550), (650, 300)]


def run_train(username: str, password: str, server_ip: str, server_id: int,
              should_stop, on_status):
    """Chay den khi should_stop() tra True hoac loi khong the phuc hoi.
    on_status(state: str, hp, sp, hp_max, sp_max, message: str) goi moi khi trang
    thai doi (state: "connecting"|"running"|"error"|"stopped")."""
    on_status("connecting", None, None, None, None, "Dang dang nhap...")
    try:
        cred = login_mod.login(username, password)
    except Exception as e:
        on_status("error", None, None, None, None, f"Login loi: {e}")
        return

    try:
        c = GameClient(cred["user_id"], cred["access_token"], host=server_ip,
                        server_id=server_id)
        c._label = username
        c.connect()
    except Exception as e:
        on_status("error", None, None, None, None, f"Ket noi loi: {e}")
        return

    def wander():
        while c.running and not should_stop():
            if not c.in_combat():
                x, y = random.choice(WANDER_POINTS)
                try:
                    c.send(0x06, b"\x01\x00\x01" + struct.pack("<H", x) + struct.pack("<H", y))
                except OSError:
                    break
            time.sleep(2)

    threading.Thread(target=wander, daemon=True).start()
    on_status("running", None, None, None, None, "Da vao game, dang treo cay")

    while c.running and not should_stop():
        time.sleep(3)
        ch = c.state.char
        on_status("running", ch.hp, ch.sp, ch.hp_max, ch.sp_max, "")

    c.close()
    on_status("stopped", None, None, None, None, "Da dung")


def run_train_sync_for_test(username: str, password: str, server_ip: str, server_id: int) -> str:
    """Wrapper THUAN PYTHON cho instrumented test: goi run_train() voi callback thu thap
    trang thai vao list noi bo (khong can Kotlin proxy callback vao Python - Chaquopy 16.0.0
    khong ho tro goi truc tiep obj(...) tren Java lambda tuy y qua call-syntax Python).
    Tra ve state CUOI CUNG da ghi nhan ("error"/"stopped"/"running"/...). should_stop=True
    ngay lap tuc (lambda: True) -> neu login/connect thanh cong thi vong lap chinh thoat
    ngay sau 1 vong, khong treo test that."""
    states = []

    def _on_status(state, hp, sp, hp_max, sp_max, message):
        states.append(state)

    run_train(username, password, server_ip, server_id, lambda: True, _on_status)
    return states[-1] if states else ""
