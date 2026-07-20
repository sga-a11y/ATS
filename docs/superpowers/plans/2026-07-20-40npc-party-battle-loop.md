# 40 NPC Party Battle Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho party có bot leader tự lập đủ đội và lặp battle 40 NPC tại `(910, 290)`, dừng khi thua và relogin cả party nếu có account rớt giữa trận.

**Architecture:** Tách protocol/state machine 40 NPC vào module nhỏ `bot/npc40.py`; `GameClient` chỉ cấp packet observations và lifecycle worker. Coordinator hiện có quyết định event đứng yên hay event party, đồng thời dùng supervisor để cưỡng bức relogin cả party mà không nhân generation disconnect.

**Tech Stack:** Python 3, threading, pytest, JSON configuration, Chaquopy Python sync cho Android.

## Global Constraints

- Làm trên branch `master` theo yêu cầu người dùng.
- PC và APK phải thay đổi cùng lúc.
- Không build cho tới khi người dùng test bản dev.
- Chỉ `npc_40` dùng flow mới; event không có bot leader giữ nguyên đứng yên.
- Chỉ leader gửi packet NPC và chỉ bắt đầu khi đủ số member cấu hình.

---

### Task 1: Protocol và state machine 40 NPC

**Files:**
- Create: `bot/npc40.py`
- Create: `tests/test_npc40.py`
- Test: `captures/40npc_loop_20260720.pcap`
- Test: `captures/40npc_choose_no_20260720.pcap`

**Interfaces:**
- Produces: `is_repeat_prompt(opcode, packet) -> bool`, `party_defeated(units) -> tuple[bool, int, int]`, `run_loop(client, point, stop_event, on_loss, sleep_fn=time.sleep) -> bool`.
- `client` supplies `running`, `send`, `navigate_to`, `combat_ready`, `_battle_start_seq`, `_npc40_prompt_seq`, and `_npc40_last_defeated`.

- [ ] **Step 1: Write failing packet/policy tests**

Kiểm tra capture có `09001e` cho Có, `09001f` cho Không, prompt `0x41 0a0001`, và `party_defeated` chỉ trả true khi đã thấy unit hợp lệ nhưng tất cả HP bằng 0.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_npc40.py -q`
Expected: FAIL vì `bot.npc40` chưa tồn tại.

- [ ] **Step 3: Implement minimal protocol runner**

Worker gửi đúng chuỗi capture; wait loop có cap, dừng theo generation và gọi `on_loss` sau khi gửi Không.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_npc40.py -q`
Expected: PASS.

### Task 2: GameClient packet observations và worker lifecycle

**Files:**
- Modify: `bot/client.py`
- Modify: `tests/test_npc40.py`

**Interfaces:**
- Produces: `GameClient.start_npc40_loop(point, on_loss) -> bool`, `GameClient.stop_npc40_loop() -> None`.
- Consumes: helpers từ `bot.npc40`.

- [ ] **Step 1: Add failing dispatch/lifecycle tests**

Test `0x34` tăng battle generation, exact `0x41 0a0001` tăng prompt generation và chụp defeat, còn các packet `0x41` khác không kích prompt.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_npc40.py -q`
Expected: FAIL tại counter/method còn thiếu.

- [ ] **Step 3: Implement counters and daemon worker**

Khởi tạo counter/event trong client, observe packet trong `_dispatch`, bảo đảm chỉ có một worker và worker tự thoát khi client ngừng chạy.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_npc40.py -q`
Expected: PASS.

### Task 3: Party coordinator và whole-party relogin

**Files:**
- Modify: `events.json`
- Modify: `run_party_digioi.py`
- Create: `tests/test_npc40_party_policy.py`

**Interfaces:**
- Produces: `_is_npc_repeat_party_event(mode, has_leader, ev) -> bool`, forced-relogin marker keyed by username.
- Consumes: `GameClient.start_npc40_loop` và state party hiện có.

- [ ] **Step 1: Write failing policy/config tests**

Test `npc_40` có point `(910, 290)`, chỉ bật auto party khi có leader, và nhánh no-leader vẫn là event stand.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_npc40_party_policy.py -q`
Expected: FAIL vì config/helper chưa có.

- [ ] **Step 3: Integrate normal party pipeline**

Giữ `go_to_event` cho từng account; bypass nhánh đứng yên chỉ với 40 NPC có leader; leader đợi đủ join, set quân sư và start worker; member combat-ready và đứng theo leader.

- [ ] **Step 4: Integrate disconnect reset**

Khi `disc_gen` tăng trong active loop, đánh dấu survivor forced reconnect rồi đóng phiên. `finally` coi forced reconnect là reconnectable; supervisor không tăng `disc_gen` cho forced close và reset readiness đúng một lần cho disconnect thật.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest tests/test_npc40_party_policy.py tests/test_npc40.py -q`
Expected: PASS.

### Task 4: APK parity, knowledge và verification

**Files:**
- Modify: `KNOWLEDGE.md`
- Modify: `android/app/src/main/python/train_bot/client.py`
- Create: `android/app/src/main/python/train_bot/npc40.py`
- Modify: `android/app/src/main/python/train_bot/run_party_digioi.py`
- Modify: Android `events.json` asset theo cơ chế sync hiện có.

**Interfaces:**
- Consumes: PC implementation đã green.
- Produces: byte-identical Python/config behavior trên APK.

- [ ] **Step 1: Sync APK sources**

Run: `python tools/sync_apk_python.py`
Expected: client/coordinator/module/config Android được cập nhật.

- [ ] **Step 2: Update protocol knowledge**

Ghi hai lựa chọn `09001e`/`09001f`, prompt `0a0001`, close `080029`/`0a0000`, và đường dẫn capture.

- [ ] **Step 3: Run target tests**

Run: `python -m pytest tests/test_npc40.py tests/test_npc40_party_policy.py -q`
Expected: PASS.

- [ ] **Step 4: Run full tests**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Inspect diff without building**

Run: `git status --short` and `git diff --check`
Expected: chỉ source/test/docs/captures liên quan; không có whitespace error; không tạo artifact build.
