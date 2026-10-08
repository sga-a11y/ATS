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
