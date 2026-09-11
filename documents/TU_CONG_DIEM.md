# Tự cộng điểm tiềm năng cho nhân vật

Bot tự tiêu điểm tiềm năng theo một **bảng rule của từng acc**, duyệt **từ trên xuống**.

Cấu hình: `config.ACCOUNT_POINT[username]` — `{"reserve": N, "rules": [{"stat": ..., "target": ...}]}`
Mã hàm: `auto_cong_diem()` trong `run_party_digioi.py`; gửi gói `C:008-001` qua `Client.add_attr_point()`.

## Luật

**Dòng đầu cố định: `Point để dành: N`** — luôn giữ lại N điểm, chỉ tiêu phần vượt quá N.

**Các dòng sau là mục tiêu của từng chỉ số**, duyệt từ trên xuống: dòng nào chỉ số **gốc** chưa đạt
thì cộng cho đủ rồi mới xuống dòng tiếp; đạt rồi thì bỏ qua.

**Chốt theo ĐIỂM GỐC** (`char_diem_goc`), không phải tổng có trang bị — cộng điểm làm tăng điểm gốc,
còn tổng thì thay đổi theo đồ đang đeo; chốt theo tổng sẽ làm bot dồn điểm theo bộ đồ.

**Duyệt hết bảng mà vẫn dư hơn số để dành** → báo cho user ở màn "Chú ý", không tự tiêu.

### Dòng AGI bỏ qua số để dành (user chốt 11/09)

Khi tính **đến lượt** dòng AGI thì **bỏ qua** số điểm để dành — nhưng vẫn phải hoàn thành mọi dòng
phía trên trước.

Lý do: "để dành" tồn tại để **giữ điểm cho các dòng phía sau chưa tới lượt**. AGI là dòng quyết định
lượt đánh và nó nằm cuối bảng, nên khi đã tới lượt nó thì không còn dòng nào phải giữ cho nữa — giữ
tiếp là giữ mãi mãi.

Ví dụ user đưa ra: **để dành 33 · hpx 22 · int 55 · agi 44**

| Tình trạng | Bot làm gì |
|---|---|
| `int` mới 50, còn đủ 7 điểm vượt | cộng 5 vào `int` cho đủ 55, rồi tới lượt AGI → tiêu cả 33 |
| `int` mới 50, chỉ còn 2 điểm vượt | cộng 2 vào `int` rồi **dừng** — vẫn giữ nguyên 33 |
| `int` đã đủ 55 | tới lượt AGI ngay → nâng AGI tới 44, không quan tâm số để dành |
| `hpx` chưa đủ 22 | dừng ở `hpx`, **không** được nhảy xuống AGI để mượn khoá |
| `agi` đã đủ 44 | không tiêu gì, giữ nguyên số để dành |

Bảng **không có dòng AGI** → không ai mở khoá được, để dành giữ nguyên như cũ.

Test khoá: `tests/test_diem_de_danh_bo_qua_o_dong_agi.py` (chạy thật hàm, không đọc chữ).
