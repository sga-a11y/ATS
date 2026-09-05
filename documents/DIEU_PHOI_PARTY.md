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
