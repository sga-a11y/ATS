# Android: Tự động nhận mail/quà/quân đoàn + nhập giftcode + vận tiêu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Android tự động nhận mail/quà giờ online/quà quân đoàn/vận tiêu giống hệt PC (không có
toggle bật-tắt nào), cộng thêm 1 nút "Nhập giftcode" mỗi Party (áp dụng cho toàn bộ account đang
chạy trong Party đó), khớp đúng hành vi PC.

**Architecture:** Các hàm nghiệp vụ (`claim_mail`, `claim_online_gifts`, `claim_legion_gift`,
`do_van_tieu`, `redeem_giftcode`) đã có sẵn nguyên vẹn trong `train_bot/client.py` (copy từ PC ở
Task 3 của plan trước, chưa từng được gọi). Việc cần làm: (1) thêm dữ liệu `vantieu_requests.json`
+ bật `VANTIEU_ENABLE`, (2) thêm 1 thread phụ trong `train_runner.py` gọi các hàm tự động theo
lịch, (3) mở rộng cơ chế lệnh sống đã có (`pendingCmd`/`getCmd`, dùng cho đổi kênh/teleport thành)
để hỗ trợ thêm loại lệnh `"giftcode"`, (4) thêm nút+dialog UI theo đúng pattern `ChannelDialog`/
`CityDialog` đã có.

**Tech Stack:** Python (Chaquopy) cho logic nghiệp vụ, Kotlin/Compose cho UI - không thêm thư viện
mới, tái dùng nguyên các cơ chế đã có trong Foreground Service Android hiện tại.

---

## Bối cảnh đã xác nhận (đọc trực tiếp code trước khi viết plan)

- `train_bot/client.py` ĐÃ CÓ nguyên vẹn: `claim_mail()` (dòng 1455), `claim_online_gifts()` (dòng
  1501), `redeem_giftcode(code)` (dòng 1618), `claim_legion_gift()` (dòng 1634), `do_van_tieu()`
  (dòng 2497) + toàn bộ state hỗ trợ (`vantieu_slots`, `vantieu_roster`, `vantieu_req_code`,
  `vantieu_unlocked`, `vantieu_max`, `vantieu_started`, `_on_vantieu`, `_on_vantieu_roster`,
  `_match_vantieu_pet`, `_ole_to_dt`).
- `train_bot/config.py` hiện có `VANTIEU_ENABLE = False`, `VANTIEU_PETS = []`,
  `VANTIEU_PETS_NAMES = []`, `VANTIEU_REQUESTS = {}` (dòng 52-55) - cần đổi `VANTIEU_ENABLE = True`
  và nạp `VANTIEU_REQUESTS` thật từ asset (hiện đang rỗng cứng).
- Các hàm này dùng file lưu trạng thái **đường dẫn tương đối** (`_GIFT_FILE = "gift_state.json"`,
  `_DAILY_FILE = "daily_state.json"`, `_VANTIEU_FILE = "vantieu_state.json"` trong `client.py`) -
  dựa vào current-working-directory ghi được. Trên PC luôn ổn (chạy từ thư mục có quyền ghi). Trên
  Android CHƯA từng được xác nhận CWD của tiến trình Chaquopy có ghi được hay không - **Task 2
  Step 1 phải xác nhận việc này bằng test thật trước khi tin tưởng các hàm claim tự động chạy ổn
  định** (nếu ghi lỗi, các hàm này tự bọc try/except nên KHÔNG crash, nhưng sẽ mất tính năng "nhớ
  đã nhận" giữa các lần chạy - claim lại từ đầu mỗi lần mở app, chấp nhận được cho v1 nhưng cần ghi
  nhận rõ nếu xảy ra).
- Cơ chế lệnh sống đã có: `BotForegroundService.pendingCmd` (Kotlin, `ConcurrentHashMap<String,
  Array<Any>>`) + `sendCommand(usernames, cmd)` + `train_runner.py::_apply_cmd(c, cmd, on_status)`
  (dòng 70, switch theo `cmd[0]`: `"channel"`, `"channel_auto"`, `"city"`) - loại lệnh mới
  `"giftcode"` chỉ cần thêm 1 nhánh `elif` vào `_apply_cmd`, không cần sửa cơ chế truyền lệnh.
- UI pattern đã có: `PartyCard` (MainActivity.kt dòng 328) có sẵn nút "Đổi kênh"/"Đổi thành" mở
  `ChannelDialog`/`CityDialog` (state `showChannelDialog`/`showCityDialog` cục bộ trong
  `PartyCard`) - nút giftcode làm y hệt pattern này, thêm 1 dialog nhập text đơn giản.

## File Structure

```
android/app/src/main/assets/train_bot_data/
  vantieu_requests.json          # MOI: copy tu E:\Claude\ATS\vantieu_requests.json

android/app/src/main/python/train_bot/
  config.py                      # SUA: VANTIEU_ENABLE=True, nap VANTIEU_REQUESTS tu asset
  train_runner.py                # SUA: them thread phu (_auto_claim_loop), them nhanh "giftcode"
                                  # trong _apply_cmd

android/app/src/main/java/com/tsbot/android/
  BotForegroundService.kt        # SUA: them sendGiftcode(usernames, code)
  MainActivity.kt                # SUA: PartyCard them nut "Giftcode" + GiftcodeDialog
```

---

### Task 1: Dữ liệu vận tiêu (`vantieu_requests.json` + `config.py`)

**Files:**
- Create: `android/app/src/main/assets/train_bot_data/vantieu_requests.json`
- Modify: `android/app/src/main/python/train_bot/config.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainBotImportTest.kt`

- [ ] **Step 1: Copy file dữ liệu**

```bash
cp "E:\Claude\ATS\vantieu_requests.json" "E:\Claude\ATS\android\app\src\main\assets\train_bot_data\vantieu_requests.json"
```

- [ ] **Step 2: Đọc cấu trúc thật của `vantieu_requests.json` trước khi viết loader**

```bash
python3 -c "
import json
d = json.load(open(r'E:\Claude\ATS\vantieu_requests.json', encoding='utf-8'))
print(list(d.keys())[:5])
print(type(d.get('requests', d)))
"
```
Xác nhận đúng key top-level (có thể là `"requests"` hoặc phẳng trực tiếp - đối chiếu với cách
`config.VANTIEU_REQUESTS.get(self.vantieu_req_code or "")` được dùng trong `client.py::do_van_tieu`
dòng 2544: key là CHUỖI HEX `vantieu_req_code`, value là 1 object mô tả yêu cầu hệ/doanh - đọc
`_match_vantieu_pet` (dòng 2478) để biết chính xác field nào được truy cập trong value, đảm bảo
loader Android giữ đúng cấu trúc dict (không cần convert kiểu như `pets.json`/`skills_data.json`
vì `client.py` đã tự xử lý object value trực tiếp, không cần int hoá key ở tầng config).

- [ ] **Step 3: Sửa `train_bot/config.py`**

Đọc file hiện tại trước khi sửa (dòng 52-55 hiện có `VANTIEU_ENABLE = False` + 3 hằng số rỗng).
Thay bằng:
```python
VANTIEU_ENABLE = True
VANTIEU_PETS = []          # KHONG dung (chi dung che do smart-match qua VANTIEU_REQUESTS)
VANTIEU_PETS_NAMES = []    # KHONG dung (chi dung che do smart-match qua VANTIEU_REQUESTS)


def _load_vantieu_requests():
    """Doc vantieu_requests.json (bang tra ma yeu cau -> pet phu hop, dung cho che do smart-match
    cua do_van_tieu()). Giu NGUYEN cau truc dict tu file (client.py tu xu ly key/value truc tiep,
    khong can convert kieu nhu pets.json)."""
    try:
        d = json.loads(_read_asset("vantieu_requests.json"))
        return d.get("requests", d)   # ho tro ca 2 dang: co wrapper "requests" hoac phang truc tiep
    except Exception as e:
        _log_asset_error("vantieu_requests.json", e)
        return {}


VANTIEU_REQUESTS = _load_vantieu_requests()
```
(Đặt đoạn này SAU định nghĩa `_read_asset`/`_log_asset_error` đã có trong file - nếu thứ tự hàm
trong file khác, di chuyển đoạn `_load_vantieu_requests`/`VANTIEU_REQUESTS` xuống sau các hàm phụ
trợ đó, giữ nguyên các phần khác của file không đổi.)

- [ ] **Step 4: Cập nhật test import để bắt lỗi sớm nếu load hỏng**

Đọc `android/app/src/androidTest/java/com/tsbot/android/TrainBotImportTest.kt` hiện tại, thêm 1
test method mới (giữ nguyên `importAllModulesNoError` đã có):
```kotlin
    @Test
    fun vantieuRequestsLoadsNonEmpty() {
        val py = Python.getInstance()
        val config = py.getModule("train_bot.config")
        val enabled = config.get("VANTIEU_ENABLE")!!.toBoolean()
        assertTrue("VANTIEU_ENABLE phai la True (khop bot/config.py)", enabled)
        val requests = config.get("VANTIEU_REQUESTS")!!
        assertTrue("VANTIEU_REQUESTS phai load duoc du lieu that (khong rong)", requests.callAttr("__len__").toInt() > 0)
    }
```
(Thêm `import org.junit.Assert.assertTrue` vào đầu file nếu chưa có.)

- [ ] **Step 5: Build + chạy test**

```bash
cd android
export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainBotImportTest
```
Kiểm tra XML report tại `android/app/build/outputs/androidTest-results/connected/**/TEST-*.xml` có
`failures="0"` và 2 test (`importAllModulesNoError`, `vantieuRequestsLoadsNonEmpty`) đều pass -
KHÔNG chỉ tin "BUILD SUCCESSFUL" (bài học từ các task trước: sourceSet sai vị trí vẫn báo build
thành công nhưng 0 test chạy).

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/assets/train_bot_data/vantieu_requests.json android/app/src/main/python/train_bot/config.py android/app/src/androidTest/java/com/tsbot/android/TrainBotImportTest.kt
git commit -m "feat(android): them du lieu vantieu_requests.json + bat VANTIEU_ENABLE khop bot/config.py"
```

---

### Task 2: Thread phụ tự động nhận mail/quà/quân đoàn/vận tiêu (`train_runner.py`)

**Files:**
- Modify: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Xác nhận CWD ghi được trên Android TRƯỚC khi viết logic phụ thuộc vào nó**

Đọc `bot/client.py` gốc để xác nhận `_GIFT_FILE`/`_DAILY_FILE`/`_VANTIEU_FILE` là đường dẫn TƯƠNG
ĐỐI (dựa vào CWD). Viết 1 đoạn test nhanh (không cần tài khoản thật) xác nhận CWD của tiến trình
Chaquopy trên Android có ghi được không:
```kotlin
    @Test
    fun cwdIsWritableOnAndroid() {
        val py = Python.getInstance()
        val os = py.getModule("os")
        val cwd = os.callAttr("getcwd").toString()
        val testFile = java.io.File(cwd, "cwd_write_test.tmp")
        testFile.writeText("test")
        assertTrue("CWD ($cwd) phai ghi duoc de claim_mail/claim_online_gifts/do_van_tieu luu trang thai dung", testFile.exists())
        testFile.delete()
    }
```
Thêm test này vào `TrainRunnerTest.kt`. Chạy:
```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest
```
**Nếu test này FAIL** (CWD không ghi được): các hàm `claim_mail`/`claim_online_gifts`/
`claim_legion_gift`/`do_van_tieu` vẫn CHẠY được (tự bọc try/except quanh phần ghi file, chỉ mất
khả năng nhớ trạng thái giữa các lần chạy - claim lại từ đầu mỗi lần mở app). Ghi chú lại kết quả
trong commit message ở Step 5, KHÔNG chặn tiếp tục task này dù test fail (đây là suy giảm tính
năng nhẹ, không phải lỗi chặn).

- [ ] **Step 2: Thêm thread phụ trong `run_train()`**

Đọc `train_bot/train_runner.py` hiện tại (đã có `_apply_cmd`, vòng lặp chính trong `run_train`) để
biết chính xác vị trí chèn. Thêm hàm mới TRƯỚC `run_train`:
```python
def _auto_claim_loop(c, should_stop):
    """Thread phu: tu nhan mail/qua online/qua quan doan/van tieu - GIONG HET PC, KHONG co
    toggle bat-tat (VANTIEU_ENABLE=True co dinh trong config.py, khop bot/config.py). Chay
    doc lap voi vong lap combat chinh, moi loi chi log (khong lam crash run_train)."""
    # Quan doan: chi can goi 1 lan/ngay, ham tu co guard qua daily_state.json - goi som sau login.
    try:
        if not c.in_combat():
            c.claim_legion_gift()
    except Exception as e:
        log.warning("[%s] auto_claim: loi nhan qua quan doan: %s", c._label, e)
    next_vantieu_check = 0.0
    while c.running and not should_stop.call():
        time.sleep(30)   # 30s/vong - du nhanh voi mail/qua online, khong spam server
        if c.in_combat():
            continue   # giua tran de bi server bo qua/loi (giong luu y o _do_manual_cmd ben PC)
        try:
            c.claim_mail()
        except Exception as e:
            log.warning("[%s] auto_claim: loi nhan mail: %s", c._label, e)
        try:
            c.claim_online_gifts()
        except Exception as e:
            log.warning("[%s] auto_claim: loi nhan qua online: %s", c._label, e)
        if time.time() >= next_vantieu_check:
            try:
                nxt = c.do_van_tieu()
                next_vantieu_check = nxt if nxt is not None else time.time() + 1800
            except Exception as e:
                log.warning("[%s] auto_claim: loi van tieu: %s", c._label, e)
                next_vantieu_check = time.time() + 300   # loi -> thu lai sau 5p thay vi spam ngay
```
Cần thêm `import logging` + `log = logging.getLogger("train_runner")` ở đầu file nếu chưa có
(kiểm tra file hiện tại - nếu đã có biến `log` dùng tên khác, dùng lại tên đó cho nhất quán thay vì
tạo logger mới).

- [ ] **Step 3: Khởi động thread phụ trong `run_train()`, ngay sau khi vào game**

Tìm dòng `on_status.call("running", None, None, None, None, f"Da vao game...` trong `run_train()`
(đã có, xem file hiện tại) - thêm NGAY SAU dòng đó:
```python
    import threading
    threading.Thread(target=_auto_claim_loop, args=(c, should_stop), daemon=True).start()
```
(Nếu `threading` chưa import ở đầu file, thêm `import threading` vào phần import đầu file thay vì
import cục bộ trong hàm.)

- [ ] **Step 4: Chạy lại toàn bộ test suite để xác nhận không phá vỡ vòng lặp chính hiện có**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest,com.tsbot.android.TrainBotImportTest
```
Xác nhận qua XML report `failures="0"`, đặc biệt `invalidLoginReportsErrorNotCrash` và
`kotlinCallbackObjectIsCallableFromPython` (test cũ) vẫn pass - thread phụ không được khởi động
trong nhánh login-thất-bại (vì code chèn ở Step 3 nằm SAU đoạn xử lý lỗi login/connect, giữ đúng
vị trí).

- [ ] **Step 5: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): tu dong nhan mail/qua online/qua quan doan/van tieu qua thread phu - giong het PC, khong co toggle bat-tat"
```

---

### Task 3: Lệnh giftcode qua cơ chế lệnh sống (`_apply_cmd`)

**Files:**
- Modify: `android/app/src/main/python/train_bot/train_runner.py`
- Test: `android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt`

- [ ] **Step 1: Thêm nhánh `"giftcode"` vào `_apply_cmd`**

Đọc `_apply_cmd(c, cmd, on_status)` hiện tại (đã có nhánh `"channel"`, `"channel_auto"`, `"city"`).
Thêm nhánh mới:
```python
        elif kind == "giftcode":
            code = str(cmd[1])
            ok = c.redeem_giftcode(code)
            on_status.call("running", None, None, None, None,
                           f"Da nhap giftcode '{code}'" if ok else f"Giftcode '{code}' khong hop le")
```
(Chèn vào đúng vị trí trong chuỗi `if/elif` hiện có của `_apply_cmd`, giữ style try/except bao
ngoài đã có nguyên vẹn.)

- [ ] **Step 2: Viết test xác nhận lệnh giftcode được thực thi đúng qua callback giả lập**

Đọc `TrainRunnerTest.kt` hiện tại để biết đúng cách tạo callback giả lập (`_CallableStub`/
`PyObject.fromJava`) đã dùng cho test khác. Thêm test mới dùng `run_train_sync_for_test`-style
(login thất bại nhanh, không cần tài khoản thật) KHÔNG đủ để test `_apply_cmd` (cần `c` là
`GameClient` thật đã connect). Thay vào đó, viết test Python-only trực tiếp gọi `_apply_cmd` với 1
`GameClient` giả lập tối thiểu:
```kotlin
    @Test
    fun applyGiftcodeCommandCallsRedeemGiftcode() {
        val py = Python.getInstance()
        val mod = py.getModule("train_bot.train_runner")
        val lastMessage = AtomicReference<String>()
        val onStatus = PyObject.fromJava(KotlinStatusCallback(lastMessage) { state, _, _, _, _, msg -> lastMessage.set(msg) })
        // Goi qua module-level helper thay vi tao GameClient that (khong co mang/tai khoan that
        // trong CI) - test nay chi xac nhan _apply_cmd dinh tuyen dung sang redeem_giftcode,
        // KHONG xac nhan ket qua that tu server (can tai khoan that, test thu cong rieng).
        val fakeClientModule = py.getModule("train_bot.train_runner")
        // Dung mock don gian: mot object Python co method redeem_giftcode ghi lai code nhan duoc.
        val testHelper = py.getModule("builtins").callAttr("exec", """
class _FakeClient:
    _label = "test"
    def redeem_giftcode(self, code):
        self.last_code = code
        return True
_fake_client = _FakeClient()
""")
        val fakeClient = py.getModule("__main__").get("_fake_client")
        mod.callAttr("_apply_cmd", fakeClient, arrayOf<Any>("giftcode", "TESTCODE123"), onStatus)
        assertTrue(lastMessage.get().contains("TESTCODE123"))
    }
```
Ghi chú cho kỹ sư thực hiện: nếu cách gọi `exec` qua `builtins` không hoạt động trơn tru với
Chaquopy (khác biệt giữa `__main__` module namespace trên Android so với CPython chuẩn), thay bằng
cách đơn giản hơn: tạo sẵn 1 module test-only nhỏ `train_bot/_test_fake_client.py` (chỉ chứa class
`FakeClient` y hệt trên) và import trực tiếp `py.getModule("train_bot._test_fake_client")` thay vì
exec động - chọn cách nào chạy được thật, xác nhận bằng build+test trước khi coi là xong.

- [ ] **Step 3: Build + chạy test**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.tsbot.android.TrainRunnerTest
```
Xác nhận qua XML report `failures="0"`.

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/python/train_bot/train_runner.py android/app/src/androidTest/java/com/tsbot/android/TrainRunnerTest.kt
git commit -m "feat(android): them lenh 'giftcode' vao co che lenh song (_apply_cmd) - goi redeem_giftcode"
```

---

### Task 4: `BotForegroundService.sendGiftcode`

**Files:**
- Modify: `android/app/src/main/java/com/tsbot/android/BotForegroundService.kt`

- [ ] **Step 1: Thêm hàm `sendGiftcode`**

Đọc `BotForegroundService.kt` hiện tại (đã có `sendChannel`/`sendChannelAuto`/`sendCity` dùng
chung `sendCommand`). Thêm ngay sau `sendCity`:
```kotlin
    fun sendGiftcode(usernames: List<String>, code: String) = sendCommand(usernames, arrayOf<Any>("giftcode", code))
```

- [ ] **Step 2: Build để xác nhận không lỗi biên dịch**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew compileDebugKotlin
```
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/BotForegroundService.kt
git commit -m "feat(android): BotForegroundService.sendGiftcode - gui lenh giftcode qua co che lenh song da co"
```

---

### Task 5: UI nút "Giftcode" trên mỗi Party

**Files:**
- Modify: `android/app/src/main/java/com/tsbot/android/MainActivity.kt`

- [ ] **Step 1: Thêm tham số `onSendGiftcode` vào `PartyCard`**

Đọc `PartyCard` hiện tại (dòng ~328, đã nhận `onSendChannel`/`onSendChannelAuto`/`onSendCity`).
Thêm tham số mới vào danh sách:
```kotlin
    onSendGiftcode: (String) -> Unit,
```
(thêm vào cuối danh sách tham số của `fun PartyCard(...)`, ngay sau `onCurrentChannel`).

- [ ] **Step 2: Thêm state + nút + dialog trong `PartyCard`**

Tìm đoạn code hiện có (trong `PartyCard`, sau `var showCityDialog by remember { ... }`):
```kotlin
            var showChannelDialog by remember { mutableStateOf(false) }
            var showCityDialog by remember { mutableStateOf(false) }
```
Thêm ngay dòng tiếp theo:
```kotlin
            var showGiftcodeDialog by remember { mutableStateOf(false) }
```
Tìm đoạn Row chứa nút "Đổi kênh"/"Đổi thành" (dòng ~432-442):
```kotlin
                Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "Kênh: ${curChannel?.toString() ?: "—"}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.weight(1f))
                    OutlinedButton(onClick = { showChannelDialog = true }) { Text("Đổi kênh") }
                    Spacer(Modifier.width(6.dp))
                    OutlinedButton(onClick = { showCityDialog = true }) { Text("Đổi thành") }
                }
```
Thêm 1 nút giftcode ngay sau nút "Đổi thành" (bên trong cùng `Row` đó, trước dấu `}` đóng Row):
```kotlin
                    Spacer(Modifier.width(6.dp))
                    OutlinedButton(onClick = { showGiftcodeDialog = true }) { Text("Giftcode") }
```
Tìm đoạn code hiện có xử lý `showCityDialog` (dòng ~452-457):
```kotlin
            if (showCityDialog) {
                CityDialog(
                    onDismiss = { showCityDialog = false },
                    onPick = { info -> onSendCity(info.cityId, info.flag); showCityDialog = false },
                )
            }
```
Thêm ngay sau đó:
```kotlin
            if (showGiftcodeDialog) {
                GiftcodeDialog(
                    onDismiss = { showGiftcodeDialog = false },
                    onSave = { code -> onSendGiftcode(code); showGiftcodeDialog = false },
                )
            }
```

- [ ] **Step 3: Viết composable `GiftcodeDialog`**

Thêm vào cuối file (hoặc gần các composable dialog khác như `ChannelDialog`/`CityDialog` để dễ
tìm - đọc file hiện tại để xác định vị trí các composable đó, đặt `GiftcodeDialog` ngay sau
`CityDialog`):
```kotlin
@Composable
fun GiftcodeDialog(
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
) {
    var code by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Nhập giftcode") },
        text = {
            OutlinedTextField(
                value = code,
                onValueChange = { code = it },
                label = { Text("Giftcode") },
                singleLine = true,
            )
        },
        confirmButton = {
            Button(onClick = { if (code.isNotBlank()) onSave(code.trim()) }) {
                Text("Lưu")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Hủy") }
        },
    )
}
```

- [ ] **Step 4: Truyền `onSendGiftcode` từ nơi gọi `PartyCard`**

Tìm chỗ gọi `PartyCard(...)` hiện tại (đã có `onSendChannel`/`onSendChannelAuto`/`onSendCity`/
`onGetChannels`/`onCurrentChannel`) trong `TsBotApp`. Thêm dòng:
```kotlin
                        onSendGiftcode = { code -> service?.sendGiftcode(party.accounts.map { it.username }, code) },
```
(thêm ngay sau dòng `onSendCity = { id, flag -> ... },` đã có, khớp đúng thứ tự tham số vừa thêm ở
Task 5 Step 1 - vị trí trong lời gọi không bắt buộc phải khớp thứ tự khai báo hàm vì Kotlin dùng
named arguments, nhưng đặt gần nhau cho dễ đọc/bảo trì).

- [ ] **Step 5: Build APK + kiểm tra UI thủ công**

```bash
cd android && export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew assembleDebug
```
Expected: `BUILD SUCCESSFUL`. Cài lên máy ảo và xác nhận bằng `uiautomator dump` thấy nút
"Giftcode" xuất hiện cạnh "Đổi kênh"/"Đổi thành" trên 1 Party đã có account:
```bash
ADB="E:\MuMuPlayerGlobal\nx_main\adb.exe"
"$ADB" install -r app/build/outputs/apk/debug/app-debug.apk
"$ADB" shell am start -n com.tsbot.android/.MainActivity
"$ADB" shell uiautomator dump /sdcard/ui.xml && "$ADB" pull /sdcard/ui.xml /tmp/ui.xml
grep -o 'text="Giftcode"' /tmp/ui.xml
```
(dùng `//sdcard/ui.xml` thay vì `/sdcard/ui.xml` nếu chạy qua Git Bash để tránh path-mangling, đã
gặp ở các task trước.)

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/tsbot/android/MainActivity.kt
git commit -m "feat(android): nut 'Giftcode' moi Party - nhap 1 lan, ap dung cho toan bo acc dang chay trong Party do (khop hanh vi PC)"
```

---

## Self-Review (đã thực hiện)

**1. Spec coverage:** Tự động nhận mail/quà/quân đoàn/vận tiêu (Task 1-2) ✓, không có toggle
bật-tắt nào được thêm ✓ (đã kiểm tra kỹ, không có checkbox/switch nào trong plan), nhập giftcode
per-Party (Task 3-5) ✓, dữ liệu `vantieu_requests.json` (Task 1) ✓.

**2. Placeholder scan:** Không có "TBD"/"sau này". Task 3 Step 2 có 1 đoạn hướng dẫn engineer tự
điều chỉnh cách tạo fake client nếu cách viết sẵn không chạy được trên Chaquopy thật - đây KHÔNG
phải placeholder che giấu thiếu sót, mà là quyết định kỹ thuật cụ thể (2 phương án rõ ràng: exec
động hoặc module test-only riêng) cần xác nhận bằng chạy thử thật, giống các task trước đã làm
(vd Task 1 Step 1 của plan Foreground Service trước cũng có tương tự với Chaquopy Pair vs data
class).

**3. Type consistency:** `_apply_cmd(c, cmd, on_status)` giữ nguyên chữ ký đã có, chỉ thêm 1
nhánh `elif`. `sendGiftcode`/`onSendGiftcode` đặt tên nhất quán với `sendCity`/`onSendCity` đã có.
`GiftcodeDialog` theo đúng pattern `AddAccountDialog` (đơn giản hơn `ChannelDialog`/`CityDialog` vì
không cần fetch danh sách, chỉ 1 ô nhập text).

## Execution Handoff

Plan hoàn chỉnh, lưu tại `docs/superpowers/plans/2026-07-04-android-auto-claim-vantieu.md`. Hai
lựa chọn thực thi:

1. **Subagent-Driven (khuyến nghị)** - dispatch subagent riêng cho từng Task, review 2 vòng sau
   mỗi task.
2. **Inline Execution** - thực thi tuần tự trong session này, có điểm dừng để anh xem sau mỗi task.

Anh muốn làm theo cách nào?
