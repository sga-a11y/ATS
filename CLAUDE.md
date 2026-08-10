# Hướng dẫn cho Claude khi làm bot TS Online (repo này)

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

### Build ở máy khác (vd máy công ty)
`python build_product.py` là ĐỦ — clone mới có sẵn mọi file dữ liệu cần thiết. Hai thứ PHẢI chép
tay vì không nằm trong git:
- **`certs/`** (`atsbot-release.jks` + `.properties`) — thiếu thì build APK dừng kèm thông báo rõ.
  Không có key cố định thì APK mới KHÔNG cài đè được lên bản cũ.
- **`gamedata_*.dat`** — CHỈ cần khi chạy lại `tools/crack_*.py` để sinh JSON. Build KHÔNG cần
  (các JSON đã commit sẵn).

### Bốn cổng chặn tự động — build sẽ DỪNG, không ra bản thiếu
`build_bundle()` và `build_apk()` đều gọi `tools/sync_apk_python.py` trước; `run()` `sys.exit(1)`
khi lệnh con lỗi. Nên các lỗi dưới đây KHÔNG thể lọt ra bản build:
| Thông báo | Nghĩa là | Cách sửa |
|---|---|---|
| `file trong bot/ chua khai bao` | Thêm file `.py` mới mà quên khai báo | Thêm vào `SHARED` (dùng chung) hoặc `PC_ONLY` |
| `copy xong van LECH` | Chép hỏng / bị ghi đè ngược | Chạy lại sync |
| `ban APK con import tuyet doi 'bot.*'` | Trên Android không có package `bot` | Sync tự đổi bằng regex; lỗi này = regex chưa phủ dạng import mới |
| `asset APK chua khai bao trong SHARED_ASSETS` | File assets chỉ được chép tay | Thêm vào `SHARED_ASSETS` |

**Bài học đắt**: `SHARED`/`SHARED_ASSETS` từng là allowlist chép tay nên thiếu mà KHÔNG AI BÁO —
`party_battle.py` lệch 48 dòng và 14 file assets chỉ cập nhật tay. Build vẫn chạy, chỉ khác HÀNH VI.
Thêm file dùng chung mà không khai báo = bản APK chạy code cũ âm thầm.

### APK: cập nhật core phải DỪNG HẾT party trước
Dọn `sys.modules` chỉ chạy khi không acc nào đang chạy. Update core lúc đang chạy → vẫn chạy code
cũ, log sẽ báo `CORE MOI v... nhung dang co acc CHAY -> VAN chay code cu v...`. Dấu hiệu core đã
nạp đúng: `CORE LOAD: core=v<version> client=/data/.../bot_bundle/current/android/train_bot/client.py`.
