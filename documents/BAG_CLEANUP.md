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
| `+ tên "Bí Cấp"/"BC "` | **477** | đúng cuộn gọi võ tướng |

Đã đối chiếu: không có cuộn nào mang chữ "Cấp" mà nằm ngoài bộ lọc, và đủ cả 51 cuộn của
`junk_scrolls.json` cũ.

| Mặc định | Điều kiện |
|---|---|
| Giữ lại | tướng **có vũ khí chuyên dụng** (86 cuộn) — đối chiếu `exclusive_weapons.json` |
| Phân giải | còn lại (391 cuộn) |

Cuộn của **bản nâng cấp** một tướng vẫn là tướng đó, mà `exclusive_weapons.json` chỉ liệt kê npc
gốc → phải lần ngược chuỗi trước khi đối chiếu (dùng chung `build_reincarnation_up`/`to_base` với
`crack_furnace_notify.py`):

    "BC Trương Giác Chân" → npc 41003 → (lần ngược) → 10001 Trương Giác (CÓ vkcd)

> **Còn hở**: 22 cuộn bản nâng cấp (npc id ≥ 40000, vd "BC Yến Nhân Trương Phi" 46407,
> "Bí Cấp Ma Quan Vũ" 45437) **không nối được vào chuỗi** — data K.Toá/T.Tinh không có cạnh cho
> chúng, và tên npc cũng không tra được. Chúng đang mặc định "Phân giải"; user tự đổi nếu muốn giữ.

Mặc định chỉ là **gợi ý, không khoá cứng**: pet có vkcd nhiều con vẫn lởm, user đổi được cả hai
chiều.

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
