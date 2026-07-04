package com.tsbot.android

/** Danh sach che do chay:
 *  - STAND_STILL: ve 1 thanh (city_key) roi dung yen.
 *  - STAY_LOGIN: KHONG ve thanh - dung nguyen tai cho login (mirror START_CITY_ID=0 ben PC).
 * Chua co du lieu toa do di chuyen theo tung map nen chua ho tro tu dong di lang thang. */
object RunModes {
    const val STAND_STILL = "stand_still"
    const val STAY_LOGIN = "stay_login"

    val ALL: Map<String, String> = mapOf(
        STAND_STILL to "Đứng yên tại thành",
        STAY_LOGIN to "Login ở đâu đứng yên đó",
    )
}
