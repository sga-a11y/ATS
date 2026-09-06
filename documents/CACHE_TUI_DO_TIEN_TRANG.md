# CACHE TÚI ĐỒ + TIỀN TRANG

Mục đích (user chốt 06/09/2026):
- **Túi đồ** — *"để xem lại khi offline"*.
- **Tiền trang** — *"để xem và nhớ lại trong đó đang có gì"*, để sau này mở rộng
  [soi lò](SOI_LO.md) check cả đồ trong kho.

## 1. Server gửi kho khi nào?

**Không bao giờ tự gửi.** Bot chỉ thấy tiền trang đúng lúc nó đi NPC Trác Quận và mở kho:

```
C2S 0x20 sub0200 08 → C2S 0x14 sub0100 [npc] → C2S 0x14 sub0600
                                    → S2C 0x1e sub0100 = TOÀN BỘ kho   (S:030-001)
kho còn mở, mỗi lần cất/lấy         → S2C 0x1e sub0400/0500 = MỘT ô    (S:030-004/005)
```

Đóng kho là hết. Login lại không có gói nào mang kho về.

**Hệ quả**: cache kho chỉ mới bằng **lần mở kho gần nhất**, và acc chưa từng mở kho thì
**coi như không có gì**. Không làm nút "đọc lại kho" — mở kho tốn một chuyến đi Trác Quận,
không bõ công (user chốt).

## 2. Lưu ở đâu

Dùng chung `account_skills_cache.json` (đã có sẵn đường nạp ở cả PC lẫn APK, và đã có sẵn cơ chế
"acc tắt thì đọc cache"), thêm 2 khoá mỗi acc:

| Khoá | Nội dung |
|---|---|
| `bag` / `bag_ts` | `{slots: {slot: [tid, cnt]}, cap, used, equip_fit, pet_equip_fit, pets, pet_slot}` |
| `bank` / `bank_ts` | `{slots: {idx: [tid, cnt]}}` |

Bốn hàm `save_*_cache` cũ chép tay giống hệt nhau → gom lại thành `_cache_ghi` / `_cache_doc`.
Ghi chỉ khi nội dung đổi (so chữ ký, dùng lại `_skill_cache_sig`).

Cache lưu cả **đồ đang mặc + pet mang theo**: thiếu thì bản offline mất hàng 6 ô trang bị và mất
các nút chọn pet, nhìn khác hẳn lúc acc chạy — user tưởng hỏng. **Không** cache chỉ số nhân
vật/pet: chúng đổi theo cấp/trang bị, lưu ra là lệch.

### Nhịp ghi

**Túi đồ chỉ ghi ở HAI mốc: lúc LOGIN và lúc DỪNG acc** (user chốt 06/09: *"trong lúc chạy thì chỉ
dùng cache tiền trang, cache túi đồ ghi liên tục cũng thừa"*). Bản cache chỉ để **xem khi acc đã
tắt**, nên chỉ bản ghi cuối cùng có người đọc — mọi bản ghi giữa chừng là phí.

| Nguồn | Nhịp | Vì sao |
|---|---|---|
| `0x17 sub05` snapshot đầy (login) | ghi | bản đầy đủ nhất, và hiếm |
| `close()` — dừng acc / mất kết nối | ghi | chốt lại lần cuối; nội dung không đổi thì `_cache_ghi` tự bỏ qua |
| `0x17 sub08` nhặt/dùng từng món | **không ghi** | túi đổi vài giây một lần × 246 acc, mà không ai đọc |
| `S:030-001/004/005` kho | ghi mọi lần | kho chỉ mở lúc đi cất đồ — hiếm, và bỏ lỡ một lần là mất cả lần mở |

> Bản đầu tiên có tiết chế 120s cho `sub08`. Vẫn không đủ: đo 06/09 với 246 acc, cache túi chiếm
> **91.5% file** (596/651 KB) và thành ~20 lượt ghi/phút, **mỗi lượt ghi lại cả file** → 6/12 lần
> đọc rơi trúng lúc file đang ghi dở.

## 3. Bản cache là CHỈ XEM

Trước đây `bag_info()` **từ chối cache hẳn**, với lý do đúng:

> *"tui do KHONG cache duoc — no la snapshot SONG trong client, doc file ra thi vua sai vua nguy
> hiem (bam 'phan giai' theo so cu la mat nham do)"*

Lo đó chỉ đúng với **nút bấm**, không đúng với **xem**. Nên giữ nguyên tinh thần bằng cách khoá nút:

| Ngữ cảnh | Nút còn lại |
|---|---|
| Acc chạy, tab túi | đủ như cũ |
| **Acc tắt**, tab túi | **chỉ "Tự cất vào tiền trang"** — nút này ghi thẳng `accounts.json`, không gửi gói nào lên server |
| Tab Tiền trang (luôn) | không nút nào |

`bag_info()` trả kèm `live` (False = bản cache) và `ts`; UI khoá nút theo cờ đó. `bag_cmd()` vẫn
trả `"False: acc chưa chạy"` khi không có client — bản cache không có đường nào bấm được.

Bản PC dùng shim `gui.py::_TuiCache` (client giả, chỉ đọc) thay vì rải `if self._live` khắp
`BagDialog`: dialog gọi `self.c.<...>` ở vài chục chỗ, quên một chỗ là `AttributeError` giữa chừng
→ dialog mở ra không có lưới nào (đã từng xảy ra). Shim không có hàm gửi lệnh nào, nên lỡ gọi là
lỗi to ngay tại chỗ, không âm thầm gửi sai.

## 4. Tab "Tiền trang"

Tab thứ 5 của cửa sổ Túi đồ, ngay bên phải "Nguyên liệu". `TAB_TIEN_TRANG = 5` để **riêng**, không
nhét vào `bot/bag_tabs.py::TAB_NAMES` — bảng đó là luật **phân loại item** của client
(`matches_tab`), còn tiền trang không phải một loại item mà là một cái kho khác.

Kho không lọc theo tab và không bao giờ ghép thêm đồ đang mặc vào lưới.

### Hàng nút ở trên chật — nút "Mua slot" từng bị cắt

Thêm tab thứ 5 làm hàng trên dài thêm ~85px → nút "Mua slot (240 vàng)" bị đẩy ra ngoài, chỉ còn
thấy `Mua :` (user báo 06/09). Ba việc đã làm:

1. Rộng cửa sổ = `max(lưới 10 cột, 780)` → **820**. Đo bằng Tk: 5 tab = 475, số ô = 138, nút mua =
   120, lề = 32 → cần 759; lấy dư cho chuỗi giá dài hơn.
2. **Pack bên phải TRƯỚC** rồi mới đến hàng tab. Tk chia chỗ theo thứ tự pack, đứa nào pack sau mà
   thiếu chỗ thì bị cắt — nút "Mua slot" là thứ **duy nhất không đoán được bằng mắt**, nên nó phải
   được chia chỗ đầu tiên. Hàng tab chịu thiệt nếu hết chỗ (chữ ngắn, vẫn đọc được).
3. Mốc ảnh chụp của bản cache để ở **tiêu đề cửa sổ**
   (`Túi đồ - sieugaaa  (ảnh chụp 11:58 hôm nay — acc tắt, chỉ xem)`), không nhét vào hàng nút.
   Dòng đếm chỉ còn `138/180 (tab này: 15) · chỉ xem`.

`tests/test_cache_tui_do_tien_trang.py::TestHangNutTrenKhongCatMatNutMuaSlot` dựng dialog thật rồi
đo toạ độ: nút "Mua slot" phải nằm trọn trong cửa sổ với chuỗi giá dài nhất, và cả 5 tab không được
tràn ra ngoài.

Acc tắt thì **không lập thread hỏi giá slot**: shim `_TuiCache` không có `query_bag_slot_price`, và
dù có cũng không mua được.

## 5. Ghi nguyên tử

`open(path, "w")` **cắt trắng file trước rồi mới ghi**. Giữa hai bước đó, ai đọc file cũng thấy
bản dở dang. Đo bằng tay 06/09 lúc bot đang chạy 90 acc: `account_skills_cache.json` nhảy
**8 KB → 80 KB → 56 KB** trong vài giây. Hậu quả: GUI đọc trúng khe đó thì `json.load` ném lỗi →
hiện "chưa có ảnh chụp"; sập nguồn đúng lúc đó thì **mất sạch cả file**.

Thêm cache túi đồ (to hơn nhiều, ×90 acc) làm khe đó rộng ra, nên đổi cả 6 chỗ ghi trong
`bot/client.py` sang `_ghi_json_an_toan()`: ghi ra `<file>.tam<pid>` rồi `os.replace`. `os.replace`
là thao tác nguyên tử trên cùng ổ đĩa — đọc giả thấy bản **cũ** hoặc bản **mới**, không bao giờ
thấy bản dở. Ghi hỏng thì file cũ còn nguyên và file tạm bị xoá.

> Bẫy đi kèm: mấy bài test cache (điểm tiềm năng, túi đồ) trước đây ghi thẳng vào
> `account_skills_cache.json` **thật của máy**. Bot đang chạy ghi đè lên nó vài lần một giây nên
> bản ghi của test biến mất giữa chừng → test đỏ mà chẳng liên quan gì đến code. Đã cho chúng chạy
> trên file tạm riêng.

## 6. Cho soi lò (chưa nối)

```python
from bot.client import bank_counts_cache
bank_counts_cache(username)   # -> {tid: tổng}  — CÙNG hình dạng với c.bag_counts
```

[Luật soi lò](SOI_LO.md) hiện đọc `bag_counts` ("trong túi đã có chưa"). Muốn tính cả kho thì cộng
thêm nguồn này, không phải bóc lại gói. Nhớ: `{}` nghĩa là **không có gì trong kho** (theo quyết
định ở mục 1), không phải "không biết".
