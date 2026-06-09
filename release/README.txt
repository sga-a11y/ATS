==========================================================
   TS ONLINE - BOT TREO MAY / TRAIN PARTY  (huong dan)
==========================================================

YEU CAU:
  - Python 3.8 tro len (https://www.python.org/downloads/)
    Khi cai NHO TICH "Add Python to PATH".
  - KHONG can cai thu vien gi them (chi dung thu vien chuan).

----------------------------------------------------------
BUOC 1: TAO FILE CAU HINH
----------------------------------------------------------
  - Vao thu muc "bot", COPY file:  config.example.py  ->  config.py
  - Mo bot/config.py, sua:
      * PARTIES: dien tai khoan (username, password).
          - SLOT 0 = CHU PARTY (bot tu moi + dan train).
          - Slot 1-4 = thanh vien.
          - Moi party toi da 5 acc. Co the nhieu party.
      * START_CITY_ID quyet dinh CHE DO:
          - = 49942 (hoac 0)        -> train DI GIOI (chay long vong)
          - = map_id co trong train_maps.json -> train MAP THUONG
            (vd 12831 = Rung Noi Huynh)
          - = ID 1 thanh (vd 12061) -> ve thanh dung cho (dung voi run_bot)

----------------------------------------------------------
BUOC 2: CHAY BOT
----------------------------------------------------------
  CACH 1 - Train party (Di Gioi / map thuong):
     Double-click:  run_digioi.bat
       (login het acc -> vao DG / map -> lap party -> quan su -> cay)

  CACH 2 - Treo may / member cho chu party moi:
     Double-click:  run_bot.bat
       (login -> dung cho -> tu nhan loi moi party + tu danh)

  Dong cua so hoac Ctrl+C de dung. Bi rot mang -> tu dong ket noi lai.

----------------------------------------------------------
THEM DIEM TRAIN MAP THUONG (train_maps.json)
----------------------------------------------------------
  - Login 1 acc vao map muon cay -> xem dong log:  >>> MAP HIEN TAI = X <<<
  - Mo train_maps.json, them:
      "X": { "name":"Ten map", "safe":[x,y], "mobs":[[x,y]] }
    * safe = toa do AN TOAN (tap ket lap party)
    * mobs[0] = toa do CO QUAI (leader ra dung cay) - bot dung diem dau tien
    * Toa do = DUNG toa do hien trong game (UI).
  - Doi diem dung cay: sua mobs[0] thanh toa do moi.

----------------------------------------------------------
GHI CHU
----------------------------------------------------------
  - File trong "bot/config.py" la cua RIENG ban (tai khoan) - KHONG chia se.
  - Cac file checkin_state.json / gift_state.json ... tu sinh khi chay.
  - Bot tu lam hang ngay: diem danh, qua online, qua quan doan, exp offline, mail.
