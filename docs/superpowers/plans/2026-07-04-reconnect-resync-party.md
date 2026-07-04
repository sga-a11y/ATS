# Plan: Auto-reconnect + resync party khi rớt mạng

## Bối cảnh / lỗ hổng hiện tại
Game hay rớt kết nối. Khi `c.running=False` (server drop / socket chết):
- Mọi vòng trong `run_account` đều `if not c.running: return` → **luồng account thoát = nick chết**.
- Không có vòng reconnect giữa phiên. Log thực tế: *"PARTY 2 DA THOAT HET vi leader MAT KET NOI"*.
- Đã có: login retry 6 lần (chỉ lúc đầu), `relogin()` (resync khi kẹt bãi, KHÔNG phải do rớt).
- Đã có scaffold điều phối: `_pstate` với `reform_gen`, `leader_gone`, `member_maps`, `rally_point`, sync kênh (events), `_do_reform`.

## Yêu cầu (chốt với user)
**Gate chung:** CHỈ reconnect nếu party **có bot-leader**. Không có bot-leader → nick rớt **tiễn luôn** (giữ hành vi cũ), các nick khác về chế độ chờ party tay.

**Chờ vô hạn** tới khi đủ party mới đánh tiếp. Reconnect thử **vô hạn** (chỉ dừng khi GUI Stop). Nhiều đứa rớt cùng lúc → chờ tất cả về.

**3 case theo mode:**

1. **TRAIN** (đang ở map train): thấy có đứa rớt →
   - Cả party chạy ra `rally_point` (safe gần bãi) ngừng đánh/lòng vòng.
   - **GIẢI TÁN party** (đang trong party không đổi kênh được → phải tan mới sync kênh).
   - Chờ (vô hạn) tới khi nick rớt login lại xong.
   - **Đủ party → CHECK cùng map train TRƯỚC:**
     - **Cùng map** → sync kênh → lập lại party → pull lại spot.
     - **Khác map** → reform bình thường (về thành: reform tự lo sync kênh + party + route lại). KHÔNG sync kênh tại chỗ (vô nghĩa khi khác map).

2. **DỊ GIỚI**: thấy có đứa rớt →
   - Leader **đứng yên** (ngừng lòng vòng), **giải tán party**, chờ.
   - Nick rớt về xong → **cả lũ restart flow từ đầu**: vào dị giới nếu đang ở ngoài → sync kênh → lập party → chạy lòng vòng.

3. **TEAM DUNGEON** (đang check quest / đánh phó bản tổ đội) mà có đứa rớt →
   - **Relogin CẢ party** (tất cả nick), để khi login lại mọi nick bị **đẩy ra ngoài dungeon** → mới chạy tiếp được (1 đứa kẹt trong dungeon = cả lũ tắc).
   - Sau khi tất cả ra ngoài + login lại → về flow bình thường (sync kênh, party, chạy tiếp).

## Thiết kế

### Shared state thêm vào `_pstate`
- `reconnecting: set()` — username đang rớt/đang login lại.
- `disc_gen: int` — +1 mỗi lần có đứa rớt (để các nick khác phát hiện nhanh, giống `reform_gen`).
- `disc_lock` hoặc dùng `lock` sẵn có để bảo vệ `reconnecting`.
- (tuỳ) `force_relogin_all: Event` — case 3: leader ra lệnh cả party relogin.

### Phát hiện disconnect
- Nick tự phát hiện: trong vòng reconnect, khi `not c.running and not _stopped()` → tự `reconnecting.add(self)` + `disc_gen += 1` TRƯỚC khi login lại; login + resync xong → `reconnecting.discard(self)`.
- Nick khác phát hiện: watch `disc_gen`/`reconnecting` trong vòng keepalive (giống cách watch `reform_gen` hiện có).
- (Phòng hờ) nick rớt "đột tử" không kịp add: leader có thể suy ra từ `member_maps` heartbeat cũ / thread `is_alive` — cân nhắc ở stage sau nếu cần.

### Vòng reconnect (bọc `run_account`)
- Tách phần "login + main loop" thành thân có thể lặp. Khi thoát vì `not c.running` mà `not _stopped()` **và** `has_leader`:
  - `reconnecting.add(username)` + `disc_gen += 1`.
  - backoff (vd 5s, tăng dần tới trần ~30s), `login()` + `connect()` + chờ vào world.
  - Vào world xong → resync (kênh/party do flow bên dưới lo) → `reconnecting.discard` khi party đủ lại.
  - Lặp vô hạn tới khi được (hoặc GUI Stop).
- `not has_leader` → không reconnect, `return` (chết như cũ).

### Hook vào từng mode
- **TRAIN**: trong keepalive, nếu `reconnecting` ≠ rỗng và `train_on_map` → chạy ra `rally_point` + giải tán party + `barrier` chờ `reconnecting` rỗng → rồi đi nhánh reform sẵn có (sync kênh → lập party → pull spot / route).
- **DỊ GIỚI**: leader thấy `reconnecting` ≠ rỗng → dừng vòng lòng vòng, giải tán, chờ rỗng → nhảy về đầu flow digioi.
- **TEAM DUNGEON**: khi phát hiện rớt trong lúc dungeon (barrier `dungeon_done` / `o5` đang chạy) → leader set `force_relogin_all` → mọi nick `c.close()` + vào vòng reconnect → tất cả ra ngoài dungeon → flow tiếp.

## Rủi ro
- Đụng lõi điều phối 5 luồng (dễ deadlock/kẹt barrier). Phải test kỹ từng mode.
- `reconnecting` phải được dọn đúng mọi nhánh thoát (kể cả lỗi) — tránh party chờ vĩnh viễn một nick đã bỏ.
- Sync kênh yêu cầu KHÔNG trong party — đảm bảo giải tán trước khi sync ở cả 3 case.

## Triển khai theo stage (mỗi stage test riêng)
1. **Vòng reconnect cơ bản** (1 nick rớt tự login lại, chưa lo party) + gate has_leader.
2. **Tín hiệu disc_gen/reconnecting** + nick khác phát hiện.
3. **TRAIN**: rally + disband + chờ + reform.
4. **DỊ GIỚI**: leader dừng + disband + chờ + restart flow.
5. **TEAM DUNGEON**: force_relogin_all.
6. Rà edge: nhiều đứa rớt, rớt ngay lúc reform, GUI Stop giữa chờ, dọn `reconnecting` mọi nhánh.

## Chưa quyết (default tạm, confirm khi code)
- Backoff reconnect: 5s→30s? Vô hạn lần.
- Case 3 phát hiện "đang trong team dungeon": mốc nào chính xác (o5_state=="running" / dungeon barrier chưa xong)? — xác định lúc đọc kỹ đoạn dungeon.
