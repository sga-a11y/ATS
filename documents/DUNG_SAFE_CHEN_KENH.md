# Đứng yên ở safe (chèn kênh)

Thêm 08/10/2026. Mục đích: có những acc chỉ vào map train để **chèn cho full kênh**, để party chính
train thoải mái, không bị người lạ vào quấy.

## User thấy gì
- Mode **Train** hoặc **DG + Train** → chọn **Map cụ thể** → ô Quái/Điểm có mục cuối
  **`🛡 Đứng yên ở safe (chèn kênh)`**.
- Chọn mục đó thì hiện ô **Kênh** (1–99, mặc định 1). PC là spinbox, APK là ô "Kênh đứng yên".
- Tab party trên PC hiện thêm `· Safe k<kênh>`.
- Chọn 1 trong 5 mục **Tự chọn map** thì mục này **không có**. Tự chọn map luôn đi đánh.
- `🎲 Bot tự chọn (ngẫu nhiên)` chỉ random trong các `Điểm 1..N` thật, **không bao giờ** rơi vào
  chế độ đứng yên, vì chế độ này là cờ riêng, không phải chỉ số điểm.

## Bot làm gì
1. Flow party như train thường: gom map → gom kênh → lập party.
2. **Kênh:** khi cả party đã ở map train (pha train), kênh đích **ghim** đúng kênh user chọn.
   Không bao giờ tự chọn "kênh ít người nhất". Lệnh đổi kênh tay trên GUI vẫn thắng.
   Ở thành tập kết hoặc trong Dị Giới thì không ghim, vì mỗi map một danh sách kênh.
3. **Kênh đầy (mã 4)** là chuyện bình thường. Acc nào chưa vào được thì cứ đứng ở map train,
   **30 giây** gửi lại một lần cho tới khi có chỗ (`DUNG_SAFE_KENH_DAY_CHO_SEC`).
4. **Chỗ đứng** = safe đầu tiên của map (`TRAIN_MAPS[map]["safe"][0]`), cũng là chỗ bot ra đứng
   khi đổi kênh. Map chưa học safe thì đứng ngay chỗ vừa vào map.
5. Ra safe bằng `navigate_to(flee=True)` (gặp quái thì bỏ chạy), không theo đường capture ra bãi
   quái. Đã đứng trong ô ±40 quanh safe thì **không đi nữa** (`DUNG_SAFE_BAN_KINH`).
6. `train` = đứng im: không `combat_ready`, không chạy vòng, không ghi thống kê chặn train.
   Vẫn duy trì Phúc Thần / mua HP-SP. Việc định kỳ (daily, PB tổ đội, world boss...) vẫn chạy
   như train thường, xong thì quay về safe.
7. Tắt watchdog **ĐỨNG HÌNH 240s** khi cả party đang ở map train. Đứng im là đúng việc; không tắt
   thì cứ 240s lại bị gom về thành.
8. DG + Train: pha DG **vẫn đánh** như cũ, chỉ pha train mới đứng yên.

## Lưu cấu hình
- PC (`accounts.json`): `stand_safe` (bool), `stand_channel` (int). Lưu cả trong `train_last`, nên
  đổi qua mode khác rồi quay lại, hoặc "Áp chế độ cho mọi party", vẫn giữ riêng từng party.
- APK (`PartyStore`): `stand_safe`, `stand_channel`. Truyền vào `setup_party_runtime` ở **2 vị trí
  CUỐI CÙNG** (`trainPick.isEmpty() && standSafe`, `standChannel`).

## Code
| Chỗ | Việc |
|---|---|
| `bot/train_pick.py::dung_safe_kenh` | Nguồn duy nhất: cờ nào bật, kênh mấy (tự chọn map → 0) |
| `run_party_digioi.py::_kenh_dung_safe` | Chỉ khi ở pha train **và** đang ở map train |
| `_engine_chot_kenh` | `pinned = kenh_ghim or _kenh_dung_safe(...)` |
| `_chuan_bi_bai_train` | `mob_spot` = safe |
| `_chup_anh_cap_party` | `acc_dung_hinh = []` khi đứng yên ở map train |
| `bot/party_engine.py::thi_hanh(dung_safe=)` | Nhánh `ra_spot`/`train`/`doi_kenh` riêng |
| `PartyEngine._dung_safe` | Chỉ `PHA_TRAIN` |
| Test | `tests/test_dung_safe_chen_kenh.py` |

## Chưa đo trên máy thật
- Kênh đầy lâu thì party không đủ người cùng kênh, tức không lập được party. **Đọc code (chưa đo
  log):** cả party cùng map mà lệch kênh thì `quyet_dinh_cap_party` ra `dong_bo` (đồng bộ tại
  chỗ), không `gom` về thành. Chỉ lệch MAP mới gom. Acc đã vào kênh thì `nghi` ở map train, acc
  chưa vào thì 30s thử lại một lần. Chạy thật lần đầu nên grep `DUNG YEN O SAFE` + `DIEU PHOI`
  trong `party.log` để xác nhận.
