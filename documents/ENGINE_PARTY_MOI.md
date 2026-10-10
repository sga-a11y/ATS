# Engine party — một luồng quyết định cho mỗi party

## Trạng thái mã sau yêu cầu ngày 24/09/2026

Tất cả party dùng `PartyEngine`. Đã bỏ vòng điều phối toàn cục, watcher party,
luồng gửi lệnh kênh riêng và kịch bản quyết định trong `run_account`.
Không còn cơ chế đổi ngưỡng để quay về engine cũ.

Mỗi nhịp engine đọc trạng thái, chạy luật cấp party, cập nhật kết quả và giao
thao tác cho các worker. Worker dùng lại luồng account đang có để thực hiện
thao tác game có thể chặn; không tự lập kế hoạch cho party. Các chế độ train,
Di Giới, event, city, stand và lệnh đi map thủ công đi qua cùng engine.

Mã Python PC/APK đã đồng bộ. Việc kiểm tra mã và unit test không đồng nghĩa
đã build hay xác minh trên tài khoản game thật. Kế hoạch và phạm vi kiểm tra:
[Single party controller](../docs/superpowers/plans/2026-09-24-single-party-controller.md).

### Sửa sau chạy thật 27/09

- **Mọi việc chặn phải huỷ được.** `fc_gom` (2K lệch tầng → đi bộ về tầng gom) trước đây gọi
  `regroup_to_event_start` mà không có `abort`. Party 5: engine ra `fc_gom` lúc 11:10:34, một giây
  sau cả đội đã chung tầng và engine giao `nghi`, nhưng 3 member vẫn đi bộ về 12922 suốt 2 phút
  (bị kéo lên 12924 vẫn plan lại đường), rồi bị kick mã 14, party vỡ và kẹt `lap_party`. Giờ
  engine truyền `con_lam` → `abort` xuống tận `follow_smart_scene_route`.
- **Party bị bỏ khỏi cấu hình thì engine tự dừng** (`_cap_nhat_engine`), không chạy tiếp nhịp
  rồi văng `IndexError` ở `party_accounts` (party 21, STOP 26/09 18:41: 20 traceback).
- Test: `tests/test_fc_gom_huy_duoc.py`.
- **2K thua/xong thì cả đội ra khỏi tháp.** `VIEC_DOI_THUONG` từng nằm trong `VIEC_DI_CHUYEN`
  (danh sách việc đi bằng teleport, trong tháp bị đổi thành `nghi`). Với 2K, `doi_thuong` là đi
  bộ ra (`exit_event`) rồi tắt acc, nên bị chặn là sai. Party 7/11/13 (27/09) thua boss Đỉnh Tháp
  12934 (10/10 ô phe mình HP 0) rồi đứng yên. Party 27 thì chỉ acc đã văng ra ngoài được thoát.
  Lỗi có từ 18/09 (`85ec4e8`). Test: `Test2KThuaThiRaKhoiThap` trong `tests/test_engine_moi_2k.py`.
- **Event không có leader bot** ("Bot đứng yên, chờ nhận lời mời từ ..."): làm y engine cũ —
  chưa ở map event thì `vao_event`, đã ở map event thì `lap_party` (acc không phải leader chỉ mở
  cửa nhận lời mời của người trong whitelist), event xong vẫn `doi_thuong`. Trước đó engine đổi
  mọi việc thành `nghi` nên party 7 (27/09) đứng ở 12003, không vào event
  (`party_modes._event_cho_moi`). Đã vào đội người thật thì `nghi` (đứng yên theo họ).
- **Về thành đứng yên** (mode `city`, APK "Đứng yên (Tương Dương)"): lệch map thì `city` (tự về thành),
  NHƯNG đang trong đội (`so_member > 0`, bị người mời kéo đi) thì `nghi` — theo đội, không rời đội bay về.
  Rời đội/giải tán xong mới tự về thành lại (29/09).
- **Đội trưởng trong whitelist KHÔNG phải "party lạ"**: `_engine_routine_decisions` trước chỉ coi
  chính mình + leader bot là hợp lệ, không có leader bot thì mọi đội trưởng đều "lạ". Party 7
  (27/09): 4 acc nhận lời mời người thật 15:57:24, lên tầng 12923, roster server về 15:57:39 →
  15:57:40 cả 4 bị giao `roi_party_la` (lặp mỗi giây). Engine cũ không có bước này. Giờ hỏi
  `client.doi_truong_hop_le()`: mình / leader bot / người mình đã nhận lời mời / tên trong
  `leaders_for` — cùng luật với `_accept_party_invite`. Test: `TestDoiTruongWhitelistKhongPhaiPartyLa`
  trong `tests/test_apk_event_co_leader.py`.
- **Mode event luôn đánh quest mode**: `_cap_nhat_tuy_chon_client` đặt lại
  `state.force_quest_mode` và `default_pet_role = "quest"` như `run_account` cũ lúc login.
  Thiếu hai cờ này thì party không có leader bot đánh event bằng combo train, và pet bị trả về
  vai train. Test: `tests/test_event_quest_mode_engine.py`.

### Sửa 07/10 — mode `stand` / `city` không đi phó bản đội

- Báo lỗi `BL-1007-8C5F` (party 1, mode stand: "login tại chỗ k đi phó bản đội"). Cả 4 acc xong
  daily lúc 13:35:43, ô 5 chưa làm, engine ra `pb_doi`/`pb_doi_theo`. Nhưng `party_modes.decide_mode`
  của stand (và city) ép mọi việc ngoài `lap_party`/`doi_kenh` thành `nghi`. Worker đang `nghi` sẵn
  nên log im hẳn. Lỗi có từ 26/09 (`90bfb10`). Engine cũ thì vẫn chạy PB đội lúc login cho cả hai mode.
- Giờ stand/city cho `pb_doi`/`pb_doi_theo` đi qua (kể cả lúc đang đánh, giống mode train). Event
  `chaos_vs` không đổi.
- Stand/city **đánh PB tại chỗ**: bỏ bước "về thành tập kết trước" của nhánh PB (cờ
  `pb_tai_cho`, đặt trong `_cap_nhat_engine` theo `mode`). Thành tập kết ở hai mode này có thể là
  thành còn sót lại từ phiên train trước, còn `ve_thanh` thì bị ép thành `nghi` → kẹt mãi. Mode
  train vẫn về thành trước (user chốt 21/09).
- Test: `tests/test_stand_city_pb_doi.py`.

Phần dưới ghi lại thiết kế ban đầu và các tình huống lịch sử. Những mô tả
chạy song song hoặc fallback engine cũ trong lịch sử không còn áp dụng.

## 1. Vì sao làm

Không phải vì hiệu năng. Đo trong repo này: 1 quyết định đánh = **0,014ms** (p99 0,024ms),
5 acc = 0,1ms trên ngân sách `submit_delay` 500ms. Thread không phải nút thắt.

Lý do là **lệnh không tới được acc**. Trong `run_account` (5.690 dòng):

| | số |
|---|---|
| vòng lặp | 57 |
| vòng CHỜ (có `sleep`/`wait`) | 39 |
| vòng chờ **không có hạn** (kẹt được mãi) | **21** |
| trong đó **điếc với `reform_gen`** | **14** |

Mỗi vòng chờ phải *tự nhớ* nghe 4 loại lệnh (kênh · `reform_gen` · `rally_gen` · `cmd_gen`)
⇒ 21 × 4 = 84 ô phải nhớ, hiện lấp được ~11. Mỗi lỗi user báo là **một ô trống**, vá xong còn 70 ô.

**Ca đẻ ra tài liệu này — party 11, 15/09** (`luumuoi` treo 64 phút, party kẹt 22 phút):

```
11:24:17 [luumuoi] Dungeon: con 1 luot FREE (flag 0x3030) -> vao FREE
11:25:22 [luumuoi] (member) ca party xong dungeon          <- IM TUYỆT ĐỐI từ đây, 0 dòng/64 phút
12:27:51 [luusau]  (LEADER) -> REFORM party (gen 30)        <- leader làm đúng, lần thứ 8 liên tiếp
12:27:51 [luusau]  reform: dieu phoi bao GOM -> thoi moi    <- không mời vì member lệch map (L17)
12:27:51 [party 11] REFORM gen -> 30 ... [23011, 23851] -> gom ve cung map/kenh
```

`do_daily_dungeon()` phải `leave_party()` (PB đơn bắt buộc solo) → party vỡ → `luumuoi` rơi vào
vòng chờ lời mời `while not st["invited"].is_set()` — vòng này nghe lệnh **kênh** và **`rally_gen`**,
**không nghe `reform_gen`**, mà lệnh gom map lại đi bằng `reform_gen`. Ba bên đều "đúng luật" nên
kẹt vĩnh viễn: điều phối ra lệnh đều đặn 3 phút/lần, leader về thành chờ, member điếc ở bãi.

**Gốc không phải "mỗi acc một thread". Gốc là: mỗi acc tự quyết định lúc nào thì nghe lệnh.**

## 2. Nguyên tắc

Giữ nguyên **L0–L17** trong [RULE_DIEU_PHOI.md](RULE_DIEU_PHOI.md). Engine mới KHÔNG nới luật nào —
nó chỉ làm cho việc *nghe lệnh* không còn phụ thuộc vào acc đang đứng ở đoạn code nào.

- Điều phối quyết, acc thi hành (L1). Không đổi.
- Đủ party rồi làm gì thì làm; party hỏng thì gom bằng được (L0). Không đổi.

## 3. Kiến trúc: 1 luồng quyết định + N luồng thi hành

```
        ┌──────────────── PartyEngine (1 thread / party, nhịp 1s) ─────────────────┐
        │  đọc trạng thái thật của 5 client  →  quyet_dinh()  →  giao việc          │
        │  KHÔNG có vòng chờ nào ở đây: mỗi nhịp chạy hết rồi trả về                │
        └───────┬─────────────┬─────────────┬─────────────┬─────────────┬──────────┘
                │             │             │             │             │
            Worker acc1   Worker acc2   Worker acc3   Worker acc4   Worker acc5
            (1 thread mỗi acc: chạy việc CHẶN, có thể bị HỦY giữa chừng)
                │             │             │             │             │
            GameClient    GameClient    GameClient    GameClient    GameClient
            (bot/client.py — GIỮ NGUYÊN, không sửa một dòng)
```

**Vì sao không phải "1 thread làm tất"**: một acc mất gói sẽ làm đứng cả party, và một exception
giết luôn 5 acc. Tách thi hành ra worker thì giữ được cách ly lỗi của engine cũ, mà quyết định
vẫn tập trung.

### Luồng quyết định (`PartyEngine.nhip()`)
- Hàm **thuần**: `(trạng thái 5 client, state party) -> danh sách việc`. Không I/O, không `sleep`.
- Vì không chặn, **mọi lệnh đều được xử lý ở nhịp kế tiếp** — trễ tối đa 1 giây. Không tồn tại
  khái niệm "vòng chờ điếc".
- Thứ tự quyết định giữ đúng chuỗi user chốt từ đầu:
  `lệch map → đồng bộ map · lệch kênh → đồng bộ kênh · cùng map cùng kênh → lập party · đủ party → đi train`

### Luồng thi hành (`AccWorker`)
- Hàng đợi **1 việc tại một thời điểm**; việc mới thay việc cũ.
- Mọi việc phải nhận được cờ hủy. `client.py` đã có sẵn đường này: `navigate_to(..., abort=...)`,
  `follow_smart_route(..., abort=...)`, `enter_di_gioi_safe` kiểm `self.running`.
- Việc = gọi thẳng hàm có sẵn trong `GameClient` (`do_daily_dungeon`, `do_world_boss_all`,
  `enter_di_gioi_safe`, `navigate_to`, `switch_channel`…). **Không viết lại thao tác game.**

## 4. Bốn cửa chặn bắt buộc (thiếu là hai engine đánh nhau)

| # | Cửa | Vì sao |
|---|---|---|
| 1 | `_dieu_phoi_quyet` **bỏ qua** party engine mới | hai nguồn ra lệnh cho cùng một party = đúng cái bệnh đang chữa |
| 2 | `run_account` **không chạy** cho acc thuộc party mới | tránh hai luồng cùng điều khiển một client |
| 3 | State **riêng**, không đụng `_party_state` của engine cũ | tránh đua ngầm giữa hai cơ chế |
| 4 | **APK giữ engine cũ** | Android chạy chung file này; chỉ chuyển sau khi PC chứng minh |

GUI đọc `_party_state` để vẽ bảng theo dõi / "chú ý" / nút Stop ⇒ engine mới phải **xuất bản**
cùng dữ liệu đó ở dạng chỉ-đọc, nếu không user mù 14 party.

## 5. Chọn engine

Hằng số một chỗ:

```python
PARTY_ENGINE_MOI_TU = 31     # party số 31 trở đi dùng engine mới (0 = tắt hẳn)
```

Đặt `0` là toàn bộ về engine cũ ngay — đường lui trong một giây, không phải sửa code rải rác.

## 6. Tiêu chí thắng thua (định TRƯỚC, không cãi bằng cảm giác)

Đo trên `party.log`, so **party 1–20 (cũ)** với **21–56 (mới)**, cùng khung giờ:

| đo | ghi chú |
|---|---|
| % thời gian party đủ 4/4 | chỉ số chính |
| số lần `MAT PARTY` / giờ | |
| số lần lệch map kéo dài > 3 phút | |
| **số acc im > 5 phút** | chính là bệnh party 11 |
| lượt PB đơn / WB / Dị Giới hoàn thành / acc | không được kém đi |

**Lưu ý khi đọc số**: 14 party mẫu nằm ở **14 server khác nhau** (dong_trac, luu_bi, ton_quyen…),
tải mỗi server một khác ⇒ so theo tỉ lệ, đừng so số tuyệt đối.

**Hạn**: sau 2 tuần engine mới không thắng rõ ⇒ bỏ, quay về hoàn thiện engine cũ. Không nuôi
hai engine vô thời hạn — mọi lỗi sẽ phải sửa hai lần.

## 7. Thứ tự làm

1. ~~Khung `PartyEngine` + `AccWorker` + 4 cửa chặn + xuất bản state cho GUI~~ — **XONG**
2. ~~Test nhịp quyết định + test chặn engine cũ không đụng party mới~~ — **XONG** (71 test riêng,
   gồm bài diễn tập lại đúng ca party 11: `tests/test_engine_moi_khong_ket_nhu_party11.py`)
3. ~~Chạy **2 party** trước (`PARTY_ENGINE_MOI_TU = 53`), đọc log 1 ngày~~ — **XONG**
4. ~~Hạ ngưỡng dần: 53 → 49 → 45 → **41**~~ — **XONG** (16/09)
5. Đường đi của ngưỡng: 53 → 41 → 31 (17/09 sáng) → 51 (17/09 chiều, thu lại) → **21**
   (20/09) ← **đang ở đây**, 36/56 party.
   Mỗi lần mở rộng đều sau một đợt sửa theo log thật; để hẹp thì mỗi lần hỏng ít thiệt hại,
   để rộng thì bắt lỗi nhanh hơn.
6. So bảng tiêu chí ở mục 6 rồi mới quyết định có mở rộng xuống party 1–20 hay không.

**Một ngày sửa theo log thật (17/09)** — mọi lỗi đều cùng một họ: engine ra lệnh **cấp party**
nhưng chưa tính tới việc acc **đang dở một việc dài** (đi đường, đánh nhau), hoặc tự nghĩ ra
phép tính thay vì gọi lại hàm flow cũ đã có:

| ca thật | gốc |
|---|---|
| p43 tele qua lại thành ↔ bãi | `gom`/`dong_bo` là **trạng thái**, lệnh thật đi bằng `reform_gen`/`resync_gen` |
| p44/p45 mỗi đứa một thành | dùng `_pick_start_city` thay vì `chot_thanh_tap_ket` (thành của chính route) |
| p44/p45 kẹt sau khi đi mở thành | `_o_thanh_di_qua` hỏi nguồn khác → thống nhất `diem_gom_hien_tai` |
| p42 không ra bãi | đủ đội rồi vẫn ép người kéo về điểm gom → vòng vô tận |
| p56 vừa đánh vừa đòi tele | không giao việc di chuyển cho acc **đang trong trận** |
| p51 leader lộn về thành | đang giữa đường thì **đi bộ tiếp**, không `follow_smart_route` lại từ thành |
| 60 acc mất nhiệm vụ ngày | engine mới không chạy khối "việc hàng ngày" → thêm `VIEC_DAILY` |
| PB tổ đội hoãn 98% số lần | bỏ cửa hoãn còn sót (boss/PB đơn đã bỏ từ 14/09) |
| p45 không đánh PB đội | nhánh PB đội nằm **sau** `dp_viec` nên không bao giờ chạy tới |

### Engine mới hiện làm được gì

| việc | trạng thái |
|---|---|
| việc vặt sau login (PB đơn, boss TG, boss quân đoàn, vận tiêu, nhiệm vụ ngày, dọn túi) | có |
| vào Dị Giới + đếm giờ theo **đồng hồ server** + đổi pha DG → train | có |
| trong Dị Giới chạy lòng vòng tìm quái — **chỉ LEADER** chạy, member đi theo (y engine cũ) | có |
| đồng bộ map (về map đông người nhất, hoà thì theo leader / điểm tập kết đã chốt) | có |
| đồng bộ kênh | có |
| lập party (leader mời, member chỉ mở cửa nhận) | có |
| ra bãi quái rồi mới đánh | có |
| **phó bản tổ đội (lv20/50/80/110)** | có |
| mode event (40NPC, loạn đấu) | chưa cần — 14 party mẫu không có mode này |

**Phó bản tổ đội đi đường lập đội RIÊNG, không dùng party thường** (user 15/09: *"đường lập pt PB
nó khác với lập pt đi train"*). Theo `KNOWLEDGE.md`:

| | party thường | phòng PB |
|---|---|---|
| mời | `0x0d/0900` | `Dungeon.SendInvite` → `0x2f/0800` |
| member phải làm gì | mở gate `set_party_invite_ready` | **không gì cả** — `_on_dungeon` tự accept `0x2f/0f00` → join room `0x2f/0300` → ready `0x2f/0b00` |
| điều kiện | cùng map + cùng kênh | *"KHÔNG bắt buộc check gắn như party thường vì server/client cho mời theo roleId đã biết"* |

Nên trong nhịp quyết định, PB tổ đội đứng **trước cả chuỗi gom** — không đợi cùng map, cùng kênh
hay đủ party thường. Bắt gom đủ 4/4 rồi mới cho đánh PB là tự đặt thêm điều kiện game không đòi,
và mỗi phút gom là một phút có thể mất lượt PB.

Level còn lượt đọc từ **đồng hồ server** (`team_dungeon_remaining` ← `mission_steps[daily_flag]` ←
`0x18 sub 0x06`), không tự đếm — acc có thể đã đánh ở máy khác/phiên trước.

## 8. Điều KHÔNG làm

- Không sửa `bot/client.py` (3030 test đang phủ nó).
- Không sửa engine cũ trong lúc dựng engine mới, trừ 4 cửa chặn.
- Không chuyển APK cho tới khi có số liệu.
- Không xoá `run_account` — nó là bản đối chứng, và là đường lui.

---

## 21/09/2026 — Bước 1: luật cấp party đã chuyển vào ENGINE

User: *"chuyển về cùng 1 thread thì để cái điều phối làm lồn gì nữa, thread biết hết tất cả thông
tin rồi thì nó phải nắm vai trò điều phối luôn"* và *"về lâu dài tao sẽ xóa engine cũ và điều phối"*.

### Trước

Quyết định nằm ở **ba nơi**, nơi thứ ba engine mới không bao giờ chạy:

| Nơi | Ai chạy |
|---|---|
| `party_engine.quyet_dinh()` | engine mới |
| `_dieu_phoi_quyet()` — 210 dòng, 19 nhánh | cả hai |
| rải rác trong `run_account()` — 5471 dòng | **chỉ engine cũ** |

Đó là nguồn của cả loạt lỗi "flow cũ có mà engine mới không có" (p41 PB thiếu người, p43 kẹt kênh,
p55 lập party khi thiếu acc…). Đếm được **31 quyết định cấp party** còn kẹt trong `run_account`.

### Sau

`party_engine.quyet_dinh_cap_party(anh) -> (viec, ly_do, HieuUng)` — **hàm thuần**, giữ nguyên
19 nhánh và toàn bộ chú thích ca hỏng thật. `_dieu_phoi_quyet` giờ chỉ còn ba việc, **không còn
luật nào**:

```
1. CHUP ANH   `_chup_anh_cap_party`  - đọc client/state
2. HOI ENGINE `quyet_dinh_cap_party` - hàm thuần
3. THI HANH   `_thi_hanh_hieu_ung`   - làm những thay đổi trạng thái mà quyết định kéo theo
```

`HieuUng` mang mọi tác dụng phụ ra ngoài: `doi_pha_train`, `reset_joined`, `kenh_hong`,
`rut_reform`, `dang_gom`, `nguoi_keo`, `chot_tang_gom`, `chot_2k_xong`, `xoa_nhip_acc`, và ba mốc
thời gian (`lech_tu`, `het_lech_tu`, `o_thanh_tu`). Hàm quyết định **không đọc đồng hồ** — giờ
truyền vào qua `anh.bay_gio`.

### Việc chuyển làm lộ một luật suýt mất

Test `test_DG_party_du_va_cung_kenh_thi_khong_resync` bắt được: bản chuyển đầu tiên **đánh rơi**
cửa *"trong DG, party ĐỦ + cùng kênh thì đứng hình không được resync"*. `resync_gen` chỉ làm được
một việc — bắt mọi member `leave_party()` rồi mời lại — nên với party đang lành đó là **đập đội**.
Chính nó làm leader *"mời 2198s chưa đủ party (2/4)"* đêm 10→11/09. Đã khôi phục.

> Đây là lý do 34 test neo-source đỏ khi chuyển **không được sửa cho xanh lấy lệ**: một trong số
> đó là luật thật bị mất.

### Ba mươi tư test neo-source đã dời neo

Chúng neo luật bằng cách đọc `run_party_digioi.py`. Luật dời thì neo dời theo — đọc
`bot/party_engine.py`, và tên việc cấp party đổi `VIEC_*` → `DP_*`. **Không nới lỏng phép kiểm
nào**: các phép so thứ tự nhánh, đếm số chỗ ghi, kiểm "chỉ một nơi được quyết" đều giữ nguyên ý.

### Còn lại của lộ trình

2. Kéo **31 quyết định** còn kẹt trong `run_account` vào `quyet_dinh_cap_party`
3. Chuyển `_dieu_phoi_chot_kenh` (241 dòng) vào engine; xoá `_dieu_phoi_loop`

Xong bước 3 là xoá được điều phối, engine cũ chỉ còn là code thi hành.

### "Không thấy đồng đội" mà cùng kênh + chắc kênh → bỏ qua `dong_bo` (28/09)

`quyet_dinh_cap_party`, nhánh `ai_lech_instance`: chỉ ra `dong_bo` khi còn lý do nghi số kênh
(lệch kênh, hoặc có acc `kenh_dang_chac()==False`). Cả party **cùng một kênh và đều chắc kênh**
(`AnhCapParty.kenh_chac_ca_party`) thì bỏ qua nhánh này, xuống thẳng bước lập party (`moi`).

Lý do: "thấy nhau" đo bằng `0x03` / `S:001-001` là **tầm nhìn** (theo khoảng cách), không phải
kênh — đứng xa nhau trong thành là mất nhau dù cùng kênh; lời mời tổ đội không cần tầm nhìn.
Instance và kênh là một (CORE_FLOW) → không có gì để đồng bộ.

Ca thật party 1, 28/09: cả 5 `@21011/k1`, roster `0/4`, `sga008`/`tuyetdo` "không thấy" →
`dong_bo` → mọi acc `nghi`, `_giao_kenh_dich` không có đích, chốt kênh không bump reform vì
việc ≠ `moi` → đứng im ở Giang Lăng 75+ phút, không một dòng log.

## Bấm "Lưu" setting khi đang chạy — nạp config nguyên khối (28/09)
`reload_config` (gui.py) KHÔNG còn dùng `importlib.reload(config)`: reload chạy lại config.py ngay
trên module đang dùng, giữa chừng `PARTIES` chỉ còn 1 party mẫu → `_cap_nhat_engine` tưởng party bị
xoá → dừng engine → cả party thoát (ca thật 28/09: 37 party lúc 09:13:24, 35 party lúc 09:25:27,
log `ENGINE: party khong con trong cau hinh -> dung engine`).
Giờ `_nap_lai_config_nguyen_khoi()` chạy config vào module TẠM rồi chép sang một lượt. Party không đổi
setting chạy tiếp; party đổi setting quan trọng (mode/map/server...) vẫn bị stop như cũ.
Test: `tests/test_gui_nap_lai_config_nguyen_khoi.py`.

## Đổi kênh: dính trận trên đường ra safe không bị rút việc (28/09)
Ca thật party 1: `sga008` được giao `doi_kenh` → tập kết thành `ve_safe` → đi qua bãi quái dính trận →
`_giao_kenh_dich` hạ về `nghi` vì đang combat → `navigate_to` abort → trận xong lại giao `ve_safe`.
Đo: 79/79 lần lật trùng một trận `BO CHAY`, 61 lần abort, acc không bao giờ tới safe → party lệch kênh mãi,
không lập lại được party.
Giờ acc **đang làm `ve_safe`** thì dính trận vẫn giữ `doi_kenh` (`_ra_safe_engine_moi` tự chờ hết trận
rồi đi tiếp). Lệnh tay / lệnh tự động đang chạy vẫn hạ về `nghi` như cũ.
Thêm log `ENGINE: <acc> lech kenh (a -> b) nhung CHUA giao doi_kenh: <ly do>` (khi lý do đổi, nhắc lại mỗi
60s) để đo ca acc lệch kênh đứng im (nasau/tuyet cùng ngày, chưa chốt gốc).
Test: `tests/test_dieu_phoi_tu_gui_lenh_doi_kenh.py::test_battle_while_walking_to_safe_keeps_channel_action`.

## Không phải `train` thì leader dừng chạy vòng (02/10)
Ca thật party 1: party vỡ giữa Dị Giới (`roster leader=0/4`), engine giao `lap_party`/`nghi` đúng luật
2300 lần, nhưng `nanam` (leader) vẫn `Run-around` từ 07:21 tới 08:39 → 20 trận g=482..501 chỉ 1 người.
Gốc: `start_run_around()`/`stop_run_around()` chỉ được gọi trong nhánh `VIEC_TRAIN` của `thi_hanh`,
nên vòng chạy cũ sống sót qua mọi việc khác.
Giờ đầu `thi_hanh`: việc khác `VIEC_TRAIN` mà client đang chạy vòng (`_running_route`) → `stop_run_around()`.
Đủ party, engine giao lại `train` → nhánh train tự bật lại vòng chạy.
Chưa chốt: vì sao gom party trong DG thất bại >1 tiếng (leader báo server CHƯA HỀ thấy member quanh mình).
Test: `tests/test_party_engine_vong.py::TestKhongPhaiTrainThiDungChayLongVong`.

## Dị Giới SOLO — làm y engine cũ (09/10)
Ca thật BL-1008-C452 (08/10, APK, party 1 tick Dị Giới Solo): cả 5 acc `(member) vao world` (solo →
không có leader), engine vẫn đếm cần 5 member và giao `lap_party` **511 lần** trong 1,5 phút, 0 lần
`Run-around` → cả party đứng im trong DG 49942 tới khi user Stop. Engine mới (90bfb10, 26/09) làm rơi
mất toàn bộ nhánh `elif digioi_solo` của engine cũ.
Giờ (giống engine cũ):
- `_mode_can_lap_doi()` trả `False` khi `mode == "digioi"` và `digioi_mode == "solo"` → `n_members = 0`,
  điều phối `lam`, không chốt/đồng bộ kênh, không lập đội, không reform (chung cửa với Loạn Đấu).
- `quyet_dinh` pha DG: `can_bao_nhieu <= 0` → acc nào đã vào DG và còn giờ là `train` ngay, không chờ
  acc khác vào, không đứng vì acc khác hết giờ. (Party 1 acc cũng ra 0 nhưng kết quả như cũ.)
- `thi_hanh` `train` cho acc DG solo (`_train_dg_solo`): tự `start_run_around()` (party thật vẫn chỉ
  leader chạy). Bảo hiểm thuốc: thiếu HP hoặc SP → `flee_mode` + đứng yên; có lại → chạy tiếp.
  Log: `Di Gioi SOLO -> tu chay long vong ...` / `Di Gioi SOLO -> THIEU thuoc ... -> DUNG YEN`.
Test: `tests/test_dg_solo_engine_moi.py`.

## Cửa nhận lời mời party: chỉ giữ khi ĐANG làm việc vặt thật (10/10)

Ca thật 09/10 party 21 (chế độ đứng yên, user mời tay): ba acc được mời lúc **còn** đang làm việc vặt
→ `account_task.__exit__` nhả lời mời ra → vào đội. Riêng `dieutam` xong việc vặt lúc 23:56:04, lời mời
tới lúc 23:56:12 → `Chua san sang vao party -> GIU loi moi` lặp tới 23:57:59, không bao giờ vào.

Gốc: cờ `party_invite_ready` mặc định `False` mỗi lần relogin, chỉ bật khi (a) việc vặt kết thúc mà
**lúc đó đã có** lời mời bị giữ, hoặc (b) engine giao `lap_party`. Lời mời tới **sau** việc vặt thì
không còn ai nhả → phải "mời thật sớm" mới vào được.

Sửa (`client.py` nhánh `0x0d sub09`): giữ lời mời chỉ khi `not party_invite_ready and
dang_lam_viec_vat()` — pha việc vặt đọc từ báo cáo task, không kẹt được. Acc rảnh thì accept ngay
(vẫn qua lọc whitelist `PARTY_LEADERS` trong `_accept_party_invite` như cũ).
Test: `tests/test_party_invite_gate.py` (`test_loi_moi_toi_SAU_khi_viec_vat_xong_van_vao`).

## Pha train mà acc đang trong Dị Giới → về thành trước (10/10)
Ca thật 10/10 party 25 (mode train, cả 5 acc login vào đã ở DG 49942): điều phối thấy "cùng map, lệch
kênh [1, 4, 5]" → `dong_bo` → giao `doi_kenh` **232 lần** trong ~6 phút, đổi kênh thành công **0 lần**
(6 lần `result=3`, còn lại server im). Chỉ ra khỏi DG khi `DUNG HINH qua 240s` ép `gom`. Party 23 cùng
ngày: 1 acc (gclm10) kẹt trong DG ~9 phút.

Engine cũ (`on-20260914-1802`): login không ở map train (kể cả DG) = **sai map** → "CA PARTY ve thanh
don nhau roi KEO toi map train" (`_do_reform` → `go_to_town` → `RA KHOI DG truoc`). Luật "lệch kênh
trong DG thì đồng bộ tại chỗ" chỉ dành cho **pha DG**. Engine mới bỏ bước setup đó nên rơi vào bậc kênh.

Sửa (`party_engine._quyet_dinh_goc`, nhánh `(0c2)`, sau pha DG, trước PB tổ đội / chuỗi điều phối):
- `pha == PHA_TRAIN` và **không** phải mode stand/city (`pb_tai_cho`) → acc nào `trong_dg` nhận
  `ve_thanh`; acc còn lại đi tiếp chuỗi điều phối như cũ. Đang trong trận thì vẫn hoãn (`nghi`) như mọi
  việc di chuyển khác.
- `thi_hanh(ve_thanh)` chưa chốt được thành tập kết mà đang trong DG → vẫn `exit_di_gioi()` (đi bộ ra
  cổng, `flee_mode`), nhịp sau về thành tiếp. Ngoài DG thì giữ nguyên: lệnh rỗng.
Test: `tests/test_pha_train_trong_dg_thi_ve_thanh.py`.
