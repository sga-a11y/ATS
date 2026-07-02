# Android Foreground Service Foundation (đa tài khoản, mode Train) — Thiết kế

> Sub-project tiếp theo sau "Android Phase 1 Foundation" (`docs/superpowers/plans/2026-07-02-android-app-phase1-foundation.md`, đã hoàn thành: Gradle+Chaquopy+NDK scaffold, protocol-native C++/JNI, smoke-test login username/password/server hoạt động thật trên thiết bị).

## Mục tiêu

Cho phép app Android chạy **nhiều tài khoản cùng lúc** ở **mode Train** (chỉ Train — Dị Giới và Phó bản tổ đội để lại cho sub-project sau), điều khiển qua UI Compose (form nhập, chưa có bubble nổi — bubble là sub-project riêng sau đây). Đây là lớp "lõi chạy bot nền", các UI (bubble, control panel) sau này chỉ là lớp vỏ gọi vào lớp lõi này.

## Không làm trong sub-project này

- Bubble UI nổi (chat-head) — sub-project riêng, làm sau khi Service chạy ổn.
- Mode Dị Giới (Party/Solo) và Phó bản tổ đội (ô 5) — để lại cho sub-project riêng, tái dùng khung Service này.
- Import cấu hình từ file PC — người dùng nhập trực tiếp trên Android.
- PyArmor/R8 obfuscation, anti-debug/root check (đã liệt kê trong spec thiết kế tổng Android, làm ở giai đoạn hoàn thiện sản phẩm).

## Kiến trúc

```
MainActivity (Compose UI)
   │  bind
   ▼
BotForegroundService (Kotlin, android.app.Service)
   │  1 lần: Python.start(AndroidPlatform)
   │
   ├─ Thread "acc-<username>" → gọi bot_client.run_account(...)  (Python, port từ bot/client.py)
   ├─ Thread "acc-<username2>" → ...
   └─ StateFlow<Map<username, AccountStatus>> — UI/bubble sau này bind vào đây
```

- **1 ForegroundService duy nhất**, khởi động Chaquopy Python interpreter **1 lần** (`Python.start()` là singleton, gọi nhiều lần vô nghĩa/lỗi).
- **Mỗi account chạy 1 Kotlin thread riêng**, thread đó gọi 1 hàm Python `run_account(username, password, server_key, on_status_update)` — hàm này port từ vòng lặp chính của `bot/client.py`/`run_party_digioi.py` (chỉ phần Train, bỏ nhánh Dị Giới/ô5/party-sync).
- **Không multi-process** — theo quyết định đã chốt, đơn giản hơn, tài nguyên điện thoại đủ dùng cho một vài account train song song.
- Mỗi thread Python tự mở socket TCP riêng (qua `bot_native_bridge.encode_frame`/`decode_stream` đã có sẵn từ Phase 1) tới server đã chọn, độc lập hoàn toàn với các thread khác (không chia sẻ state, không cần đồng bộ giữa các acc vì mode Train không có phối hợp party).

### Giao tiếp Service ↔ UI

- Service expose `val accountStatus: StateFlow<Map<String, AccountStatus>>` (bound service, `MainActivity` bind qua `onServiceConnected`).
- `AccountStatus(state: Connecting|Running|Stopped|Error, hp: Int?, sp: Int?, lastLog: String)`.
- Mỗi thread Python cập nhật trạng thái bằng cách gọi 1 callback Kotlin (`onStatusUpdate(username, state, hp, sp, lastLog)`) truyền vào khi start — callback này cập nhật `MutableStateFlow` phía Kotlin. Không dùng broadcast/Intent (chậm hơn, không cần thiết vì UI và Service cùng process).
- **API điều khiển** (gọi từ UI, chạy trên bound service instance):
  - `service.startAccount(username: String)` — đọc account từ `accounts.json`, spawn thread.
  - `service.stopAccount(username: String)` — set flag dừng vòng lặp Python (kiểm tra định kỳ trong vòng lặp chính, giống PC dùng biến `should_stop`), đóng socket, join thread.
  - `service.startAll()` / `service.stopAll()` — lặp qua toàn bộ account đã lưu.

### Lưu cấu hình

- File JSON trong `context.filesDir`:
  - `accounts.json`: `[{ "username": str, "password": str, "server_key": str }]`
  - Không có khái niệm "party" ở sub-project này (Train không cần leader/white-list) — chỉ là danh sách account độc lập, mỗi account tự chạy train riêng.
- Đọc/ghi bằng `org.json.JSONArray`/`JSONObject` (built-in Android, không cần thêm thư viện) từ phía Kotlin; phía Python đọc lại qua tham số truyền vào khi gọi `run_account(...)` (Kotlin đọc file, truyền username/password/server_key làm tham số Python — Python không tự đọc file cấu hình, tránh 2 nơi cùng đọc/ghi 1 file).
- **Lưu ý bảo mật**: mật khẩu lưu dạng plaintext trong file JSON nội bộ app (không world-readable, theo sandbox chuẩn Android) — chấp nhận được cho v1, không mã hoá thêm (giữ đơn giản, YAGNI).

### Port logic Train từ PC

- Port tối thiểu từ `bot/client.py` + phần Train trong `bot/combat.py`/`bot/state.py`: kết nối, auth (đã có từ Phase 1), nhận packet, vòng lặp combat Train (đòn thường/combo, không có boss/quest logic).
- **Không port**: `run_party_digioi.py` (party sync, o5_team, digioi_mode) — thuộc sub-project Dị Giới/Phó bản sau.
- File Python mới trong `android/app/src/main/python/`: `bot_client_train.py` (hoặc tái dùng cấu trúc cũ nếu import trực tiếp từ `bot/` package được — cần kiểm tra khi viết plan liệu Chaquopy có thể import thẳng package `bot/` gốc của PC hay phải copy/port thủ công do khác biệt môi trường I/O, sẽ quyết định cụ thể trong plan).

## Testing

- Unit/instrumented test tối thiểu cho sub-project này: 1 test start 2 account giả lập (mock server hoặc server thật với tài khoản test) chạy song song, xác nhận cả 2 đều nhận được trạng thái `Running` và không có thread nào block thread còn lại (test song song thật, không phải tuần tự).
- Test `stopAccount` dừng đúng account được chỉ định, không ảnh hưởng account khác đang chạy.

## Rủi ro

- Chaquopy dùng chung 1 interpreter cho nhiều thread — cần xác nhận GIL của CPython không làm nghẽn cổ chai khi nhiều account cùng lúc đang ở vòng lặp busy (đa số thời gian mỗi thread đang `socket.recv()` block I/O, nên GIL nhả ra khi block I/O — rủi ro thấp nhưng cần verify bằng test thực tế trong plan).
- Điện thoại tầm trung có thể giới hạn số account chạy song song thực tế (pin, CPU) — không đặt giới hạn cứng trong code, để người dùng tự cân nhắc.
