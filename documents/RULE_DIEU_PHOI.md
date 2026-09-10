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

Luật này **đứng trên 27 luật còn lại**. Khi có xung đột, L0 thắng.

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

## 28 luật thi hành

### L1 — Chỉ MỘT chỗ được quyết

Mọi quyết định cấp party (đi đâu, kênh nào, gom hay làm, đủ chưa, xong chưa, thoát hay ở lại)
chỉ được phát sinh trong luồng điều phối. Luồng acc **thi hành**, không quyết.

> Vi phạm thật: `_on_crawl_done` tự bấm `event_exit_now` → leader rớt mạng ở tầng 5 thành "2K đã
> xong" → kéo cả 5 acc đi bộ ngược 8 tầng rồi tắt game (p12, 13:50).

> Vi phạm thật (07/09, giết hai party trong một đêm): `resync_gen` có **bốn** chỗ bump, ba trong
> số đó là **leader tự quyết** — và chỉ chỗ của điều phối mới có cooldown + chốt *"người khác vừa
> bump thì im"*. Leader bắn thẳng, không chốt gì, nên nó đập chính cái party đang gom dở:
>
> ```
> p9   02:33:30  PARTY: c0edf0a0 vao doi -> roster 3 nguoi
>      02:33:30  PARTY: loi moi -> DONG Y (lubbay)
>      02:33:50  (LEADER) Di Gioi moi 24s chua du party (2/4) -> giai tan + sync lai kenh
>      02:33:55..57  3 member  Roi/giai tan party cu
> p11  02:10:32  PARTY-JOINED: 3 -> 0 (nguoi ghi=LEADER)
>      02:10:32  PARTY: loi moi -> DONG Y (luumuoi)      <- member đang vào NGAY lúc đó
>      02:10:33  (LEADER) sync kenh/map OK: 5/5 acc o map 49942
>      02:13..02:21  "chua du member (1/4) -> MOI LAI" mỗi phút    <- 11 PHÚT chết
> ```
>
> Leader còn đếm **trễ hơn roster server** (`2/4` trong khi roster đã 3 người) nên nó đập cả party
> thật sự đang đủ dần. Đã bỏ: leader chỉ mời tiếp, điều phối quyết có đồng bộ hay không.

**Kiểm:** một cờ quyết định chỉ được `set()` ở **đúng một** chỗ, và chỗ đó phải nằm trong hàm của
điều phối. `tests/test_leader_khong_tu_dap_party.py` đếm số chỗ bump `resync_gen` — phải bằng 1.

### L1b — Cấm cờ TỰ HẾT HẠN thay cho trạng thái thật

Không đặt `x_until = now + N` rồi coi hết hạn là "xong". Trạng thái cấp party phải là **một ô, một
chỗ ghi (điều phối), mọi acc đọc**. Timer per-acc luôn lệch với sự thật, và khi việc kết thúc sớm
thì phải đi hạ cờ từng acc — sót một acc là nó kẹt tới hết hạn.

> Vi phạm thật (07/09, p51 + p53): mỗi acc tự ôm `_phoban_until = now + 600` lúc accept lời mời
> phó bản; `go_to_town()` bail khi cờ còn hạn. Phó bản vỡ vì thiếu người thì leader hạ cờ của
> riêng nó, member nào đã rời vòng chờ `o5_state` thì ôm đủ 10 phút:
>
> ```
> 02:40:32 [vumhai] (LEADER) roster phong pho ban chi 3/4 member sau 8.3s -> HUY danh
> 02:40:33 [vumhai] -> da ra khoi pho ban (map 62002 -> 12001)
> 02:40:39..02:45:41  qv813/qv814/qv815 spam "dang vao pho ban -> ngung teleport"
> 02:45:46  RECONNECT: relogin HANG LOAT (ca party bi ep)
> ```
>
> Cả log **651 dòng** như vậy. Đã thay bằng `_PARTY_PB_PHA[pidx]`: điều phối `dat_pha_pho_ban()`
> bật khi vào pha, tắt trong `finally` — xong/thiếu người/dis/ngoại lệ đều một đường ra.

**Kiểm:** grep `_until = time.time() +` ở trạng thái cấp party. Có là sai, trừ khi nó là *hạn chót
kỹ thuật* (deadline chờ server trả lời), không phải *trạng thái của party*.

### L2 — Đọc thẳng, cấm báo cáo

Điều phối **đọc thẳng** client. Cấm mọi cơ chế "acc báo lên rồi điều phối đọc": hàm `bao_*`,
bảng `*_reports`, `Event` chờ, barrier đếm người.

> Vi phạm thật: chính tôi thêm `bao_kenh_day()` để acc báo "kênh này đầy" — trong khi
> `c._chan_switch_result` đã có sẵn mã server trả về. Bắt báo cáo là tự làm mù mình.

> Vi phạm thật (07/09): `channel_map_reports` — acc phải "khai" map/kênh sau khi đổi kênh, leader
> đếm đủ người mới đi tiếp. Acc nào bận việc khác thì không khai → leader đếm thiếu → `TIMEOUT 60s`
> → reform → lặp lại. Party 18 (23:36–23:43) đốt 6 phút với `cho acc bao cao map (1/5)` trong khi
> 4 member **đã ở đúng map từ đầu** — thông tin leader thấy được ngay bằng
> `account_clients[u].current_map`. Đã bỏ bảng; hàm cũ chỉ còn giữ một việc là **đặt cờ hỏng khi
> acc thấy chính nó sai map** — thứ duy nhất leader không tự thấy được.

> **Ghi cờ lên client cũng là báo cáo** (09/09). `_dg_da_xong` từng được coi là "hợp lệ" vì cờ nằm
> trên chính client, comment còn ghi *"bot đọc thẳng, không ai khai báo"*. Sai: **acc tự kết luận
> "mình hết giờ DG" rồi ghi cờ, điều phối chỉ đọc lại kết luận đó** — chỉ khác chỗ cất, bản chất
> vẫn là báo cáo. Acc kết luận sai là cả party tin theo.
>
> Ca thật: `haabo` (party 2) mất kết nối lúc 00:54:41, **16 giây sau** đã tự ghi "xong DG" →
> 4 acc kia đứng chờ nó. Cả ngày nó **chưa vào DG lần nào**, và vừa sang ngày mới nên còn nguyên
> 120 phút. Ba tầng sai chồng nhau: kết luận lúc đang dis · kết luận khi chưa nhận đồng hồ
> `S:085-001 id 0x1b` · `relogin()` dùng lại object cũ nên giữ số phút của phiên trước.
>
> Đã bỏ cờ. Điều phối tự đọc `_acc_het_gio_dg(c)` — ba nguồn sự thật, theo thứ tự:
> `S:097-001` mã 2 `<時間已滿>` → hết giờ · đồng hồ server còn ≥ 1 phút → còn giờ ·
> **chưa có đồng hồ → `None` = CHƯA BIẾT, phải chờ** (không được suy thành "hết giờ").
> Nguyên tắc: *khác biệt giữa "biết là hết" và "chưa biết" phải giữ được đến tận nơi ra quyết định*
> (xem thêm L13).

### L2b — Việc chung thì ra MỘT LỆNH cho cả party, đừng để mỗi acc tự lo

Khi cả party cùng phải làm một việc (ra khỏi instance, hạ cờ, đổi kênh, về thành), điều phối phát
**một lệnh chạm tới mọi client**. Mỗi acc "tự lo phần mình" nghe thì hợp lý, nhưng acc nào đang kẹt
ở nhánh khác sẽ không bao giờ tới lượt tự lo.

> Vi phạm thật (07/09, p42 — user: *"leader ở ngoài còn member vẫn trong PB kìa"*): phó bản **vỡ**
> thì server không gửi `S:047-012` nên không acc nào tự biết đường ra, mà leader chỉ gọi
> `_exit_pb_or_reconnect` cho **chính nó**. Leader về thành, member nằm nguyên map 62012, và
> `go_to_town` của họ thì bail vì *"đang trong phó bản tổ đội"*:
>
> ```
> 10:40:39 [luubhai] go_to_town: DANG TRONG pho ban to doi (map=62012) -> khong teleport
> 10:40:39 [luubhai] (member) reform: CHUA ve duoc Hội Kê (map=62012) -> nghi 10s thu lai
> ```
>
> Đã thêm `_thoat_pb_ca_party(pidx)`: điều phối kéo **mọi acc còn trong instance** ra bằng
> `C:047-010`, gắn vào cả ba đường vỡ. Cùng họ với `dat_pha_pho_ban` (L1b).

### L2c — Đo VIỆC PHẢI LÀM, không chỉ đo các acc với nhau

Ba phép đo quen thuộc — *lệch map · lệch kênh · thiếu người trong đội* — chỉ so **các acc với
nhau**. Cả party cùng đứng sai một chỗ thì cả ba đều xanh, và điều phối kết luận "ổn". Phải có
thêm hai phép đo so với **việc phải làm**:

1. **Đúng mode chưa** — mode train/DG mà cả party dậm chân ở **thành** quá lâu là sai. Thành là
   chỗ đi qua (tele trung gian, cất đồ, mua thuốc), không phải chỗ làm việc.
2. **Có tiến độ không** — đọc `(map, vị trí, đang đánh)` của từng acc; y hệt nhau quá lâu nghĩa là
   **không ai nhúc nhích**, bất kể mọi thứ "khớp".

Cả hai đồng hồ reset khi có chuyển động, và reset sau khi ra lệnh — không bắn lệnh gom liên tục.

> Vi phạm thật (07/09, party 1 — **44 phút**, 327 lượt log):
>
> ```
> 12:36:15..13:20:31
>   4 acc : reform: CHO ca party ve Trường Sa (4/5) - THIEU: brubb46677
>           [map=23001, da ve Trường Sa, cho ca party (37s)]
>   brub  : (member) CHO leader quyet dinh (leader co the dang reconnect)...
> ```
>
> Cả năm đứa **đã ở Trường Sa**, cùng kênh. brub chờ leader, leader chờ brub. Con số `(37s)` đứng
> im suốt 44 phút. Điều phối không thấy gì "lệch" nên im theo.

### L2d — Đếm đội bằng SỰ THẬT CỦA SERVER

`joined_member_count()` đọc `_PARTY_JOINED` — bảng do **chính bot** ghi khi thấy acc accept. Nó là
sổ nhớ, và nó **ôm stale**: party tan mà không ai `unmark` thì bot vẫn tưởng còn đủ. Roster server
(`c.party_members`, từ `0x0d`) mới là sự thật. Chỉ cần **một** acc còn sống mà roster của nó thiếu
người là đội chưa đủ.

> Vi phạm thật (07/09, party 1 — user: *"đủ đội cái lồn, bọn nó có cùng party đéo đâu"*): điều phối
> kết luận "đủ đội" → `VIEC_LAM` → im, trong khi log của chính leader lặp lại liên tục:
> `13:26:49 [xGAx] KHONG o party nao (roster server + local deu rong)`.

### L2e — Có những thứ SUY RA được, đừng ngồi chờ gói báo

**Leader rớt và đang login lại ⇒ đội đã tan.** Đội trưởng rời khỏi thế giới thì server tháo đội —
không cần chờ `0x0d` nào xác nhận. Các member còn sống chỉ nhận roster mới khi server chịu gửi, và
trong lúc đó roster của họ vẫn giữ số cũ; ngồi chờ nó là ngồi im qua cả quãng leader đăng nhập lại.

Suy ra được thì kết luận ngay, xoá sổ nhớ (L2d) và chuẩn bị mời lại để leader vừa vào là có đội.

### L3 — Lệnh phải có MỤC TIÊU ĐO ĐƯỢC

Mỗi lệnh phải phát biểu được bằng một câu kiểm được từ trạng thái thật:
*"cả party ở kênh N"*, *"cả party ở map M"*, *"đội đủ K người"*, *"đã tới `top_map`"*.

Không đo được thì không phải lệnh — nó là lời cầu nguyện.

### L3b — Điều phối phải TỰ GỬI LỆNH, không ghi bảng rồi chờ acc đọc

**Ghi trạng thái ≠ ra lệnh.** Điều phối đặt `st["kenh_dich"] = 16` xong là mới **viết lên bảng
thông báo**. Lệnh chỉ tồn tại khi gói tin đã ra khỏi socket.

Chỗ sai cũ: người gửi `switch_channel` là `_nghe_lenh_kenh()` trong `run_account`, mà hàm đó chỉ
chạy khi acc **đi ngang qua** một trong chín điểm nghe. Acc nào tụt vào một vòng dài nằm hẳn
trong `bot/client.py` (boss thế giới, vận tiêu, phó bản) là **điếc suốt vòng đó**.

> Ca thật 09/09 party 3 (user: *"sao điều phối vô dụng vãi lồn"* → *"thông báo cái lồn, viết 1
> đống rule thế mà chỉ là thông báo á"*):
> ```
> 12:40:16 [party 3] CHOT kenh dich = 16 (kenh IT NGUOI NHAT ma du cho ca team)
> 12:40:33 [nanam]   Boss the gioi: DA VAO TRAN -> danh CHO HET TRAN
> 12:41:03 [party 3] kenh dich 16 qua 45s van chua gom xong ({2:1, 8:2, 10:2}) -> chot lai
>          ... 14 nhịp, 9 phút, phân bố kênh KHÔNG nhúc nhích một li ...
> ```
> Suốt 9 phút **không một dòng `Doi kenh` nào** của cả năm acc — lệnh chưa từng được gửi đi, không
> phải đổi kênh thất bại. Bằng chứng cơ chế vẫn đúng, chỉ là không được chạy: 13:08:59 lúc acc
> rảnh, bốn member đổi kênh xong trong **một giây**.
>
> Cùng log đó lòi thêm: leader `nanam` nghe lệnh **chậm hơn member 74 giây** (13:08:59 vs
> 13:10:13) vì leader đi qua điểm nghe khác. Điều phối tự gửi thì cả năm nhận cùng một nhịp.

Cả party chạy trong **một tiến trình** — `account_clients[u]` đã nằm trong tay điều phối. Không có
lý do gì để nhờ acc gửi hộ.

- Điều phối **tự gọi** `c.switch_channel()` cho từng acc lệch (`_dieu_phoi_thi_hanh_kenh`).
- Gửi trong **thread riêng**: vòng điều phối chạy 2 giây/nhịp cho mọi party, một acc chậm không
  được làm cả hệ đứng hình.
- Điều kiện an toàn (đang trận / đang event / grace kết trận) điều phối **đọc thẳng từ client**,
  không cần acc hợp tác — và dùng **chung một hàm** với đường cũ (`_kenh_doi_duoc_ngay`); hai bản
  sao thì sớm muộn lệch nhau, mà lệch ở đây là đứt kết nối mã 47.
- Đường acc tự nghe **giữ lại làm lưới đỡ** (acc đổi kênh xong bị đẩy đi nơi khác), không còn là
  đường chính.

### L3c — Lệnh điều phối THI HÀNH TUYỆT ĐỐI, việc riêng đứng sau

User 09/09: *"lệnh của điều phối phải thi hành tuyệt đối"*. Đây là L0 áp cho việc vặt: đang có
lệnh gom (kênh hoặc map) thì acc **không được lao vào vòng việc riêng dài**, và vòng đang chạy
**phải bỏ được giữa chừng**.

**Chặn LƯỢT MỚI, không cắt ngang lượt đang chạy.** User 09/09: *"đang làm việc vặt thì làm nốt
chứ"*. Bỏ dở giữa trận là mất lượt, mất vé, mất vật phẩm — không được gì. Cửa kiểm đặt ở **đầu mỗi
vòng lặp**, tức trận/lượt hiện tại luôn chạy hết, chỉ lượt tiếp theo bị chặn.

Boss thế giới và phó bản solo đều là vòng nhiều lượt liên tiếp nằm hẳn trong client — acc chui vào
đó là điếc suốt cả chuỗi. Phó bản solo còn tệ hơn: nó `leave_party()` ngay dòng đầu rồi vào một map
riêng, tức **vừa phá đội vừa làm lệch map** — đúng hai thứ điều phối đang cố sửa.

- **Trước khi vào**: hỏi `_dieu_phoi_dang_ra_lenh()` — đang có lệnh thì **hoãn**, làm sau.
- **Giữa chuỗi**: truyền `cho_phep=` (`do_world_boss_all`, `do_daily_dungeon`), kiểm **mỗi vòng
  lặp** và **trước `buy_dungeon_ticket()`** để không mất vé.
- **Kế hoạch nói trước dích cụ thể**: `viec == VIEC_GOM/VIEC_DONG_BO` là đủ để hoãn, không đợi đến
  lúc có `kenh_dich`/`gom_dich`.
- **Hoãn vẫn phải đánh dấu xong** (`wb_done` trong `finally`) — leader chờ cờ đó trước khi lập phó
  bản, không đánh dấu thì cả party treo chờ một acc không bao giờ báo.

### L3d — Lệch MAP xử ngay, và đồng hồ lệch không được RESET vì một nhịp

*"Đi train thì đơn giản là khác map thì gom map, khác kênh thì gom kênh, đủ thì đi train"*
(user 09/09). Cái đơn giản đó từng bị bọc hai lớp trì hoãn chồng nhau:

1. **Ân hạn 60 giây dùng chung cho lệch map và lệch kênh.** 60 giây là hạn của một *chuyến gom
   đang chạy* (về thành trung gian → thành tập kết); lấy nó làm hạn **phát hiện** lệch thì party
   lệch cả phút vẫn chưa được ra lệnh. Teleport chuyển tiếp chỉ mất vài giây → lệch map có ân hạn
   riêng, ngắn (`LECH_MAP_AN_HAN_SEC`).
2. **Đồng hồ reset về 0 khi thấy cùng map một nhịp.** Party lệch **ngắt quãng** thì đồng hồ không
   bao giờ chạy đủ hạn → **không bao giờ được gom**, dù điều phối in "còn lệch map" ba chục lần.

> Ca thật 09/09 party 1 — `brub` bị dump ra 21011 lúc 13:08:28 và đứng đó; bốn acc kia ra/vào phó
> bản solo liên tục nên tập map chớp tắt giữa `{21011}` và `{21011, 62001}`:
> ```
> 13:08:16 gen 23: viec=lam - con lech map [21011, 62001] -> chua lap party, cho gom xong
> 13:08:42 gen 25: viec=moi - cung map/kenh nhung DOI chua du     <- đồng hồ RESET
> 13:08:52 gen 26: viec=lam - con lech map [21011, 62001]         <- đếm lại từ đầu
> 13:09:22 gen 29: viec=moi - cung map/kenh                       <- RESET lần nữa
> 13:11:33 gen 33: viec=gom - party dang o 2 MAP khac nhau        <- ba phút sau
> ```
> Ba phút cho một việc điều phối **đã biết từ giây đầu tiên**.

Hết lệch phải **giữ được `HET_LECH_CHAC_SEC`** thì đồng hồ mới được gỡ. Nhưng đồng hồ treo lại
**không được biến thành lệnh**: `lech_lau` phải kèm điều kiện *đang lệch thật* — giữ tuổi là để
không mất dấu một lần lệch ngắt quãng, không phải để ra lệnh đồng bộ cho party đang lành.

### L3e — Gói gửi lên server phải kiểm trạng thái TRƯỚC TỪNG GÓI, không bắn mù cả chuỗi

Chuỗi `send()` cách nhau nửa giây là **ba thời điểm khác nhau**, không phải một. Trạng thái server
đổi giữa chừng thì gói sau rơi vào ngữ cảnh sai. Với gói dialog/event, rơi vào giữa trận =
`S:000-000` mã 47 `<戰鬥未結束事件先結束>` → **đứt kết nối**, và leader đứt là party tan.

> Ca thật 09/09 event 40NPC (user: *"40npc, ko dc party nao đánh luôn"*) — **92 lần mã 47 trong 18
> phút**, gói áp đảo quanh lúc rớt là `0x14 0600` (ADVANCE): 55/92. Đọc gửi-cuối/nhận-cuối:
> ```
> 21:44:13 [ttsau] 40NPC: het tran, party alive=1/1
> 21:44:13 [tt*]   cả 5 acc: Nhan item: Thắng Lệnh 1     <- party VỪA THẮNG
> 21:44:17.241     <<nhan 0x35 ...      <- lượt của TRẬN MỚI, trận đã bắt đầu lại
> 21:44:17.269     >>gui  0x14 0600     <- vẫn đang bắn nốt chuỗi dialog của trận TRƯỚC
> 21:44:17         SERVER NGAT KET NOI: ma la 47
> ```
> Không phải "không đánh được" — 357 lần nhận Thắng Lệnh trong cùng khoảng đó. Party đánh, thắng,
> rồi tự giết mình sau mỗi trận.

Chuỗi 40NPC là **các trận nối đuôi nhau** (server tự mở trận kế tiếp) nên khe giữa hai trận rất
hẹp. Mọi gói dialog phải đi qua một cửa: chờ trận giải xong, và **bỏ gói** nếu trận mới đã bắt đầu.
`_battle_start_seq` lên ở `0x34` còn `state.in_battle` lên sớm hơn ở `0x35` — chỉ nhìn seq là còn
một khe lọt.

### L3f — Số đo phải đo đúng cái mình tưởng đang đo

`state.allies` chỉ mang unit **chính client đó thấy** trong trận của nó. Dùng nó để đếm party thì
kết quả luôn là `1/1`, kể cả party 5 acc — và con số đó vừa đi vào log user đọc, vừa đi vào chỗ
kết luận thắng thua.

> Cả 77 trận 40NPC ngày 09/09 đều in `party alive=1/1`, trong khi cùng lúc năm acc đều nhận Thắng
> Lệnh. Con số sai không chỉ vô dụng — nó **lái cả việc chẩn đoán đi sai hướng**.

Đếm party thì đọc thẳng các client cùng party trong tiến trình (`party_peers()` → `_PARTY_CLIENTS`),
đúng như L2. Và khi chưa đọc được HP thì tính là **còn sống** — kết luận thua oan là kéo cả party
ra khỏi event.

### L3g — Party HẾT VIỆC CHUNG thì điều phối phải im, đừng ra lệnh cho vui

Không phải party nào cũng luôn có việc cấp party. Khi việc còn lại là **solo** — mỗi acc tự làm rồi
thoát — thì gom map, đồng bộ kênh, lập lại đội đều **vô nghĩa và có hại**: lệnh kéo acc ra khỏi
đúng việc nó đang làm.

> Ca thật 09/09 sau 22h, 40NPC ngoài giờ (user: *"mode 40npc, ngoài giờ event thì chỉ log vào và đi
> đổi thưởng rồi out, m còn phải đồng bộ kênh làm lồn gì"*):
> ```
> 22:00:31 [party 49] gen 26: viec=lam - con lech map [10991, 12003]
> 22:00:37 [party 49] gen 27: viec=gom - party dang o 2 MAP khac nhau [10991, 12003]
> 22:00:30 [dakbon]  DIEU PHOI GUI doi kenh 2 (dang o 1) -> ket qua 4
> 22:00:33 [quanmot] (LEADER) DIEU PHOI chot kenh 14, minh dang o 1 -> tu chuyen
> ```
> `12003` **chính là** map đổi thưởng — "lệch map" lúc đó là đúng ý đồ. Lệnh đổi kênh còn dính mã 4
> (kênh đầy) nên lặp mãi.

Nhánh của acc đã đúng từ trước (hủy party → đổi thưởng → thoát); thiếu là **cửa tương ứng ở cấp
điều phối**. Cửa đó nằm ở cả hai chỗ ra lệnh: `_dieu_phoi_quyet` (trả `VIEC_LAM`) và
`_dieu_phoi_chot_kenh` (trả `None` **và gỡ `kenh_dich` còn treo** từ lúc trong giờ).

**Cửa phải hẹp đúng bằng ca đó** (user: *"đừng có tiện tay xoá luôn cái đồng bộ kênh lập pt khi
trong thời gian event"*): chỉ mode `event` + `kind == npc_repeat` + **ngoài** khung giờ. Trong giờ
event, và mọi mode khác (train, DG, 2K, loạn đấu) giữ nguyên toàn bộ. `tests/
test_40npc_ngoai_gio_khong_dieu_phoi.py` khoá **cả hai chiều** — có cả nhóm test bắt buộc trong giờ
vẫn phải chốt kênh, vẫn gom khi lệch map, vẫn lập lại party khi đội tan.

> Bẫy kèm theo: test cấp party không set `PARTY_CONFIG` sẽ ăn config **thật** của máy user. Party 0
> ở đó là mode 40NPC, nên `test_doi_kenh_phai_lap_lai_party` chuyển đỏ/xanh theo **đồng hồ thật**.
> Test cấp party phải cô lập `PARTY_CONFIG` trong `setUp`/`tearDown`.

### L3h — Cửa "không còn việc" phải đứng TRƯỚC việc, không phải sau

Một cửa kiểm đặt sai chỗ thì vô dụng như không có. Hai cửa "ngoài giờ event" (40NPC, loạn đấu)
từng nằm **dưới** cả đoạn `go_to_event` — acc login ngoài giờ vẫn đi hết đường vào map event, cổng
đã đóng nên không bao giờ vào được, rồi vòng ngoài gọi lại mãi.

> Ca thật 09/09 (user: *"các party 40npc, ngoài time event rồi mà log in vào thấy vẫn có log ko vào
> dc map event, hết event rồi thì vào map event làm lồn gì"*) — event đóng lúc 22:00:
> ```
> 22:31:37 [xGAx] (LEADER) chua vao duoc map event 10991 (dang o 12003) -> thu lai (lan 1/5)
> ```
> **3372 dòng** như vậy tính từ 22:30. Mà `12003` chính là map đổi thưởng — acc đã đứng đúng chỗ nó
> cần đến, chỉ thiếu mỗi việc **ngừng đi vào map event**.

Quy tắc đọc diff: mọi cửa dạng "hết giờ / hết việc / đã xong" phải nằm **trên** đường làm việc mà
nó định chặn. `tests/test_ngoai_gio_chan_truoc_khi_vao_map_event.py` so vị trí hai cửa với
`go_to_event`.

### L3i — Vòng thử lại nằm trong vòng ngoài thì "5 lần" không phải là trần

`for _lan in range(1, 6)` trông như có giới hạn, nhưng nếu hàm chứa nó được vòng ngoài gọi lại thì
trần đó **reset mỗi lượt** — thành vòng lặp vô hạn có nhịp.

> Party 53 (2K, `nhi_kieu`): **276 lần** thử vào map 12922 từ 22:00 đến 23:20 — **80 phút**. Hết 5
> lần thì acc "đứng yên tại safe", rồi vòng ngoài chạy lại từ đầu, lại 5 lần nữa.

Bộ đếm phải sống **trên client** (qua được nhiều lượt gọi), có trần, và vào được thì **xoá bộ đếm**
— trục trặc thoáng qua giữa giờ event không được cộng dồn thành "bỏ cuộc".

Đây chỉ là **lưới đỡ**. Nguyên nhân gốc của ca 2K là `events.json` để `lich: null` nên không ai
biết khung giờ; event nào khai báo `lich` thì đã bị chặn từ L3h.

### L3j — Mặc định im lặng của UI cũng là một quyết định, và nó ghi vào config

`idx = next((i for i, (k, _l) in enumerate(self.events) if k == cur), 0)` — không khớp thì lặng lẽ
lấy **phần tử đầu danh sách**. Người dùng bật mode event cho party mới, chưa động vào ô Event, bấm
Lưu → config ghi luôn event đầu bảng.

> Ca thật: party 53 thành `nhi_kieu` (2K) trong khi **52 party kia đều `npc_40`** (user:
> *"nhị kiều cái lồn mẹ mày, mode 40npc mà"*). Bot rồi đi vào map 2K và thử vào 276 lần.

Mặc định phải suy từ **những gì người dùng đã chọn ở nơi khác** (event mà đa số party đang dùng),
không phải từ thứ tự tình cờ trong file dữ liệu. Cùng bệnh ở `run_party_digioi`: fallback
`_k = next(iter(_evs))` cũng cho ra event đầu bảng.

### L3k — Một acc, một lệnh đang bay. Thêm đường ra lệnh phải kèm khoá

Khi có **hai đường** cùng ra một lệnh cho cùng một acc (điều phối tự gửi + acc tự nghe), không khoá
thì hai gói cùng bay, server trả **một** kết quả, luồng còn lại timeout — và cái timeout đó là
**bằng chứng giả** do chính bot tạo ra.

> Ca thật 10/09 party 2 (user: *"sao lại chốt kênh 8 bị full trong khi rất nhiều kênh khác trống"*)
> — cùng một acc, cùng một giây, hai giá trị `wait` khác nhau:
> ```
> 00:09:05 [gamo] Doi kenh 3 TIMEOUT sau 4.0s      <- đường điều phối
> 00:09:06 [gamo] Doi kenh 3 TIMEOUT sau 6.0s      <- đường acc tự nghe
> ```

Khoá phải là `blocking=False` — **xếp hàng cũng là gửi thừa**; lệnh đang bay sẽ trả kết quả thật
cho cả hai. Và lệnh bị bỏ **không được ghi kết quả gì**: ghi `-1` cho lệnh mình tự bỏ là tự chế ra
bằng chứng.

> Đây là hồi tố của chính L3b: thêm đường điều phối tự gửi để chữa ca party 3 bị điếc, nhưng đường
> cũ vẫn chạy song song. **Thêm một đường ra lệnh thì phải hợp nhất, không phải cộng thêm.**

### L3l — Phân biệt "server nói" với "bot đoán", đừng để cái đoán tước mất lựa chọn

Mã 2 `<沒有該分區>` và mã 4 `<分區人數已滿>` là **server nói rõ**. `-1` là bot tự đặt khi hết lượt
chờ mà server im lặng — đó là **không biết**, không phải "kênh đầy".

> Timeout hàng loạt (từ L3k) đẩy hết kênh trống vào sổ đen. Sổ đen nuốt sạch ứng viên → nhánh "kênh
> ít người nhất mà đủ chỗ cả team" không còn gì để chọn → rơi xuống nhánh cuối và chốt bừa vào một
> trong ba kênh party đang đứng, **cả ba đều đầy**:
> ```
> 00:09:27 party lech kenh {4:1, 6:1, 8:1, 14:1, 21:1} -> CHOT kenh dich = 8
> ```
> Bảng kênh lúc đó có **57 kênh**.

Nguyên tắc: **thông tin yếu chỉ được dùng khi nó không tước mất lựa chọn.** Còn ứng viên thì cứ
tránh kênh vừa timeout; hết ứng viên thì bỏ phần suy đoán ra và tìm lại — tốn nhất là thêm một lần
đổi kênh. Bằng chứng mạnh thắng: một acc timeout mà acc khác nhận mã 4 thì kênh đó là **chắc**.

Kèm theo: khi rơi xuống nhánh đường cùng, **phải nói ra vì sao**. Log cũ chỉ in "không kênh nào đủ
chỗ" — không phân biệt được *57 kênh đều đầy thật* / *sổ đen nuốt hết* / *đọc sai sức chứa*, ba
nguyên nhân khác hẳn nhau. Giờ in thẳng: bao nhiêu kênh trong bảng, bao nhiêu bị sổ đen, kênh rỗng
nhất còn mấy chỗ.

### L3m — Đừng xoá dữ liệu cũ trước khi có dữ liệu mới

Hỏi lại server không phải lý do để vứt câu trả lời cũ. Bản cũ vài chục giây vẫn dùng được; bản
**rỗng** thì không dùng được vào việc gì, và nó đẩy mọi nhánh quyết định xuống đường cùng.

> Ca thật 10/09 (user: *"hình như nó vẫn ko tìm kênh ít người trước mà nó chốt kênh member đang ở
> luôn"*) — **mọi** lần chốt kênh đều rơi vào nhánh (b) "lấy kênh đang nhiều member nhất", nhánh
> (a) "kênh ít người nhất mà đủ chỗ cả team" **không chạy lần nào**. Dòng log chẩn đoán thêm hôm
> trước chỉ ra ngay:
> ```
> 02:26:28 [party 45] khong kenh nao du 5 cho - bang 0 kenh, so den 0 kenh, kenh rong nhat con ?
> ```
> Đếm cả file: **6105 lần `bang 0 kenh`** so với 277 lần `bang 58 kenh` — **94%** số lần chốt kênh,
> điều phối không có dữ liệu kênh nào. Luật chọn không sai; **dữ liệu không có**.
>
> `request_channel_list()` đặt `self.channels = {}` ngay khi gửi `0x07 0100`, rồi `S:007-001` mất
> vài giây mới về (có khi không về). `pick_best_channel` còn gọi nó tới 4 lần liên tiếp.

Cách đúng: giữ bản cũ, khi gói về thì **thay thế nguyên khối** (không có cảnh nửa cũ nửa mới), và
bên đọc **tự bỏ bản quá cũ** theo mốc nhận (`DS_KENH_QUA_CU_SEC`, rộng hơn nhịp hỏi lại vài lần để
luôn còn bản dùng được giữa hai lần hỏi).

> Bài học rộng hơn: *"cũ"* và *"rỗng"* là hai trạng thái khác nhau, và code hay gộp chúng làm một.
> Cũng cùng họ với L3l (*"không biết"* ≠ *"kênh đầy"*) và L13 (*"chưa biết"* ≠ *"hết"*).

**Dòng log chẩn đoán đã trả công ngay lần đầu.** Nếu không có nó, ba khả năng — 57 kênh đầy thật /
sổ đen nuốt hết / đọc sai sức chứa — vẫn còn phải đoán, và t đã đoán sai một lần rồi (L3l).

### L3n — Không vòng chờ nào được VÔ HẠN, và không chờ cờ do LEADER bật

Một barrier `while not <cờ leader>.is_set()` không có hạn là chỗ acc **biến mất khỏi tầm điều
phối**: nó không nghe lệnh, không log, không tự thoát. Điều phối vẫn ra lệnh đều đặn — nhưng không
ai nghe.

> Ca thật 10/09 party 50 (user: *"p50 bị làm sao"* → *"vẫn còn để leader quyết định cơ à"*):
> ```
> 11:53:51 [dakmot] (LEADER) reform: 4/4 member join lai -> KEO qua cong ra train map
>                   -> set route_party_ready, đi qua cổng
> 11:54:05 [dakmot] qua cong idx=1 -> map 18000        <- leader sang map mới MỘT MÌNH
> 11:54:21..38  3 member: PARTY ... ROI doi -> roster 3 -> 2 -> 1   (đội TAN)
>               leader vào vòng reform mới -> route_party_ready.clear()
> 11:54:38 → 12:00   ba acc IM HOÀN TOÀN, không cả keepalive `pos=`
> ```
> py-spy trên tiến trình thật xác nhận ba luồng đứng đúng dòng đó. Trong khi ấy điều phối **biết
> hết**: `12:00:40 party dang o 2 MAP KHAC NHAU [18000, 18021] -> se gom` — ra lệnh vào chỗ không
> người nhận.

Hai tầng sai chồng nhau:

1. **Chờ vô hạn** — lối thoát duy nhất là `_ab()` (`reform_gen` đổi). Leader im luôn thì kẹt vĩnh viễn.
2. **Cờ do leader `clear()` được** — leader vào vòng reform mới là member đang chờ vòng hai bị đá
   ngược về vòng một, đếm lại từ đầu. Chỉ thêm hạn thôi **không đủ**.

Cách đúng: cờ chỉ còn là **đường thoát sớm**; điều kiện thật nằm ở chỗ khác — đọc thẳng
`account_clients` (L2): leader còn chạy không · leader đã tới đích chưa · mình đã tới đích chưa —
cộng **hạn cứng**. Hết đường nào thì `return`, trả quyền cho keepalive → điều phối (L1).

**Kiểm bằng máy:** `tests/test_khong_cho_vo_han_co_cua_leader.py` quét mọi
`while not st["..."].is_set():` trong mã (đã bỏ comment) và bắt buộc mỗi cái có ít nhất một lối
thoát: hạn thời gian, nghe được lệnh điều phối (`_nghe_lenh_kenh()`), hoặc thoát khi leader tắt.
Thêm barrier mới mà quên lối thoát là test đỏ.

### L3o — Acc KHÔNG có quyền phủ quyết lệnh điều phối

Điều phối chốt `VIEC_GOM` thì acc **phải gom**. Acc chỉ được chọn *cách* thi hành (gom tại chỗ hay
về thành), không được quyết *có gom hay không*.

`_party_tai_cho_xu_ly` chạy trong **luồng acc**. Nó tự đọc tình hình, tự kết luận, rồi trả `True` =
"đã xử lý tại chỗ" — mà `True` thì caller **bỏ luôn `_do_reform()`**, tức đường gom của điều phối.
Nói cách khác: lệnh điều phối phải đi qua cửa của acc, và acc có quyền chặn. Chính comment cũ trong
hàm tự thú: *"đây là acc TỰ QUYẾT bắt cả party rồi đổi"*.

> Ca thật 10/09 party 10 (user: *"leader đứng train 1 mình thế kia"* → *"vụ này là đứa nào quyết
> định mà đéo thèm nghe theo điều phối"*):
> ```
> 19:06:18 [party 10] REFORM gen -> 17 - party dang o 4 MAP khac nhau -> gom
> 19:07:57 [party 10] viec=gom - party dang o 2 MAP khac nhau [21001, 21841]
> 19:16:39..19:18:31  bốn member lặp y hệt một dòng MỖI 22 GIÂY:
>     (member) BO QUA sync kenh: party dang o KHAC MAP [21001, 21841]
> ```
> Leader đánh trận một mình ở 21841 suốt hơn 10 phút. **Lệnh gom có, người thi hành không có** — acc
> đã tự trả `True` qua nhánh *"sync kênh chưa xong → đồng bộ lại"*.

Ca này còn lòi ra một mâu thuẫn: `_tinh` kết luận **"lech_kenh"** (số chụp *trước* vòng chờ ra
rally, kéo dài hàng chục giây) trong khi `_party_same_map` đọc `account_clients` **ngay lúc đó** lại
thấy khác map. Hai chỗ cùng một sự thật, hai kết quả — và cái sai thắng. **Số đọc sau cùng mới là
số đúng** (`_cung_map_ca_party`).

Hai sửa: đầu `_party_tai_cho_xu_ly` đọc kế hoạch điều phối, chốt `VIEC_GOM` thì trả `False` ngay
(rơi xuống `_do_reform()`); và sync kênh hỏng **vì lệch map** thì cũng trả `False` — lệch map phải
gom map, không phải thử lại sync tại chỗ.

> **Bẫy khi sửa chỗ này:** nhiều test neo vào `_party_tai_cho_xu_ly` bằng **cửa sổ ký tự cố định**
> (`s[i:i + 5600]`). Thêm một khối comment là trượt hết, và trượt kiểu đó báo "code sai" trong khi
> hành vi không đổi — đúng L3i. Neo theo **thụt lề giảm** để lấy trọn thân hàm, đừng theo `def` kế
> tiếp: giữa thân còn hàm lồng nhau, lấy theo `def` ra 100k ký tự.

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

**Mọi `_bump_reform` trong hàm điều phối PHẢI có cooldown.** Hàm điều phối chạy mỗi 2 giây, mà mỗi
`_bump_reform` là **abort mọi acc đang đi đường** (`_ab()`). Bump liên tục = tự huỷ chính việc mình
vừa sai.

> Vi phạm thật, và là code tôi viết sáng 06/09 rồi quên đặt hạn — đúng cái luật này:
> `p28 REFORM gen -> 8541`, `p39 -> 8614`, `p23 -> 8035` — **tám nghìn lần bump trong 5 tiếng**,
> user: *"rất nhiều party kẹt ở thành mà không đi đánh"*.
> `tests/test_rule_dieu_phoi.py` giờ quét mọi `_bump_reform` trong hàm `_dieu_phoi*` / `_chot*`
> và bắt buộc phải có cooldown gần đó.

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
| Bảng `*_reports` / `*_done_by` để đếm đủ người | L2 |
| Việc chung mà chỉ acc gọi hàm tự lo cho mình | L2b |
| Kết luận "ổn" chỉ vì các acc khớp nhau, không so với việc phải làm | L2c |
| Cả party ở THÀNH lâu mà mode là train/DG/event | L2c |
| Đếm đội bằng `joined_member_count` thay vì `c.party_members` | L2d |
| Chờ gói xác nhận thứ đã suy ra chắc chắn (leader rớt ⇒ đội tan) | L2e |
| `while` chờ cờ của acc khác, không có lối ra cấp party | L9 |
| Leader tự `leave_party()` / xoá danh sách đã-join giữa vòng mời | L1, **L0** |
| `x_until = now + N` làm trạng thái cấp party | L1b |
| Việc kết thúc mà phải đi hạ cờ từng acc | L1b, L2 |

## Được ép bằng test

`tests/test_rule_dieu_phoi.py` bắt các vi phạm kiểm được bằng máy; `test_leader_khong_tu_dap_party.py`
(L1) và `test_pho_ban_vo_ha_co_ca_party.py` (L1b) neo hai ca ở trên. Test đỏ ở đó nghĩa là **luật bị
phá**, không phải "test cũ neo sai" — sửa code, đừng sửa test.

Phần còn lại (L3, L4, L5, L7, L11, L12) phải tự soi khi review, dùng bảng "Cấm" ở trên.
