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
sửa tay, không tắt được). Nay danh sách mở rộng lên 807 cuộn nên bật sẵn sẽ phá đồ của user —
bắt buộc user tự tick sau khi soát List.

> **Đổi hành vi**: bản này bot KHÔNG còn tự phân giải 51 cuộn cũ cho tới khi user tick.

## List cuộn — mặc định & override

`pet_scrolls.json` (807 cuộn) sinh bởi `tools/crack_pet_scrolls.py` từ `gamedata_Item.dat`:
`kind 38` (Bí Cấp) và `spare3 > 0` (`spare3` = npc id của tướng được gọi).

> `kind 38` còn ôm cả hộp quà / phiếu chọn — chúng có `spare3 = 0`. Không lọc thì list ra 5553
> mục và bot có thể phân giải nhầm hộp quà.

| Mặc định | Điều kiện |
|---|---|
| Giữ lại | tướng **có vũ khí chuyên dụng** (109 cuộn) — đối chiếu `exclusive_weapons.json` |
| Phân giải | còn lại (698 cuộn) |

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
