package com.tsbot.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class AccountStore(private val context: Context) {
    private val file = File(context.filesDir, "accounts.json")

    fun load(): List<Account> {
        if (!file.exists()) return emptyList()
        val arr = JSONArray(file.readText())
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            Account(o.getString("username"), o.getString("password"), o.getString("server_key"))
        }
    }

    fun save(accounts: List<Account>) {
        val arr = JSONArray()
        accounts.forEach { a ->
            val o = JSONObject()
            o.put("username", a.username)
            o.put("password", a.password)
            o.put("server_key", a.serverKey)
            arr.put(o)
        }
        file.writeText(arr.toString())
    }

    fun add(account: Account) {
        val current = load().filterNot { it.username == account.username }
        save(current + account)
    }

    fun remove(username: String) {
        save(load().filterNot { it.username == username })
    }
}
