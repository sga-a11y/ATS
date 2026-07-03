package com.tsbot.android

data class Party(
    val name: String,
    val serverKey: String,
    val accounts: List<Account> = emptyList(),
)
