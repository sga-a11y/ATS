# Pet Rời chức (hết trung thành) — PC + APK

User chốt 27/09/2026.

## Vấn đề
Pet hết trung thành bị game chuyển sang trạng thái **"Rời chức"** và không xuất chiến được. Bot vẫn
gán con đó cho một vai (train/boss/quest/pb_don), nên cứ cố đổi sang nó và server từ chối mãi
(log: `doi pet sang 0xa058 KHONG duoc xac nhan ... trung thanh=21`).

Đã kiểm tra thêm: mode **Dị giới** vẫn đổi pet giống mode train, tức nhịp acc gọi
`ensure_pet_role("train")` và có `_doi_pet_sau_tran`. Đếm trên `party.log` 27/09 được 34.831 lần
đổi thành công trong DG, nên phần đó không cần sửa.

## Hành vi
- Server báo Rời chức qua gói `S:019-007 <<[followIndex][isRetire]>>` (xem KNOWLEDGE.md mục 7i).
- Pet đã Rời chức thì bot **không gửi lệnh đổi sang con đó nữa** trong phiên login này và giữ
  pet hiện tại.
- **Login lại thì tính lại từ đầu**, vì cờ nằm trên client của phiên.
- Màn **⚠ Chú ý** của party (PC + APK) có thêm dòng:
  **"acc xxx pet yyy đã bị Rời chức ko xuất chiến được"**, kèm nút "Bỏ qua" (chỉ bỏ qua trong
  phiên login này). Loại này được xếp vào nhóm "cần làm ngay", nút Chú ý chuyển sang màu cam.

## Code
| Chỗ | Việc |
|---|---|
| `bot/client.py` `_on_pet_retire` / `pets_roi_chuc` | Parse gói, lưu theo marker (gói có thể tới trước `0x0f`) |
| `bot/client.py` `switch_pet` | Pet Rời chức thì `return False`, không gửi lệnh |
| `run_party_digioi.py` `pet_roi_chuc_notify_items` / `_skip` | Nguồn cho màn Chú ý |
| `gui.py` `_party_notify_items` / `_add_row` | Hiện trên PC |
| `BotForegroundService.kt` / `MainActivity.kt` | Hiện trên APK |
| `tests/test_pet_roi_chuc.py` | Giữ hành vi |

## Tự tăng trung thành pet (thêm 30/09)
Phòng từ gốc: không để pet tụt tới mức Rời chức.

- Setting party **"Tự tăng trung thành pet khi trung thành <40"** (Cài đặt nâng cao, dưới "Tự mua
  shop"), key `auto_pet_faith`, **mặc định BẬT**. Có trên cả PC và APK.
- **Chỉ chạy lúc login**, ngay sau `use_login_items()`. Áp cho **tất cả pet mang theo** (ô 1..4).
- Pet trung thành **< 40** → dùng **Thiên Lý Mã `0xbf6b` (+3)** trước, hết thì **Danh Mã `0xbf69` (+1)**,
  cho tới khi **> 40** (41). Pet **đúng 40 thì không dùng**. Không đụng tới item nào khác.
- **Target = marker (ô) của chính pet đó**, đọc cùng bản ghi `0x0f` với pet_id + trung thành
  (`_pet_marker_pid`), giống cách hồi pet. Không bao giờ hardcode ô 1.
- Số trung thành sau khi dùng là bot **tự cộng** (+3/+1 mỗi cái): chưa biết server có gửi lại số mới
  không, cần đối chiếu log `Trung thanh: pet o N (id ...) X -> Y` khi chạy thật.

| Chỗ | Việc |
|---|---|
| `bot/client.py` `tang_trung_thanh_pet` | Tính số item, `use_slot(slot, target=marker, qty=n)` |
| `run_party_digioi.py` `lam_login_chores` / `setup_party_runtime(auto_pet_faith=)` | Gọi lúc login / nhận setting APK (tham số CUỐI) |
| `gui.py`, `bot/config.py` (+ bản APK) | Ô tick + key `auto_pet_faith` |
| `Party.kt` / `PartyStore.kt` / `MainActivity.kt` / `BotForegroundService.kt` | Ô tick APK |
| `tests/test_tang_trung_thanh_pet.py` | Giữ hành vi (đúng ô, thứ tự +3/+1, ngưỡng 40) |
