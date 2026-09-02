# Event 40 NPC (`npc_40`)

Event đánh theo party, leader điều khiển. Mở **Thứ 2 / Thứ 4 / Thứ 6, 20:00–22:00**
(`npc40.in_event_window`). Map event `10991`, NPC ở `(910, 290)` (đọc từ `events.json`, không
hardcode). Đổi thưởng ở map `12003`, NPC `(570, 770)` — **server chỉ cho đổi sau 22h**.

Code: `bot/npc40.py` (vòng lặp), `bot/client.py::start_npc40_loop` (thread + `_on_char_skill_data`
kề bên), `run_party_digioi.py` (coordinator, `_on_npc40_loss` / `_before_npc40_repeat`).

## Luật hồi máu — áp dụng cho MỌI event

> **Hết trận là hồi FULL HP + SP cả char lẫn pet, rồi mới đánh tiếp.** Không gác sau bất kỳ điều
> kiện nào (chốt 02/09/2026).

| Event | Chỗ thực thi |
|---|---|
| 2K Nhị Kiều | `floor_crawl._fight_one` → `heal_party()` sau mọi trận, kể cả trận thua |
| Loạn đấu | `loandau.run_loop` → `before_repeat()` mỗi vòng |
| 40 NPC | `npc40.run_loop` → `_end_npc_dialog` → `before_repeat()` → `_open_event_battle` |

Hàm hồi là `client.heal_npc40_between_battles()` = `heal_full(force=True)` (ngưỡng 1.0, char + pet).

**Thứ tự bắt buộc: đóng dialog → hồi máu → mở lại NPC.** Dùng item lúc prompt còn mở thì server
trả `0x14 08 0001` rồi **kick**.

### Lỗi cũ (đã sửa 02/09/2026)

Từ commit `ee515db` (03/08/2026), việc hồi máu ở 40NPC bị gác sau
`casualties = total > 0 and alive < total`, tức **chỉ hồi khi có đứa chết**. Mục đích lúc đó là
tiết kiệm ~5s/trận bằng đường tắt `CHOOSE_YES` + advance. Hai cái sai:

1. Còn sống nhưng thoi thóp thì không hồi → vào trận sau chắc chết.
2. `alive/total` đọc từ `state.allies`, **chỉ đếm char của chính leader** — party 5 acc + pet mà
   log ra `alive=1/1`. Nên kể cả ý định "hồi khi có đứa chết" cũng chỉ đúng khi đúng char leader chết.

Hậu quả thật (party 42, server luu_bi, 02/09): hết trận 10 leader còn **27/796 HP**,
`casualties=False` → vào thẳng trận 11 → char + pet chết sạch từ lượt 4.

Đường tắt `_confirm_repeat_battle` đã **xoá hẳn** để không ai gọi lại.

## Ba lối ra — đều qua `npc40._ket_thuc()`

`_ket_thuc` gọi `on_loss()` → báo party tan hàng, đóng dialog NPC, đặt `client._npc40_done = True`.
Chưa tới 22h thì đặt thêm `_npc40_bo_thuong = True` (đổi thưởng bây giờ không ăn; chạy lại bot sau
22h vẫn nhận bình thường — **không mất gì**).

| Lối ra | Điều kiện |
|---|---|
| Hết giờ | `not in_event_window()` sau một trận (qua 22h) |
| Thua 2 trận liên tiếp | `consec_loss >= 2` — chốt 31/08: "thua 2 lần cứ thoát đi" |
| **Thua sạch** | Chờ prompt "đánh tiếp?" quá `CHECK_CHO_PROMPT` (180s) |

> ⚠️ `_wait_counter` trả `False` ở **hai** tình huống khác hẳn nhau: hết số lần chờ (thua thật) và
> `not _active()` — acc **bị rớt / GUI Stop**, trả `False` ngay lập tức. Chỉ (a) mới là thua.
>
> Nhầm (b) thành thua thì leader đặt `_npc40_done` → coordinator bật `go_claim` → **cả 4 member
> đang khoẻ mạnh lập tức bỏ chạy đi đổi thưởng dù chưa đánh trận nào**. Đã xảy ra thật (party 6
> tao_thao, 02/09): leader bị kick mã 47 lúc 21:43:26 (17s sau khi vào trận **đầu**), 21:43:31 cả 4
> member sang map 12003; leader login lại lúc 21:43:35 tự chọn kênh 10 trong khi member còn ở kênh 5
> → nhìn ra ngoài là **"party loạn kênh"**.

### Chỉ kết luận thua khi có bằng chứng

Bản thân việc "không thấy prompt" **không đủ** để kết luận thua. Bằng chứng thật là
`client._npc40_hp_snap` — chốt HP cuối đọc được trong trận (`_da_thua_that()`).

| Tình huống | Xử lý |
|---|---|
| Acc rớt / GUI Stop | `return False` — để supervisor login lại, **không** phải thua |
| Không prompt **+ quân nhà nằm hết** | `_ket_thuc()` — thua thật |
| Không prompt **+ quân nhà còn sống** | Đóng dialog, **mở lại NPC**, tối đa `MAX_THU_LAI` (3) lần |
| Hết 3 lần vẫn không vào được trận | `_ket_thuc()` — bó tay |

Ba chỗ khác cũng từng bỏ cuộc ngay từ lần đầu, nay đều thử lại `MAX_THU_LAI` lần: **đi tới NPC**,
**mở trận đầu**, **mở trận kế tiếp**. Một lần hụt gói không được phép làm cả party mất phần còn lại
của event.

### Vì sao "thua sạch" phải là một lối ra riêng

Thua sạch thì **server không gửi prompt "đánh tiếp?"**. Mà `_npc40_last_defeated` chỉ được set khi
prompt về → `consec_loss` không bao giờ tăng → luật "thua 2 trận" **chưa từng chạy một lần nào**.
Trước đây timeout chỉ `return False` câm, `on_loss()` không ai gọi → member không biết mà tan hàng.

Party 42 dính đúng thế: 20:37:19 leader timeout, sau đó leader đứng `(910,290)`, 4 member đứng
`(370,680)`, **im lặng vô hạn**.

Ngưỡng 180s chọn theo độ dài trận thật: một trận 40NPC chạy ~100s (party 42, trận 10:
20:31:42 → 20:33:15). Vòng chờ này ôm cả trận kế tiếp chứ không chỉ cái prompt, nên để ngắn quá thì
trận dài bình thường bị kết luận nhầm là thua.

## Phạm vi của quyết định "thua → thoát"

> **Chỉ có giá trị trong lần login đó.** Login lại thì đánh lại từ đầu, cho tới khi lại thua 2 trận
> liên tiếp (chốt 02/09/2026).

`consec_loss` là biến cục bộ trong `run_loop` nên vốn đã đúng. Hai cờ ở `_party_state[pidx]` thì
không — chúng sống theo **tiến trình**, không theo lần login:

| Cờ | Lỗi cũ |
|---|---|
| `go_claim` | **Không được xoá ở bất kỳ đâu.** Set một lần là mọi acc login sau đó đều đọc thấy → "40NPC xong → đi đổi thưởng + thoát" ngay khi vừa vào game → **log vào xong out luôn** |
| `event_battle_done` | Có xoá nhưng chỉ ở nhánh reconnect, lại còn gác sau `event_battle_active` — mà `_on_npc40_loss` đã hạ cờ đó xuống `False` trước → thực tế không bao giờ xoá sau khi thua |

Sửa: xoá cả hai ngay khi vào phiên event mới (`event_party_mode and not is_reconnect`), **trước** chỗ
đọc cờ, và thêm cả hai vào danh sách reset của `start_party`.

`is_reconnect` được loại trừ có chủ ý: một acc rớt giữa chừng rồi vào lại không được phép làm cả
party đánh tiếp trong khi 4 đứa kia đã bỏ cuộc.

Thoát vì thua 2 trận **không** tính là "rớt" (`reconnectable` chỉ bật theo `_forced_reconnect` /
`_login_failed` / `_unexpected_error` / `server_closed`) nên acc không tự login lại rồi đánh tiếp.

## Thread chết âm thầm

`run_loop` chạy trong thread nên **trị trả về bị vứt đi**. `start_npc40_loop` bọc nó lại: mọi lối ra
`False` (đi tới NPC lỗi, mở trận đầu timeout, vào trận tiếp timeout, exception) đều gọi `on_loss()`
một lần để party không đứng chờ mãi.
