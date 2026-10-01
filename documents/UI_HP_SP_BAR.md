# Thanh HP/SP Char + Pet (PC + APK)

User chốt 01/10/2026: hiển thị thanh HP/SP của char và pet giống bản APK.

## Dữ liệu
- `account_status()` (run_party_digioi.py, PC và APK giống hệt nhau) trả về:
  `hp, sp, hp_max, sp_max` (từ `c.state.char`) và `pet_hp, pet_sp, pet_hp_max, pet_sp_max` (từ `c.state.pet`).
- Nguồn: gói 0x0b (max + cur) và 0x33 (cur theo từng lượt). Ngoài trận thì giữ số cuối cùng.
  Chưa có số liệu → không vẽ thanh.

## PC (gui.py)
- Cột `hpsp` nằm **ngay bên phải cột Nhân vật** (user chốt 01/10). Treeview không gắn được ảnh riêng cho
  từng cột, nên mỗi dòng có 1 `tk.Canvas` đặt đè lên ô (`tree.bbox(u, "hpsp")`). Vị trí được đặt lại
  mỗi lần refresh, cũng như khi `<Configure>`, kéo cột, hoặc `<Map>`.
- Nửa trái là Char, nửa phải là Pet. Mỗi nửa có 2 dòng: HP (xanh lá #22c55e) và SP (xanh dương #3b82f6),
  mỗi dòng gồm thanh + chữ `cur/max`. Dưới 20% → cam #f59e0b. Chỉ vẽ lại khi số liệu/kích thước đổi.
- Click/double-click lên Canvas = chọn dòng / start acc (giống click vào bảng).
- Style riêng `Party.Treeview` với rowheight=28. Trạng thái 90→70, Map 130→160 (tên map dài), DG còn 70→55.

## APK (MainActivity.kt)
- Card acc: HP, SP (char) rồi P.HP, P.SP (pet) bằng `StatBar`. Dưới 20% → `StatLowColor` (cam).
