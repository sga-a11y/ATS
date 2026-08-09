# EVENT NHỊ KIỀU (2K) — thiết kế auto đánh nhiều tầng

Trạng thái: **đang chờ pcap** (chưa code). Event hiện bị ẩn từ 30/07 (`e8f015b`, lý do ghi
"chưa làm xong" = thiếu đúng phần auto đánh mô tả dưới đây).

## Đang có sẵn (đã chạy được)
Vào map event — dựng từ `ts_event.pcap` (đã verify chứa map 12921/12922):

- chọn event `0x4d 03000100` → server tele tới **staging 12921**
- đi bộ 4 chặng → qua cổng `idx=2` tại (350,330) → **map event 12922**
- đường ra: `exit.out_map = 12003`, đi bằng smart scene route

Dữ liệu nằm ở `events.json → events.nhi_kieu`. Code chạy: `client.go_to_event()` / `exit_event()`.

## Cái còn thiếu — auto đánh
2K **không dùng lại được** cơ chế 40 NPC. Khác biệt cốt lõi:

| | 40 NPC (`kind: npc_repeat`) | 2K (cần mới) |
|---|---|---|
| Vị trí | đứng yên 1 điểm, mở lại trận cùng chỗ | **đi cảnh**, nhiều tầng |
| Vòng lặp | mở NPC → đánh → lặp | tới điểm quái → đánh sạch → **lên tầng kế** |

## Quyết định đã chốt (theo yêu cầu người dùng)
1. **Lập party, cả đội đi cùng nhau** (leader dẫn, member bám theo) — không phải mỗi nick đi riêng.
2. **Tầng dưới khác nhau, tầng trên giống nhau** → kịch bản phải chịu được cả hai, không hardcode
   cứng toàn bộ.
3. **Dùng lại bộ tìm đường thông minh sẵn có** để tới điểm đánh nhau, thay vì chép cứng từng bước
   `move` như phó bản lv20: `follow_smart_scene_route()` / `_route_move()` (walkability đọc từ
   `Ground.mmg`), và quét quái động kiểu mode train (`mob_scanner`) cho các tầng khác nhau.
4. Dữ liệu tầng để trong `events.json` (`party_battle.kind = "floor_crawl"`), **không hardcode**
   trong .py — giống cách 40 NPC để `point` trong json.

## Khuôn code sẽ theo
`do_team_dungeon_lv20` — nó đã đúng hình dạng "nhiều chặng nối tiếp": một list, mỗi phần tử là
`{thoại, moves, transit}` cho một chặng. Khác là 2K thay `moves` cứng bằng smart route + scan quái.

## Bản đồ tháp — ĐÃ CÓ SẴN trong `world_nav.json` (không cần pcap)
Giả thuyết "map ID tăng dần" đã được xác nhận bằng dữ liệu:

- Tháp chính: **12922 → 12959** (38 tầng), 12921 là map chờ. `12940` không tồn tại.
- `edges` có sẵn cạnh nối từng tầng kèm **door index**, `gates` có sẵn **toạ độ tâm cổng**.
  38/39 map có toạ độ cổng → leo tầng dựng được hoàn toàn từ dữ liệu tĩnh.
- Door index lên tầng **không cố định**: đa số `2`, nhưng có `1` (12925, 12927, 12944, 12950-12953),
  `3` (12930), `5` (12945-12947, 12955-12958). ⇒ **phải đọc từ `world_nav.json`, không hardcode.**
- Nhánh riêng `12941 → 12942 → 12943` (12941 có cổng ra 10997) — chưa rõ là nhánh khác của 2K hay
  event khác; đừng gộp vào tháp chính khi chưa xác minh.

### Tầng KHÔNG có cổng lên trong dữ liệu tĩnh — **giả thuyết, cần pcap xác nhận**
`12934, 12939, 12949, 12954` (và `12943` ở nhánh riêng) chỉ có **door 1 = đi xuống**, không có cổng
lên. Nghi là **tầng boss/chốt**: cổng lên chỉ hiện sau khi dọn sạch tầng → không nằm trong file tĩnh.
Chưa xác minh, **không được code như thể đã chắc**.

## Còn chờ pcap để chốt (KHÔNG được đoán)
- **Cách chạm quái**: tự lao vào hay phải bấm/tương tác?
- **Dấu hiệu "sạch quái tầng này"** để biết lúc nào được đi tiếp.
- **4 tầng chốt** ở trên: cổng lên xuất hiện thế nào sau khi clear?
- Mốc kết thúc / thất bại; có phải leo hết 12959 không.

(Đã tự trả lời được nhờ dữ liệu tĩnh: chuyển tầng bằng cổng thường + door index; map id từng tầng;
số tầng ≈ 38.)

Capture cần: từ lúc chọn event, qua cổng vào, **trọn 3 tầng liên tiếp** (2 tầng chưa đủ thấy quy
luật lặp), và nếu tiện thì cả lúc kết thúc/thoát ra. Đặt tên file có `2k` hoặc `nhikieu`
(repo đã có `ts_event.pcap` chỉ chứa đoạn vào map).

> Theo lệ repo: **giữ pcap tới khi tính năng hết bug**; xác nhận điều mới thì cập nhật
> `KNOWLEDGE.md`.
