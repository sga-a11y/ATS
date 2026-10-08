# Áp chế độ cho mọi party (đổi 1 phát)

User yêu cầu 02/10/2026: đổi chế độ cho cả loạt party mà không phải sửa tay từng cái.

## Cách dùng
- **PC**: Settings → mở 1 party mẫu → chỉnh Chế độ → bấm **⇉ Áp chế độ cho mọi party** (hàng
  Game/Server) → xác nhận → **💾 Lưu**.
- **APK**: Sửa party → ngay dưới ô "Chế độ chạy" bấm **⇉ Áp chế độ cho mọi party VTC/TSM** →
  bấm Đổi. APK ghi luôn vào `parties.json` (giống nút "Áp dụng cho tất cả" của cài đặt nâng cao).

## Luật (user chốt)
1. **Chỉ áp cho party CÙNG nhà phát hành** (VTC/TSM) với party mẫu.
2. **Dị Giới / Train**: CHỈ đổi chế độ. **Cấp quái DG**, **map train**, **số quái min/max**,
   **hệ quái**, **linh hồn** giữ riêng từng party — không bao giờ chép từ party mẫu.
   - Map train lưu bền ở `train_last` (`{pick, sc, mob_index}`), giữ nguyên qua mọi mode — nên
     Event → DG+Train lấy lại đúng map cũ của party đó.
   - CHỈ party **chưa từng có** map train (không có `train_last`, không đang ở mode train) mới
     mượn **map** của party mẫu, để không lấy `start_city_id` rác (49942) làm map train.
   - Ca hỏng 07/10 (bản đầu): PC lưu map chung ở `start_city_id`/`train_pick` nên sang Event là mất;
     57 party Event → DG+Train thành cùng map `avg-25` + cùng min/max `2–6` của party mẫu.
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
APK lưu map train ở trường riêng (`trainMapKey`/`trainPick`) nên vốn không mất khi đổi mode.
PC từ 07/10 lưu thêm `train_last` để đạt cùng hành vi. Party PC lưu trước 07/10 ở mode khác train
thì chưa có `train_last` → lần đầu vẫn mượn map party mẫu (map cũ đã mất từ trước, không cứu được).
