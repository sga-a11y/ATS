# Auto-update bản PC: exe + core bundle

Có hai đường update, cùng đọc chung `version.json` trên release `latest`:

| Đường | Tải gì | Khi nào | User thấy |
|---|---|---|---|
| **Core bundle** (ngầm) | `aTSBot-bundle.zip` → `bot_bundle/current/pc` | `bundle_version` mới hơn `bot_bundle/version.txt` | Không hỏi gì; app tự khởi động lại |
| **Exe** (hỏi) | `aTSBot.zip` (cả thư mục) → `_update.bat` chép đè | `pc_app_required_version` mới hơn exe đang chạy (chỉ nhảy khi `gui.py` đổi) | Hộp thoại hỏi cập nhật |

Khi khởi động, `gui.py` nạp `bot/*` + `run_party_digioi.py` từ `bot_bundle/current/pc` đè lên bản
compiled trong exe (`_BundleFirstFinder`). Nghĩa là **core mới luôn chạy trên exe cũ**.

## Sự cố 07/10 (v1.1.202610071122): exe cũ bấm mở không có gì xảy ra

- Commit `980c609` thêm `bot/bug_report.py` có `import uuid`.
- Exe Nuitka chỉ đóng gói những module thư viện chuẩn mà code **lúc build exe** có import. Đo bằng
  `tools/do_module_exe.py`: các exe 10/08, 27/08, 28/09 đều có 410 module và **không có `uuid`**.
- Thứ tự cũ trong `gui._check_update`: áp core trước → restart → rồi mới hỏi cài exe. Restart xong,
  exe cũ nạp core mới → `ModuleNotFoundError: No module named 'uuid'` ngay ở `import run_party_digioi`
  → exe không console nên chết im lặng.
- Vì chết **trước** bước check update nên user không tự thoát được. Xoá `bot_bundle` cũng không cứu
  được: mở lên là exe tự tải lại core hỏng.

## Bốn lớp chặn (07/10)

1. **Hotfix**: `bug_report.py` tạo boundary multipart bằng `os.urandom(16).hex()`, bỏ `uuid`.
2. **Cổng chặn lúc build** (`build_product.validate_core_imports` + `tests/test_core_chi_import_module_exe_cu_co.py`):
   quét AST mọi import trong core. Module nào không có trong `tools/exe_module_baseline.json` thì
   **build dừng**. Import nằm trong `try/except ImportError|Exception` thì được bỏ qua (code đã tự
   lo trường hợp thiếu).
3. **Server bắt cài exe thì không áp core ngầm** (`updater.check_bundle_update`): nếu
   `pc_app_required_version` mới hơn exe đang chạy thì bỏ qua core và đi thẳng tới hộp thoại cài exe.
   Kèm theo, `_update.bat` **luôn xoá `bot_bundle`**, vì zip đầy đủ đã có đúng code của bản đó.
   - Đánh đổi: user từ chối cài exe thì cũng không nhận core mới, cho tới khi chịu cài exe.
     Chấp nhận được, vì core mới viết cho vỏ `gui.py` mới.
   - Lớp này nằm trong `bot/updater.py`, tức trong core. Nó có hiệu lực với mọi exe ngay khi máy đã
     có core chứa nó; không cần exe mới.
4. **Exe tự cứu khi core hỏng** (`gui._bootstrap_bundle_path` / `gui._nap_core`). Lớp này chỉ có
   trong exe build từ 07/10 trở đi:
   - Core **cũ hơn** exe (cài exe mới mà `bot_bundle` cũ còn sót) thì bỏ qua core.
   - Nạp core lỗi (`run_party_digioi` + các module ở `_BOT_GUI_NAP_NGAY`) thì ghi `core_loi.log`
     cạnh exe, gỡ core, nạp bản trong exe → **app vẫn mở**, vẫn hỏi cài exe được.
   - `party.log` có dòng `update: CORE TAI VE LOI KHI NAP (...)` hoặc `update: core v... CU HON exe ...`.
     Tiêu đề cửa sổ hiện version exe, không hiện version core.

## User đang kẹt (exe trước 07/10 + core 1.1.202610071122)

Core hỏng đã nằm sẵn trên máy, và exe chết trước khi kịp chạy code mạng nào → **không có bản vá nào
từ server tự tới được máy đó**. User phải làm tay **một** trong hai cách:

- **Xoá thư mục `bot_bundle`** cạnh `aTSBot.exe` rồi mở lại. Exe cũ chạy code của chính nó, tự tải
  core đã hotfix (chạy được trên exe cũ, đã đo), khởi động lại, rồi hỏi cài exe mới → bấm đồng ý.
- Hoặc tải `aTSBot.zip` mới nhất rồi chép đè cả thư mục. `accounts.json` không nằm trong zip nên được giữ.

User **chưa mở app** kể từ lúc release 07/10 11:35 thì không bị gì: lần mở tới, họ nhận thẳng core đã hotfix.

## Đo lại baseline module của exe

```
python tools/do_module_exe.py "<thư mục có aTSBot.exe>" ["<thư mục khác>" ...]
```

- Công cụ chép exe ra thư mục tạm, cài một core giả. Core giả dùng `importlib.util.find_spec` liệt
  kê module có trong exe rồi thoát. Kết quả ghi vào `tools/exe_module_baseline.json` (mỗi exe một
  mục, `co` = phần giao của các exe đã đo).
- Đối chứng lúc viết công cụ: exe 28/09 không có `uuid`, exe 07/10 có. Ra đúng như vậy thì công cụ
  đo đúng.
- Cần dùng một module mới mà exe cũ không có:
  - Ưu tiên viết bằng module đã có.
  - Hoặc bọc trong `try/except ImportError` và có đường lui.
  - Muốn bỏ hỗ trợ exe quá cũ: xoá mục exe đó khỏi baseline rồi đo lại bằng exe mới hơn. Chỉ làm
    khi chắc user không còn dùng exe đó, vì lớp 3 chỉ bảo vệ các release có bắt cài exe.
