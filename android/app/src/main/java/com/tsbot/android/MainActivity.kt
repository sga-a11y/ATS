package com.tsbot.android

import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        val status = TextView(this)
        status.text = "TS Bot Android - Phase 1 (foundation)"
        val btn = Button(this)
        btn.text = "Smoke test login (xem Logcat)"
        btn.setOnClickListener {
            thread {
                try {
                    val module = Python.getInstance().getModule("smoke_login")
                    val ok = module.callAttr("run_smoke_test").toBoolean()
                    runOnUiThread { status.text = "Smoke test: ${if (ok) "OK - nhan duoc frame" else "THAT BAI"}" }
                } catch (e: Exception) {
                    // KHONG de loi (vd GAME_HOST con la "CHANGE_ME" -> gaierror) lam CRASH ca app -
                    // hien loi ngay tren man hinh de biet ma sua, thay vi app dong dot ngot.
                    runOnUiThread { status.text = "Smoke test LOI: ${e.message}" }
                }
            }
        }
        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        layout.addView(status)
        layout.addView(btn)
        setContentView(layout)
    }
}
