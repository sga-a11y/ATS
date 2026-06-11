# Cấu trúc CONFIG (đọc khi setup máy mới)

> `config.py` và `accounts.json` **KHÔNG up git** (chứa mật khẩu). Máy mới phải tự tạo.
> File này mô tả cấu trúc để tạo lại đúng.

## File nào tracked / gitignored

| File | Git? | Vai trò |
|---|---|---|
| `bot/config.example.py` | ✅ tracked | Bản mẫu của config.py |
| `bot/config.py` | ❌ gitignore | Config thật (copy từ example, điền mật khẩu) |
| `accounts.json` | ❌ gitignore | **Cấu hình party (GUI sửa file này)** |
| `servers.json` | ✅ tracked | Danh sách server (ip + id auth) |
| `train_maps.json` | ✅ tracked | Map train: safe + điểm quái |
| `cities.json` | ✅ tracked | Thành để teleport (city_id + flag) |
| `pets.json` | ✅ tracked | Pet: skills + boss_skill |
| `skills_db.json` | ✅ tracked | Tên + SP skill |

## Setup máy mới (3 bước)

1. `copy bot\config.example.py bot\config.py` (giữ nguyên, không cần sửa gì nếu dùng GUI).
2. Chạy `python gui.py` (hoặc `run_gui.bat`) → bấm **⚙ Cấu hình** → thêm party/acc/server/mode → **Lưu** (tự tạo `accounts.json`).
3. Start.

> `config.py` giờ chỉ giữ hằng số game (API_KEY, GAME_HOST, skill, combat tuning...).
> Phần party + mode + server thì **accounts.json override** (GUI quản lý). Không cần sửa code.

## accounts.json — cấu trúc (GUI tự ghi)

```json
{
  "channel": 4,                      // kênh chung (picker chọn kênh ít người, fallback)
  "parties": [
    {
      "server": "trieu_van",         // key trong servers.json (trieu_van / tao_thao)
      "mode": "train",               // CHẾ ĐỘ (xem bảng dưới)
      "start_city_id": 12831,        // map/thành theo mode
      "mob_index": 0,                // (mode train) chọn điểm quái thứ mấy trong train_maps.json
      "city_flag": 0,                // (mode city) flag thành, lấy từ cities.json
      "do_dungeon": true,            // có tự đánh daily dungeon không
      "accounts": [
        { "u": "sga001", "p": "matkhau" },   // DÒNG ĐẦU = chủ PT (leader)
        { "u": "sga002", "p": "matkhau" },
        { "u": "#sga003", "p": "matkhau" }   // username bắt đầu '#' = BỎ QUA acc đó
      ]
    }
  ]
}
```

### mode (chế độ mỗi party)
| mode | Ý nghĩa | start_city_id | Field thêm |
|---|---|---|---|
| `digioi` | Train Dị Giới | 49942 (cố định) | — |
| `train` | Train map | map_id (trong train_maps.json) | `mob_index` (điểm quái) |
| `city` | Tập trung về thành rồi đứng yên | city_id (trong cities.json) | `city_flag` |
| `stand` | Login đâu đứng yên đó | 0 | — |
| `cleanbag` | Dọn túi (chưa làm) | 0 | — |

### Quy ước accounts
- **Dòng đầu = chủ PT (leader)** — bot tự mời + dẫn train + set quân sư.
- **Leader rỗng** `{ "u": "", "p": "" }` ở đầu = **KHÔNG có bot-leader** (member tự đứng chờ leader ngoài/tay mời). GUI = tick "Không có chủ PT".
- **Username có `#` đầu** = **bỏ qua** acc đó (như comment), vẫn giữ trong file để bật/tắt.

## servers.json (tracked)

```json
{
  "servers": {
    "trieu_van": { "label": "Triệu Vân", "ip": "103.82.28.98", "id": 1 },
    "tao_thao":  { "label": "Tào Tháo",  "ip": "103.82.28.99", "id": 2 }
  }
}
```
- `ip` = IP TCP connect.
- `id` = **SERVER ID trong gói auth** (byte thứ 5: `00 00 02 01 [id]`). Sai id → connect được nhưng KHÔNG vào world.
- **Thêm server mới:** capture 1 lần login server đó, đọc byte thứ 5 gói auth (0x01) = id.

## Cách config.py nạp accounts.json
1. Đọc `accounts.json` → build `PARTIES` (bỏ acc `#`) + `PARTY_CONFIG[pidx]` = {mode, start_city_id, mob_index, city_flag, server, server_ip, server_id, do_dungeon}.
2. `START_CITY_ID` toàn cục = party đầu (fallback cho CLI).
3. Không có `accounts.json` → dùng `PARTIES` hardcode trong config.py.

## State files (auto tạo, gitignore)
- `checkin_state.json`: điểm danh / quà 14 ngày / số lượt dungeon đã đánh.
- `gift_state.json`: thời gian online + mốc quà online đã nhận.
- `party.log`: log chạy.
