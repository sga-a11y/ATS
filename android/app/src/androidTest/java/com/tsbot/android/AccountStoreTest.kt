package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals

@RunWith(AndroidJUnit4::class)
class AccountStoreTest {
    @Test
    fun addThenLoadReturnsSameAccount() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = AccountStore(ctx)
        store.save(emptyList())
        store.add(Account("hoangt306", "pw123", "hoang_trung"))
        val loaded = store.load()
        assertEquals(1, loaded.size)
        assertEquals("hoangt306", loaded[0].username)
        assertEquals("hoang_trung", loaded[0].serverKey)
        store.save(emptyList())
    }

    @Test
    fun removeDeletesAccount() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = AccountStore(ctx)
        store.save(emptyList())
        store.add(Account("acc1", "pw", "trieu_van"))
        store.add(Account("acc2", "pw", "trieu_van"))
        store.remove("acc1")
        val loaded = store.load()
        assertEquals(1, loaded.size)
        assertEquals("acc2", loaded[0].username)
        store.save(emptyList())
    }
}
