# 40 NPC Party Battle Loop Design

## Mục tiêu

Mở rộng mode event `npc_40` hiện có để party có bot leader tự lập đủ đội, đi đến NPC tại `(910, 290)`, vào trận và tiếp tục đánh. Party không có bot leader giữ nguyên hành vi đứng yên chờ điều khiển tay. Không build trong đợt thay đổi này; người dùng sẽ chạy bản dev trước.

## Dữ liệu packet đã xác nhận

- Mở NPC: C2S `0x20 020008`, sau đó `0x14 01000500`.
- Xác nhận **Có**: C2S `0x14 09001e`.
- Xác nhận **Không**: C2S `0x14 09001f`.
- Tiến dialog: C2S `0x14 0600`.
- Bắt đầu battle: S2C opcode `0x34`.
- NPC hỏi lại sau trận: S2C `0x41 0a0001`, tiếp theo dialog `0x14 0100...`.
- Đóng vòng sau khi chọn Không: S2C `0x14 080029`, cuối cùng `0x41 0a0000`.

Hai capture nguồn là `captures/40npc_loop_20260720.pcap` và `captures/40npc_choose_no_20260720.pcap`.

## Thiết kế

### Cấu hình

`events.json` bổ sung riêng cho `npc_40`:

```json
"party_battle": {
  "kind": "npc_repeat",
  "point": [910, 290]
}
```

Không đưa raw packet vào JSON vì protocol chỉ được xác nhận cho 40 NPC và chưa có event thứ hai dùng lại.

### Client

Client theo dõi hai bộ đếm tăng đơn điệu:

- `_battle_start_seq`: tăng khi nhận S2C `0x34`.
- `_npc40_prompt_seq`: tăng khi nhận đúng S2C `0x41 0a0001`.

Leader chạy một worker nền để keepalive và xử lý disconnect vẫn hoạt động:

1. Đi đến `(910, 290)` và gửi `combat_ready`.
2. Mở NPC theo capture, tiến dialog đến khi thấy `_battle_start_seq` mới.
3. Chờ `_npc40_prompt_seq` mới sau trận.
4. Nếu đội thua, gửi lựa chọn Không và đóng dialog rồi dừng worker.
5. Nếu đội chưa thua, gửi lựa chọn Có và tiến dialog đến battle tiếp theo.

Không spam packet mù: mỗi pha có giới hạn số lần tiến dialog và dừng ngay khi bộ đếm server tăng.

### Nhận biết thua

Dialog sau thắng và thua giống nhau. Tại thời điểm nhận prompt sau trận, client chụp trạng thái cuối của toàn bộ char/pet phía party đã biết từ battle stats. Nếu đã thấy ít nhất một unit hợp lệ và không còn unit nào có HP lớn hơn 0, trận được coi là thua. Đây là heuristic ban đầu theo yêu cầu “cứ xử lý, lỗi thì fix”; log phải in rõ số unit sống/tổng để chỉnh tiếp từ dữ liệu thật.

### Điều phối party

- Có bot leader và `party_battle.kind == npc_repeat`: dùng pipeline sync kênh, đợi đủ member, mời đủ party và đặt quân sư đang có. Chỉ leader gửi packet NPC; member chỉ auto combat.
- Không có bot leader: giữ nguyên nhánh event đứng yên hiện tại.
- Leader chỉ khởi động worker khi số member đã join bằng đúng số member cấu hình.

### Disconnect giữa trận

Khi một account rớt lúc vòng 40 NPC đang hoạt động:

1. Supervisor tăng generation disconnect thật đúng một lần và xóa readiness/join state cũ.
2. Các account còn sống đóng phiên hiện tại với cờ “forced party relogin”; các lần đóng cưỡng bức này không tăng thêm generation.
3. Supervisor đăng nhập lại toàn bộ account.
4. Mỗi account vào lại event bằng flow có sẵn, sync kênh, lập đủ party; leader khởi động lại từ bước mở NPC.

Như vậy trận dở bị bỏ và party đánh lại sau khi đủ đội.

## PC/APK và kiểm thử

- Code gốc sửa ở PC, sau đó chạy `tools/sync_apk_python.py` để đồng bộ APK.
- Test protocol từ hai capture, state machine Có/Không, heuristic thua, policy có/không leader, forced relogin không nhân generation và parity PC/APK.
- Cập nhật `KNOWLEDGE.md` với packet đã xác nhận.
