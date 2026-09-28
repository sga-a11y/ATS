# ĐIỀU KHIỂN TỪ XA — nhắn tin riêng cho acc bot

User dùng một nick khác trong game **nhắn tin riêng (mật thoại)** cho một acc bot bất kỳ trong
party. Đúng người, đúng cú pháp thì bot làm theo.

## Lệnh

| Lệnh | Tác dụng |
|---|---|
| `off <phút>p` (vd `off 30p`, 1..600) | Bot nhắn lại `OK off 30p, quay lai luc HH:MM` → **cả party** logout → hết giờ tự login lại, chạy tiếp |

Chỉ có `off`: đã off rồi thì không còn ai nhận tin để ra lệnh `on`.

## Ai được ra lệnh

- Dùng lại whitelist có sẵn (ô "leaders"): **whitelist CHUNG + whitelist RIÊNG của party**
  (`config.leaders_for(pidx)`), trên cả PC lẫn APK. Không có UI mới.
- So tên **không phân biệt hoa/thường**, phải khớp nguyên tên (kể cả dấu).
- **Whitelist rỗng → không ai ra lệnh được** (khác nhận lời mời party: rỗng = nhận hết).
- Nick lạ hoặc sai cú pháp → bot im lặng, không trả lời (chỉ ghi log).

## Hành vi

- **Off cả party**: thiếu 1 acc thì party cũng không làm được gì.
- Hạn off lưu ở `remote_off.json` (cạnh exe/app): tắt/mở tool giữa chừng vẫn chờ đủ giờ.
- Hết hạn: login lần lượt, mỗi acc cách nhau 3s theo vị trí trong party, để tránh mã 90.
- User bấm **Stop** acc/party trên GUI → xoá hạn off; lần Start sau chạy ngay.
- Lệnh lặp lại khi party đang off → bỏ qua.

## Kỹ thuật

- Nhận: `S:002-003` → `GameClient._on_whisper` (`bot/client.py`), parse ở `bot/remote_cmd.py`.
- Gửi xác nhận: `C:002-003` → `GameClient.send_whisper`.
- Off party: `run_party_digioi._remote_off_party` → `_force_supervisor_reconnect` từng acc;
  `_run_account_supervised` chờ hết hạn ở đầu vòng lặp.
- Protocol lấy từ crack client, **chưa đối chiếu pcap**: mỗi tin riêng log gói thô
  (`TIN RIENG tu ... (raw ...)`) vào `party.log` để kiểm lại lần chạy thật đầu tiên.
