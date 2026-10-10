# MODE "LÀM QUEST" — chính tuyến + phụ tuyến (sinh tự động từ `Eve.emg`)

> Trạng thái 08/10/2026: **ĐỢT 1 XONG (data)**, đợt 2 (bot chạy) chưa làm.
> Nối tiếp mode quest CS1 (`documents/QUEST_CHUYEN_SINH.md`) — dùng lại bộ chạy, đổi nguồn data.
>
> - `tools/crack_eve_quest.py` → `main_quests.json` (chính tuyến 400 quest / 380 có chỗ nhận /
>   2523 bước, 77 bước không có sự kiện riêng; phụ tuyến 388 / 376 / 1383, 40). Khai báo
>   `SHARED_ASSETS` + `DATA_JSON`.
> - `tests/test_main_quests_khop_capture.py`: khớp 8/8 capture Cự Thú (chỉ để KIỂM bộ đọc data —
>   capture là bằng chứng thật duy nhất về server; quest chạy thử không liên quan Cự Thú).
> - Test đầu tiên (user chốt 08/10): **10 quest chính tuyến đầu tiên acc CHƯA làm, tất cả đi
>   solo.** Nấc A chỉ đọc (log kế hoạch, không gửi gói) → nấc B chạy thật.
> - **Nấc A ĐÃ CODE (08/10)**, user đối chiếu sổ nhiệm vụ: khớp (vuchin: đúng 3 quest).
> - **Nấc B ĐÃ CODE (09/10), CHƯA CHẠY THẬT** — đi lẻ làm thật, xem mục "Nấc B".
> - **User chốt 09/10 (chiều):** bỏ giới hạn 10 quest/phiên (*"giới hạn làm gì, ko cần thiết"*);
>   THỨ TỰ: [Chính] trong sổ trước → hết (hoặc kẹt) thì [Hướng Dẫn] trong sổ → [Chính] xuất hiện
>   lại thì quay về Chính. p52 16:28: 3 acc xong 10023 + 12288 (đánh Bánh Bao Thịt 13–50s), sổ
>   còn 12290/12292/12296 [Hướng Dẫn].
> - Phụ tuyến chưa hiện (user 08/10).

## Nấc A — chỉ đọc (code 08/10)

```
GUI/APK: mode "Làm quest", Quest = "Chính tuyến" → Chạy
 → việc đầu phiên (login chore, daily) như mode quest CS1 (`_quest_cho_viec_dau`)
 → mỗi acc sống, không đang đánh → việc `quest` → `quest_runner.chay_chinh_tuyen_doc`:
     chờ cờ nhiệm vụ → tính kế hoạch → log khi kế hoạch ĐỔI → đứng yên 30s, lặp
 → KHÔNG lập party, KHÔNG DI MAP, KHÔNG xoay chủ, KHÔNG gửi gói quest
```

Log mẫu:
```
[acc] QUEST CT (CHI DOC): cap 150 | xong 37/400 | dang do 1 | nhan duoc 12 | chua danh gia duoc 3 [...]
[acc] QUEST CT   1. 10384 Hang Sâu Tuyết Động [PARTY] buoc 2/3 -> map 19506 npc 2 (550,320) | CO TRAN boss lv90
```
**User chốt 08/10 — cách a:** chỉ làm quest ĐANG CÓ trong sổ nhiệm vụ; xong thì server tự giao
quest tiếp (y chơi tay). Quest server cho nhận ngay mà sổ không có (vd 10268 chỉ đòi cấp) chỉ đếm
trong log, KHÔNG tự đi nhận (`ke_hoach_chinh_tuyen(chi_so=True)`; cách b = `chi_so=False`).

Thứ tự: quest ĐANG LÀM (`mission_steps`, server hay tự giao quest sau khi xong quest trước) →
quest nhận được ngay (mọi điều kiện server đúng), theo **thứ tự cốt truyện** `thu_tu` (độ sâu
chuỗi giao quest, tool tính) rồi mới tới mã. Log còn in "da xong: …" và "mission dang co: …" để
đối chiếu sổ nhiệm vụ.

`[LOG]` qg506 08/10 (lv187, xong 16/400, đang dở 0): bản đầu xếp theo MÃ → 10098 "Tấn công Từ
Châu" (giữa truyện) lên đầu; user: *"đoạn đầu gặp Giản Ung trả lời 3 câu hỏi, đánh Đốc Bưu, gặp 3
anh em, mã phu bắt ngựa"*. Data đúng như vậy: 12280 → 12282 → 12284 → 12286 (Tân Thủ Thôn) →
**12288 Trác Quận kỳ ngộ** B1 Giản Ung (12136 NPC 1, chọn 30 → 32 → 32 → 31: xoá 12288 + giao
**10001 Đào Viên Kết Nghĩa**: 12002 NPC 3 đánh trận → Trương Phi → Quan Vũ → Trương Thế Bình → Lưu
Bị) → 12288 B2 Mã Phu (12001 NPC 6). Mã quest KHÔNG theo cặp chẵn/lẻ cố định: 10001 là mã LẺ có
bước. "Xoá mission KÈM giao quest khác" = chuyển tiếp; xoá trơn = bỏ quest (10528 chọn 31) `[nghi]`.
Nhiều quest giữa truyện (10268, 8 Cự Thú) chỉ đòi cấp → acc cấp cao nhận được ngay, không theo chuỗi. Điều kiện bot chưa đọc được
(`cls1` item, `cls9`…) = "chưa đánh giá được", không đoán là đúng. `[LOẠI]` = PARTY nếu quest có
trận ở bất kỳ bước nào (theo data; user sẽ đánh dấu tay trận solo được).

| Chỗ | Việc |
|---|---|
| `quests.json` mục `chinh_tuyen` `{label, nguon}` (`tools/build_quests.py`) | GUI/APK tự hiện chuỗi, không sửa Kotlin |
| `quest_runner.chuoi()` | KHÔNG trả mục chính tuyến → bộ chạy CS1 lỡ gặp chỉ thấy "không có chuỗi" (không hiểu nhầm "xong hết → thoát game") |
| `quest_runner.danh_gia_dk / ke_hoach_chinh_tuyen / chay_chinh_tuyen_doc` | đánh giá điều kiện server, kế hoạch, log |
| `run_party_digioi._chinh_tuyen_quyet` | việc từng acc; dùng lại việc `quest` có sẵn (đã khai báo trong engine) |
| `tests/test_quest_chinh_tuyen.py` | điều kiện, kế hoạch, không gửi gói, quyết định việc |

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
| 1 主線 = nhãn game **[Chính]** | 400 | 386 | 14 hụt: quest Tân thủ thôn đầu game |
| 3 指引 = nhãn game **[Phụ]** | 388 | 350 | |
| 2 支線 = nhãn game **[Hướng Dẫn]** | 90 | 15 | Hương Dũng, Giúp Lưu Yên đưa thư… có NPC/bước thật. User 08/10: *"giúp lưu yên là quest khác"* → KHÔNG thuộc chuỗi Chính tuyến, key riêng `huong_dan` trong `main_quests.json`, log in "[Huong Dan] dang co (CHUA LAM)". "Địa Điểm Tham Quan"/"Tìm Nguyên Liệu": data không có chỗ nhận |

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

## Nấc B — đi lẻ làm thật (code 09/10, chưa chạy thật)

Luật user chốt 08/10: quest không có trận → đi lẻ; có trận → chỉ đi lẻ khi có trong
`quest_solo.json` (đánh dấu tay; ban đầu `[10001]` — *"Đào Viên Kết Nghĩa đánh solo toàn bộ"*);
còn lại đứng yên + "Chú ý" (party làm sau). Sổ hết quest [Chính] và [Hướng Dẫn] → tắt game
acc đó (09/10: không còn giới hạn số quest mỗi phiên).

```
mỗi nhịp, mỗi acc (quest_runner.chay_chinh_tuyen):
 kế hoạch (cách a: quest [Chính] trong sổ xếp như client, RỒI [Hướng Dẫn] trong sổ theo mã;
 trừ chuỗi Cự Thú) → quest ĐẦU TIÊN làm được:
   bước "thiếu" / thiếu item / thiếu ô võ tướng / có trận chưa đánh dấu solo / 3 lần không lên
   bước → vào "Chú ý", xét quest sau
 → lam_buoc_ct: trong party → leave_party → follow_smart_route (tele thành gần + đi bộ, GẶP QUÁI
   BỎ CHẠY) → chạm cửa "trước" → TẮT flee → bấm NPC/cửa → quest_hoi_thoai trả lời THEO SURFACE
   (`chon_map`) → đánh trận nếu có → kiểm: cờ xong / bước đổi / mission mới → claim_achievements
 → không còn gì làm được, không kẹt → `_qct_het` → engine stop_account (1 lần)
```

| Ràng buộc | Loại | Ghi chú |
|---|---|---|
| Trả lời chọn theo SURFACE server hỏi (`resultMeanNo` = pkt[22:24]) | `[CAPTURE]` | 10806/10528/10360/10326: mean = surface `Eve.emg`; phát lại capture 10806 B1 + 10528 B1 với `chon_map` khớp từng gói (`tests/test_quest_chinh_tuyen.py`) |
| Surface không có trong bảng → DỪNG, không đoán | **BOT TỰ ĐẶT** | chọn sai = ngắt kết nối |
| NPC xin gia nhập cần ô võ tướng trống: đang dùng + số gia nhập ≤ 4 | `[CAPTURE]` Lua + user 08/10 | `Role.maxFollowNpc = 4`, `EventHandler` class 3 style 1 "要求加入玩家"; 10001 B3 Trương Phi, B4 Quan Vũ (`gia_nhap` trong data) |
| Ô võ tướng: `S:015-008` (gói MỚI) làm gốc, `S:015-001` thêm / `S:015-002` xoá của chính mình | `[CAPTURE]` protocal.lua | KHÔNG lấy lại từ gói cache (`_on_pet_list` đọc lại cache khi 0x13 tới sau) |
| `can` kind 1 (NPC đi theo) không chặn; kind 3 (item) thiếu trong túi thì chặn | **BOT TỰ ĐẶT** | NPC đi theo do bước trước cho; item chưa biết lấy ở đâu |
| Bước cần dắt NPC mà NPC chưa theo + có chỗ đưa (`lay_npc` trong data) → đi lấy TRƯỚC: tới NPC đưa, bấm, chọn theo `chon_map`, chờ `S:015-001` có đúng id NPC, rồi mới tới NPC bước. Ô võ tướng tính thêm 1 cho mỗi NPC phải lấy. Lấy 3 lần không theo → "Chú ý" | `[LOG]` + user 09/10 | p52 09/10 vummot/vuchin: 10023 bấm thẳng Mã Phu 3 lần `KHONG LEN BUOC` (Mã Phu đòi `cls9 == 18005`). User: *"chỉ cần chạy đi nói chuyện với con ngựa là sẽ có ngựa"* → ngựa NPC 9 (12001), surface 11 chọn 30 |
| Bước thiếu item → lấy y client TỰ DẪN ĐƯỜNG (`MarkManager.Navigation`: điều kiện chưa đạt → tới `condition.sceneId/position`, eventKind 1 = tự bấm NPC, 2 = cửa). Data: `lay_item` (504 chỗ ở chính tuyến). NPC/cửa có sự kiện CLICK → bấm + hội thoại; còn lại (điểm trên map, quái chỉ chạm-server như Bánh Bao Thịt) → tới điểm, `combat_ready()` bật lại hộp máy, ĐỨNG YÊN cho quái lao vào | `[CAPTURE]` Lua + user 09/10 | user: *"chạy đến chỗ quái thì đứng yên cho quái lao vào mình thôi"*; 12288 B4 "Giao thịt xay": 12808 NPC 13 Bánh Bao Thịt lv1 (mô tả item "Nhân thường thấy trong bánh Bao Thịt") |
| Đánh lấy item KHÔNG giới hạn trận; bấm NPC/cửa không có trận mà 3 lần không ra item → "Chú ý" | user 09/10 | *"đánh khi nào ra thì thôi"*. Client không có bảng rơi đồ (server gửi `S:053-004` sau trận) - quái để đánh = quái client chỉ |
| Quest thuộc CHUỖI KỊCH BẢN riêng (`quests.json` có `quests`, vd `cs1_cu_thu` 8 Cự Thú: 10324 10326 10328 10360 10384 10528 10564 10806) KHÔNG vào kế hoạch chính tuyến dù mang nhãn [Chính] → mode Cự Thú (party) làm. Log ghi riêng dòng "chuoi rieng (Cu Thu ...)" | user 09/10 | *"Thương khung loạn vũ là quest 8 cự thú"* - 10806 lọt danh sách chính tuyến, trước chỉ tình cờ bị chặn "cần party"; bật `solo_het` là bot sẽ đi lẻ đánh nó |
| [Hướng Dẫn] làm SAU [Chính]; mỗi nhịp tính lại nên [Chính] mới vào sổ là được làm trước ngay | user 09/10 + Eve.emg | Hướng Dẫn GIAO Chính: 12290 B5 (12179 NPC 1 Cửu Sởi chọn 30) → giao 10015 Giải Cứu Cửu Sởi + tạm xoá 12290; 12292 Hương Dũng dẫn ra ~25 quest [Chính] (11064…11180) |
| Điểm client chỉ nằm trên MAP MỎ (`Eve.emg` Mine) → đi lại TRONG vùng mỏ gần điểm quest nhất (bằng nhau thì quái lv thấp), không đứng yên. Data: `lay_item[].mo` (15 chỗ) | `[LOG]` + Lua + user 10/10 | p52 09/10 19:14→00:11 Vuba/vubon đứng (1250,1030) map 12591 **0 trận**: điểm đó nằm giữa mỏ 2 (y 200–560) và mỏ 3 (y 1480–1860); mỏ do SERVER kích hoạt (`EventManager.lua` `Mine = 7 --地雷(現在由Server觸發)`). User: *"chọn mỏ theo quest chứ"* |
| Mỏ có quái khoáng (NPC kind 16) → đeo **Cuốc** (`sa = 8`) cho char + pet xuất chiến, KHÔNG bỏ chạy quái khoáng (`state.danh_khoang_den`, tự hết hạn 120s); đủ item → đeo lại vũ khí cũ. Không có Cuốc → "Chú ý" | Talk + user 10/10 | thoại 11116: *"Khi đào khoáng ngươi và võ tướng phải trang bị Cuốc"*; 11112 cho 2 Cuốc (10001). User: *"phải đeo cuốc vào để đánh quái khoáng, ko bỏ chạy khi gặp quái khoáng"*. Quái rơi thẳng Tích Sa (user: *"đánh quái rơi ra tích sa để trả nhiệm vụ luôn"*) |
| Điểm farm (không phải NPC/cửa/mỏ) mà trong 400px KHÔNG có quái "chạm là đánh" (NPC có sự kiện `serStroke` = `when[3]` kèm KQ vào trận) → ĐI LẠI quanh điểm (gốc + 4 hướng lệch 120px, `flee=False`); có quái đó thì vẫn đứng yên. Data: `lay_item[].di_lai` (412/504 chỗ) | `[LOG]` + `Eve.emg` + user 10/10 | p52 10/10: vubon đứng 11176 map 12582 (1300,1000) **21 phút 0 trận**, Vuba thêm 2 phút 0 trận; cùng map đang đi thì gặp trận sau 6s. Đối chứng: 12841 có Hắc Sơn GiápBinh (serStroke) cách điểm ~110px → đứng yên 5s là vào trận. Map 12582 chỉ có trận ngẫu nhiên khi đi (Mine 1 `o=1` → Fight 1–11). Train map vẫn quét thật (user: vùng đi tuần mỗi chỗ một khác) |
| Đã đứng ở điểm đánh quái (cùng map, cách ≤200px, không phải NPC bấm/mỏ đào) → KHÔNG gọi lại `_di_toi` (lệnh đó gặp quái là BỎ CHẠY). Đi đường xa vẫn bỏ chạy như luật 08/10. `_dang_o_diem_farm`, `_GAN_DIEM_FARM_PX` | `[LOG]` + user 10/10 "sửa đi" | p52 10/10 Vuba 11180 map 12861 (770,1610): **12/69 trận bỏ chạy**, 11/12 ngay sau `smart path (770, 1610) -> (770,1610)` lúc `lam_buoc_ct` lặp lại (~75s/lần). Vòng sau đi tới đúng điểm đang đứng |
| Bước có ĐK `cls7 par6 pst3 ops5 val=npcId` = NPC đó phải Ở NHÀ TRỌ → trước khi gặp NPC bước: tới chủ nhà trọ (KQ `t7 c7 pst4`, ưu tiên cùng scene), chọn "Võ Tướng" → server mở bảng `S:031-007` → `C:031-003 +ô đi theo` → `S:031-003` xác nhận → `C:031-010` đóng bảng → `0x14 06`. NPC không đi theo thì làm bước luôn. 3 lần không gửi được → "Chú ý". Data: `cat_tro` (12290 B7, 11000 B5) | Talk + Lua + user 10/10 + `[LOG]` | 12290 B7 thoại 53107 *"hãy gửi Cửu Sởi vào Nhà Trọ"*; 12244 Đại Trưởng Quỹ surface 2: 30 Ăn uống / 31 Nơi ở (`t7 c7 pst5`) / **32 Võ Tướng** (`t7 c7 pst4`). p52 10/10 vummot/vuchin/vumuoi kẹt B7 từ 03:58. User: *"m phân tích đúng"*. Chạy thật 10/10: vummot/vuchin/vumuoi qua B7 |
| Mode `quest` (Cự Thú + chính tuyến) KHÔNG dùng Phúc Thần, đang đeo ngọc thì THÁO ra túi (y mode event) | user 10/10 | *"chế độ làm Q cự thú và chính tuyến thì sẽ ko dùng Phúc thần, thằng nào đang đeo ngọc thì tháo ra"* - `run_party_digioi.MODE_KHONG_PHUC_THAN`, luật ghi ở `CORE_FLOW.md` mục Ngọc Phúc Thần (user cho sửa) |
| Server thêm/xoá võ tướng GIỮA PHIÊN (`S:015-001/002`) → sửa luôn danh sách pet mang theo (`state.carried_pets`) + cache acc tắt | `[LOG]` | vuchin 10/10 11:20:11 `VO TUONG XOA o 4` (Cửu Sởi vào nhà trọ) mà tab pet GUI vẫn còn Cửu Sởi |
| Cất nhà trọ thành công = `S:031-003` HOẶC ô đi theo bị xoá; ô đã trống thì không gửi lệnh cất | `[LOG]` | p52 10/10: server không gửi `S:031-003`, chỉ `VO TUONG XOA` + cả danh sách nhà trọ (`S:031-006`) → log cũ báo nhầm "server KHONG xac nhan". Cả 3 acc qua 12290 B7 (11:20) |
| Mode quest chính tuyến KHÔNG donate nguyên liệu quân đoàn (cả donate sau login lẫn bán khi chưa có quân đoàn) | user 10/10 | *"chế độ làm nhiệm vụ này thì ko donate nguyên liệu cho quân đoàn"* - `run_party_digioi._cho_donate_nguyen_lieu` |
| `quest_solo.json` `"solo_het": true` → MỌI quest đi lẻ, bỏ qua danh sách | user 09/10 | *"những quest đầu này cứ cho solo hết, đến khi nào t bảo đi party"*. CHỈ chính tuyến - Cự Thú CS1 vẫn party |
| NPC đang theo = `client.follow_npc` (ô → id NPC, từ `S:015-008` gói mới + `S:015-001/002`) | `[CAPTURE]` protocal.lua + `[LOG]` | `S:015-001 +NPCID(4)` = `pkt[18:22]`; record pet list ô 4 = 12020 Trương Phi |
| Đi lẻ: TẮT `flee_mode` ngay trước khi bấm NPC | code client | `flee_mode` chỉ tác dụng khi không ở party → để bật thì gặp boss quest bot bỏ chạy |
| Toạ độ đứng bấm = `endX/endY` của bước (điểm dẫn đường client) | `[CAPTURE]` | 10324 B1 client bấm NPC 2 từ (744,369), NPC đứng (830,360) |
| Đang làm quest mà dính trận → giữ việc `quest` | `[LOG]` | party 7, 04/10 (y CS1) |
| L0 ngoại lệ pha đi lẻ | user 08/10 | ghi ở `RULE_DIEU_PHOI.md` |
| Có acc nhận `lenh_tay` (vd worker mới sau relogin) → acc ĐANG DỞ sự kiện quest vẫn giữ `quest` | `[LOG]` | p52 09/10 11:27:19: qv810 relogin → `_quest_cho_viec_dau` trả quyết định gốc → qv809/qv811 đang đánh Đốc Bưu bị `nghi` → `su kien dung`, sau đó server LỜ mọi lần bấm NPC (`server im 60s`, vet=[]) |
| Đếm "3 lần không lên bước" gồm cả `im_lang`/`can_chon`/`het_gio` (trừ `dung` = bị huỷ từ ngoài) | `[LOG]` | p52 09/10: chỉ đếm `xong` → vuchin/vummot thử mãi mỗi 60s, không bao giờ báo "Chú ý" |
| Lần chạy thật đầu (p52 09/10): vumuoi làm B1 → B2 (server làm gộp B2+B3, Trương Phi vào ô 4 `VO TUONG THEM o 4`) → B4 đứng yên "cần 1 ô võ tướng" | `[LOG]` | đúng thiết kế |

"Chú ý" (PC `gui.py` `_quest_ket` · APK `quest_ket`): `<acc>: quest X bước N đứng yên - <lý do>`,
nút "Bỏ qua" (`quest_ket_notify_items/skip` trong `run_party_digioi.py`, dùng chung PC/APK).

## Chưa làm / rủi ro

- Data client vs server VTC có thể lệch → giữ chặn "3 lần hội thoại xong không lên bước thì dừng".
- Một surface có nhiều mã cùng dẫn tới lên bước → ưu tiên nhánh KHÔNG có trận.
- **11120 Chuẩn Bị Nguyên Liệu 3** (sau 11116): nhận quest server đưa 35 Vô Danh Tích Sa, cần nộp
  1 **Vô Danh Tích Thạch** (44042) = HỢP từ Tích Sa (thoại 53066 "Dùng nguyên liệu khoáng mới thu
  thập hợp thành Vô Danh Tích Thạch, trong quá trình hợp thành có thể thất bại!"). ĐÃ LÀM 10/10
  (user xác nhận *"2 Tích Sa → 1 Tích Thạch"*): `quest_runner._HOP = {44042: 37407}` - thiếu Tích
  Thạch mà túi còn ≥2 Tích Sa thì HỢP tại chỗ (`client.combine_slots`, cùng ô được), hỏng thì hợp
  tiếp; hết Sa mới đi đào mỏ theo client chỉ. Công thức khác: ghi tay vào `_HOP` khi đã chốt.
- Gom đồ: đã làm theo chỗ client dẫn đường (`lay_item`); 25 lần cần item không có toạ độ → đứng
  yên "client không chỉ chỗ lấy". Dẫn NPC: đã có pha lấy NPC (`lay_npc`) cho
  194/219 bước có `can` NPC của chính tuyến (đếm 09/10); 25 bước còn lại NPC do bước trước tự đưa
  hoặc chưa tìm ra chỗ đưa (vd 10212, 10660, 11080 — gặp thì "3 lần không lên bước").
- `lay_npc` có trận: đếm 0 trong chính tuyến → chưa làm nhánh party cho pha lấy NPC.

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
