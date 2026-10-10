# Tự chọn map train

Code: `bot/train_pick.py` (APK: `android/.../train_bot/train_pick.py` — giống hệt).

## Bảng "Hệ quái muốn đánh" (nút `⬦ Hệ`)
- 8 tick hệ (7 hệ + Vô hệ). Tick hết hoặc không tick gì = đánh tất cả các hệ.
- **Quái linh hồn** (thêm 01/10/2026), mặc định KHÔNG tick:
  - Không tick → bot chỉ chọn map thường, bỏ qua map `LH-...` (như cũ).
  - Có tick → bot CHỈ chọn map `LH-...`, bỏ qua map thường. Các luật khác giữ nguyên
    (hạ level tối đa -5, ưu tiên map chưa quét, lọc số quái/hệ, map thấp nhất).
  - Nút hiện thêm chữ `LH` khi đang tick.
- Map LH phải có level ở cuối tên (vd `LH-Xxx 150-155`) thì bot mới tính được.
- Chọn map TAY thì không bị bộ lọc này ảnh hưởng.

## Đứng yên ở safe
Chọn map TAY mới có mục `🛡 Đứng yên ở safe (chèn kênh)`; tự chọn map thì không bao giờ đứng yên.
Chi tiết: `documents/DUNG_SAFE_CHEN_KENH.md`.

## Lưu cấu hình
- Key `mob_soul` (bool) trong preset party (accounts.json / PartyStore APK).
- APK truyền `party.mobSoul` vào `setup_party_runtime` ở vị trí CUỐI CÙNG.

## Thêm map đang đứng vào Map train (chỉ bản dev, 10/10/2026)
- Thay cho log `MAP HIEN TAI` cũ (mất từ commit `90bfb10` 26/09 khi bỏ engine cũ).
- Bảng party → bấm header **Map ↧** → popup "Teleport về thành" → nút
  **📍 Thêm map đang đứng vào Map train**. Chỉ hiện khi chạy `python gui.py`
  (`updater.is_frozen()` = False); bản exe không có nút này. APK không làm.
- Lấy `current_map` của leader (không có thì acc đang chạy đầu tiên của party).
- Thành → báo không train được. Đã có → báo đã có. Còn lại hỏi xác nhận rồi thêm map **rỗng**
  (tên theo game, nhóm "Chưa phân nhóm") qua `train_maps_store.add_empty_map` — không bao giờ
  ghi đè map đã có. Lần đầu party tới map đó bot tự AUTO LEARN bãi quái/safe.
