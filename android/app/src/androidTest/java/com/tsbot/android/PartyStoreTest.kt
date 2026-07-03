package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.assertEquals

@RunWith(AndroidJUnit4::class)
class PartyStoreTest {
    @Test
    fun addPartyThenLoadReturnsSameParty() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = PartyStore(ctx)
        store.save(emptyList())
        store.addParty(Party("Nhom 1", "hoang_trung", accounts = listOf(Account("hoangt306", "pw123"))))
        val loaded = store.load()
        assertEquals(1, loaded.size)
        assertEquals("Nhom 1", loaded[0].name)
        assertEquals("hoang_trung", loaded[0].serverKey)
        assertEquals(1, loaded[0].accounts.size)
        assertEquals("hoangt306", loaded[0].accounts[0].username)
        store.save(emptyList())
    }

    @Test
    fun removePartyDeletesIt() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = PartyStore(ctx)
        store.save(emptyList())
        store.addParty(Party("p1", "trieu_van"))
        store.addParty(Party("p2", "trieu_van"))
        store.removeParty("p1")
        val loaded = store.load()
        assertEquals(1, loaded.size)
        assertEquals("p2", loaded[0].name)
        store.save(emptyList())
    }

    @Test
    fun addAccountToPartyThenRemoveIt() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = PartyStore(ctx)
        store.save(emptyList())
        store.addParty(Party("p1", "trieu_van"))
        store.addAccountToParty("p1", Account("acc1", "pw"))
        store.addAccountToParty("p1", Account("acc2", "pw"))
        var loaded = store.load()
        assertEquals(2, loaded[0].accounts.size)

        store.removeAccountFromParty("p1", "acc1")
        loaded = store.load()
        assertEquals(1, loaded[0].accounts.size)
        assertEquals("acc2", loaded[0].accounts[0].username)
        store.save(emptyList())
    }

    @Test
    fun runModeDefaultsToStandStillAndRoundTrips() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val store = PartyStore(ctx)
        store.save(emptyList())
        store.addParty(Party("p1", "trieu_van"))
        assertEquals(RunModes.STAND_STILL, store.load()[0].runMode)

        store.updateParty("p1", Party("p1", "trieu_van", runMode = RunModes.STAND_STILL))
        assertEquals(RunModes.STAND_STILL, store.load()[0].runMode)
        store.save(emptyList())
    }
}
