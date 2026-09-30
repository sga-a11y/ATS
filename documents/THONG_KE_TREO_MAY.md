# Thống kê treo máy

User chốt 29/09. Chép logic `MachineBox.Statistics` của client (`_lua_dec/Logic/MachineBox.lua:1049`).

## Phạm vi
- Start party (phiên mới) → thống kê MỚI cho mọi acc trong party.
- Stop → đồng hồ dừng, số liệu **giữ** để xem trên GUI. Tắt app là mất (không cache file).
- Mất kết nối / relogin **không** reset (số liệu giữ ở `run_party_digioi.idle_stats`, không ở client).

## Điểm đếm (client → bot)
| Mục | Client | Bot |
|---|---|---|
| Thời gian | timer 1s khi bật Hộp Máy | từ lúc Start party tới lúc thread acc kết thúc hẳn |
| Số lần login | (client không có) | mỗi lần vào world thật, kể cả relogin |
| Số trận | `FightField.lua:457` | tracker event `start` / nhánh 0x33 legacy lần đầu thấy quái |
| Số lần chết | `FightRoleController.lua:1634` (CHỈ char mình bị giết) | char VÀ pet ra trận, HP từ >0 xuống 0 - tách riêng char/pet |
| EXP | `Role.SetAttribute` + `Breakthrough` (CHỈ char) | gói `0x02/0a` câu 40476, gộp theo tên; tên trùng nhân vật = char, còn lại = pet |
| Vật phẩm nhận | `Item.lua:673/682`, bỏ id 23024 (đồ hỏng) | `0x17/08` phần số lượng tăng, bỏ 23024 |
| Vật phẩm dùng | `SedUseItem`/`Supply` | `0x17/09` (số lượng trong gói) |

Khác client: EXP lấy từ gói thông báo chứ không từ gói thuộc tính.

## Thêm 30/09 (user chốt)
Thứ tự chi tiết: thông số chung → **Daily quest** → **PB tổ đội** → EXP → vật phẩm.
- **Daily quest (x/9)**: ô bingo đã xong = `client._quest_cells` (server báo, không cache).
  Ô dạng đếm (vd ô9 đánh 50 trận) chỉ biết xong/chưa.
- **PB tổ đội**: LV20/50/80/110 theo `team_dungeon_remaining()` (0 = đã đánh ✅; `?` = chưa có mission-step).
- Đọc qua `GameClient.daily_status()`; `IdleStats.bind_client()` giữ weakref, Stop thì giữ lần đọc cuối.
- **EXP**: thêm số lần nhận + exp lần cuối: `[char] mamot: 38,070 (18 lần, lần cuối 555)`.

## UI (PC)
Tab party → nút **📊 Thống kê** (trước Check AGI). Cửa sổ kiểu Soi dame boss: mỗi acc một dòng
bên trái, chi tiết bên phải, tự cập nhật 2s khi còn acc chạy.

## UI (APK)
Hàng nút party: **📊 Thống kê** trước Check AGI → `IdleStatsDialog` (MainActivity.kt), cùng bố
cục với `LegionDmgDialog`: màn rộng chia trái/phải, màn hẹp danh sách → chạm xem chi tiết.
Gọi `idle_stats_report_json(pidx)` qua `BotForegroundService.idleStatsJson`.

## Code
`bot/idle_stats.py` · `GameClient._idle_on_fight/_idle_check_death` · `run_party_digioi.idle_stats_report`
· `gui.IdleStatsDialog`.
