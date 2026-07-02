package com.tsbot.android

import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        val py = Python.getInstance()
        val module = py.getModule("smoke_login")

        val userInput = EditText(this)
        userInput.hint = "Tài khoản"

        val passInput = EditText(this)
        passInput.hint = "Mật khẩu"
        passInput.inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD

        val serverLabels: List<PyObject> = module.callAttr("server_labels").asList()
        val serverKeys = serverLabels.map { it.asList()[0].toString() }
        val serverNames = serverLabels.map { it.asList()[1].toString() }

        val serverSpinner = Spinner(this)
        serverSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, serverNames)

        val status = TextView(this)
        status.text = "Nhập tài khoản, mật khẩu, chọn server rồi bấm Đăng nhập"

        val loginBtn = Button(this)
        loginBtn.text = "Đăng nhập"
        loginBtn.setOnClickListener {
            val username = userInput.text.toString()
            val password = passInput.text.toString()
            val serverKey = serverKeys[serverSpinner.selectedItemPosition]
            if (username.isBlank() || password.isBlank()) {
                status.text = "Vui lòng nhập đủ tài khoản và mật khẩu"
                return@setOnClickListener
            }
            status.text = "Đang đăng nhập..."
            loginBtn.isEnabled = false
            thread {
                try {
                    val result = module.callAttr("run_smoke_test", username, password, serverKey).asList()
                    val ok = result[0].toBoolean()
                    val msg = result[1].toString()
                    runOnUiThread {
                        status.text = msg
                        loginBtn.isEnabled = true
                    }
                } catch (e: Exception) {
                    runOnUiThread {
                        status.text = "Lỗi: ${e.message}"
                        loginBtn.isEnabled = true
                    }
                }
            }
        }

        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        val pad = (16 * resources.displayMetrics.density).toInt()
        layout.setPadding(pad, pad, pad, pad)
        layout.addView(userInput)
        layout.addView(passInput)
        layout.addView(serverSpinner)
        layout.addView(loginBtn)
        layout.addView(status)
        setContentView(layout)
    }
}
