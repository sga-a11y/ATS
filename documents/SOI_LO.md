# SOI LÒ (lò rèn / shop lò) — luật tự mua

Bot soi lò một lần lúc login (`process_furnace`), gói `0x59`:
`C:089-001` soi (sub01) → `C:089-002` mua (sub02) `[kind 1B][slot 1B][itemId 2B LE]`.

`kind` = tab: **1 = Võ tướng, 2 = Trang bị, 5 = Chuyển sinh** (`FURNACE_TAB_KIND`).

## Ba chế độ mỗi item

| Chế độ | Nghĩa |
|---|---|
| `auto` | tự mua (theo luật bên dưới) |
| `notify` | chỉ báo lên "Chú ý", user tự quyết |
| `skip` | bỏ qua hẳn |

Item không có trong config của acc thì mặc định:
1. id **ngoài** `furnace_pool.json` (game update thêm item mới) → `notify`
2. id trong `furnace_default_notify.json` (món của võ tướng có vũ khí chuyên dụng) → `notify`
3. còn lại → bỏ qua

## Luật tự mua (`auto`)

| Tab | Mua khi |
|---|---|
| Võ tướng (1) | có là mua, không giới hạn |
| Trang bị (2) | trong **túi** chưa có cái nào (≥1 là thôi) |
| Chuyển sinh (5) | xem bảng dưới |

### Tab chuyển sinh

`bag_counts` = số lượng **trong túi**, không tính đồ đang mặc.

| Món | Không mua khi |
|---|---|
| **Kim Tỏa `X`** | túi đã có ≥1 · **hoặc** đã sở hữu `X` ở **rb1/rb2** |
| **Mê `X`** | túi đã có ≥1 · **hoặc** `X` **đã học đặc kỹ** |
| **Tướng Tinh** | chỉ khi túi đã có ≥1 — ngoài ra mua không giới hạn |

> Lý do (user chốt 2026-09-01): *"mua nó cũng rẻ thôi, nhưng mua vật phẩm ko cần dùng nữa nó tốn
> slot đồ là chính"*. Nên luật nhắm vào **slot túi**, không phải chips.

**Sở hữu võ tướng** = 4 con **mang theo** (`state.carried_pets`) + toàn bộ **nhà trọ**
(`vantieu_roster_ids`, về lúc login qua `S:031-006`).

## Ghép item → võ tướng: dùng npc_id, KHÔNG dùng tên

Tên item bị viết tắt trong game: `K.Tỏa Mã Ng.Nghĩa` trong khi võ tướng tên đầy đủ là
`Mã Nguyên Nghĩa`. Ghép bằng tên là trượt. `items_gamedata.json` có sẵn npc_id:

| `a1k` (= `a2k`) | Loại | `a1v` | `a2v` |
|---|---|---|---|
| 65 | Kim Tỏa | npc rb0 | npc rb1 |
| 66 | Mê | npc rb1 | npc rb2 |
| 67 | Tướng Tinh | npc rb1 | npc rb2 |

Ví dụ `K.Tỏa Mã Ng.Nghĩa` (`0xb7fb`): `a1v=10007` = `0x2717` "Mã Nguyên Nghĩa rb0",
`a2v=41099` = "Mã Nguyên Nghĩa" (rb1).

Bảng dựng runtime bởi `_load_chuyen_sinh_map()`. Kim Tỏa chỉ cho biết rb0+rb1; **rb2 suy tiếp** từ
món Mê/Tướng Tinh có cùng rb1.

**Lọc id rác**: `a1v`/`a2v` không phải lúc nào cũng là võ tướng — `Mê Nhạn Điêu Tuyết` có
`a1v=100` (level yêu cầu), `K.Tỏa Ngọc Thố` có `a1v/a2v` không hề nằm trong `pets.json`. 50/938 món
dính kiểu này. Chỉ nhận giá trị **thật sự có trong `pets.json`**; món không lần ra võ tướng nào thì
bỏ khỏi bảng (giữ hành vi cũ = vẫn mua). Sau lọc: 456 Kim Tỏa / 165 Mê / 308 Tướng Tinh.

> **Hạn chế đã biết**: 150/456 món Kim Tỏa không có rb2 trong bảng. Trong đó **141 món là võ tướng
> KHÔNG CÓ rb2 trong game** (không tồn tại bản 45xxx cùng tên) — không phải sót. Còn **9 món** có
> bản 45xxx cùng tên nhưng cố tình không gán, vì tên không tin được:
> Tôn Kiên có **4** bản 45xxx trùng tên, và `K.Tỏa Tuân Du` lại trỏ tới võ tướng **`Hứa Du`** —
> tên item và tên võ tướng còn không khớp nhau.
> Với 9 món này, nếu acc đang giữ tướng ở rb2 thì bot vẫn mua thừa 1 cái.
>
> Cũng không suy theo dải id: cùng một tướng có id ở nhiều dải (Vu Độc: 10098 / 41010 / 42091 /
> 45230), và "Quan Vũ" có tới 19 bản khác tên hiển thị giống nhau.

## Đặc kỹ: vì sao phải cache

Cờ `specialSkillLearned` **chỉ có** trong gói `0x0f` — võ tướng đang mang theo (`Role.lua:857`),
và `S:020-049` khi tướng vừa học.

Võ tướng nằm **nhà trọ** về qua `S:031-006` → `Inn.SaveNpc` chỉ mang `npcId / level / exp / hp /
name / status` (`_lua_dec/Logic/Inn.lua:25`) — **chính client cũng không biết** con trong kho đã học
đặc kỹ hay chưa (`status` chỉ là cờ đang đi vận tiêu).

Nên bot **nhớ lại**: mỗi khi thấy `pet_special_skill[pid] = True` thì ghi npc_id vào khoá `dac_ky`
trong `account_skills_cache.json` (`save_dac_ky_cache`). Cất vào kho rồi vẫn nhớ. Cache chỉ **gộp
thêm**, không bao giờ xoá — đặc kỹ học rồi là vĩnh viễn.

Hệ quả: acc mới cài bot mà tướng đã học đặc kỹ **từ trước** và đang nằm nhà trọ thì lần đầu vẫn mua
thừa 1 món Mê; sau khi con đó được mang theo một lần là bot nhớ.
