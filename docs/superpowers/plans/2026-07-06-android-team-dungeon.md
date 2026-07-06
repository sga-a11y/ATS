# Android: Phó bản tổ đội (team dungeon o5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khi Party bật "Làm nhiệm vụ hàng ngày" và cả party chưa xong phó bản tổ đội (o5) hôm đó,
leader tự tạo phó bản, mời member theo entity, chờ ready thật, đánh 4 trận theo kịch bản đã ghi sẵn.

**Architecture:** `do_team_dungeon_lv20`/`_DUNGEON_READY`/`dungeon_ready_count`/hook `_o5_team_fn`
đã có sẵn nguyên vẹn trong `client.py` (Task 3, chưa từng được gọi) - KHÔNG sửa `client.py`. Chỉ
port `_handle_o5_team` (hàm điều phối tầng `train_runner.py`) từ `run_party_digioi.py:1405-1510`,
mirror y hệt, chỉ đổi khoá `pidx`→`party_name`, và set hook `c._o5_team_fn` trong
`_do_daily_if_enabled` (đã có từ sub-project #2) TRƯỚC khi gọi `claim_daily_quests`.

**Tech Stack:** Python (Chaquopy, tái dùng `client.py`/`party_state.py` đã có).

---

## Nguyên tắc bắt buộc

**KHÔNG diễn giải lại logic PC bằng lời rồi viết code theo trí nhớ.** Đọc đúng
`run_party_digioi.py:1405-1510` TRƯỚC khi viết, copy sát cấu trúc, CHỈ đổi khoá `pidx: int` →
`party_name: str`. Nếu thấy đoạn PC dùng thứ gì không có trong bước, DỪNG lại và báo cáo
(NEEDS_CONTEXT) thay vì tự suy diễn.

---

## File Structure

```
android/app/src/main/python/train_bot/
  party_state.py     # SUA: them field o5_done_by/o5_state vao _pstate()
  train_runner.py     # SUA: them _handle_o5_team() + set hook trong _do_daily_if_enabled()
```

---

### Task 1: Thêm field `o5_done_by`/`o5_state` vào `party_state.py`

**Files:**
- Modify: `android/app/src/main/python/train_bot/party_state.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/PartyStateTest.kt`

- [ ] **Step 1: Đọc `run_party_digioi.py:134-165` (`_pstate`) để xác nhận 2 field PC có
  (`o5_done_by = {}`, `o5_state = "idle"`) trước khi thêm - đối chiếu với bản Android hiện tại
  (`android/app/src/main/python/train_bot/party_state.py`, đã trim field không dùng cho Dị
  Giới/train, cần thêm lại 2 field này cho phó bản tổ đội).**

- [ ] **Step 2: Sửa `_pstate()` trong `party_state.py`**

Đọc file hiện tại (dict trả về hiện có `channel`/`channel_ready`/`invited`/`lock`/`ready_members`/
`n_members`/`leader_gone`/`reform_gen`/`reconnecting`/`disc_gen`). Thêm 2 key:
```python
                "o5_done_by": {},    # username -> da xong o5 (pho ban to doi) hom nay chua? (bool)
                "o5_state": "idle",  # "idle"|"running"|"done" - member PHAI cho != "idle"
```
(chèn vào cuối dict literal trong `_pstate()`, trước dấu `}` đóng).

- [ ] **Step 3: Test xác nhận field mới tồn tại**

Đọc `PartyStateTest.kt` hiện tại (đã có `sharedStateKeyedByPartyName`/`leadersForReturnsRegisteredName`).
Thêm:
```kotlin
    @Test
    fun pstateHasO5Fields() {
        val py = Python.getInstance()
        val ps = py.getModule("train_bot.party_state")
        val st = ps.callAttr("_pstate", "party-o5-test")
        val o5State = st.callAttr("get", "o5_state").toString()
        assertEquals("idle", o5State)
        val o5DoneBy = st.callAttr("get", "o5_done_by")
        assertTrue("o5_done_by phai la dict rong luc khoi tao", o5DoneBy.callAttr("__len__").toInt() == 0)
    }
```
(thêm `import org.junit.Assert.assertEquals` nếu chưa có trong file).

- [ ] **Step 4: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
ANDROID_SERIAL=emulator-5566 ./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.PartyStateTest
```
Xác nhận qua XML report `failures="0"` (kiểm tra `adb devices` trước, dùng emulator đang hoạt động
- biết trước `emulator-5578`/`emulator-5564` có thể hỏng, không liên quan code này).

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/python/train_bot/party_state.py android/app/src/androidTest/java/com/tsbot/android/PartyStateTest.kt
git commit -m "feat(android): them field o5_done_by/o5_state vao party_state - can cho pho ban to doi"
```

---

### Task 2: `_handle_o5_team()` + set hook trong `_do_daily_if_enabled`

**Files:**
- Modify: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Đọc `run_party_digioi.py:1405-1510` (`_handle_o5_team`) TRƯỚC khi viết - đây là
  đoạn PHỨC TẠP, đọc kỹ toàn bộ, không bỏ sót nhánh nào (member-chờ, leader-chờ-report, leader-đánh,
  xử lý đồng đội rớt giữa chừng qua `relogin()`, bump `reform_gen`).**

- [ ] **Step 2: Đọc `_do_daily_if_enabled()` hiện tại trong `train_runner.py`** (dòng ~51-63,
  hiện chỉ nhận `(c, do_daily, label, on_status)`, gọi `claim_daily_quests(heavy=True)` +
  `do_daily_dungeon()`). Sửa chữ ký thêm 3 tham số tuỳ chọn (mặc định `None`/`False` để 2 lời gọi từ
  `run_train`/`_run_digioi_solo_once` - không có party thật - không cần đổi gì):

```python
def _do_daily_if_enabled(c, do_daily, label, on_status, party_name=None, is_leader=False,
                         should_stop=None):
    """Goi claim_daily_quests(heavy=True) + do_daily_dungeon() 1 LAN neu do_daily=True. Loi chi
    log, khong lam crash vong lap chinh (giong quy uoc _auto_claim_loop). Neu party_name duoc
    truyen (tuc dang chay trong 1 party THAT - Di Gioi/Train) -> set hook _o5_team_fn TRUOC khi
    goi claim_daily_quests, de _on_dungeon (client.py) goi lai _handle_o5_team lam BUOC CUOI cua
    claim_daily_quests (mirror PC's c._o5_team_fn set luc setup account)."""
    if not do_daily:
        return
    if party_name is not None and should_stop is not None:
        c._o5_team_fn = (lambda o5d: _handle_o5_team(c, party_name, label, is_leader, should_stop, o5d))
    try:
        c.claim_daily_quests(heavy=True)
    except Exception as e:
        log.warning("[%s] loi claim_daily_quests: %s", label, e)
    try:
        c.do_daily_dungeon()
    except Exception as e:
        log.warning("[%s] loi do_daily_dungeon: %s", label, e)
```

- [ ] **Step 3: Viết `_handle_o5_team()`** (đặt sau `_do_daily_if_enabled`, trước
  `RUN_MODE_STAND_STILL`)

```python
def _handle_o5_team(c, party_name, label, is_leader, should_stop, o5_done):
    """O5 PHO BAN TO DOI = BUOC CUOI claim_daily_quests (sau khi check + thu lam moi o khac). Mirror
    run_party_digioi.py:1405-1510 nguyen van, CHI doi khoa pidx -> party_name. Moi acc report o5 da
    xong chua. LEADER cho CA party report -> CHI khi MOI nguoi deu CHUA xong o5 -> tao + keo party
    vao danh (member auto-accept 0x2f 0f->03 + ready 0x2f 0b trong _on_dungeon, di theo leader).
    MEMBER PHAI CHO leader danh xong (o5_state != "idle" roi thanh "done") MOI duoc return - tiep
    tuc flow rieng. KHONG cho -> member tu chay tiep SONG SONG luc dang trong pho ban -> gui goi xen
    vao giua tran -> server khong nhan atk hop le -> ket cung (xac nhan qua log PC thuc te)."""
    st = party_state_mod._pstate(party_name)
    with st["lock"]:
        st["o5_done_by"][label] = bool(o5_done)
    has_leader = party_state_mod.leaders_for(party_name) != [] or is_leader
    if not is_leader and not has_leader:
        # Party KHONG CO LEADER BOT (vd "Khong co chu PT") -> KHONG AI se chay nhanh leader ben duoi
        # de set o5_state="done" -> cho vo ich toi khi timeout. Khong co leader thi khong co gi de
        # cho -> bo qua NGAY (mirror PC).
        return
    if not is_leader:
        _t0log = time.time()
        while True:
            if should_stop.call() or not c.running:
                return
            if time.time() - _t0log > 60:
                log.info("[%s] (member) CHO leader danh xong team dungeon...", label)
                _t0log = time.time()
            if st["reconnecting"]:
                log.warning("[%s] (member) dong doi ROT trong team dungeon -> RELOGIN thoat instance", label)
                try:
                    c.relogin()
                except Exception:
                    pass
                return
            with st["lock"]:
                state = st["o5_state"]
            if state == "done":
                return
            if not c.in_combat():
                try:
                    c.do_heal()
                except Exception:
                    pass
            time.sleep(2)
    # LEADER: cho CA party (gom minh) report o5. n_members KHONG tinh minh (leader) - + 1 cho tong so.
    total_members = st["n_members"] + 1
    if total_members < 2:
        return   # khong du party de danh pho ban to doi
    _t0log = time.time()
    while True:
        if should_stop.call() or not c.running:
            return
        with st["lock"]:
            reported = len(st["o5_done_by"]) + len(st["reconnecting"]) >= total_members
        if reported:
            break
        if time.time() - _t0log > 30:
            log.info("[%s] (LEADER) CHO ca party report o5 (%d/%d)...",
                     label, len(st["o5_done_by"]), total_members)
            _t0log = time.time()
        time.sleep(2)
    with st["lock"]:
        statuses = dict(st["o5_done_by"])
    if all(not v for v in statuses.values()):
        log.info("[%s] (LEADER) CA party (%d nguoi) chua xong o5 -> PHO BAN TO DOI LV20",
                 label, total_members)
        with st["lock"]:
            st["o5_state"] = "running"
        _dg0 = st["disc_gen"]
        try:
            ok = c.do_team_dungeon_lv20()
            if ok:
                c.claim_daily_quests(heavy=False)
            if st["disc_gen"] > _dg0 or st["reconnecting"]:
                log.warning("[%s] (LEADER) dong doi ROT trong team dungeon -> RELOGIN thoat instance", label)
                try:
                    c.relogin()
                except Exception:
                    pass
        finally:
            with st["lock"]:
                st["o5_state"] = "done"
                st["reform_gen"] += 1
    else:
        with st["lock"]:
            st["o5_state"] = "done"
        log.info("[%s] (LEADER) o5: KHONG phai ca party chua xong -> bo qua pho ban to doi", label)
```

GHI CHÚ QUAN TRỌNG khác PC 1 điểm nhỏ (đã cân nhắc, ghi rõ để không bị coi là lỗi): PC dùng
`party_accounts(pidx)` (đọc từ `PARTY_CONFIG` toàn cục) để biết chính xác danh sách username thành
viên rồi so khớp `all(m in st["o5_done_by"] ... for m in members)`. Android không có cấu trúc
tương đương thuận tiện ở tầng `train_runner.py` (party info nằm bên Kotlin) - dùng ĐẾM SỐ LƯỢNG
(`len(st["o5_done_by"]) + len(st["reconnecting"]) >= total_members`) thay vì so khớp CHÍNH XÁC
từng username. Về mặt chức năng tương đương (mỗi account chỉ tự ghi đúng 1 lần cho chính nó), chỉ
khác cách kiểm tra "đã đủ chưa".

- [ ] **Step 4: Gọi `_do_daily_if_enabled` với tham số mới ở 2 nơi cần party (Dị Giới + Train)**

Trong `_run_party_digioi_once` (đã có dòng gọi `_do_daily_if_enabled(c, do_daily, username,
on_status)` ngay sau `"Da vao Di Gioi"`), sửa thành:
```python
        _do_daily_if_enabled(c, do_daily, username, on_status, party_name, is_leader, should_stop)
```
Trong `_run_party_train_once` (đã có dòng gọi tương tự ngay sau `_digioi_login_once`/
`set_leader_name`), sửa thành:
```python
    _do_daily_if_enabled(c, do_daily, username, on_status, party_name, is_leader, should_stop)
```
(đọc lại 2 vị trí gọi hiện tại trong file thật trước khi sửa, đảm bảo đúng dòng - KHÔNG sửa lời
gọi trong `run_train`/`_run_digioi_solo_once`, giữ nguyên 4 tham số cũ vì không có party thật).

- [ ] **Step 5: Build + kiểm tra cú pháp**

```bash
cd android && python3 -c "import ast; ast.parse(open('app/src/main/python/train_bot/train_runner.py', encoding='utf-8').read())"
```
Expected: không lỗi.

- [ ] **Step 6: Viết test xác nhận `_handle_o5_team` không crash khi gọi trực tiếp (không cần
  tài khoản thật) - dùng `_FakeClientForTest` đã có từ sub-project #4**

Đọc `train_runner.py` hiện tại để xem `_FakeClientForTest`/`apply_giftcode_cmd_for_test` (đã có,
gần cuối file) - thêm 1 hàm test-only tương tự:
```python
def handle_o5_team_member_returns_when_done_for_test(party_name: str) -> bool:
    """CHI DUNG TRONG TEST: goi _handle_o5_team voi is_leader=False, xac nhan return ngay khi
    o5_state da la 'done' tu truoc (khong bi treo cho vo han)."""
    party_state_mod._pstate(party_name)["o5_state"] = "done"
    fake = _FakeClientForTest()
    fake.running = True
    should_stop = _CallableStub(lambda: False)
    _handle_o5_team(fake, party_name, "test-member", False, should_stop, False)
    return True   # khong treo -> ham tra ve duoc toi day
```
Cần thêm `self.running = True` vào `_FakeClientForTest.__init__` nếu chưa có thuộc tính này (đọc
class hiện tại trước khi sửa - class này dùng chung cho các test khác, KHÔNG phá vỡ test đã có).

Thêm Kotlin test vào `TrainRunnerTest.kt`:
```kotlin
    @Test
    fun handleO5TeamMemberReturnsWhenAlreadyDone() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val result = mod.callAttr("handle_o5_team_member_returns_when_done_for_test", "party-o5-member-test")
        assertTrue(result.toBoolean())
    }
```

- [ ] **Step 7: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
ANDROID_SERIAL=emulator-5566 ./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest
```
Xác nhận XML report `failures="0"` (trừ `cwdIsWritableOnAndroid` đã biết là lỗi môi trường cũ,
không liên quan).

- [ ] **Step 8: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): _handle_o5_team() - port nguyen van tu run_party_digioi.py, set hook trong _do_daily_if_enabled cho Di Gioi/Train"
```

---

## Self-Review (đã thực hiện)

**1. Spec coverage:** Field `o5_done_by`/`o5_state` (Task 1) ✓. `_handle_o5_team` port nguyên văn
(Task 2) ✓. Set hook `_o5_team_fn` trong `_do_daily_if_enabled`, CHỈ áp dụng cho Dị Giới/Train (có
party thật), KHÔNG áp dụng cho `run_train`/solo (Task 2 Step 4) ✓. Không thêm UI/toggle riêng -
tự động kèm "Làm nhiệm vụ hàng ngày" đã có ✓.

**2. Placeholder scan:** Không có "TBD". Ghi chú ở Task 2 Step 3 về khác biệt nhỏ so với PC (đếm số
lượng thay vì so khớp username) là quyết định kỹ thuật CÓ GIẢI THÍCH rõ, không phải placeholder.

**3. Type consistency:** `_handle_o5_team(c, party_name, label, is_leader, should_stop, o5_done)` -
nhất quán giữa định nghĩa (Task 2 Step 3) và lời gọi qua hook lambda (Task 2 Step 2) và test (Task 2
Step 6). `_do_daily_if_enabled(c, do_daily, label, on_status, party_name=None, is_leader=False,
should_stop=None)` - tham số mới có default nên KHÔNG phá vỡ 2 lời gọi cũ (`run_train`/
`_run_digioi_solo_once`) không cần sửa.

## Execution Handoff

Plan hoàn chỉnh, lưu tại `docs/superpowers/plans/2026-07-06-android-team-dungeon.md`. Hai lựa chọn
thực thi:

1. **Subagent-Driven (khuyến nghị)** - dispatch subagent riêng cho từng Task, review sau mỗi task.
2. **Inline Execution** - thực thi tuần tự trong session này.

Anh muốn làm theo cách nào?
