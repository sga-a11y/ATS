# Gacha pet / gacha thẻ hằng ngày

## Khi nào chạy (user chốt 03/10/2026)
- Chạy trong **việc vặt lúc login** (`lam_login_chores`), **ngay trước vận tiêu** (`do_van_tieu`).
- **Không** còn dựa vào ô bingo 6 (pet) / ô 4 (thẻ). `claim_daily_quests` không gọi gacha nữa,
  chỉ nhận thưởng hàng/cột khi server báo ô đã xong.
- Không phụ thuộc checkbox "Đánh daily dungeon" của party.

## Điều kiện quay (mỗi banner)
1. Check shop: bộ đếm server `RoleCount` (S2C `0x55`) — pet `sid 0x11`, thẻ `sid 0x12`.
   `value >= max` → đã quay hôm nay → bỏ qua. Chưa có sid → coi như chưa quay (giống client).
2. Đủ xu (≥ 9000 / lượt). Thiếu xu → bỏ qua, lần login sau thử lại.
3. Thứ tự: pet trước, thẻ sau. Sau khi quay bot tự đánh dấu counter = 1/1 (server `0x55` sẽ ghi đè).

## Code
- `bot/client.py`: `GACHA_RC_PET` / `GACHA_RC_CARD`, `_gacha_da_mua`, `claim_gacha_pet`, `claim_gacha_card`.
- `run_party_digioi.py`: `lam_login_chores`, ngay trước `next_vantieu = c.do_van_tieu()`.
- Bản APK giống hệt (`android/app/src/main/python/train_bot/`).
- Packet: `KNOWLEDGE.md` mục "GACHA PET / CARD".
