# Loạn đấu lôi đài (亂鬥擂台) — thiết kế

> Trạng thái: **đã code, đang chạy.** Thứ 3 chạy từ 25/08/2026; thứ 7 thêm 05/09/2026 (mục 2b).

## 1. Định danh trong client

| Thứ | Giá trị | Nguồn |
|---|---|---|
| Activity | `EActivity.ChaosVS = 32` (亂鬥擂台) | `_lua_dec/Data/ActivityInfo.lua:33` |
| Kiểu trận | `EWar.ChaosVS = 15` (玩家戰人亂鬥賽) | `_lua_dec/Logic/FightManager.lua:17` |
| Biến thể | `NewChaosVS = 27` (無界亂鬥賽), `ChaosBouns = 28` (trận thưởng) | cùng file |
| NPC | `15162` = Lôi Đài Phù Sư; còn có "Chủ Lôi Đài" | `protocal.lua:2769` |

Event họ hàng: `DareNpc = 33` (挑戰擂台賽) chính là **event 40 NPC** của bot.

### Bảng triggerID của các cửa lôi đài (`protocal.lua:2759`)

| triggerID | sự kiện |
|---|---|
| 3 | **亂鬥 — loạn đấu** |
| 4 | 團P |
| 5 | 挑戰賽 — **40 NPC** |
| 8 | 比武擂台 |
| 14 | đổi thưởng |

**triggerID = byte option trong dialog.** Đối chiếu 40NPC (KNOWLEDGE mục 7o): mở NPC bằng
`0x20 020008` rồi `0x14 0100 **05** 00`, NPC đổi thưởng là `0x14 0100 **0e** 00` (= 14).
Suy ra loạn đấu là `0x20 020008` → `0x14 0100 **03** 00`. **Chưa verify bằng capture.**

Gói liên quan: `S:020-032` lỗi lôi đài · `S:020-040 <擂台賽活動訊息> +種類(1)` (kind 1/2 =
mở/đóng) · `S:023-111 <亂鬥戒指訊息>` (nhẫn loạn đấu — phần thưởng).

Map tên "Lôi đài đấu trận": `49993-49995`, `54501-54505`, `54901-54905`
(khác `10991/10994` "Lôi đài tỉ võ" của 40NPC).

## 2. Hành vi đã chốt với user

- **Giờ:** **thứ 3 20:00–22:00**, **thứ 5 20:00–22:00**, **thứ 7 20:30–22:30** (mục 2b). Không đâm 40NPC (thứ 2/4/6).
- **Solo:** mỗi acc chạy độc lập. **Không** lập party, **không** `do_channel_sync`, không barrier.
- **Làm tới đâu:** đánh hết lượt rồi đi đổi thưởng, xong thoát.
- **Quest mode:** bật. Không phải code thêm — `run_party_digioi.py:1713` đã có
  `force_quest_mode = (mode == "event")` và không phụ thuộc leader.
- **HP dùng cho xếp thứ tự bảo vệ:** giữ **HP tuyệt đối** (user chốt), không đổi sang %.

## 2b. Thứ 7 là một SẢNH KHÁC — không phải thứ 3 đổi giờ

Nguồn: `captures/loandau_t7_20260905.pcap` (thứ 7 05/09/2026, 20:36, 322s, 2 trận).
Đã ghép luồng TCP theo seq trước khi dò `c0 91` — **0 byte không giải được**.

| | Thứ 3 | Thứ 7 |
|---|---|---|
| khung giờ | 20:00–22:00 | **20:30–22:30** |
| chọn event `0x4d` | `03000300` (id 3) | **`03005a00` (id 90)** |
| map | 10991 "Lôi đài tỉ võ" | **54901** |
| điểm NPC | (910, 290) | **≈ (1630, 430)** |
| option NPC | `0x14 0100 **03** 00` | **`0x14 0100 01 00`** |
| chờ ghép trận | 336.6s / 0.6s | 1.3s |

Map 54901 nằm trong dải `54901-54905` "Lôi đài đấu trận" — mục 1 đã tách rõ dải này khác
`10991` của thứ 3. Nhiều khả năng là biến thể `NewChaosVS = 27` (無界亂鬥賽).

**Chuỗi đăng ký giống hệt về hình** — chỉ khác đúng byte option:

```
C2S 0x20 020008              mở NPC
C2S 0x14 0100 01 00          option 01        <- t3 là 03
S2C 0x14 0100...3930         page 1
C2S 0x14 0600                advance
S2C 0x14 0100...0500         page 2 (t3 kết 0200, t7 kết 0500)
C2S 0x14 09001e              CHỌN CÓ
C2S 0x14 0600  x3            advance
S2C 0x14 0d00
S2C 0x14 08 2a               ĐĂNG KÝ XONG
```

Page 2 kết `0500` thay vì `0200` **không phá `dang_ky()`**: hàm chỉ dùng `is_choice_page` để
quyết có advance một lần hay không, mà page 1 kết `3930` (không phải choice) ở **cả hai ngày**
→ vẫn advance 1 lần rồi `09001e`.

### Thứ 5 — 團P "loạn đấu đội", nhưng vẫn đăng ký SOLO

Nguồn: `captures/loandau_doi_20260903.pcap` + `..._dangky_tran1_20260903.pcap`
(03/09/2026 = thứ 5). **Một luồng TCP, một IP** → cùng server, *không* phải vô giới.

Khác thứ 3 đúng **hai byte**:

| | Thứ 3 | Thứ 5 |
|---|---|---|
| chọn event `0x4d` | `03000300` (id 3) | **`03000200` (id 2)** |
| option NPC | `0x14 0100 **03** 00` | **`0x14 0100 04 00`** |
| map / spawn | 10991 / (370,680) | **giống hệt** |
| điểm NPC | (910, 290) | **giống hệt** |

Option `04` khớp bảng triggerID mục 1: **`4 = 團P`**. Đường đi bộ trong cả hai capture đều kết
thúc ở `(910,290)` rồi mới `0x20 020008`, nên NPC là **cùng một NPC** với thứ 3 và 40NPC.

Tên gọi là "loạn đấu **đội**" nhưng **user chốt 05/09: vẫn đăng ký SOLO, không lập party.**
Chuỗi đăng ký giống thứ 3 y nguyên (`09001e` rồi advance).

### Khai báo: `lich` trong `events.json`

Chỉ khai thứ nào **khác** giá trị gốc; thứ 3 dùng luôn giá trị gốc của entry nên không lặp lại.

```json
"lich": [
  {"thu": 1, "tu": "20:00", "den": "22:00"},
  {"thu": 5, "tu": "20:30", "den": "22:30",
   "select": "03005a00", "dest_map": 54901,
   "party_battle": {"point": [1630, 430], "npc_option": "01000100"}}
]
```

`loandau.bien_the_hom_nay(ev, now)` trả **bản sao** đã đè tham số hôm nay;
`config.event_hom_nay(key)` là cửa duy nhất `run_party_digioi` lấy `ev`, nên mọi đường xuôi
(teleport, `select`, điểm NPC) tự đúng theo ngày. Event không khai `lich` thì không bị đụng tới.

Vì hai ngày lệch nửa tiếng, `in_event_window` phải so **cả phút** — `20 <= now.hour < 22`
không biểu diễn được 20:30.

### ⚠️ Hai giả định CHƯA kiểm

- **Điểm NPC (1630, 430)** là toạ độ dừng cuối khi user đi bộ trong capture, **không** đọc từ
  gamedata. Chạy thật mà không mở được NPC thì đây là chỗ chỉnh đầu tiên.
- **`select` id 90** không có trong `EActivity` (`ActivityInfo.lua` không có id 90). Nó là chỉ
  số trong danh sách dịch chuyển server gửi. Thứ 3 dùng id 3 ổn định nhiều tuần nên id 90 khả
  năng cũng ổn định — nhưng đây là **suy đoán**, chưa kiểm.

### Ra khỏi sân vô giới: KHÔNG cần chạy ra NPC — cứ tắt acc

User chốt 05/09 sau khi chạy thật: sân vô giới nằm trên **máy khác**, mà login lần sau **luôn vào
máy gốc** → tắt game là ra khỏi map event luôn.

Khác hẳn thứ 3 (map 10991 **cùng máy**): ở đó không ra thì lần sau bot khởi động từ map event
chứ không phải từ thành, nên vẫn phải `exit_event`.

Capture có cho thấy client nói chuyện NPC (`0x14 04000100` → `08000100` → `09001e` → `0600`
→ `S:001-021`), và bot từng làm theo. Đã **bỏ** — nó chỉ thêm một chỗ có thể hỏng (dialog trên
map lạ, giữa lúc member còn đánh dở) mà không được gì.

### Đoạn mở NPC lần 2 trong capture KHÔNG phải đăng ký lại

Ở `t=305.44` có `0x14 0100 **02** 00` rồi `S2C 0x14 0900` → `0600` → `08 2a`. User xác nhận
05/09: **đó là đi hồi HP**, không phải đăng ký trận sau. Bot vẫn hồi HP/SP bằng **item**
(`before_repeat` → `heal_full` giữa 2 trận) như cũ — không cài đường NPC này.

Lưu ý kèm theo: `08 2a` hoá ra là mã **đóng phiên dialog** nói chung, không riêng "đã đăng ký".
Bot chỉ đọc nó ngay sau khi gửi chuỗi đăng ký nên không nhận nhầm.

## 3. Lỗ hổng phải vá trong code hiện tại

`_event_battle_kind` (`run_party_digioi.py:749`) chỉ trả kind khi **có leader**. Nên hôm nay
event chỉ có 2 dạng: *có leader thì lập party đánh vòng lặp*, *không leader thì tele vào rồi
đứng yên chờ tay*.

Loạn đấu là **dạng thứ ba chưa tồn tại**: không leader, không party, **nhưng vẫn tự đánh**.
→ Thêm nhánh riêng, **không** nhét vào `_is_party_event` (nhét bừa là làm hỏng đường
40NPC/2K đang chạy).

## 4. Đánh nhau: biết gì về đồng đội

Đối thủ là **người chơi thật**, không phải NPC.

**Biết:** vị trí (hàng/cột), tên, `HPmax/SPmax/HPcur/SPcur` — gói `0x0b` lúc spawn phủ **cả
nick người chơi tay**; mỗi lượt `0x33` cập nhật HP hiện/max + SP hiện (`0x33` **không** có
SP_max).

**Không biết:** **skill của đồng đội**. Gói duy nhất mang danh sách skill là
`S:008-013 <設定主角技能>` — 主角 = chính mình. Chỉ lộ ra sau khi họ ra tay, qua
`S:050-001 <戰鬥使用特技>`.

### Hệ quả lên rule sẵn có

- **Khống chế** (`_cc_target_order`, `combat.py:987`): lọc ưu tiên con **chưa dính CC**, rồi sắp
  `(_dangerous_enemy_rank, -hp, -pos)`. Nhánh "NPC nguy hiểm" khớp theo **tên NPC** nên với
  người chơi là vô hiệu → thực tế còn đúng luật **máu cao nhất khống chế trước**.
- **Bảo vệ** (`_protect_target_order`, `combat.py:826`): 7 tầng ưu tiên theo vai trò, trong mỗi
  tầng mới sắp theo HP tăng dần. Bốn tầng vai trò tra từ `_revive_reg`/`_support_reg` —
  **sổ do chính acc mình ghi lúc login**, người lạ không bao giờ đăng ký → luôn rơi tầng cuối.
  Rút gọn: **bản thân + pet mình trước → rồi người lạ, ít máu nhất trước.** Đúng ý user,
  không cần sửa.
- **Không trùng CC giữa char và pet của cùng một acc:** đã có sẵn, `_claim_target` dùng chung
  `_cc_claims` trong một tiến trình.
- **Chấp nhận:** nhiều acc của user rơi cùng một trận thì **không** phối hợp được (mỗi acc một
  tiến trình, `_claim_target` gom theo `party_idx`/`label`). User đã đồng ý bỏ qua.
- Phân biệt địch/ta **theo hàng** (hàng 0/1 = địch), `role_kind` chỉ dùng để biết cách đọc bản
  ghi → đánh người hay đánh quái đều chung một đường, không dính lại bug "vào trận không đánh".

## 5. Luồng thật — XÁC NHẬN bằng capture

Nguồn: `captures/loandau_20260825.pcap` (thứ 3 25/08/2026, 2 trận, 798s).

**Map = `10991` "Lôi đài tỉ võ" — TRÙNG map 40NPC, và NPC cũng là NPC ở `(910,290)`.**
Khác nhau đúng 2 chỗ: id chọn event và byte option trong dialog.

| | 40 NPC | Loạn đấu |
|---|---|---|
| chọn event `0x4d` | `03000400` (id 4) | **`03000300`** (id 3) |
| option dialog | `0x14 0100**05**00` | **`0x14 0100 03 00`** |
| map / NPC | 10991 / (910,290) | **giống hệt** |

### Chuỗi đăng ký (giống nhau ở cả 2 lần, không có biến thể "giữa-event")

```
C2S 0x20 020008              mở NPC
C2S 0x14 01000300            chọn loạn đấu (option 03)
S2C 0x14 01 ...3930          page 1 (chưa phải choice)
C2S 0x14 0600                advance
S2C 0x14 01 ...0200          page 2 — kết `0200` = CHOICE-READY
C2S 0x14 09001e              CHỌN CÓ (trùng CHOOSE_YES của 40NPC)
C2S 0x14 0600  x3            advance
S2C 0x14 0d00                S:020-013 <事件標記>
S2C 0x14 08 2a               S:020-008 <事件結束> — phiên dialog đóng = ĐĂNG KÝ XONG
```

Quy tắc page của 40NPC (kết `0200`/`0300` = choice-ready, không thì advance) **áp dụng nguyên**.

### Mốc trận

- Bắt đầu lượt: `S2C 0x34 0100`.
- Kết trận/phiên: `S2C 0x14 08 **26**` (cùng `S:020-008`, khác mã).
- Đăng ký lại cho trận sau: lặp y nguyên chuỗi trên.

### Thời gian chờ ghép — RẤT LỆCH NHAU

| | đăng ký xong | `0x34` đầu | chờ |
|---|---|---|---|
| trận 1 | 19.31 | 355.87 | **336.6 s** |
| trận 2 | 500.68 | 501.31 | **0.6 s** |

Trận 2 vào gần như tức thì → **không phải hàng chờ theo từng người**, mà là **chờ tới lượt mở
màn của sảnh**. Nên timeout phải rất rộng; mốc dừng thật là **22:00**, không phải đồng hồ đếm.

### KHÔNG có gói "đang chờ ghép trận" (đã soát trên luồng giải TRỌN VẸN)

Trong 336s chờ có **513 gói S2C**, chỉ **4 gói** mang id của mình — và cả 4 đều ở `t=355.68`,
tức đúng lúc trận bắt đầu (`0x0b sub 250` = tạo trận). Suốt thời gian chờ: **không một gói nào**.

Protocol CÓ gói hiệu ứng chờ — `S:020-044 <玩家等待動畫> +玩家ID(8) +種類(1)` (kind 1 =
SetWaitEvent, 2 = StopWaitEvent) — nhưng thân hàm trong bản client này bị **comment hết**, và
server trong capture **không hề gửi**. `S:020-040 <擂台賽活動訊息>` cũng không xuất hiện.

→ Biết "đang chờ" bằng **trạng thái**, không bằng gói: đã nhận `0x14 08 2a` mà chưa thấy
`0x0b sub 250`.

### `0x25` = số trận thắng loạn đấu — tín hiệu nhịp của sảnh

`S:037-001 <團p勝場數> +玩家ID(8) +勝場數(2)` = opcode 37 = **`0x25`**, sub `01`. Server bắn
**theo lô** đúng lúc một vòng đấu kết thúc, gồm cả id của mình:

| t | số người | ghi chú |
|---|---|---|
| 338.4 | 8 | vòng của người khác kết thúc → **17.5s sau trận của mình mở** |
| 477.8 | 10 | trận 1 của mình kết thúc (ta: win=0) |
| 791.8 | 10 | trận 2 của mình kết thúc (ta: **win=1**) |

Dùng được 2 việc: **đếm số trận đã thắng của chính mình**, và biết **sảnh vừa xong một vòng**
(vòng kế mở sau ~17s).

### ⚠️ BẪY TOOL: `analyze_pcap.py` bỏ sót frame vắt qua 2 segment TCP

`_decoded_frames()` giải **từng segment một**, frame nào bị TCP cắt ngang là **mất im lặng**.
Trên capture này: **9.78% byte (6397/65423)** không giải được, mất 6 frame — trong đó có
**`0x0b sub 250` (gói TẠO TRẬN)**, tức mốc quan trọng nhất. Phải **ghép luồng theo seq** trước
khi dò `c0 91`; ghép xong thì còn **0 byte** không giải được.

Mọi kết luận rút từ capture bằng tool cũ đều phải soi lại với con mắt này.

### Chống rớt trong lúc chờ

Suốt 336s đó client **chỉ** gửi `C2S 0x0a 0000`, đều đặn **20.0 s/lần** (40 gói cả file, mọi
khoảng đều 20.0–20.1s). Đây là thứ duy nhất giữ kết nối → vòng chờ **phải** để keepalive chạy,
tuyệt đối không chặn luồng.

## 5c. ⚠️ PHE KHÔNG CỐ ĐỊNH — sự cố đá hàng loạt 25/08 21:33

Chạy thử lần đầu: vào trận là **3 acc bị đá cùng lúc**, `S:000-000` lý do **42 = `修改戰鬥封包`**
("gói chiến đấu bị sửa", `quit = true` = đá hẳn, kéo theo reconnect hàng loạt).

Gốc rễ: mọi trận thường (train/PB/Dị Giới/40NPC/2K) đều xếp **phe ta hàng 2-3, địch hàng 0-1**,
nên hai hàng này bị **viết chết** khắp `state.py` / `combat.py` / `client.py`. Loạn đấu là PvP,
**server xếp mình vào phe nào cũng được**. Parser thật chạy lại gói tạo trận trong capture:

| trận 1 (t=355.7) | trận 2 (t=501.2) |
|---|---|
| **TA ở (0,1)** | **TA ở (0,0)** |
| kind=2 (người) ở hàng **0 và 3** | như trên |
| kind=4 (pet) ở hàng **1 và 2** | như trên |

→ Hai phe là **{0,1}** và **{3,2}**. Bot đứng hàng 0 mà coi hàng 0-1 là địch → **bắn vào đồng
đội** → server coi là gói bịa → đá. Lệnh người thật khớp đúng: `src=(0,1)→(0,3)` skill hỗ trợ
(cùng hàng 0), `src=(1,1)→(2,0)` Loạn Kích (pet đánh hàng 2 = địch).

**Cách sửa (khu trú, không đụng mode khác):** `BattleState` có `enemy_rows` / `ally_rows` /
`char_row`, **mặc định `(0,1)` / `(2,3)` / `3` = y hệt hành vi cũ**; mọi chỗ viết chết đổi sang
đọc từ đây. Riêng loạn đấu, gói tạo trận → `loandau.o_cua_minh()` → `doi_phe_theo_hang_cua_minh()`.
`combat._hang_cua(state, unit)` thay cho `3 if unit == UNIT_CHAR else 2` (11 chỗ).

**Không đọc được ô của mình → `enemy_rows = ()` + xoá quái cũ → bot KHÔNG đánh trận đó.**
Bỏ một trận còn hơn mất acc.

### Vẫn văng lần 2 (21:58) — HÀNG NGUỒN

Chia phe đã đúng (`mình ở (0,4) → địch hàng (2,3)`, `quai@[20..24,30..34]`) mà **vẫn bị đá**.
Gói `0x32` là:

```
01 00 | [hàng nguồn][cột nguồn] | [hàng đích][cột đích] | [skill u16] | [nonce 2B]
```

`client._send_combat` lấy **thẳng `d.unit`** (3=char, 2=pet) làm **hàng nguồn** — trùng nhau bấy
lâu vì trận thường luôn xếp phe ta ở hàng 2-3. Đứng hàng 0 mà khai nguồn là hàng 3 = khai một ô
**không phải của mình** → vẫn lý do 42.

Sửa: `hang_nguon = combat._hang_cua(self.state, d.unit)` rồi dùng cho cả `source` (điều phối
party) lẫn byte đầu payload. Mặc định `_hang_cua` trả đúng 3/2 nên trận thường không đổi.

### Kèm theo: HP của mình đọc sai hàng

`state.update_0x33` tra HP/SP của mình bằng `groups.get((0x03, self_slot))` (char) và
`(0x02, self_slot)` (pet) — hardcode. Ở loạn đấu ra rỗng nên log hiện `char(HP=0/0 SP=0/0)`,
khiến bot không biết máu mình và chỉ đánh thường. Đã đổi sang `char_row` / hàng pet suy từ
`ally_rows`. (`solo_multipet` cũng vậy.)

## 5b. Kết thúc: KHÔNG có bước đổi thưởng

**Server tự trao thưởng** khi event xong (user xác nhận 25/08) — khác 40NPC. Capture cũng không
có `0x14 0100 0e 00` nào, khớp với điều đó.

Hết 22:00 (hoặc login lúc ngoài giờ): **ra khỏi map event rồi tắt game**, qua
`_loandau_ra_khoi_map()` → `exit_event` (10991 → 12003). Vẫn phải ra khỏi map dù không đổi
thưởng: để nguyên trong 10991 thì lần login sau bot khởi động từ **map event** chứ không phải từ
thành. Hàm kiểm `current_map == dest_map` trước, đang ở map khác thì không làm gì.

## 6. File dự tính sửa

- `events.json` — entry `loan_dau`
- `bot/loandau.py` — module mới (**phải có** `from __future__ import annotations`, Chaquopy py3.8)
- `run_party_digioi.py` — nhánh event solo-không-leader-vẫn-chạy (mục 3)
- `tools/sync_apk_python.py` — khai báo file `bot/` mới, thiếu là build DỪNG
- `documents/LOAN_DAU.md` (file này) + mục `KNOWLEDGE.md` + test

## 7. Bài học 40NPC phải mang sang

- **Không dùng item khi prompt đang mở** → server trả `0x14 080001` + `0x00` và **kick**.
- Sau mỗi advance **poll sát 0.1s**, dừng ngay khi trận spawn — advance thừa lọt vào trận là bị kick.
- Phân biệt page **fresh** (cần advance 1 lần) vs **giữa-event** (đã là choice, chọn luôn).
- Mốc trận bám `0x0b sub 250` (vào) / `0x34` (bắt đầu lượt) / `0x0b sub 0` (kết), **không** đoán
  theo `0x14 08`.
