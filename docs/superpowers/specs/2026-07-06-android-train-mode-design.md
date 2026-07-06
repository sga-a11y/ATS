# Android: Di chuyển thông minh theo bản đồ (train mode) - Thiết kế

> Sub-project #2 trong 4 phần đã chốt thứ tự (4→1→2→3): #4 auto-claim (xong), #1 Dị Giới (xong),
> #2 train mode (bản đồ) - đây, #3 phó bản tổ đội. CÙNG LÚC nối logic thật cho 2 tuỳ chọn đã có UI
> nhưng chưa hoạt động ở sub-project #1: "Không có chủ PT" (has_leader) và "Làm nhiệm vụ hàng ngày"
> (do_daily) - áp dụng cho MỌI mode (train mới, Dị Giới, Đứng yên tại thành, Login ở đâu đứng yên đó).

## Mục tiêu

Port nguyên văn nhánh `train_on_map` (mode="train") của `run_party_digioi.py` sang Android: party
đi theo route đã ghi sẵn (`train_routes.json`) từ thành tới map train, tập kết tại điểm an toàn
(`train_maps.json`'s "safe"), chọn điểm quái (cụ thể hoặc "Bot tự chọn"), leader kéo cả party ra
điểm đó, và cơ chế **reform** (dồn cả party về thành khi có account bị văng khỏi map, rồi kéo lại)
- khớp 100% PC.

## Nguyên tắc: PORT NGUYÊN VĂN, chỉ đổi khoá pidx→party_name

Giống hệt sub-project #1: `party_state.py` (đã có từ #1) tái sử dụng nguyên - không tạo state mới.
`has_leader` (đã xây ở #1 cho Dị Giới) tái dùng cho train mode. Mọi hàm nghiệp vụ
(`follow_path`, `navigate_to`, `go_to_town`, `teleport`, `claim_daily_quests`, `do_daily_dungeon`)
đã có sẵn trong `client.py` từ Task 3, chưa từng được gọi.

## Kiến trúc

### Dữ liệu
- Copy `train_maps.json`/`train_routes.json` (gốc `E:\Claude\ATS\`) vào
  `android/app/src/main/assets/train_bot_data/`, y nguyên (20 map, 11 route).
- `train_bot/config.py` thêm `_load_train_maps()` → `TRAIN_MAPS` (dict map_id(str) → {name, safe,
  mobs}), `_load_train_routes()` → `TRAIN_ROUTES` (dict map_id(str) → {name, from_city, city_flag,
  dest_map, steps}) - mirror `_load_cities` pattern.

### `train_bot/train_runner.py` - `run_party_train()` + `run_train_solo()`
Port nhánh `train_on_map` của `run_account()` (đọc trực tiếp file PC tại thời điểm viết plan để
lấy đúng số dòng, KHÔNG diễn giải lại bằng lời):
- Setup: nếu login đúng map train + có "safe" → ra safe ngay; nếu sai map → route (đi qua thành
  `from_city`/`city_flag` rồi `follow_path` theo `steps` tới `dest_map`).
- Đồng bộ kênh (tái dùng y hệt cơ chế `channel_ready`/`is_picker` đã có từ #1).
- Leader: chờ đủ member sẵn sàng ở safe → mời theo entity → chọn điểm quái (`mob_spot`, cụ thể
  hoặc random trong `mobs`) → kéo cả party ra bằng `follow_path`/`navigate_to`.
- Member: chờ được mời (dùng `has_leader` y hệt Dị Giới - khi "Không có chủ PT" thì đứng yên chờ
  leader ngoài/tay mời, không tự invite).
- Keepalive: phát hiện account bị văng khỏi map train (chết/dump dungeon) → bump `reform_gen` →
  toàn party tự động **reform** (leader giải tán party cũ, dồn về thành, lập lại, kéo ra lại).
- `run_train_solo()`: đơn giản hơn nhiều (không route/reform/party) - map train không cần party
  vẫn hỗ trợ, nhưng ĐÂY LÀ ĐIỂM CẦN XÁC NHẬN - PC's mode "train" luôn giả định có party (route/reform
  gắn liền); nếu Android chỉ cần 1 account/map train không cần party, đó chính là
  `RUN_MODE_STAND_STILL`/`RUN_MODE_STAY_LOGIN` cũ (đứng yên tại 1 vị trí) - KHÔNG cần thêm 1 solo
  mode riêng cho train. → Quyết định: train mode LUÔN dùng party (kể cả party 1 người, is_leader
  luôn true khi chỉ có 1 account) - không làm `run_train_solo()` riêng, dùng `run_party_train()`
  cho mọi trường hợp kể cả party lẻ 1 account.

### Nối `has_leader` + `do_daily` vào tất cả mode

- **`has_leader`**: `run_party_train()` nhận tham số `has_leader` y hệt `run_party_digioi()` (đã có
  từ #1) - Kotlin đọc `party.noLeader` để truyền vào, không cần sửa gì thêm ở tầng Kotlin ngoài việc
  gọi hàm mới thay vì cũ khi mode = TRAIN.
- **`do_daily`**: thêm 1 bước gọi `c.claim_daily_quests()`/`c.do_daily_dungeon()` (nếu
  `party.doDaily == true`) NGAY SAU khi vào world, TRƯỚC khi vào logic mode-specific - áp dụng cho
  CẢ 4 mode hiện có (`run_train` cho STAND_STILL/STAY_LOGIN, `run_party_digioi`/`run_digioi_solo`
  cho Dị Giới, `run_party_train` mới cho Train) - mirror đúng vị trí gọi trong `run_account()` PC
  (dòng ~249-265, nhánh `if not is_reconnect: ... c.claim_mail() ... ` mở rộng thêm
  `claim_daily_quests`/`do_daily_dungeon` có điều kiện theo `do_daily`).
- Cần thêm tham số `do_daily: bool` vào CẢ 4 hàm chạy (`run_train`, `run_party_digioi`,
  `run_digioi_solo`, `run_party_train`) - Kotlin đọc `party.doDaily` truyền vào tất cả.

### UI (`MainActivity.kt`)
- Thêm `RunModes.TRAIN` vào dropdown mode chính.
- Khi chọn Train: hiện dropdown "Map train" (tên từ `TRAIN_MAPS`) + dropdown "Quái" (điểm quái
  trong map đó, mặc định "Bot tự chọn" = chọn ngẫu nhiên mỗi lần).
- 2 checkbox "Không có chủ PT"/"Làm nhiệm vụ hàng ngày" đã có sẵn từ #1 (hiện cho MỌI mode) - giờ
  thực sự có tác dụng, không cần thêm UI mới, chỉ cần dây nối dispatch đúng.

## Testing
Test cơ chế (route/reform state qua `party_state`, dispatch đúng hàm theo mode) không cần tài
khoản thật - mirror `TrainRunnerTest`/`PartyStateTest` đã có. Việc route/reform có chạy đúng thật
trong game cần test thủ công (giống quy ước đã áp dụng xuyên suốt dự án).

## Không làm trong sub-project này
- Không làm nhánh "event"/"cleanbag" của PC (out of scope, không liên quan train map).
- Không có "solo train" riêng biệt - train mode luôn qua `run_party_train()` (kể cả party 1
  account), dùng `run_train`/STAND_STILL cho nhu cầu 1 account không cần route/reform.
