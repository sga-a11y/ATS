package com.tsbot.android

data class Party(
    val name: String,
    val serverKey: String,
    val runMode: String = RunModes.STAND_STILL,
    val cityKey: String = Cities.ALL.keys.first(),
    val accounts: List<Account> = emptyList(),
)
