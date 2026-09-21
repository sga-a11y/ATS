# CORE FLOW — flow chuẩn của game và của bot

> **File này là của user. Claude KHÔNG được sửa nếu chưa được user cho phép trong chính lượt đó.**
> Sửa file này mà không xin phép → `tests/test_core_flow_khoa.py` đỏ ngay.
>
> **BẮT BUỘC đọc file này TRƯỚC khi viết hoặc sửa bất kỳ flow nào.** Không đọc mà sửa = lặp lại
> đúng cái bệnh đã sinh ra file này.

## Vì sao có file này

User, 21/09/2026:

> *"cứ vài bữa mày lại bịa ra 1 flow đéo đúng rồi phá cả những cái đã đúng"*
> *"cần viết ra 1 core flow, cái flow chuẩn của game, có rule mày bắt buộc phải đọc file này trước
> khi làm hay sửa 1 flow nào đó, m ko được tự ý sửa file này mà ko có sự cho phép của t"*

Ca sinh ra nó — party 20 ngày 21/09, một acc đứng ngoài đội suốt 4 phút. Claude sửa **bốn lần,
sai cả bốn**, trước khi mở log:

| Lần | Claude làm gì | Vì sao sai |
|---|---|---|
| 1 | Giữ phiên PB bằng `any(viec_dang_lam == pb_doi_theo)` | cờ tự nuôi chính nó → khoá cứng party vào PB vĩnh viễn |
| 2 | Chặn PB khi điều phối đang chốt `gom` | PB không cần cùng map → mất lượt PB vô cớ |
| 3 | Đẩy đứa lệch map xuống nhánh gom | vẫn là lấy "gom" làm điều kiện của PB |
| 4 | Bỏ check cùng map cho **mọi** lời mời | nới luật toàn cục để chữa một ca PB |

Nguyên nhân thật nằm ở **một dòng log** có sẵn trong `party.log` từ đầu:

```
17:11:44 [dieumot] (LEADER) moi 3 member theo entity (live dung map/kenh): [...]
```

Tức: **Claude tưởng "cùng map mới mời được" là luật của game, trong khi đó là điều kiện bot tự
đặt.** Đó là loại nhầm lẫn file này tồn tại để chặn.

---

## Ba nhãn nguồn — và quyền lực của từng nhãn

Mỗi khẳng định trong file phải mang một nhãn. Nhãn quyết định Claude được dựa vào nó tới đâu:

| Nhãn | Nguồn | Quyền lực |
|---|---|---|
| `[CAPTURE]` | có pcap, hoặc đã ghi trong `KNOWLEDGE.md` | **Luật cứng.** Phá là hỏng thật. |
| `[LOG]` | có dòng log thật, ghi kèm ngày + party | **Luật cứng.** |
| `[SUY ĐOÁN]` | Claude đọc code suy ra, chưa có bằng chứng | **KHÔNG được dùng làm căn cứ để đổi một hành vi đang chạy đúng.** Chỉ để tra cứu. |

Muốn nâng `[SUY ĐOÁN]` lên `[LOG]`/`[CAPTURE]`: phải có bằng chứng, và **phải xin phép user** vì
đó là sửa file này.

## Hai loại ràng buộc — luôn phải tách bạch

Ở mỗi flow, mọi điều kiện phải được xếp vào đúng một trong hai cột:

- **SERVER ĐÒI** — ràng buộc thật của game. Phá là packet bị từ chối, acc bị kick, hoặc bị đá
  mã 42 (`修改戰鬥封包`). **Claude không được nới, không được bàn lại.**
- **BOT TỰ ĐẶT** — điều kiện bot tự thêm cho chắc ăn. Luôn phải ghi kèm **lý do + ca thật** sinh
  ra nó. Đây là phần **được phép** bàn lại khi nó gây kẹt — nhưng phải sửa **đúng phạm vi gây kẹt**,
  không nới toàn cục (bài học lần 4 ở trên).

## Luật làm việc bắt buộc

1. **Bug từ vận hành → mở `party.log` TRƯỚC.** Phải trích được dòng log chứng minh rồi mới sửa.
   Không tìm được dòng thì nói "chưa tìm được", **không** được suy từ code rồi sửa. Code cho biết
   chuyện gì *có thể* xảy ra; log cho biết chuyện gì *đã* xảy ra.
2. **Sửa hẹp nhất có thể.** Đổi hành vi dùng chung thì phải có cờ phạm vi (ví dụ
   `invite_members(bo_qua_map=...)`), tuyệt đối không sửa thẳng điều kiện gốc.
3. **Cách đã thử và sai phải được ghi lại tại chỗ** — trong comment ngay cạnh code đó, kèm lý do.
   Chặn chính Claude lặp lại sau vài tuần.
4. **Test neo bằng dòng log thật**, không neo bằng suy luận.

---

# Các flow

> Trạng thái: viết lần đầu 21/09/2026, soi từ `bot/party_engine.py` + `bot/client.py` +
> `run_party_digioi.py`. Flow nào chưa có ở đây thì Claude **phải đọc code và log trước khi đụng**,
> và nên bổ sung vào file này (sau khi xin phép user).

## Khung chung — thứ tự quyết định

`quyet_dinh` (`party_engine.py:337`) = `_quyet_dinh_goc` (`:382`) + **hai bộ lọc hậu kỳ**:

- **Đang trong trận** → chỉ giữ được việc trong allowlist `VIEC_LAM_DUOC_GIUA_TRAN` =
  `{NGHI, TRAIN, PB_DOI_THEO, THOAT}` (`:334`, áp ở `:356`). `[LOG]` — allowlist chứ không phải
  blocklist, vì blocklist sót một việc là bot bỏ trận giữa chừng.
- **Đang trong tháp 2K** → mọi việc thuộc `VIEC_DI_CHUYEN` biến thành `VIEC_NGHI` (`:373`).
  `[LOG]` party 5, 06/09: leader `thsau` ghi 422.627 dòng log, trong đó 201.495 cặp lặp lại — lệnh
  di chuyển trong tháp là **lệnh rỗng** (trong tháp không teleport được), vòng nóng 8.000
  vòng/giây ăn hết GIL.

**Thứ tự nhánh** (`_quyet_dinh_goc`) — đây là **độ ưu tiên**, đổi thứ tự là đổi hành vi cả bot:

```
lệnh tay(397) → chờ(410) → login_chore(460) → daily(477) → PHA_EVENT(558) → PHA_DG(567)
  → PB đội(667) → reform/gom(694) → resync(704) → dp_viec(713) → lệch map(778)
  → lệch kênh(786) → thiếu acc sống(816) → lập party(821) → ra spot/train(835)
```

`quyet_dinh_cap_party` (`:2229`) **không** sinh `VIEC_*`; nó ra `DP_*` rồi `DICH_VIEC` (`:107`)
dịch: `DP_GOM→NGHI`, `DP_DONG_BO→NGHI`, `DP_MOI→LAP_PARTY`, `DP_DI_TRAIN→VE_MAP`,
`DP_RA_QUAI→RA_SPOT`, `DP_LAM→TRAIN`.

**Nhịp**: worker gọi việc đồng bộ; việc trả về ngay thì ngủ bù cho đủ `NHIP_WORKER_SEC = 1.0`
(`:1611`). `VIEC_NGHI` không vào `thi_hanh`, chỉ `sleep(0.2)` (`:983`).

---

## Lập party (`VIEC_LAP_PARTY`)

**Các bước** — leader mời, member mở cửa nhận. Member: `set_party_invite_ready(True)` rồi thôi
(`:1264`). Leader: `moi_party()` → `set_party_strategist()` (`:1279`, `:1283`).

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Lời mời đi bằng `0x0d/0900`, theo **entity** | `[CAPTURE]` | comment `:632`; entity **đổi mỗi lần login** |
| Member phải **cùng kênh** | `[LOG]` | 30/08 party 3 nằm ở kênh 12/12/12/2/1 → mời mãi không ai vào |
| Member phải **cùng map** | **BOT TỰ ĐẶT** | để chắc party đã tụ trước khi kéo đi train. **Bỏ** khi đội lập để đi PB — xem flow dưới |
| Phải đặt quân sư sau khi mời | `[LOG]` | `:1280` — thiếu bước này party không có quân sư |
| Không lập party ở thành trung gian | `[LOG]` | p4 13/09 *"bọn nó lập pt ở Trác Quận làm lồn gì thế"*; p41 16/09 |
| Chưa cùng map+kênh thì chưa lập | `[LOG]` | p55 20/09 *"cả party chưa cùng map cùng kênh mà đã lập party"* |

**Cấm**: chép lại logic mời vào engine mới — bản chép đầu tiên quên cả whitelist lẫn kiểm kênh
(`:1269`).

## Phó bản tổ đội (`VIEC_PB_DOI` / `VIEC_PB_DOI_THEO`)

**Đường đi hoàn toàn riêng, không dùng cửa party thường.**

- Leader: `do_team_dungeon(level)` → `do_team_dungeon_lv20/50/80/110`. Tạo phòng
  `0x2f sub0100` (`client.py:13640`) → mời từng member `0x2f/0800 [entity]` → chờ ready →
  start `0x2f/0c00`.
- Member: **chỉ bật hai cờ** `auto_accept_party = True` + `flee_mode = True` (`:1341`), không gửi
  gói nào. `_on_dungeon` tự accept (`0x2f/0300`) + tự ready (`0x2f/0b00`).

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Mời phòng đi theo **roleId**, **KHÔNG cần cùng map/cùng kênh** | `[CAPTURE]` | comment `:632`, `:1338` |
| Member **không** gọi `set_party_invite_ready` ở đây | `[LOG]` | `:1339` — mở nhầm cửa, lời mời party thường lọt vào giữa lúc chờ phòng |
| Phải đủ người **rảnh** mới mở phòng | **BOT TỰ ĐẶT** | `[LOG]` p41 20/09: ready 4/4 là **bot tự báo**, roster server chỉ 2/4 → huỷ, quay vòng |
| Check PB **sau** nhiệm vụ ngày | **BOT TỰ ĐẶT** | user chốt 20/09 |
| Chạy 10–20 phút là bình thường, **không đặt hạn chờ** | `[LOG]` | `:1330` — watchdog 180s cũ từng kéo cả 4 member ra relogin **giữa phó bản** |
| `befriend_nearby()` không phải việc phụ | `[LOG]` | `:1058` — lời mời phòng đi theo roleId từ friend-list; bỏ thì có lúc không mời được ai |

**Cấm** (ba cách đã thử ngày 21/09, sai cả ba — `:663`):
1. Giữ phiên PB bằng `any(viec_dang_lam == pb_doi_theo)` → cờ tự nuôi chính nó, khoá cứng party.
2. Hoãn PB khi điều phối đang chốt `gom` → mất lượt PB. *"đi PB đội thì có cần gom map đéo đâu"*.
3. Đẩy đứa lệch map xuống nhánh gom → vẫn là lấy gom làm điều kiện của PB.

## Gom về thành (`VIEC_VE_THANH`)

**Gom = teleport về thành tập kết**, không phải đi bộ qua cổng (`:1114`).
Thứ tự: `pre_route_town_hop()` nếu đích **không phải** Trác Quận/Nghiệp Thành (`:1148`) →
`go_to_town(city, flag)` (`:1154`).

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Mỗi thành một **flag riêng**, truyền thiếu là bay nhầm thành | `[LOG]` | p41 16/09 *"đéo gì mà tele liên tục lại còn bị sai flag"* |
| Tele thẳng về thành route hay lỗi → qua **một thành trung gian** trước | `[LOG]` | user chốt từ lâu; p21 21/09 báo thiếu bước này |
| Điều kiện pre-route xét theo **ĐÍCH**, không xét đang đứng đâu | `[LOG]` | engine cũ `_do_reform`: `if _target_city == fc` |
| Đủ đội rồi thì **người kéo được đi**, không ép về | `[LOG]` | p42 17/09 *"đi về thành tập trung đúng rồi, nhưng sau đó ko đi ra bãi train"* |
| Đang đánh thì không tele | `[LOG]` | p56 17/09 *"sao vừa đánh vừa đòi tele về thành là sao"*; teleport giữa trận = server kick |

## Đi map train (`VIEC_VE_MAP`)

`follow_smart_scene_route` (thành route chưa mở → đi bộ tới) → `build_smart_route` →
`follow_smart_route`, tất cả có `abort`.

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Không có route → **trả False**, cấm đi mù | `[LOG]` | p41 16/09: cả 5 acc nhận `ve_map` lúc 12:23:38 rồi **im 73 phút**, không một dòng log |
| **Chỉ người kéo** được lập đường | `[LOG]` | p44 17/09 — giao cho cả party thì mỗi acc tự bốc thành riêng → party chia đôi |
| Login ở map lạ → tele trung gian rồi mới về thành tập kết | `[LOG]` | p21 21/09 |

## Ra bãi quái (`VIEC_RA_SPOT`) và đánh (`VIEC_TRAIN`)

Leader có `MOB_PATHS` → `follow_path(flee=False)` để **kéo cả party**; không có thì
`navigate_to` tới spot đã xê dịch ±10.

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| `flee=False` **bắt buộc** khi ra spot | `[LOG]` | `:1352` — để mặc định True thì acc bỏ chạy mỗi lần gặp quái, không bao giờ tới |
| Xê dịch toạ độ ±10 | **BOT TỰ ĐẶT** | cả party navigate y một điểm thì chồng lên nhau |
| Tới nơi là đánh luôn, không chờ nhịp sau | `[LOG]` | `:1379` — vòng `login_chore ↔ viec_vat` 15/09 sinh ra luật này |
| Trong Dị Giới **phải chạy lòng vòng** tìm quái | `[LOG]` | p41 16/09 *"p41 đứng ở quảng trường"* — đứng yên thì quái không tự tới |
| Mua HP/SP: tick riêng, độc lập tick tổng | `[LOG]` | `:1482` — bản đầu gọi `buy_hp_sp()` thiếu tham số → `TypeError` bị nuốt → **không bao giờ mua được** |

## Dị Giới (`VIEC_DI_GIOI`)

Thứ tự **bắt buộc**: hộ phù (nếu bật) → `set_di_gioi_level(cap)` → `enter_di_gioi_safe()`.
Gói: `0x61 010001` rồi `0x61 02 00 [idx]` (`client.py:14910`, `:14914`). `[CAPTURE]`

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Bỏ bước set cấp → cả party đánh **cấp quái mặc định** thay vì cấp user chọn | `[LOG]` | `:1288` |
| Bỏ hộ phù → mất đường kéo dài giờ DG | `[LOG]` | `:1288` |
| **Không** được bắn lại `enter_di_gioi` dày hơn | `[LOG]` | `:1307` — chính cái đó đã làm **264 acc-lần** `VAO DI GIOI THAT BAI` |
| Đủ party rồi mới chạy lòng vòng | `[LOG]` | user 16/09 *"DG vẫn phải đủ pt mới chạy lòng vòng chứ"* |
| Có acc khác hết giờ DG → **đứng yên**, không đánh một mình | `[LOG]` | `:594` — không có party hồi máu thì chết |
| Mode `digioi` thuần hết giờ → **thoát game** | `[LOG]` | p46/p54 16/09 *"hết tiệm dị giới rồi mà đéo tắt acc"* |

## Event (`VIEC_VAO_EVENT`, `VIEC_FC_GOM`)

- Vào event: `go_to_event(ev)` — nó lo cả cinematic. **Chưa vào map event thì chưa được lập party**
  (`[LOG]` p41 16/09 *"mode 40npc → chưa vào map event đã thấy lập pt"*).
- 2K lệch tầng: **đi bộ** về tầng gom bằng `regroup_to_event_start`.

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| **CẤM** `go_to_event` khi party đã lập | `[LOG]` | nó `leave_party()` ngay dòng đầu → đập tan party. User 20/09 *"sao party xong leader bị văng thế"* |
| Trong tháp **không teleport được** | `[CAPTURE]` | engine cũ 06/09 quay 201.495 vòng vì ra lệnh teleport trong tháp |
| Tầng gom = **tầng thấp nhất cả đội đang ở** | `[LOG]` | user 20/09 *"trước có tìm tầng ở giữa để tập trung, m lại bỏ cái đó đi rồi à"* |

## Ngọc Phúc Thần — khi nào THÁO

Ngọc chỉ để ăn hệ số EXP lúc train. Đeo nó vào boss/phó bản là **đốt bền ngọc mà không được gì**.

**Hai luật user chốt 21/09:**

1. **Mode `event`: tắt hẳn.** Tick hay không tick đều **không dùng**, và đang đeo thì **tháo ra**.
2. **Mode khác:** trước khi đánh **boss thế giới / boss Quân Đoàn / PB đơn / PB tổ đội** thì kiểm
   tra, đang đeo là tháo.

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Ngọc đeo ở **vị trí 6** (đặc biệt) của char, **không đeo cho pet được** | `[CAPTURE]` | `_on_equip_damage`, `client.py` |
| **THÁO RA THÔI, cấm vứt/bán/phân giải** | user chốt | *"tháo ra thôi đấy nhé, đừng có tiện tay vứt bỏ"*. Tháo xong ngọc nằm trong túi, mà bot có đường dọn túi — `DISCARD_JUNK_TIDS` chỉ chứa `0x59F0` (Ngọc Hư, đã hỏng), bốn ngọc thật đều được loại trừ ở 5 chỗ |
| **Không tự đeo lại** sau khi đánh | user chọn | để `use_phuc_than_items` tự lo ở chu kỳ sau; thêm đường đeo lại riêng chỉ tạo chỗ đeo nhầm lúc còn trong instance |
| Cửa "tắt hẳn" đặt **trong `use_phuc_than_items`**, không đặt ở từng nơi gọi | `[SUY ĐOÁN]` | có **ba** đường gọi (login · keepalive engine cũ · `_duy_tri` engine mới); chặn từng đường là sớm muộn sót một cái |
| Cờ `phuc_than_tat` đặt lúc login, **trước cửa rẽ engine mới** | `[LOG]` | đặt sau cửa rẽ thì party engine mới không bao giờ được gán — đúng lỗi đã gặp với `dat_pha_pho_ban` |
| PB tổ đội: leader tháo ở `do_team_dungeon` (**cửa vào chung**), member tháo ở `_on_dungeon` lúc nhận lời mời | `[SUY ĐOÁN]` | member **không** đi qua `do_team_dungeon` (leader gọi) — thiếu chỗ này thì cả party tháo còn member vẫn đeo vào |
| Tháo **sau** các cửa "bỏ qua" (hết lượt, còn cooldown, ô đã xong) | `[SUY ĐOÁN]` | tháo rồi mới phát hiện không đánh được là mất công |

## Việc lẻ (`VIEC_LOGIN_CHORE`, `VIEC_DAILY`, `VIEC_VIEC_VAT`)

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| **Không đặt hạn giờ** cho việc vặt | `[LOG]` | user 14/09 *"m đặt hạn 300s, sau 300 mà nó vẫn chưa xong việc vặt thì sao"* |
| Đang làm việc vặt thì **không vào party** | `[LOG]` | user 14/09 — vào pt rồi bị kéo đi là hỏng việc vặt |
| **Không** làm nhiệm vụ ngày trong pha Dị Giới | `[LOG]` | `:471` — ô2 là boss thế giới, `do_world_boss()` teleport ra → **vứt acc khỏi DG** |
| Một ô hỏng không được làm mất cả lượt | `[LOG]` | `:1579` |
| `VIEC_VIEC_VAT` **không có nhánh nào sinh ra nó** | `[SUY ĐOÁN]` | chỉ tới `thi_hanh` qua `viec_dang_lam` giữ lại ở nhánh chờ (`:413`) |

## Đổi kênh theo LỆNH TAY (nút trong GUI)

Flow user chốt 21/09 — **đủ sáu bước, không được rút gọn**:

```
1. chạy về safe gần nhất
2. thoát party
3. chuyển sang kênh được chọn      (phải CÓ XÁC NHẬN của server)
4. chạy về ĐÚNG safe đã chọn ở bước 1   (đề phòng bước 1 di chuyển fail)
5. lập lại party
6. chạy ra lại điểm quái
```

Bước 1–4 nằm trong `doi_kenh_theo_lenh_tay()` (hàm **dùng chung cho cả hai engine**).
Bước 5–6 **cố ý không** nằm trong đó: xong lệnh tay, engine quay lại chu trình bình thường, thấy
party thiếu → `lap_party` → `ra_spot`. Nhét vào hàm đổi kênh là làm hai lần → đập chính party vừa lập.

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Còn trong đội thì **server từ chối** đổi kênh (`S:007-002` mã 3) | `[CAPTURE]` | vì vậy bước 2 phải trước bước 3 |
| Đổi kênh **giữ nguyên map/toạ độ** | `[CAPTURE]` | nên sang kênh mới là đứng y chỗ cũ — chỗ đó có thể đầy quái |
| Phải ra safe **trước**, không đổi giữa bầy quái | `[LOG]` | user 27/08 *"đang train mà bấm đổi kênh thì phải kết thúc trận, chạy ra điểm an toàn rồi đổi chứ"* |
| **Leader ra safe + giải tán trước, member đi sau** | `[LOG]` | p8 31/08: member đi trước → `di chuyển QUÁ XA (mã 14)` → rụng. Member tự đi theo leader nên vị trí thật của nó là chỗ leader đứng |
| Chờ leader chốt theo **số lệnh** (`cmd_gen`), không theo Event dùng chung | `[LOG]` | p8 31/08: cờ còn sót từ lệnh trước → member qua cửa ngay, đi trước leader |
| Đổi kênh phải **có xác nhận của server**, cấm báo thành công khống | `[LOG]` | user 27/08 *"party đang trong battle và ko đổi kênh được nhưng bot báo đổi kênh thành công"*. `switch_channel` chờ `S:007-002`; timeout → `_chan_switch_result = -1` → False |
| Mã 2 (không có kênh) / 4 (kênh đầy) / -1 (im lặng) → **bỏ sớm** | `[LOG]` | thử lại cũng thế; để vòng sync chọn kênh khác cho **cả party**, không để mỗi acc một nơi |
| Kiên trì tới **5 phút** trước khi bỏ | `[LOG]` | user 27/08 *"rồi sau đó thế nào, bot đợ luôn à"* — đang train thì trận nối trận, vài lần thử đầu gần như chắc chắn rơi vào giữa trận |
| **Ghim kênh** user chọn | `[LOG]` | p16 31/08: chọn kênh 1 → 09:58:22 picker tự sang kênh 2, phủ định lệnh tay |
| Bước 4 phải về **đúng điểm** của bước 1 | `[LOG]` | user 21/09 — chọn lại điểm mỗi lần thì `rally_point` có thể đã đổi, thành về một chỗ khác |
| Thất bại thì **giữ kênh cũ**, không bỏ lửng | `[LOG]` | bước đồng bộ kênh sẽ gom cả party lại — party vẫn đồng bộ, chỉ là ở kênh khác kênh user chọn |

**Cấm**: để engine mới tự xử lý riêng. Trước 21/09 nhánh `channel` của engine mới chỉ
`return _lam_xong()` vì tin "điều phối cũ lo bằng `kenh_dich`" — nhưng `_dieu_phoi_chot_kenh` nằm
trong `_dieu_phoi_loop`, mà vòng đó **bỏ qua party engine mới** ngay cửa chặn đầu tiên. Lệnh bị
đánh dấu "đã xong" rồi vứt đi. `[LOG]` party 1, 21/09:
`18:58:20 -> lenh_tay` … `18:58:22 -> train`.

## Đồng bộ kênh (`VIEC_RESYNC`)

Chỉ **member**. Thứ tự: cửa chặn "đã ở trong party thì thôi" → `leave_party()` →
`switch_channel(theo_lenh=True)`.

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Phải rời đội **trước** khi đổi kênh | `[CAPTURE]` | server cấm đổi kênh khi còn trong đội, trả `result=3` |
| Đã ở trong party rồi thì **bỏ qua resync** | `[LOG]` | p15 06/09: 4 member đọc cờ chậm 4 giây → rời party **vừa lập** → leader đánh một mình, kẹt ở cổng |
| Party đủ + cùng kênh thì resync **vô nghĩa** | `[LOG]` | `:2412` — nó chỉ làm được một việc: đập party đang lành. Đêm 10→11/09 leader *"mời 2198s chưa đủ party (2/4)"* |

---

## Phụ lục — những chỗ chưa xác minh

`[SUY ĐOÁN]` toàn bộ mục này. Đừng dựa vào để đổi hành vi đang chạy đúng.

- Trong `thi_hanh` **không có** dòng `client.send(0x..)` nào gọi trực tiếp; mọi gói đi qua hàm của
  `client`. Opcode truy được trong chuỗi gọi: `0x61` (Dị Giới), `0x2f sub0100` (tạo phòng PB).
  Các mã `0x0d/0900`, `0x2f/0800`, `0x2f/0f00`, `0x2f/0300`, `0x2f/0b00`, `C:013-004` mới chỉ thấy
  trong **comment**, chưa đối chiếu lại capture trong lần soi này.
- Thứ tự chính xác bên trong `do_team_dungeon_lv50/80/110` chưa soi (chỉ soi lv20 và
  `_create_team_dungeon_room`).
