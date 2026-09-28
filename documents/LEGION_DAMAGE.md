# THEO DÕI DAME BOSS QUÂN ĐOÀN

User chốt 28/09/2026. Luật game và cấu trúc gói: xem `KNOWLEDGE.md` mục
"BOSS QUÂN ĐOÀN — bảng damage".

## Mục tiêu
Ghi lại dame boss QĐ của **từng thành viên** (tổng + số lần đánh + lịch sử từng lần),
xem được cả khi acc đã tắt.

## Nguồn dữ liệu (server là nguồn sự thật)
| Gói | Khi nào | Ghi tổng | Đếm số lần |
|---|---|---|---|
| `S:039-002` (`0x27 sub02`) bảng QĐ, có `bossDamage` từng member | acc vừa vào game / relogin | ✅ nếu tổng > bản ghi | ❌ phần tăng = **dame lúc offline (không rõ số lần)** |
| `S:039-116` (`0x27 sub0x74`) `roleId(8)+tổng(4)` | acc đang online, server đẩy | ✅ nếu tổng > bản ghi | ✅ +1 lần, delta = dame lần đó |

- Chỉ ghi khi **tổng server > bản ghi**. Bằng nhau → bỏ qua (tự khử trùng khi nhiều acc cùng QĐ
  cùng nhận một gói). Nhỏ hơn → server đã reset (member rời/vào lại) → ghi đè, đánh dấu `reset`,
  không tính delta âm.
- Parser `039-002` đã kiểm trên 5 capture / 4 QĐ: đọc hết đúng tới byte cuối gói.
- **ĐÃ ĐO (party.log 28/09):** server đẩy `039-116` của MỌI member cho mọi acc QĐ đang online —
  18 lần đánh mới từ 16 role khác nhau, 36 lần acc khác nhận trùng (bị bỏ qua đúng). → KHÔNG cần
  đường dự phòng đọc lại bảng 5 phút/lần.
- Bảng QĐ `039-002` chỉ gửi **1 lần lúc login**. Bot giữ lại bảng đó kể cả khi chưa tick; tick lúc
  acc đang chạy → nạp bù (lấy tên/cấp boss; tổng chỉ ghi nếu lớn hơn, không coi là reset).
  Bug thật 28/09: tick giữa chừng → cả QĐ hiện `role:<id>` không tên.

## Cấp boss của từng lần đánh (user chốt 28/09 — chỉ hiện trong Chi tiết)
Nguồn crack client `Logic/Organization.lua`: `bossCount` = **số boss đã hạ** (擊殺數);
`GetBossHp(level)` mặc định `level = bossCount + 1`, HP = `level × 150000`.
- `bossCount` lấy từ `039-002` (lúc login) và `S:039-115` (`0x27 sub0x73`, `bossCount(2)+dame QĐ(4)`).
- Capture `ts_lgboss.pcap`: sau mỗi lần đánh server gửi `116` rồi **ngay sau đó** `115`.
  → Lần đánh (116) ghi `lv = bossCount đang biết + 1`. Nếu `115` ngay sau (≤30s) có `bossCount`
  tăng → lần đánh đó **hạ boss** (`kill=1`).
- **Boss quay vòng Lv1 → Lv7 → Lv1** (user xác nhận 28/09). Client KHÔNG có vòng này
  (`GetBossHp` chỉ là `bossCount + 1`) → server tự làm, chưa biết server đưa `bossCount` về 0 hay
  để tăng mãi → cấp = `bossCount % 7 + 1` (đúng cả hai), và "hạ boss" = `bossCount` **đổi** (kể cả
  6 → 0), không chỉ tăng.
- Dame offline **không** ghi cấp (không biết lúc đó đánh cấp nào).
- Chi tiết hiện: `T6 20:10  +123,456 · Boss Lv3 (hạ boss)`.
- Capture cùng file cho thấy acc nhận `116` của **member khác** (1 mẫu) → nghi server có đẩy.

## Bản ghi
- **Chung một bản ghi cho mỗi QĐ** (theo `orgId`), mọi acc có tick cùng ghi vào. File
  `legion_damage.json` cạnh exe (APK: thư mục app), có khoá ghi.
- Chia theo **tuần: 0h thứ Hai giờ VN (UTC+7)** — server reset dame đúng mốc này. Sang tuần mới mở
  bucket mới (tổng/số lần từ 0). Giữ **2 tuần** (tuần này + tuần trước), cũ hơn thì xoá.
- Cấu trúc:
  ```json
  {"orgs": {"896": {"name": "FC_ThanhXuan", "updated": 0,
     "weeks": {"2026-09-28": {"<roleId hex>": {"name": "...", "total": 0, "hits": 0,
        "last": 0, "log": [{"ts": 0, "dmg": 0, "off": 0}]}}}}},
   "accounts": {"username": "896"}}
  ```
  `off=1`: dame lúc offline; `reset=1`: server trả tổng nhỏ hơn bản ghi.

## Bật / tắt
Ô tick **"Theo dõi dame boss QĐ"** riêng từng acc, mặc định **tắt**. Lưu ở
`accounts.json` → `settings.legion_dmg` (PC) / `legion_dmg` (APK). Tick ở acc nào thì acc đó tham
gia ghi; acc không tick vẫn mở xem được.

## UI (PC + APK giống nhau)
Nút **[QĐoàn]** ngay bên phải nút Skill. Bấm vào:
```
☐ Theo dõi dame boss QĐ        QĐ FC_ThanhXuan · cập nhật 20:15
[Tuần này] [Tuần trước]
#  Tên   Tổng dame   Số lần   Lần cuối        
1  Abc   1,234,567     5      T6 20:10  [Chi tiết]
```
- Xếp giảm dần theo tổng (giống game).
- **[Chi tiết]**: lịch sử của member đó, 2 khối *Tuần này / Tuần trước*; mỗi dòng giờ + dame;
  dòng offline ghi "(lúc offline, không rõ số lần)".
- Không có cột dame offline riêng (user chốt) — chỉ hiện trong Chi tiết.

## Code
- `bot/legion_damage.py`: parse gói, tính tuần, ghi/đọc cache, dựng dữ liệu cho UI.
- `bot/client.py`: handler `0x27` sub `02`/`74` → `legion_damage` (chỉ khi acc có tick).
- `run_party_digioi.py`: `apply_legion_dmg(username, on)`, `legion_dmg_info(username)`.
- GUI PC: nút + dialog. APK: `Account.legionDmg`, `PartyStore`, `BotForegroundService`, dialog.
