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
  - Từ 07/10 bat **luôn** xóa `bot_bundle`, kể cả update thường (xem `AUTO_UPDATE.md`).
- Bản cũ phát hành trước tính năng này không có bảng. Để bật lại update: xóa `version.json` cạnh exe rồi bấm Check Update. Hướng dẫn ghi trong `DANG_DUNG_BAN_CU.txt`.

## APK
Không hạ được vỏ APK: Android chặn cài APK có versionCode thấp hơn, và version APK nằm cứng trong `BuildConfig`. Thay vào đó, **giữ vỏ APK mới và chạy core Python (engine) của bản cũ**.

**Bảng Update** (nút Check Update):
- Dòng **"APK v… · core v…"**. Hai số khác nhau khi đang chạy core cũ.
- ☑ **Tự động update**: lưu bằng cờ `SharedPreferences` (`updater/auto_update`), mặc định bật.
  - Cờ tắt thì bỏ qua cả check APK lẫn tải core.
  - Tick lại thì bỏ ghim `bot_bundle/version.txt` và kiểm tra update ngay.
- **Chọn bản cũ**: tải `releases/download/v<bản>/aTSBot-bundle.zip`, cài bằng `installBundleZip` với version `9.<bản>`, rồi tắt cờ. Áp dụng **ngay**, kể cả khi đang có acc chạy (user tự bấm chọn): acc đang chạy tự login lại trên core đó. Xem mục "APK: tự áp dụng core" bên dưới.
- Thanh tiêu đề hiện `v<core thật> (tắt update)`.

**Cửa chặn "bundle cũ hơn APK" (06/09) không phải sửa.** Cửa so chuỗi `bundleVer > VERSION_NAME`, mà core ghim `9.x` luôn lớn hơn nên tự qua. Bundle cũ sót lại (không ghim) vẫn bị chặn như trước.

**Rủi ro vỏ mới + core cũ:** Kotlin gọi khoảng 50 hàm Python, và hàm mới được thêm liên tục (ví dụ `bag_slot_*` và `pet_roi_chuc_notify_skip` từ 27/09). Mọi chỗ gọi đều bọc `try`, nên core cũ thiếu hàm nào thì **chỉ tính năng đó** không chạy, bot không chết.

## APK: tự áp dụng core (06/10)
Trước đây core mới tải về xong chỉ "chờ áp dụng": user phải Dừng tất cả rồi Start lại, quên là chạy code cũ mà tưởng đã update. Giờ core được nạp trong một **tiến trình mới**, không bao giờ thay module Python giữa chừng.

**User thấy gì:**
- **Không acc nào chạy** (mở app, bấm Kiểm tra bản mới): có core mới thì tự tải, tự áp dụng, không hỏi.
- **Đang có acc chạy**: **không tự làm gì**, vì áp dụng sẽ cắt ngang mọi acc (đang phó bản, boss...). Thanh tiêu đề hiện "Có core mới — bấm Check Update để áp dụng"; trong bảng Cập nhật có nút **"Áp dụng ngay (acc sẽ login lại)"**. Không bấm thì acc chạy tiếp core cũ; Stop/Start **không** tự áp dụng — lần mở app hoặc Kiểm tra bản mới kế tiếp lúc không acc nào chạy mới áp dụng.
- **Chọn bản cũ**: áp dụng ngay như bấm "Áp dụng ngay". Cờ tắt tự động update được lưu chắc (`commit`) trước khi áp dụng; áp dụng lỗi thì trả cờ về như cũ.
- Bỏ tick **Tự động update** thì không có gì xảy ra cả (không check, không tải, không restart).

**Luồng áp dụng** (`ApkUpdater.installBundleZip` → `BotForegroundService.restartForCore`):
1. Ghi kế hoạch chạy lại: chỉ những acc **đang chạy thật** (`core_update_runtime.active_accounts`), vào `core_update_resume.json` + journal `core_update_restart.json`.
2. Dừng mọi acc, chờ thread cũ thoát (`quiesce`, tối đa 25s), xả cache.
3. Đổi thư mục: `bot_bundle/current` → `previous`, bản mới → `current`, ghi `version.txt`.
4. `CoreRestartService` (tiến trình riêng `:core_restart`) giết tiến trình bot cũ rồi bật lại `BotForegroundService` (và mở lại app nếu đang hiện). Tiến trình cũ đã chết sẵn thì vẫn bật lại bot.
5. Tiến trình mới nạp core, xác nhận đúng bản rồi mới chạy lại các acc trong kế hoạch.

**Kế hoạch chạy lại lấy từ cấu hình đang lưu LÚC ÁP DỤNG** (đúng thứ tự party hiện tại), không lấy ảnh chụp lúc Start: party đã xoá không sống lại, party phía sau không bị bỏ sót (review 06/10 #1).

**Chờ thread cũ dừng tối đa 45s** (`QUIESCE_SECONDS`): `stop_account` chờ tới 25s mới cưỡng bức đóng socket (member chờ leader về safe), nên 25s cũ chắc chắn hụt. Test giữ hai số này đi cùng nhau.

**Stop trong lúc đang áp dụng** được tôn trọng: acc bị Stop thì gạch khỏi kế hoạch; Dừng tất cả thì không chạy lại acc nào.

**Lỗi thì quay về**:
- Core mới nạp lỗi → khôi phục `previous`, khởi động lại trên core cũ, chạy lại đúng các acc đó. Bản lỗi được ghi lại (`failed_version`): tự update **bỏ qua đúng bản đó**, bản mới hơn vẫn lên bình thường; nạp thành công bản sau thì xoá ghi nhận.
- Áp dụng lỗi giữa chừng (cài file lỗi...) → khôi phục rồi cũng **khởi động lại tiến trình** để chạy lại acc trên core cũ; chỉ khi không bật được tiến trình mới thì mới chạy lại ngay trong tiến trình cũ (và chỉ khi thread cũ đã dừng hẳn).
- Thanh tiêu đề hiện "Cập nhật lỗi — xem chi tiết" tới khi user mở bảng Cập nhật xem rồi đóng.
- Bị kill giữa chừng thì lần mở sau `recoverInterruptedInstall` dọn theo journal; hàm này không bao giờ ném lỗi (tránh crash lặp).
- Trước khi bắt đầu, bản sao lưu `previous` sót lại bị xoá: rollback không bao giờ khôi phục một bản cũ hơn. Trước update mà chưa có thư mục core thì rollback xoá luôn core mới và `version.txt`.
- Áp dụng xong mà tiến trình cũ không bị thay sau 30s → tự thoát; Android bật lại service (sticky) và tiến trình mới làm tiếp theo journal. Không còn cảnh app "chết" vì kẹt trạng thái đang áp dụng.
- Không áp dụng bundle **không mới hơn APK** (bundle đó bị bỏ qua khi nạp, áp dụng chỉ làm acc login lại vô ích).

**Mở lại UI**: Android 10+ có thể chặn mở activity từ nền; bot vẫn chạy, bấm thông báo để mở app.

**Kiểm thử**: `tests/test_android_core_update_runtime.py` (Python), `CoreUpdateRestartTest` (instrumented), `tools/test_android_core_restart.py --adb <adb> --serial <máy>` chạy trên app riêng `com.tsbot.android.verification` (bản debug, core giả, không kết nối game).

## Giới hạn
- Danh sách chỉ gồm **100 bản gần nhất** (`RELEASE_LIMIT`, PC và APK; không lọc theo ngày để ngừng build vẫn còn bản chọn), và phải `>= 1.1.202608080000`. `installed_app_version` có từ 07/08/2026, các bản cũ hơn không khóa được.
- Nguồn danh sách là **`releases.json`**:
  - Mỗi lần build, `build_product.py::_write_releases_json` sinh file này từ API có token, rồi upload lên release. File có cùng cấu trúc JSON với GitHub API.
  - App tải file qua `releases/latest/download/releases.json`, đi qua CDN nên không giới hạn lượt.
  - Chỉ khi tải file lỗi mới lùi về `api.github.com`. Không token thì API chỉ cho **60 lượt/giờ mỗi IP**, và nhà mạng VN hay cho nhiều người dùng chung IP. User đã gặp `403 rate limit exceeded` ngày 28/09.

## Bước 2 (sau)
Cho user vote bản ổn định/lỗi (Cloudflare Worker + KV) và hiện kết quả trong danh sách chọn bản.
