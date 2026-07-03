package com.tsbot.android

/** Danh sach che do chay - hien chi co "dung yen tai thanh" (an toan nhat, chua co du
 * lieu toa do di chuyen theo tung map nen chua ho tro tu dong di lang thang). */
object RunModes {
    const val STAND_STILL = "stand_still"

    val ALL: Map<String, String> = mapOf(
        STAND_STILL to "Đứng yên tại thành",
    )
}
