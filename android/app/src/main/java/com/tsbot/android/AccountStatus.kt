package com.tsbot.android

enum class RunState { IDLE, CONNECTING, RUNNING, ERROR, STOPPED }

data class AccountStatus(
    val state: RunState = RunState.IDLE,
    val hp: Int? = null,
    val sp: Int? = null,
    val hpMax: Int? = null,
    val spMax: Int? = null,
    val charName: String = "",
    val charLevel: Int? = null,
    val petName: String = "",
    val petLevel: Int? = null,
    val partyAvgLevel: Int? = null,
    val mapId: Int? = null,
    val channel: Int? = null,
    val message: String = "",
)
