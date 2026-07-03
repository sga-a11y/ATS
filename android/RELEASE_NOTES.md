# aTSBot Android - Release Notes

## v0.1 (2026-07-03) - Bản đầu tiên

Bản Android đầu tiên (APK debug), chạy song song nhiều tài khoản train ngay trên điện thoại/máy ảo,
không cần bật máy tính.

### Tính năng chính
- **Quản lý theo Party**: tạo nhiều Party, mỗi Party chọn 1 server riêng, thêm/sửa/xoá account
  (chỉ cần Tài khoản/Mật khẩu, server đã chọn sẵn ở cấp Party).
- **Start/Stop từng account** hoặc **Start party/Stop party** (bật/tắt cả party 1 lúc).
- **Chế độ chạy - "Đứng yên tại thành"**: chọn 1 trong 16 thành (Trác Quận, Lạc Dương, Trường An...),
  bot tự đăng nhập, tự về đúng thành đã chọn rồi đứng yên treo cây tại đó - không tự đi lung tung nên
  không lo đi xuyên tường/kẹt map lạ (bản đầu chưa có dữ liệu đường đi an toàn theo từng khu).
- **Tự nhận lời mời vào Party từ người thật**: nếu acc đang chạy nhận được lời mời party ngoài
  (không phải tự bot lập party), sẽ tự động đồng ý gia nhập - dùng được để ghép chung acc bot vào
  Party do người chơi thật cầm đầu (kể cả phó bản tổ đội).
- Chạy nền qua Foreground Service - tắt màn hình/chuyển app khác vẫn treo cây bình thường.

### Chưa có (để dành bản sau)
- Bubble nổi (chat-head) điều khiển nhanh không cần mở app.
- Tự động di chuyển/đi lang thang theo bản đồ (hiện chỉ đứng yên tại thành).
- Mode Dị Giới, tự lập phó bản tổ đội (hiện chỉ tự NHẬN lời mời có sẵn, không tự tạo).
- Boss mode thủ công (để làm chung lúc port tính năng đánh boss/dungeon thật).

### Đã sửa (trong quá trình test)
- Bug nghiêm trọng: đọc file dữ liệu (skill, pet, danh sách thành) lỗi trên Android cũ hơn bản 13,
  khiến danh sách skill/thành bị rỗng âm thầm mà không báo lỗi.
- Bug quest_mode (chế độ đánh khi gặp nhiều quái) không được reset đúng lúc giữa các trận, khiến bot
  bị kẹt ở chế độ Train (đòn thường/combo) dù gặp trận đông quái, không dùng skill diện rộng dù đã học.
- Bug quest_mode không được bật khi acc tự nhận lời mời phó bản (trường hợp không có acc-leader điều
  phối) - đã đồng bộ lại giống hành vi của acc-leader.
