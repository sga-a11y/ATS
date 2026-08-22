# VẬN TIÊU (escort / dispatch) — thiết kế

## Mục đích
Gửi pet đi vận tiêu (~4h) rồi nhận quà. Opcode `0x56`. Số lượt/ngày do server báo
(`RoleCount id=8`), số slot đã mở do server báo (`S:056-006`).

## Vì sao cho user chọn PET (2026-08-22)
Vận tiêu **có EXP**. Trước đây bot dùng **tất cả** pet trong nhà trọ, cứ trùng hệ/doanh là gửi →
EXP rải đều. User muốn **dồn EXP cho vài con** nên cần chọn riêng.

## Vị trí cài đặt
| | Trước | Sau |
|---|---|---|
| Bật/tắt vận tiêu | Cài đặt nâng cao (1 ô tick **CHUNG cả party**) | Bảng setting **Hồi HP/SP của TỪNG ACC** |
| Chọn pet | không có | nút **📋 List** cạnh ô tick, mỗi pet nhà trọ 1 ô |

Ô ở Cài đặt nâng cao đã **bỏ hẳn** (cả PC lẫn APK) để không có 2 nơi điều khiển cùng một thứ.

Nút **"Áp dụng cho TẤT CẢ acc"** chỉ đồng bộ **ô tick vận tiêu**, **KHÔNG** đồng bộ list pet — pet
nhà trọ mỗi acc một khác (pet id khác hẳn nhau) nên áp list của acc này sang acc khác là vô nghĩa.

## Luật chọn pet (`GameClient.vantieu_candidates`)
| Tình huống | Bot làm gì |
|---|---|
| Acc không có pet trong nhà trọ | bỏ qua, ghi log |
| **Không tick con nào** (mặc định) | dùng **TẤT CẢ** — y hệt hành vi cũ |
| **Tick hết** | dùng **TẤT CẢ** — như trên |
| Tick lẻ | **chỉ** những con được tick; chấm điểm hệ/doanh trong phạm vi đó |
| Tick lẻ, không con nào hợp hệ/doanh | lấy **con đầu** trong list đã tick (score 0) |
| Mọi con đã tick đều đang vận tiêu | **CHỜ** xong mới gửi tiếp, không gửi con ngoài list |
| Tick pet đã bán / lấy khỏi nhà trọ | coi như không tick → dùng tất cả (không để bot đứng hình) |

Mặc định "bật vận tiêu + không tick con nào" ⇒ **tương thích ngược tuyệt đối**: user đang chạy bot
không thấy gì khác.

## Tick lưu theo PET ID, không theo index nhà trọ
Index nhà trọ (`1..30`) **xê dịch khi thêm/bớt pet** → tick theo index sẽ trượt sang con khác.
Pet ID lấy từ gói roster, mỗi acc chỉ có 1 con cùng ID.

Cấu trúc bản ghi `S:031-006` xem `KNOWLEDGE.md` (đã bóc từ `vt_kholog.pcap`, đối chiếu
`npc_names.json` khớp 4/4).

## Cache để chỉnh khi acc offline
Roster nhà trọ chỉ được server gửi **lúc login**. Để user tick pet khi acc đang tắt, bot ghi list
vào `account_skills_cache.json` khoá `inn` (dùng chung file có sẵn thay vì thêm file mới).

- `save_inn_cache(username, [[pet_id, tên], ...])` — gọi ngay khi nhận roster.
- `save_skill_cache` **giữ nguyên** khoá `inn` (hàm này thay cả entry, không giữ thì mỗi lần cache
  skill sẽ xoá mất list pet).
- API đọc: `account_inn_pets(username)` — acc chạy thì LIVE, acc tắt thì cache.

## Đường truyền cấu hình
Đi **chung `heal_json`** (cùng một dialog) thay vì thêm tham số vị trí mới cho
`setup_party_runtime` — Kotlin gọi hàm đó **theo vị trí**, chèn tham số giữa chừng là vỡ.

```
GUI/APK  ──heal_json {..., "vantieu": {"on": bool, "pets": [id...]}}──>  apply_account_heal()
         → config.ACCOUNT_VANTIEU[user] → c.vantieu_enable / c.vantieu_pick_ids
```
PC còn nạp thẳng từ `accounts.json` (field `vantieu` mỗi acc) lúc import `bot/config.py`.

## Bug đã sửa kèm đợt này
`used` cũ chỉ nhớ pet gửi **trong lần chạy này**, không nhớ pet **đang chạy ở slot từ trước** → gửi
lại chính con đó. Trước ít lộ vì roster nhiều con; nhưng "mở 2-3 slot mà chỉ tick 1 pet" thì sai
chắc chắn. Nay loại luôn các `vantieu_slots[slot]["pet"]` (innIndex server đang cho chạy).

## Còn nợ
`S:031-003` (gửi pet vào nhà trọ) và `S:031-004` (lấy pet ra) **chưa xử lý** — bắt được 2 gói này
thì cập nhật roster lúc đang chạy mà không cần login lại. Hiện roster chỉ tươi sau mỗi lần login.
