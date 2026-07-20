# Daily Rollover Design

## Mục tiêu

Bot treo xuyên 0h phải reset state theo ngày đúng một lần mà không cần Stop/Start. Rollover chỉ thay đổi bộ đếm/cache local; không teleport, rời party, relogin, chạy daily quest, gửi vận tiêu hoặc kích hoạt boss.

## Nguyên nhân

`GameClient.connect()` chỉ load `_online_base`, `_connect_time` và `claimed_gifts` một lần. `claim_online_gifts()` dùng các giá trị đó suốt vòng đời client. Qua 0h, tick tiếp theo tính uptime từ hôm trước rồi lưu state và danh sách quà đã nhận của hôm trước vào key ngày mới.

State thực tế lúc 01:07 ngày 2026-07-21 xác nhận lỗi: nhiều acc có `online_sec` từ 13.000 đến 21.000 giây và đủ `claimed=[10,20,30,60,90,180]`, trong khi acc mới Start chỉ có 180-360 giây và `claimed=[]`.

## Thiết kế

### Mốc ngày của client

Mỗi `GameClient` có `_daily_date`, được đặt thành ngày local hiện tại khi `connect()`. Vòng keepalive gọi `reset_daily_counters_if_needed()` trước `claim_online_gifts()`.

Hàm so sánh ngày hiện tại với `_daily_date`:

- Cùng ngày: trả `False`, không thay đổi gì.
- Sang ngày mới: cập nhật `_daily_date`, reset state an toàn, log một lần và trả `True`.

Hàm nhận `today`/`now` tùy chọn để test 23:59 -> 00:00 không phụ thuộc đồng hồ thật.

### State được reset

- Quà online: `_online_base = 0`, `_connect_time = now`, `claimed_gifts = set()`, ghi ngay record ngày mới.
- Daily quest: `_quest_cells = set()`, `_claimed_lines = set()`, `_claimed_loaded = False`.
- Vận tiêu RAM: `vantieu_started = None`, `vantieu_slots = {}`, `vantieu_req_code = None`. File `vantieu_state.json` đã tự trả count 0 khi ngày khác nên không cần xóa file.
- Dungeon: `dungeon_runs_today = None` để lần query tiếp theo lấy lại server state.
- Các bộ đếm phản hồi ngắn theo ngày: `_gift_status = {}` và `_gift_recv = 0`.

Rollover không gọi các routine tương ứng. Quà online tiếp tục tự đếm vì vốn được gọi mỗi tick. Vận tiêu và daily quest chỉ được mở khóa cache; chúng chạy khi luồng hiện có gọi lại.

### State không reset cưỡng bức

- `digioi_minutes`: đang điều khiển thời gian trong Dị Giới; đặt giả về 0 có thể làm bot tính sai thời gian còn lại.
- `legion_boss_count` và `legion_boss_next`: main loop dùng chúng để trigger reform; đặt về 0 có thể kéo party đi ngay sau 0h.
- Battle, party, map, route, mob learning và item state: không phải state theo ngày.
- Check-in, quà 14 ngày, `daily_state.json`, shop và local count vận tiêu: helper của chúng đã so sánh `date.today()` mỗi lần đọc.

Các counter server-sensitive chỉ thay đổi khi server gửi packet mới hoặc routine hiện có query lại.

### Migration state quà cũ

Record `gift_state.json` mới có `version: 2`. `_load_gift_state()` chỉ tin record version 2; record cũ không version được coi là state rỗng một lần.

Việc này sửa ngay các record ngày 2026-07-21 đã bị phiên bản cũ ghi bẩn. Bot có thể gửi lại request cho mốc server đã nhận trong hôm nay; server từ chối request trùng và bot vẫn tiếp tục bình thường.

### PC/APK

Source gốc sửa ở PC, sau đó chạy `tools/sync_apk_python.py`. `client.py` và coordinator Android phải đồng bộ với PC. Không build trước khi test source/dev.

## Kiểm thử

- Cùng ngày không reset và không ghi file.
- 23:59 -> 00:00 reset đúng một lần; lần tick thứ hai cùng ngày không reset lại.
- Quà online ngày mới bắt đầu từ 0 và chỉ claim mốc 10 phút sau đủ thời gian mới.
- State daily quest, vận tiêu và dungeon được invalid đúng danh sách.
- `digioi_minutes`, legion boss, battle, party và route không đổi.
- Record gift version 1/không version bị bỏ; version 2 được load bình thường.
- Coordinator gọi rollover trước `claim_online_gifts()` ở mỗi tick.
- PC/APK parity và regression hiện có tiếp tục pass.
