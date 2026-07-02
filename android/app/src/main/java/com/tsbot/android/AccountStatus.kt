package com.tsbot.android

enum class RunState { IDLE, CONNECTING, RUNNING, ERROR, STOPPED }

data class AccountStatus(
    val state: RunState = RunState.IDLE,
    val hp: Int? = null,
    val sp: Int? = null,
    val hpMax: Int? = null,
    val spMax: Int? = null,
    val message: String = "",
)
