# Áp chế độ cho mọi party (đổi 1 phát)

User yêu cầu 02/10/2026: đổi chế độ cho cả loạt party mà không phải sửa tay từng cái.

## Cách dùng
- **PC**: Settings → mở 1 party mẫu → chỉnh Chế độ → bấm **⇉ Áp chế độ cho mọi party** (hàng
  Game/Server) → xác nhận → **💾 Lưu**.
- **APK**: Sửa party → ngay dưới ô "Chế độ chạy" bấm **⇉ Áp chế độ cho mọi party VTC/TSM** →
  bấm Đổi. APK ghi luôn vào `parties.json` (giống nút "Áp dụng cho tất cả" của cài đặt nâng cao).

## Luật (user chốt)
1. **Chỉ áp cho party CÙNG nhà phát hành** (VTC/TSM) với party mẫu.
2. **Dị Giới / Train**: CHỈ đổi chế độ. **Cấp quái DG** và **map train** giữ riêng từng party.
   - Party chưa có map train (vd đang DG thuần) mà chuyển sang Train/DG+Train → mượn map (cả
     min/max quái, hệ, linh hồn) của party mẫu, để không lấy `start_city_id` rác làm map train.
   - Chuyển sang DG thuần → `start_city_id = 49942`. Kiểu chạy Party/Solo giữ riêng.
3. **Event**: đồng bộ về **cùng event** (+ tick "Chỉ đánh 1 trận") của party mẫu.
4. **Tập trung về thành**: party đang ở mode thành thì giữ thành riêng; party từ mode khác chuyển
   sang thì lấy thành của party mẫu.
5. Không đụng server, acc, cài đặt nâng cao, hồi máu, lò.

## Code
- PC: `gui._doi_che_do_preset` (hàm thuần), `SettingsDialog._apply_mode_to_all`, nút trong
  `PartyConfigFrame.__init__`. Test: `tests/test_ap_che_do_moi_party.py`.
- APK: `Party.copyModeFrom` (Party.kt), `PartyStore.applyModeToSameGameParties`,
  nút + AlertDialog trong `AddPartyDialog` (MainActivity.kt).

## Khác biệt nhỏ PC / APK
APK lưu map train ở trường riêng (`trainMapKey`/`trainPick`) nên map vẫn còn kể cả khi party đang
ở DG thuần → DG→Train trên APK giữ được map cũ. PC thì khi lưu mode DG, map train bị ghi đè
(`start_city_id=49942`), nên DG→Train trên PC sẽ mượn map party mẫu.
