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
    // false = so kenh tren KHONG duoc server xac nhan (lenh doi kenh gan nhat hong) -> UI them `?`.
    // Game khong co lenh hoi "toi dang o kenh nao" (KNOWLEDGE.md muc 7), nen `channel` la gia tri
    // server day den lan cuoi va no SAI duoc. Ban PC hien `5?`; day la ban sao cho APK.
    // THAM SO MOI DAT CUOI: Kotlin goi constructor theo VI TRI o vai cho.
    val channelChac: Boolean = true,
)
