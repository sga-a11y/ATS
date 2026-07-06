# Android: Tự động nhận mail/quà/quân đoàn + nhập giftcode + vận tiêu - Thiết kế

> Sub-project #1 trong 4 phần đã chốt thứ tự làm (4→1→2→3): #4 tự động nhận
> quà/mail/giftcode/vận tiêu, #1 Dị Giới thật (party thật), #2 di chuyển thông minh theo bản đồ,
> #3 phó bản tổ đội. Đây là sub-project #4.

## Mục tiêu

Port sang Android các hành vi **tự động, không cần cấu hình gì thêm** mà bot PC đã có sẵn (chạy
đúng như PC, không phát minh thêm UI bật/tắt không tồn tại bên PC):
- Tự nhận mail (`claim_mail`)
- Tự nhận quà mốc giờ online (`claim_online_gifts`)
- Tự nhận quà quân đoàn hàng ngày (`claim_legion_gift`)
- Tự chạy vận tiêu (escort) theo chế độ smart-match có sẵn (`do_van_tieu`)

Và 1 hành động **cần người dùng nhập tay** (giống PC, không tự động được vì cần dữ liệu thật):
- Nhập giftcode (`redeem_giftcode`) - áp dụng cho toàn bộ account đang chạy trong 1 Party.

## Không làm trong sub-project này

- **Không thêm bất kỳ checkbox/toggle bật-tắt nào** cho vận tiêu hay các tính năng tự động khác -
  PC không có, Android không được tự bịa thêm. `VANTIEU_ENABLE=True` là hằng số cố định trong
  `train_bot/config.py` (khớp `bot/config.py`), luôn bật cho mọi account.
- Chế độ vận tiêu "gửi pet theo danh sách cố định" (`VANTIEU_PETS`/`VANTIEU_PETS_NAMES`) - chỉ
  dùng chế độ **smart-match** (roster + `vantieu_requests.json`), đơn giản hơn, không cần UI chọn
  pet thủ công.
- Boss mode: **không đụng tới** trong sub-project này - hoàn toàn tự động theo ngữ cảnh dungeon
  (`self.state.boss_mode = True/False` do các hàm dungeon-specific tự set), không có form nhập
  liệu hay toggle nào ở đây cả. Đợi tới khi port tính năng đánh boss/dungeon thật (sub-project #3
  hoặc sau).

## Kiến trúc

### Dữ liệu cần thêm
- Copy `vantieu_requests.json` (gốc: `E:\Claude\ATS\vantieu_requests.json`) vào
  `android/app/src/main/assets/train_bot_data/vantieu_requests.json`.
- `train_bot/config.py` thêm: `VANTIEU_ENABLE = True`, load `VANTIEU_REQUESTS` từ asset JSON đó
  (theo đúng pattern `_load_cities`/`_load_pets` đã có, dùng `_log_asset_error` khi lỗi).

### `train_bot/train_runner.py` - vòng lặp phụ (song song với vòng lặp combat chính)
Các hàm `claim_mail`/`claim_online_gifts`/`claim_legion_gift`/`do_van_tieu` đã có sẵn nguyên vẹn
trong `train_bot/client.py` (copy từ PC ở Task 3, chưa từng được gọi tới). Cần 1 thread phụ (giống
`wander()` cũ, nhưng không xoá - thêm mới) gọi các hàm này theo lịch:
- `claim_mail()`: gọi mỗi ~60s (hàm tự có cơ chế chờ ổn định bên trong, gọi dư không hại vì tự
  kiểm tra danh sách mail rỗng thì return ngay).
- `claim_online_gifts()`: gọi mỗi ~60s (hàm tự kiểm tra mốc giờ đã đủ chưa).
- `claim_legion_gift()`: gọi 1 lần khi bắt đầu chạy + mỗi ~30 phút (hàm tự có guard "1 lần/ngày"
  qua `daily_state.json`, gọi dư không hại).
- `do_van_tieu()`: gọi lần đầu ngay sau khi vào game, hàm trả về epoch "giờ gọi lại tiếp theo"
  (hoặc `None` = hết việc hôm nay) - thread phụ dùng giá trị này để `sleep` chính xác tới đúng
  giờ thay vì poll liên tục.

Thread phụ này chạy độc lập, không chặn/bị chặn bởi vòng lặp combat chính - mọi lỗi bên trong
(kết nối rớt giữa chừng...) chỉ log, không làm crash `run_train()` (bọc try/except quanh mỗi lần
gọi, giống quy ước "không bao giờ throw ra ngoài run_train()" đã có).

### Giftcode - UI + Service
- `BotForegroundService` thêm `fun redeemGiftcode(usernames: List<String>, code: String)`: với
  MỖI username đang có thread chạy, gửi lệnh redeem qua cơ chế lệnh sống đã có sẵn (`pendingCmd`/
  `getCmd`, giống cơ chế đổi kênh/teleport thành hiện tại) - thêm loại lệnh mới `["giftcode", code]`.
- `train_runner.py`'s vòng lặp chính (đã có đọc lệnh qua `getCmd.call()`) thêm xử lý loại lệnh
  `"giftcode"`: gọi `c.redeem_giftcode(code)`.
- UI (`MainActivity.kt`): thêm 1 nút "🎟 Giftcode" trên mỗi `PartyCard` (cạnh "Start party"/"Stop
  party"), bấm mở `AlertDialog` nhập code, bấm Lưu gọi
  `service.redeemGiftcode(party.accounts.map { it.username }, code)` - gửi cho TẤT CẢ account
  đang chạy trong Party đó (khớp hành vi PC: 1 nút/Party, áp dụng cho acc đang Start trong Party).

## Testing

- Test đơn giản: xác nhận `train_bot.config.VANTIEU_REQUESTS`/`VANTIEU_ENABLE` load được (giống
  `TrainBotImportTest`/test CITIES đã có).
- Test cơ chế lệnh giftcode: giả lập gửi lệnh `["giftcode", "TESTCODE"]` qua `getCmd`, xác nhận
  `train_runner.py` gọi đúng `redeem_giftcode` với code đó (dùng callback giả lập như
  `TrainRunnerTest` đã có, không cần tài khoản thật).
- Không có test tự động cho việc mail/quà/vận tiêu THẬT có về đúng không (cần tài khoản thật +
  thời gian chờ thật - để test thủ công, giống các tính năng cần server thật khác trong dự án).

## Rủi ro

- `do_van_tieu()`/`claim_mail()` gọi khi đang giữa combat có thể bị server bỏ qua/lỗi (giống lưu ý
  đã có ở nhánh đổi kênh/teleport: "switch_channel/leave_party giữa battle dễ bị server bỏ qua").
  Thread phụ nên kiểm tra `not c.in_combat()` trước khi gọi các hàm này, tương tự cách
  `_do_manual_cmd` bên PC chờ hết trận trước khi đổi kênh/teleport.
