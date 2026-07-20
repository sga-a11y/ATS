# Hướng dẫn cho Codex khi làm bot TS Online (repo này)

## TRƯỚC khi reverse-engineer / mò cấu trúc packet → ĐỌC `KNOWLEDGE.md`
Nhiều gói đã được ghi chú sẵn (opcode, offset, stat code) trong `KNOWLEDGE.md`. **Bắt buộc grep/đọc
`KNOWLEDGE.md` (bảng opcode + mục "STATS PACKETS" + "BATTLE FLOW") TRƯỚC** khi thêm debug log hay đoán
cấu trúc gói. Sau khi xác nhận điều mới → cập nhật lại `KNOWLEDGE.md`.

> Bài học: từng tốn rất nhiều vòng mò nguồn pet maxSP (qua 0x08/0x33/share) trong khi `KNOWLEDGE.md`
> đã note `0x0b = Full stats có SP_max` ngay từ đầu.

### Nguồn stat trong battle (hay nhầm — nhớ kỹ)
- **`0x0b` party-broadcast (>100B, lúc spawn)** = full-stat MỌI member: block
  `[b1][slot][HPmax 4B][SPmax 4B][HPcur 4B][SPcur 4B]` (b1=3 char / 2 pet). **NGUỒN DUY NHẤT có pet
  maxSP**, kể cả nick người chơi tay. `allies` bị `clear()` mỗi `0x34` → maxSP phải lưu bền ở
  `state.ally_spmax`.
- **`0x33`** = stat per-turn: chỉ HP_cur/SP_cur/HP_max (0xcd). **KHÔNG có SP_max.**
- **`0x08`** = stat theo entity: chỉ CHAR (unit 01). **Không mang pet.**

## Mốc kết trận = `0x14 sub0700` (KHÔNG dùng idle/`0x34`)
`0x34` bắn thất thường (1 lần/nhiều trận). `in_combat()` / `quest_mode` / reset phải bám
`state.in_battle` (set mỗi lượt `0x35` + `0x34`, HẠ ở `0x14 sub0700` END thật). Đừng ép hết-trận theo
idle ngắn → nghỉ giữa lượt quest có thể >13s → hồi item/vào gate giữa trận.

## Lưu ý build (xem thêm KNOWLEDGE.md mục 0)
User chạy BẢN BUILD (exe) từ `config.example.py`, KHÔNG phải `config.py` (dev, gitignored). Đổi key
config phải sửa đồng thời `config.example.py`. `config.py` chứa mật khẩu thật → KHÔNG BAO GIỜ commit.
