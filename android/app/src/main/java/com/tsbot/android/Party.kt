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
    val accounts: List<Account> = emptyList(),
)
