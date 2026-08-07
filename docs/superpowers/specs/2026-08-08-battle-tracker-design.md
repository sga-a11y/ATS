# Battle Tracker dựa trên protocol client thật

## Mục tiêu

Thay cơ chế battle hiện tại dựa trên suy đoán bằng state machine bám đúng Lua client thật. Engine phải dựng được roster hai phe, lượt, hành động, HP/SP, trạng thái, thay đổi vị trí, quân tiếp viện và kết thúc trận; đồng thời cung cấp dữ liệu đúng cho combat AI và log đọc được theo từng lượt.

PC và APK dùng cùng logic Python. Các file tương ứng phải giữ đồng bộ byte-for-byte sau khi triển khai.

## Nguồn sự thật

- Lua client đã giải mã: `Common/protocal.lua`, `Logic/FightManager.lua`, `Logic/FightField.lua`, `Controller/FightRoleController.lua`.
- Capture chính: `captures/teamdungeon_lv110_mumu12_20260805_202150.pcap`.
- Packet server là nguồn trạng thái có thẩm quyền. Không suy kết trận từ dialog và không coi status packet là danh sách hành động.

## Kiến trúc

Tạo một `BattleTracker` chịu trách nhiệm duy nhất về lifecycle battle và dữ liệu trong trận. `GameClient` chuyển các opcode battle vào tracker. `BattleState` giữ API tương thích cho `combat.py`, nhưng các view như `enemy_hp`, `enemy_slots`, `allies`, trạng thái bảo vệ/khống chế được sinh từ tracker thay vì được cập nhật bởi nhiều heuristic độc lập.

Tracker có các khái niệm:

- `generation`: tăng đúng một lần khi nhận `0x0B/FA`.
- `turn`: tăng khi nhận `0x34/01`.
- `units[(row, col)]`: roster hiện tại của cả hai phe.
- `pending_actions[(source_row, source_col)]`: action đã gửi nhưng chưa ACK.
- `statuses[(row, col)][status_kind]`: sáu nhóm trạng thái cơ bản.
- `buffs[(row, col)]`: buff thường và extra buff có lượt/lớp.
- `active`: chỉ true giữa create và end của chính người chơi.

Mỗi unit lưu tối thiểu role kind, role/master ID, template ID, tên hiển thị, phe, vị trí, HP/SP hiện tại và tối đa, level, trạng thái sống/chết/bay/rời trận.

## Lifecycle và opcode

### Tạo trận

`0x0B/FA` là mốc tạo trận duy nhất. Tracker xóa state trận cũ, tăng generation, nhận terrain/fight number và bắt đầu log trận.

`0x0B/0A` cập nhật war style, round ban đầu và giới hạn trận.

`0x0B/05` parse `RoleAppear` theo fixed header của client để tạo hoặc thay unit tại đúng `(row, col)`. Header cung cấp role/master ID, template, vị trí, max/current HP/SP và level. Phần appearance biến độ dài chỉ được parse thêm khi đủ bằng chứng; thiếu tên người chơi thì dùng nhãn ổn định theo role ID, không đoán.

### Đồng bộ đầu lượt

`0x35/01` được xử lý như `RevRestoreStatus`: mỗi record cập nhật đúng một `status_kind`; `skill_id=0` chỉ xóa nhóm đó. Packet là incremental, không được xóa snapshot toàn cục.

`0x35/15` lưu buff kind, số lượt và value. `0x35/20` lưu extra buff gồm skill, level, weight, status ID/kind, lượt, lớp, caster, attribute và value.

`0x34/01` là mốc duy nhất mở lượt. Nó tăng turn, xóa ACK/pending của lượt trước, xác định char/pet do acc hiện tại điều khiển còn sống và không bị khóa hành động, rồi mới lên lịch quyết định. Không xóa roster, HP, trạng thái hoặc enemy slots tại đây.

`0x34/02` cộng SP quân sư cho các unit thuộc phe tương ứng và clamp theo max SP.

### Chọn và xác nhận hành động

Combat AI nhận danh sách unit điều khiển được từ roster/owner, không nhận “offer” từ `0x35/01`. Target hợp lệ lấy từ roster sống của hai phe và luật skill hiện có.

Sau khi gửi C2S `0x32/01`, tracker ghi pending theo source. S2C `0x35/05` ACK đúng `(row, col)` và đánh dấu unit đã hoàn tất chọn action. Không dùng timer 1,5 giây để tự mở khóa lượt. Nếu thiếu ACK, chỉ retry theo một timeout có generation/turn/source guard và không bao giờ gửi lại sau khi turn đổi hoặc trận kết thúc.

### Kết quả hành động

S2C `0x32/01` được parse đúng cấu trúc `RevAttackSkill`: attacker, skill, fight area, danh sách target, hit result, hit animation và danh sách attribute `{kind, value uint32, sign}`.

Với hit/thunder, giá trị thường là delta: sign 0 cộng, sign 1 trừ; kết quả được clamp về `[0, max]`. Miss/heart-eye không áp delta như hit. Attribute thuộc sáu nhóm trạng thái gọi cùng quy tắc `HandleStatus`; `0x35/01` ở ranh giới lượt vẫn là snapshot có thẩm quyền.

S2C `0x33/01` là cập nhật absolute hiếm: parse `isRevive` rồi các record `{row, col, attr_kind, value int32}`. Không đọc uint16 và không dùng scanner lệch byte.

### Thay đổi roster giữa trận

- `0x35/03`: unit bị flyout tại đúng ô.
- `0x0B/01`: unit rời trận, xóa trạng thái và không còn là target sống.
- `0x35/07`: chuyển unit từ ô nguồn sang ô đích, giải phóng ô đích như client.
- `0x35/14`: đổi body/template của unit.
- `0x0B/05`: unit mới xuất hiện hoặc thay unit cũ tại ô đó; PB110 dùng flow chung này thay vì chỉ vá riêng tên reinforcement.

### Kết thúc trận

`0x0B/00` chỉ kết thúc battle local khi role ID khớp chính acc (hoặc guard index tương ứng với context được chứng minh). `0x0B/01` tiếp tục dọn từng unit. Khi local battle kết thúc, hủy timer action, đóng generation, log kết quả cuối và phát callback cho event/dungeon.

Các `0x14/0700`, `0x14/0800` chỉ là dialog/event signal. Chúng không được thay đổi `BattleTracker.active`; mode event có thể dùng chúng sau khi tracker đã xác nhận end.

## Battle log

Log INFO theo format ổn định:

```text
[BATTLE g=12] START fight=2 style=...
[BATTLE g=12 t=3] TURN START alive ally=10 enemy=4
[BATTLE g=12 t=3] quanA/CHAR Băng Phong -> Trình Khoáng@(0,3): HIT HP 2104-428=1676; Seal=Băng Phong
[BATTLE g=12 t=3] ACK quanA/PET
[BATTLE g=12 t=3] FLYOUT Trình Khoáng@(0,3)
[BATTLE g=12 t=3] SPAWN Địch mới@(0,3) HP=3200/3200
[BATTLE g=12] END turns=5 ally_alive=8 enemy_alive=0
```

Một action nhiều target được log một dòng cho mỗi target. Status/buff thay đổi không đi kèm action vẫn có dòng riêng. Raw packet chỉ xuất ở DEBUG. Tên chưa biết dùng `role:<hex>` hoặc `npc:<id>` để không log sai danh tính.

## Tích hợp combat AI

Các quyết định hồi HP/SP, hồi sinh, điều kiện HP địch `>1500`, tránh cast trùng CC/protection, phá bảo vệ và chọn target đều đọc snapshot tracker của đúng generation/turn.

Giữ lớp tương thích trong giai đoạn đầu:

- `enemy_hp`: HP hiện tại từ roster địch.
- `enemy_slots`: vị trí địch còn sống.
- `allies`: unit phe mình, gồm char/pet.
- `protect_status`, `crowd_status`: view từ status map.
- `enemy_gen`: thay bằng revision của roster/HP trong cùng generation để guard dữ liệu cũ.

Không còn `available` tạo từ zero-status records. `_make_decisions` chỉ chạy một lần sau `0x34/01`, có guard `(generation, turn)` và chỉ gửi action cho source thuộc local acc.

## Đồng bộ battle giữa nhiều acc trong cùng party

Mỗi `GameClient` vẫn giữ tracker local cho dữ liệu nhận trên chính socket của acc đó, nhưng các acc cùng `party_idx` dùng chung một `PartyBattleCoordinator` trong process. Coordinator nhận semantic event đã parse hợp lệ, dựng canonical snapshot của trận và phân bổ target/action để các acc không chọn chồng lên nhau.

Coordinator không dùng một acc cố định làm nguồn và không chờ đủ toàn bộ acc ở hàng rào READY:

- Bản semantic event hợp lệ đến đầu tiên từ bất kỳ acc nào được dùng ngay. Acc bị chậm, đơ hoặc mất kết nối không khóa các acc còn lại.
- Gói thiếu hoặc parse lỗi không được mutate canonical state; bản hợp lệ đến sau từ acc khác vẫn được nhận.
- Event broadcast trùng được deduplicate theo ý nghĩa: action theo `(generation, turn, source, skill)`, status theo `(generation, turn, position, status_kind)`, ACK theo `(generation, turn, source)`, spawn/exit theo `(generation, role_id, position)`.
- Nếu các bản cùng semantic key mâu thuẫn, coordinator giữ state đang có, ghi WARNING một lần và dùng bản được nhiều socket độc lập xác nhận hơn khi có đủ bằng chứng; tuyệt đối không dừng cả lượt để chờ biểu quyết.
- `0x34/01` có payload giống nhau ở mọi lượt nên coordinator dùng phase state machine. Bản đầu tiên hợp lệ khi phase cho phép sẽ mở lượt kế; các bản từ socket khác chỉ xác nhận cùng lượt. `0x34` cũ đến muộn sau khi canonical turn đã tiến bị bỏ.

Coordinator có thể khóa canonical snapshot, tính plan và reserve target ngay khi acc đầu tiên nhận `0x34`. Tuy nhiên từng acc chỉ được gửi C2S action sau khi chính socket của acc đó đã nhận `0x34/01` khớp `(generation, turn)`. Ví dụ A nhận trước thì chỉ A gửi action của A; B nhận sau mới được lấy action đã reserve cho B và gửi. Nếu B nhận quá muộn khi canonical turn đã đổi, action cũ của B bị hủy.

Reservation nằm dưới một lock chung theo `(generation, turn)` và bao phủ CC, protection, hồi sinh, hồi HP/SP và phá bảo vệ. Nó chỉ ngăn các action không nên trùng; kịch bản chủ ý focus damage vẫn được phép cùng target. ACK và retry vẫn là state local của từng socket, có guard generation/turn/source.

Battle event chung chỉ log một lần từ coordinator theo dạng `[P19 BATTLE g=... t=...]`. Mỗi acc chỉ log các sự kiện riêng `DECISION`, `SEND`, `ACK` để còn chẩn đoán socket nào chậm hoặc mất gói. Các party khác nhau dùng coordinator khác nhau và không ảnh hưởng nhau.

## Tương thích event và lỗi mạng

- 40 NPC, PB20/50/80/110, Dị Giới và train cùng dùng một tracker.
- Callback battle end thay thế các chỗ đang suy luận từ `0x14`; dialog flow vẫn giữ riêng.
- Relogin giữa trận nhận `0x0B/FA` và roster hiện hành thì dựng lại generation mới từ server, không nối state cũ.
- Packet thiếu/truncated bị bỏ qua có log DEBUG/WARNING; không mutate state một nửa.
- Một packet không tìm thấy source/target không được làm văng recv loop.

## Kiểm thử

Triển khai theo TDD với các lớp test:

1. Unit test decoder cho `0x0B/FA`, `/0A`, `/05`, `0x32/01`, `0x33/01`, `0x34`, `0x35/01`, `/03`, `/05`, `/07`, `/15`, `/20`.
2. Test delta HP/SP: damage/heal, miss, clamp, hồi sinh, giá trị trên 65535.
3. Test lifecycle: `0x34` không xóa roster; action chỉ một lần/turn; ACK đúng source; end chỉ khi `0x0B/00` khớp local ID; `0x14` không kết thúc tracker.
4. Replay capture PB110: đúng 5 generation, 31 turn, 8 flyout/reinforcement, không cần `0x33`, roster/HP không âm và slot thay thế đúng.
5. Test combat AI dùng HP/status tracker để tránh CC/protection trùng và áp ngưỡng HP địch.
6. Test coordinator nhiều acc: gói trùng đến lệch thời điểm chỉ tăng một turn/log một lần; acc nhanh không gửi thay acc chậm; acc chậm chỉ gửi sau `0x34` local; acc đơ/dis không khóa đội; packet cũ không được gửi action; reservation không trùng CC/protection/revive/heal.
7. Chạy toàn bộ test hiện có, compile Python PC/APK, so hash các module mirror và `git diff --check`.

## Phạm vi không làm trong lượt này

- Không mô phỏng animation hoặc chia damage nhiều hit ngẫu nhiên; chỉ ghi tổng delta server để HP cuối chính xác.
- Không thay đổi kịch bản skill do người dùng cấu hình ngoài việc cấp dữ liệu battle đúng.
- Không build/release cho đến khi parser, replay capture và regression test đều qua; build chỉ thực hiện khi người dùng yêu cầu.
