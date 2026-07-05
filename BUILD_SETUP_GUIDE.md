# Hướng dẫn cài môi trường + build (PC exe + Android APK)

Máy nào cũng cần **clone/pull repo git trước** (`git clone https://github.com/sga-a11y/ATS.git`
hoặc `git pull` nếu đã có sẵn) để có mã nguồn. Phần dưới đây là cài **công cụ build** (khác máy khác
phải tự cài lại, không đi theo git).

---

## 1. Build bản PC (`aTSBot.exe`)

### Cần cài
- **Python 3.12** (bản 64-bit, tải từ python.org — bản dùng khi viết hướng dẫn này: `3.12.10`)
- Sau khi cài Python, mở terminal chạy:
  ```bash
  pip install nuitka
  ```
- **KHÔNG cần tự cài gcc/MinGW** — lần đầu chạy, Nuitka tự tải về bộ compiler MinGW64 riêng của nó
  (`--assume-yes-for-downloads` trong lệnh build đã tự động đồng ý tải). Lần build đầu tiên sẽ
  chậm hơn (phải tải ~vài trăm MB), các lần sau nhanh vì đã có cache.

### Quy trình build
```bash
cd đường-dẫn-tới-repo
python build_product.py
```
Output: thư mục `aTSBot/` (chứa `aTSBot.exe` + các file JSON cấu hình đi kèm) — gửi cả thư mục này
cho người dùng, không phải chỉ file `.exe`.

### Chú ý
- **`config.py` là file placeholder (đã tracked, chỉ chứa `acc1/password1`...)** — `build_product.py`
  đóng gói chính `config.py` này. Mật khẩu/tài khoản THẬT nằm ở `accounts.json` (gitignored, **KHÔNG**
  đóng gói vào bản build). Nên tuyệt đối không đưa acc thật vào `config.py`.
- **Bản gửi đi KHÔNG kèm `accounts.json`** (từ 07/2026): người nhận **copy đè bản update** lên bản cũ
  mà **không mất** cấu hình acc đã lưu. Lần đầu chạy `aTSBot.exe`, GUI tự tạo `accounts.json` mặc
  định (Cấu hình 1 trống) — người nhận vào "Cấu hình" nhập acc rồi Lưu.
- Nếu build báo lỗi liên quan tới đường dẫn cache Nuitka (`structuredquerycondition.h No such
  file` hoặc lỗi tương tự dù file có thật) — nguyên nhân là cache Nuitka nằm trong thư mục bị
  sandbox hoá (`%LOCALAPPDATA%\Nuitka` có thể bị OneDrive/App sandbox can thiệp). `build_product.py`
  đã tự đặt `NUITKA_CACHE_DIR` về ổ đĩa gốc để tránh lỗi này — nếu vẫn gặp, kiểm tra biến môi
  trường này có bị ghi đè bởi cấu hình hệ thống không.
- Số phiên bản (`1.1.YYYYMMDDHHMM`) tự sinh theo **thời điểm build**, không cần sửa tay.
- Build xong nằm ở `E:\...\aTSBot\` (thư mục ngang hàng với mã nguồn, không phải trong `_work`/`_stage`
  — 2 thư mục đó chỉ là tạm, có thể xoá).

---

## 2. Build bản Android (`app-debug.apk`)

### Cần cài
1. **JDK 17** (khuyên dùng Eclipse Temurin):
   ```powershell
   winget install --id EclipseAdoptium.Temurin.17.JDK -e
   ```
   Sau khi cài, **PHẢI set `JAVA_HOME`** trỏ đúng bản 17 trước MỌI lệnh `gradlew` (máy có thể có
   sẵn Java bản cũ hơn ở `JAVA_HOME` mặc định, gây lỗi build):
   ```bash
   export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
   ```
   (đường dẫn có thể khác chút tuỳ bản patch Temurin cài được lúc đó — kiểm tra bằng
   `ls "C:\Program Files\Eclipse Adoptium"`).

2. **Android SDK command-line tools** — tải `commandlinetools-win-*.zip` từ
   `https://developer.android.com/studio#command-tools`, giải nén vào
   `<SDK_ROOT>\cmdline-tools\latest\` (chú ý: thư mục `latest` phải chứa trực tiếp `bin/`, `lib/`...
   bên trong, không phải lồng thêm 1 cấp `cmdline-tools/cmdline-tools/`).

   **Lưu ý khi giải nén trên Windows:** dùng `cp -r` để copy nội dung, **KHÔNG dùng `mv`** — từng
   gặp lỗi `mv` báo thành công nhưng thực ra bỏ sót thư mục `lib/` (có thể do AV khoá file giữa
   chừng), khiến `sdkmanager` báo `ClassNotFoundException` dù nhìn qua tưởng đã giải nén đủ.

3. Cài các gói SDK cần thiết (từ `<SDK_ROOT>\cmdline-tools\latest\bin\sdkmanager.bat`):
   ```bash
   sdkmanager.bat --sdk_root="<SDK_ROOT>" "platform-tools" "platforms;android-34" \
     "build-tools;34.0.0" "ndk;26.3.11579264" "cmake;3.22.1"
   ```
   (cần đồng ý license — thêm `yes |` phía trước lệnh nếu chạy không tương tác được).

4. Tạo file `android/local.properties` (file này **bị gitignore**, mỗi máy tự tạo riêng, KHÔNG
   commit lên git vì đường dẫn SDK khác nhau từng máy):
   ```properties
   sdk.dir=C\:\\Android
   ndk.dir=C\:\\Android\\ndk\\26.3.11579264
   ```
   (thay `C:\Android` bằng đường dẫn `<SDK_ROOT>` thật của máy đó, dùng `\\` thay cho `\`).

   Không cần tự cài Gradle riêng — dự án đã có sẵn Gradle wrapper (`android/gradlew`,
   `android/gradlew.bat`) tự tải đúng bản Gradle cần dùng ở lần chạy đầu tiên.

### Quy trình build
```bash
cd android
export JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"
./gradlew assembleDebug
```
Output: `android/app/build/outputs/apk/debug/app-debug.apk`

### Cài lên máy ảo/điện thoại để test
```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
**Nếu sửa code Python (`train_bot/*.py`) và cài lại bằng `-r` mà thấy hành vi vẫn như bản cũ:**
Chaquopy (thư viện chạy Python trong app) có cache giải nén Python riêng trên máy, đôi khi
`install -r` không làm mới cache này. Cách chắc chắn nhất: **gỡ hẳn app rồi cài lại** (không dùng
`-r`), hoặc xoá data app trong Settings → Apps → aTSBot → Xoá dữ liệu — **lưu ý việc này xoá sạch
toàn bộ Party/account đã lưu trong app, phải nhập lại từ đầu**.

### Chú ý khác
- `pyc { src = false }` trong cấu hình Gradle nghĩa là APK chỉ chứa Python đã biên dịch (`.pyc`),
  không có mã nguồn `.py` gốc — đây là 1 lớp bảo vệ chống dịch ngược, không phải lỗi nếu không tìm
  thấy `.py` khi giải nén APK ra xem.
- Build cảnh báo `NDK was located by using ndk.dir property... deprecated` — vô hại, chỉ là gợi ý
  Gradle muốn chuyển sang khai báo NDK version trong `build.gradle.kts` thay vì `local.properties`,
  không ảnh hưởng kết quả build.
