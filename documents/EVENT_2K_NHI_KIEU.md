# EVENT NHỊ KIỀU (2K) — thiết kế auto đánh nhiều tầng

Trạng thái: **đang chờ pcap** (chưa code). Event hiện bị ẩn từ 30/07 (`e8f015b`, lý do ghi
"chưa làm xong" = thiếu đúng phần auto đánh mô tả dưới đây).

## Đang có sẵn (đã chạy được)
Vào map event — dựng từ `ts_event.pcap` (đã verify chứa map 12921/12922):

- chọn event `0x4d 03000100` → server tele tới **staging 12921**
- đi bộ 4 chặng → qua cổng `idx=2` tại (350,330) → **map event 12922**
- đường ra: `exit.out_map = 12003`, đi bằng smart scene route

Dữ liệu nằm ở `events.json → events.nhi_kieu`. Code chạy: `client.go_to_event()` / `exit_event()`.

## Cái còn thiếu — auto đánh
2K **không dùng lại được** cơ chế 40 NPC. Khác biệt cốt lõi:

| | 40 NPC (`kind: npc_repeat`) | 2K (cần mới) |
|---|---|---|
| Vị trí | đứng yên 1 điểm, mở lại trận cùng chỗ | **đi cảnh**, nhiều tầng |
| Vòng lặp | mở NPC → đánh → lặp | tới điểm quái → đánh sạch → **lên tầng kế** |

## Quyết định đã chốt (theo yêu cầu người dùng)
1. **Lập party, cả đội đi cùng nhau** (leader dẫn, member bám theo) — không phải mỗi nick đi riêng.
2. **Tầng dưới khác nhau, tầng trên giống nhau** → kịch bản phải chịu được cả hai, không hardcode
   cứng toàn bộ.
3. **Dùng lại bộ tìm đường thông minh sẵn có** để tới điểm đánh nhau, thay vì chép cứng từng bước
   `move` như phó bản lv20: `follow_smart_scene_route()` / `_route_move()` (walkability đọc từ
   `Ground.mmg`), và quét quái động kiểu mode train (`mob_scanner`) cho các tầng khác nhau.
4. Dữ liệu tầng để trong `events.json` (`party_battle.kind = "floor_crawl"`), **không hardcode**
   trong .py — giống cách 40 NPC để `point` trong json.

## Khuôn code sẽ theo
`do_team_dungeon_lv20` — nó đã đúng hình dạng "nhiều chặng nối tiếp": một list, mỗi phần tử là
`{thoại, moves, transit}` cho một chặng. Khác là 2K thay `moves` cứng bằng smart route + scan quái.

## Bản đồ tháp — ĐÃ CÓ SẴN trong `world_nav.json` (không cần pcap)
Giả thuyết "map ID tăng dần" đã được xác nhận bằng dữ liệu:

- Tháp chính: **12922 → 12959** (38 tầng), 12921 là map chờ. `12940` không tồn tại.
- `edges` có sẵn cạnh nối từng tầng kèm **door index**, `gates` có sẵn **toạ độ tâm cổng**.
  38/39 map có toạ độ cổng → leo tầng dựng được hoàn toàn từ dữ liệu tĩnh.
- Door index lên tầng **không cố định**: đa số `2`, nhưng có `1` (12925, 12927, 12944, 12950-12953),
  `3` (12930), `5` (12945-12947, 12955-12958). ⇒ **phải đọc từ `world_nav.json`, không hardcode.**
- Nhánh riêng `12941 → 12942 → 12943` (12941 có cổng ra 10997) — chưa rõ là nhánh khác của 2K hay
  event khác; đừng gộp vào tháp chính khi chưa xác minh.

### Tầng KHÔNG có cổng lên trong dữ liệu tĩnh — **giả thuyết, cần pcap xác nhận**
`12934, 12939, 12949, 12954` (và `12943` ở nhánh riêng) chỉ có **door 1 = đi xuống**, không có cổng
lên. Nghi là **tầng boss/chốt**: cổng lên chỉ hiện sau khi dọn sạch tầng → không nằm trong file tĩnh.
Chưa xác minh, **không được code như thể đã chắc**.

## Còn chờ pcap để chốt (KHÔNG được đoán)
- **Cách chạm quái**: tự lao vào hay phải bấm/tương tác?
- **Dấu hiệu "sạch quái tầng này"** để biết lúc nào được đi tiếp.
- **4 tầng chốt** ở trên: cổng lên xuất hiện thế nào sau khi clear?
- Mốc kết thúc / thất bại; có phải leo hết 12959 không.

(Đã tự trả lời được nhờ dữ liệu tĩnh: chuyển tầng bằng cổng thường + door index; map id từng tầng;
số tầng ≈ 38.)

Capture cần: từ lúc chọn event, qua cổng vào, **trọn 3 tầng liên tiếp** (2 tầng chưa đủ thấy quy
luật lặp), và nếu tiện thì cả lúc kết thúc/thoát ra. Đặt tên file có `2k` hoặc `nhikieu`
(repo đã có `ts_event.pcap` chỉ chứa đoạn vào map).

> Theo lệ repo: **giữ pcap tới khi tính năng hết bug**; xác nhận điều mới thì cập nhật
> `KNOWLEDGE.md`.


## Lệch tầng → gom về TẦNG THẤP NHẤT cả đội đang ở

**Bot ra lệnh, cả party theo** — không acc nào tự tính lấy. Điều phối chốt một tầng đích vào kế
hoạch (`ke_hoach["tang_gom"]`, hàm `_tang_gom_2k`), mọi acc đọc cùng con số đó rồi đi bộ xuống.

- Cả đội còn trong tháp → `min(map)`: đứa ở tầng thấp khỏi phải đi, đứa trên đi bộ xuống.
- Có acc đang ở **ngoài** tháp → về cửa vào `dest_map` (12922): acc ngoài tele vào bình thường,
  acc trong tháp đi bộ xuống đấy.

Đọc thẳng `current_map` của từng client, **không** đọc `st["event_start_map"]` (bảng đó chỉ được
điền lúc login) — nhờ vậy bắt được cả lệch tầng **giữa chừng**.

Trong map event **không teleport được**, nên gom = đi bộ theo cổng
(`client.regroup_to_event_start(ev, dest=<tầng>)`).

### Ba lỗi đã sửa (06/09/2026)

**1. Nhánh gom về tầng thấp nhất từng CHẾT.** Commit `032f42a` (09/08) thêm `_2k_regroup_target`
nhưng đặt nó ở nhánh `elif` **thứ hai** với điều kiện y hệt nhánh ngay trên
(`elif _inside_floor_crawl_tower(ev, c.current_map):` × 2). Python chỉ vào nhánh khớp đầu tiên →
nhánh mới không chạy lần nào; nhánh cũ tụt thẳng về **đáy tháp 12922**, mất hết tầng đã leo.
`client.regroup_to_event_start` cũng bị định nghĩa hai lần y như vậy. Đã xoá bản chết ở cả hai chỗ.

**2. Lệnh GOM trong tháp không ai thi hành được.** Điều phối bảo GOM → leader gọi `_do_reform()` =
đi route **về thành**, mà trong tháp không có route nào → in `reform: khong co smart/legacy route ->
bo qua` rồi trả về ngay. Giờ qua `_thi_hanh_gom()`: có `tang_gom` thì **đi bộ xuống tầng**, ngoài
event mới reform như cũ.

**3. Leader quay vòng trần 8.000 vòng/giây.** `_do_reform()` trả về tức thì rồi `continue` **không
ngủ**. Party 5 (06/09): `thsau` **422.627 dòng log**, 201.495 lần lặp, cao điểm **7.985 dòng trong
một giây**. Vòng đó ăn GIL nên **bỏ đói luôn luồng điều phối** — kế hoạch đóng băng ở `viec=gom`
suốt 5 phút dù cả party đã chung kênh từ 13:15:37; vòng nóng tự nuôi chính nó. Đã thêm
`time.sleep(KE_HOACH_NHIP)` sau khi thi hành lệnh.

Kèm theo: **cùng map mà lệch kênh → `VIEC_DONG_BO`**, không phải `VIEC_GOM`, và không đòi leader
phải "báo cáo" (`_lech_kenh_that`) trước. Party 5 có cả 5 acc ở map 12922 mà vẫn bị ra lệnh gom về
thành — giữa tháp 2K thì vô nghĩa.


## Tầng CHỐT — cổng lên chỉ hiện sau khi THẮNG

`world_nav.json` chỉ có cổng **xuống** cho **12934 / 12939 / 12943 / 12949 / 12954**. Đó không
phải thiếu dữ liệu: user xác nhận 06/09 — *"đánh chưa thắng được nên thế, khi nào đánh thắng mới
xuất hiện cổng"*. Lúc crack dữ liệu scene thì tầng chưa dọn nên cổng chưa tồn tại.

**Vòng leo tháp vì thế phải ĐÁNH HẾT TẦNG rồi mới kết luận.** Bản cũ kiểm cổng lên *trước*, không
thấy là `break` ngay → lên tầng 11 rồi **đứng im, không đánh trận nào** (party 1 và party 11,
06/09: *"lên đỉnh tháp thì ko thấy đánh tiếp"*).

### Tầng 11 (12934 "Đỉnh Tháp") khác tầng thường hai chỗ

Bóc từ `captures/2k_tang11_20260906.pcap`:

```
10.80  C2S 0x14 0800 02        qua cổng idx 2 (từ 12933)
10.91  S2C 0x0c map=12934 pos=(630,890)          ← chỗ cập bến
12.76  C2S 0x0c 0100 → 13.70 C2S 0x14 0600 → S2C 0x14 08 2a    (scene_resume, đúng như mọi tầng)
14.97..16.26  C2S 0x06 move → (639,670) (644,575) (647,480) (650,430)
16.70  C2S 0x14 0800 02        ← KÍCH TRẬN bằng idx 2
16.94  S2C 0x14 0100 …         thoại mở
17.00..19.77  C2S 0x14 0600 ×6 ↔ S2C 0x14 0100 ×6
19.91  S2C 0x14 0900           thoại xong
20.53  C2S 0x5b 0200 ×12       xếp đội hình
23.93  C2S 0x32 0100           ĐÁNH
```

| | Tầng thường | Tầng 11 (12934) |
|---|---|---|
| điểm đánh | `[510,1190] [290,730] [510,330]` | **`[650,430]`** (một điểm) |
| idx kích trận | 3..8 | **2** |

`battle_idx` trong `events.json` khai idx riêng cho tầng chốt. **Không** mở rộng khoảng mặc định
xuống 2: ở tầng thường idx 2 thường **là cổng** (12933 door=2) → bấm vào là qua cổng sớm.

Sáu bước thoại không cần code thêm — `_fight_one` đã có `_DIALOG_CAP = 15`.

**Còn thiếu**: cổng lên 12935 (door + toạ độ) — phải capture đoạn *thắng xong → cổng hiện → lên
tầng 12* rồi bổ sung `world_nav.json`. Code đã hỏi lại `_up_gate` sau khi đánh xong nên bổ sung
dữ liệu là chạy được ngay, không phải sửa code.


## Đổi kênh trong tháp = tan đội. Ra lệnh thì phải lập lại đội

Server **cấm đổi kênh khi đang trong đội**: `C:007-000` trả `result=3` *"DANG TO DOI thi khong doi
khu duoc"*. Nên muốn đổi kênh là **phải rời đội trước** — đó là luật của game, member làm đúng.

Sai nằm ở **người ra lệnh**. Party 5 (06/09) — user: *"p5 leader đi 1 mình"*:

```
16:34:04  4 member: Doi kenh 2 THAT BAI: khong co khu do de doi (result=2)
16:34:14  4 member: Doi kenh 2 THAT BAI: DANG TO DOI thi khong doi khu duoc (result=3)
16:34:14  4 member: -> roi party roi thu lai
16:34:15  4 member: Doi kenh OK -> 2            ← đổi được, nhưng ĐÃ RA KHỎI ĐỘI
16:34:26  leader:   Doi kenh OK -> 2
16:34:53  leader:   qua cong idx=2 -> map 12929  ← đội đã tan, không ai bị kéo theo
16:35:38  leader:   tang 6 chi danh duoc 0/3 tran
16:36:01  DIEU PHOI: gom - party dang o 2 MAP khac nhau [12928, 12929]   ← lệnh rơi vào hư không
```

Lệnh gom lúc 16:36:01 vô dụng vì leader đang kẹt trong luồng `run_floor_crawl`, mà luồng đó
**không đọc kế hoạch**.

### Hai chỗ đã vá

**1. Điều phối nợ thì phải trả.** Chốt `kenh_dich` → đặt `st["kenh_no_lap_party"]`. Khi cả party
đã về chung kênh mà đội không còn đủ → `_bump_reform("doi kenh xong -> lap lai party")`. Ra lệnh
đổi kênh là ra lệnh hai bước, không được bỏ dở bước hai.

**2. Không được lên tầng một mình.** `run_floor_crawl` nhận callback `du_party()`, gọi **ngay
trước `_enter_gate`** (sau khi đã đánh xong tầng): chưa đủ thì mời lại tại chỗ trong
`DU_PARTY_TRUOC_CONG_SEC = 60s`; hết hạn vẫn chưa đủ thì **thôi leo** (`break`) để điều phối xử lý.
Qua cổng một mình là hỏng cả vòng — member bị bỏ lại tầng dưới, leader leo tiếp và đánh không nổi.

---

## 20/09/2026 — 2K chuyển hẳn sang ENGINE PARTY MỚI (mọi party)

Ngày 20/09 **không party nào vào được Nhị Kiều**. Log thật, cả loạt acc của mọi party cùng giây
14:15:33:

```
[tkbon]   DIEU PHOI chot tang gom Thong Dao (12922), minh dang o 12001 -> di bo xuong
[tkbon]   gom doi: di bo 12001 -> 12922 (map event khong teleport duoc)
[dieutam] scene route: khong tim thay duong 12061 -> 12922
[dieutam] gom doi: KHONG di bo duoc 12061 -> 12922
```

Gốc: acc còn **ở thành** mà bị giao "đi bộ vào map event". Không có đường bộ từ thành vào cụm map
event, nên lệnh thất bại → điều phối chốt GOM lại → lặp vô tận.

User: *"event 2k thì tất cả đều chạy engine mới, engine cũ lỗi thế thì chạy làm đéo gì"*.

### Quy tắc mới

`floor_crawl` chạy **engine mới cho MỌI party**, không xét ngưỡng `PARTY_ENGINE_MOI_TU`
(`EVENT_KIND_ENGINE_MOI_MOI_PARTY`). Các loại event khác vẫn theo ngưỡng như cũ.

### Ba điều engine mới phải biết về 2K

| | |
|---|---|
| **Map event là CẢ DẢI TẦNG** | `dest_map..top_map`, không phải một map. Chỉ kể `dest_map` thì leo lên tầng 2 là engine tưởng acc "ra khỏi event" → giao `vao_event` → `go_to_event` → kéo cả đội về 12921, **mất sạch tầng đã leo**. Sân chờ 12921 **không** kể vào dải: acc ở đó vẫn phải `go_to_event` đi tiếp vào 12922. |
| **Trong tháp KHÔNG teleport được** | `ve_thanh` / `resync` / `ve_map` đều đi bằng teleport → là lệnh **rỗng**. Engine cũ quay 201.495 vòng vì điều này (party 5, 06/09). Engine mới chặn hẳn mọi việc di chuyển khi `tang_gom` đang bật. |
| **Lệch tầng chỉ có một đường: ĐI BỘ** | `VIEC_FC_GOM` → `regroup_to_event_start(ev, dest=tang_gom)`. Tầng gom do `_tang_gom_2k` của engine cũ chốt — **tầng thấp nhất cả đội đang ở**, không phải đáy tháp (tụt về đáy là mất sạch tầng đã leo). Chỉ khi còn đứa **ngoài** tháp nó mới trả `dest_map` = 12922 (cửa vào, chỗ ngoài tele vào được). |

### ⚠️ BẪY: `go_to_event` có `leave_party()` ngay dòng đầu

Vào event phải **không có party** (dính party từ trước thì tele lỗi), nên `go_to_event` rời party
trước. Gọi nó ở đường **gom** = đập tan party vừa lập.

Đã xảy ra thật trong chính ngày 20/09: bản vá đầu tiên cho acc ngoài tháp gọi `go_to_event` để
"tele vào" → user: *"sao party xong leader bị văng thế"*. Đường gom chỉ được dùng
`regroup_to_event_start`. `tests/test_engine_moi_2k.py` giữ cả hai bẫy này.

### Vòng leo tháp dùng CHUNG một hàm

`chay_leo_thap_2k()` tách từ `_start_training` ra cấp module (y cách `chot_thanh_tap_ket` đã tách
từ `_do_reform`). Cả engine cũ lẫn engine mới **gọi lại chính hàm đó** — không ai chép lần hai.
Hai bản vòng leo tháp song song thì sẽ lệch nhau, chỉ là sớm hay muộn.

### ⚠️ BẪY: hai callback của engine mới vốn viết cho 40NPC

Mở cửa cho 2K mà để nguyên chúng thì **cả party chạy về Quảng Trường rồi thoát game** dù 2K chưa
đánh phút nào (đã xảy ra thật 20/09 — user: *"làm lồn gì mà bọn nó chạy về quảng trường rồi out hết"*):

| Callback | Bản 40NPC | 2K phải là |
|---|---|---|
| `_event_xong_engine_moi` | `not in_40npc_window()` — khung giờ **của 40NPC** | `st["event_exit_now"]` — điều phối là người duy nhất chốt "2K hết", và nó phân biệt `thua/xong/het_duong` = hết thật với `ket/dut` = chưa hết |
| `_doi_thuong_engine_moi` | `claim_40npc_reward()` → về Trác Quận → NPC 12003 | 2K **không có NPC đổi thưởng**: `exit_event(ev)` ra khỏi tháp rồi thoát game |

2K (`nhi_kieu`) để `lich: null` — **không có khung giờ**. Hỏi khung giờ của event khác là ngoài
khung đó nó trả "xong" ngay lập tức.

### Công tắc an toàn vẫn nguyên

`PARTY_ENGINE_MOI_TU = 0` (hoặc config hỏng) vẫn **tắt hẳn** engine mới cho mọi party, kể cả 2K.
2K chỉ được miễn phần xét **số party**, không được miễn công tắc tắt.

---

## 20/09/2026 (chiều) — bỏ thread `floorcrawl-*`, engine giao TỪNG BƯỚC

User: *"vòng leo tháp thì có cái lồn gì đâu, đi theo party chỉ leader di chuyển, bọn kia tự đi
theo rồi, có gì mà 1 thread ko điều khiển hết được"*.

Đúng vậy — đọc lại `run_floor_crawl` thì cả vòng chỉ là chuỗi bước **của riêng leader**; member
không xuất hiện một dòng nào (chúng dính party nên tự theo).

### Vì sao phải bỏ

`start_floor_crawl` **đẻ thread riêng rồi trả về ngay**. Engine mới nhịp 1 giây thấy "việc xong
trong một nhịp" nên giao lại liên tục, mỗi lần lại gửi gói gia hạn quest-mode cho **cả party**:

```
15:29:45 -> 15:30:15  ENGINE: taot006 -> danh_event      ← 30 lần liên tiếp, mỗi giây
15:29:58 ENGINE: 'danh_event' giao lai 40 lan lien tiep cho taot006 - viec chay xong ngay
15:30:16 [taot006] RECONNECT: server rot -> login lai sau 5s (lan 1)
15:30:16 [party 7] DIEU PHOI: nguoi keo 'taot006' khong con chay -> tam giao cho tat ca
```

Leader rớt → 4 member quay vòng `lap_party` mãi. User: *"party xong rồi, đéo thấy đi đánh, 1 lúc
sau leader dis"*. Engine cũ không dính vì nó gọi `_start_training` **đúng một lần**.

### Cách làm mới

`floor_crawl.tinh_buoc(ev, scene, k)` — **hàm thuần**, luôn trả tuple 4 phần tử:

| Trả về | Engine giao |
|---|---|
| `("danh", idx, point, None)` | `VIEC_2K_DANH` cho **leader**, member `nghi` |
| `("len_tang", nxt, door, center)` | `VIEC_2K_LEN_TANG` cho **leader**, member `nghi` |
| `("xong" / "het_duong", …)` | ghi `2k_ket_qua` để `_dieu_phoi_chot_2k_xong` chốt như cũ |

Tiến độ `{"scene", "k"}` nằm ở **state party** (không ở client) — leader rớt, acc khác lên thay
vẫn đọc tiếp được. `k` đếm theo **từng lần thử**, không theo trận thắng (điểm đã hết quái vẫn
phải tính là đã đi qua, nếu không thì quay lại điểm 1 mãi — log thật tầng 8/12931).

Bước nhỏ **gọi lại `floor_crawl`** (`danh_mot_diem`, `qua_cong_len_tang`) — không chép logic đánh
hay qua cổng sang chỗ khác.

### Ba thứ bỏ được

1. thread `floorcrawl-*` — engine không còn cảnh bấm nút rồi mất lái
2. callback `du_party()` **nằm chờ 60 giây** — thay bằng engine đọc ảnh chụp trước khi giao
   `VIEC_2K_LEN_TANG`, đúng luật "không acc nào chờ acc khác"
3. cửa chặn `_floor_crawl_started` — không còn vòng nào để gọi trùng

### L0 vẫn có cửa NGAY TRƯỚC CỔNG

Qua cổng là bước **không quay lại được**, nên ngoài việc engine chỉ giao khi ảnh chụp thấy đủ đội,
`qua_cong_len_tang` còn **hỏi lại một phát** ngay trước `_enter_gate` (đi bộ tới cổng có thể mất
cả phút, mà đội tan giữa chừng là chuyện bình thường trong tháp — đổi kênh phải rời đội trước).
Hỏi một phát rồi thôi, **không nằm chờ**. `tests/test_rule_dieu_phoi.py` neo cả hai đường.

> **Engine cũ giữ nguyên**: `chay_leo_thap_2k` + `run_floor_crawl` còn đủ, party chạy engine cũ
> (ngưỡng = 0) vẫn leo tháp như trước.

---

## 20/09/2026 — GỐC THẬT: recv-loop không nghe thoại trong tháp (hồi quy từ 14/09)

Cả ngày 20/09 **không một acc nào đánh được trận 2K nào, không ai lên được tầng nào** — ở **cả
engine cũ lẫn engine mới**. Đổi engine không cứu được gì vì lỗi nằm trong `client.py`.

```
16:47:25 [ttmmot] 2K: bam idx=3 tai pos=(987, 439) map=12922 kenh=1
16:47:28 [ttmmot] 2K: idx=3 khong mo thoai sau 3s -> coi nhu diem da het quai
```

Đối chiếu capture MuMu cùng ngày, người thật bấm **đúng gói đó** thì server trả lời sau 0.06s:

```
0.83 C2S 0x14 08 00 03                    ← bấm điểm
0.89 S2C 0x14 0100 0000 0001 0003 03 …    ← thoại mở
0.93 C2S 0x14 0600  (×4)                  ← đẩy thoại
2.36 S2C 0x34 0100                        ← BATTLE START
```

Tức bot **gửi đúng**, nhưng **không nghe thấy** server trả lời.

### Chuỗi nhân quả

`_fight_one` biết "thoại đã mở" qua `client._last_dialog_evt`. Recv-loop chỉ cập nhật mốc đó khi
`in_team_dungeon()`. Ngày **14/09**, `in_team_dungeon()` đổi từ *đọc `_team_dungeon_until`* sang
*đọc `current_map in TEAM_DUNGEON_MAPS`* — sửa đúng một bug thật (party 44 tự nhận đang ở PB khi
đã về thành). Nhưng `TEAM_DUNGEON_MAPS` chỉ có **4 map phó bản 62xxx**, không có map 2K nào.

Trong khi đó 2K dựa vào **chính cái mốc thời gian ấy**: `run_floor_crawl` vẫn đặt
`_team_dungeon_until` kèm chú thích *"BẮT BUỘC cho 2K vì recv-loop CHỈ cập nhật `_last_dialog_evt`
trong cửa sổ này"*. Từ 14/09 **không ai đọc mốc ấy nữa** → trong tháp `_last_dialog_evt` đóng băng
→ mọi điểm đều bị kết luận "hết quái" → bỏ qua sạch → cổng không bao giờ mở.

### Sửa

`in_floor_crawl_map(map_id)` (cache theo `map_id`, vì nằm trong recv-loop) — map thuộc dải
`dest_map..top_map` của event `floor_crawl` cũng được theo dõi thoại:

```python
if opcode == 0x14 and (self.in_team_dungeon()
                       or in_floor_crawl_map(getattr(self, "current_map", 0))):
```

`tests/test_thoai_trong_thap_2k.py` neo lại, kèm kiểm `TEAM_DUNGEON_MAPS` không bị đụng.

> **Bài học**: khi một hàm đổi từ *mốc thời gian* sang *đọc trạng thái thật*, phải rà những chỗ
> **dựa vào tác dụng phụ của mốc cũ**. Ở đây chú thích trong `floor_crawl.py` đã nói rõ nó phụ
> thuộc, mà vẫn lọt — vì chú thích nằm ở file khác với chỗ sửa.

### Mấy hướng đã loại trừ (ghi lại để khỏi đi lại)

| Nghi ngờ | Bác bỏ bằng |
|---|---|
| Bot gửi sai gói / sai idx | Capture: bot gửi `08 00 03 00`, y hệt client thật |
| Thiếu gói "ready for battle" | Capture: không có gói chuẩn bị nào trước khi bấm |
| Server trả lời chậm, timeout 3s quá ngắn | Capture: server trả lời sau **0.06s** |
| Chưa đăng ký sự kiện (`0x4d`) do relogin sẵn trong map | Đang ở trong map event thì tới điểm là đánh được |
| `_team_dungeon_until` chưa đặt lúc bấm cổng | Có đặt; và cổng chỉ là hậu quả của việc không đánh được |
