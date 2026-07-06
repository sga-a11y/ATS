# Android: Train mode (di chuyển thông minh theo bản đồ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Party đi theo route đã ghi sẵn từ thành tới map train, tập kết an toàn, leader kéo cả
party ra điểm quái, tự động reform khi có account bị văng khỏi map - VÀ nối "Không có chủ PT"
(`has_leader`) + "Làm nhiệm vụ hàng ngày" (`do_daily`) vào TẤT CẢ 4 hàm chạy hiện có.

**Architecture:** Port nguyên văn nhánh `train_on_map` của `run_party_digioi.py` (PC), tái dùng
100% máy móc đã xây ở sub-project #1 (`party_state.py`, `has_leader`, đồng bộ kênh, invite theo
entity). Đơn giản hoá 1 điểm CÓ CHỦ ĐÍCH so với PC: thay vì PC's cơ chế "tạm dừng + chờ đúng đồng
đội đang reconnect rồi mới reform" (dùng `disc_gen`/`reconnecting` set), Android dùng lại đúng
pattern outer-supervisor-loop đã chứng minh hoạt động ở #1 - mỗi account tự backoff-reconnect độc
lập, và khi vào lại thì tự re-sync kênh/re-join party từ đầu (không cố gắng "chờ đúng lúc" đồng đội
khác). Kết quả tương đương (party rồi cũng tự gom lại), chỉ khác về độ mượt khi nhiều acc rớt cùng
lúc - chấp nhận được, tránh phải port thêm 1 tầng điều phối phức tạp riêng.

**Tech Stack:** Python (Chaquopy, tái dùng `client.py`/`party_state.py` đã có), Kotlin/Compose cho
UI mode mới.

---

## Nguyên tắc bắt buộc cho MỌI task dưới đây

**KHÔNG diễn giải lại logic PC bằng lời rồi viết code theo trí nhớ.** Mỗi bước có ghi rõ file+dòng
PC cần đọc - LUÔN mở đọc đúng đoạn đó trước khi viết code, copy sát cấu trúc, CHỈ đổi khoá
`pidx: int` → `party_name: str`. Nếu thấy đoạn PC dùng thứ gì không có trong bước, DỪNG lại và báo
cáo (NEEDS_CONTEXT) thay vì tự suy diễn.

---

## File Structure

```
android/app/src/main/assets/train_bot_data/
  train_maps.json          # MOI: copy tu E:\Claude\ATS\train_maps.json
  train_routes.json        # MOI: copy tu E:\Claude\ATS\train_routes.json

android/app/src/main/python/train_bot/
  config.py                # SUA: them TRAIN_MAPS/TRAIN_ROUTES loader
  train_runner.py          # SUA: them do_daily param (4 ham cu) + run_party_train() (moi)

android/app/src/main/java/com/tsbot/android/
  RunModes.kt               # SUA: them RunModes.TRAIN
  Party.kt                  # SUA: them trainMapKey/trainMobIndex
  PartyStore.kt             # SUA: luu/doc 2 field moi
  BotForegroundService.kt   # SUA: startPartyTrain() + truyen do_daily vao 4 ham cu
  MainActivity.kt           # SUA: dropdown Map train + Quai khi chon mode Train

android/app/src/androidTest/java/com/tsbot/android/
  TrainRunnerTest.kt         # SUA: them test cho do_daily param + run_party_train dispatch
```

---

### Task 1: Dữ liệu `TRAIN_MAPS`/`TRAIN_ROUTES`

**Files:**
- Create: `android/app/src/main/assets/train_bot_data/train_maps.json`
- Create: `android/app/src/main/assets/train_bot_data/train_routes.json`
- Modify: `android/app/src/main/python/train_bot/config.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainBotImportTest.kt`

- [ ] **Step 1: Copy dữ liệu**

```bash
cp "E:\Claude\ATS\train_maps.json" "E:\Claude\ATS\android\app\src\main\assets\train_bot_data\train_maps.json"
cp "E:\Claude\ATS\train_routes.json" "E:\Claude\ATS\android\app\src\main\assets\train_bot_data\train_routes.json"
```

- [ ] **Step 2: Xác nhận cấu trúc thật (đối chiếu trước khi viết loader)**

```bash
python3 -c "
import json
m = json.load(open(r'E:\Claude\ATS\train_maps.json', encoding='utf-8'))['maps']
r = json.load(open(r'E:\Claude\ATS\train_routes.json', encoding='utf-8'))['routes']
print('maps:', len(m), 'routes:', len(r))
k = list(m.keys())[0]
print('map sample keys:', list(m[k].keys()))
k2 = list(r.keys())[0]
print('route sample keys:', list(r[k2].keys()))
"
```
Expected: `maps: 20 routes: 11`, map sample keys `['name', 'safe', 'mobs']`, route sample keys
`['name', 'from_city', 'city_flag', 'dest_map', 'steps']`.

- [ ] **Step 3: Thêm loader vào `train_bot/config.py`**

Đọc file hiện tại (đã có `_load_cities`/`_load_vantieu_requests` theo pattern `_read_asset`/
`_log_asset_error`). Thêm vào cuối file:
```python
def _load_train_maps():
    """Doc train_maps.json: {map_id(str): {"name", "safe": [[x,y],...], "mobs": [[x,y],...]}}."""
    try:
        d = json.loads(_read_asset("train_maps.json"))
        return d.get("maps", d)
    except Exception as e:
        _log_asset_error("train_maps.json", e)
        return {}


TRAIN_MAPS = _load_train_maps()


def _load_train_routes():
    """Doc train_routes.json: {map_id(str): {"name","from_city","city_flag","dest_map","steps"}}."""
    try:
        d = json.loads(_read_asset("train_routes.json"))
        return d.get("routes", d)
    except Exception as e:
        _log_asset_error("train_routes.json", e)
        return {}


TRAIN_ROUTES = _load_train_routes()
```

- [ ] **Step 4: Thêm test xác nhận load được**

Đọc `TrainBotImportTest.kt` hiện tại (đã có `vantieuRequestsLoadsNonEmpty`), thêm:
```kotlin
    @Test
    fun trainMapsAndRoutesLoadNonEmpty() {
        val py = Python.getInstance()
        val config = py.getModule("train_bot.config")
        val maps = config.get("TRAIN_MAPS")!!
        assertTrue("TRAIN_MAPS phai load duoc du lieu that", maps.callAttr("__len__").toInt() > 0)
        val routes = config.get("TRAIN_ROUTES")!!
        assertTrue("TRAIN_ROUTES phai load duoc du lieu that", routes.callAttr("__len__").toInt() > 0)
    }
```

- [ ] **Step 5: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainBotImportTest
```
Xác nhận qua XML report (`android/app/build/outputs/androidTest-results/connected/**/TEST-*.xml`)
`failures="0"`. Nếu emulator lỗi cài đặt (biết trước: `emulator-5578`/`emulator-5564` có thể hỏng),
target riêng emulator hoạt động qua `ANDROID_SERIAL=emulator-5566 ./gradlew ...`.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/assets/train_bot_data/train_maps.json android/app/src/main/assets/train_bot_data/train_routes.json android/app/src/main/python/train_bot/config.py android/app/src/androidTest/java/com/tsbot/android/TrainBotImportTest.kt
git commit -m "feat(android): them du lieu TRAIN_MAPS/TRAIN_ROUTES (copy nguyen tu PC)"
```

---

### Task 2: Nối `do_daily` vào 4 hàm chạy hiện có

**Files:**
- Modify: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Đọc `run_party_digioi.py:248-265`** (đoạn `if not is_reconnect: ... c.claim_mail() ...`
  và các hàm claim khác) để xác nhận CHÍNH XÁC nơi PC gọi nhiệm vụ hàng ngày trong luồng
  login - đối chiếu, KHÔNG có dòng `claim_daily_quests`/`do_daily_dungeon` TRỰC TIẾP trong đoạn
  này trên PC (nó nằm RẢI RÁC theo từng mode ở các chỗ khác nhau: dòng 314 `c.claim_daily_quests()`
  cho mode khác train/digioi, dòng 442/730/749/1349 `c.claim_daily_quests(heavy=...)`/
  `c.do_daily_dungeon()` theo timing riêng của Dị Giới). Do phạm vi sub-project này đã CẮT các
  nhánh mode khác (train/city/event/cleanbag) khỏi luồng Dị Giới từ sub-project #1, quyết định đơn
  giản hoá: gọi 1 LẦN `claim_daily_quests(heavy=True)` + `do_daily_dungeon()` NGAY SAU khi vào
  world (trước khi vào logic mode-specific), thay vì rải rác theo nhiều thời điểm như PC - đây là
  ĐIỂM ĐƠN GIẢN HOÁ CÓ CHỦ ĐÍCH (khác 1 chút so với PC nhưng đạt cùng mục đích: nhiệm vụ hàng ngày
  được làm 1 lần/phiên), không phải sai sót.

- [ ] **Step 2: Thêm helper dùng chung**

Đọc `train_bot/train_runner.py` hiện tại. Thêm hàm nhỏ (đặt gần đầu file, sau các import):
```python
def _do_daily_if_enabled(c, do_daily, label, on_status):
    """Goi claim_daily_quests(heavy=True) + do_daily_dungeon() 1 LAN neu do_daily=True. Loi chi
    log, khong lam crash vong lap chinh (giong quy uoc _auto_claim_loop)."""
    if not do_daily:
        return
    try:
        c.claim_daily_quests(heavy=True)
    except Exception as e:
        log.warning("[%s] loi claim_daily_quests: %s", label, e)
    try:
        c.do_daily_dungeon()
    except Exception as e:
        log.warning("[%s] loi do_daily_dungeon: %s", label, e)
```

- [ ] **Step 3: Thêm tham số `do_daily` vào `run_train()`**

Đọc chữ ký hiện tại: `run_train(username, password, server_ip, server_id, run_mode, city_key,
should_stop, on_status, get_cmd=None)`. Sửa thành:
```python
def run_train(username: str, password: str, server_ip: str, server_id: int,
              run_mode: str, city_key: str, should_stop, on_status, get_cmd=None,
              do_daily: bool = True):
```
Tìm dòng `c.connect()` trong `run_train` (sau khối `try: c = GameClient(...)`), thêm NGAY SAU khi
connect thành công (trước đoạn xử lý `run_mode == RUN_MODE_STAND_STILL`/xử lý go_to_town):
```python
        _do_daily_if_enabled(c, do_daily, username, on_status)
```

- [ ] **Step 4: Thêm tham số `do_daily` vào `run_party_digioi()`/`_run_party_digioi_once()`**

Sửa chữ ký `_run_party_digioi_once(username, password, server_ip, server_id, party_name, is_leader,
is_picker, has_leader, should_stop, on_status, is_reconnect)` thành thêm `do_daily` vào cuối:
```python
def _run_party_digioi_once(username, password, server_ip, server_id, party_name, is_leader,
                            is_picker, has_leader, do_daily, should_stop, on_status, is_reconnect):
```
Trong thân hàm, ngay sau dòng `on_status.call("running", None, None, None, None, "Da vao Di Gioi")`,
thêm:
```python
        _do_daily_if_enabled(c, do_daily, username, on_status)
```
Sửa `run_party_digioi(username, password, server_ip, server_id, party_name, is_leader, is_picker,
has_leader, should_stop, on_status)` thêm `do_daily` (đặt trước `should_stop` để nhất quán vị trí
với các tham số bool khác):
```python
def run_party_digioi(username, password, server_ip, server_id, party_name, is_leader, is_picker,
                     has_leader, do_daily, should_stop, on_status):
```
Sửa lời gọi nội bộ `_run_party_digioi_once(...)` bên trong `run_party_digioi` để truyền thêm
`do_daily` đúng vị trí.

- [ ] **Step 5: Thêm tham số `do_daily` vào `run_digioi_solo()`/`_run_digioi_solo_once()`**

Tương tự Step 4, thêm `do_daily` vào `_run_digioi_solo_once(username, password, server_ip,
server_id, should_stop, on_status, is_reconnect)` → thêm trước `should_stop`, và
`run_digioi_solo(username, password, server_ip, server_id, should_stop, on_status)` → thêm trước
`should_stop`. Gọi `_do_daily_if_enabled(c, do_daily, username, on_status)` ngay sau
`on_status.call("running", ...)` đầu tiên trong `_run_digioi_solo_once` (sau khi xác nhận đã vào
Dị Giới, trước khi kiểm tra `has_hp_and_sp_items()`).

- [ ] **Step 6: Cập nhật các lời gọi test cũ theo chữ ký mới**

Đọc `TrainRunnerTest.kt` hiện tại - các dòng gọi `mod.callAttr("run_party_digioi", ...)` (đã có từ
sub-project #1, hiện truyền 10 tham số dương: username, password, ip, id, party_name, is_leader,
is_picker, has_leader, shouldStop, onStatus) cần thêm `true` (do_daily mặc định bật) vào ĐÚNG VỊ TRÍ
trước `shouldStop`:
```kotlin
        mod.callAttr("run_party_digioi", "invalid_user_xyz", "wrong_pw", "127.0.0.1", 1,
            "test-party-digioi", true, true, true, true, shouldStop, onStatus)
```
(9 tham số dương trước callback, thêm 1 `true` cho `do_daily`). Tương tự dòng gọi
`run_digioi_solo` (nếu có) thêm `true` trước `shouldStop`. Kiểm tra kỹ bằng cách đọc lại file thật
trước khi sửa - số lượng/thứ tự tham số phải khớp CHÍNH XÁC với Step 4/5 vừa viết.

- [ ] **Step 7: Build + kiểm tra cú pháp, chạy test**

```bash
cd android
python3 -c "import ast; ast.parse(open('app/src/main/python/train_bot/train_runner.py', encoding='utf-8').read())"
export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
ANDROID_SERIAL=emulator-5566 ./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest
```
Xác nhận XML report `failures="0"` (trừ `cwdIsWritableOnAndroid` đã biết là lỗi môi trường cũ,
không liên quan).

- [ ] **Step 8: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): noi do_daily (claim_daily_quests/do_daily_dungeon) vao run_train/run_party_digioi/run_digioi_solo"
```

---

### Task 3: `run_party_train()` (core train mode)

**Files:**
- Modify: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Đọc các đoạn PC sau TRƯỚC khi viết (bắt buộc)**

  - `run_party_digioi.py:301-340` (setup: đúng map+có safe → ra safe; sai map → route sau).
  - `run_party_digioi.py:369-409` (`do_channel_sync` - ĐÃ port ở sub-project #1, tái dùng y hệt,
    không viết lại).
  - `run_party_digioi.py:411-518` (`_do_reform` đầy đủ - giải tán party cũ, về thành, lập lại, kéo
    qua route bằng `move_to`/`_enter_gate`, ra safe, đi ra spot).
  - `run_party_digioi.py:886-925` (`_start_training` - nhánh `train_on_map`: chọn spot, kéo bằng
    `follow_path`/`navigate_to`).
  - `run_party_digioi.py:38-51` (`_jitter`, `_nearest_safe` - hàm phụ trợ thuần, port y nguyên).

- [ ] **Step 2: Thêm 2 hàm phụ trợ (module-level, đặt gần đầu `train_runner.py` cùng các import)**

```python
import random


def _jitter(pt):
    """Xe dich toa do +-10 ngau nhien (9 kha nang) de bot khong dung cung 1 diem."""
    dx, dy = random.choice([-10, 0, 10]), random.choice([-10, 0, 10])
    return (pt[0] + dx, pt[1] + dy)


def _nearest_safe(pos, safes):
    """Diem safe gan vi tri 'pos' nhat (khoang cach binh phuong). pos=None -> diem dau."""
    if not safes:
        return None
    if not pos:
        return safes[0]
    px, py = pos
    return min(safes, key=lambda s: (s[0] - px) ** 2 + (s[1] - py) ** 2)
```

- [ ] **Step 3: Viết `_run_party_train_once()`** (đặt sau `_run_digioi_solo_once`/`run_digioi_solo`,
  trước `run_train`)

```python
def _run_party_train_once(username, password, server_ip, server_id, party_name, map_key,
                          mob_index, is_leader, is_picker, has_leader, do_daily, should_stop,
                          on_status, is_reconnect):
    """1 lan chay (khong bao reconnect) - mirror run_account() nhanh train_on_map cua PC. Don gian
    hoa 1 diem CO CHU DICH so voi PC: KHONG co co che 'tam dung cho dung dong doi dang reconnect'
    (disc_gen/reconnecting) - moi account tu backoff-reconnect doc lap (giong Di Gioi), khi vao lai
    tu re-sync kenh/re-join party tu dau. Tra reconnectable: bool."""
    st = party_state_mod._pstate(party_name)
    tm = config.TRAIN_MAPS.get(map_key)
    route = config.TRAIN_ROUTES.get(map_key)
    if tm is None:
        on_status.call("error", None, None, None, None, f"Khong tim thay map train '{map_key}'")
        return False
    c, ok = _digioi_login_once(username, password, server_ip, server_id, party_name, is_reconnect)
    if not ok:
        on_status.call("error", None, None, None, None, "Login/vao world that bai (6 lan)")
        return False
    if is_leader:
        party_state_mod.set_leader_name(party_name, c.char_name or username)
    _do_daily_if_enabled(c, do_daily, username, on_status)
    try:
        sc = int(map_key)
        safe_list = tm.get("safe") or []
        mobs = tm.get("mobs") or []
        spot = mobs[mob_index] if (mob_index is not None and 0 <= mob_index < len(mobs)) else None
        # 1) Setup: dung map + co safe -> ra safe ngay. Sai map -> can route (xu ly o Step 4 _do_reform).
        if c.current_map == sc and safe_list:
            c.navigate_to(*_nearest_safe(c.pos, safe_list))
        need_route = c.current_map != sc
        # 2) Dong bo kenh (tai dung y het co che tu sub-project #1)
        if is_picker:
            st["channel_ready"].clear()
            st["channel"] = None
            need = st["n_members"] + (1 if has_leader else 0)
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
        else:
            while not st["channel_ready"].wait(5):
                if not c.running or should_stop.call():
                    return False
            if st["channel"]:
                c.switch_channel(st["channel"])
        # 3) Neu sai map (can route) hoac vua sync kenh xong -> dung ham reform chung de dua ca
        # party toi diem quai (mirror PC goi _do_reform(to_spot=False) khi login sai map, roi flow
        # thuong se lap party/di spot; o day gop lam 1 buoc luon cho gon).
        if need_route or not safe_list:
            ok_reform = _reform_to_spot(c, st, party_name, route, spot, is_leader, has_leader,
                                        do_daily, should_stop, on_status, username)
            if not ok_reform:
                return False
        else:
            # Dung map, co safe -> chi can lap party (khong can route) roi di ra spot.
            c.flee_mode = False
            if is_leader:
                for _ in range(6):
                    if not c.running or should_stop.call():
                        break
                    c.invite_members(gap=1.0)
                    st["invited"].set()
                    time.sleep(4)
                    if joined_member_count(party_name) >= st["n_members"]:
                        break
                st["invited"].set()
                try:
                    c.set_party_strategist()
                except Exception:
                    pass
                _abs = lambda: should_stop.call() or not c.running
                if spot:
                    c.navigate_to(*_jitter(spot), flee=False, abort=_abs)
                c.combat_ready()
                c.flee_mode = False
                on_status.call("running", None, None, None, None, "(LEADER) Da ra diem quai, dung cay danh")
            elif has_leader:
                on_status.call("running", None, None, None, None, "(member) Cho vao party")
                while not st["invited"].wait(2):
                    if not c.running or should_stop.call() or st["leader_gone"].is_set():
                        return False
                c.combat_ready()
                c.flee_mode = False
            else:
                on_status.call("running", None, None, None, None,
                               "(member) KHONG co chu PT - dung yen tai safe, cho moi party tay")
        # 4) Vong giu song: phat hien bi vang khoi map train -> reform.
        out_cnt = 0
        while c.running and not should_stop.call():
            time.sleep(DIGIOI_KEEPALIVE_POLL)
            if (not is_leader) and has_leader and st["leader_gone"].is_set():
                on_status.call("stopped", None, None, None, None, "Chu party da thoat -> member thoat theo")
                return False
            if c.current_map == sc:
                out_cnt = 0
            elif not c.in_combat():
                out_cnt += 1
                if out_cnt >= 2:
                    on_status.call("running", None, None, None, None,
                                   "Bi vang khoi map train -> dang reform (dua ca party ve gom lai)")
                    ok_reform = _reform_to_spot(c, st, party_name, route, spot, is_leader, has_leader,
                                                do_daily, should_stop, on_status, username)
                    if not ok_reform:
                        return False
                    out_cnt = 0
        return False
    finally:
        reconnectable = has_leader and (not should_stop.call()) and getattr(c, "server_closed", False)
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


def _reform_to_spot(c, st, party_name, route, spot, is_leader, has_leader, do_daily, should_stop,
                    on_status, label):
    """Dua CA party ve thanh gom nhau -> giai tan + lap lai -> keo qua route (neu co) -> ra safe ->
    ra diem quai. Mirror _do_reform cua PC (run_party_digioi.py:411-518), CAT phan boss quan doan/
    dungeon-tai-thanh (da co _do_daily_if_enabled goi rieng, khong lap lai o day de tranh goi trung
    do_daily nhieu lan moi vong reform). Tra False neu bi should_stop/mat ket noi giua chung."""
    if route is None:
        on_status.call("error", None, None, None, None, "Khong co route cho map nay - khong the reform")
        return False
    fc = int(route.get("from_city", 0))
    ff = int(route.get("city_flag", 0))
    c.flee_mode = True
    if is_leader:
        c.leave_party()
        reset_party_joined(party_name)
    if fc:
        try:
            c.go_to_town(fc, ff)
        except Exception as e:
            log.warning("[%s] reform: loi ve thanh: %s", label, e)
    # Re-sync kenh (khong chi switch ve kenh cu - server co the da day kenh cu day/khac)
    if is_leader:
        st["channel_ready"].clear()
        st["channel"] = None
        need = st["n_members"] + (1 if has_leader else 0)
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
    else:
        while not st["channel_ready"].wait(5):
            if not c.running or should_stop.call():
                return False
        if st["channel"]:
            c.switch_channel(st["channel"])
    if is_leader:
        while joined_member_count(party_name) < st["n_members"]:
            if should_stop.call() or not c.running:
                return False
            try:
                c.invite_members(gap=1.0)
            except Exception:
                pass
            st["invited"].set()
            time.sleep(4)
        st["invited"].set()
        try:
            c.set_party_strategist()
        except Exception:
            pass
        _abs = lambda: should_stop.call() or not c.running
        for stp in route.get("steps", []):
            if _abs():
                return False
            t1 = time.time()
            while c.in_combat(idle_secs=3.0) and not _abs() and time.time() - t1 < 60:
                time.sleep(0.5)
            if "gate" in stp:
                if not c._enter_gate(int(stp["x"]), int(stp["y"]), int(stp["gate"])):
                    break
            else:
                c.move_to(int(stp["move"][0]), int(stp["move"][1]))
                time.sleep(0.5)
        dest_map = int(route.get("dest_map", 0))
        if c.current_map == dest_map and not _abs():
            tm2 = config.TRAIN_MAPS.get(str(dest_map)) or {}
            safe_list = tm2.get("safe") or []
            if safe_list:
                c.navigate_to(*_jitter(_nearest_safe(c.pos, safe_list)), flee=False, abort=_abs)
            if spot:
                c.navigate_to(*_jitter(spot), flee=False, abort=_abs)
        c.combat_ready()
        c.flee_mode = False
    else:
        while not st["invited"].wait(2):
            if not c.running or should_stop.call() or st["leader_gone"].is_set():
                return False
        for _ in range(15):
            if not c.running or should_stop.call():
                break
            time.sleep(1)
        c.combat_ready()
        c.flee_mode = False
    return True


def run_party_train(username, password, server_ip, server_id, party_name, map_key, mob_index,
                    is_leader, is_picker, has_leader, do_daily, should_stop, on_status):
    """Vong lap NGOAI CUNG: bao _run_party_train_once bang reconnect vo han (cung backoff
    5s x3 -> 30s x10 -> 60s nhu run_party_digioi/run_digioi_solo)."""
    st = party_state_mod._pstate(party_name)
    st["n_members"] = max(st["n_members"], 0)
    attempt = 0
    is_reconnect = False
    while True:
        reconnectable = _run_party_train_once(username, password, server_ip, server_id, party_name,
                                              map_key, mob_index, is_leader, is_picker, has_leader,
                                              do_daily, should_stop, on_status, is_reconnect)
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
Cần thêm `from .client import GameClient, joined_member_count, reset_party_joined` (thêm
`reset_party_joined` vào import hiện có `from .client import GameClient, joined_member_count` -
xác nhận `reset_party_joined` là hàm module-level trong `client.py` bằng
`grep -n "^def reset_party_joined" android/app/src/main/python/train_bot/client.py` trước khi
sửa).

- [ ] **Step 4: Build + kiểm tra cú pháp**

```bash
cd android && python3 -c "import ast; ast.parse(open('app/src/main/python/train_bot/train_runner.py', encoding='utf-8').read())"
```
Expected: không lỗi.

- [ ] **Step 5: Viết test dispatch không cần tài khoản thật**

```kotlin
    @Test
    fun trainInvalidLoginReportsErrorNotCrash() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val states = mutableListOf<String>()
        val shouldStop = PyObject.fromJava(KotlinShouldStopCallback())
        val onStatus = PyObject.fromJava(object {
            fun call(state: String, hp: PyObject?, sp: PyObject?, hpMax: PyObject?, spMax: PyObject?, msg: String) {
                states.add(state)
            }
        })
        mod.callAttr("run_party_train", "invalid_user_xyz3", "wrong_pw", "127.0.0.1", 1,
            "test-party-train", "12831", -1, true, true, true, true, shouldStop, onStatus)
        assertTrue(states.contains("error") || states.contains("stopped"))
    }
```
(map_key `"12831"` là map thật có trong dữ liệu - xác nhận lại bằng
`python3 -c "import json; print('12831' in json.load(open(r'train_maps.json', encoding='utf-8'))['maps'])"`
chạy từ thư mục gốc repo trước khi tin tưởng test này chạy đúng nhánh map-tồn-tại.)

- [ ] **Step 6: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
ANDROID_SERIAL=emulator-5566 ./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest
```
Xác nhận XML report `failures="0"` (trừ `cwdIsWritableOnAndroid` đã biết).

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): run_party_train() - port nguyen van nhanh train_on_map + reform tu run_party_digioi.py"
```

---

### Task 4: Dây nối Kotlin (`BotForegroundService.kt`)

**Files:**
- Modify: `android/app/src/main/java/com/tsbot/android/BotForegroundService.kt`

- [ ] **Step 1: Đọc file hiện tại để xác định đúng vị trí sửa `startAccount`/`startPartyDigioi`**
  (đã truyền `has_leader` từ sub-project #1 - giờ cần thêm `do_daily` vào CẢ 2 hàm này, cộng thêm
  hàm mới `startPartyTrain`).

- [ ] **Step 2: Sửa `startAccount` thêm tham số `doDaily: Boolean`**

```kotlin
    fun startAccount(account: Account, serverIp: String, serverId: Int, runMode: String, cityKey: String, doDaily: Boolean) {
```
Trong thân hàm, sửa lời gọi `module.callAttr("run_train", ...)` thêm `doDaily` vào cuối:
```kotlin
                    module.callAttr(
                        "run_train", account.username, account.password, serverIp, serverId,
                        runMode, cityKey, shouldStop, onStatus, getCmd, doDaily,
                    )
```

- [ ] **Step 3: Sửa `startPartyDigioi` thêm `doDaily`**

Đọc thân hàm hiện tại (đã đọc `party.noLeader` → `hasLeader`). Thêm `party.doDaily` vào lời gọi
`run_party_digioi`:
```kotlin
                    module.callAttr(
                        "run_party_digioi", account.username, account.password, serverIp, serverId,
                        party.name, isLeader, isPicker, hasLeader, party.doDaily, shouldStop, onStatus,
                    )
```

- [ ] **Step 4: Thêm hàm `startPartyTrain`** (theo đúng pattern `startPartyDigioi` đã có)

```kotlin
    /** Khoi dong CA Party o che do Train (di chuyen thong minh theo ban do). Giong startPartyDigioi
     * ve cau truc (n_members set truoc, account dau tien = picker, has_leader theo party.noLeader). */
    fun startPartyTrain(party: Party, serverIp: String, serverId: Int, mapKey: String, mobIndex: Int) {
        if (party.accounts.isEmpty()) return
        val partyModule = Python.getInstance().getModule("train_bot.party_state")
        val hasLeader = !party.noLeader
        val nMembers = if (hasLeader) party.accounts.size - 1 else party.accounts.size
        partyModule.callAttr("set_n_members", party.name, nMembers)
        val picker = party.accounts.first()
        party.accounts.forEach { account ->
            val isLeader = hasLeader && account.username == picker.username
            val isPicker = account.username == picker.username
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
                        "run_party_train", account.username, account.password, serverIp, serverId,
                        party.name, mapKey, mobIndex, isLeader, isPicker, hasLeader, party.doDaily,
                        shouldStop, onStatus,
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
```

- [ ] **Step 5: Build để xác nhận không lỗi biên dịch**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew compileDebugKotlin
```
Expected: `BUILD SUCCESSFUL`. Nếu `startAccount` được gọi ở nơi khác trong `MainActivity.kt` chưa
truyền `doDaily` (chữ ký đã đổi ở Step 2), sửa các lời gọi đó truyền `party.doDaily` - lỗi biên
dịch sẽ chỉ thẳng vị trí cần sửa.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/BotForegroundService.kt
git commit -m "feat(android): BotForegroundService.startPartyTrain + truyen do_daily vao startAccount/startPartyDigioi"
```

---

### Task 5: UI chọn map train + dây nối dispatch (`MainActivity.kt`, `Party.kt`, `PartyStore.kt`, `RunModes.kt`)

**Files:**
- Modify: `android/app/src/main/java/com/tsbot/android/RunModes.kt`
- Modify: `android/app/src/main/java/com/tsbot/android/Party.kt`
- Modify: `android/app/src/main/java/com/tsbot/android/PartyStore.kt`
- Modify: `android/app/src/main/java/com/tsbot/android/MainActivity.kt`

- [ ] **Step 1: Thêm `RunModes.TRAIN`**

Đọc `RunModes.kt` hiện tại (đã có `STAND_STILL`/`STAY_LOGIN`/`DIGIOI`). Thêm:
```kotlin
    const val TRAIN = "train"
```
vào object, và thêm `TRAIN to "Train (map bản đồ)"` vào map `ALL`.

- [ ] **Step 2: Thêm field vào `Party.kt`**

Đọc file hiện tại (đã có `digioiSolo`/`noLeader`/`doDaily`). Thêm:
```kotlin
    // Chi dung khi runMode == RunModes.TRAIN: key trong config.TRAIN_MAPS (vd "12831").
    val trainMapKey: String = "",
    // Chi dung khi runMode == RunModes.TRAIN: index trong tm["mobs"] cua map do, -1 = "Bot tu chon"
    // (leader chon ngau nhien moi lan vao/reform). Mirror PC's mob_index (-1 mac dinh).
    val trainMobIndex: Int = -1,
```
(đặt trước `val accounts: List<Account> = emptyList()`).

- [ ] **Step 3: Cập nhật `PartyStore.kt` lưu/đọc 2 field mới**

Đọc file hiện tại (đã có pattern `o.optBoolean("no_leader", false)` v.v). Thêm vào `load()`:
```kotlin
                trainMapKey = o.optString("train_map_key", ""),
                trainMobIndex = o.optInt("train_mob_index", -1),
```
Thêm vào `save()`:
```kotlin
            o.put("train_map_key", p.trainMapKey)
            o.put("train_mob_index", p.trainMobIndex)
```

- [ ] **Step 4: Thêm dropdown "Map train" + "Quái" trong `AddPartyDialog` (`MainActivity.kt`)**

Đọc lại `AddPartyDialog` hiện tại (đã có `digioiSolo`/`noLeader`/`doDaily` state + render). Thêm
tham số:
```kotlin
    initialTrainMapKey: String = "",
    initialTrainMobIndex: Int = -1,
```
và state:
```kotlin
    var trainMapKey by remember { mutableStateOf(initialTrainMapKey.ifEmpty { pyTrainMapKeys().firstOrNull() ?: "" }) }
    var trainMobExpanded by remember { mutableStateOf(false) }
    var trainMobIndex by remember { mutableStateOf(initialTrainMobIndex) }
    var trainMapExpanded by remember { mutableStateOf(false) }
```
Cần 1 hàm helper đọc `TRAIN_MAPS` từ Python để hiển thị tên map trong dropdown - thêm vào
`BotForegroundService.kt` (companion object hoặc top-level function trong `MainActivity.kt`, tuỳ
engineer chọn theo pattern file đã có) hàm:
```kotlin
fun trainMapOptions(): List<Pair<String, String>> {
    val config = com.chaquo.python.Python.getInstance().getModule("train_bot.config")
    val maps = config.get("TRAIN_MAPS")!!
    return maps.asMap().entries.map { (k, v) ->
        k.toString() to (v.callAttr("get", "name")?.toString() ?: k.toString())
    }.sortedBy { it.second }
}

fun trainMobOptions(mapKey: String): List<Pair<Int, String>> {
    val config = com.chaquo.python.Python.getInstance().getModule("train_bot.config")
    val maps = config.get("TRAIN_MAPS")!!
    val info = maps.callAttr("get", mapKey) ?: return listOf(-1 to "Bot tự chọn")
    val mobs = info.callAttr("get", "mobs") ?: return listOf(-1 to "Bot tự chọn")
    val list = mutableListOf(-1 to "Bot tự chọn")
    mobs.asList().forEachIndexed { i, pt ->
        val coords = pt.asList()
        list.add(i to "Điểm ${i + 1} (${coords[0]}, ${coords[1]})")
    }
    return list
}
```
(đặt 2 hàm này ở top-level trong `MainActivity.kt`, gần các hàm helper khác đã có như `RunModes`).
Sửa lại state declaration ở trên dùng `trainMapOptions()` thay vì hàm giả định `pyTrainMapKeys()`:
```kotlin
    var trainMapKey by remember { mutableStateOf(initialTrainMapKey.ifEmpty { trainMapOptions().firstOrNull()?.first ?: "" }) }
```
Thêm render trong khối `if (selectedMode == RunModes.TRAIN) { ... }` (đặt gần khối render
`RunModes.DIGIOI` hiện có, theo đúng pattern `ExposedDropdownMenuBox` đã dùng cho map/thành):
```kotlin
                if (selectedMode == RunModes.TRAIN) {
                    Spacer(Modifier.height(8.dp))
                    val mapOptions = trainMapOptions()
                    ExposedDropdownMenuBox(expanded = trainMapExpanded, onExpandedChange = { trainMapExpanded = it }) {
                        OutlinedTextField(
                            value = mapOptions.find { it.first == trainMapKey }?.second ?: trainMapKey,
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Map train") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = trainMapExpanded) },
                            modifier = Modifier.fillMaxWidth().menuAnchor(),
                        )
                        DropdownMenu(expanded = trainMapExpanded, onDismissRequest = { trainMapExpanded = false }) {
                            mapOptions.forEach { (key, name) ->
                                DropdownMenuItem(text = { Text(name) }, onClick = {
                                    trainMapKey = key; trainMobIndex = -1; trainMapExpanded = false
                                })
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    val mobOptions = trainMobOptions(trainMapKey)
                    ExposedDropdownMenuBox(expanded = trainMobExpanded, onExpandedChange = { trainMobExpanded = it }) {
                        OutlinedTextField(
                            value = mobOptions.find { it.first == trainMobIndex }?.second ?: "Bot tự chọn",
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Quái") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = trainMobExpanded) },
                            modifier = Modifier.fillMaxWidth().menuAnchor(),
                        )
                        DropdownMenu(expanded = trainMobExpanded, onDismissRequest = { trainMobExpanded = false }) {
                            mobOptions.forEach { (idx, label) ->
                                DropdownMenuItem(text = { Text(label) }, onClick = {
                                    trainMobIndex = idx; trainMobExpanded = false
                                })
                            }
                        }
                    }
                }
```
Sửa `onSave` cuối dialog thêm 2 tham số:
```kotlin
                        onSave(Party(name, selectedKey, selectedMode, selectedCity, digioiSolo, noLeader, doDaily, trainMapKey, trainMobIndex))
```
(xác nhận thứ tự tham số positional của `Party(...)` khớp đúng thứ tự khai báo trong `Party.kt`
sau Step 2 - `trainMapKey`/`trainMobIndex` phải đứng SAU `doDaily` và TRƯỚC `accounts`, đọc lại
`Party.kt` để chắc chắn thứ tự).

- [ ] **Step 5: Sửa dispatch `startAccountIn`/`startPartyIn`**

Đọc code hiện tại (đã rẽ nhánh `RunModes.DIGIOI` + `digioiSolo`). Thêm nhánh `RunModes.TRAIN`:
```kotlin
    fun startAccountIn(party: Party, account: Account) {
        val info = Servers.ALL[party.serverKey] ?: return
        when {
            party.runMode == RunModes.DIGIOI && party.digioiSolo ->
                service?.startAccountDigioiSolo(account, info.ip, info.serverId)
            party.runMode == RunModes.DIGIOI ->
                service?.startPartyDigioi(party, info.ip, info.serverId)
            party.runMode == RunModes.TRAIN ->
                // Train luon can party (ke ca party 1 nguoi) vi route/reform gan lien voi co che
                // party - bam Start 1 account rieng le se khoi dong CA Party (giong Di Gioi party).
                service?.startPartyTrain(party, info.ip, info.serverId, party.trainMapKey, party.trainMobIndex)
            else ->
                service?.startAccount(account, info.ip, info.serverId, party.runMode, party.cityKey, party.doDaily)
        }
    }

    fun startPartyIn(party: Party) {
        if (party.runMode == RunModes.DIGIOI && !party.digioiSolo) {
            val info = Servers.ALL[party.serverKey] ?: return
            service?.startPartyDigioi(party, info.ip, info.serverId)
        } else if (party.runMode == RunModes.TRAIN) {
            val info = Servers.ALL[party.serverKey] ?: return
            service?.startPartyTrain(party, info.ip, info.serverId, party.trainMapKey, party.trainMobIndex)
        } else {
            party.accounts.forEach { startAccountIn(party, it) }
        }
    }
```

- [ ] **Step 6: Sửa lời gọi `AddPartyDialog` cho Edit Party truyền thêm 2 tham số mới**

Tìm nơi gọi `AddPartyDialog(title = "Sửa party", ...)` (đã có `initialDigioiSolo`/`initialNoLeader`/
`initialDoDaily`), thêm:
```kotlin
            initialTrainMapKey = partyBeingEdited.trainMapKey,
            initialTrainMobIndex = partyBeingEdited.trainMobIndex,
```

- [ ] **Step 7: Build**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew assembleDebug
```
Expected: `BUILD SUCCESSFUL`. Sửa mọi lỗi biên dịch phát sinh từ thay đổi chữ ký `Party(...)`/
`startAccount(...)` ở các nơi gọi khác chưa được liệt kê ở trên (trình biên dịch sẽ chỉ thẳng).

- [ ] **Step 8: Cài lên emulator, kiểm tra cấu trúc qua grep (theo đúng pattern đã dùng ở giftcode/
  Dị Giới - party rỗng nên không mở được dropdown qua UI thật)**

```bash
adb devices
adb -s emulator-5566 install -r android/app/build/outputs/apk/debug/app-debug.apk
```
Xác nhận qua grep source rằng dropdown Map train dùng đúng `RunModes.ALL`/`trainMapOptions()`:
```bash
grep -n "RunModes.TRAIN\|trainMapOptions\|trainMobOptions" android/app/src/main/java/com/tsbot/android/MainActivity.kt
```

- [ ] **Step 9: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/RunModes.kt android/app/src/main/java/com/tsbot/android/Party.kt android/app/src/main/java/com/tsbot/android/PartyStore.kt android/app/src/main/java/com/tsbot/android/MainActivity.kt
git commit -m "feat(android): UI chon 'Train (map ban do)' - dropdown Map train + Quai, dispatch startPartyTrain"
```

---

## Self-Review (đã thực hiện)

**1. Spec coverage:** Dữ liệu TRAIN_MAPS/TRAIN_ROUTES (Task 1) ✓. `do_daily` nối vào CẢ 4 hàm chạy
(Task 2, run_train/run_party_digioi/run_digioi_solo + Task 3/4 cho run_party_train) ✓. `has_leader`
tái dùng cho train mode (Task 3/4, tham số `has_leader` xuyên suốt) ✓. Route/reform (Task 3) ✓. UI
Map/Quái dropdown (Task 5) ✓. Điểm đơn giản hoá "mỗi account tự reconnect độc lập thay vì PC's
disc_gen coordination" đã nêu rõ trong phần Architecture, không phải thiếu sót ẩn.

**2. Placeholder scan:** Không có "TBD". Task 5 Step 4 có đề cập "tuỳ engineer chọn theo pattern
file đã có" cho vị trí đặt 2 hàm helper - đây là quyết định tổ chức code nhỏ (không phải logic
nghiệp vụ), chấp nhận được.

**3. Type consistency:** `run_party_train(username, password, server_ip, server_id, party_name,
map_key, mob_index, is_leader, is_picker, has_leader, do_daily, should_stop, on_status)` - nhất
quán giữa Task 3 (định nghĩa) và Task 4 (gọi từ Kotlin) và Task 5 test. `Party.trainMapKey`/
`trainMobIndex` - tên field nhất quán giữa Task 5's `Party.kt`/`PartyStore.kt`/`MainActivity.kt`.
`_do_daily_if_enabled(c, do_daily, label, on_status)` - chữ ký dùng nhất quán ở Task 2/3.

## Execution Handoff

Plan hoàn chỉnh, lưu tại `docs/superpowers/plans/2026-07-06-android-train-mode.md`. Hai lựa chọn
thực thi:

1. **Subagent-Driven (khuyến nghị)** - dispatch subagent riêng cho từng Task, review 2 vòng sau
   mỗi task.
2. **Inline Execution** - thực thi tuần tự trong session này, có điểm dừng để anh xem sau mỗi task.

Anh muốn làm theo cách nào?
