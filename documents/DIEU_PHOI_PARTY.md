# Điều phối party — bot quyết định, không phải leader

> Rule user chốt 05/09/2026: **"bỏ mẹ cái leader quyết định party làm gì đi, bot là người quyết định"**

## 1. Vì sao phải đổi

Trước 05/09 **không hề có ai điều phối**. Năm luồng acc tự thương lượng với nhau qua một đống cờ
dùng chung trong `st[...]`: `leader_ok`, `channel_ready`, `ready_members`, `dt_done`, `invited`,
`route_done`, `rally_ready`... Luồng của acc leader tình cờ ôm nhiều quyết định nhất nên thành
"người chỉ huy" — nhưng nó cũng chỉ là một luồng đang bận login/đánh/đi đường như bốn đứa kia.

Hệ quả tất yếu: **luồng nào rơi vào một vòng không đọc đúng cờ là cả party chết.**

### Ca chết thật: party 19, 05/09, kẹt 2 giờ 42 phút

```
14:05:29  4 member xong DG -> "DUNG YEN cho party (4/5) | CON THIEU: quan801"
14:38:48  [quanmot] "Di Gioi con lai: 0h20m"      <- nhịp đếm giờ DG, dòng CUỐI CÙNG
14:39:45  leader rơi vào vòng mời party trần
          -> in "lech map live 12001!=12003" 488 LẦN
~14:59    hết giờ DG của leader - KHÔNG AI KIỂM -> không bao giờ báo "xong DG"
15:00:32  server đá leader về thành 12003, member vẫn ở 12001
16:47:07  vẫn nguyên trạng thái đó
```

Vòng giết party ([`run_party_digioi.py`], nay đã xoá):

```python
while joined_member_count(pidx) < st["n_members"]:   # CHO VO HAN
    if not c.running or _stopped(): break
    try: c.invite_members(gap=1.0)
    except Exception: pass
    time.sleep(4)
```

Chỉ hai lối ra: mất kết nối, hoặc Stop. Không đọc giờ DG, không đọc `reform_gen`, không gọi
`_resync_ck` → **ép đồng bộ cũng không phá được**.

### Bốn tầng lưới an toàn đều thủng

| Tầng | Vì sao không cứu được |
|---|---|
| `_barrier_watchdog` | Vòng đó không gọi |
| Luật watcher (1) "cả party cùng chờ" | Leader không ở pha `wait`, member báo cáo quá cũ → `waiting_tuoi` rỗng |
| Luật watcher (2b) "thiếu người quá lâu" | Đọc `st["training_started"]` mà **không chỗ nào ghi** → chưa từng chạy lần nào |
| Luật watcher (3) "có acc đang chờ" | `if waiting: continue` → chặn không cho xuống luật (4) |

Đếm trên log cả ngày: `THIEU NGUOI` **0 lần**, `LECH VIEC` **0 lần**, `DEADLOCK` 2227 lần.

## 2. Kiến trúc mới

Mỗi party có **một luồng điều phối** (nâng cấp từ `_party_watcher`). Nó nhìn thấy toàn bộ — cả 5
client trong `account_clients`: map, kênh, giờ DG, đang đánh không — nên **không cần barrier,
không cần Event, không chờ ai**.

```
        ┌──────────────── DIEU PHOI (2s/nhịp) ────────────────┐
        │  đọc THẲNG client của cả 5 acc                       │
        │  → quyết: pha | map | kênh | việc                    │
        │  → ghi st["ke_hoach"] (gen tăng khi nội dung đổi)    │
        │  → thi hành: bump reform_gen khi cần gom             │
        └──────────────────────┬──────────────────────────────┘
                               │  chỉ ĐỌC
        ┌──────────┬───────────┼───────────┬──────────┐
      acc1       acc2        acc3        acc4       acc5      ← thi hành
```

**Tính chất quan trọng: deadlock biến mất về mặt cấu trúc**, không phải nhờ vá thêm lối thoát.
Vì không còn chờ chéo — chỉ có một chỗ quyết, và chỗ đó không bao giờ chờ ai.

### Kế hoạch (`st["ke_hoach"]`)

| Khoá | Nghĩa |
|---|---|
| `gen` | Tăng **chỉ khi nội dung đổi** — không thì cả party bị giật lại mỗi 2 giây |
| `pha` | `digioi` \| `train` |
| `map` | Map mà đa số party đang ở (đích để gom về) |
| `kenh` | Kênh chung, `None` nếu đang lệch |
| `viec` | `lam` \| `gom` \| `moi` |
| `ly_do` | Câu chữ để đọc log biết vì sao |

### Việc (`viec`)

- **`gom`** — lệch map > 15s (`KE_HOACH_LECH_MAP_SEC`) hoặc lệch kênh. Điều phối tự
  `_bump_reform` → mọi acc đang đi đường bị abort qua `_ab()` rồi gom về cùng chỗ.
- **`moi`** — đã cùng map + cùng kênh nhưng chưa đủ người trong đội.
- **`lam`** — đủ rồi, vào việc.

### Kênh đích là TRẠNG THÁI, không phải cái bắt tay từng vòng

`_dieu_phoi_chot_kenh()` đọc thẳng `current_channel` của từng client, chốt **kênh đông người
nhất** (ít phải di chuyển nhất) vào `st["kenh_dich"]`. Trong keepalive mỗi acc tự so kênh mình
với `kenh_dich`, lệch thì tự `switch_channel`. Không chờ ai báo cáo, không có "vòng" để lỡ.

Bỏ qua khi: party khác map, hoặc có acc chưa rõ kênh. **Không nhường vòng bắt tay** — điều phối
là người quyết, `do_channel_sync` chỉ còn là cánh tay thi hành.

Kênh đầy thì vào **sổ đen** `st["kenh_day"]` (`bao_kenh_day`, hạn `KENH_DAY_HAN_SEC = 120s` rồi tự
rụng vì người ra vào liên tục). Điều phối bỏ qua kênh trong sổ đen, lấy kênh đông nhì; mọi kênh
party đang đứng đều đầy thì `_kenh_trong_cho_ca_party` lấy kênh trống đủ chỗ cho **cả** party từ
`c.channels`. Về chung một kênh thì sổ đen xoá sạch.

**Chốt rồi thì GIỮ** (`KENH_DICH_KIEN_NHAN_SEC = 45s`). Hàm chốt chạy mỗi 2 giây; chốt lại từ đầu
mỗi nhịp thì acc vừa bắt đầu chuyển sang kênh A là phân bố đổi → chốt kênh B → cả lũ quay đầu →
lại đổi. Đúng kiểu thrash đã chữa cho `gom`/`reform` bằng grace + cooldown, mà hàm chốt kênh lại
thiếu. Đích chỉ được đổi khi kênh đó **vào sổ đen**, hoặc **quá hạn** mà vẫn chưa gom xong.

> **Bug thật P3 (06/09), mất 4 phút mới đồng bộ xong** — và trong 4 phút đó không mời party được
> vì lời mời không qua được kênh khác:
> ```
> 15:38:28 {1:1, 2:1}       -> CHỐT 1
> 15:38:38 {1:1, 2:2}       -> CHỐT 2      (đổi ý sau 10 giây)
> 15:41:27 {1:2, 2:2, 4:1}  -> CHỐT 1
> 15:41:39 {1:3, 2:1, 4:1}  -> CHỐT 2
> ```

**Vòng đồng bộ hỏng thì phải ĐÓNG CỬA** (`_dong_vong_sync`: xoá `channel_ready` / `channel` /
`channel_failed`). Không đóng thì cờ kẹt SET vĩnh viễn và acc nào còn bám vào lệnh đã chết thì
treo mãi. Không acc nào được "đỗ lại chờ ai pick lại" nữa: vào kênh không được, hoặc sang kênh rồi
mà sai map → ghi sổ / thoát ngay, điều phối lo tiếp.

> **Bug thật P3 (06/09, kẹt 1 tiếng)**: cả party rớt rồi login lại, leader chốt kênh 15; 3 member
> sang OK rồi `break`, `batbat` gặp `result=4` (kênh vừa đầy) → "báo leader pick lại" rồi đỗ lại.
> Leader thoát vòng sync mà không xoá `channel_ready`, `_bump_reform` thì vô dụng
> (`reform: khong co smart/legacy route -> bo qua` × 28) → leader lặp `CHO du member san sang
> (3/4)` từ 02:38 đến 03:34.

Song song, `pick_best_channel` có nhánh chặn đầu tiên: **cả party còn sống cùng map đã chung một
kênh → `return 0` (giữ nguyên)**, không thèm hỏi danh sách kênh. Trước đây picker thấy kênh mình
đang đứng "đông" — đông chính vì party mình — rồi lùa cả party sang kênh khác, và acc nào vừa
xong vòng đồng bộ trước đó thì không bao giờ biết đích đã đổi (lỗi party 53, 02:09 ngày 06/09).

## 3. Những quyết định đã chuyển đi

| Quyết định | Trước | Nay |
|---|---|---|
| Chuyển pha DG → train | Barrier `dt_done`, mỗi acc tự báo | Điều phối đọc thẳng đồng hồ DG (`_het_gio_dg`) |
| Khi nào gom | Leader tự phát hiện | Điều phối thấy lệch là ra lệnh |
| Khi nào mời | Leader mời vô hạn | Leader hỏi `viec` trước mỗi vòng |
| Chốt cấp quái DG | Acc login trước chốt | `_dieu_phoi_chot_map`, chỉ chốt khi đủ level cả party |
| Chốt map train | Acc login trước chốt | Như trên |

### `_het_gio_dg` — điểm mấu chốt

`dt_done` do **chính luồng acc** ghi. Luồng đó kẹt thì không bao giờ ghi → cả party chờ mãi.
Điều phối đọc thẳng `digioi_minutes_live()` nên luồng acc có kẹt cũng không giấu được.

Ba trường hợp:
- còn giờ → chưa hết
- `digioi_minutes_live() >= 120` → hết
- **ra ngoài map DG mà chỉ còn < 2 phút → hết** (đồng hồ nội bộ *đứng yên* khi ở ngoài DG nên
  không bao giờ tự về 0 — đúng trạng thái `quanmot` lúc 15:00)

Ra ngoài mà **còn nhiều giờ** thì **không** tính là hết — bị văng/đi chỗ khác, ép tính là hết thì
acc bị khai tử oan (lỗi cũ đã từng mắc).

## 4. Chốt cấp quái / map train

`account_last` chỉ nằm trong RAM, **reset mỗi lần start bot**. Nên lần chạy đầu tiên, acc nào
login xong trước là chốt cho cả party bằng mình nó:

```
14:10:05 >>> PARTY 1: TU CHON CAP QUAI DG -> cap 150 (muon 152, level party [167, 197])
                                                                  ^^^^^^^^^^ 1/5 acc
14:12:12 >>> PARTY 19: TU CHON CAP QUAI DG -> cap 140 (level party [153, 181])
```

Mà cả hai hàm đều **chốt một lần rồi giữ nguyên cả phiên** → sai là sai đến lúc restart bot.

Nay `_auto_dg_level` / `_auto_train_target` **trả `None` khi chưa đủ level cả party**. Điều phối
gọi lại mỗi 2 giây nên chốt ngay giây đầu tiên đủ dữ liệu.

"Đủ" = mọi acc trong party (trừ acc user đã bấm Stop) đều có **cả char level lẫn
`active_pet_confirmed`**. Phải chờ cả pet vì pet level lệch char hàng chục cấp (log 05/09: char
~154 / pet ~188) — chốt lúc mới có char là trung bình tụt ngay.

Acc side vẫn có `_cho_du_level_party` — **chờ vô hạn, không timeout** (rule user: "đủ party mới
làm gì thì làm"). Lối ra: Stop, và `_resync_ck` để lệnh ép đồng bộ vẫn unwind được.

## 5. Leader còn làm gì

Leader vẫn là **cái tay**, không phải cái đầu. Game bắt buộc leader mới gửi được lời mời, mới kéo
được route, mới set được quân sư — những chỗ đó giữ nguyên. Cái bỏ đi là quyền **quyết định**.

`_moi_theo_dieu_phoi()` thay cho hai vòng mời trần. Mỗi vòng nó hỏi lại:

1. `_resync_ck` — ép đồng bộ
2. `reform_gen` đổi — điều phối đã đổi hướng
3. `viec == gom` — thôi mời, đi gom
4. `_finish_digioi_train_if_time_over` — hết giờ DG thì báo cho cả party
5. `_dg_gather_giveup` — acc khác đã hết giờ DG
6. trần `READY_WAIT_REFORM_SEC` — quá hạn thì tự gom một lần

## 6. Neo bằng test

`tests/test_dieu_phoi_party.py`:

- **Mọi vòng `while ... joined_member_count(...)` phải có ít nhất một lối ra cấp party.**
  `_stopped()` / `c.running` **không tính** — đó chỉ là "bot tắt", không phá được thế kẹt.
- **Mọi khoá `st[...]` mà watcher đọc đều phải có chỗ ghi** — chặn tái diễn kiểu
  `training_started` (luật chết âm thầm, không ai biết).
- Tái hiện party 19: leader kẹt, không tự báo `dt_done` → điều phối vẫn phải đổi pha được.

`tests/test_chot_map_dg_doi_du_acc.py`: chờ đủ acc, không timeout, Stop thoát được, ép đồng bộ
unwind được, thiếu acc thì **không chốt bừa**.

## 7. Teleport LUÔN phải thoát tổ đội trước

Client game chặn thẳng ở `UITeleport.CheckTeleport()` (`_lua_dec/UI/UITeleport.lua:673`) — đang
trong tổ đội thì **không gửi gói nào cả**:

```lua
if Role.player.war ~= EWar.None then ... return true; end      -- đang đánh
if SceneManager.sceneId == 10701 then ... return true; end     -- scene cấm
if not Team.IsAlone(Role.playerId) then ... return true; end   -- ĐANG TỔ ĐỘI
```

Gói bot gửi vốn đã **đúng** (`C:068-001 <使用晶石天行異能> +場景ID(2) +NO(1)`), cái thiếu là điều
kiện thứ ba. Gửi mù thì server im lặng bỏ qua, còn vòng `go_to_town` cứ bắn lại mỗi 2s tới hết
deadline — đó chính là một nguồn spam sinh `mã 13 (gửi gói quá nhanh)`.

Ca thật 07/09 `[dieumot]`, cùng acc cùng thành, chỉ khác đã rời đội hay chưa:

| Giờ | Việc | Kết quả |
|---|---|---|
| 00:04:21 | `Roi/giai tan party cu` → tele | **4 giây, 2 gói** |
| 00:05:05 | còn trong đội → tele | **40 giây, 19 gói** |

Cả log hôm đó: **4758 gói teleport**, phần lớn là bắn lại.

**Rời đội đặt trong `teleport()`, KHÔNG phải `go_to_town()`.** Có nhiều đường gọi tele
(`pre_route_town_hop`, route train, NPC40, mua HP/SP…); đặt ở hàm cuối cùng thì không sót đường
nào. Mất người thì điều phối gom lại — đúng **L0**, và nó vốn đã làm vậy (04:21 rời → 05:52 gom).

Neo bằng `tests/test_tele_phai_roi_doi_truoc.py`.

## 8. Vào Dị Giới cũng phải thoát tổ đội — và server có nói lý do

Cùng luật `Team.IsAlone` với §7. Client chặn ở `UITeleport.OnClick_LimitFightArea`
(`_lua_dec/UI/UITeleport.lua:501`); nếu vẫn gửi thì server trả `S:097-001 <進入結果>` với mã rõ
ràng (bảng đầy đủ ở `KNOWLEDGE.md` §7b-DG): **5 = đang tổ đội**, **2 = hết giờ hôm nay**.

Bot trước đây **không đọc gói này** — bắn 12 lần rồi đoán `nhieu kha nang HET GIO DI GIOI hom nay`.
Ca thật 07/09 party 17, hai dòng liền nhau tự tố:

```
00:37:20 [chutam] SOAT LAI thay CON 120 phut DG (server: da dung 0/120)
00:38:31 [chutam] VAO DI GIOI THAT BAI sau 12 lan -> nhieu kha nang HET GIO DI GIOI hom nay
```

Đoán sai → đánh dấu "xong DG" → cả party kẹt chéo, ba lệnh chọi nhau:

```
01:04:05 [chutam] xong DG, DUNG YEN cho party (1/5)
01:04:00 [chusau] (LEADER) CHO ca party ve Tương Dương (1/5)
01:03:29 [chusau] (LEADER) chu708 KET 91s khong ve duoc Tương Dương -> EP RELOGIN de cuu party
01:04:19 [chubay] Di Gioi con lai: 1h20m (da o 39 phut)
```

**Luật rút ra:** server có gói báo lý do thì **đọc gói**, đừng suy từ triệu chứng. Suy sai ở đây
không dừng lại ở một acc — nó thành trạng thái "xong DG" giả, kéo cả party vào thế kẹt.

Chỉ mã **1** (cấp không đủ) và **2** (hết giờ) mới được dừng hẳn; 3/4/5 là tạm thời, phải thử lại.

Neo bằng `tests/test_vao_di_gioi_giong_client.py`.
