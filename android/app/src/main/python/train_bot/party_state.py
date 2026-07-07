"""State chia se GIUA CAC THREAD ACCOUNT trong CUNG 1 Party (Dị Giới thật). Mirror _pstate(pidx)
cua run_party_digioi.py (PC) - CHI doi khoa pidx (int) -> party_name (str), vi Android dat ten
Party bang chuoi thay vi so thu tu. Khong sua doi logic - port nguyen."""
import threading

_party_state = {}
_state_lock = threading.Lock()

# party_name -> ten leader (char_name) DUOC TIN CAY cho party do - dung boi config.leaders_for().
# Mirror config.PARTY_LEADERS_BY_IDX cua PC (o day khong can bang GLOBAL PARTY_LEADERS vi Android
# moi Party doc lap, khong co khai niem "leader chung cho tat ca party" nhu PC).
_leader_names = {}


def _pstate(party_name: str) -> dict:
    with _state_lock:
        if party_name not in _party_state:
            _party_state[party_name] = {
                "channel": None,
                "channel_ready": threading.Event(),
                "invited": threading.Event(),
                "lock": threading.Lock(),
                "ready_members": set(),
                "n_members": 0,
                "leader_gone": threading.Event(),
                "reform_gen": 0,
                "reconnecting": set(),
                "disc_gen": 0,
                "o5_done_by": {},    # username -> da xong o5 (pho ban to doi) hom nay chua? (bool)
                "o5_state": "idle",  # "idle"|"running"|"done" - member PHAI cho != "idle"
                "mob_spot": None,    # diem quai leader chon (share cho member) - mirror PC _pstate
                "rally_point": None, # safe GAN mob_spot nhat -> CA PARTY ve day (gan leader -> member
                                     # bi keo vao tran party). Truoc day member ve nearest-safe-cua-minh
                                     # -> xa mob spot leader -> khong danh (bug leader solo).
                "rally_ready": threading.Event(),  # leader da chon spot + tinh rally_point xong
            }
        return _party_state[party_name]


def set_n_members(party_name: str, n: int) -> None:
    """Set n_members TRUOC khi bat ky thread account nao bat dau vong keepalive - goi tu Kotlin
    (BotForegroundService.startPartyDigioi) 1 LAN cho ca Party truoc khi start tung account-thread."""
    _pstate(party_name)["n_members"] = n


def set_leader_name(party_name: str, char_name: str) -> None:
    """Leader tu dang ky ten nhan vat cua minh cho party_name nay - de member's client (qua
    config.leaders_for) biet loi moi tu ai la DUOC TIN CAY."""
    if not party_name or not char_name:
        return
    _leader_names[party_name] = char_name


def leaders_for(party_name: str) -> list:
    """config.leaders_for(party_idx) trong client.py goi ham nay (qua config, xem Step 4)."""
    name = _leader_names.get(party_name)
    return [name] if name else []


def reset_party_state(party_name: str) -> None:
    """Xoa sach state cua 1 party (vd khi Stop ca party) - de lan Start sau khong dinh du lieu cu."""
    with _state_lock:
        _party_state.pop(party_name, None)
    _leader_names.pop(party_name, None)
