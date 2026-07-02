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

QUY UOC GOI CALLBACK TU KOTLIN (quan trong cho BotForegroundService o task sau):
  Chaquopy KHONG cho Python goi truc tiep mot doi tuong Kotlin/Java bat ky bang cu
  phap obj(...) (khong tu dong proxy __call__ cho SAM/lambda). Vi vay should_stop/
  on_status o day PHAI la doi tuong co PHUONG THUC ten "call" (vd Kotlin
  `object { fun call(...) }`), va duoc goi qua .call(...) - KHONG goi truc tiep
  should_stop()/on_status(...). Day la hop dong API on dinh cho phia Kotlin khi
  wire BotForegroundService.
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
    on_status.call("connecting", None, None, None, None, "Dang dang nhap...")
    try:
        cred = login_mod.login(username, password)
    except Exception as e:
        on_status.call("error", None, None, None, None, f"Login loi: {e}")
        return

    try:
        c = GameClient(cred["user_id"], cred["access_token"], host=server_ip,
                        server_id=server_id)
        c._label = username
        c.connect()
    except Exception as e:
        on_status.call("error", None, None, None, None, f"Ket noi loi: {e}")
        return

    def wander():
        while c.running and not should_stop.call():
            if not c.in_combat():
                x, y = random.choice(WANDER_POINTS)
                try:
                    c.send(0x06, b"\x01\x00\x01" + struct.pack("<H", x) + struct.pack("<H", y))
                except OSError:
                    break
            time.sleep(2)

    threading.Thread(target=wander, daemon=True).start()
    on_status.call("running", None, None, None, None, "Da vao game, dang treo cay")

    while c.running and not should_stop.call():
        time.sleep(3)
        ch = c.state.char
        on_status.call("running", ch.hp, ch.sp, ch.hp_max, ch.sp_max, "")

    c.close()
    on_status.call("stopped", None, None, None, None, "Da dung")


class _CallableStub:
    """Boc 1 ham Python thanh doi tuong co .call(...) - mo phong dung HOP DONG API
    ma phia Kotlin se dung that (object { fun call(...) }), de test thuan Python
    van di qua CHINH XAC duong goi .call() nhu production, khong test rieng 1
    duong khac (goi truc tiep) roi tuong da dung."""
    def __init__(self, fn):
        self._fn = fn

    def call(self, *args):
        return self._fn(*args)


def run_train_sync_for_test(username: str, password: str, server_ip: str, server_id: int) -> str:
    """Wrapper THUAN PYTHON cho instrumented test: goi run_train() voi callback thu thap
    trang thai vao list noi bo, boc qua _CallableStub de di dung qua .call() convention
    (xem docstring module ve ly do khong goi obj(...) truc tiep).
    Tra ve state CUOI CUNG da ghi nhan ("error"/"stopped"/"running"/...). should_stop=True
    ngay lap tuc -> neu login/connect thanh cong thi vong lap chinh thoat ngay sau 1 vong,
    khong treo test that."""
    states = []

    def _on_status(state, hp, sp, hp_max, sp_max, message):
        states.append(state)

    should_stop = _CallableStub(lambda: True)
    on_status = _CallableStub(_on_status)
    run_train(username, password, server_ip, server_id, should_stop, on_status)
    return states[-1] if states else ""
