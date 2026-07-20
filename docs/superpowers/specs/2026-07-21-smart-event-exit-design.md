# Smart Event Exit Design

## Mục tiêu

Thay route thoát event dựa trên waypoint capture bằng route tự dựng từ ID map và vị trí hiện tại. Trường hợp đầu tiên là map 40 NPC `10991` thoát ra map `12003`, nhưng cơ chế áp dụng cho mọi event có `exit.out_map` và có dữ liệu trong `world_nav.json`/`Ground.mmg`.

## Nguyên nhân lỗi

`GameClient.exit_event` hiện replay `exit.steps`, gửi cả movement flag từ capture và tự gán `self.pos` theo waypoint. Sau battle, vị trí thật có thể khác route capture; dead-reckoning tiếp tục từ tọa độ giả làm nhân vật đi sai hoặc không tới cổng.

## Thiết kế

### Đồng bộ vị trí

Trước khi dựng route, client phải lấy một tọa độ mới do server xác nhận:

1. Gửi request scene state `C2S 0x0c 0100` và chờ một `S2C 0x03` self-spawn mới.
2. Nếu request không tạo self-spawn trong thời gian giới hạn, gọi `relogin()`; login mới luôn chờ `S2C 0x03` và đặt lại `self.pos`.
3. Chỉ tiếp tục khi `current_map` vẫn là source map và `self.pos` khác `None`.

Client dùng một generation tăng mỗi lần parse thành công tọa độ self-spawn `0x03`, tránh nhầm dữ liệu cũ với phản hồi mới.

### Dựng và chạy route

`exit_event` chỉ đọc `ev.exit.out_map`, không đọc `ev.exit.steps`:

1. `source_map = current_map` sau resync.
2. Gọi `build_smart_scene_route(source_map, out_map, safe=None)`; router dùng graph `world_nav.json` để chọn đúng cổng và `Ground.mmg` để A* từ `self.pos` tới tâm cổng.
3. Chạy route bằng executor smart-route hiện có, chờ server xác nhận đổi map sau từng cổng.
4. Thành công chỉ khi `current_map == out_map`.

Không giữ waypoint capture làm fallback. Nếu thiếu Ground map, graph/cổng, tọa độ hoặc A* không tìm được đường, hàm trả `False` và log rõ tầng thất bại.

### Cấu hình

`events.json` của 40 NPC giữ `exit.out_map = 12003` nhưng xóa `exit.steps` và ghi chú capture cũ. Việc chọn cổng/tọa độ hoàn toàn đến từ dữ liệu map.

### PC/APK

Sửa source PC trước, sau đó chạy `tools/sync_apk_python.py` để client/coordinator và `events.json` Android đồng bộ. Không build cho tới khi người dùng test bản dev.

## Kiểm thử

- Self-spawn `0x03` tăng position generation và cập nhật tọa độ.
- Resync ưu tiên request scene state; timeout mới relogin.
- `exit_event` truyền đúng source map, out map và vị trí server mới vào smart scene router.
- Thay đổi vị trí bắt đầu vẫn tạo route A* hợp lệ tới cổng.
- `exit.steps` không còn ảnh hưởng route.
- Thiếu route hoặc relogin thất bại trả `False`, không replay capture.
- PC/APK parity và các test smart-route hiện có tiếp tục pass.
