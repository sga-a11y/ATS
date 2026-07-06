package com.tsbot.android

/** Danh sach che do chay (khop dung 1-1 voi "mode" cua run_party_digioi.py: PC chi co 1 mode
 * "digioi" duy nhat, party-hay-solo la 1 SUB-OPTION rieng (pcfg["digioi_mode"]=="solo") BEN
 * TRONG mode do, KHONG phai 2 mode tach biet):
 *  - STAND_STILL: ve 1 thanh (city_key) roi dung yen.
 *  - STAY_LOGIN: KHONG ve thanh - dung nguyen tai cho login (mirror START_CITY_ID=0 ben PC).
 *  - DIGIOI: vao Di Gioi - party.digioiSolo quyet dinh chay party that hay solo doc lap.
 * Chua co du lieu toa do di chuyen theo tung map nen chua ho tro tu dong di lang thang. */
object RunModes {
    const val STAND_STILL = "stand_still"
    const val STAY_LOGIN = "stay_login"
    const val DIGIOI = "digioi"
    const val TRAIN = "train"
    const val EVENT = "event"

    val ALL: Map<String, String> = mapOf(
        STAND_STILL to "Đứng yên tại thành",
        STAY_LOGIN to "Login ở đâu đứng yên đó",
        DIGIOI to "Dị Giới",
        TRAIN to "Train (map bản đồ)",
        EVENT to "Event (tele đứng đợi mời PT)",
    )
}
