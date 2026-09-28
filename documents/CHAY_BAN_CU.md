# Tự động update / chạy bản cũ (PC)

## Vì sao
Auto-update luôn kéo lên bản mới nhất. Nếu bản mới lỗi (ví dụ lúc viết lại engine) thì user không có đường lui.

## User thấy gì (nút "Check Update")
Bấm **Check Update** sẽ mở bảng gồm:
- **"Bạn đang dùng v1.1.xxx"** (luôn hiện bản thật).
- ☑ **Tự động update**. Cài lần đầu thì mặc định có tick.
  - **Bỏ tick** → bot không tự update nữa. Tiêu đề cửa sổ hiện `(đã tắt tự động update)`.
  - **Tick lại** → bot kiểm tra ngay và lên bản mới nhất.
- Nút **Kiểm tra bản mới**. Khi đang tắt tự động update, bấm vào chỉ báo "đang tắt, tick để lên bản mới".
- Nút **Chọn bản cũ** → hiện danh sách các bản trên GitHub release. Chọn một bản → **"Tải bản này"**:
  - Nếu đang có acc chạy thì bắt Stop trước.
  - Khi tải, bỏ tick tự động update. Bot tắt, cài đè bản đó vào **chính thư mục hiện tại**, rồi tự mở lại.
  - `accounts.json` giữ nguyên, vì zip không chứa file này.

## Cơ chế (không cần sửa code bản cũ)
- Updater so version bằng **so chuỗi** (`remote > current`).
  - Phần app đọc `version.json` cạnh exe (`installed_app_version`).
  - Phần core đọc `bot_bundle/version.txt`, không có thì lấy version app.
- **Bỏ tick** (`set_auto_update(False)`): ghi `9.<bản thật>` vào **cả** `version.json` **lẫn** `bot_bundle/version.txt`, ví dụ `9.1.1.202609141802`. Chuỗi `9...` lớn hơn mọi `1.1...` trên server, nên bot coi mình là mới nhất. Bản thật lưu ở `pinned_real_version`; bỏ `9.` ở đầu cũng ra bản thật.
- **Tick** (`set_auto_update(True)`): ghi lại bản thật.
- **Chọn bản cũ**: `download_and_swap(zip của tag v<bản>, pin_version=<bản>)`. Luồng giống update thường (stage → `_update.bat` kill exe → xcopy đè → mở lại), thêm 2 bước:
  - ghim `version.json` trong stage thành `9.<bản>`;
  - bat **xóa `bot_bundle`** trước khi chép. `gui.py` luôn nạp `bot_bundle/current` nếu có, nên để lại thì core mới đè lên code bản cũ.
- Bản cũ phát hành trước tính năng này không có bảng. Để bật lại update: xóa `version.json` cạnh exe rồi bấm Check Update. Hướng dẫn ghi trong `DANG_DUNG_BAN_CU.txt`.

## APK
Không hạ được vỏ APK: Android chặn cài APK có versionCode thấp hơn, và version APK nằm cứng trong `BuildConfig`. Thay vào đó, **giữ vỏ APK mới và chạy core Python (engine) của bản cũ**.

**Bảng Update** (nút Check Update):
- Dòng **"APK v… · core v…"**. Hai số khác nhau khi đang chạy core cũ.
- ☑ **Tự động update**: lưu bằng cờ `SharedPreferences` (`updater/auto_update`), mặc định bật.
  - Cờ tắt thì bỏ qua cả check APK lẫn tải core.
  - Tick lại thì bỏ ghim `bot_bundle/version.txt` và kiểm tra update ngay.
- **Chọn bản cũ**: tải `releases/download/v<bản>/aTSBot-bundle.zip`, cài bằng `installBundleZip` với version `9.<bản>`, rồi tắt cờ. Đang có acc chạy thì bắt dừng trước. Bấm Start sau đó sẽ nạp core cũ, vì lúc không acc nào chạy thì service purge `sys.modules`.
- Thanh tiêu đề hiện `v<core thật> (tắt update)`.

**Cửa chặn "bundle cũ hơn APK" (06/09) không phải sửa.** Cửa so chuỗi `bundleVer > VERSION_NAME`, mà core ghim `9.x` luôn lớn hơn nên tự qua. Bundle cũ sót lại (không ghim) vẫn bị chặn như trước.

**Rủi ro vỏ mới + core cũ:** Kotlin gọi khoảng 50 hàm Python, và hàm mới được thêm liên tục (ví dụ `bag_slot_*` và `pet_roi_chuc_notify_skip` từ 27/09). Mọi chỗ gọi đều bọc `try`, nên core cũ thiếu hàm nào thì **chỉ tính năng đó** không chạy, bot không chết.

## Giới hạn
- Danh sách chỉ gồm các bản `>= 1.1.202608080000`. `installed_app_version` có từ 07/08/2026, các bản cũ hơn không khóa được.
- Danh sách lấy từ GitHub API: không cần đăng nhập, giới hạn 60 lần/giờ mỗi IP. Lỗi thì hiện thông báo.

## Bước 2 (sau)
Cho user vote bản ổn định/lỗi (Cloudflare Worker + KV) và hiện kết quả trong danh sách chọn bản.
