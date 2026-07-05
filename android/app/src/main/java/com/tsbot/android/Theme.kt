package com.tsbot.android

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Bang mau app (dark theme - hop app bot game, do choi mat khi nhin lau). Dung mot bang
// mau CO DINH (khong dynamic color theo he thong) de UI nhat quan tren moi may/Android.
private val Emerald = Color(0xFF34D399)   // accent chinh (nut/hanh dong)
private val EmeraldDark = Color(0xFF059669)
private val SlateBg = Color(0xFF0F172A)   // nen app
private val SlateSurface = Color(0xFF1E293B)   // card party
private val SlateSurfaceHi = Color(0xFF334155)   // card account (noi len tren party)
private val SlateText = Color(0xFFE2E8F0)
private val SlateTextDim = Color(0xFF94A3B8)

// Mau trang thai account - dung o cham trang thai + thanh/nhan (xem statusColor()).
val StatusRunning = Color(0xFF22C55E)   // dang chay - xanh la
val StatusConnecting = Color(0xFFF59E0B)   // dang ket noi - vang
val StatusError = Color(0xFFEF4444)   // loi - do
val StatusStopped = Color(0xFF64748B)   // da dung - xam
val StatusIdle = Color(0xFF475569)   // chua chay - xam dam

val HpColor = Color(0xFF22C55E)   // thanh HP - xanh la
val SpColor = Color(0xFF3B82F6)   // thanh SP - xanh duong

private val TsColorScheme = darkColorScheme(
    primary = Emerald,
    onPrimary = Color(0xFF06251A),
    primaryContainer = EmeraldDark,
    onPrimaryContainer = Color(0xFFD1FAE5),
    secondary = Color(0xFF60A5FA),
    background = SlateBg,
    onBackground = SlateText,
    surface = SlateSurface,
    onSurface = SlateText,
    surfaceVariant = SlateSurfaceHi,
    onSurfaceVariant = SlateTextDim,
    error = StatusError,
    outline = SlateSurfaceHi,
)

/** Mau ung voi trang thai account (cham + nhan). */
fun statusColor(state: RunState): Color = when (state) {
    RunState.RUNNING -> StatusRunning
    RunState.CONNECTING -> StatusConnecting
    RunState.ERROR -> StatusError
    RunState.STOPPED -> StatusStopped
    RunState.IDLE -> StatusIdle
}

/** Nhan tieng Viet cho trang thai (thay cho ten enum tho "RUNNING"). */
fun statusLabel(state: RunState): String = when (state) {
    RunState.RUNNING -> "Đang chạy"
    RunState.CONNECTING -> "Đang kết nối"
    RunState.ERROR -> "Lỗi"
    RunState.STOPPED -> "Đã dừng"
    RunState.IDLE -> "Chưa chạy"
}

@Composable
fun TsBotTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = TsColorScheme,
        typography = Typography(),
        content = content,
    )
}
