# Phó bản tổ đội (ô 5 nhiệm vụ ngày)

Bốn bậc: **lv20 / lv50 / lv80 / lv110** (`TEAM_DUNGEON_LEVELS` trong `bot/config.py`, map
`TEAM_DUNGEONS` trong `bot/client.py`). Bật/tắt từng bậc bằng tick trong GUI (`team_dungeons`).

Leader tạo phòng và mời, member auto-accept rồi ready. Mã liên quan:
`run_party_digioi.py::_run_auto_team_dungeons_if_needed` / `_handle_auto_team_dungeon`,
`bot/client.py::do_team_dungeon`.

## Yêu cầu cấp — bỏ qua bậc không đủ cấp

> **PB lvN cần nhân vật cấp ≥ N.** Có bất kỳ acc nào trong party chưa đủ → **bỏ qua bậc đó**
> (chốt 02/09/2026).

Server không cho acc dưới cấp **ready** trong phòng. Bot trước đây không biết điều đó nên cứ tạo
phòng rồi chờ, và mỗi chu kỳ đều kết thúc y hệt nhau:

```
23:34:50 [qv801] (LEADER) === PHO BAN TO DOI LV80: tao + moi 4 member ===
23:35:36 [qv801] (LEADER) lv80 member ready 0/4 sau 40.1s -> HUY phong, relogin ca party
23:42:09 [qv801] (LEADER) === PHO BAN TO DOI LV80: tao + moi 4 member ===
23:42:55 [qv801] (LEADER) lv80 member ready 0/4 sau 40.1s -> HUY phong, relogin ca party
```

Party 19 (server quan_vu) cả 5 acc mới **lv68**, tick PB80 đang bật → lặp vô hạn: 40s chờ + relogin
cả party, mỗi chu kỳ.

**Cách làm:** mỗi acc báo `char_level` vào `st["char_level_by"]` tại đúng chỗ đã báo
`team_dungeon_done_by` (cùng một điểm đồng bộ, không thêm barrier mới). Leader gọi `_thieu_level()`
**trước khi tạo phòng**; thiếu thì log rõ acc nào cấp bao nhiêu, đánh dấu bậc đó `"done"` để member
không chờ mãi, rồi đi tiếp.

Acc **chưa đọc được cấp** (chưa có gói `0x05`) thì không tính là thiếu — thả cho thử còn hơn bỏ oan
một bậc đang làm được.

## PB hỏng không được làm mất ô 1

Trong mode `digioi_train`, `do_daily_dungeon()` (**ô 1** — phó bản solo 2 lượt) chỉ được gọi ở
**đúng một chỗ**: khối bàn giao hết Dì Giới trong `_finish_digioi_train_after_dg`. Khối đó từng có:

```python
if not _run_auto_team_dungeons_if_needed(...):
    log.warning("pho ban to doi khong xong -> VAN chuyen sang pha TRAIN")
    _dt["relogin_train"] = True
    return True          # ← thoát ở đây
if do_daily:
    c.do_daily_dungeon()          # ← ô 1, không bao giờ tới
    c.claim_daily_quests(heavy=True)
```

Nên **phó bản tổ đội hỏng thì mất luôn phó bản solo** — hai việc không liên quan gì nhau. Pha train
không vá lại được vì `_do_startup_daily` chỉ gọi `claim_daily_quests`, **không** gọi
`do_daily_dungeon`.

Đo được cuối ngày 02/09: 6 acc (`quan808/809/810`, `qv801/802`, `dt803`) dừng ở `o xong=[2..9]` —
đủ 8/9, thiếu đúng ô 1.

Sửa: bỏ `return` sớm, để khối `if do_daily:` chạy rồi mới bàn giao sang train. `relogin_train` vẫn
được đặt trước khi `return True` nên việc chuyển pha không đổi.
