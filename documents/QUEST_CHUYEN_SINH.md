# MODE "LÀM QUEST" — chuyển sinh 1 (Bát đại Cự Thú)

> Trạng thái 03/10/2026: khung (mode, chỉ định chủ party, xoay vòng, thoát game) + **bộ chạy quest
> theo kịch bản**. **Đủ kịch bản 8/8** quest Bát đại Cự Thú (mỗi quest một capture
> `captures/cs1_<id>_*.pcap`, giữ tới khi chạy ổn). **CHƯA chạy thật lần nào.**

## Chủ party làm một bước (`quest_runner.lam_buoc`)

```
quest tiếp theo = quest ĐANG LÀM (mission_steps server gửi) > quest đầu tiên chưa xong CÓ kịch bản
  → điểm cần tới: chưa nhận = `nhan_tai` (từ capture) · bước N = steps[N] (data client + kịch bản)
  → chưa ở map của bước / chưa đủ đội: lệnh DI MAP CÓ SẴN (`party_route_maps`) từ thành cả party
    đã mở gần nhất → map của bước: tele về thành, gom, lập đội, chủ kéo cả đội đi bộ
  → cả đội đã ở map, đủ đội: chủ party đi bộ tới NPC/cửa trong map
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
| **Di chuyển = lệnh DI MAP có sẵn** (`party_route_maps(thành cả party đã mở gần nhất, map bước)`), y mode city khi thành chưa mở. Không có code di chuyển riêng của quest | user chốt 04/10 | *"mọi cơ chế đều có sẵn rồi ... m dùng lại hay code mới"*. Bản tự viết trước đó hỏng liên tiếp: p9/p11 chọn thành chưa mở (`CHUA MO` ×3684), p27 chốt thành khi mới 1/5 acc vào (×1624), p13 chủ tự tele → rời đội (22 vòng) |
| Chỉ ra lệnh DI MAP khi **CẢ PARTY đã vào world + nhận cờ nhiệm vụ**; mỗi đích ra 1 lần, tới nơi mà đội vẫn chưa đủ thì ra lại sau 30s | `[LOG]` | party 27, 04/10: `_pick_start_city` bỏ qua acc chưa có client |
| Chủ party **đang làm dở sự kiện quest** thì KHÔNG ra lệnh DI MAP / không đổi việc (kiểm TRƯỚC mọi nhánh) — chờ hết sự kiện (`S:020-008`) | `[LOG]` | server báo lên bước TRƯỚC khi sự kiện hết. Party 11, 04/10: ra lệnh ngay → hội thoại bị huỷ (`su kien dung`) → server coi chủ vẫn trong sự kiện, `Teleport -> city 12001` bị nuốt 77 lần, chủ kẹt Quan Phủ, member ở Hội Kê |
| Bước gộp bị kẹt (data `ev_kind 0`, không kịch bản riêng) trùng toạ độ một cửa đã có kịch bản của cùng quest → dùng lại cửa đó | `[SUY ĐOÁN]` | party 13, 04/10: sự kiện B1 Phẫn Nộ bị huỷ ở bước 2 → kẹt bước 2 (cùng (2207,282) với cửa 2) → đứng ~30 phút. Chạm cửa không sự kiện = `S:020-008` kind 0x23 vô hại |
| **L0 — không nhánh nào để party lẻ đứng im**: chưa đủ đội thì cùng map → lập đội; khác map → lệnh DI MAP tới map của bước, hoặc **về chỗ chủ party** nếu không có bước làm được. Đủ đội mà không có bước → giữ đội đứng chờ | user (L0, RULE_DIEU_PHOI) | party 13, 04/10: nhánh "chờ" = cả party `nghi`, roster 0/4 ~30 phút. User: *"rule tối thượng đủ party rồi làm gì thì làm của t đâu"* |
| Login ở map event: `go_to_town` tới thành đã mở tự đi bộ ra khỏi map event trước khi tele | `[CAPTURE]`/user 27/09 | trước đây bị chặn sớm ở bước "thành chưa mở" nên không chạy tới (party 11, 04/10) |
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
  → chờ cả đội làm xong việc đầu phiên (login chores, nhiệm vụ ngày) bằng worker sẵn có
  → lệnh DI MAP có sẵn đưa cả party tới map của bước kế tiếp (gom, lập đội, kéo đi bộ — L0)
  → chủ party làm quest; member đứng trong đội
  → chủ xong 8/8: log "QUEST: <chu> xong het ... -> CHI DINH <acc> lam chu party"
       → đổi chủ TẠI CHỖ (không logout), log "DA DOI chu party X -> Y tai cho"
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
| Đổi chủ party **ngay tại chỗ, không logout ai**: chủ mới lên slot 0 trong config (engine đọc live mỗi nhịp), gán lại `_pe_la_leader`, chủ cũ rời đội → `lap_party` có sẵn mời lại. Acc đã xong vẫn online hỗ trợ; chỉ cả party xong mới thoát | `[LOG]` + user 04/10 | bản cũ dừng cả party rồi start lại: p3/4/5 04/10 cả 5 acc STOP mỗi lần đổi, dừng hụt thì `KHONG start lai` → party tắt hẳn. User: *"thằng nào xong rồi vẫn online để hỗ trợ"* |
| Đủ đội mới kích hoạt bước quest; thiếu người thì gom lại | user (L0) | hội thoại đã mở được chạy đến khi server đóng sự kiện; kiểm tra lại đội ngay trước mỗi lần kích hoạt |
| **Không có ô chọn thành tập kết** | user chốt 03/10 | lệnh DI MAP tự chọn thành xuất phát (`_pick_start_city`, cả party đã mở) theo map của bước kế tiếp |
| Đủ đội = mọi acc trong phiên đã online và `so_member` (roster server `S:013-006`) của chủ ≥ số acc trong phiên − 1 | `[CAPTURE]` + user (L0) | acc đang kết nối lại vẫn phải được chờ; chỉ acc đã tắt hẳn mới bị loại khỏi snapshot |

## Code

| Chỗ | Việc |
|---|---|
| `tools/crack_mark_steps.py` | `.dat` → `marks.json` (3448 nhiệm vụ / 4505 bước, không theo git) |
| `tools/build_quests.py` | `marks.json` → `quests.json` (chỉ chuỗi quest bot làm, đóng gói exe + APK) |
| `bot/quest_runner.py` | đọc trạng thái, `chon_chu_party`, `quest_tiep_theo`, `chay` (khung) |
| `bot/party_modes.py` `decide_quest` · `run_party_digioi.py` `_quest_den_dich` | việc từng acc khi đã tới nơi · ra lệnh DI MAP có sẵn |
| `run_party_digioi.py` `_ap_chu_party_quest` | đưa chủ party chỉ định lên slot 0 lúc `start_party` |
| `run_party_digioi.py` `_quest_dieu_phoi` / `_quest_doi_chu` | xoay vòng chủ party / thoát game |
| `gui.py` `_render_quest` · APK `MainActivity.kt` | ô Quest + Chủ party |
| `tests/test_quest_mode.py`, `tests/test_quest_regressions.py` | Logic quest và hồi quy từ review 04/10, log vận hành 05/10 |

Key config party: `mode = "quest"`, `quest_key` (key trong `quests.json`), `quest_leader`
(username). `start_city_id`/`city_flag` KHÔNG dùng ở mode này.

## Chưa làm (chờ capture)

Sửa theo log 05/10: việc ngày hoàn tất trước khi tự ra lệnh đi quest; sau khi bắt đầu gom đội,
không giao mới việc lẻ có thể tách đội. Hội thoại vẫn được giữ đến khi worker nhận kết quả và
xóa `_qev`, kể cả server đã báo hết sự kiện. Hội thoại hoàn tất 3 lần mà bước/cờ nhiệm vụ không
tiến triển thì ngừng kích hoạt lại bước đó và ghi cảnh báo; bước mới từ server vẫn được làm tiếp.
Khởi động lại acc cho phép thử lại. Đây là giới hạn của bot, không phải luật của server.

Ca `mhmmot` (00:50:52–00:58:27, 15 lần nhận Sâm Lan Thái Hồ không tiến triển): NPC 4 tại
18001 khớp capture 03/10. `MarkData.ReadInfo`/`marks.json` không cung cấp điều kiện nhận bị thiếu;
chưa xác định lý do server không cấp nhiệm vụ. Giữ nguyên NPC và mã chọn, cần capture ca này
để kết luận nguyên nhân.

- Nhận quest ở NPC (data client không có, chỉ biết nơi nhận — user đọc trong game).
- Mã chọn đáp án hội thoại từng NPC (`0x14 09`, đoán sai = server ngắt kết nối).
- Bước chỉ có toạ độ (`ev_kind = 0`): sự kiện tự bật khi đi tới — cần capture xem tới đâu thì nổ.
- Bước bắt tổ đội (`team = true`) + đánh boss Cự Thú.
- Phần cuối chuyển sinh: lên cấp 120, gặp Thái Bạch Tinh Quân, gói `C:023-046`.
