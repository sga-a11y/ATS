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
import time

from . import config
from . import login as login_mod
from .client import GameClient

# Chi 1 che do duy nhat hien tai: DUNG YEN TAI THANH (khong tu di chuyen sau khi ve
# thanh). Ban dau tung dung 1 danh sach toa do CO DINH de "wander" ngau nhien, nhung
# toa do do KHONG biet ban do nao co tuong/chuong ngai gi - dung tren MOI map se
# khien nhan vat di xuyen tuong/ket ket (user phat hien qua test thuc te tren app
# that). Cac che do "tu dong di lang thang theo map" that su can du lieu toa do di
# chuyen duoc theo TUNG map (nhu bot/config.py's train_maps.json/train_routes.json
# ben PC) - CHUA port sang Android, de danh cho ban sau. Gio chi ho tro ve 1 thanh
# CO THAT (nguoi dung chon, xem config.CITIES) roi dung yen tai do cho AN TOAN.
RUN_MODE_STAND_STILL = "stand_still"


def run_train(username: str, password: str, server_ip: str, server_id: int,
              run_mode: str, city_key: str, should_stop, on_status):
    """Chay den khi should_stop() tra True hoac loi khong the phuc hoi.
    on_status(state: str, hp, sp, hp_max, sp_max, message: str) goi moi khi trang
    thai doi (state: "connecting"|"running"|"error"|"stopped").
    run_mode: hien chi ho tro RUN_MODE_STAND_STILL - cac gia tri khac cung bi coi
    nhu dung yen (khong wander) de tranh hanh vi sai.
    city_key: key trong config.CITIES (vd "trac_quan") - thanh se ve va dung yen.
    Neu khong hop le hoac go_to_town that bai, van tiep tuc treo cay tai vi tri
    hien tai (KHONG return loi) - chi bao qua on_status de nguoi dung biet."""
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

    # go_to_town (train_bot/client.py, copy nguyen tu bot PC) tu xu ly: cho het tran
    # truoc khi teleport, thoat Di Gioi neu dang o do, lap lai toi khi xac nhan da
    # doi map. Day la ham THAT da chay on dinh tren PC, KHONG tu viet lai logic teleport.
    # Neu ve thanh that bai (vd dang ket tran qua lau) -> KHONG dung han, van treo cay
    # tai vi tri hien tai, chi ghi canh bao vao message cua trang thai "running" ben
    # duoi (tranh phat 1 trang thai "error" thoang qua roi bi de ngay, mat thong tin).
    warning = ""
    city_info = config.CITIES.get(city_key)
    if city_info is not None:
        city_id, flag = city_info
        on_status.call("connecting", None, None, None, None, "Dang ve thanh...")
        try:
            ok = c.go_to_town(city_id, flag)
            if not ok and c.running:
                warning = "(Chua ve duoc thanh - co the dang ket tran, van treo cay tai vi tri hien tai)"
        except Exception as e:
            warning = f"(Loi ve thanh: {e} - van treo cay tai vi tri hien tai)"
    else:
        warning = f"(Khong tim thay thanh '{city_key}' - dung yen tai vi tri hien tai)"

    on_status.call("running", None, None, None, None, f"Da vao game, dang treo cay (dung yen) {warning}".strip())

    while c.running and not should_stop.call():
        time.sleep(3)   # 3s giua moi lan cap nhat trang thai UI - du nhanh, khong spam callback
        try:
            ch = c.state.char
            if ch is not None:
                on_status.call("running", ch.hp, ch.sp, ch.hp_max, ch.sp_max, "")
        except Exception as e:
            # vd chua nhan du 0x0b/0x33 -> state chua day du. KHONG de crash ca vong lap
            # (muc tieu: moi loi bao qua callback, khong bao gio nem exception ra ngoai
            # run_train() - BotForegroundService dua vao dieu nay de khong crash Service).
            on_status.call("error", None, None, None, None, f"Loi doc trang thai: {e}")
            break

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
    run_train(username, password, server_ip, server_id, RUN_MODE_STAND_STILL, "trac_quan",
              should_stop, on_status)
    return states[-1] if states else ""
