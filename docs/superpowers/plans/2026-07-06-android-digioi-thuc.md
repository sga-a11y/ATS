# Android: Dị Giới thật (party thật trong game) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nhiều account trong 1 Party Android cùng vào Dị Giới thật trong game, đồng bộ kênh, lập
party thật (leader mời bằng entity, member tự accept), leader chạy lòng vòng tìm quái, member tự
theo/tự đánh, tự reconnect vô hạn khi rớt mạng - VÀ chế độ Dị Giới SOLO (mỗi account chạy độc lập,
không lập party) - khớp 100% `run_party_digioi.py` (PC).

**Architecture:** PC đã giải quyết bài toán "nhiều party chạy song song trong 1 process" bằng dict
module-level khoá theo `pidx` (int). Android's Chaquopy cũng chạy 1 process Python duy nhất cho
toàn app (nhiều thread account của `BotForegroundService`) - **y hệt kiến trúc PC**, chỉ khác
`pidx` (int) → dùng `party.name` (String) làm khoá. Phần lớn máy móc party (`_PARTY_ENTITIES`,
`_PARTY_JOINED`, `invite_members`, `enter_di_gioi_safe`, `pick_best_channel`, `start_run_around`,
auto-accept qua `config.leaders_for(party_idx)`) **ĐÃ ĐƯỢC PORT SẴN** trong
`android/app/src/main/python/train_bot/client.py` từ Task 3 (dùng `self.party_idx` - Python dict
key chấp nhận bất kỳ giá trị hashable nào, kể cả string, KHÔNG cần sửa gì trong `client.py`). Việc
còn thiếu, CHỈ có: (1) `config.leaders_for()` (chưa tồn tại trong bản Android config.py rút gọn),
(2) 1 nơi lưu trạng thái chia sẻ theo Party (mirror `_pstate(pidx)` của `run_party_digioi.py`) vì
Android không có file `PARTY_CONFIG`/`_party_state` toàn cục như PC, (3) 2 hàm chạy vòng lặp mới
trong `train_runner.py` (party thật + solo), (4) dây nối Kotlin (mode mới + is_leader).

**Tech Stack:** Python (Chaquopy, tái dùng nguyên `train_bot/client.py` đã có), Kotlin/Compose cho
UI mode mới - không thêm thư viện.

---

## Nguyên tắc bắt buộc cho MỌI task dưới đây

**KHÔNG diễn giải lại logic PC bằng lời rồi viết code theo trí nhớ.** Mỗi bước có ghi rõ
file+dòng PC cần đọc - LUÔN mở đọc đúng đoạn đó trước khi viết bất kỳ dòng code nào cho bước đó,
copy sát cấu trúc (biến, thứ tự gọi hàm, điều kiện) sang Python, CHỈ đổi kiểu khoá `pidx: int` →
`party_name: str`. Nếu thấy đoạn PC dùng thứ gì không có trong bước, DỪNG lại và báo cáo
(NEEDS_CONTEXT) thay vì tự suy diễn.

---

## File Structure

```
android/app/src/main/python/train_bot/
  party_state.py          # MOI: mirror _pstate(pidx) cua run_party_digioi.py, khoa = party_name (str)
  config.py                # SUA: them DIGIOI_LIMIT + leaders_for(party_name)
  train_runner.py          # SUA: them run_party_digioi() + run_digioi_solo()

android/app/src/main/java/com/tsbot/android/
  BotForegroundService.kt  # SUA: startAccount them run_mode "digioi_party"/"digioi_solo"
  MainActivity.kt          # SUA: dropdown mode them 2 lua chon moi

android/app/src/androidTest/java/com/tsbot/android/
  PartyStateTest.kt        # MOI: test party_state.py (khong can tai khoan that)
  TrainRunnerTest.kt        # SUA: them test dispatch is_leader/leaders_for
```

---

### Task 1: `party_state.py` + `config.leaders_for()`

**Files:**
- Create: `android/app/src/main/python/train_bot/party_state.py`
- Modify: `android/app/src/main/python/train_bot/config.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/PartyStateTest.kt`

- [ ] **Step 1: Đọc đúng `_pstate(pidx)` trong PC (`run_party_digioi.py:134-165`) - đã trích sẵn
  bên dưới, đối chiếu lại file thật trước khi viết (số dòng có thể lệch nếu file đổi):**

```python
def _pstate(pidx):
    if pidx not in _party_state:
        _party_state[pidx] = {"channel": None,
                              "channel_ready": threading.Event(),
                              "invited": threading.Event(),
                              "lock": threading.Lock(),
                              "ready_members": set(),
                              "n_members": 0,
                              "leader_gone": threading.Event(),
                              "reform_gen": 0,
                              "reconnecting": set(),
                              "disc_gen": 0}
    return _party_state[pidx]
```
(Bản Android CHỈ giữ các field thật sự dùng bởi luồng Dị Giới - đã loại bỏ các field chỉ dùng cho
train-map/route/o5-dungeon/bingo không thuộc phạm vi sub-project này: `started_train`,
`dungeon_done`, `dailies_done`, `o5_done_by`, `o5_state`, `leader_ok`, `leader_bad`,
`stop_leader_done`, `route_party_ready`, `route_done`, `map_results`, `member_maps`, `mob_spot`,
`rally_point`, `rally_ready`, `path_done`, `cmd_gen`, `cmd`, `summary_done` - các field này thuộc
mode train/route, KHÔNG dùng trong nhánh `is_digioi`).

- [ ] **Step 2: Viết `party_state.py`**

```python
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
            }
        return _party_state[party_name]


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
```

- [ ] **Step 3: Đọc `bot/config.py:383-389` (đã trích sẵn, đối chiếu lại file thật) - hiểu tại
  sao `client.py` gọi qua `config.leaders_for` (không gọi thẳng `party_state.leaders_for`):**

```python
def leaders_for(pidx):
    out = list(PARTY_LEADERS)
    for nm in PARTY_LEADERS_BY_IDX.get(pidx, []):
        if nm not in out:
            out.append(nm)
    return out
```
`android/app/src/main/python/train_bot/client.py:1156-1157,1225-1226` gọi
`config.leaders_for(self.party_idx) if hasattr(config, "leaders_for") else ...` - vậy CHỈ cần thêm
hàm `leaders_for` vào `config.py` (không cần sửa `client.py`).

- [ ] **Step 4: Thêm vào `train_bot/config.py`** (đọc file trước để chèn đúng chỗ, cuối file sau
  `CITIES = _load_cities()`):

```python
DIGIOI_LIMIT = 120   # so phut Di Gioi/ngay (khop run_party_digioi.py DIGIOI_LIMIT)


def leaders_for(party_name):
    from . import party_state
    return party_state.leaders_for(party_name)
```

- [ ] **Step 5: Viết test xác nhận state chia sẻ đúng giữa "2 thread" giả lập**

```kotlin
package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PartyStateTest {
    @Before
    fun setUp() {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().targetContext))
        }
    }

    @Test
    fun sharedStateKeyedByPartyName() {
        val py = Python.getInstance()
        val ps = py.getModule("train_bot.party_state")
        val st1 = ps.callAttr("_pstate", "party-a")
        val st2 = ps.callAttr("_pstate", "party-a")
        // Cung 1 party_name -> CUNG 1 dict instance (Python object identity qua id())
        assertEquals(st1.callAttr("__class__").toString(), st2.callAttr("__class__").toString())
        val other = ps.callAttr("_pstate", "party-b")
        assertTrue(other != st1)
    }

    @Test
    fun leadersForReturnsRegisteredName() {
        val py = Python.getInstance()
        val ps = py.getModule("train_bot.party_state")
        ps.callAttr("set_leader_name", "party-c", "chibao")
        val config = py.getModule("train_bot.config")
        val leaders = config.callAttr("leaders_for", "party-c")
        assertTrue(leaders.asList().map { it.toString() }.contains("chibao"))
    }
}
```
(Nếu emulator/device đã cắm sẵn từ phiên trước - dùng `adb devices` kiểm tra trước khi chạy.)

- [ ] **Step 6: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.PartyStateTest
```
Xác nhận `failures="0"` qua XML report tại
`android/app/build/outputs/androidTest-results/connected/**/TEST-*.xml`.

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/python/train_bot/party_state.py android/app/src/main/python/train_bot/config.py android/app/src/androidTest/java/com/tsbot/android/PartyStateTest.kt
git commit -m "feat(android): party_state.py + config.leaders_for - mirror _pstate(pidx)/leaders_for(pidx) cua PC, khoa doi tu int sang str"
```

---

### Task 2: `run_party_digioi()` trong `train_runner.py`

**Files:**
- Modify: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Đọc các đoạn PC sau TRƯỚC khi viết (bắt buộc, không viết theo trí nhớ)**

  - `run_party_digioi.py:717-765` (nhánh `is_digioi` lúc setup: pre-check hết giờ, vào DG, nhiệm
    vụ nhẹ, đồng bộ kênh).
  - `run_party_digioi.py:918-934` (leader: `start_run_around()`, chờ member).
  - `run_party_digioi.py:935-951` (member: chờ được mời, đứng yên tại safe).
  - `run_party_digioi.py:1296-1354` (vòng keepalive DG: đếm ngược giờ THEO TỪNG ACCOUNT, phát hiện
    bị đẩy ra khỏi map DG → vào lại).
  - `run_party_digioi.py:1512-1541` (`_run_account_supervised` - vòng bọc reconnect vô hạn).
  - `run_party_digioi.py:1364-1367` (xác định `reconnectable` dựa vào `c.server_closed`).
  - `bot/client.py:3033-3041` (`invite_members`), `bot/client.py:2987-3024` (`pick_best_channel`).

- [ ] **Step 2: Viết `run_party_digioi()` trong `train_bot/train_runner.py`** (thêm sau
  `_auto_claim_loop`, trước `run_train`)

```python
from . import party_state as party_state_mod

DIGIOI_KEEPALIVE_POLL = 3   # giay/vong keepalive (khop nhip 3s cua run_train, PC dung ~2-3s)


def _digioi_login_once(username, password, server_ip, server_id, party_name, is_reconnect):
    """1 lan login + vao world (KHONG bao reconnect - _run_digioi_supervised o duoi lo backoff).
    Tra (client, ok: bool). Mirror run_party_digioi.py:189-234 (vong 6 lan thu login/connect)."""
    c = None
    ok = False
    for attempt in range(6):
        try:
            cred = login_mod.login(username, password)
            c = GameClient(cred["user_id"], cred["access_token"], host=server_ip, server_id=server_id)
            c._label = username
            c.party_idx = party_name   # KHOA CHIA SE STATE - day la diem MAU CHOT: dung party_name (str)
                                        # thay vi pidx (int) nhu PC, moi may moc trong client.py
                                        # (_PARTY_ENTITIES/_PARTY_JOINED/invite_members/...) tu dong hoat
                                        # dong dung vi Python dict chap nhan bat ky khoa hashable nao.
            c.connect()
            for _ in range(15):
                if c.self_entity is not None and c.current_map is not None:
                    ok = True
                    break
                time.sleep(1)
            if ok:
                return c, True
            log.warning("[%s] chua vao world -> login lai...", username)
            c.close()
            time.sleep(5)
        except Exception as e:
            log.warning("[%s] login/connect loi (lan %d): %s", username, attempt + 1, e)
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
            time.sleep(5)
    return c, False


def _run_party_digioi_once(username, password, server_ip, server_id, party_name, is_leader,
                            is_picker, should_stop, on_status, is_reconnect):
    """1 lan chay (khong bao reconnect) - mirror run_account() nhanh is_digioi cua PC, CAT bo cac
    phan khong lien quan DG (train map/city/event/cleanbag, daily quest/dungeon/boss nang - da co
    sub-project #4 lo phan auto-claim). Tra 'reconnectable': bool (server dong dong ket noi khong
    phai do Stop -> nen thu login lai)."""
    st = party_state_mod._pstate(party_name)
    c, ok = _digioi_login_once(username, password, server_ip, server_id, party_name, is_reconnect)
    if not ok:
        on_status.call("error", None, None, None, None, "Login/vao world that bai (6 lan)")
        return False   # login that bai lien tuc -> supervisor van thu lai (giong PC)
    if is_leader:
        party_state_mod.set_leader_name(party_name, c.char_name or username)
    try:
        # 1) Pre-check het gio (mirror run_party_digioi.py:721-724)
        if not c.in_di_gioi() and c.digioi_minutes >= config.DIGIOI_LIMIT:
            on_status.call("stopped", None, None, None, None,
                           f"Da het gio Di Gioi hom nay ({c.digioi_minutes}/{config.DIGIOI_LIMIT} phut)")
            return False
        # 2) Vao DG that su TRUOC khi lam gi khac (mirror run_party_digioi.py:745-756)
        if not c.in_di_gioi() and not c.enter_di_gioi_safe():
            on_status.call("error", None, None, None, None, "Khong vao duoc Di Gioi (het gio?)")
            return False
        on_status.call("running", None, None, None, None, "Da vao Di Gioi")
        # 3) Dong bo kenh (mirror run_party_digioi.py:369-409, ham noi bo do_channel_sync)
        if is_picker:
            st["channel_ready"].clear()
            st["channel"] = None
            need = st["n_members"] + 1
            ch = 0
            t0 = time.time()
            while c.running and not should_stop.call():
                r = c.pick_best_channel(need=need)
                if r is None:
                    time.sleep(3 if time.time() - t0 <= 30 else 60)
                    continue
                ch = r
                break
            st["channel"] = ch
            st["channel_ready"].set()
            on_status.call("running", None, None, None, None,
                           f"Chon kenh {ch} cho ca party" if ch else "Ca party giu nguyen 1 kenh")
        else:
            while not st["channel_ready"].wait(5):
                if not c.running or should_stop.call():
                    return False
            if st["channel"]:
                c.switch_channel(st["channel"])
                on_status.call("running", None, None, None, None, f"Da doi kenh chung -> {st['channel']}")
        # 4) Leader: moi + cho member + chay long vong. Member: cho duoc moi.
        c.flee_mode = False
        if is_leader:
            for _ in range(6):
                if not c.running or should_stop.call():
                    break
                c.invite_members(gap=1.0)
                time.sleep(4)
                if party_state_mod is not None and c.self_entity is not None:
                    from . import client as client_mod
                    if client_mod.joined_member_count(party_name) >= st["n_members"]:
                        break
            try:
                c.set_party_strategist()
            except Exception:
                pass
            c.combat_ready()
            c.start_run_around()
            on_status.call("running", None, None, None, None, "(LEADER) Bat dau chay long vong")
        else:
            on_status.call("running", None, None, None, None,
                           "(member) Cho vao party, dung yen tai safe")
            t0 = time.time()
            while not st["invited"].wait(2):
                if not c.running or should_stop.call() or st["leader_gone"].is_set():
                    return False
        # 5) Vong giu song (mirror run_party_digioi.py:1296-1354, CHI phan DG + het gio per-account)
        out_cnt = 0
        last_dg = 0.0
        while c.running and not should_stop.call():
            time.sleep(DIGIOI_KEEPALIVE_POLL)
            if is_leader and st["leader_gone"].is_set():
                pass   # leader tu no khong tu thoat theo minh
            if (not is_leader) and st["leader_gone"].is_set():
                on_status.call("stopped", None, None, None, None, "Chu party da thoat -> member thoat theo")
                return False
            if c.current_map == config.DIGIOI_MAP_ID and time.time() - last_dg >= 30:
                last_dg = time.time()
                remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                on_status.call("running", None, None, None, None,
                               f"Di Gioi con lai {remain} phut (da o {c.digioi_minutes} phut)")
                if remain <= 0:
                    on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                    return False
                out_cnt = 0
            elif c.current_map is not None and c.current_map != config.DIGIOI_MAP_ID and not c.in_combat():
                out_cnt += 1
                if out_cnt >= 2:
                    remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                    if remain >= 2:
                        on_status.call("running", None, None, None, None,
                                       f"Bi day ra khoi Di Gioi (con {remain} phut) -> vao lai")
                        try:
                            c.enter_di_gioi_safe()
                        except Exception:
                            pass
                        out_cnt = 0
                    else:
                        on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                        return False
            else:
                out_cnt = 0
        return False   # should_stop -> khong can reconnect
    finally:
        reconnectable = (not should_stop.call()) and getattr(c, "server_closed", False)
        try:
            c.close()
        except Exception:
            pass
        if is_leader and not reconnectable:
            st["leader_gone"].set()
        if reconnectable:
            with st["lock"]:
                st["reconnecting"].add(username)
                st["disc_gen"] += 1
        else:
            st["reconnecting"].discard(username)


def run_party_digioi(username, password, server_ip, server_id, party_name, is_leader, is_picker,
                     should_stop, on_status):
    """Vong lap NGOAI CUNG: bao _run_party_digioi_once bang reconnect vo han (mirror
    _run_account_supervised, run_party_digioi.py:1512-1541). server dong ket noi (server_closed)
    va KHONG phai do Stop -> backoff 5s x3 -> 30s x10 -> 60s, thu lai VO HAN toi khi duoc hoac Stop."""
    st = party_state_mod._pstate(party_name)
    st["n_members"] = max(st["n_members"], 0)
    attempt = 0
    is_reconnect = False
    while True:
        reconnectable = _run_party_digioi_once(username, password, server_ip, server_id, party_name,
                                               is_leader, is_picker, should_stop, on_status, is_reconnect)
        if should_stop.call() or not reconnectable:
            break
        attempt += 1
        wait = 5 if attempt <= 3 else (30 if attempt <= 13 else 60)
        on_status.call("connecting", None, None, None, None,
                       f"Server rot -> login lai sau {wait}s (lan {attempt})")
        for _ in range(wait):
            if should_stop.call():
                break
            time.sleep(1)
        if should_stop.call():
            break
        is_reconnect = True
    on_status.call("stopped", None, None, None, None, "Da dung")
```

QUAN TRỌNG - trước khi coi bước này DONE, tự kiểm tra lại 2 điểm sau đối chiếu với code PC đã đọc
ở Step 1 (không được bỏ qua, đây là nơi dễ sai nhất theo kinh nghiệm phiên làm việc trước):
  - `remain <= 0` xử lý HẾT GIỜ là của TỪNG ACCOUNT RIÊNG (không phải party-wide) - account này
    return False (thoát), các thread account khác trong party KHÔNG bị ảnh hưởng.
  - `n_members` cần được set ĐÚNG trước khi gọi `run_party_digioi` cho từng account (xem Task 4,
    Kotlin phải set qua 1 cách nào đó - đề xuất: leader's `run_party_digioi` được gọi với
    `st["n_members"]` set SẴN bởi `BotForegroundService` TRƯỚC khi start bất kỳ thread nào, xem
    Task 4 Step 2).

- [ ] **Step 3: Kiểm tra `joined_member_count` là hàm module-level trong `client.py` (không phải
  method) - xác nhận import đúng**

```bash
grep -n "^def joined_member_count" android/app/src/main/python/train_bot/client.py
```
Expected output: `44:def joined_member_count(party_idx):` (số dòng có thể khác, chỉ cần thấy hàm
tồn tại ở module-level). Sửa lại import trong `_run_party_digioi_once` cho gọn (bỏ import cục bộ
lặp lại mỗi vòng lặp, đưa `from .client import GameClient, joined_member_count` lên đầu file cùng
dòng `from .client import GameClient` đã có sẵn) - xoá dòng
`from . import client as client_mod` + `client_mod.joined_member_count(...)` ở Step 2, thay bằng
gọi thẳng `joined_member_count(party_name)`.

- [ ] **Step 4: Build + kiểm tra cú pháp**

```bash
cd android
python3 -c "import ast; ast.parse(open('app/src/main/python/train_bot/train_runner.py', encoding='utf-8').read())"
```
Expected: không lỗi (không in gì ra).

- [ ] **Step 5: Viết test xác nhận `run_party_digioi` gọi đúng chuỗi hàm khi login thất bại (không
  cần tài khoản thật, mirror `invalidLoginReportsErrorNotCrash` đã có)**

```kotlin
    @Test
    fun digioiInvalidLoginReportsErrorNotCrash() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val states = mutableListOf<String>()
        val shouldStop = KotlinCallableStub { true }
        val onStatus = PyObject.fromJava(object {
            fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                states.add(state)
            }
        })
        mod.callAttr("run_party_digioi", "invalid_user_xyz", "wrong_pw", "127.0.0.1", 1,
            "test-party-digioi", true, true, shouldStop, onStatus)
        assertTrue("Phai bao trang thai loi hoac dung, khong duoc crash", states.contains("error") || states.contains("stopped"))
    }
```
(Kiểm tra `TrainRunnerTest.kt` đã có helper nào tương đương `KotlinCallableStub` chưa - nếu có
class callable stub Kotlin sẵn dùng cho `should_stop`, tái dùng thay vì viết mới; nếu chưa có, thêm
1 class nhỏ:
```kotlin
class KotlinCallableStub(private val fn: () -> Boolean) {
    fun call(): Boolean = fn()
}
```
)

- [ ] **Step 6: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest
```
Xác nhận `failures="0"`. Lưu ý test này gọi login thật (HTTP) với creds sai - sẽ mất vài giây do
retry 6 lần backoff 5s trong `_digioi_login_once`; nếu quá lâu trong CI, đây là hành vi ĐÚNG với
thiết kế (không rút ngắn số lần retry chỉ vì test chậm - đó là an toàn thật cho sản phẩm).

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): run_party_digioi() - port nguyen van nhanh is_digioi + reconnect supervisor tu run_party_digioi.py, khoa pidx->party_name"
```

---

### Task 3: `run_digioi_solo()` trong `train_runner.py`

**Files:**
- Modify: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Đọc đúng đoạn PC sau trước khi viết**

  - `run_party_digioi.py:819-846` (nhánh `digioi_solo`: không lập party, không đồng bộ kênh, kiểm
    tra `has_hp_and_sp_items()` trước khi chạy lòng vòng).
  - `run_party_digioi.py:1302-1311` (trong vòng keepalive DG, phần riêng cho `digioi_solo`: bảo
    hiểm hết thuốc HP/SP giữa chừng thì tự dừng, có lại thuốc thì tự chạy tiếp - KHÔNG cần restart
    bot).

- [ ] **Step 2: Viết `run_digioi_solo()`** (thêm ngay sau `run_party_digioi` trong
  `train_bot/train_runner.py`)

```python
def _run_digioi_solo_once(username, password, server_ip, server_id, should_stop, on_status,
                          is_reconnect):
    """Di Gioi SOLO: KHONG lap party, KHONG dong bo kenh - moi acc doc lap hoan toan (mirror
    run_party_digioi.py:819-846,1302-1311). Tra reconnectable: bool."""
    c, ok = _digioi_login_once(username, password, server_ip, server_id, None, is_reconnect)
    if not ok:
        on_status.call("error", None, None, None, None, "Login/vao world that bai (6 lan)")
        return False
    try:
        if not c.in_di_gioi() and c.digioi_minutes >= config.DIGIOI_LIMIT:
            on_status.call("stopped", None, None, None, None,
                           f"Da het gio Di Gioi hom nay ({c.digioi_minutes}/{config.DIGIOI_LIMIT} phut)")
            return False
        if not c.in_di_gioi() and not c.enter_di_gioi_safe():
            on_status.call("error", None, None, None, None, "Khong vao duoc Di Gioi (het gio?)")
            return False
        c.state.solo_multipet = True
        if c.has_hp_and_sp_items():
            c.flee_mode = False
            c.combat_ready()
            c.start_run_around()
            on_status.call("running", None, None, None, None, "Di Gioi SOLO - dang chay long vong")
        else:
            c.flee_mode = True
            on_status.call("running", None, None, None, None,
                           "Di Gioi SOLO - THIEU thuoc HP/SP, dung yen (khong chay long vong)")
        out_cnt = 0
        last_dg = 0.0
        while c.running and not should_stop.call():
            time.sleep(DIGIOI_KEEPALIVE_POLL)
            if c.current_map == config.DIGIOI_MAP_ID and time.time() - last_dg >= 30:
                last_dg = time.time()
                ok_items = c.has_hp_and_sp_items()
                if ok_items and c.flee_mode:
                    c.flee_mode = False
                    c.combat_ready()
                    c.start_run_around()
                    on_status.call("running", None, None, None, None,
                                   "Di Gioi SOLO: da co du thuoc -> chay tiep")
                elif not ok_items and not c.flee_mode:
                    c.flee_mode = True
                    on_status.call("running", None, None, None, None,
                                   "Di Gioi SOLO: HET thuoc HP/SP -> dung yen")
                remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                if remain <= 0:
                    on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                    return False
                out_cnt = 0
            elif c.current_map is not None and c.current_map != config.DIGIOI_MAP_ID and not c.in_combat():
                out_cnt += 1
                if out_cnt >= 2:
                    remain = max(0, config.DIGIOI_LIMIT - c.digioi_minutes)
                    if remain >= 2:
                        try:
                            c.enter_di_gioi_safe()
                        except Exception:
                            pass
                        out_cnt = 0
                    else:
                        on_status.call("stopped", None, None, None, None, "Het gio Di Gioi that -> thoat")
                        return False
            else:
                out_cnt = 0
        return False
    finally:
        reconnectable = (not should_stop.call()) and getattr(c, "server_closed", False)
        try:
            c.close()
        except Exception:
            pass


def run_digioi_solo(username, password, server_ip, server_id, should_stop, on_status):
    """Vong ngoai reconnect vo han cho Di Gioi SOLO - cung backoff nhu run_party_digioi."""
    attempt = 0
    is_reconnect = False
    while True:
        reconnectable = _run_digioi_solo_once(username, password, server_ip, server_id,
                                              should_stop, on_status, is_reconnect)
        if should_stop.call() or not reconnectable:
            break
        attempt += 1
        wait = 5 if attempt <= 3 else (30 if attempt <= 13 else 60)
        on_status.call("connecting", None, None, None, None,
                       f"Server rot -> login lai sau {wait}s (lan {attempt})")
        for _ in range(wait):
            if should_stop.call():
                break
            time.sleep(1)
        if should_stop.call():
            break
        is_reconnect = True
    on_status.call("stopped", None, None, None, None, "Da dung")
```

- [ ] **Step 3: Build + kiểm tra cú pháp**

```bash
cd android && python3 -c "import ast; ast.parse(open('app/src/main/python/train_bot/train_runner.py', encoding='utf-8').read())"
```
Expected: không lỗi.

- [ ] **Step 4: Viết test tương tự Task 2 Step 5 cho `run_digioi_solo`**

```kotlin
    @Test
    fun digioiSoloInvalidLoginReportsErrorNotCrash() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val states = mutableListOf<String>()
        val shouldStop = KotlinCallableStub { true }
        val onStatus = PyObject.fromJava(object {
            fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                states.add(state)
            }
        })
        mod.callAttr("run_digioi_solo", "invalid_user_xyz2", "wrong_pw", "127.0.0.1", 1, shouldStop, onStatus)
        assertTrue(states.contains("error") || states.contains("stopped"))
    }
```

- [ ] **Step 5: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest
```
Xác nhận `failures="0"`.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): run_digioi_solo() - port nguyen van nhanh digioi_solo tu run_party_digioi.py"
```

---

### Task 4: Dây nối Kotlin (`BotForegroundService.kt`)

**Files:**
- Modify: `android/app/src/main/java/com/tsbot/android/BotForegroundService.kt`

- [ ] **Step 1: Đọc `startAccount` hiện tại (đã dùng `run_train`) để biết đúng vị trí chèn**

Đọc `android/app/src/main/java/com/tsbot/android/BotForegroundService.kt` (đã có ở đầu file cấu
trúc `startAccount(account, serverIp, serverId, runMode, cityKey)` gọi `module.callAttr("run_train",
...)`). Thêm 2 hằng số mode mới ngay dưới khai báo `runningThreads` (hoặc chỗ hợp lý gần đầu class):

```kotlin
    companion object {
        const val RUN_MODE_DIGIOI_PARTY = "digioi_party"
        const val RUN_MODE_DIGIOI_SOLO = "digioi_solo"
    }
```

- [ ] **Step 2: Thêm hàm `startPartyDigioi` (party thật) - gọi 1 lần cho CẢ Party, KHÔNG lặp qua
  từng account như `startAccount` đơn lẻ, vì cần biết `n_members` TRƯỚC khi bất kỳ thread nào bắt
  đầu chạy vòng lặp keepalive**

```kotlin
    /** Khoi dong CA Party o che do Di Gioi THAT (party trong game). Account dau tien = leader
     * (khop PARTY_CONFIG's is_leader tren PC - leader duoc khai bao san theo account, khong doi
     * giua cac lan chay). Goi 1 LAN cho ca Party (khac startAccount tung acc rieng le) vi
     * n_members phai duoc set TRUOC khi bat ky thread nao bat dau vong keepalive. */
    fun startPartyDigioi(party: Party, serverIp: String, serverId: Int) {
        if (party.accounts.isEmpty()) return
        val partyModule = Python.getInstance().getModule("train_bot.party_state")
        val st = partyModule.callAttr("_pstate", party.name)
        st.callAttr("__setitem__", "n_members", party.accounts.size - 1)
        val leader = party.accounts.first()
        party.accounts.forEach { account ->
            val isLeader = account.username == leader.username
            stopFlags[account.username] = false
            val thread = Thread {
                try {
                    val module = Python.getInstance().getModule("train_bot.train_runner")
                    val shouldStop = PyObject.fromJava(object {
                        fun call(): Boolean = stopFlags[account.username] == true
                    })
                    val onStatus = PyObject.fromJava(object {
                        fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                            _status.update {
                                it + (account.username to AccountStatus(
                                    state = RunState.valueOf(state.uppercase()),
                                    hp = hp?.toInt(), sp = sp?.toInt(),
                                    hpMax = hpMax?.toInt(), spMax = spMax?.toInt(), message = msg,
                                ))
                            }
                        }
                    })
                    module.callAttr(
                        "run_party_digioi", account.username, account.password, serverIp, serverId,
                        party.name, isLeader, isLeader, shouldStop, onStatus,
                    )
                } catch (e: Exception) {
                    _status.update {
                        it + (account.username to AccountStatus(RunState.ERROR, message = e.message ?: "loi khong ro"))
                    }
                } finally {
                    runningThreads.remove(account.username)
                    stopFlags.remove(account.username)
                }
            }
            if (runningThreads.putIfAbsent(account.username, thread) == null) thread.start()
        }
    }

    /** Di Gioi SOLO: moi account doc lap hoan toan, khong lap party/dong bo kenh. */
    fun startAccountDigioiSolo(account: Account, serverIp: String, serverId: Int) {
        stopFlags[account.username] = false
        val thread = Thread {
            try {
                val module = Python.getInstance().getModule("train_bot.train_runner")
                val shouldStop = PyObject.fromJava(object {
                    fun call(): Boolean = stopFlags[account.username] == true
                })
                val onStatus = PyObject.fromJava(object {
                    fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                        _status.update {
                            it + (account.username to AccountStatus(
                                state = RunState.valueOf(state.uppercase()),
                                hp = hp?.toInt(), sp = sp?.toInt(),
                                hpMax = hpMax?.toInt(), spMax = spMax?.toInt(), message = msg,
                            ))
                        }
                    }
                })
                module.callAttr("run_digioi_solo", account.username, account.password, serverIp, serverId,
                    shouldStop, onStatus)
            } catch (e: Exception) {
                _status.update {
                    it + (account.username to AccountStatus(RunState.ERROR, message = e.message ?: "loi khong ro"))
                }
            } finally {
                runningThreads.remove(account.username)
                stopFlags.remove(account.username)
            }
        }
        if (runningThreads.putIfAbsent(account.username, thread) == null) thread.start()
    }
```
GHI CHÚ: `st.callAttr("__setitem__", "n_members", ...)` - Chaquopy's `PyObject` cho phép gọi
`__setitem__` để set key trên dict Python trực tiếp từ Kotlin; nếu cách này không hoạt động khi
build thử (kiểm tra ở Step 3), thay thế bằng cách thêm 1 hàm Python nhỏ
`party_state.set_n_members(party_name, n)` (tương tự `set_leader_name`) và gọi hàm đó thay vì thao
tác dict trực tiếp từ Kotlin - AN TOÀN HƠN, ưu tiên cách này nếu không chắc `__setitem__` hoạt
động qua Chaquopy.

- [ ] **Step 3: Build để xác nhận không lỗi biên dịch**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew compileDebugKotlin
```
Expected: `BUILD SUCCESSFUL`. Nếu lỗi liên quan `__setitem__` (xem ghi chú Step 2), quay lại
`party_state.py` (Task 1) thêm hàm `set_n_members(party_name, n)`:
```python
def set_n_members(party_name: str, n: int) -> None:
    _pstate(party_name)["n_members"] = n
```
rồi sửa `BotForegroundService.kt` gọi `partyModule.callAttr("set_n_members", party.name, party.accounts.size - 1)`
thay cho dòng `__setitem__`, build lại tới khi `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/BotForegroundService.kt android/app/src/main/python/train_bot/party_state.py
git commit -m "feat(android): BotForegroundService.startPartyDigioi/startAccountDigioiSolo - goi run_party_digioi/run_digioi_solo"
```

---

### Task 5: UI chọn chế độ Dị Giới (`MainActivity.kt`)

**Files:**
- Modify: `android/app/src/main/java/com/tsbot/android/MainActivity.kt`

- [ ] **Step 1: Đọc UI chọn mode hiện tại (dropdown "Đứng yên tại thành"/"Login ở đâu đứng yên
  đó")** - tìm nơi `RUN_MODE_STAND_STILL`/`RUN_MODE_STAY_LOGIN` được hiển thị làm lựa chọn (trong
  dialog Add/Edit Party hoặc Account - đọc file để xác định chính xác composable nào đang render
  2 lựa chọn hiện có).

- [ ] **Step 2: Thêm 2 lựa chọn mới vào ĐÚNG danh sách đó**

Tại nơi liệt kê các lựa chọn mode (ví dụ 1 `DropdownMenu`/`ExposedDropdownMenuBox` liệt kê
`listOf(RUN_MODE_STAND_STILL to "Đứng yên tại thành", RUN_MODE_STAY_LOGIN to "Login ở đâu đứng yên đó")`
hoặc cấu trúc tương đương đã có), thêm:
```kotlin
BotForegroundService.RUN_MODE_DIGIOI_PARTY to "Dị Giới (party thật)",
BotForegroundService.RUN_MODE_DIGIOI_SOLO to "Dị Giới (solo, không lập party)",
```
vào cùng danh sách, giữ nguyên toàn bộ code render dropdown hiện có (chỉ thêm phần tử vào list).

- [ ] **Step 3: Xử lý dispatch khi bấm Start - tìm nơi `service?.startAccount(...)` được gọi cho
  từng account/party (trong `startAccountIn`/`onStartParty`), thêm rẽ nhánh theo `runMode`**

Tìm hàm `startAccountIn(party, account)` (hoặc tên tương đương đang gọi `service?.startAccount`)
và nơi `onStartParty = { party.accounts.forEach { startAccountIn(party, it) } }`. Sửa để rẽ nhánh:
```kotlin
    private fun startAccountIn(party: Party, account: Account) {
        val runMode = party.runMode ?: RunMode.STAND_STILL   // doc dung field runMode hien co cua Party/Account - kiem tra ten field that trong model truoc khi sua
        when (runMode) {
            BotForegroundService.RUN_MODE_DIGIOI_SOLO ->
                service?.startAccountDigioiSolo(account, party.serverIp, party.serverId)
            else ->
                service?.startAccount(account, party.serverIp, party.serverId, runMode, party.cityKey)
        }
    }

    private fun startPartyDigioiIfNeeded(party: Party): Boolean {
        if (party.runMode == BotForegroundService.RUN_MODE_DIGIOI_PARTY) {
            service?.startPartyDigioi(party, party.serverIp, party.serverId)
            return true
        }
        return false
    }
```
GHI CHÚ QUAN TRỌNG: đoạn code trên dùng tên field giả định (`party.runMode`, `party.serverIp`,
`party.serverId`, `party.cityKey`) - **đọc đúng model `Party`/`Account` thật trong
`android/app/src/main/java/com/tsbot/android/` (file model, có thể `PartyStore.kt` hoặc tương tự)
trước khi viết đoạn này**, sửa tên field cho khớp thực tế thay vì chép nguyên đoạn trên. Ở nơi gọi
`onStartParty`, thêm kiểm tra `startPartyDigioiIfNeeded(party)` TRƯỚC, chỉ lặp qua từng account
bằng `startAccountIn` nếu hàm đó trả `false` (không phải mode party-thật):
```kotlin
onStartParty = {
    if (!startPartyDigioiIfNeeded(party)) {
        party.accounts.forEach { startAccountIn(party, it) }
    }
},
```

- [ ] **Step 4: Build để xác nhận không lỗi biên dịch**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew assembleDebug
```
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 5: Cài lên emulator, kiểm tra UI thủ công**

```bash
adb devices
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.tsbot.android/.MainActivity
```
Tạo 1 Party test có 2 account, mở dropdown chọn mode - xác nhận thấy 2 lựa chọn mới "Dị Giới (party
thật)" và "Dị Giới (solo, không lập party)" (dùng `uiautomator dump` + `grep text=` như các task
trước nếu cần xác nhận qua XML thay vì nhìn màn hình).

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/MainActivity.kt
git commit -m "feat(android): UI chon che do 'Di Gioi (party that)' / 'Di Gioi (solo)' moi Party"
```

---

## Self-Review (đã thực hiện)

**1. Spec coverage:** Party thật (leader mời/member accept/đồng bộ kênh/chạy lòng vòng) - Task 2 ✓.
Solo (không lập party) - Task 3 ✓ (bổ sung theo yêu cầu "làm full hết đi", KHÔNG loại trừ như bản
spec ban đầu). Reconnect vô hạn - Task 2+3 (hàm `run_party_digioi`/`run_digioi_solo` bọc reconnect,
mirror `_run_account_supervised`) ✓. Hết giờ theo TỪNG account (không phải party-wide) - xác nhận
rõ trong code Task 2/3 ✓. UI chọn mode - Task 5 ✓. Nguyên tắc "port nguyên văn, chỉ đổi khoá
pidx->party_name" - áp dụng xuyên suốt, `party_state.py` (Task 1) là module DUY NHẤT có state mới,
mọi nơi khác tái dùng máy móc đã có sẵn trong `client.py`/`config.py`.

**2. Placeholder scan:** Không có "TBD". Task 5 có 2 chỗ ghi rõ "đọc model thật trước khi sửa tên
field" - đây là quyết định kỹ thuật cụ thể cần xác nhận qua đọc code thật (giống các plan trước
trong dự án khi tên field UI chưa chắc chắn tại thời điểm viết plan vì file đã bị session khác sửa
đổi), không phải placeholder che giấu thiếu sót - có code đầy đủ, chỉ cần đổi tên biến cho khớp.

**3. Type consistency:** `run_party_digioi(username, password, server_ip, server_id, party_name,
is_leader, is_picker, should_stop, on_status)` - chữ ký nhất quán giữa Task 2 (định nghĩa) và
Task 4 (gọi từ Kotlin). `run_digioi_solo(username, password, server_ip, server_id, should_stop,
on_status)` - nhất quán Task 3/Task 4. `party_state.leaders_for`/`config.leaders_for` - tên khớp
nhau xuyên suốt Task 1.

## Execution Handoff

Plan hoàn chỉnh, lưu tại `docs/superpowers/plans/2026-07-06-android-digioi-thuc.md`. Hai lựa chọn
thực thi:

1. **Subagent-Driven (khuyến nghị)** - dispatch subagent riêng cho từng Task, review 2 vòng sau
   mỗi task.
2. **Inline Execution** - thực thi tuần tự trong session này, có điểm dừng để anh xem sau mỗi task.

Anh muốn làm theo cách nào?
