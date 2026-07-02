# TS Online Bot — Bản Android (Native App + Floating Bubble)

## Bối cảnh

Bot hiện tại (`bot/*.py` + `run_party_digioi.py` + `gui.py`) là app Windows: GUI Tkinter, đóng
gói bằng Nuitka (biên dịch native C, chống dịch ngược mạnh). Core logic (kết nối socket TCP thẳng
tới server game, không cần app game thật, xem `bot/client.py`) là Python thuần, không phụ thuộc
Windows.

Yêu cầu: 1 app Android mà **người không biết code cũng dùng được** (loại bỏ hướng Termux), có
**icon nổi (floating bubble)** kiểu chat-head — bấm vào mở ra UI đầy đủ (Start/Stop/Cấu hình) như
bản PC, chạy được **không giới hạn số account** trên 1 máy, và có **chống dịch ngược** cho phần lõi
giao thức (vì Chaquopy chạy CPython thật, `.pyc` decompile được — khác Nuitka biên dịch native C).

## Mục tiêu

- 1 file APK, cài xong dùng được ngay, không cần cài thêm gì khác (không Termux).
- Bong bóng nổi luôn có mặt, bấm vào mở/thu UI chính.
- UI chính đầy đủ tính năng tương đương bản PC ngay từ v1 (không rút gọn):
  nhiều party/nhóm, mọi mode (Train map/Train Dị Giới/Về thành/Đứng yên), Start/Stop từng acc,
  xem log/trạng thái real-time, giftcode, cấu hình hồi máu, Dị Giới Solo/Party.
- Bot chạy nền bền (Foreground Service), không bị Android kill khi tắt màn hình.
- Không giới hạn cứng số account — cảnh báo UI nếu máy có dấu hiệu quá tải, không tự chặn.
- Phần giao thức (XOR cipher + build/parse frame) tách khỏi Python, viết native C++ (NDK/JNI).

## Kiến trúc

```
┌─────────────────────────────────────────┐
│  Overlay Bubble (Kotlin, WindowManager)  │  icon noi, bam mo/thu UI, hien badge trang thai
├─────────────────────────────────────────┤
│  Main UI (Kotlin + Jetpack Compose)      │  man party/config/log/giftcode/settings
├─────────────────────────────────────────┤
│  Foreground Service (Kotlin)             │  song nen, dieu phoi N luong account
├─────────────────────────────────────────┤
│  bot-core (Python qua Chaquopy)          │  client.py/combat.py/state.py/config.py/login.py/
│                                           │  run_party logic (port gan nguyen tu ban PC)
├─────────────────────────────────────────┤
│  protocol-native (C++ qua JNI/NDK)       │  XOR cipher + build/parse frame (opcode/length/payload)
└─────────────────────────────────────────┘
                    │
              TCP socket thang toi server game (KHONG can app game that)
```

### 1. protocol-native (C++ / NDK)
- Port `bot/protocol.py` (`encode()`, `decode()`, XOR key, cấu trúc frame `c0 91 [len2] [00 00]
  [opcode] [payload]`) sang C++, build thành `.so`.
- Expose qua JNI: 1 hàm `encodeFrame(opcode, payload) -> bytes`, 1 hàm `decodeStream(buf) ->
  List<Frame>`.
- Cả Kotlin (Foreground Service, nếu cần đọc trực tiếp) lẫn Python (qua 1 module Python mỏng gọi
  JNI qua Chaquopy's `java` bridge) đều dùng chung thư viện native này — Python **không tự làm**
  XOR/framing nữa.

### 2. bot-core (Python qua Chaquopy)
- Copy gần nguyên các file hiện có: `bot/client.py`, `bot/combat.py`, `bot/state.py`,
  `bot/config.py`, `bot/login.py`, và logic điều phối party từ `run_party_digioi.py` (tách phần
  logic party khỏi phần CLI/`argv` để dùng lại được).
- Sửa duy nhất: chỗ gọi `protocol.encode()/decode()` trỏ sang gọi native module (mục 1) thay vì
  code Python thuần hiện tại trong `protocol.py`.
- Build: Chaquopy cấu hình **không** đóng gói `.py` source trong APK — chỉ giữ bytecode biên
  dịch. Trước khi build, chạy PyArmor để obfuscate (đổi tên định danh + mã hoá chuỗi hằng số như
  skill ID, opcode map trong `config.py`).

### 3. Foreground Service
- Giữ app sống khi tắt màn hình (xin quyền loại trừ battery optimization).
- Quản lý N luồng account (mỗi acc 1 thread Python, y hệt mô hình bản PC hiện tại — `GameClient`
  mỗi acc độc lập).
- Không giới hạn cứng số account. Nếu phát hiện dấu hiệu quá tải (CPU/RAM cao, nhiều lỗi kết nối
  liên tiếp) thì chỉ **cảnh báo** trên UI, không tự dừng acc.

### 4. Overlay Bubble
- Icon nổi kiểu chat-head (Messenger), xin quyền `SYSTEM_ALERT_WINDOW`.
- Bấm vào mở Main UI (Activity), bấm lần nữa hoặc nút thu gọn thì thu UI về lại bong bóng
  (Service vẫn chạy nền, không bị dừng khi thu UI).
- Hiện badge nhỏ trên bong bóng: số acc đang chạy / tổng số.

### 5. Main UI (Kotlin + Jetpack Compose)
Tương đương các màn hình bản PC (`gui.py`):
- Danh sách nhóm/party (tabs), mỗi party: server, mode (Train map/Train Dị Giới [Party|Solo]/Về
  thành/Đứng yên), danh sách account (thêm/xoá/bật-tắt), cấu hình hồi máu riêng từng acc.
- Nút Start party / Stop party / Start từng acc / Stop từng acc.
- Bảng trạng thái real-time: acc, nhân vật, vai trò (LEADER/member/Quân sư/**solo**), map, kênh,
  trong PT, DG còn lại, đang đánh — y hệt cột trong bảng PC hiện tại.
- Giftcode: nhập + áp dụng cho acc/party chọn.
- Cài đặt: ngưỡng hồi máu mặc định, v.v.

### 6. Data layer
- JSON schema **y hệt bản PC** (`accounts.json`, `servers.json`, `cities.json`, `train_maps.json`,
  v.v.) — lưu trong storage riêng app (app-private, Android Scoped Storage).
- Vì cùng schema, sau này làm thêm tính năng import/export giữa PC và Android không cần đổi format.

### 7. Bảo vệ chống dịch ngược (nhiều lớp)
1. **Native cho phần lõi giao thức** — mục 1, lớp bảo vệ mạnh nhất (tách hẳn khỏi Python).
2. **Chaquopy: không ship `.py` source**, chỉ bytecode biên dịch.
3. **PyArmor obfuscate** code Python còn lại (đổi tên định danh, mã hoá chuỗi/hằng số) trước khi
   Chaquopy đóng gói.
4. **R8/ProGuard** obfuscate code Kotlin, ký release key.
5. Basic anti-debug/anti-root check lúc khởi động (tương tự "Anti-debug guard" bản PC hiện có ở
   `bot/_guard.py`).

**Giới hạn cần chấp nhận:** vì Chaquopy chạy CPython thật, không có mức bảo vệ nào đạt được độ
mạnh như Nuitka biên dịch native C bên PC — các lớp trên chỉ làm khó hơn, không loại trừ hoàn toàn
khả năng dịch ngược phần Python.

## Luồng dữ liệu chính (Start 1 party)

1. User bấm Start trên Main UI → ViewModel gửi lệnh tới Foreground Service.
2. Service tạo N thread Python (qua Chaquopy), mỗi thread chạy 1 `GameClient` (port từ
   `bot/client.py`) cho 1 account.
3. `GameClient` login (HTTP, `bot/login.py`) → mở socket TCP → mọi frame gửi/nhận đi qua
   `protocol-native` (JNI) để mã hoá/giải mã.
4. Combat/party logic (Python, port từ `combat.py`/`state.py`/`run_party_digioi.py`) chạy y hệt
   luồng quyết định bản PC.
5. Service phát trạng thái (map, HP/SP, đang đánh, log...) qua sự kiện nội bộ (LiveData/Flow) →
   Main UI cập nhật bảng trạng thái + Overlay Bubble cập nhật badge.

## Không làm trong v1

- Không tự động hoá UI game thật (không cần vì bot dùng socket thẳng).
- Không giới hạn cứng số account bằng code (chỉ cảnh báo UI).
- Không làm tính năng import/export PC↔Android (data layer đã tương thích sẵn, để làm sau nếu cần).

## Rủi ro / điều cần xác nhận khi build thật

- Cấu hình Chaquopy + NDK trong cùng 1 Gradle project cần kiểm chứng thực tế (build thử sớm để
  tránh vướng ở giai đoạn cuối).
- Chưa có Android Studio/SDK/NDK cài trên máy hiện tại — cần cài trước khi bắt đầu implement.
- PyArmor hỗ trợ target Android/ARM có thể cần bản trả phí tuỳ mức obfuscate mong muốn — cần kiểm
  tra giấy phép/chi phí trước khi chốt dùng.
