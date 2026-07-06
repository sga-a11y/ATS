# Android: Dị Giới thật (party thật trong game) - Thiết kế

> Sub-project #1 trong 4 phần đã chốt thứ tự làm (4→1→2→3): #4 tự động nhận quà/mail/giftcode/vận
> tiêu (đã xong), #1 Dị Giới thật (party thật) - đây, #2 di chuyển thông minh theo bản đồ,
> #3 phó bản tổ đội.

## Mục tiêu

Port sang Android luồng "Dị Giới" của `run_party_digioi.py` (PC): nhiều account trong 1 Party
cùng vào Dị Giới thật trong game, đồng bộ kênh, lập party thật (leader mời bằng entity, member tự
accept), leader chạy lòng vòng tìm quái (`start_run_around`), member tự theo/tự đánh, và tự
reconnect vô hạn khi bị rớt mạng - **khớp 100% hành vi PC, không phát minh thêm**.

## Nguyên tắc cốt lõi: PORT NGUYÊN VĂN, chỉ đổi kiểu khóa

PC đã giải quyết đầy đủ bài toán "nhiều party chạy song song trong 1 process" - Android **không
cần phát minh cơ chế mới nào**, chỉ cần đổi kiểu khóa dict từ `pidx` (số nguyên, PC) sang
`party.name` (chuỗi, khớp cách Android đặt tên Party) ở TẤT CẢ các cấu trúc dữ liệu party-scoped
sau (đọc trực tiếp từ `bot/client.py` + `bot/config.py` + `run_party_digioi.py`, port y nguyên
logic, không diễn giải lại):

- `_pstate(pidx)` (`run_party_digioi.py`) - dict trạng thái 1 party: `lock`, `invited` (Event),
  `channel`, `channel_ready` (Event), `ready_members` (set), `dailies_done`, `reconnecting` (set),
  `leader_gone` (Event), `reform_gen`, `route_party_ready`/`route_done` (Event), `n_members`,
  `mob_spot`/`mob_path`, `cmd_gen`, `disc_gen`.
- `_PARTY_ENTITIES` (`bot/client.py:~35`) - `{party_idx: set(entity_bytes)}`, mỗi account tự đăng
  ký entity của mình khi login xong.
- `_PARTY_JOINED` (`bot/client.py:36`) - `{party_idx: set(entity_bytes)}`, entity đã thật sự vào
  party (server xác nhận qua roster 0x0d sub06).
- `joined_member_count(party_idx)` / `reset_party_joined(party_idx)` (`bot/client.py:44,69`).
- `config.leaders_for(pidx)` (`bot/config.py:385-389`) = `PARTY_LEADERS` (global) ∪
  `PARTY_LEADERS_BY_IDX[pidx]` (riêng từng party) - dùng để member tự quyết định có accept lời mời
  party hay không (kiểm tra tên người mời có trong danh sách leader được tin cậy của CHÍNH party
  đó không).

Android: mọi nơi trên dùng `party.name` (String) thay `pidx` (Int) làm khóa. Không cần global
`PARTY_LEADERS` (mỗi Party Android độc lập, account đầu tiên trong `party.accounts` = leader của
đúng Party đó, tương đương PC's per-account `is_leader` khai báo trong `PARTY_CONFIG`).

## Kiến trúc

### `train_bot/party_state.py` (module mới)

Port `_pstate(pidx)` + `_PARTY_ENTITIES` + `_PARTY_JOINED` + các hàm liên quan
(`joined_member_count`, `reset_party_joined`) từ `bot/client.py`/`run_party_digioi.py` nguyên văn,
đổi khóa `pidx: int` → `party_name: str`. Đây là state CHIA SẺ giữa các thread account trong CÙNG
1 Party (Chaquopy chạy 1 process Python duy nhất cho toàn bộ app, các thread account của Android's
`BotForegroundService` đều truy cập chung namespace Python này - giống hệt cách PC's threads trong
1 process chia sẻ các dict module-level này).

### `train_bot/train_runner.py` - hàm mới `run_party_digioi(...)`

KHÔNG sửa `run_train()` hiện có (dùng cho mode "Đứng yên tại thành"/"Login ở đâu đứng yên đó").
Thêm hàm riêng `run_party_digioi(username, password, server_ip, server_id, party_name, is_leader,
leader_names, should_stop, on_status, get_cmd)`, port trực tiếp nhánh `is_digioi` của
`run_account()` trong `run_party_digioi.py` (đường dẫn dòng cụ thể sẽ được liệt kê trong plan khi
đọc lại file tại thời điểm viết plan, vì số dòng có thể lệch nếu file đổi giữa lúc viết spec và viết
plan) - CẮT bỏ hoàn toàn các nhánh không phải Dị Giới (train map/city/event/cleanbag) và các bước
daily quest/dungeon/boss nặng (đã có sub-project #4 lo mail/quà/vận tiêu/quân đoàn, không lặp lại;
`do_daily_dungeon`/`do_legion_boss`/`claim_daily_quests` KHÔNG đưa vào hàm này - out of scope, có
thể làm ở sub-project sau nếu cần).

Giữ lại các bước chính (port nguyên từ `run_party_digioi.py` nhánh DG):
1. `enter_di_gioi_safe()` (đã có sẵn trong `client.py`, port từ Task 3, chưa từng gọi).
2. Đăng ký entity vào `party_state` (`_PARTY_ENTITIES`).
3. Đồng bộ kênh: leader (picker) `pick_best_channel(need=len(party.accounts))`, ghi kết quả vào
   `party_state`; member chờ rồi `switch_channel`.
4. Leader: `invite_members()` (mời theo entity trong `party_state`), chờ đủ member
   (`joined_member_count`), `set_party_strategist()`, `start_run_around()`.
5. Member: chờ được mời (client tự auto-accept qua cơ chế đã có sẵn trong `client.py`, dùng
   `leaders_for`-tương đương lấy theo `party_name`), đứng yên tại safe cho tới khi vào party.
6. Vòng giữ sống (keepalive, poll như PC ~3-5s): phát hiện member rớt/bị dump map → leader
   re-invite; phát hiện hết giờ Dị Giới - **kiểm tra `c.digioi_minutes` CỦA TỪNG ACCOUNT RIÊNG
   LẺ** (không phải party-wide) → account đó tự thoát về thành + đóng, các account khác trong
   Party còn giờ tiếp tục chạy bình thường (khớp `run_party_digioi.py` dòng ~1312-1328).
7. Reconnect: mất kết nối ngoài ý muốn (không phải do bấm Stop) → backoff-retry login vô hạn
   (5s×3 → 30s×10 → 60s, khớp `_run_account_supervised`), gọi lại với cờ tương đương
   `is_reconnect=True` (bỏ qua các bước nặng, vào thẳng đồng bộ kênh + gia nhập lại party).

### UI (`MainActivity.kt`)

Mỗi `PartyCard` thêm 1 dropdown "Chế độ" bên cạnh 2 lựa chọn hiện có ("Đứng yên tại thành"/"Login
ở đâu đứng yên đó"), thêm lựa chọn mới "Dị Giới (party thật)". Khi chọn mode này,
`BotForegroundService.startAccount`/`startAccountIn` cho account đó gọi `run_party_digioi(...)`
thay vì `run_train(...)`, với `is_leader = (account == party.accounts.first())`.

## Testing

Test tự động chỉ xác nhận cơ chế chia sẻ state đúng (`party_state` giữa các "thread" giả lập trong
1 test, không cần tài khoản thật - mirror cách `TrainRunnerTest` đã test `run_train`/`_apply_cmd`).
Việc party có hình thành THẬT trong game hay không, đồng bộ kênh có đúng hay không, cần test thủ
công với tài khoản thật (không có cách nào test tự động điều này qua network thật - giống quy ước
đã áp dụng cho các tính năng cần server thật khác trong dự án).

## Không làm trong sub-project này

- Không làm các mode khác của `run_party_digioi.py` (train map/city/event/cleanbag) - out of scope,
  Android đã có `run_train` cho các mode đứng yên/login-tại-chỗ riêng.
- Không làm daily quest/dungeon/boss quân đoàn trong luồng Dị Giới - đã có sub-project #4 lo phần
  auto-claim liên quan, không lặp lại ở đây.
- (Đã bổ sung khi review: chế độ "Dị Giới SOLO" - mỗi account chạy độc lập, không lập party, không
  đồng bộ kênh - NẰM TRONG phạm vi sub-project này, port nguyên từ `run_party_digioi.py:819-846,
  1302-1311`, xem plan.)
