# THÚ CƯỠI (座騎) — nâng cấp + bồi dưỡng

Opcode **79 = `0x4f`**. Nguồn: `_lua_dec/Logic/Mounts.lua` + bảng `MountsGrow_C.dat`
(bóc bằng `tools/crack_mounts_grow.py` → `mounts_grow.json`). Chi tiết gói xem `KNOWLEDGE.md`.

## Luôn bật, không có ô tick
Chạy **ngay sau `use_login_items()`** (yêu cầu user) — vì bước đó có thể vừa mở "Túi Tọa Kỵ Đan"
(`0xb22c`) ra chính mấy viên kỵ đơn.

## Gói
| Lệnh | Nghĩa | Payload | Server xác nhận |
|---|---|---|---|
| `C:079-003` | nâng cấp thú cưỡi | `[bag_index 1B]` | `S:079-002 [cấp 1B]` |
| `C:079-004` | bồi dưỡng | `[kind 1B][bag_index 1B]` | `S:079-003 [kind 1B][điểm u16]` |

⚠️ Gửi **bag_index** (slot trong túi), **không phải item id**.

## 5 viên kỵ đơn (cố định suốt 15 cấp)
| kind | chỉ số | item |
|---|---|---|
| 1 | Atk | `0x7d66` Công Kỵ Đơn |
| 2 | Int | `0x7d67` Trí Kỵ Đơn |
| 3 | Def | `0x7d68` Phòng Kỵ Đơn |
| 4 | ExtraHp | `0x7d69` Hp Kỵ Đơn |
| 5 | ExtraSp | `0x7d6a` Sp Kỵ Đơn |

Viên **nâng cấp** thì **đổi theo cấp**: cấp 1–9 dùng `0x7d65` Tăng Cấp Kỵ Đơn, **cấp 10–14 dùng
`0x7d6b` Tinh Hoa Nâng Cấp Tọa Kỵ VIP**, cấp 15 hết cấp.

## Luật (lấy từ client, không đoán)
**Nâng cấp trước, bồi dưỡng sau** — vì nâng cấp *mở thêm trần* cho chỉ số.

`Mounts.AttributeUp` chặn khi: hết bảng (cấp 15), **`attributeLv >= mountsLv`**, hoặc không có
viên trong túi. Lưu ý kiểm **trước khi gửi** ⇒ chỉ số **chạm đúng bằng** cấp thú cưỡi mới dừng,
không phải dừng ở dưới một cấp.

`Mounts.LevelUp` chặn khi: đang trong trận, `mountsLv >= VIP_mount + 10`, thiếu viên, thiếu vàng.

**Bot KHÔNG tự kiểm vàng** — bot không theo dõi vàng, mà gửi hụt thì server từ chối và **không mất
gì**. Không thấy `S:079-002` trong `MOUNT_ACK_WAIT` (3s) ⇒ thiếu vàng hoặc chạm trần VIP ⇒ **thôi
ngay, không lặp**.

## Điểm → cấp
Điểm server gửi là **cộng dồn**; trừ dần `need` từng cấp (`Mounts.GetAttributeProgress`).
Điểm cần mỗi cấp (chung cả 5 chỉ số):
`10, 20, 30, 50, 100, 300, 500, 1000, 2000, 3000, 3500, 4000, 4500, 5000, 5000`.

Sau mỗi lần bồi dưỡng, bot đọc **giá trị tuyệt đối** server báo (`S:079-003`) chứ không tự cộng —
"1 viên = 1 điểm" chỉ là suy luận, đọc thẳng số server thì không bao giờ lệch.

## Trần thực tế
`attributeLv <= mountsLv` và bot chỉ tự nâng cấp được tới **cấp 9** (từ cấp 10 cần viên VIP
`0x7d6b` mà user thường không có). Nên trong thực tế chỉ số cũng dừng quanh đó.

## Chống lặp vô hạn
- Nâng cấp: server không xác nhận → dừng ngay.
- Bồi dưỡng: `MOUNT_MAX_FEED = 400` lệnh/lần login, và mỗi lệnh phải được server xác nhận mới đi
  tiếp.
- `time.sleep(0.35)` giữa các viên để không dội gói server.
