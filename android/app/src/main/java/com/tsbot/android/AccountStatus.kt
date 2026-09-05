package com.tsbot.android

enum class RunState { IDLE, CONNECTING, RUNNING, ERROR, STOPPED }

data class AccountStatus(
    val state: RunState = RunState.IDLE,
    val hp: Int? = null,
    val sp: Int? = null,
    val hpMax: Int? = null,
    val spMax: Int? = null,
    val charName: String = "",
    // NHAN LOG that su in ra dau dong log: bang charName, TRU khi trung ten voi acc
    // khac thi la "ten~username" (xem _NHAN_CHU trong bot/client.py).
    val logLabel: String = "",
    val charLevel: Int? = null,
    val charAgi: Int? = null,
    val petName: String = "",
    val petLevel: Int? = null,
    val petAgi: Int? = null,
    // Trung thanh pet DANG DUNG (0..100). < 40 -> canh bao CAM o Check AGI (user chot 05/09).
    val petFaith: Int? = null,
    val partyAvgLevel: Int? = null,
    val mapId: Int? = null,
    val channel: Int? = null,
    val message: String = "",
)
