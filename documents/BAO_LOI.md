# BÁO LỖI — user gửi version + config + log của party lỗi về Telegram

Sinh ra 07/10: user báo bug mà không có gì để xem → không sửa được, và luật CORE_FLOW bắt
**đọc log trước khi sửa**. Hệ báo lỗi đưa đúng log + config của party lỗi về tay dev.

## User thấy gì (PC và APK giống nhau)

1. Mỗi tab party có nút **🐞 Báo lỗi** ở mép phải hàng nút (cùng hàng Start/Stop party),
   màu mặc định như các nút khác. Nút **gắn với party của tab đó** — không chọn party.
2. Bấm → hộp **"Báo lỗi — Party N"**, một ô mô tả (bắt buộc, ≥ 10 ký tự).
3. Bấm Gửi → "Đang gửi... (x MB)" → xong hiện **"Đã gửi! Mã báo lỗi: BL-MMDD-XXXX"** + nút Copy,
   user nhắn mã đó cho dev.
4. Gửi lỗi (mất mạng, Telegram bị chặn) → báo thất bại và **lưu zip cạnh exe/app** để gửi tay.
5. Chống spam: mỗi máy cách nhau ≥ 2 phút mới gửi tiếp được (gửi hỏng thì không tính).
6. APK màn ngang (09/10): bàn phím từng che nút Gửi → cửa sổ dialog đặt `SOFT_INPUT_ADJUST_RESIZE`
   (co lại khi bàn phím hiện) và nội dung cuộn được, hàng nút Gửi/Đóng luôn nằm trên bàn phím.

## Gói zip gửi đi

| File | Nội dung |
|---|---|
| `info.json` | mã báo lỗi, mô tả, party, version exe / APK + core, Windows/Android, giờ gửi, region |
| `config.json` | cấu hình party đó (server, mode, map, **toàn bộ cài đặt nâng cao**), config riêng từng acc (`on`, `heal`, `furnace`, `vantieu`, `settings`), phần chung (kênh, whitelist leaders) |
| `party.log` | log đã lọc của party đó, **2 phiên start gần nhất** |

- **Username GIỮ NGUYÊN** (user chốt 07/10 — log vốn đã có username, đọc log phải khớp).
- **Chỉ bỏ password**: xoá trường `p` của mọi acc. Lớp phòng hờ: chuỗi password nào lọt vào log
  thì thay bằng `***`.

## Lọc log

- **Dòng mốc phiên**: `start_party()` ghi một dòng khi party bắt đầu phiên MỚI (`_fresh`):
  `>>> PARTY N BAT DAU PHIEN MOI <ngày giờ> v<version> acc=[...]`. Log chỉ có giờ không có ngày,
  dòng mốc mang ngày để biết phiên nào của hôm nào.
- **Lấy 2 phiên gần nhất**: user thấy lỗi thường Stop/Start lại rồi mới bấm báo lỗi → dấu vết
  lỗi nằm ở phiên TRƯỚC. Chỉ có 1 mốc thì lấy 1 phiên. Không có mốc nào (log từ bản cũ) → lấy
  phần cuối. Trần 200 MB log thô, quá thì cắt phần cũ.
- Đọc ngược `party.log` → `.1` → `.2` (RotatingFileHandler, mỗi file 1 GB).
- **Tắt/mở lại tool thì log cũ mất** (`party.log` mở `mode="w"`; APK áp core mới cũng vậy) → báo lỗi
  chỉ có log từ lần mở tool gần nhất. User chốt 07/10: chấp nhận, không sửa.
- **Giữ dòng của party đó**: `[party N]`, `[PN ...]`, nhãn là tên nhân vật / `ten~username` của
  acc trong party; dòng không có giờ ở đầu (traceback) đi theo dòng có giờ ngay trên nó.
- Mọi dòng log phải gắn được với party: `battle_tracker.py` cảnh báo "BO goi KET TRAN" trước kia
  in `[BATTLE g=..]` không nhãn (1211 dòng / 50 MB log ngày 07/10) → nay mang nhãn acc.

## Gửi

- Gửi thẳng Telegram Bot API `sendDocument` tới bot của dev (`@atsbotrpbot`), chat riêng của dev
  (chat_id trong `bot/bug_report.py`). Caption: mã, version, party, mode, mô tả. User không cần Telegram.
- **Token KHÔNG nằm trong source/git**: dev tự tạo `bao_loi_bot.json` ở gốc repo
  (`{"token": "...", "chat_id": "689905584"}`, gitignore). `build_product.write_bao_loi_bot` sinh
  module `_bao_loi_bot.py` vào `_stage/bot` (Nuitka biên dịch vào TRONG exe, + bundle) và
  `train_bot/` (APK) — không có file rời cạnh exe. Thiếu json → build vẫn chạy, bản đó chỉ lưu
  zip để gửi tay (và xoá module cũ để không sót token cũ). Chạy từ source: `doc_bot` đọc thẳng json.
- Rủi ro đã chấp nhận (user chốt 07/10): APK và bundle là file công khai trên release → người cố
  tình đào được token. Họ chỉ spam/xoá tin bot vừa gửi/đổi tên bot được; không đọc được báo lỗi cũ,
  không vào được Telegram của dev. Bị phá → @BotFather `/revoke`, sửa json, build lại.
- Giới hạn Telegram 50 MB/file; log nén ~10 lần nên 200 MB thô ≈ 20 MB zip.
- Đo 07/10 trên `party.log` thật 437 MB: lọc 200 MB cuối mất 11 s (chạy luồng nền), zip 142 KB.
- APK: zip gửi hỏng nằm ở `filesDir/bao_loi/` → nút "Chia sẻ file báo lỗi" (FileProvider,
  `res/xml/file_paths.xml`). PC: mở thư mục `bao_loi/` cạnh exe.

## Phía dev

- **Bot KHÔNG đọc lại được tin chính nó gửi** (`getUpdates` chỉ có tin gửi TỚI bot), NHƯNG
  forward được: `forwardMessage` trả Message kèm `document.file_id`. `python tools/bug_inbox.py`
  tự quét chat dev — forward im lặng từng tin mới, tin nào là `BL-*.zip` thì tải, xoá ngay bản
  forward; nhớ message_id đã quét ở `bug_reports/.da_quet`. Dev không phải làm gì, không giới hạn
  24h. Giải nén vào `bug_reports/<mã>/` (gitignore — log của user). Bot chỉ tải được file ≤ 20 MB.
  Zip có sẵn (vd user gửi qua Zalo) → `python tools/bug_inbox.py <file.zip>`.
- Đã chạy thật 07/10: `BL-1007-73E9` (party 3, digioi_train) kéo về đủ 3 file, 40.040 dòng log có
  cả dòng nhãn tên nhân vật, config 59 trường party + config riêng 5 acc, không có trường `p`.
- Script tự đặt stdout/stderr UTF-8: console Windows mặc định cp1252 nên trước đây in mô tả tiếng
  Việt là văng `UnicodeEncodeError` (gặp ở BL-1007-8C5F, file vẫn giải nén đủ).
- Đọc lỗi: "xem lỗi BL-xxxx" → đọc `bug_reports/BL-xxxx/` theo luật CORE_FLOW.

## Kỹ thuật

- `bot/bug_report.py` (SHARED PC/APK): lọc log, bỏ password, đóng zip, gửi. Test:
  `tests/test_bug_report.py`.
- `run_party_digioi.bao_loi(pidx, mo_ta, app_info)` (PC) / `bao_loi_json` (APK, trả chuỗi JSON).
  Config đọc từ `config` LÚC CHẠY (`PARTY_CONFIG`, `PARTIES`, `ACCOUNT_*`) → giống nhau hai bản.
- Nhãn acc: `client._dat_nhan_log` ghi `[username] NHAN LOG -> 'ten'` mỗi lần nhãn đổi → bộ lọc
  học nhãn mới từ chính log. Cộng thêm nhãn của client đang sống làm mốc.
- Sửa 07/10: `EP DONG BO` và `DIEU KHIEN TU XA` từng ghi `[party pidx]` (đếm từ 0, lệch 1 so với
  mọi dòng khác) → nay `pidx + 1`, không thì lọc gán nhầm sang party bên cạnh.
- PC: `gui.py` `_build_party_tab` nút `side="right"`, hộp `_bao_loi`.
- APK: nút thứ 4 hàng "Đổi kênh / Đổi thành / Giftcode" (`PartyCard`), `BugReportDialog`,
  `BotForegroundService.bugReport`.
