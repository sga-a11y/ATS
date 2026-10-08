# MODE "LÀM QUEST" — chính tuyến + phụ tuyến (sinh tự động từ `Eve.emg`)

> Trạng thái 08/10/2026: **BẢN THIẾT KẾ, CHƯA CODE.** Phân tích + luật user chốt trong cùng ngày.
> Nối tiếp mode quest CS1 (`documents/QUEST_CHUYEN_SINH.md`) — dùng lại bộ chạy, đổi nguồn data.

## Mục đích (user chốt 08/10)

Chạy quest để lấy **thưởng quest** (server tự phát lúc trả quest, `S:020-100`) và **thưởng thành
tựu** (435/600 thành tựu là `kind 15` = "xong quest X", bot đã có `claim_achievements`).

## Nguồn data: `Eve.emg` chứa nguyên kịch bản server

`[CAPTURE]` Phần `NpcEvent` + `Fight` của mỗi scene trong `CompreseData/Eve.emg` (client đọc vào
nhưng không dùng) là điều kiện + kết quả của từng NPC/cửa. Đối chiếu 8/8 capture Cự Thú: khớp chỗ
nhận (kể cả cửa ẩn 4 của 10328), cửa ẩn, mã chọn, nhảy bước (10360 chọn 31 → +3), cửa "chạm trước"
(10528 cửa 3 → hiện NPC 1), boss (19506 trận 11 = Thượng Cự Thú lv90 + 7 lính). NPC 59411 đòi đủ
đúng 8 cờ Cự Thú.

Cấu trúc (`_lua_dec/Data/Eve/*.lua`, thứ tự: Npc → Goods → Door → Mine → Surface → SceneInfo →
Group → NpcEvent → Fight). Điều kiện nhóm AND theo trường `and` (N điều kiện liền nhau cùng `toRes`).

| Mã | Nghĩa | Mức chắc |
|---|---|---|
| ĐK `cls2 pst1` | bước mission (= `0x18 sub06`) | đo được |
| ĐK `cls2 pst2 ops0` | chưa nhận mission | đo được |
| ĐK `cls2 pst3` | cờ xong (bitId của mã) | đo được |
| ĐK `cls10 par=surface pst=N` | đã chọn mã N (30 = mục 1…) | đo được |
| ĐK `cls8 pst1/2/3` | thắng / thua / chạy trận | đo được |
| ĐK `cls7 pst1` | cấp nhân vật | nghi |
| ops | 1 `<` · 2 `>` · 4 `>=` · 5 `==` | nghi |
| KQ `t0 c2 pst1 val N` | mission +N bước (mã lẻ = bật cờ xong) | đo được |
| KQ `t0 c2 pst3 val0` | xoá mission | đo được |
| KQ `t3 mean M` | vào trận `Fight[M]` của scene | đo được |
| KQ `t6 c3 mean S` | chờ chọn trên surface S | đo được |
| ĐK `cls1`, `cls9`, `cls12`… | nghi số item / NPC đi theo | chưa biết |

Loại quest (`Mark_C.dat` `kind`, comment `MarkData.lua`):

| kind | Có bước | Tìm được chỗ nhận | Ghi chú |
|---|---|---|---|
| 1 主線 chính tuyến | 400 | 386 | 14 hụt: quest Tân thủ thôn đầu game |
| 3 指引 = phụ tuyến kiểu TS cổ | 388 | 350 | |
| 2 支線 | 90 | 15 | Phần lớn là quest KHUNG tự lên bước theo chính tuyến → bot không làm riêng. "Địa Điểm Tham Quan"/"Tìm Nguyên Liệu": data không có chỗ nhận → bỏ |

`gainWay = 0` ở cả 400 + 388 → chỉ người kích hoạt được tính (như CS1).

## Luật user chốt (08/10)

1. **Quest KHÔNG có trận nào → bỏ party, mỗi acc đi lẻ.** Ngoại lệ L0: pha đi lẻ không gom party
   (ghi vào `RULE_DIEU_PHOI.md` khi code).
2. **Quest có trận → cả party, xoay vòng chủ y như 8 Cự Thú.** Chia theo CẢ QUEST (có trận ở bất
   kỳ bước nào thì cả quest đi party) — đề xuất của Claude, user chưa phản đối.
3. Trận nào solo được → user tự đánh dấu tay sau (file whitelist, mặc định rỗng).
4. Đi lẻ gặp quái **không phải quái quest** → bỏ chạy (`flee`).
5. Gặp bước bot chưa làm được (gom đồ 364 bước, dẫn NPC 208 bước, quest không có data) → acc **đứng
   yên**, bắn thông báo vào **"Chú ý"**.
6. Hết quest làm được (xong hết / thiếu cấp / kẹt) → **dừng và tắt game**.

Phân nhóm đo được: đi lẻ 100 chính + 184 phụ · party 300 chính + 204 phụ.

## Flow từ góc nhìn user

```
GUI/APK: mode "Làm quest" → ô Quest chọn "Chính tuyến" / "Phụ tuyến" → Chạy
 → mỗi acc: đọc cờ xong + mission đang làm + cấp → ra quest kế tiếp của RIÊNG acc đó
     (đang làm dở > quest đủ điều kiện nhận, mã nhỏ nhất)
 → quest kế không có trận: acc rời party, tự DI MAP + đi bộ tới NPC/cửa, hội thoại, chọn mã từ data
 → quest kế có trận: acc vào HÀNG CHỜ PARTY
 → khi mọi acc còn chạy đều ở hàng chờ (hết việc lẻ): gom party → lần lượt từng acc làm chủ
   đánh quest party của mình (xoay vòng như CS1) → xong mà quest kế là loại lẻ thì tách ra đi lẻ
 → mỗi quest xong: claim_achievements (thưởng thành tựu)
 → acc kẹt bước chưa hỗ trợ: đứng yên + "Chú ý": "<acc>: quest X bước N cần item Y / dẫn NPC Z"
 → acc hết quest làm được → tắt game acc đó; cả party hết → log THOAT GAME
```

## Chưa làm / rủi ro

- Data client vs server VTC có thể lệch → giữ chặn "3 lần hội thoại xong không lên bước thì dừng".
- Một surface có nhiều mã cùng dẫn tới lên bước → ưu tiên nhánh KHÔNG có trận.
- Giai đoạn 2: gom đồ / dẫn NPC (chưa biết lấy item ở đâu).

## Code dự tính (chưa làm)

| Chỗ | Việc |
|---|---|
| `tools/crack_eve_quest.py` (mới) | `Eve.emg` + `marks.json` + `npc_table.json` → `main_quests.json` |
| `bot/quest_runner.py` | quest kế theo điều kiện data; cờ "đi lẻ/party" mỗi quest |
| `run_party_digioi.py` | pha đi lẻ / hàng chờ party / xoay chủ; `quest_notify_items` cho "Chú ý"; tắt game |
| `gui.py` · APK `MainActivity.kt` | ô Quest thêm 2 chuỗi; "Chú ý" hiện dòng quest kẹt |
| `tools/sync_apk_python.py` · `build_product.py` | khai báo `main_quests.json` cả `SHARED_ASSETS` + `DATA_JSON` |
| `tests/` | data sinh ra khớp 8 kịch bản capture CS1; luật đi lẻ/party; thông báo kẹt |
| `KNOWLEDGE.md` · `RULE_DIEU_PHOI.md` | cấu trúc NpcEvent/Fight; ngoại lệ L0 pha đi lẻ |
