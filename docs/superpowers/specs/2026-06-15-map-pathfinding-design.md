# Hệ thống tìm đường liên map (auto đi tới bãi quái)

Ngày: 2026-06-15
Trạng thái: Đã duyệt thiết kế, chờ viết plan.

## ⚑ REVISED (2026-06-15, sau khi chốt với user) — Route replay per train map
KHÔNG cần graph cổng toàn game + BFS. Mỗi train map chỉ cần **1 route replay định sẵn**
(capture 1 lần): `teleport thành → [move waypoints] → gate(idx) → [waypoints] → gate(idx) → tới train map`.
Bot **CHỈ leader replay; member tự bị kéo theo**.

**Kịch bản train mode:**
1. Check cả party đã ở train map chưa → ở hết → chạy safe + lập party + train (như cũ).
2. Có acc lạc map → **tất cả teleport về thành** → lập party + set quân sư →
   **leader follow_route(train_map)** tới train map (member tự theo) → train.

**Dữ liệu `train_routes.json`:**
```json
{ "routes": { "12831": {
    "name":"Rung Noi Huynh", "from_city":12011, "city_flag":3, "dest_map":12831,
    "steps":[ {"gate":1,"x":1250,"y":930}, {"move":[886,1567]}, ...,
              {"gate":18,"x":1110,"y":1830} ] } } }
```
- step `{"move":[x,y]}` = đi 1 bước; step `{"gate":idx,"x","y"}` = move tới (x,y) rồi gửi 0x14 04/08[idx].
- Seed từ capture qua `tools/parse_gate_capture.py` (đã rút route 12831).
- `train_routes.json` thay vai trò `map_gates.json`/BFS cho kịch bản thực dụng này.
  (pathfind.py/BFS giữ lại cho tương lai đa-route, hiện chưa dùng.)

**follow_route(route)** (client.py): teleport(from_city, city_flag); với mỗi step:
move → move_to+wait; gate → move_to(x,y) + 0x14 04/08[idx] + 0c0100 + 0x14 0600 + chờ.
Dừng nếu STOP / current_map==dest_map.

---

## Mục tiêu (gốc)
Cho bot **tự đi từ map hiện tại tới map train** (rồi ra bãi quái), thay vì yêu cầu nhân vật
phải được "park" sẵn trên map train lúc login. Cơ chế giống thoát Dị Giới: đi tới **cổng
dịch chuyển** → sang map khác → lặp tới khi tới đích.

Giải luôn bài cũ: train mode khi login **sai map** hiện đang "HỦY CẢ PARTY"; sau tính năng này
sẽ **tự đi tới train map** rồi train.

## Bối cảnh khảo sát (đã làm)
- Game `com.vtcmobile.gz06` (VTC, Unity IL2CPP + Lua, logic ở Lua **đã mã hóa**).
- Data tables nằm ở `/sdcard/Android/data/<pkg>/files/Data/*.dat` (binary).
- **`Warp_C.dat` đã decode sạch**: header 4B (số record=41) + mỗi record 16B:
  `[warp_id u32][srcMap u16][dstMap u16][x u32][y u32]`.
  Vd: 12001 Trác Quan → 11804 @(310,1530); 12061 Ng.Thành → 11806 @(160,900).
- File đã pull về `gamedata/` (Warp_C.dat, DoorGroupData.dat, Npc_C.dat, SceneSet_C.dat,
  CityEx.dat) + `gamedata/Lua/` (767 file, mã hóa) + `il2cpp/out/` (dump.cs ...).
- Các bảng khác (DoorGroupData, Npc_C, SceneSet) binary biến độ dài → **chưa decode** (cần
  schema từ Lua đã mã hóa). → Chọn hướng **hybrid**: dùng Warp_C + capture cổng theo nhu cầu.

## Phạm vi (hybrid - YAGNI)
- KHÔNG giải mã Lua, KHÔNG RE toàn bộ bảng game ở giai đoạn này.
- Dùng Warp_C (đã decode) seed các cổng thành↔overworld.
- Bổ sung cổng các map THỰC SỰ dùng bằng capture (giống cách làm Dị Giới).

## Dữ liệu: TÁCH 2 file (tránh làm loạn train map list)
`train_maps.json` chỉ chứa map TRAIN (có quái) cho gọn — nếu nhét cả map trung gian (chỉ
có cổng, không quái) vào sẽ làm rối dropdown/Edit Map. Nên đồ thị cổng để file riêng.

**`train_maps.json` (GIỮ NGUYÊN):** chỉ map train — `safe` (thêm tay) + `mobs`.
```json
"12831": { "name": "Rừng Nội Huỳnh 28-30", "safe": [[470,1210]], "mobs": [[590,870],[1070,1850]] }
```

**`map_gates.json` (FILE MỚI):** đồ thị cổng TẤT CẢ map (gồm map trung gian).
```json
{ "maps": {
    "12011": { "name": "Cu Loc", "gates": [ {"x":1250, "y":930, "to":11807, "idx":1} ] },
    "11807": { "name": "Overworld...", "gates": [ {"x":1110, "y":1830, "to":12831, "idx":18} ] }
}}
```
- `to` = map_id đích; `idx` = số cổng cho gói `0x14` (BẮT BUỘC). Đồ thị CÓ HƯỚNG.
- Map không có trong file → BFS không ra đường (fallback cũ).
- Pathfinding đi bằng `map_gates.json`; tới train map thì lấy `safe`/`mobs` từ `train_maps.json`.

## Cơ chế đi qua cổng (ĐÃ XÁC NHẬN từ capture gate.pcap)
Cổng map thường dùng GIỐNG thoát Dị Giới — gói `0x14`:
```
move_to(x, y)                    # đi tới gần cổng
C2S 0x14 04 00 [idx] 00          # áp sát cổng idx
C2S 0x14 08 00 [idx] 00          # VÀO cổng -> server đổi map
C2S 0x0c 0100  +  0x14 0600      # xác nhận/load
-> chờ current_map == to
```
- `idx` lấy từ capture (gói `0x14 0800[idx]`); toạ độ lấy từ gói `0x06 move` ngay trước đó.
- DoorGroupData.dat (đã crack: map→[(linked,idx)]) CHỈ cho idx+graph, KHÔNG có toạ độ.
  Toạ độ cổng nằm trong scene collision (Ground.mmg) — không decode được từ data tables.
  → toạ độ + idx + dest đều lấy từ **capture** (parser tự rút).

## Thành phần

### 1. Loader (bot/config.py)
- `_load_train_maps()` GIỮ NGUYÊN (chỉ safe + mobs).
- Thêm `_load_map_gates()` đọc `map_gates.json` → `MAP_GATES[map_id] = [(x,y,to), ...]`.

### 2. Đồ thị + BFS (module mới `bot/pathfind.py`)
- Đồ thị = `MAP_GATES` (đọc từ `map_gates.json`).
- `find_path(src_map, dst_map)` → list chặng `[(gate_x, gate_y, next_map), ...]` (BFS,
  đường ngắn nhất theo số cổng). Trả `[]` nếu đã ở đích; `None` nếu không có đường.

### 3. Đi qua cổng (bot/client.py)
- `walk_through_gate(x, y, expected_map, timeout)`:
  đi từng bước `move_to(x,y)` (bật `flee_mode` né quái dọc đường, giống `navigate_to`),
  chờ `current_map == expected_map`. Lặp tới timeout.
  **Cơ chế chính xác (tự đổi map khi giẫm cổng vs cần gói trigger như Dị Giới `0x14`)
  sẽ chốt bằng 1 capture lúc implement** — đây là rủi ro chính, xử lý trước tiên.
- `go_to_map(target_map)`:
  `find_path(current_map, target)` → với mỗi chặng `walk_through_gate(...)`; lỗi 1 chặng →
  dừng + log rõ (map kẹt). Tôn trọng STOP (`self.running`) như `go_to_town`/`navigate_to`.

### 4. Tích hợp (run_party_digioi.py)
Train mode, nhánh `self_map_ok == False`:
- Nếu `find_path(login_map, sc)` có đường → `go_to_map(sc)`; tới nơi (current_map==sc) thì
  tiếp tục flow train bình thường (chạy safe → dungeon → lập party → ra bãi quái).
- Không có đường → giữ hành vi cũ (log rõ "không có đường tới train map, cần park tay").

## Luồng dữ liệu
login → biết `current_map` → (train mode, sai map) → `go_to_map(sc)`
→ BFS ra chuỗi cổng → đi từng cổng (flee dọc đường) → tới `sc` → `navigate_to(safe)` → train.

## Xử lý lỗi
- Cổng đi mãi không đổi map (timeout) → log "kẹt ở cổng (x,y) map M, không tới được N" → dừng.
- Bị quái chặn (battle) → flee, đi tiếp (như navigate_to, cộng dồn bước).
- STOP giữa chừng → dừng ngay (check `self.running`).
- Không có `gates` cho map → không tìm được đường → fallback hành vi cũ.

## Kiểm thử
- Unit: `find_path` trên đồ thị mẫu (thẳng, rẽ nhánh, không đường, đã ở đích, vòng lặp).
- Loader: đọc `gates` đúng, map thiếu `gates` → rỗng.
- Tích hợp (tay): 1 acc login sai map → bot tự đi tới train map (sau khi có capture cổng).

## Phụ thuộc / rủi ro
- **Rủi ro #1:** cơ chế đi qua cổng map thường — phải capture xác nhận TRƯỚC khi tin `walk_through_gate`.
- Đồ thị thưa: Warp_C chỉ cho 1 hop thành→overworld; tới train map cần capture thêm cổng
  trung gian. Hybrid chấp nhận bổ sung dần theo map đang dùng.

## Edit Map (TrainMapEditor) — giữ nguyên
- Vẫn cho sửa/thêm/xóa **safe + mobs** như hiện tại (mob chưa lấy được từ data game).
- `gates` ở file RIÊNG `map_gates.json` (code import Warp_C / capture đổ vào) — KHÔNG đụng Edit Map.
- Khi nào decode được Npc_C (lấy mob tự động) thì mới tính rút editor còn safe-only.

## Ngoài phạm vi (sau này, nếu cần)
- Giải mã Lua (Frida hook) để lấy trọn schema + tự sinh toàn bộ gates/mobs/safe.
- Decode DoorGroupData/Npc_C để auto-fill đồ thị toàn game.
