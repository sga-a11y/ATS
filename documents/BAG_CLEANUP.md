# Tự dọn túi đồ (Cài đặt nâng cao)

Gom các việc dọn túi rải rác thành 1 công tổng có thể tắt/bật, và cho user tự chọn cuộn võ
tướng nào được phân giải.

## Cấu trúc

```
Cài đặt nâng cao
  ☑ Tự dọn túi đồ  [Chi tiết]          auto_bag_clean (mặc định BẬT) = CÔNG TỔNG
        ☑ Tự bán Nồi đất               auto_sell_noi_dat       (mặc định BẬT)
        ☑ Tự vứt item rác (Ngọc Hư)    auto_discard_junk       (mặc định BẬT)
        ☐ Tự phân giải cuộn VT rác [List]  auto_decompose_scrolls (mặc định TẮT)
```

Tắt công tổng → cả 3 mục con ngưng, không cần bỏ tick từng cái. Cấu hình **theo party**
(nằm trong Cài đặt nâng cao nên có sẵn nút "Áp dụng cho các party khác").

## Vì sao "phân giải cuộn" mặc định TẮT

Phân giải là **mất hẳn** cuộn. Trước đây bot luôn phân giải theo `junk_scrolls.json` (51 cuộn,
sửa tay, không tắt được). Nay danh sách mở rộng lên 477 cuộn nên bật sẵn sẽ phá đồ của user —
bắt buộc user tự tick sau khi soát List.

> **Đổi hành vi**: bản này bot KHÔNG còn tự phân giải 51 cuộn cũ cho tới khi user tick.

## List cuộn — mặc định & override

`pet_scrolls.json` (477 cuộn) sinh bởi `tools/crack_pet_scrolls.py` từ `gamedata_Item.dat`:
`kind 38` + `spare3 > 0` + **tên bắt đầu bằng "Bí Cấp" / "BC "**.

`kind 38` = "dùng vào thì nhận được một thứ gì đó", không riêng cuộn gọi võ tướng:

| Lọc | Còn lại | Vấn đề |
|---|---|---|
| `kind 38` | 5553 | ôm cả hộp quà, phiếu chọn (`spare3 = 0`) |
| `+ spare3 > 0` | 807 | vẫn còn thú cưỡi ("Ba Đậu", "Bạch Hổ Phiếu"), chân dung, thời trang, đồ ăn — chúng cũng trỏ vào một npc id |
| `+ tên "Bí Cấp"/"BC "` | 477 | đúng cuộn gọi võ tướng |
| `+ furnaceCount > 0` | **448** | game chỉ cho phân giải khi `furnaceCount > 0` (`Item.IsDismantle`, `Logic/Item.lua:2519`) — 29 cuộn không phân giải được, hầu hết là bản đặc biệt |

Đã đối chiếu: không có cuộn nào mang chữ "Cấp" mà nằm ngoài bộ lọc, và đủ cả 51 cuộn của
`junk_scrolls.json` cũ.

| Mặc định | Điều kiện |
|---|---|
| Giữ lại | tướng **có vũ khí chuyên dụng** (95 cuộn) — đối chiếu `exclusive_weapons.json` |
| Phân giải | còn lại (353 cuộn) |

Cuộn của **bản nâng cấp** một tướng vẫn là tướng đó, mà `exclusive_weapons.json` chỉ liệt kê npc
gốc → phải lần ngược chuỗi trước khi đối chiếu (dùng chung `build_reincarnation_up`/`to_base` với
`crack_furnace_notify.py`):

    "BC Trương Giác Chân" → npc 41003 → (lần ngược) → 10001 Trương Giác (CÓ vkcd)

> **Còn hở**: 22 cuộn bản nâng cấp (npc id ≥ 40000, vd "BC Yến Nhân Trương Phi" 46407,
> "Bí Cấp Ma Quan Vũ" 45437) **không nối được vào chuỗi** — data K.Toá/T.Tinh không có cạnh cho
> chúng, và tên npc cũng không tra được. Chúng đang mặc định "Phân giải"; user tự đổi nếu muốn giữ.

Mặc định chỉ là **gợi ý, không khoá cứng**: pet có vkcd nhiều con vẫn lởm, user đổi được cả hai
chiều.

### Đồ chuyển sinh đi theo cuộn

Cuộn ở trạng thái **Phân giải** thì **K.Toả + T.Tinh + Mê** của đúng con pet đó cũng bị phân giải
(mạch của pet bỏ đi thì giữ làm gì) — trường `extra` trong `pet_scrolls.json`, ghép theo npc gốc
giống `crack_furnace_notify.py`. Mặc định: 353 cuộn phân giải kéo theo 626 món (tổng 979 tid).

Nhiều cuộn có thể trỏ cùng một npc gốc (`Bí Cấp X` và `BC X Chân`) nên **dùng chung** đồ chuyển
sinh. Khi một cuộn giữ, một cuộn phân giải thì **GIỮ LẠI THẮNG**, không phá đồ. (Hiện 0 trường
hợp trùng, nhưng user đổi trạng thái tay là tạo ra ngay.)

`scroll_modes` trong config **chỉ lưu mục user đã đổi khác mặc định** → game ra cuộn mới thì tự
theo mặc định, và sửa bảng mặc định sau này vẫn có hiệu lực, không bắt user tick lại.

## Nguồn danh sách phân giải (đã đổi)

Trước đây `decompose_junk_scrolls` còn lấy thêm `items_known.json` (type `scroll`/`junk`). Nguồn
này **đã bỏ**: nó bắt theo type nên sẽ phân giải cả cuộn user tick "Giữ lại".

## File liên quan

| File | Vai trò |
|---|---|
| `tools/crack_pet_scrolls.py` → `pet_scrolls.json` | sinh danh sách cuộn |
| `bot/client.py` | `_load_pet_scrolls`, `_decompose_scroll_tids`, gate ở 3 hàm dọn túi |
| `run_party_digioi.py` | `_scroll_modes_map`, gán vào client, tham số `setup_party_runtime` |
| `gui.py` | `_open_bag_clean_detail`, `_open_scroll_list` |
| `MainActivity.kt` | `ScrollListDialog`, `loadPetScrolls`, dialog "Dọn dẹp túi đồ" |
| `Party.kt` / `PartyStore.kt` | 4 field mới + đọc/ghi JSON |

⚠️ `setup_party_runtime` được Kotlin gọi **theo vị trí** → tham số mới phải thêm ở **cuối**
signature, chèn vào giữa sẽ làm lệch hết các tham số phía sau.

## Đồng bộ với Soi lò (chỉ chạy lúc ấn Lưu)

Hai cấu hình này đá nhau được: lò "tự mua" K.Toả/Mê khi túi trống → phân giải xoá đi → vòng lò
sau lại mua. Engine chỉ mua khi túi **chưa có** nên vòng đốt tiền này **lặp vĩnh viễn**, không tự
thoát. Nên khi lưu:

| Đổi ở đâu | Hành động |
|---|---|
| Cuộn: Phân giải → Giữ lại | không làm gì bên lò (giữ cuộn thì mua/báo vẫn hợp lý) |
| Cuộn: Giữ lại → Phân giải | lò đặt **Bỏ qua** cho Bí Cấp + K.Toả + T.Tinh + Mê của cuộn đó |
| Lò: Bỏ qua → Tự mua/Thông báo | cuộn sở hữu mục đó về **Giữ lại** |

⚠️ **Lệch phạm vi**: config lò lưu theo **từng account** (`account["furnace"]`), còn list phân giải
theo **party** (`party["scroll_modes"]`). Nên chiều cuộn→lò phải ghi vào lò của **mọi account trong
party**; không quét hết thì account khác vẫn mua rồi bị phá.

Ghi `"skip"` **tường minh** chứ không xoá key: item mặc định Thông báo mà xoá key thì lần sau lại
về notify. Ngược lại, cuộn mặc định Giữ thì **xoá key** khỏi `scroll_modes` thay vì ghi `"keep"`
(file config chỉ lưu phần khác mặc định).

Ở cấu hình mặc định hiện tại: **0 xung đột** — cả hai bên cùng suy từ rule vkcd. Xung đột chỉ sinh
ra khi user tự sửa tay.

Điểm nối khác nhau giữa 2 bản (cùng thời điểm "ấn Lưu"): PC nối trong nút Lưu của chính 2 dialog
con; APK so 2 bản config ở chỗ lưu ngoài (lưu party / lưu account) để khỏi đổi chữ ký 3 dialog.
