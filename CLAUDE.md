# Hướng dẫn cho Claude khi làm bot TS Online (repo này)

## TRƯỚC khi reverse-engineer / mò cấu trúc packet → ĐỌC `KNOWLEDGE.md`
Nhiều gói đã được ghi chú sẵn (opcode, offset, stat code) trong `KNOWLEDGE.md`. **Bắt buộc grep/đọc
`KNOWLEDGE.md` (bảng opcode + mục "STATS PACKETS" + "BATTLE FLOW") TRƯỚC** khi thêm debug log hay đoán
cấu trúc gói. Sau khi xác nhận điều mới → cập nhật lại `KNOWLEDGE.md`.

> Bài học: từng tốn rất nhiều vòng mò nguồn pet maxSP (qua 0x08/0x33/share) trong khi `KNOWLEDGE.md`
> đã note `0x0b = Full stats có SP_max` ngay từ đầu.

### ⚠️ BẪY: viết file bằng heredoc làm HỎNG `KNOWLEDGE.md` → grep im lặng bỏ qua cả file
Ghi file qua `python - <<'PY'` thì dãy escape trong chuỗi Python **bị nuốt một tầng**:
`\0` → **byte NUL 0x00 thật**, `\b` → **backspace 0x08**, `\n` → **xuống dòng thật**.

Đã xảy ra thật (2026-08-22): ghi mục vận tiêu vào `KNOWLEDGE.md`, `\0` thành 3 byte NUL →
**`grep` coi cả file là nhị phân và bỏ qua TOÀN BỘ, không báo lỗi gì**. Hệ quả: tra
"thú cưỡi" ra rỗng nên kết luận nhầm là `KNOWLEDGE.md` không có mục đó, trong khi nó **có**
(mục `Horse/Mount login`, `0x4f sub0100`). Tức bẫy này không chỉ hỏng 1 dòng — nó **vô hiệu hoá
chính file kiến thức mà mục trên bắt phải đọc trước**.

Cách làm đúng:
- Ưu tiên **Write/Edit tool** cho nội dung có dấu `\`; heredoc chỉ dùng cho thao tác đơn giản.
- Bắt buộc dùng heredoc → viết `chr(92) + "0"` thay vì `\0`.
- Ghi xong file text thì **kiểm ngay**: `python -c "print(b'\x00' in open('F','rb').read())"`
  (hoặc `grep -c "" F` — ra `Binary file ... matches` là hỏng).

### ⚠️ BẪY: `_load_gamedata_items()` CHÉP TAY từng trường — thiếu trường là hỏng ÂM THẦM
Loader không đọc thẳng JSON mà dựng dict mới với một danh sách trường viết tay. Trường nào quên
khai báo thì `rec.get("x")` trả `None` → `0`, **không lỗi, không log**. Đã cắn **hai lần trong
cùng ngày 2026-09-04**:
- thiếu `fc/mat/lv/kd` → tự mở rương coi MỌI món là "không phân giải, không donate được" và
  **vứt sạch** hàng trăm trang bị;
- thiếu `st` → túi đồ/tiền trang bản APK sắp xếp với `st` toàn 999, tức sai hẳn thứ tự game.

Thêm trường mới vào `items_gamedata.json` thì **phải khai báo trong loader**, và
`tests/test_gamedata_loader_giu_du_truong.py` giữ danh sách trường bắt buộc — cập nhật cả nó.

### Nguồn stat trong battle (hay nhầm — nhớ kỹ)
- **`0x0b` party-broadcast (>100B, lúc spawn)** = full-stat MỌI member: block
  `[b1][slot][HPmax 4B][SPmax 4B][HPcur 4B][SPcur 4B]` (b1=3 char / 2 pet). **NGUỒN DUY NHẤT có pet
  maxSP**, kể cả nick người chơi tay. `allies` bị `clear()` mỗi `0x34` → maxSP phải lưu bền ở
  `state.ally_spmax`.
- **`0x33`** = stat per-turn: chỉ HP_cur/SP_cur/HP_max (0xcd). **KHÔNG có SP_max.**
- **`0x08`** = stat theo entity: chỉ CHAR (unit 01). **Không mang pet.**

## Mốc kết trận (bot dùng) = `0x14 sub0700` (KHÔNG dùng idle/`0x34`)
> **Lưu ý tên gọi (sửa 19/08/2026):** trong client `S:020-007` là **`<事件換場景>`** (event đổi
> scene), KHÔNG phải "kết trận". Kết trận thật là **`S:011-000 <結束戰鬥>`** ->
> `FightManager.FightOver` (đặt `war = None`). Mốc `0x14 sub0700` vẫn dùng được vì thực nghiệm
> nó tới đúng lúc hết trận, nhưng đừng tưởng đó là gói kết trận của game.
> **Hết trận client KHÔNG gửi gói nào** — đã đọc cả `FightOver` lẫn `FightField.ExitFight`:
> không có `Network.Send`. Trận là lớp phủ cùng scene (`fightRoot:SetActive(false)`), không đổi
> scene nên cũng không có `C:012-001 <換場景完畢>`. Đừng đi tìm "gói ready sau trận", không có.
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

**Build xong thì máy đó có thư mục `_nk/`** (Nuitka TỰ TẢI bộ biên dịch MinGW về, đã gitignore).
Đừng ngạc nhiên nếu thấy nó chiếm chỗ, và **đừng để test đi bộ vào đó** — thư viện chuẩn Python
bên trong có byte `0x0c` hợp lệ. Đã bỏ qua trong `tests/test_file_text_khong_co_byte_la.py`
(2026-08-24); trước khi bỏ, máy nào build 1 lần là test đỏ 22 file **không phải mã của mình**,
và bộ test chạy 83s thay vì 26s chỉ vì đi bộ qua đó.

### Sửa Kotlin thì PHẢI chạy `python -m unittest discover -s tests`
`gradlew compileReleaseKotlin` chỉ nói code **biên dịch được**, KHÔNG nói nó còn đúng ý. Nhiều test
Python **đọc thẳng `MainActivity.kt`/`BotForegroundService.kt` bằng regex** để giữ hành vi.

Đã xảy ra (2026-08-24): thêm `trainPick` làm `ModeCfg` đổi từ
`party.trainMapKey.toIntOrNull() ?: 0` thành `if (party.trainPick.isEmpty()) ... else 0` →
`test_digioi_train_maps_to_party_mode_with_selected_train_target` đứt. Biên dịch vẫn PASS nên
lọt qua, máy kia pull về mới phát hiện. Bài test giờ neo theo **ý nghĩa** thay vì dạng chữ.

### Sáu cổng chặn tự động — build sẽ DỪNG, không ra bản thiếu
`build_bundle()` và `build_apk()` đều gọi `tools/sync_apk_python.py` trước; `run()` `sys.exit(1)`
khi lệnh con lỗi. Nên các lỗi dưới đây KHÔNG thể lọt ra bản build:
| Thông báo | Nghĩa là | Cách sửa |
|---|---|---|
| `file trong bot/ chua khai bao` | Thêm file `.py` mới mà quên khai báo | Thêm vào `SHARED` (dùng chung) hoặc `PC_ONLY` |
| `copy xong van LECH` | Chép hỏng / bị ghi đè ngược | Chạy lại sync |
| `ban APK con import tuyet doi 'bot.*'` | Trên Android không có package `bot` | Sync tự đổi bằng regex; lỗi này = regex chưa phủ dạng import mới |
| `asset APK chua khai bao trong SHARED_ASSETS` | File assets chỉ được chép tay | Thêm vào `SHARED_ASSETS` |
| `Servers.kt FALLBACK thieu server` | Thêm server vào `servers.json` mà quên `Servers.kt` | Thêm vào `FALLBACK` trong `Servers.kt` |
| `asset APK chua khai bao trong DATA_JSON cua build_product.py` | File có trong `SHARED_ASSETS` (APK có) nhưng bản **exe** không đóng gói | Thêm vào `DATA_JSON` trong `build_product.py` |

**Tái phạm lần 3 (2026-08-24)** — cổng thứ 6 sinh ra từ đây. Thêm `npc_table.json` vào
`SHARED_ASSETS` (APK) nhưng quên `DATA_JSON` (exe) → bản exe không có file → bảng thống kê hiện
`id 17363` thay vì `Thủy lv130`. **Không ai báo** vì vòng copy dùng `if os.path.exists(src)` —
thiếu thì im lặng bỏ qua.

Đối chiếu hai danh sách lòi thêm một lỗi **có sẵn từ lâu**: `mounts_grow.json` cũng thiếu →
**bản exe lâu nay bỏ hẳn tính năng thú cưỡi**, log chỉ ghi `Thu cuoi: thieu mounts_grow.json -> bo qua`.

> Quy tắc: mỗi lần thêm file dữ liệu dùng chung phải khai báo ở **CẢ HAI** nơi —
> `SHARED_ASSETS` (`tools/sync_apk_python.py`, cho APK) và `DATA_JSON` (`build_product.py`, cho exe).
> Giờ quên là build DỪNG, không ra bản thiếu nữa.

**Bài học đắt**: `SHARED`/`SHARED_ASSETS` từng là allowlist chép tay nên thiếu mà KHÔNG AI BÁO —
`party_battle.py` lệch 48 dòng và 14 file assets chỉ cập nhật tay. Build vẫn chạy, chỉ khác HÀNH VI.
Thêm file dùng chung mà không khai báo = bản APK chạy code cũ âm thầm.

**Tái phạm (2026-08-14)**: `Servers.kt` cũng là map chép tay → PC có 17 server, APK chỉ 16
(**thiếu Trương Liêu id 18**) vì thêm server mới chỉ sửa `servers.json`. Đã cho `Servers.kt` đọc
thẳng `assets/train_bot_data/servers.json`; map cũ chỉ còn là FALLBACK khi đọc asset lỗi, và có
cổng chặn bắt FALLBACK phải phủ đủ key.

> **Quy tắc rút ra**: dữ liệu dùng chung PC/APK thì bản Kotlin phải **ĐỌC file JSON**, không được
> chép lại thành hằng số. Chép tay ở đâu là ở đó sẽ lệch, chỉ là sớm hay muộn.

### APK: cập nhật core phải DỪNG HẾT party trước
Dọn `sys.modules` chỉ chạy khi không acc nào đang chạy. Update core lúc đang chạy → vẫn chạy code
cũ, log sẽ báo `CORE MOI v... nhung dang co acc CHAY -> VAN chay code cu v...`. Dấu hiệu core đã
nạp đúng: `CORE LOAD: core=v<version> client=/data/.../bot_bundle/current/android/train_bot/client.py`.
