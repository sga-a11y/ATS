==========================================================
   TS ONLINE - BOT TREO MAY / TRAIN PARTY  (huong dan)
==========================================================

YEU CAU:
  - Python 3.8 tro len (https://www.python.org/downloads/)
    Khi cai NHO TICH "Add Python to PATH".
  - KHONG can cai thu vien gi them (chi dung thu vien chuan).

----------------------------------------------------------
BUOC 1: TAO FILE CONFIG GOC (1 lan)
----------------------------------------------------------
  - Vao thu muc "bot", COPY:  config.example.py  ->  config.py
    (giu nguyen, KHONG can sua gi - chi giu hang so game: API, server...)

----------------------------------------------------------
BUOC 2: MO GIAO DIEN (GUI) - dat cau hinh + chay
----------------------------------------------------------
  Double-click:  run_gui.bat     (hoac chay: python gui.py)

  Trong GUI:
    1. Bam  [Cau hinh]  -> moi PARTY 1 tab, dat:
         - Server   : Trieu Van / Tao Thao (dropdown)
         - Che do   : Train Di Gioi | Train map | Tap trung ve thanh | Dung yen
         - Map/Quai/Thanh (dropdown - tuy che do)
         - [v] Khong co chu PT  (neu muon member cho leader tay moi)
         - [v] Danh daily dungeon
         - Danh sach acc: moi dong "user,pass" (DONG DAU = chu PT).
             Them '#' dau dong de TAM TAT acc do.
       -> Bam [Luu]  (tu nap lai, khong can dong app).

    2. Bam  [START TAT CA]  hoac  [Start party] / [Start acc chon].
    3. Bang trang thai live: nhan vat / map / kenh / trong party / DG con / danh.
    4. Khung Log: bam tab party hoac chon acc de LOC log theo party/acc.

  -> Cau hinh luu vao  accounts.json  (GUI tu tao/sua, co chua mat khau).

----------------------------------------------------------
CHE DO (mode) moi party
----------------------------------------------------------
  - Train Di Gioi      : vao Di Gioi chay long vong train (het gio -> dungeon).
  - Train map          : char PHAI dung san tren map train -> ra diem quai cay.
  - Tap trung ve thanh : teleport ve thanh roi dung yen (dan di nhiem vu tay).
  - Dung yen           : login dau dung yen do.

----------------------------------------------------------
DATA (sua bang file json neu can)
----------------------------------------------------------
  - servers.json    : server (ip + id auth). Them server moi o day.
  - train_maps.json : map train (diem an toan + diem quai).
  - cities.json     : thanh de teleport.
  - pets.json       : pet (skill train + boss_skill danh dungeon).

  Chi tiet cau truc config: xem file  CONFIG.md.

----------------------------------------------------------
GHI CHU
----------------------------------------------------------
  - Dong cua so GUI hoac bam Stop de dung. Bi rot mang -> tu ket noi lai.
  - Tat ca acc thoat -> GUI bao ro ly do (sai map / het gio DG / login loi).
  - File log: party.log.
  - CLI cu (khong GUI): chay  python run_party_digioi.py
