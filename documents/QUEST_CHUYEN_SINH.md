# MODE "LÀM QUEST" — chuyển sinh 1 (Bát đại Cự Thú)

> Trạng thái 03/10/2026: khung (mode, chỉ định chủ party, xoay vòng, thoát game) + **bộ chạy quest
> theo kịch bản**. **Đủ kịch bản 8/8** quest Bát đại Cự Thú (mỗi quest một capture
> `captures/cs1_<id>_*.pcap`, giữ tới khi chạy ổn). **CHƯA chạy thật lần nào.**

## Chủ party làm một bước (`quest_runner.lam_buoc`)

```
quest tiếp theo = quest ĐANG LÀM (mission_steps server gửi) > quest đầu tiên chưa xong CÓ kịch bản
  → điểm cần tới: chưa nhận = `nhan_tai` (từ capture) · bước N = steps[N] (data client + kịch bản)
  → khác map: follow_smart_route = TELE về thành gần nhất rồi đi cổng (user 03/10: tele cho nhanh)
    cùng map: navigate_to
  → chạm các cửa sự kiện `truoc` (nếu có) → kích hoạt NPC (`0x20 020008` + `0x14 01`) / cửa (`0x14 08`)
  → quest_hoi_thoai: `0x14 06` đúng luật client, chọn theo `chon`, trận thì chờ cả đội đánh xong
  → KIỂM: mission lên bước hoặc cờ xong bật. Không lên → log "KHONG LEN BUOC", chờ 30s thử lại
```

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| `0x14 06` chỉ khi conduct bật, không session/interacting/trận | `[CAPTURE]` Lua client | gửi thừa = ngắt mã 5; giữa trận = mã 47 |
| Đặt cờ session **trước** khi gửi `0x14 06` | **BOT TỰ ĐẶT** | test phát lại capture bắt được: gói trả lời tới trước khi đặt cờ thì bị ghi đè, bot đứng chờ mãi |
| Mã chọn chỉ lấy từ capture; hết mã mà server vẫn hỏi → DỪNG | **BOT TỰ ĐẶT** | chọn sai = ngắt kết nối |
| Chủ party đang đi quest mà dính trận quái → **giữ việc `quest`**, không đổi `nghi` | `[LOG]` | party 7, 04/10 (lặp 4/4): `03:12:43 ENGINE: taot006 -> nghi` → quest huỷ giữa đường |
| Đang giữa đường thì **đi bộ tiếp**, chỉ tele khi đi bộ dài hơn (số cổng) | `[LOG]` | tele khi còn trong đội = client bắt rời đội trước: `03:12:59 Teleport: dang o to doi (4 member) -> ROI DOI truoc` → đội tan |
| Movie: chờ cố định `QEV_MOVIE_WAIT` = 16s | `[SUY ĐOÁN]` | capture đo 9s / 15s; chưa biết server có kiểm |
| Bước `ev_kind = 0` (chỉ toạ độ) = cửa ẩn tại toạ độ đó, số cửa lấy từ capture (`cua`) | `[CAPTURE]` | 10324, 10326, 10328 |
| Bước bị server làm gộp (nhảy +2/+3) mà char lỡ kẹt ở giữa → chưa có kịch bản, log + đứng yên | **BOT TỰ ĐẶT** | không đoán |

Test: `tests/test_quest_hoi_thoai_capture.py` phát lại **đúng chuỗi gói server** của 5 đoạn hội thoại
trong 2 capture và so chuỗi bot gửi với client thật (khớp từng gói, kể cả chọn + đánh boss).

## Luật user chốt (03/10)

1. Luôn chạy theo **party**. User **chỉ định chủ party**, không mặc định acc đầu danh sách như
   các mode khác.
2. Chủ party làm quest, các acc còn lại chỉ đứng trong đội để hỗ trợ (đi theo, đánh cùng).
3. Chủ party xong hết chuỗi quest → **chỉ định acc đầu tiên (theo thứ tự danh sách) chưa xong**
   làm chủ party, làm tiếp.
4. Cả party xong hết → **thoát game**.

Vì sao bắt buộc xoay vòng: cả 8 quest đều `gainWay = 0` (đo được từ `Mark_C.dat`), tức **chỉ người
kích hoạt** được tính. Member đi theo đánh hỗ trợ không xong quest.

## Flow từ góc nhìn user

```
GUI/APK: chọn mode "Làm quest" → chọn Quest + Chủ party → Chạy
  → bot đưa acc được chỉ định lên làm chủ party (slot 0)
  → cả party về THÀNH GẦN BƯỚC KẾ TIẾP của chủ party, lập đội (đủ đội mới làm — L0)
  → chủ party làm quest; member đứng trong đội
  → chủ xong 8/8: log "QUEST: <chu> xong het ... -> CHI DINH <acc> lam chu party"
       → dừng party, start lại với chủ party mới (không login lại bằng tay)
  → cả party xong 8/8: log "QUEST: ca party xong het ... -> THOAT GAME"
```

Chủ party user chọn được giữ trong `accounts.json`; bot đổi chủ **chỉ trong phiên chạy**, không ghi
ngược ra file.

## Ràng buộc

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Chỉ người kích hoạt được tính quest (`gainWay=0`) | `[CAPTURE]` data client | `Mark_C.dat`, `MarkData.ReadInfo` trường `gainWay` |
| Biết acc đã xong quest nào bằng cờ nhiệm vụ (`0x18 sub07/05`) | `[CAPTURE]` | `client.mark_flag_get(bit)`, 1-based như `CheckFlag` client |
| Acc chưa nhận cờ (đang login) = **chưa biết**, không phải "chưa xong" | **BOT TỰ ĐẶT** | đoán bừa là xoay chủ party oan |
| Đổi chủ party = **dừng party rồi start lại** | **BOT TỰ ĐẶT** | vai leader gắn lúc START (`run_account(is_leader)`, `_pe_la_leader`); đi lại đúng đường chỉ định từ đầu thay vì vá cờ trên acc đang chạy. Gói `C:013-009 <換隊長>` có trong client nhưng bot chưa dùng, chưa capture |
| Đủ đội mới làm quest; thiếu người thì gom lại | user (L0) | kể cả đang giữa quest — gom ở thành gần bước đang làm |
| **Không có ô chọn thành tập kết**: thành gom = thành tele mà `build_route` chọn cho map của bước kế tiếp của chủ party | user chốt 03/10 | *"mỗi quest gần 1 thành khác nhau ... quest nào thì bot tự chọn thành gần nhất"*. `_quest_thanh_tap_ket` tính lại khi chủ sang bước/quest khác; chủ chưa nhận cờ → chưa có thành → party đứng chờ |
| Đủ đội = `so_member` (roster server `S:013-006`) của chủ ≥ số acc đang sống − 1 | `[CAPTURE]` | CORE_FLOW rule 4, cấm tự đếm |

## Code

| Chỗ | Việc |
|---|---|
| `tools/crack_mark_steps.py` | `.dat` → `marks.json` (3448 nhiệm vụ / 4505 bước, không theo git) |
| `tools/build_quests.py` | `marks.json` → `quests.json` (chỉ chuỗi quest bot làm, đóng gói exe + APK) |
| `bot/quest_runner.py` | đọc trạng thái, `chon_chu_party`, `quest_tiep_theo`, `chay` (khung) |
| `bot/party_modes.py` `_quest_viec` | quyết định việc từng acc mode `quest` |
| `run_party_digioi.py` `_ap_chu_party_quest` | đưa chủ party chỉ định lên slot 0 lúc `start_party` |
| `run_party_digioi.py` `_quest_dieu_phoi` / `_quest_doi_chu` | xoay vòng chủ party / thoát game |
| `gui.py` `_render_quest` · APK `MainActivity.kt` | ô Quest + Chủ party |
| `tests/test_quest_mode.py` | 24 test |

Key config party: `mode = "quest"`, `quest_key` (key trong `quests.json`), `quest_leader`
(username). `start_city_id`/`city_flag` KHÔNG dùng ở mode này.

## Chưa làm (chờ capture)

- Nhận quest ở NPC (data client không có, chỉ biết nơi nhận — user đọc trong game).
- Mã chọn đáp án hội thoại từng NPC (`0x14 09`, đoán sai = server ngắt kết nối).
- Bước chỉ có toạ độ (`ev_kind = 0`): sự kiện tự bật khi đi tới — cần capture xem tới đâu thì nổ.
- Bước bắt tổ đội (`team = true`) + đánh boss Cự Thú.
- Phần cuối chuyển sinh: lên cấp 120, gặp Thái Bạch Tinh Quân, gói `C:023-046`.
