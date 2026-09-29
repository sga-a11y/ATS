# NHIỀU BẢN TS ONLINE (MULTI REGION)

Mục tiêu: 1 bot chạy được các bản TS Online khác nhau trên thế giới (VTC VN, TSM Đài Loan...).

## 1. So sánh VTC vs TSM (29/09/2026)

Nguồn: kéo `files/Lua` của 2 package trên MuMu, giải mã bằng `tools/decrypt_lua.py`
(cùng key AES), diff. Kết quả để ở `_work/tsm/` (dec_vtc/, dec_tsm/).

| | VTC (`com.vtcmobile.gz06`) | TSM (`mycard.chinesegamer.tsm` v2.7) |
|---|---|---|
| Engine | Unity + tolua | giống |
| File Lua/Data chung | 928 | 814 giống từng byte |
| protocal.lua | | chỉ lệch 1 gói: `C:001-052` (VtcMod) chỉ VTC có |
| Login | `ELogin.VNSDK` (HTTP mobiplay → token), chuỗi dài 2 byte | `ELogin.AccPwd`: acc/pass thẳng vào gói TCP 0x01, chuỗi dài **1 byte** |
| Encoding chuỗi | Unicode (utf-16-le) | **Big5** |
| Heartbeat client | 90s | 20s (bot gửi 15s → ổn cả 2) |
| Múi giờ server | UTC+7 | UTC+8 |
| Skill riêng | | 41001-41004, 42004, 45004, 46004 |

**Kết luận:** chung protocol → core bot (combat/party/dungeon/vận tiêu) dùng lại được. Chỉ khác:
server, login, encoding, múi giờ, tính năng đã mở. Localize text hiển thị: bỏ qua.

⚠️ Encoding KHÔNG phải localize: sai encoding là hỏng login, tên party, so khớp tên.

## 2. Kiến trúc

`bot/region.py` — MỘT chỗ duy nhất khai báo các bản (dict `REGIONS`), sync sang APK.
(Không để JSON riêng vì APK đọc data qua asset khác PC.)

```
REGIONS["vtc"] = {login: "mobiplay", xor_key: 0xAD, encoding: "utf-16-le", utc_offset: 7}
REGIONS["tsm"] = {login: "accpwd",   xor_key: 0xAD, encoding: "big5",      utc_offset: 8}
```

- `GameClient(..., region=None)` → `self.region` (mặc định `vtc`). Mỗi client region riêng → chạy
  song song acc nhiều bản được.
- `protocol.xor/encode(..., key)` nhận key theo region.
- Mọi `.decode/.encode` chuỗi trong gói dùng `self.region.encoding`.
- Giờ event/so hạn dùng `region.server_now()` = UTC + utc_offset (không phụ thuộc giờ máy).
  Lợi luôn cho VTC: máy để sai múi giờ vẫn vào event đúng giờ.
- Log/hiển thị giờ cho user vẫn dùng giờ máy (cố ý).

## 3. Trạng thái

- [x] Giai đoạn A: refactor, VTC chạy y nguyên (gói auth/xor/chuỗi so byte-by-byte với HEAD: giống hệt).
- [x] `battle_tracker`, `legion_damage`, `remote_cmd`, `_parse_exp_broadcast`: nhận region/encoding
      của client. **Bug thật 29/09 (party 55 TSM):** tracker decode tên unit bằng UTF-16 → "doc ngoai
      hinh nguoi choi hong" → tracker g=0 không bao giờ active → `in_battle` sai → PB spam
      `0x14 0600` giữa trận → server ngắt **mã 47**. Train không lỗi vì không spam hội thoại.
- [x] Độ dài chuỗi: `Region.char_bytes` (UTF-16 = 2, Big5 = 1). Check `% 2` cũ làm TSM không đọc
      được tên char ASCII lẻ byte (`stmot` = 5 byte).

### Nguyên tắc (user chốt 29/09): KHÔNG làm hỏng VTC, sau còn thêm NHIỀU bản
- Không `if game == "tsm"` trong code. Khác biệt = thuộc tính trong `REGIONS`, code hỏi `self.region`.
- Không dùng `_region.get()` (mặc định) trong đường xử lý gói của client — truyền `self.region`.
- Thêm bản mới = thêm 1 entry `REGIONS` + server `"game"` + event `"games"`, không sửa logic.
- Mỗi lần sửa: so gói tin VTC byte-by-byte với HEAD + chạy đủ test.
- [x] Capture login TSM (`captures/tsm_login_20260929.pcap`): XOR **0xAD** (giống VTC), server
      `34.81.22.35:6614`, serverId **21**. Gói login:
      `C:001-000 +ver(2)=0x0102 +serverId(2) +connectCode(4)=0 +kind(1)=1 +L(1)+acc +L(1)+pwd`.
      Cùng khuôn gói auth VTC (VTC: kind=25, độ dài chuỗi 2 byte).
- [x] Login `accpwd` cho TSM (`auth.build_accpwd_auth_packet`, gói sinh ra khớp capture từng byte).
      `run_party_digioi`: region `accpwd` → bỏ HTTP login, `user_id/access_token` = acc/pass game.
- [x] Chọn game: **KHÔNG lưu field riêng — suy từ server** (`servers.json` field `"game"`, không có
      = vtc; server TSM `tsm_21`). Không thể lệch game ↔ server.
  - PC GUI: dòng đầu tab party `Game: [VTC▼]  Server: [..▼]`. Đổi game → lọc server + event.
  - APK: dialog party có dropdown Game cạnh Server (`Servers.Info.game`, `GAMES`).
  - `config.py` (PC + APK) và `setup_party_runtime` (APK, suy game từ IP+id) ghi `PARTY_CONFIG["game"]`.
- [x] **Event theo game**: `events.json` mỗi event có thể khai `"games": ["vtc","tsm"]`, không khai
      = chỉ VTC. GUI/APK chỉ hiện event của game đang chọn. Bot chặn ở 1 chỗ
      (`region.chan_event_sai_game`): party mode event mà event không thuộc game → về `stand` + log.
      Lịch giờ event ghi theo **giờ server của bản đó** (`server_now()`).
- [x] **Đổi quà event theo game**: cache `event_exchange.json` (VTC, giữ tên cũ) /
      `event_exchange_tsm.json` (+ `_sig.txt` riêng). Tick đổi quà reset theo chữ ký của đúng game.
- [ ] Tách data theo bản (servers.json, train_maps, map_gates, npc_names...).
- [ ] `features` bật/tắt tính năng theo bản.
