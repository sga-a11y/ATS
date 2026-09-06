# RULE ĐIỀU PHỐI — luật chung, mọi tính năng phải theo

> Chốt 06/09/2026 sau một ngày sửa liên tiếp p3, p5, p12, p15, p1, p11.
> **Code vi phạm bất kỳ điều nào dưới đây là code sai, không phải "cách làm khác".**

Tài liệu này nói về **cách ra lệnh và thi hành lệnh ở cấp party**. Nó áp cho *mọi* tính năng:
Địa Giới, train, event 2K, 40NPC, loạn đấu, phó bản, cất đồ, vận tiêu — bất cứ chỗ nào có nhiều
acc phải phối hợp.

---

## Nguyên tắc gốc

> **Bot là người điều phối. Không acc nào ra lệnh, không acc nào chờ acc khác báo cáo.**

Cả party chạy trong **một tiến trình**. `account_clients[u]` cho biết mọi thứ về mọi acc: map,
kênh, HP, roster, mã lỗi server vừa trả, đang đánh hay không. **Không có gì phải hỏi, phải chờ,
phải báo.**

---

## L0 — LUẬT TỐI THƯỢNG

> ### **Đủ party rồi làm gì thì làm. Party hỏng thì phải gom lại BẰNG ĐƯỢC.**

Luật này **đứng trên 13 luật còn lại**. Khi có xung đột, L0 thắng.

### Hai vế, vế nào cũng tuyệt đối

**Vế 1 — Đủ mới được làm.** Thiếu dù một người thì **việc chính dừng hết**: không đánh, không leo
tầng, không qua cổng, không đi route, không đăng ký event, không vào phó bản. Việc duy nhất được
phép làm là **gom lại**.

**Vế 2 — Hỏng thì gom BẰNG ĐƯỢC.** Không có đường "thôi kệ, làm tiếp với người còn lại". Không có
đường "gom mãi không được thì bỏ event". Cách này hỏng thì **đổi cách khác** (L7), không phải bỏ cuộc.

### Chỉ ba lý do được phép ngừng gom

1. **Hết giờ khách quan** — hết giờ Địa Giới, hết khung giờ event.
2. **User Stop.**
3. **Acc đã tắt hẳn** và không thể bật lại (không phải "đang login lại" — cái đó là *chờ*, không
   phải *mất*).

Ngoài ba lý do đó, **mọi trạng thái thiếu người đều phải quay về gom**, kể cả khi đã thử 10 lần.

### Ba ca chết thật sinh ra luật này (06/09)

| Ca | Vi phạm vế nào |
|---|---|
| **p5** — 4 member rời đội để đổi kênh, leader qua cổng lên tầng 6 **một mình**, tầng đó `đánh được 0/3 trận` | Vế 1: thiếu người mà vẫn qua cổng |
| **p15** — đội tan lúc 14:18:57, leader **đánh một mình** 3 phút/trận suốt 4 phút, không ai mời lại | Cả hai vế |
| **p3** — leader lặp `CHO du member san sang (3/4)` 28 lần trong 1 tiếng, mỗi lần `reform` đều vô dụng | Vế 2: "gom" mà không đổi cách = không phải gom |

### Áp vào code như thế nào

- Trước **mọi bước không quay lại được** (qua cổng, vào phó bản, đăng ký event, tele đi xa) phải
  có một cửa kiểm `đủ party chưa?`. Chưa đủ → mời lại tại chỗ → vẫn chưa đủ → **thôi, không đi**.
- Sau **mọi lệnh làm tan đội** (đổi kênh, giải tán để sync) phải có bước **lập lại đội** — và đó
  là phần của chính lệnh đó (L5).
- Vòng "gom" phải **đổi cách** khi cách cũ hỏng, không lặp y nguyên (L7, L11).
- Hàm kết luận "xong / thua / thôi" phải phân biệt được **hết thật** với **đang thiếu người**
  (L13). Thiếu người **không bao giờ** là lý do để kết thúc.

---

## 13 luật thi hành

### L1 — Chỉ MỘT chỗ được quyết

Mọi quyết định cấp party (đi đâu, kênh nào, gom hay làm, đủ chưa, xong chưa, thoát hay ở lại)
chỉ được phát sinh trong luồng điều phối. Luồng acc **thi hành**, không quyết.

> Vi phạm thật: `_on_crawl_done` tự bấm `event_exit_now` → leader rớt mạng ở tầng 5 thành "2K đã
> xong" → kéo cả 5 acc đi bộ ngược 8 tầng rồi tắt game (p12, 13:50).

**Kiểm:** một cờ quyết định chỉ được `set()` ở **đúng một** chỗ, và chỗ đó phải nằm trong hàm của
điều phối.

### L2 — Đọc thẳng, cấm báo cáo

Điều phối **đọc thẳng** client. Cấm mọi cơ chế "acc báo lên rồi điều phối đọc": hàm `bao_*`,
bảng `*_reports`, `Event` chờ, barrier đếm người.

> Vi phạm thật: chính tôi thêm `bao_kenh_day()` để acc báo "kênh này đầy" — trong khi
> `c._chan_switch_result` đã có sẵn mã server trả về. Bắt báo cáo là tự làm mù mình.

### L3 — Lệnh phải có MỤC TIÊU ĐO ĐƯỢC

Mỗi lệnh phải phát biểu được bằng một câu kiểm được từ trạng thái thật:
*"cả party ở kênh N"*, *"cả party ở map M"*, *"đội đủ K người"*, *"đã tới `top_map`"*.

Không đo được thì không phải lệnh — nó là lời cầu nguyện.

### L4 — Ra lệnh phải THEO TỚI CÙNG

Ra lệnh xong phải biết: **ai đã xong · ai chưa · ai hỏng và hỏng mã gì** — rồi **xử lý cái hỏng**.

Mã server là dữ liệu, không phải tiếng ồn. Ví dụ đổi kênh (`_on_channel_switch_result`):

| Mã | Nghĩa | Điều phối phải làm |
|---|---|---|
| 2 | không có khu đó | đang trong **instance** → lệnh đổi kênh **sai loại**, đổi cách khác |
| 3 | đang tổ đội | đổi kênh **sẽ làm tan đội** → xong phải lập lại đội |
| 4 | kênh đầy | kênh đó không dùng được → chọn kênh khác |

> Vi phạm thật: 16:34:04 server nói thẳng *"khong co khu do de doi"* (mã 2). Bot bỏ qua, 10 giây
> sau đâm tiếp vào mã 3 → 4 member rời đội để đổi kênh → leader qua cổng một mình (p5).

### L5 — Ra lệnh thì phải TRẢ NỢ HẬU QUẢ

Lệnh nào có tác dụng phụ bắt buộc thì tác dụng phụ đó là **phần hai của chính lệnh đó**, không
phải việc của người khác.

Server cấm đổi kênh khi đang trong đội → **đổi kênh tất yếu làm tan đội**. Member rời đội là làm
đúng luật game. Sai là ở người ra lệnh nếu không lập lại đội.

### L6 — Lệnh phải DÍNH, không đổi ý mỗi nhịp

Điều phối chạy mỗi 2 giây. Chốt lại từ đầu mỗi nhịp = acc vừa bắt đầu làm thì lệnh đã đổi.

Đã ra lệnh thì **giữ đủ lâu để thi hành xong** (`KENH_DICH_KIEN_NHAN_SEC = 45s`). Chỉ đổi khi:
mục tiêu đã đạt · mục tiêu hỏng (kênh đầy) · quá hạn.

> Vi phạm thật: chốt kênh 1 → 2 → 1 → 2 trong 3 phút, cả party quay đầu liên tục, 4 phút mới
> đồng bộ xong và suốt 4 phút đó không mời party được (p3, 15:38–15:42).

### L7 — Lệnh phải có HẠN và LEO THANG

Không lệnh nào được lặp vô hạn. Quá hạn thì **đổi cách làm**, không phải làm lại y cũ to tiếng hơn.

> Vi phạm thật: leader lặp `CHO du member san sang (3/4)` 28 lần trong 1 tiếng, mỗi lần
> `_bump_reform` rồi `reform: khong co smart/legacy route -> bo qua` (p3, 02:38–03:34).

### L8 — Lệnh hỏng phải ĐÓNG CỬA

Mọi đường thoát thất bại đều phải dọn cờ của lệnh đó. Cờ kẹt `set()` = acc còn bám vào lệnh đã
chết = treo vĩnh viễn.

> Vi phạm thật: `do_channel_sync` thoát mà không xoá `channel_ready` → `batbat` đỗ lại chờ 1 tiếng
> (p3, 02:38:31).

### L9 — Không acc nào được ĐỖ LẠI CHỜ acc khác

Thi hành hỏng thì **ghi nhận rồi đi tiếp**, để điều phối lo. Cấm `while` chờ một acc khác bấm nút.

> Vi phạm thật: `batbat` vào kênh đầy → *"báo leader pick lại"* rồi đỗ trong `while
> channel_ready.is_set()`, còn leader thì đang kẹt trong vòng chờ chính nó.

### L10 — Vòng thi hành phải CÓ NHỊP

Thi hành xong một lệnh thì **ngủ một nhịp điều phối** rồi mới đọc lệnh tiếp. Cấm `continue` trần.

> Vi phạm thật: `_do_reform()` ở map event trả về tức thì → `continue` không ngủ → **8.000
> vòng/giây, 201.495 lần**, ăn hết GIL nên **bỏ đói luôn luồng điều phối** — kế hoạch đóng băng ở
> `viec=gom` suốt 5 phút dù party đã chung kênh. Vòng nóng tự nuôi chính nó (p5, 13:15–13:20).

### L11 — Lệnh phải ĐÚNG LOẠI với ngữ cảnh

Cùng một mục tiêu, mỗi ngữ cảnh có cách làm khác nhau. Ra lệnh sai loại thì không ai thi hành được.

| Ngữ cảnh | Gom lại bằng | KHÔNG dùng |
|---|---|---|
| Ngoài thành / train | reform về thành theo route | — |
| Trong Địa Giới | đồng bộ **tại chỗ** (`resync`) | reform (phải đi bộ ra cổng) |
| Trong tháp 2K | đi bộ xuống **tầng thấp nhất cả đội tới được** | reform (không có route), đổi kênh (instance) |
| Cùng map, lệch kênh | đổi kênh | gom về thành (thừa một vòng đi đường) |

> Vi phạm thật: điều phối ra `VIEC_GOM` giữa tháp 2K → `_do_reform` in *"khong co smart/legacy
> route -> bo qua"* rồi trả về ngay. Lệnh không bao giờ được thi hành.

### L12 — LUỒNG CON cũng phải nghe lệnh

Thread phụ (`run_floor_crawl`, `npc40.run_loop`, `loandau.run_loop`…) phải có lối thoát theo kế
hoạch. Thread không đọc lệnh = một vùng chết mà điều phối không với tới.

> Vi phạm thật: điều phối ra lệnh gom lúc 16:36:01, nhưng leader đang kẹt trong `run_floor_crawl`
> — luồng đó không đọc kế hoạch. Lệnh rơi vào hư không, leader leo tiếp một mình (p5).

### L13 — "KHÔNG BIẾT" không phải "KHÔNG SAO"

Thiếu dữ liệu phải trả về *không biết* và xử lý như *không biết*, tuyệt đối không mặc định thành
*bình thường*.

> Vi phạm thật: `party_defeated` trả `bool(known) and alive == 0`. `allies` rỗng → `False` =
> "không thua". Log in `party song 0/0` — đó là **không biết**, mà bot đọc thành **thắng**, rồi
> báo "2K xong" và kéo cả đội ra khỏi tháp (p1, 15:14:41).
>
> Sửa đúng: đọc HP của **chính từng acc** (`state.char`) — luôn có, không phụ thuộc gói `0x0b`.

---

## Trước khi viết code: năm câu phải trả lời

Thêm bất kỳ hành vi phối hợp nào, trả lời hết năm câu này rồi mới gõ:

0. **Bước này có cần đủ party không?** — nếu không quay lại được thì **có**, và phải chặn khi
   thiếu (L0). Lệnh này có làm tan đội không? Có thì ai lập lại?
1. **Ai quyết?** — phải là điều phối (L1).
2. **Đo bằng gì?** — trường nào trên client cho biết đã xong (L2, L3).
3. **Hỏng thì sao?** — liệt kê từng mã lỗi server và cách xử lý (L4); tác dụng phụ bắt buộc là gì
   và ai trả (L5).
4. **Bao lâu thì thôi?** — hạn, và quá hạn thì đổi sang cách gì (L7).

Không trả lời được câu nào thì **chưa được viết**.

## Cấm — nhận diện nhanh khi đọc diff

| Thấy cái này | Là vi phạm |
|---|---|
| `def bao_*(st, ...)` / `st["*_reports"]` / barrier đếm người | L2 |
| `Event()` mới để "chờ acc khác" | L2, L9 |
| `while ...: time.sleep(0.5)` chờ acc khác đổi cờ | L9 |
| `continue` ngay sau khi thi hành lệnh, không `sleep` | L10 |
| `return` / `break` ở đường lỗi mà không dọn cờ lệnh | L8 |
| Cờ quyết định được `set()` ở hai chỗ trở lên | L1 |
| Bỏ qua giá trị trả về của lệnh gửi server | L4 |
| Hàm đo trạng thái trả `False` khi thiếu dữ liệu | L13 |
| Đi bước không quay lại được mà không kiểm đủ party | **L0** |
| Kết luận "xong/thua/thôi" trong khi đang thiếu người | **L0** |
| Lệnh làm tan đội mà không có bước lập lại | **L0**, L5 |
| Ghi cờ "nợ"/"đã báo" trong khi đọc thẳng client là ra | L2 |

## Được ép bằng test

`tests/test_rule_dieu_phoi.py` bắt các vi phạm kiểm được bằng máy. Test đỏ ở đó nghĩa là **luật bị
phá**, không phải "test cũ neo sai" — sửa code, đừng sửa test.

Phần còn lại (L3, L4, L5, L7, L11, L12) phải tự soi khi review, dùng bảng "Cấm" ở trên.
