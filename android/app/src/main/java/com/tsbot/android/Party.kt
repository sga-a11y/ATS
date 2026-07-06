package com.tsbot.android

data class Party(
    val name: String,
    val serverKey: String,
    val runMode: String = RunModes.STAND_STILL,
    val cityKey: String = Cities.ALL.keys.first(),
    // Chi dung khi runMode == RunModes.DIGIOI: true = SOLO (moi acc doc lap, khong lap party,
    // khong dong bo kenh) | false = lap party that (leader moi, member accept). Mirror PC's
    // pcfg["digioi_mode"] == "solo" - 1 sub-option BEN TRONG mode "digioi", KHONG phai 2 mode
    // rieng biet o dropdown chinh.
    val digioiSolo: Boolean = false,
    // Chi dung khi runMode == RunModes.DIGIOI va digioiSolo == false (party that): true = "Khong
    // co chu PT" (khong account nao lam leader - moi account la member, dung yen cho leader
    // NGOAI/tay moi party that su, KHONG tu invite, KHONG tu dong reconnect khi rot). Mirror PC's
    // no_leader_var (gui.py) / has_leader = PARTY_LEADER_ACC.get(pidx) is not None.
    val noLeader: Boolean = false,
    // Lam nhiem vu hang ngay (bingo 9 o: phó bản đơn, boss thế giới, gacha, hợp đồ... + nhan
    // thuong). Mirror PC's do_daily (gui.py). CHUA duoc noi vao logic chay nao (UI-only, se lam
    // sau) - gia tri mac dinh True khop PC's default.
    val doDaily: Boolean = true,
    val accounts: List<Account> = emptyList(),
)
