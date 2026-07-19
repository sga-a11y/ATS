# TS Online Bot - Knowledge Base
> Tổng hợp toàn bộ kiến thức đã khám phá về game TS Online Mobile (com.vtcmobile.gz06)

---

## 0. DEBUG LỖI USER BÁO (bản gửi đi = EXE)

> **User dùng BẢN BUILD (aTSBot.exe), KHÔNG phải dev source.** EXE build bằng `build_product.py`,
> stage source từ repo hiện tại; `bot/config.py` là file placeholder tracked được đóng gói vào exe.

- **User báo lỗi config/hành vi → soi code ship trong build + `bot/config.py` placeholder TRƯỚC.**
- Tài khoản/mật khẩu THẬT nằm ở `accounts.json` (gitignored, KHÔNG đóng gói vào build). `config.py`
  chỉ là placeholder/hằng số game; tuyệt đối không đưa acc thật vào `config.py`.
- **Khi đổi key config từ GUI/run_party** (vd `do_dungeon`->`do_daily`): phải sửa ĐỒNG THỜI các chỗ đọc/ghi
  key đó như `run_party_digioi.py` + `gui.py` + `bot/config.py` placeholder (và Android `config.py` nếu GUI APK dùng key này).
- File JSON ship theo build: `build_product.py` -> `DATA_JSON`. Thêm data mới phải thêm vào đây.

## 1. THÔNG TIN CƠ BẢN

- **Game:** TS Online Mobile — VTC Mobile, engine Unity 2022.3.62f2 + Lua scripts
- **Package:** com.vtcmobile.gz06
- **Game server:** 103.82.28.98:6614 (TCP)
- **Account API:** https://graph.mobiplay.vn

---

## 2. PROTOCOL

### Encoding
- **XOR key:** 0xAD (toàn bộ TCP payload)
- **Header format:** `c0 91 [len_lo len_hi] 00 00 [opcode] [payload]`
- Length = 2 bytes Little-Endian, là tổng kích thước packet (kể cả header)
- **Capture lưu ý:** đừng hardcode tcpdump `port 6614` cho MuMu/mobile. Đã gặp MuMu 12 app
  `com.gsn.getmoney.gl` mở game flow ở port khác (vd `120.138.72.34:10109`) khiến pcap lọc 6614
  chỉ còn header 24B, không có packet. Capture nên bắt `tcp`, rồi `analyze_pcap.py` tự XOR/dò frame
  `c0 91` trong mọi TCP payload.

### Login HTTP (Account API)
```
POST https://graph.mobiplay.vn/accountapiv4/server/login?api_key=<API_KEY>
Body: username=XXX&password=XXX&device_id=XXX&agency_id=1&client_version=1.1&lang=vi&device_os=android
Response: access_token, account_id
```

### Auth Game Server (TCP)
- Sau khi TCP connect đến 103.82.28.98:6614
- Gửi C2S opcode 0x01 (144 bytes)
- Payload chứa: `user_id` + `access_token` dạng UTF-16LE

---

## 3. OPCODES

### Client → Server (C2S)
| Opcode | Ý nghĩa |
|--------|---------|
| 0x01 | Game server login (access_token) |
| 0x0a | Heartbeat (gửi mỗi ~20s) |
| 0x0c | Ready signal trong battle |
| 0x14 | Party action |
| 0x20 | Accept party invite / ready |
| 0x27 | Exit battle |
| 0x32 | **Combat action** (17 bytes) |
| 0x41 | Enter battle (solo/leader) |

### Server → Client (S2C)
| Opcode | Ý nghĩa |
|--------|---------|
| 0x01 | Entity registration |
| 0x03 | Entity join map |
| 0x07 | Entity stat update |
| 0x08 | Damage result |
| 0x0b | **Full stats** (HP/SP max+cur) |
| 0x0c | **Mob info** tại battle start |
| 0x0d | Player state |
| 0x0f | Entity full info |
| 0x14 | Party update |
| 0x27 | Player info (có username) |
| 0x29 | Unknown |
| 0x2b | Unknown |
| 0x2f | Unknown |
| 0x32 | Server combat echo/result |
| 0x33 | **Stats per turn** (HP/SP current) |
| 0x34 | **Battle start** (party mode) |
| 0x35 | **Available actions** (34b) + confirmation (11b) |
| 0x41 | Battle enter confirmed |
| 0x4f | Entity registration small |
| 0x55 | **Unit ready** (1 per char/pet) |
| 0x6e | Entity info |

---

## 4. COMBAT PACKET (C2S 0x32)

```
c0 91 11 00 00 00 32 01 00 [unit] [action_type] [b11] [target_pos] [skill_lo skill_hi] [crc crc]
```

| Field | Bytes | Giá trị | Ghi chú |
|-------|-------|---------|---------|
| unit | 1 | 3=char, 2=pet | |
| action_type | 1 | 1=member, 2=leader | Đọc từ S2C 0x35 |
| b11 | 1 | thường=0 | unknown flag |
| target_pos | 1 | 0-indexed | 0..2 (3mob), 0..4 (5mob) |
| skill_id | 2 | LE uint16 | |
| crc | 2 | varies | server không validate chặt |

---

## 5. BATTLE FLOW

### Solo / Party Leader
```
C2S 0x41 → S2C 0x41 (confirmed)
S2C 0x0c × N (mob info, N = số mob)
S2C 0x0b (char + pet stats)
--- Mỗi lượt ---
S2C 0x33 (stats snapshot)
S2C 0x35 × 7-9 (available actions)
C2S 0x32 × 2 (char + pet actions)
S2C 0x35 × 2 (11b, confirmation)
S2C 0x32 (server result)
```

### Party Member
```
C2S 0x20 (accept invite)
C2S 0x14 (party ready)
S2C 0x03 × N (members join)
S2C 0x55 × (N_players × 2) (units ready)
S2C 0x34 (battle start — thay cho 0x41!)
--- Tiếp theo giống solo ---
```

---

## 6. STATS PACKETS

### LƯỚI BATTLE: 4 HÀNG × tối đa 5 CỘT (KEY cho target + buff)
Mỗi entity trong 0x33 = block `[00][b1][b2][type][2B][00]`. **b1 = HÀNG, b2 = CỘT.**

| b1 | Hàng | Ghi chú |
|----|------|---------|
| 0 | Quái hàng 1 (trước) | b2 = cột quái |
| 1 | Quái hàng 2 (sau) | b2 = cột quái |
| 2 | **Pet** đội mình | b2 = vị trí member (0-4) |
| 3 | **Char** đội mình | b2 = vị trí member (0-4) |

**Combat 0x32 target encoding:** `byte b = HÀNG ĐÍCH`, `target = CỘT`:
- Đánh quái hàng trước: b=0, target=cột | hàng sau: b=1, target=cột
- (Heal/buff đồng đội → b=2 nhắm pet, b=3 nhắm char; target=cột member). 0x35 offer = danh sách CỘT.
- Vị trí nội bộ bot dùng: `pos = b1*10 + b2` (hàng=pos//10, cột=pos%10).
- **CỰC QUAN TRỌNG — offer-space 0x35 KHÔNG luôn 0-indexed:** cột nội bộ `b2` (từ 0x33) LUÔN
  0-indexed (0-4). NHƯNG `target` gửi trong 0x32 phải theo offer-space của 0x35:
  - **Train thường:** 0x35 offer cột `[0,1,2,3,4]` → `target = b2` (giữ nguyên).
  - **PHÓ BẢN TỔ ĐỘI (5 người, 2 hàng quái):** 0x35 offer cột `[1,2,3,4,5]` (1-indexed!) →
    `target = b2 + 1`. Gửi `b2` thẳng = **LỆCH 1 CỘT** → đánh trượt / dồn vào con trâu (HP 2x) →
    quái không chết (đã dính bug này).
  - **SAI LẦM ĐÃ SỬA (đừng lặp lại):** từng dùng `target = b2 + min(offered)` (`_offer_min`) để
    "tự điều chỉnh" — SAI trong thực tế, vì **Dị Giới cũng offer `[1,2,3,4,5]` (min=1) nhưng
    KHÔNG cần +1** (khác phó bản tổ đội cùng dạng offer nhưng CẦN +1) → `min(offered)` không đủ
    để phân biệt 2 context này, làm bot nhắm lệch sang con kế bên (test thực tế: 3 quái liền
    nhau, offer=[1..5], bị target vào con cuối thay vì con giữa). Fix đúng: `_col_reachable` /
    `_resolve_target` (combat.py) — kiểm tra TỪNG cột có thật sự nằm trong offered không (thử cả
    2 quy ước 0-indexed và +1), KHÔNG đoán 1 offset chung cho cả trận.

### S2C 0x33 — Stats per turn
Pattern entries: `03 02 [type] [4-byte LE]`
| type | Hex | Thông số |
|------|-----|---------|
| 25 | 0x19 | HP current |
| 26 | 0x1a | SP current |
| 27 | 0x1b | **INT (tri luc)** — tang dame skill + hoi SP tot khi lam quan su (KHONG tang SP max). Khi CONG DIEM: S2C 0x08 `01 00 1b 01 [val 2B]`. LUC LOGIN: nam trong gói char-info **S2C 0x05** (payload ~252B) tai **payload offset 9** (=pkt[16]). Xac nhan int2.pcap (login 4->5). |
| 205 | 0xcd | HP max |

### Tang chi so (cong diem stat)
- **C2S 0x08:** `01 00 00 00 [stat_id 1B] [amount 1B] 00 00 00 00` — vd tang INT 1 diem = `01 00 00 00 1b 01 00 00 00 00`. Xac nhan int.pcap. Dung cho auto cong diem.

### S2C 0x0b — Full stats
**Char/Pet:** `03 0X [HP_max 4B] [SP_max 4B] [HP_cur 4B] [SP_cur 4B]`
- X=02: char, X=01: pet

**Mob:** offset 31 = HP_max (4B LE), offset 35 = SP_max (4B LE)

**QUAN TRONG — gói 0x0b party (>100B, lúc spawn/start battle) = full-stat TẤT CẢ thành viên:**
- Mỗi block: `[b1][slot][HP_max 4B][SP_max 4B][HP_cur 4B][SP_cur 4B]` (b1=3 char, 2 pet; slot=vị trí battle 0-4).
- **Đây là NGUỒN DUY NHẤT có `SP_max` của đồng đội (cả pet, kể cả nick người chơi tay).**
  `0x33` chỉ có HP_max (0xcd), KHÔNG có SP_max. `0x08` chỉ mang stat CHAR (unit 01), không có pet.
- Quét toàn gói tìm block hợp lệ (validate cur≤max...) → nạp `ally_spmax[(b1,slot)]`.
  Lưu BỀN: `allies` bị `clear()` mỗi `0x34` nhưng gói 0x0b party chỉ tới lúc spawn → phải giữ riêng.
- Xem `state.update_0x0b` + `ally_low_sp` (hồi SP toàn team cho cả pet).

### QUAN TRONG: slot stats trong 0x33 = VI TRI BATTLE (atype), KHONG phai member-index
- self_slot (key b2 doc HP/SP cua minh) PHAI = my_atype (vi tri tran, FILL=[1,3,0,4]).
- Dung idx+1 (vi tri trong member list) = SAI -> doc nham SP/HP cua char khac.
  Trieu chung: SP doc duoc giam 15/luot (cost Hoa Tien cua char KHAC) du minh danh thuong.

### S2C 0x35 — Available actions (34 bytes)
Format: `01 00 [entries: unit action_type target 00 00]`
- Bot đọc entry của unit=3 (char) và unit=2 (pet) → lấy action_type

---

## 7. SKILL DATABASE

| skill_id | Tên | Type | SP | Target | Ghi chú |
|----------|-----|------|----|--------|---------|
| 10000 | Đánh thường | attack | 0 | enemy | Always available, fallback |
| 12003 | Hỏa Tiễn | attack AoE | 15 | enemy | Splash ngang (target ± 2 bên), priority=10 |
| 17001 | Phòng thủ | defense | 0 | self | Giảm dame nhận, cả char+pet |
| 17997 | Bỏ chạy | flee | 0 | self | 0x4651. Thoát khỏi trận. Gửi 0x32 skill này cho cả char (b=3,target=2) + pet (b=2,target=2). Xác nhận flee.pcap |
| 11004 | Thanh Lưu | heal | 22 | 1 ally | Hồi HP+SP 1 người, char only |
| 11010 | Toàn Trị Liệu | heal AoE | 42 | all ally | Hồi HP toàn party, char only |
| 12006 | ??? | ? | ? | ? | Pet skill, chưa khám phá |

### Targeting Rules (TRAIN - dùng CHUNG đánh thường + combo để đồng target → combo ăn)
- **Chọn target (đánh thường & combo):**
  1. Block 3 quái liền nhau cùng hàng (đầu tiên) → con **GIỮA** (AoE trúng cả 3)
  2. Không có → block 2 quái (đầu tiên) → con **ĐẦU** (thấp nhất)
  3. Không có → con **LẺ** đầu tiên
  - ⚠️ KHÔNG focus lowest-HP (mỗi unit ra target khác nhau → vỡ combo)
- **Heal AoE:** dùng khi nhiều ally bị thương (Toàn Trị Liệu)
- **Defense:** khi HP thấp (tùy config)

---

## 7b. PARTY SYSTEM (đã tách lệnh riêng)

> Quan trọng: party có **quân sư (strategist)** → hồi SP mỗi turn đánh. Đây là lý do SP regen.

**Entity ID:** mỗi nhân vật có entity 8 bytes (vd self=e6a1d6f8808d0300, gaha=b59fd6f8808d0300). Entity động theo session — bot phải đọc từ S2C khi join.

**Cấu trúc lệnh party C2S:** `c0 91 11 00 00 00 0d [SUB] 00 [self_entity 8B]`
Byte SUB quyết định hành động. Tất cả reference **self entity** (target ngầm định = member còn lại trong party 2 người).

| Hành động | Dir | Opcode | SUB | Cấu trúc | Ghi chú |
|-----------|-----|--------|-----|----------|---------|
| Mời vào party | C2S | 0x0d | **07** | `0d 07 00 [member_entity 8B]` | MỜI THEO ENTITY người được mời — ĐÃ XÁC NHẬN (invite_dg.pcap). KHÔNG dùng 0x52/index! |
| Set quân sư | C2S | 0x0d | **05** | `0d 05 00 [self_entity]` | cho SP regen — ĐÃ XÁC NHẬN |
| Demote → thường | C2S | 0x0d | **06** | `0d 06 00 [self_entity]` | bỏ quân sư — ĐÃ XÁC NHẬN |
| Kick member | C2S | 0x0d | **0a** | `0d 0a 00 [self_entity]` | đuổi member — ĐÃ XÁC NHẬN (isolated) |
| Giải tán party | C2S | 0x0d | **04** | `0d 04 00 [member_entity]` | reference entity member (KHÁC kick) — ĐÃ XÁC NHẬN |
| Chuyển chủ party | C2S | 0x0d | **09** | `0d 09 00 [self_entity]` | chỉ chuyển được cho quân sư — ĐÃ XÁC NHẬN |
| Nhận lời mời (notify) | S2C | 0x0d | **09** | `0d 09 00 [self_entity]` | server bao co loi moi (cung sub 09 nhung chieu S2C) |
| Accept lời mời | C2S | 0x0d | **08** | `0d 08 00 01 [self_entity]` | byte 01 = dong y (00 = tu choi?) — ĐÃ XÁC NHẬN |

**self_entity:** doc luc login tu packet 0x69 (`69 01 00 [entity]`) hoac tu chinh notify 0x0d sub=09.
| Thành viên join | S2C | 0x0d | 05 | `0d 05 00 [member_entity][self_entity]` | danh sách party update |
| Thông báo join | S2C | 0x0d | 0a | `0d 0a 00 01 08 [name UTF-16LE]` | kèm username |

**Lưu ý:** Trong party 2 người, target ngầm định. Party 3+ người cần test thêm để biết field chỉ định member cụ thể.

## 7c. TELEPORT VỀ THÀNH (opcode 0x44)

```
C2S 0x44: c0 91 0c 00 00 00 44 01 00 [city_id 2B LE] [flag 1B]
```
- **city_id:** ID thành (2 byte LE)
- **flag:** byte cuối (00/02/03 — có thể là index/biến đếm, chưa rõ)

**City IDs đã biết:**
| Thành | city_id (hex) | dec |
|-------|---------------|-----|
| Trác Quận | 0x2ee1 | 12001 |
| Ng.Thành | 0x2f1d | 12061 |
| Cự Lộc | 0x2eeb | 12011 |

Lưu ý: phải thoát/giải tán party mới teleport được.

## 7d. DI CHUYEN & DOI MAP

**Di chuyen:** C2S 0x06 = `c0 91 0e 00 00 00 06 01 00 01 [x 2B LE] [y 2B LE]`
- Gui toa do dich (x,y) -> nhan vat tu di toi do
- Server gui 0x06 lien tuc cap nhat vi tri cac entity

**!!! TRONG PARTY: member TU DONG DI THEO leader, KHONG di chuyen duoc (0x06 bi vo hieu).**
- => Chi can DI CHUYEN LEADER. Member chi auto-follow + auto-fight.
- Member bot KHONG can wander. Chi co leader (user hoac 1 bot-leader) di chuyen de trigger gap quai.
- Vi the member bot bi keo vao tran cua leader du dung yen (no auto-follow toi cho danh).

**Doi map qua cong (gate):** KHONG co lenh thoat rieng. Chi can DI CHUYEN toi dung toa do cong -> server tu doi map.

**Cong thoat DI GIOI:** toa do ~**(270, 210)**. Duong di mau: (749,592)->(650,470)->(430,350)->(270,210).
- Toi cong -> map tu doi. Co C2S 0x14 (`14 04 00 01 00`, `14 08 00 01 00`) khi toi cong.
- C2S 0x61 (`61 01 00 01` / `61 02 00 02`) + C2S 0x0c (`0c 01 00`) = handshake scene khi map load xong (sent SAU khi doi map, tren MOI map).

**VAO DI GIOI:** KHONG phai 0x44. Vao qua NPC/dialog -> KHONG ra 1 packet co dinh (chi thay 0x61/0x27/0x0c scene handshake). KHO auto bang packet.
- !!! KHONG vao Di Gioi duoc khi DANG TRONG PARTY. Phai THOAT PARTY truoc.
- FLOW DUNG (moi acc): thoat party -> vao Di Gioi (solo) -> chuyen cung 1 channel (0x07) -> lap lai party (invite + set quan su) -> cay.
- => Moi bot VAN CAN tu vao Di Gioi (khong follow duoc vi phai thoat party).
- **VAO DI GIOI = goi API HTTPS toi 103.82.31.230:443** (KHONG phai TCP game server!). Vao bang 1 NUT menu (tu bat ky dau). Da correlate: click nut -> HTTPS 103.82.31.230 (+41s) -> game server doi scene (+47s). 
- **Dị Giới hộ phù / socket 10109 (capture MuMu 12 2026-07-16):** cặp raw
  `90 00 03 01 03 fa` -> `80 00 04 01 03 fa 00` trên luồng
  `10.0.2.15:49096 <-> 120.138.72.34:10109` lặp đều mỗi 10s (+7.47s, +17.47s, ...),
  nên đây gần như chắc là heartbeat/keepalive của gateway mobile, **KHÔNG phải gói dùng hộ phù**.
  Capture TCP-only từ login -> vào game -> dùng hộ phù vẫn chỉ thấy heartbeat và không có frame TS
  `c0 91`/XOR. Hộ phù có thể đi qua UDP/non-TCP hoặc kênh khác; script công ty đã đổi sang
  `tcpdump -i any -w ... not port 5555` để bắt lại toàn bộ traffic trừ ADB.
- **Dị Giới hộ phù item 0xff8c (capture MuMu 12 2026-07-16, full traffic):** dùng qua cơ chế
  item túi bình thường, KHÔNG có opcode riêng. Inventory snapshot: slot `0x15` = item `0xff8c`
  (Dị Giới Hộ Phù). Gói dùng: C2S `0x17 0f0015010000000000`
  (`0f00 [slot=0x15][qty=1] 000000 [target=00] 00`). Server ACK:
  S2C `0x17 09001501000000`, rồi bắn `0x55 id=0x1b value=60` để cập nhật timer. Bot chỉ cần
  `use_item(0xff8c)` / `use_slot(slot, target=0)`, KHÔNG tự cộng giờ thủ công.
- De AUTO vao Di Gioi: phai decrypt HTTPS 103.82.31.230 (dung mitmproxy + APK patched tsvtc-patched.apk de trust cert) -> lay URL+params -> replicate bang Python (bot da co lib HTTP cho login). TODO.
- map_id Di Gioi: CHUA XAC DINH chac (gia tri 0xc316 o offset 28 cua 0x03 co the la toa do).

## 7d-RE. MAP COLLISION / SMART PATHFIND (xac nhan 2026-07-17)

Muc tieu: tim data game biet o nao tren map di duoc / bi chan (tuong, song, object...) de pathfind dung hon.

**Ket luan da xac nhan: grid trong `Ground.mmg` CHINH LA block/collision.** Ket luan cu bi sai vi
tool render row-major (`grid[y*w+x]`), trong khi `MapData.lua` doc va luu **X-major**
(`blocks[x][y]`, byte index `(x-1)*blockHeight+(y-1)`). Lua game quy dinh:
- obstacle khi `(value & 1) == 1` HOAC `(value & 4) == 4`;
- sea khi `(value & 2) == 2`;
- ngoai bien / khong co map = obstacle.

**Data da tim thay trong MuMu 12 (APK alone khong du data, vi game tai them GB data):**
- Real data path tren emulator: `/sdcard/Android/data/com.vtcmobile.gz06/files`
- Cac pack quan trong da keo local tam vao `.codex_mumu_probe/` (gitignored, KHONG commit file nang):
  `Ground.mmg`, `Wem.mmg`, `Eve.emg`, `Talk_C.dat`, `ResourceList.dat`, `BasePackageList.dat`,
  `global-metadata.dat`, `libil2cpp.so`, `libtolua.so`.
- `Ground.mmg` co 4469 entry `.map`. Index o gan EOF; entry chuan:
  `[u8 nameLen][name][11 byte metadata][u32 offset LE][u32 size LE]`.
  Vi du `12831.map` -> offset `0x32bc42` (3333397), size `0x2b72` (11122).
- Format `.map` da doc duoc phan lon:
  `u32 width_px`, `u32 height_px`, `u8 chunk_count`, moi chunk 6 byte, tiep theo `u16 grid_w`,
  `u16 grid_h`, roi `grid_w*grid_h` byte grid. Sau do co event_count/object_count/tail metadata.
  Vi du `12831.map`: `1664x2560`, grid `84x129`, object_count `19`.
- `Wem.mmg` la pack object `.wem`; object_id trong tail `.map` map duoc 100% sang WEM.
  WEM entry hay 21 byte, co object_id va kich thuoc sprite (vd `10621002.wem` width~416 height~224 flags~511).

**Monster/encounter data da soi (2026-07-17):**
- `Ground.mmg` CHI la collision/passability, khong co danh sach diem spawn quai.
- `gamedata/Data/SceneFight_C.dat` co `381` record, format fixed `25` byte/record
  (`len=9529 = 4 + 381*25`). Record co dau hieu chua `map_id`, `x`, `y`, level min/max.
  Vi du: map `12831` -> `(1310,2410)` lv `28-30`; `14821` -> `(3090,290)` lv `74-105`;
  `20821` -> `(310,270)` lv `62-68`; `56801` -> `(310,1090)` lv `114-120`.
- Cac toa do nay KHONG trung voi `train_maps.json` mob points (thuong moi map chi 1 record),
  nen tam ket luan day la encounter/fight config/anchor cua scene, KHONG phai full list cac diem
  quai dung/di qua co the train.
- `gamedata/Data/SceneSet_C.dat` co `3677` record fixed `17` byte; moi train map match 1 record
  theo `map_id`, nhung record giong scene metadata/flag, chua thay toa do spawn.
- Huong dung hop ly: dung `SceneFight_C.dat` de biet map nao co random encounter + level range,
  lay toa do lam candidate/seed, roi ket hop `Ground.mmg` + thong ke battle runtime de hoc diem train tot.

**Vung quai hoc tu packet runtime (xac nhan 2026-07-19):**
- S2C `0x07` sub `00 00` co layout
  `[entity 8B][map_id u16 LE][x u16 LE][y u16 LE]` (offset full packet:
  entity `9:17`, map `17:19`, x `19:21`, y `21:23`) -> vi tri entity luc vao tam nhin/map.
- S2C `0x06` sub `01 00` co layout
  `[entity 8B][direction u8][x u16 LE][y u16 LE]` (offset full packet:
  entity `9:17`, direction `17`, x `18:20`, y `20:22`) -> entity di chuyen.
- S2C `0x0c` rich record sub `00 00` (body thuong >=40B) la profile PLAYER; entity trong
  record nay phai loai khoi mob scanner. Self entity + entity party cung phai loai.
- Capture `captures/bachai_route_20260716.pcap`, map `11013`: 5 entity khong phai player lap
  cac waypoint co dinh. Gom duoc 2 bai: nhom 3 con quanh tam `(530,930)`, nhom 2 con quanh
  tam `(1150,530)`. Vung nhom dau bao phu cac diem train config `(590,1010)` va `(450,810)`.
- Ket luan: diem trong `train_maps.json` la diem dung trong/gan vung quai di chuyen, KHONG phai
  danh sach spawn chinh xac. Co the quet map bang `Ground.mmg` + nghe `0x07/0x06`, doi waypoint
  lap on dinh, gom patrol gan nhau va lay medoid/diem walkable lam tam bai.
- Code: `bot/mob_scanner.py` (observer + full scan), `bot/mob_spots.py` (cache atomic).
  Cache runtime `mob_spots.json` CHI luu cac tam `[x,y]` + metadata scan/fingerprint; KHONG luu
  entity, waypoint, polygon, bounding box hay trace. Android dung cung code/schema qua
  `tools/sync_apk_python.py`.
- Safe map train khong can config san: smart route cho phep `safe=None`, di toi warp cuoi roi lay
  `client.pos` do self-spawn server tra ve, project sang o walkable gan nhat va cache 1 diem `safe`
  theo fingerprint trong `mob_spots.json`. Login san trong map KHONG duoc ghi de safe bang toa do bai.
- Neu login san dung map train nhung ca cache lan config deu chua co safe, coordinator coi acc la
  chua toi dich: ca party ve thanh, lap lai party va di tron smart route qua warp cuoi. Chi khi
  `via_route=True` moi hoc `client.pos` sau warp lam safe; vi tri login ban dau tuyet doi khong duoc dung.
- Bug da xac nhan map `20801` (2026-07-19): JSON `"safe": []` bi loader cu chuan hoa thanh `[()]`;
  coordinator vi the khong build smart route du `world_nav` co duong `20001 -> 20000 -> 20801`.
  Member dau tien danh gia `route-less` va goi `stop_party`; cac nick con lai bao "MAT KET NOI"
  chi la hau qua socket bi dong. Fix: empty safe giu nguyen `[]`, member cho plan cua leader khi
  smart routing bat, leader hoc safe sau warp roi moi set rally.

**Da giai ma Lua, khong can hook runtime:**
- `LuaFileUtils.ReadFile` goi `CryptUtils.DeCrypt`; `ProjectSetting.cctor` cung cap AES/Rijndael
  CBC PKCS7 key `1234567870541704`, IV `7054170412345678`.
- Da decrypt va doi chieu `MapManager.lua`, `MapData.lua`, `FindWay.lua`, `BlockController.lua`,
  `MoveController.lua`, `GridController.lua`, `Scene.lua`.
- `BLOCK_UNIT=20`, `BLOCK_CONVERT=0.05`; world -> block:
  `ceil((x-centerLeft)*0.05), ceil((y-centerTop)*0.05)`; block -> world:
  `(blockX*20-10+centerLeft, blockY*20-10+centerTop)`.
- Map nho hon viewport 800x600 co `centerLeft/centerTop` can giua theo cong thuc trong
  `MapManager.OnEnterScene`; tool/runtime da port dung.

**Thuat toan game trong `FindWay.lua`:**
- dich bi block -> thu 8 o lan can theo thu tu tren/duoi/trai/phai/4 goc;
- neu duong thang clear thi di thang;
- neu khong: A* chi 4 huong, edge cost 1, heuristic Euclidean;
- sau A*, `GetBestPath` bo cac waypoint thua bang `MapManager.IsLineWay` (check ca ceil va floor
  sat hai mep line, khong cho cat goc vat can).
- `bot/pathfind.py` da port `find_local_path`, `is_line_clear`, `GroundMapStore`; `navigate_to`
  tu dong dung smart waypoint neu `config.SMART_PATHFIND=True` va co `config.GROUND_MAP_PATH`,
  khong co file thi fallback navigate cu.
- `tools/ground_map.py` da doc name->offset/size, render dung X-major va expose quy doi toa do.
- Verify that map `12831`: `1664x2560`, grid `84x129`; safe `(470,1210)` -> mob
  `(1070,1850)` cho route block `(24,61) -> (25,65) -> (54,93)` thay vi xuyen vach.

**Tinh trang Frida/MuMu luc dung:**
- Device MuMu 12 cong ty: `127.0.0.1:7555`; package `com.vtcmobile.gz06`.
- Da day `frida-server` len `/data/local/tmp/frida-server`, chay root OK; Python frida installed tam o `.codex_frida/`.
- Attach vao PID game OK, nhung `Process.arch` Frida bao `x64` do MuMu/native bridge; module list khong thay export ARM
  `libtolua.so`, nen hook truc tiep `tolua_loadbuffer/luaL_loadbuffer/lua_loadx` chua duoc.

### Smart world routing cho train map (implemented 2026-07-17)

- Smart routing la duong CHINH cho moi train map. `train_routes.json` chi con la fallback tam thoi
  trong giai doan live acceptance va co the xoa sau khi da test on dinh.
- `world_nav.json` la asset generated, versioned: chua 16 thanh co flag teleport da xac minh,
  scene/area graph va tam gate lay tu `Warp_C.dat`, `DoorGroupData.dat`, `Eve.emg`.
- `gamedata/Ground.mmg` (27 MB) la collision data runtime. File nay quan trong va duoc track/ship
  trong desktop release; khong rut gon thanh subset nua.
- `smart_routes.json` la cache runtime disposable, duoc fingerprint theo navigation data va ghi
  atomic. Cache giu structural route + local waypoint theo block xuat phat, phai gitignore.
- Flow train: tim thanh teleport gan nhat -> teleport bang city+flag da biet -> BFS chuoi gate ->
  A* collision-safe toi tung gate -> xac nhan map sau moi gate -> toi safe. Scene bat ngo thi
  invalidate/rebuild dung 1 lan; tuyet doi khong `go_to_town(train_map_id)`.
- Hạp Cốc Tử Ngọ 1 (`14821`) da verify offline: Trường An `14001`, flag `6`, gate
  `14001/1 -> 22000/17 -> 14821`; gate `22000/17` co center `(560,2510)`.
- Rule project: tinh nang runtime phai lam dong thoi cho PC va APK. Desktop build copy
  `world_nav.json` + `gamedata/Ground.mmg`; Gradle cung dong goi hai file canonical nay vao APK,
  service materialize theo `versionCode` ra app `filesDir`, va Android bat `SMART_WORLD_ROUTING=True`.

**Next:** live acceptance 1 party tren map `14821`, sau do test reconnect o scene trung gian va reform
khi mot member bi van map. Neu log/map verify dung, co the xoa fallback `train_routes.json`.

## 7e. CHUYEN SUB-CHANNEL (opcode 0x07)

Map dong nguoi (Di Gioi) chia nhieu sub-channel. **PHAI cung channel moi moi vao party duoc.**

```
C2S 0x07 = c0 91 0b 00 00 00 07 02 00 [channel_id 2B LE]
```
- channel 81 = `07 02 00 51 00`, channel 79 = `07 02 00 4f 00`, channel 38 = `07 02 00 26 00`
- Sau khi gui -> server doi scene (0x27 + 0x61 + 0x0c handshake), nhan vat sang channel moi.
- Bot.switch_channel(n) da implement.

## 7f. TIMER DI GIOI (packet 0x55)

S2C 0x55 (len 23): `c0 91 17 00 00 00 55 01 00 01 00 00 00 [id 2B LE][value 4B LE][max 4B LE]`
- byte[13:15] = id counter (LE), byte[15:19] = value (uint32 LE)
- **id=0x1b => so phut Di Gioi da tinh vao quota hom nay.** Bot tinh `con_lai = 120 - value`.
  Capture cu sau khi vao Di Gioi: `0x1b=9`; capture dung Ho Phu `0xff8c`: server gui lai
  `0x1b=60`. Neu dang con <15p va dung Ho Phu, server tu cap nhat lai counter nay (du kien
  value giam 60), bot KHONG tu cong/tru gio thu cong.
- `0xac/0xab/0xa9` la cac counter 0x55 khac thay trong pcap (vd `0xac=449`, `0xab=52`,
  `0xa9=27169`), KHONG dung de tinh timer Di Gioi.

## 7g. QUA ONLINE (opcode 0x57)

Nhan qua khi online du so phut. **id qua = so phut moc.**

```
C2S 0x57 nhan qua: c0 91 ... 57 [02 00][03][id 4B LE][01]
S2C 0x57 ket qua:  c0 91 ... 57 [02 00][03][status 1B]   (status=0: thanh cong)
```

- **6 moc qua:** 10, 20, 30, 60, 90, 180 phut (id = so phut, vd moc 20p -> id=0x14)
- Qua online tinh theo TONG THOI GIAN ONLINE (ke ca o thanh, da xac nhan nhan duoc khi dung o thanh).
- **0x1b (S2C 0x55) = counter timer DI GIOI**, KHONG phai online time -> KHONG dung cho qua online.
- LUU Y: C2S 0x57 [03 00] (query list) tra ve 3 entry tinh 50/70/100 - FEATURE KHAC, KHONG lien quan qua online.
- ANTI-CHEAT: client that disable nut claim khi chua du gio -> KHONG bao gio gui claim som.
  Bot phai lam giong: chi claim khi DA DU GIO. Dung uptime cua bot (time tu connect) lam
  moc online (uptime <= online time that -> uptime>=moc thi chac chan da san sang).
  Luu trang thai da nhan ra gift_claims.json theo ngay (tranh re-claim khi reconnect).
- Logic o client.claim_online_gifts().

## 7g2. DIEM DANH HANG NGAY (opcode 0x57, type=01)

Diem danh theo **SO LAN da diem danh** (hom nay ngay N -> mai N+1; bo ngay thi KHONG tang).
Mo menu = duoc tinh. Moi ngay nhan 1 lan.

```
C2S 0x57 nhan: c0 91 ... 57 [02 00][01][day 4B LE][01]   (type=01 khac qua online type=03)
S2C 0x57 ket qua: [02 00][01][status]
  status=0: OK (dung ngay hom nay) | status=2: ngay DA nhan | status=5: ngay CHUA toi (tuong lai)
```

- Bot tu dem + luu checkin_state.json {label:{date,day}}. 1 lan/ngay.
- Lan dau/desync: quet day=1..40, server chi chap nhan dung ngay hom nay (status=0), con lai 2/5
  -> scan AN TOAN (chi 1 ngay status=0). Xac nhan checkin.pcap + test sga001/003.
- Logic o client.claim_checkin(). Goi luc login trong run_party_digioi.

**0x57 type khac (cung co che [02 00][type][day 4B][01], status 0=OK/2=da nhan/5=chua toi):**
- type=01: diem danh hang ngay
- type=03: qua online (id = so phut moc)
- type=04: **QUA 14 NGAY user moi** (day 1..14, nhan het thi dung). client.claim_14day_gift().
- Code chung: client._claim_daily_gift(kind, gtype, max_day, name, finite). State checkin_state.json
  key "label:kind".

## 7h. EXP OFFLINE (opcode 0x54)

Nhan exp tich luy khi offline (bang hien luc login).

```
C2S 0x54 hoi info:  c0 91 ... 54 [01 00][type 2B=1c00]
S2C 0x54 tra ve:    c0 91 ... 54 [01 00][type 2B][flag 1B][exp 4B LE]  (exp>0 = co the nhan)
C2S 0x54 nhan:      c0 91 ... 54 [02 00][02][type 2B]
S2C 0x54 ket qua:   c0 91 ... 54 [02 00][type 2B][status 1B]  (status=1: thanh cong)
S2C 0x1a sau do:    +exp vao nhan vat (vd 0x12c = 300 exp)
```

- type = 0x1c (28). Bot: request_offline_exp() -> auto nhan neu exp>0 (giong client, an toan).
- Logic o client.request_offline_exp() + _on_offline_exp().

## 7i. PET DANG DUNG (opcode 0x13)

- **C2S 0x13** `01 00 [pet_id 2B LE]` = doi pet (chon pet tu tui).
- **S2C 0x13** `01 00 [pet_id]` = xac nhan doi pet.
- **S2C 0x13** `04 00 [pet_id]` = pet dang dung, gui luc LOGIN.
- pet_id (vd 0xa051, 0xa0db) = id pet -> bot doc luc login de biet pet nao.
- Pet skill KHONG gui qua mang (client-side, theo loai pet). Server CHI gui pet_id (0x13).
- Khi pet ko co skill ma gui -> server cho DUNG YEN (phi luot). Server VAN echo skill yeu cau
  trong 0x32 va SP khong tru on dinh (co quan su hoi) -> KHONG detect tu choi dang tin.
- => Dung config.PET_AOE_SKILL { pet_id: skill_aoe } (None=danh thuong). Bot doc pet_id luc
  login -> tra map -> decide_pet dung dung skill. Tong quat moi skill combo (Hoa Tien/Nem Da/...).

## 7j. PARTY-TRAIN MAP THUONG + COMBAT-ACTIVE (QUAN TRONG!)

**Van de:** bot dung yen tren map thuong -> quai CHAY NGANG QUA, KHONG aggro (trong khi char that
dung yen thi quai lao vao danh). Di Gioi thi danh duoc binh thuong.

**Goc re:** char phai o trang thai **COMBAT-ACTIVE** thi mob-AI moi aggro. Trang thai nay bat bang
**chuoi C2S gui NGAY SAU AUTH** (client that gui luc login, bot khong gui -> server coi bot
"co mat nhung AI bo qua"). Chuoi (xem login.pcap), gui ngay sau auth trong `connect()`:
```
0x19 2900f0 | 0x2b 0400 | 0x01 1000 | 0x7c 0400 | 0x41 0200 | 0x0c 0100 |
0x57 0300 | 0x01 1000 | 0x62 020001000000 | 0x41 01003235010100000101000000
```
Quan trong nhat: **0x41 `01003235010100000101000000`** = "dang ky san sang battle".

**Bay cuc khó:** DOI KENH (0x07 switch_channel) + LAP PARTY **RESET** trang thai combat-active.
Gui lai MOI 1 goi 0x41 KHONG du -> phai gui lai **TOAN BO chuoi setup** (`combat_ready()` =
`_login_setup()`) SAU khi da doi kenh + lap party + toi diem quai. Luc do quai moi aggro.

**Di Gioi KHAC:** vao tran kieu va-cham/dong quai khi DI CHUYEN -> khong can combat-active.
Map thuong DUNG YEN -> BAT BUOC combat-active.

**Toa do:** packet == toa do UI trong game (590,870 UI = 590,870 packet). (Luu y: dung capture
nham DEVICE khac -> toa do/hanh vi sai lung tung. Luon capture dung MuMu dang dieu khien!)

**Code:** client._login_setup() goi trong connect(); client.combat_ready() goi o diem quai sau
khi lap party; run_party_digioi mode map-train doc train_maps.json.

## 7k. SOLO DAILY DUNGEON + DUNG ITEM TRONG BATTLE (chua implement, ghi nho)

**Vao solo daily dungeon** (capture dungeon.pcap): huy party -> query -> vao -> danh -> thuong -> ra.
- Huy party: C2S 0x0d `04 00 [self_entity]`
- Query pho ban: C2S 0x2f `01 00` -> S2C 0x2f tra info
- **VAO: C2S 0x2f `02 00 02 00 00`** -> map doi sang dungeon (~61969) -> tu danh (combat 0x32/0x35 nhu thuong)
- Tier theo level (byte tier trong `0x2f 0200[T]0000`; start boss `0x14 0800[T-1]00`; mua ve `0x54 ...0d00[T]00`):
  - `<=80`: tier `02` (capture cu).
  - `81..150`: tier `03` (capture nick cao: `0x2f 0200030000` / `0x14 08000200` / `0x54 ...0d000300`).
  - `>=151`: tier `04` (**suy luan theo pattern, chua capture verify**; user chap nhan fix theo suy doan 2026-07-16).
- Xong: S2C 0x14 sub 64 (man complete) -> claim thuong (C2S 0x52 ...) -> S2C 0x55 (vat pham)
- Ra: C2S 0x0d `04 00 [self]` (don)
- TODO: implement auto (vao -> danh -> nhan thuong -> ra -> danh dau 1 lan/ngay).

**DUNG ITEM trong battle:** C2S `0x32` prefix `02 00` (skill la `01 00`):
- `02 00 02 02 02 02 [item_id 2B LE] [tail 2B]`
- **item 26461 (0x675d) = hoi ~62 SP** (xac nhan: SP nhay len 89 sau khi dung). Dung cho auto hoi SP.

**Pet skill don (dungeon):** pet dung skill **12009 (0x2ee9)** = danh don (them vao pets.json theo pet_id khi can).

## 7L. TÚI ĐỒ & THAO TÁC VẬT PHẨM — NGUYÊN TẮC SLOT (CỰC QUAN TRỌNG, ĐỪNG NHẦM LẦN NỮA)

> **MỌI thao tác lên item (dùng/hợp/đổi trang bị/support...) đều tham chiếu theo SLOT TÚI ĐỒ
> (vị trí item trong túi), KHÔNG phải theo item_id (tid gamedata 0x65xx...).**

**`tid` (id gamedata, vd 0x65c2 = Thịt Dê Khô) CHỈ để client tra TÊN/HP/SP từ `items_gamedata.json`
(hiển thị). KHÔNG BAO GIỜ gửi tid lên server cho thao tác.** Server định danh item trong túi theo
**vị trí slot** mà nó đã gửi cho client.

### Túi đồ (bot đọc → `self.bag_slots`)
- S2C `0x17` sub `05 00`: snapshot túi. Record 36B: `[idx 1B][tid 2B LE][count 4B LE][29 pad]`.
- `bag_slots[idx] = [tid, count]` ; `bag_counts[tid] = tổng`. `idx` = **slot** (1 byte, 0..255).

### Các thao tác đã verify (đều dùng SLOT, đọc LIVE từ bag_slots)
| Thao tác | Gói C2S | Mã hóa slot |
|---|---|---|
| Dùng item (heal HP/SP, túi sự kiện) — `use_slot` | `0x17` `0f 00 [slot 1B][qty 1B] 00*3 [target 1B] 00` | slot thô (1B) |
|   ↳ target: 0=char; PET = **VỊ TRÍ PET trong đội mang theo (1-based, user tự xếp = marker gói 0x0f)** — XÁC NHẬN capture `captures/pet_heal_20260715.pcap` (Quan Vũ vị trí 3 → target=03; Thái Văn Cơ vị trí 1 → target=01; char → 00). Hardcode 1 từng gây bug hồi pet vô dụng khi pet không ở vị trí 1. Pet chết trong trận được server TỰ HỒI SINH 1HP lúc kết trận → state pet.hp=0 từ 0x33 cuối là stale, vẫn hồi item bình thường ngay sau trận. **Đừng gửi `00*4`: dư 1 byte sẽ làm lệch target; char target=0 vẫn có vẻ chạy nhưng pet không hồi đúng.** | — |
|   ↳ Dị Giới SOLO có tối đa 4 pet cùng ra trận: stat trong battle dùng atype `0,1,3,4` nhưng `use_slot` vẫn target bằng marker pet `1,2,3,4` (`0→1`, `1→2`, `3→3`, `4→4`). Hồi ngoài trận phải quét `state.multi_pet` và hồi từng con có stat, không chỉ `active_pet_slot`. | — |
|   ↳ **Kho capture bằng chứng: `captures/`** (được git giữ lại, ngoại lệ gitignore) — capture mới nào có giá trị lâu dài thì COPY vào đây với tên mô tả + ngày, KHÔNG bắt user capture lại. | — |
| **Hợp vật phẩm** — `do_combine_item` | `0x17` `0e 00 [cid1 2B] 00 00 00 [cid2 2B] 00*8 01` | **cid = 0x0100 + slot** |
| Túi Vật Liệu Sự Kiện — `use_event_bags` | (dùng `use_slot`) | slot thô |

### HỆ QUẢ (lý do từng tốn cả 1 session để hiểu)
- **Slot ĐỘNG**: đổi khi túi sắp xếp lại (item bị tiêu/thêm). VD Măng Khô qua 3 phiên = cid
  0x116 / 0x117 / 0x112 (vì slot 0x16/0x17/0x12 đổi). → **PHẢI đọc slot LIVE từ `bag_slots`,
  TUYỆT ĐỐI KHÔNG hardcode id/cid tĩnh** (đã từng làm `compound_ids.json` map tid→cid = SAI hoàn toàn).
- Gói hợp dùng `cid = 0x100 + slot`, KHÔNG phải tid túi. Compound.dat (công thức hợp) mã hóa
  phức tạp, **KHÔNG cần đụng** — chỉ cần gửi 0x100+slot của 2 item là server tự xử.
- **Item nào "đánh hết" trong túi** (item_id biến mất khỏi bag_slots) → KHÔNG dùng được nữa.

### LÀM ĐÚNG TỪ ĐẦU khi thêm thao tác item mới (phân giải pet rác, đổi trang bị, support...)
1. Tìm SLOT của item trong `bag_slots` (lọc theo tid để xác định đúng item).
2. Gửi lệnh theo SLOT đó (tái dùng `use_slot` hoặc biến thể `0x100+slot` cho hợp).
3. **Đừng tự chế id** — bám cơ chế slot có sẵn (`use_slot` đã đúng từ vụ HP/SP).

## 7m. NHIỆM VỤ HÀNG NGÀY (BINGO 9 Ô) — opcode 0x5b

- **Mở panel (bulk):** C2S `0x5b 02 00 09 01 00 01 [id 2B][cell] ...` (9 ô, id ô N = `0x2e+N`, vd ô1=0x2f, ô9=0x37).
- **Server trả status TỪNG Ô theo thứ tự (1→9)**, mỗi ô 1 frame `0x5b`:
  - `02 00 01 01 00 [ô]` = ô **ĐÃ XONG** (quest sự kiện — kèm số ô) → handler `_quest_cells.add`.
  - `02 00 04` = **chưa xong**.
  - `02 00 03` = ô **quest ĐẾM** (vd ô9 battle-50). **CỰC QUAN TRỌNG:** bulk LUÔN trả `02 00 03`
    cho ô9 dù XONG hay CHƯA → **không phân biệt được**. (Đã verify: chumot xong & ttmmot chưa đều `020003`.)
- **→ Phải QUERY RIÊNG ô đếm:** C2S `0x5b 02 00 01 01 00 09 37 00` (ô9, id 0x37). Server trả
  `020001010009` nếu đã đủ 50 → bắt được; chưa đủ trả `020003/020004`. (Xem `_query_quests`.)
- **KHÔNG cache** trạng thái ô (từng dùng `quest_state.json` → POISON khi parse sai + thừa vì server
  gửi lại đầy đủ mỗi query). Mỗi login `_quest_cells = set()`, tin trực tiếp server.
- **Claim hàng/cột:** đủ CẢ 3 ô mới claim `0x5b 03 00 01 00 [line][0x2f+line-1]` (line R1-3=1-3, C1-3=4-6, tổng kết=7).
- **Trạng thái ĐÃ NHẬN thưởng (claimed) = bitmask trong frame `0x51` lúc login** (KHÔNG ở 0x5b!). Ngay
  sau marker `c0 fe 03 00 00 00` là **2 byte mask (uint16 LE)** — **line L đã nhận = bit (L+3)**.
  Vd `32d0` → bits {4,6,7,9} → line {1,3,4,6} đã nhận. Bot đọc → skip line đã nhận (`_claimed_lines`).
  Verify nhiều nick: nhận hàng 1 → `3040`→`3050`; nhận hàng 3 → `3290`→`32d0`.
- **Bài học 1:** quest "đếm số lần" → bulk không lộ done, phải hỏi riêng từng ô.
- **Bài học 2 (QUAN TRỌNG):** `analyze_pcap.py` từng cap `ln<=2000` → **DROP frame lớn** (0x51 ~1004B,
  0x55 ~15KB) → kết luận sai "server không gửi". ĐÃ sửa `ln<=65535`. Khi không thấy data trong gói,
  NGHI tool drop frame lớn trước → raw-decode lại với limit cao (đây là tật cũ, đã dính 2 lần: túi đồ + claimed).

## 7n. PHÓ BẢN TỔ ĐỘI LV20 (ô5 daily) — opcode 0x2f + battle loop (capture team.pcap)

Luồng 5 người (1 leader + 4 member). Map quan trọng: **ô5 bingo = phó bản tổ đội**.

> **Sẽ có nhiều phó bản tổ đội cấp cao hơn sau này (lv30/40/...)** — kịch bản từng trận (số trận,
> tọa độ di chuyển, số lần thoại, gói transit) sẽ KHÁC HẲN theo từng level, viết hàm riêng cho mỗi
> level (`do_team_dungeon_lv30`, `do_team_dungeon_lv40`...). Nhưng **CƠ CHẾ NỀN TẢNG dưới đây áp
> dụng lại được cho MỌI level**, đã xác nhận qua debug thực tế ở lv20 (xem BUG6-10):
> 1. **Phải gọi `combat_ready()` (gửi lại `0x41`) ngay sau khi START phòng** (`0x2f 0c00`) — thiếu
>    bước này thì nhân vật KHÔNG di chuyển thật dù gói `0x06` gửi đúng cú pháp (server âm thầm bỏ
>    qua lệnh move vì "mất combat-active" sau khi lập party mới, xem BUG7).
> 2. **Dialog với NPC = spam `0x14 0600` tới khi server IM LẶNG THẬT SỰ**, dùng kiểu WHITELIST (chỉ
>    tính các sub THẬT SỰ liên quan thoại là "còn đang thoại", vd `0100`/`1000`/`0d00`) chứ KHÔNG
>    dùng kiểu loại-trừ — có nhiều gói rác lặp lại (vd `0800` noise, `2c00`) trông giống thoại nhưng
>    không liên quan, dùng loại-trừ sẽ bị chờ vô ích rất lâu (xem BUG10).
> 3. **Mốc kết trận THẬT = `0x14 sub0800` với byte cuối (`pkt[9]`) = `0x03` hoặc `0x04`**, bất kể
>    `in_battle` đang `True`/`False` lúc nhận. KHÔNG chỉ dựa vào `in_battle=True` vì có trận tự động
>    resolve (server tự xử lý, không có pha `0x35` thật) sẽ không bao giờ bật cờ này (xem BUG9).
> 4. **Nhận thưởng TRƯỚC KHI `leave_party()`** — nội dung gói nhận thưởng có thể khác theo từng phó
>    bản, nhưng thứ tự (thoại tổng kết → nhận thưởng → giải tán) nên giữ nguyên (xem BUG8).
> 5. **Sau khi đánh xong thành công, gọi lại `claim_daily_quests(heavy=False)`** để claim bù hàng/
>    cột/tổng kết bingo có ô phó bản (ô phó bản là bước CUỐI trong `claim_daily_quests` nên lúc claim
>    hàng/cột, ô đó còn tính là CHƯA xong).

### Member side (ĐÃ CÓ trong `_on_dungeon`, KHÔNG cần làm lại)
- S2C `0x2f sub=0f` = lời mời phó bản → auto-accept **C2S `0x2f 03 00 [invite_id 4B] 00`** → sau 2.5s
  auto-ready **C2S `0x2f 0b 00`**. Whitelist theo `PARTY_LEADERS`.
- Khi battle bật (0x34/0x35 broadcast CHO CẢ PARTY) → battle AI (0x32) tự đánh. **Giả thuyết: member
  KHÔNG cần tự spam dialog/chuyển cảnh** — leader trigger battle là cả party bị kéo vào. (CẦN verify bằng
  1 capture member nếu member kẹt ngoài battle.)

### Tích hợp (ĐÃ implement)
- **Ô5 = BƯỚC CUỐI trong `claim_daily_quests`** (sau khi check + thử làm mọi ô khác — ô khác fail như
  hết xu gacha vẫn OK, không phụ thuộc). Gọi qua hook `client._o5_team_fn` (set bởi run_party_digioi).
- **Mỗi acc report ô5 đã xong chưa** vào `st["o5_done_by"]`. **LEADER chỉ chạy `do_team_dungeon_lv20` khi CẢ
  party đều CHƯA xong ô5** (`_handle_o5_team` chờ tất cả report, gate all-not-done). Member chỉ report
  rồi return → tự accept lời mời + đi theo.

### Leader side — `do_team_dungeon_lv20` (đã implement)
Chuỗi C2S (verify timeline team.pcap):
1. **Mở panel:** `0x2f 0100` (×2).
2. **Tạo phó bản:** `0x2f 02 00 01 00 01` (5 byte). Mật mã "22": nghi `0x41 0100 3232 ...` (`3232`="22"
   ASCII) nhưng bắn lúc t=118 (giữa battle 1) → CHƯA chắc. Mật mã có thể bỏ (bot chỉ mời nick mình).
3. **Mời member theo ENTITY:** `0x2f 08 00 [entity 8B]` cho TỪNG member (KHÁC party-invite `0x0d 07`!).
4. **Start:** `0x2f 0c 00` (sau khi 4 member ready).

### Vòng battle (4 trận) — leader chạy. **TRIGGER BATTLE = spam `0x14 0600`**
- **Mốc bật trận = burst `0x14 0600` (advance NPC dialog).** MỌI trận bật (S2C 0x34) ngay sau tràng
  `0x14 0600`. Số lần KHÁC nhau mỗi cảnh (**7–20 lần**) → **KHÔNG hardcode**: spam `0x14 0600` mỗi
  ~0.5s tới khi `state.in_battle=True`, có cap (vd 25 lần / 15s).
- **Di chuyển `0x06` = nhiều khả năng KHÔNG bắt buộc** cho battle. Trận 1: vào → dialog → battle, KHÔNG
  có move nào. Move ở trận 2-4 chỉ đi tới NPC/cổng trước transit. Replay cả move cho chắc, nhưng cái
  thật sự chuyển cảnh là transit + dialog.
- **Chuyển cảnh giữa trận:** `0x14 08 00 [area] 00` (area 01→02→03). Trận 4 đặc biệt dùng
  `0x20 02 00 08` + `0x14 01 00 14 00` (giống event boss thế giới).
- **Set quân sư (1 lần, sau trận 1):** `0x0d 05 00 [entity]` (đã có `set_strategist`).
- Trình tự thực tế: enter `0x14 08000100`→dialog→**B1**→dialog→set quân sư→move→`0x14 08000200`→dialog→
  **B2**→`0x7c 0400`→dialog→move→`0x14 08000300`→dialog→**B3**→dialog→move→`0x20 020008`+`0x14 01001400`→
  dialog→**B4**.
- ⚠️ **ĐÃ SỬA LẠI (2026-07-01):** claim cũ "kết bằng `0x14 0900`" SAI — `0x14 sub0900`/`0800` xuất hiện
  TRÀN LAN cả lúc KHÔNG hề trong trận (login, chờ ready...) nên KHÔNG dùng được làm mốc kết trận.
  **Mốc ĐÚNG đã xác nhận qua nhiều capture leader thật:** gói `0x14 sub0800` với **byte cuối (byte thứ
  10, `pkt[9]`) = `0x03` hoặc `0x04`** là tín hiệu **KẾT TRẬN THẬT**, bất kể `in_battle` đang `True` hay
  `False` lúc nhận (`client.py` biến `_genuine_end_seen`). Một số trận (đặc biệt trận boss/B4, dùng cơ
  chế transit `0x20`) **KHÔNG BAO GIỜ bật `in_battle=True` qua `0x35` thật** (server tự resolve) — phải
  dựa vào tín hiệu tail=03/04 này để biết đã xong, KHÔNG chờ `in_battle=True`.
- Ngoài ra còn 1 gói `0x14 sub2c00` (payload `[entity 8B][01 hoặc 02]`) lặp lại liên tục xen kẽ với
  `sub0800` noise — ĐÃ XÁC NHẬN là rác hoàn toàn không liên quan (không có trong bất kỳ capture leader
  người thật nào, chỉ xuất hiện phía bot, có thể do lệch nhịp phía server) — bỏ qua, KHÔNG dùng làm mốc.
- **Victory dialog (thoại thắng lợi) = cutscene CỐ ĐỊNH, số lần KHÁC nhau mỗi trận:** B1→B2=**9**,
  B2→B3=**10**, B3→B4=**20**. Gửi THIẾU → không qua được màn thắng lợi → transit trận sau TRƯỢT (kẹt).
  Phải gửi ĐÚNG số (`vdlg` trong segments). Approach-dialog (sau transit) thì spam-tới-khi-battle.

### Nhận thưởng + thoát
- Sau B4: `0x5b 0200010100053300` (query ô5 status) → `0x0d 04 00 [entity]` (sub04 = rời/giải tán) →
  `0x7c 0400` → `0x01 1000` (về thành?) → mở panel `0x5b 020009...` → claim line
  `0x5b 03 00 01 00 [line][reward 2B]` (capture claim line 2/5/7).

### 🐞 ROOT CAUSE ĐÃ TÌM RA (2026-07-01) — MEMBER TỰ CHẠY TIẾP GIỮA LÚC ĐÁNH PHÓ BẢN
**Triệu chứng:** turn nào cũng lặp lại y hệt mỗi ~20-25s (server timeout), quái không chết, cuối cùng
leader bị server ngắt kết nối (`Server dong ket noi`).

**Root cause (user tự phát hiện qua quan sát log, KHÔNG phải packet-level):** hook `_o5_team_fn` gọi
`_handle_o5_team` ở CUỐI `claim_daily_quests()`. Member (`is_leader=False`) TRƯỚC ĐÂY chỉ report
`o5_done_by` rồi **return NGAY** — KHÔNG chờ leader đánh phó bản xong. Thread của member (trong
`run_party_digioi.py`) chạy tiếp SONG SONG các bước flow riêng (channel sync, go_to_town, teleport,
lập party train...) TRONG LÚC nhân vật member vẫn đang ở trong trận (do đã accept lời mời + server kéo
vào battle). Member gửi `0x06`/`0x14`/`0x44` xen giữa combat → server không nhận atk hợp lệ từ member
đó trong turn → turn không hoàn tất → server re-offer cùng turn mỗi ~20-25s (timeout) → lặp vô hạn →
leader cuối cùng bị kick.
- Bằng chứng: log `[chuba] (member) xong daily login (5/5 acc) -> sync kenh + lap party -> ... ->
  go_to_town: dung -> MAT KET NOI` xảy ra **giữa lúc trận 1 đang lặp lại (chưa xong)**.

**Fix:** thêm `st["o5_state"]` (`"idle"→"running"→"done"`, `run_party_digioi.py`). Leader set
`"running"` NGAY TRƯỚC `do_team_dungeon_lv20()`, set `"done"` trong `finally` (dù thành công hay lỗi).
Member: sau khi report, **CHỜ** (poll, cap 600s) tới khi `state == "done"` mới được return/chạy tiếp
flow riêng. Xem `_handle_o5_team`.

**Các fix trước đó vẫn giữ (không liên quan bug này nhưng đúng, không revert):**
- `_offer_min` offset target (train +0, phó bản +1) — targeting đúng, đã verify quái chết ở trận 1,2.
- `flee_mode=False` suốt phó bản; random delay 0x32 0.5-2s (`_team_dungeon_until`, cửa sổ 300s).
- Victory dialog đúng số (vdlg 9/10/20); moves + transit từng trận.
- **ĐÃ SAI (đừng lặp lại hướng này):** "che chắn 2 hàng" (user bác) — nguyên nhân THẬT không liên quan
  tới hàng/cột quái, mà là race condition ở tầng flow member/leader.

**BUG 2 (2026-07-01, sau khi fix bug 1) — TAIL 0x32 CỐ ĐỊNH gây kẹt khi đánh lặp cùng target:**
- Sau fix `o5_state`, member không còn văng nữa (test full 4 trận: trận 1,2 qua được, KẸT trận 3).
- **User quan sát chính xác:** trong 1 turn CHƯA xong (không có gói `0x33` cập nhật quái xen giữa),
  server **re-offer lại y hệt turn đó** cho TOÀN BỘ 5 acc, cách nhau chỉ **~3-10s** (không phải 20-25s
  safety) — tức server chủ động re-prompt vì action TRƯỚC ĐÓ coi như KHÔNG được nhận.
- **Root cause tìm ra:** `_send_combat` gửi gói `0x32` với **tail (2 byte cuối, nonce) CỐ ĐỊNH `0000`**
  (comment cũ đã ghi client thật LUÔN đổi giá trị này, có sẵn cờ test `RAND_TAIL` nhưng mặc định TẮT).
  Khi 2 turn LIÊN TIẾP bot đánh **CÙNG skill + CÙNG target** (rất hay xảy ra khi dồn vào 1 con "trâu"
  HP cao — trận 3 có 2 con 229/235 HP, nhiều turn liền là mục tiêu thấp máu nhất) → gói `0x32` **giống
  hệt byte-by-byte** với gói trước → nghi server coi là **gói lặp/replay → âm thầm bỏ qua** → turn
  không tiến → lặp vô hạn. Trận 1,2 quái yếu, target đổi liên tục mỗi round (quái chết nhanh) → gói tự
  nhiên khác nhau dù tail=0000 → ít dính. Trận 3 có quái trâu → dính liên tục → kẹt cứng.
- **Fix:** bỏ cờ env `RAND_TAIL`, **LUÔN LUÔN random tail** trong `_send_combat` (đúng hành vi client
  thật, không chỉ trong phó bản — áp dụng cho MỌI combat kể cả train, an toàn vì đây là hành vi đúng).
- **Test lại: VẪN KẸT trận 3 y hệt** (tail random không đủ) → giả thuyết tail SAI, phải tìm tiếp.

**BUG 3 (2026-07-01, sau khi tail-fix không đủ) — ROOT CAUSE THẬT: gửi atk theo offer 0x35 CỦA THÀNH
VIÊN KHÁC (chưa phải lượt mình), do fallback sai trong `_offered_targets`:**
- **User hỏi thẳng:** "giữa 2 lần atk không có gói tin quái nào — dựa vào đâu mà biết đó là turn mới?"
  → buộc soi lại đúng cơ chế trigger, không đoán nữa.
- **Xác nhận:** server gửi **1 gói `0x35` RIÊNG cho TỪNG unit** (party 5 người = tới 10 gói/lượt,
  mỗi gói CHỈ 1 `atype`) — không phải 1 gói gộp cho cả đảng (xem mục 5 BATTLE FLOW).
- **`_on_actions` (client.py) trigger `_arm_decision()` cho MỌI gói `0x35` ≥20B, KHÔNG kiểm tra gói đó
  có offer cho `atype` của MÌNH hay không** — tức bot cũng bị kích đánh khi nhận gói `0x35` của
  **THÀNH VIÊN KHÁC** trong đảng (server broadcast cho cả đảng biết đang tới lượt ai).
- **`_offered_targets(options, atype)` (combat.py) có FALLBACK NGUY HIỂM:** `return t or [o[1] for o
  in options]` — khi batch KHÔNG chứa offer đúng `atype` mình (`t` rỗng, vì đó là lượt người khác) →
  **fallback dùng TOÀN BỘ target của người khác làm của mình** → tính atk dựa trên dữ liệu SAI CHỦ.
- Vì `enemy_hp` chưa đổi (chưa ai đánh trúng thật) → `_train_target` tính RA CÙNG 1 kết quả mỗi lần
  bị kích nhầm → nhiều lần gửi atk **giống hệt nhau**, không có gói `0x33`/`0x0b` cập nhật quái xen
  giữa (vì đó KHÔNG PHẢI turn mới thật) — **khớp chính xác quan sát của user**.
- **Fix 2 lớp:**
  1. `_offered_targets`: bỏ fallback, batch rỗng cho atype mình → trả `[]` (không đánh).
  2. `_make_decisions` (client.py): thêm guard `if self.state.my_atype not in {o[0] for o in
     char_opts}: char_opts = []` — giống guard đã có sẵn cho PET (dòng gần đó) nhưng CHAR trước đây
     THIẾU. Không guard này thì dù `_offered_targets` trả `[]`, `_train_target([],...)` trả `None` →
     `_attack` vẫn fallback đánh **cột 1 cứng** (`fb_col=1`) — đánh mù không dựa offer thật nào.
- Áp dụng CHUNG (không chỉ phó bản) — lỗi tiềm ẩn mọi trận đảng, party nhỏ (2 người) ít lộ vì offer
  đến gần nhau hơn trong debounce window.

**Test guard atype (2026-07-01, log 4 member `quan*` theo leader thật):** CHẠY ĐƯỢC trọn trận 1,2 và
tiếp tục sang trận 10-quái tiến triển tốt → 3 fix trước (`o5_state`, tail random, atype guard) đã sửa
đúng gốc "kẹt tổng thể". **CÒN 1 LỖI NHỎ, VÔ HẠI:** user quan sát TRỰC TIẾP trên màn hình xác nhận —
mỗi trận kết thúc thật (đã thắng) thì bot vẫn gửi thêm **1 lệnh atk thừa** ngay sau đó.

**BUG 4 — đánh MÙ khi quái đã chết hết (root cause của "atk thừa sau khi thắng"):**
- `_combat_attack` (combat.py): nhánh BOSS/QUEST đều check `and es` (chỉ chạy khi còn quái sống), NHƯNG
  nhánh **TRAIN mode (cuối hàm) KHÔNG check `es` rỗng** — khi quái chết hết (`es=[]`, có thể do server
  gửi thêm 1 gói `0x35` "tàn dư" ngay sau khi thắng), code rơi xuống TRAIN mode, gọi
  `_train_target([], offered)` → trả `None` → `_attack(..., pos=None, ...)` → **fallback đánh MÙ cột 1
  cứng** (`fb_col`), dù không còn mục tiêu nào. Đây chính là gói atk thừa user thấy.
- **Fix:** `_combat_attack` return `None` sớm nếu `not es` (không đánh gì cả). `decide_char`/`decide_pet`
  đã tự nhiên trả `None` xuyên qua. `_make_decisions` (client.py) thêm guard `if d is None: log...(bỏ
  qua)` cho cả CHAR và PET trước khi gọi `_send_combat` (trước đây gọi vô điều kiện → crash nếu `d=None`).

**Test BUG4 (2026-07-01, log DBG-SEG bot-tu-lam-leader):** vẫn kẹt — có trận `enemy_hp` KHÔNG ĐỔI
1 CHÚT NÀO giữa 2 round giống hệt (không phải `es` rỗng — quái vẫn "sống" theo state, chỉ là KHÔNG
CÓ gói `0x33` MỚI nào xen giữa 2 lần gửi atk). User chỉ chính xác: **"lần atk cuối không có log quái
mà vẫn gửi"** — tức code gửi atk dựa trên **dữ liệu quái CŨ (stale)**, không kiểm tra có cập nhật mới
hay không trước khi đánh.

**BUG 5 — ROOT CAUSE THẬT: gửi atk mà KHÔNG kiểm tra có dữ liệu quái MỚI (`0x33`) hay chưa:**
- `_make_decisions` chỉ bị kích bởi gói `0x35` (offer lượt) — gói này **KHÔNG mang thông tin quái**.
  Thông tin quái CHỈ đến từ gói `0x33`/`0x0b` riêng biệt, hoàn toàn độc lập với `0x35`.
- Nếu `0x35` tới mà KHÔNG có `0x33` mới đi kèm (ví dụ: trận đã kết thúc thật, server chỉ gửi thêm
  offer "tàn dư"/re-broadcast lại đúng turn cũ) → code **vẫn cứ đánh, dùng `enemy_hp` CŨ** từ lần
  trước — dữ liệu STALE, có thể tình huống thực tế đã khác hẳn (trận đã xong).
- Verify từ log: `11:43:39` (round 1, có `DBG33` trước đó) → `11:43:50` (round 2, atk Y HỆT) —
  **KHÔNG có dòng `DBG33`/`DBG0B` NÀO** xen giữa 2 lần gửi atk.
- **Fix:** thêm bộ đếm thế hệ `state.enemy_gen` (tăng mỗi khi CÓ gói `0x33` thật cập nhật nhóm quái).
  `_combat_attack` lưu `state.last_atk_gen_char`/`last_atk_gen_pet` (riêng theo unit) mỗi lần đánh;
  **nếu `enemy_gen` KHÔNG đổi so với lần đánh trước của unit đó → `return None` (bỏ qua, không đánh
  lại trên dữ liệu cũ)**. Chỉ đánh khi có dữ liệu quái MỚI thật sự kể từ lần đánh trước.
- Thêm log `DBG-ENDBATTLE` phân biệt 2 đường hạ `in_battle`: gói kết trận THẬT (`0x14` sub `0700`/
  `0c00`/`0900`/`0800`) vs **safety 25s** (khi 25s không có 0x35 nào, ép `in_battle=False` — CÓ THỂ
  trận CHƯA xong thật, chỉ là miss gói end) — để lần test sau phân biệt rõ 2 trường hợp.

**BUG 6 — leader chờ SAFETY 25s mỗi trận dù trận đã kết thật (2026-07-01):**
- Sau BUG5, leader vẫn mất ~25-44s giữa mỗi trận vì (a) `enemy_slots` rỗng KHÔNG đồng nghĩa trận đã
  kết — HP quái cũ (>0) vẫn còn lưu do leader không nhận `0x33` cuối để zero nó; (b) gói kết trận thật
  (tail=03/04) hoá ra CHỈ gửi riêng cho MEMBER, **LEADER KHÔNG BAO GIỜ nhận được** gói này cho chính nó.
- **Fix:** registry dùng chung theo `party_idx` (`_PARTY_BATTLE_END`, cùng cơ chế với `_PARTY_ENTITIES`
  có sẵn) — khi BẤT KỲ member nào xác nhận kết trận thật, ghi timestamp dùng chung; leader đọc timestamp
  đó (chỉ trong cửa sổ phó bản to đội) để hạ `in_battle` ngay, không cần đợi 25s.

**BUG 7 — trận 4 (boss) không bao giờ vào được dù gói gửi đúng cú pháp (2026-07-01):**
- Đối chiếu byte-by-byte 2 capture LEADER THẬT (cùng 1 account, 1 lần bot chạy thất bại + 1 lần người
  điều khiển tay thành công): nội dung gói gửi giống hệt nhau, NHƯNG:
  1. **Thiếu gói `0x41`** (OP_BATTLE_ENTER, "đăng ký sẵn sàng battle" — đã dùng ở `_login_setup`/
     `combat_ready()` cho map thường). Người thật gửi gói này **13 lần** trong cả phiên; `do_team_dungeon_lv20`
     trước đây KHÔNG BAO GIỜ gọi `combat_ready()`. Tạo phó bản = tạo party mới, đúng tình huống
     `combat_ready()` cần gọi lại (comment cũ: "Sau khi ĐỔI KÊNH / lập party, char có thể mất
     combat-active"). **Fix: gọi `self.combat_ready()` ngay sau khi START phó bản (`0x2f 0c00`).**
  2. **Nhịp bấm dialog đầu tiên sau transit trận 4 quá nhanh** (bot ~0.34s vs người thật ~1.27s) — dù
     KHÔNG phải nguyên nhân chính (đã test tăng delay riêng lẻ vẫn fail), vẫn giữ delay 1.0-1.6s trước
     lần bấm đầu cho khớp nhịp người thật.
- Sau khi thêm `combat_ready()`, trận 4 vào được thật (nhân vật di chuyển thật, đánh được).

**BUG 8 — thiếu bước NHẬN THƯỞNG trước khi giải tán party (2026-07-01):**
- Sau khi thắng trận 4, `do_team_dungeon_lv20` trước đây `_wait_combat_clear` xong là `leave_party()` NGAY —
  bỏ qua đoạn thoại tổng kết + màn nhận thưởng → server tính là CHƯA hoàn thành dù đã đánh xong 4 trận.
- Capture người thật: sau trận 4, còn đoạn thoại tổng kết (`0x14 sub0100`/`sub1000` lặp), rồi client gửi
  **`0x5b 0200010100053300`** (NHẬN THƯỞNG) TRƯỚC KHI gửi `0x0d 04` (giải tán). **Fix:** spam dialog qua
  đoạn tổng kết (`_adv_dialog_until_idle`) → gửi `0x5b` nhận thưởng → chờ → mới `leave_party()`.

**BUG 9 — leader bị server kick kết nối ngay lúc/ngay sau vào trận 4 (2026-07-01):**
- Log xác nhận: leader nhận đúng tín hiệu kết trận thật (`sub0800 tail=03`) nhưng vì `in_battle` lúc đó
  đã là `False` sẵn (đã hạ qua cơ chế BUG6), code KHÔNG coi đây là điều kiện dừng — `_dialog_until_battle`
  (chỉ dừng khi `in_battle=True`) tiếp tục gửi THÊM `0x14 0600` vào đúng lúc trận đã kết thật → server
  kick vì spam thừa. (Một số trận boss tự động resolve, KHÔNG BAO GIỜ bật `in_battle=True` qua `0x35`
  thật, nên trước đây sẽ luôn bị lỗi này.)
- **Fix:** `_dialog_until_battle` dừng ngay khi `state.in_battle=True` **HOẶC** thấy tín hiệu kết trận
  thật (`_genuine_end_seen`), không chỉ chờ `in_battle=True`.

**BUG 10 — chờ di chuyển rất lâu mỗi trận dù không lỗi (2026-07-01):**
- `_adv_dialog_until_idle` (spam thoại tới khi server im lặng) dùng kiểu loại-trừ: chỉ loại `sub2c00`
  khỏi việc reset đồng hồ im lặng, còn `sub0800` noise (tail 26/27, cũng là rác lặp lại không liên quan)
  vẫn được tính là "còn đang thoại" → liên tục làm mới đồng hồ → chờ vô ích rất lâu (tới 50 lần/22s)
  trước khi chuyển sang move.
- **Fix:** đổi sang WHITELIST — chỉ 3 sub THẬT SỰ liên quan thoại (`0100`=ack dòng thoại, `1000`=cutscene
  loop, `0d00`=mở cảnh) mới reset đồng hồ; mọi sub khác (kể cả rác mới phát sinh sau này) không ảnh hưởng.

**KẾT QUẢ CUỐI (2026-07-01): pho ban to doi chạy ỔN ĐỊNH — đủ 4 trận, di chuyển thật, nhận thưởng, không
rớt kết nối.** Đã gỡ hết log debug tạm (DBG33/DBG0B/DBG35/DBG-RAW/DBG-CAPTURE); các log
`(LEADER) tran N: ...` giữ lại vì hữu ích theo dõi vận hành bình thường, không còn là debug tạm.

## 8. GAME MECHANICS

| Mechanic | Mô tả |
|----------|-------|
| HP restore | KHÔNG tự hồi sau trận. Chỉ hồi khi lên level |
| SP restore | KHÔNG tự hồi sau trận. Hồi khi lên level |
| SP regen | Hồi SP mỗi turn khi party CÓ quân sư (strategist). Đây là cơ chế chính để duy trì SP |
| Level up | Hồi đầy HP+SP, tăng max HP |
| Target | 0-indexed: 0=trái, N-1=phải |
| Party leader | action_type = 2 |
| Party member | action_type = 1 |
| Solo | action_type = 2 (char), 0 (pet) |

---

## 9. COMBAT AI LOGIC (dự kiến)

```python
def choose_action(sp_cur, sp_max, hp_cur, hp_max, mobs, party):
    hp_pct = hp_cur / hp_max

    # Ưu tiên 1: Heal all nếu nhiều ally bị thương
    if sp_cur >= 42 and count_low_hp_allies(party) >= 2:
        return skill(11010, target=any_ally)

    # Ưu tiên 2: Heal 1 nếu có ally HP thấp
    if sp_cur >= 22 and has_low_hp_ally(party):
        return skill(11004, target=lowest_hp_ally)

    # Ưu tiên 3: Phòng thủ nếu HP bản thân thấp
    if hp_pct < 0.3:
        return skill(17001, target=self)

    # Ưu tiên 4: Hỏa Tiễn nếu đủ SP
    if sp_cur >= 15:
        return skill(12003, target=best_aoe_target(mobs))

    # Fallback: Đánh thường
    return skill(10000, target=weakest_mob(mobs))
```

---

## 10. TODO

- [ ] Code login.py (HTTP → access_token)
- [ ] Code game_client.py (TCP + auth + heartbeat)
- [ ] Code combat_bot.py (lắng nghe 0x33/0x35 → gửi 0x32)
- [ ] Khám phá skill 12006
- [ ] Test với 100 accounts
- [ ] Implement daily tasks (sau combat)
