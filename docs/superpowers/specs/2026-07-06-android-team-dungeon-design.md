# Android: Phó bản tổ đội (team dungeon o5) - Thiết kế

> Sub-project #3 (cuối cùng trong thứ tự 4→1→2→3): #4 auto-claim (xong), #1 Dị Giới (xong), #2 train
> mode (xong), #3 phó bản tổ đội - đây.

## Mục tiêu

Port nguyên văn cơ chế phó bản tổ đội (o5, lv20) từ `run_party_digioi.py`'s `_handle_o5_team` sang
Android: khi Party bật "Làm nhiệm vụ hàng ngày" (đã nối logic ở sub-project #2) và CẢ party chưa
làm phó bản tổ đội hôm đó, leader tự tạo phó bản, mời member theo entity, chờ ready thật, đánh 4
trận theo kịch bản đã ghi sẵn (`do_team_dungeon_lv20`, đã có sẵn trong `client.py` từ Task 3, chưa
từng được gọi).

## Nguyên tắc: PORT NGUYÊN VĂN, chỉ đổi khoá pidx→party_name

`do_team_dungeon_lv20`/`_do_team_dungeon_lv20_inner`/`_DUNGEON_READY`/`dungeon_ready_count`/
`reset_dungeon_ready`/hook `_o5_team_fn` đã có sẵn NGUYÊN VẸN trong
`android/app/src/main/python/train_bot/client.py` (Task 3, chưa từng được gọi) - **KHÔNG sửa
`client.py`**. Chỉ cần port `_handle_o5_team` (hàm điều phối ở tầng `train_runner.py`, tương đương
PC's `run_party_digioi.py`) + set hook.

## Kiến trúc

### `party_state.py` - thêm 2 field còn thiếu
`o5_done_by` (dict username→bool: acc đó đã xong o5 hôm nay chưa) và `o5_state`
("idle"|"running"|"done") - mirror PC's `_pstate` field tương ứng, thêm vào dict trả về của
`_pstate()`.

### `train_runner.py` - `_handle_o5_team` + set hook

Trong `_do_daily_if_enabled` (đã có từ #2), TRƯỚC khi gọi `c.claim_daily_quests(heavy=True)`, set:
```python
c._o5_team_fn = lambda o5d: _handle_o5_team(c, st, username, party_name, is_leader, should_stop, o5d)
```
(chỉ áp dụng khi có `party_name`/`st` - tức trong `_run_party_digioi_once`/`_run_party_train_once`,
KHÔNG áp dụng cho `run_train`/`_run_digioi_solo_once` vì không có party thật để mời).

Port `_handle_o5_team` nguyên văn từ `run_party_digioi.py:1405-1510`:
- Ghi nhận acc này đã báo cáo o5 xong/chưa vào `st["o5_done_by"]`.
- Không có leader (`has_leader=False`) → bỏ qua ngay (mirror PC, tránh treo vô ích).
- Member: chờ vô hạn tới khi `o5_state` chuyển "done" (leader đánh xong, thành công hay fail đều
  vậy), xử lý ca "đồng đội rớt giữa lúc đánh" bằng `relogin()`.
- Leader: chờ CẢ party report o5 xong/chưa → nếu TẤT CẢ đều chưa xong → tạo phó bản, mời theo
  entity, chờ ready thật, gọi `do_team_dungeon_lv20()`, claim bù `claim_daily_quests(heavy=False)`
  sau khi xong, xử lý ca đồng đội rớt giữa chừng, bump `reform_gen` để cơ chế reform có sẵn (từ #2)
  tự động gom lại party sau khi phó bản giải tán.

## Testing
Test dispatch/state (party_state field mới, hook được set đúng) không cần tài khoản thật - mirror
các sub-project trước. Việc đánh phó bản thật cần test thủ công.

## Không làm trong sub-project này
- Không làm các level phó bản khác (lv30/40...) - PC cũng chưa có, chỉ có lv20.
- Không thêm UI/toggle riêng cho tính năng này - hoàn toàn tự động kèm "Làm nhiệm vụ hàng ngày",
  khớp PC.
