# TS Online Bot — Release Notes

## v1.0.0 (2026-06-18)

Bản product chính thức đầu tiên (đóng gói `.exe`, không cần cài Python).

### Tính năng chính
- **Quản lý nhiều party / tối đa ~100 acc** qua GUI (Tkinter), mỗi party 1 chế độ riêng.
- **11 server**: Triệu Vân, Tào Tháo, Lữ Bố, Lưu Bị, Tôn Quyền, Trương Phi, Chu Du, Quan Vũ, Điêu Thuyền, Gia Cát Lượng, Đại Kiều.
- **Chế độ:** Train map • Train Dị Giới • Tập trung về thành • Đứng yên.
- **Tự động:** lập party + mời + đồng bộ kênh, đánh daily dungeon, vận tiêu, nhận quà online, nhận mail/quà sự kiện/exp offline, nhập giftcode.
- **Tìm đường thông minh:** route từ thành tới bãi train (kéo cả party qua cổng), replay đường đi tới điểm quái xa (mob_paths).
- **Tự phục hồi:** kẹt bãi → relogin resync vị trí; có acc chết/văng map → cả party về thành lập lại; hết giờ DG → tự đánh dungeon.

### GUI
- Bấm header **Kênh** → đổi kênh cả party; header **Map** → teleport thành (rồi tiếp tục chạy như setting).
- Bấm header **Tài khoản / Nhân vật** → che 3 mức (full / `s***01` / `*****`) tránh lộ khi share màn hình.
- Chấm trạng thái party: 🟢 đủ acc / 🟡 chạy một phần / ⚫ tắt. Giữ thông tin tên+level char/pet khi tắt party.
- Cột Nhân vật hiện `tên_lvchar_tênPet_lvPet` (pet đang dùng, level đúng).

### Bảo vệ code (bản gửi đi)
- **Nuitka** biên dịch native C → không decompile lại được mã nguồn Python.
- **Anti-debug guard:** phát hiện debugger → tự thoát (người dùng thường không ảnh hưởng).
- **Không nhúng tài khoản:** ship `accounts.json` mẫu (acc1/pass1, acc2/pass2, acc3/pass3) — người nhận tự sửa.
- File JSON config để cạnh `.exe`, sửa được.

### Cách dùng (người nhận)
1. Chạy `aTSBot.exe`.
2. Bấm **Cấu hình** → nhập tài khoản + chọn chế độ từng party → Lưu.
3. **START**.
