# TS Online Bot - Knowledge Base
> Tổng hợp toàn bộ kiến thức đã khám phá về game TS Online Mobile (com.vtcmobile.gz06)

---

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

### S2C 0x33 — Stats per turn
Pattern entries: `03 02 [type] [4-byte LE]`
| type | Hex | Thông số |
|------|-----|---------|
| 25 | 0x19 | HP current |
| 26 | 0x1a | SP current |
| 205 | 0xcd | HP max |

### S2C 0x0b — Full stats
**Char/Pet:** `03 0X [HP_max 4B] [SP_max 4B] [HP_cur 4B] [SP_cur 4B]`
- X=02: char, X=01: pet

**Mob:** offset 31 = HP_max (4B LE), offset 35 = SP_max (4B LE)

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
| 11004 | Thanh Lưu | heal | 22 | 1 ally | Hồi HP+SP 1 người, char only |
| 11010 | Toàn Trị Liệu | heal AoE | 42 | all ally | Hồi HP toàn party, char only |
| 12006 | ??? | ? | ? | ? | Pet skill, chưa khám phá |

### Targeting Rules
- **Attack AoE ngang (Hỏa Tiễn):** chọn target có nhiều kẻ bên cạnh nhất
- **Heal single:** chọn ally HP% thấp nhất
- **Heal AoE:** dùng khi nhiều ally bị thương
- **Defense:** khi HP < 30% (tùy config)

---

## 7b. PARTY SYSTEM (đã tách lệnh riêng)

> Quan trọng: party có **quân sư (strategist)** → hồi SP mỗi turn đánh. Đây là lý do SP regen.

**Entity ID:** mỗi nhân vật có entity 8 bytes (vd self=e6a1d6f8808d0300, gaha=b59fd6f8808d0300). Entity động theo session — bot phải đọc từ S2C khi join.

**Cấu trúc lệnh party C2S:** `c0 91 11 00 00 00 0d [SUB] 00 [self_entity 8B]`
Byte SUB quyết định hành động. Tất cả reference **self entity** (target ngầm định = member còn lại trong party 2 người).

| Hành động | Dir | Opcode | SUB | Cấu trúc | Ghi chú |
|-----------|-----|--------|-----|----------|---------|
| Mời vào party | C2S | 0x52 | — | `c0910c00000052 0100 [01 16 00]` | 0x16 = index người mời trong list |
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
- De AUTO vao Di Gioi: phai decrypt HTTPS 103.82.31.230 (dung mitmproxy + APK patched tsvtc-patched.apk de trust cert) -> lay URL+params -> replicate bang Python (bot da co lib HTTP cho login). TODO.
- map_id Di Gioi: CHUA XAC DINH chac (gia tri 0xc316 o offset 28 cua 0x03 co the la toa do).

## 7e. CHUYEN SUB-CHANNEL (opcode 0x07)

Map dong nguoi (Di Gioi) chia nhieu sub-channel. **PHAI cung channel moi moi vao party duoc.**

```
C2S 0x07 = c0 91 0b 00 00 00 07 02 00 [channel_id 2B LE]
```
- channel 81 = `07 02 00 51 00`, channel 79 = `07 02 00 4f 00`, channel 38 = `07 02 00 26 00`
- Sau khi gui -> server doi scene (0x27 + 0x61 + 0x0c handshake), nhan vat sang channel moi.
- Bot.switch_channel(n) da implement.

## 7f. TIMER DI GIOI (packet 0x55)

S2C 0x55 (len 23): `c0 91 17 00 00 00 55 01 00 01 00 00 00 [id 1B] 00 [value 2B LE] 00 00 ff ff ff 7f`
- byte[13] = id counter, byte[15:17] = value (uint16 LE)
- **id=0xac => THOI GIAN DI GIOI CON LAI (PHUT).** Vd 111 = 1h51m. (KHONG phai giay - da xac nhan thuc te)
- Di Gioi gioi han 2h/ngay. Bot doc 0xac de biet con bao nhieu giay -> tu dung/roi khi sap het.
- id khac: 0x1b (tang dan, elapsed?), 0x01 (=1). Chua can.

## 7g. QUA ONLINE (opcode 0x57)

Nhan qua khi online du so phut. **id qua = so phut moc.**

```
C2S 0x57 nhan qua: c0 91 ... 57 [02 00][03][id 4B LE][01]
S2C 0x57 ket qua:  c0 91 ... 57 [02 00][03][status 1B]   (status=0: thanh cong)
```

- **6 moc qua:** 10, 20, 30, 60, 90, 180 phut (id = so phut, vd moc 20p -> id=0x14)
- Qua online tinh theo TONG THOI GIAN ONLINE (ke ca o thanh, da xac nhan nhan duoc khi dung o thanh).
- **0x1b (S2C 0x55) = thoi gian DI GIOI**, KHONG phai online time -> KHONG dung cho qua online.
- LUU Y: C2S 0x57 [03 00] (query list) tra ve 3 entry tinh 50/70/100 - FEATURE KHAC, KHONG lien quan qua online.
- ANTI-CHEAT: client that disable nut claim khi chua du gio -> KHONG bao gio gui claim som.
  Bot phai lam giong: chi claim khi DA DU GIO. Dung uptime cua bot (time tu connect) lam
  moc online (uptime <= online time that -> uptime>=moc thi chac chan da san sang).
  Luu trang thai da nhan ra gift_claims.json theo ngay (tranh re-claim khi reconnect).
- Logic o client.claim_online_gifts().

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
