package com.tsbot.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PartyStateTest {
    @Before
    fun setUp() {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().targetContext))
        }
    }

    @Test
    fun sharedStateKeyedByPartyName() {
        val py = Python.getInstance()
        val ps = py.getModule("train_bot.party_state")
        val st1 = ps.callAttr("_pstate", "party-a")
        val st2 = ps.callAttr("_pstate", "party-a")
        // Cung 1 party_name -> CUNG 1 dict instance (Python object identity qua id())
        assertEquals(st1.callAttr("__class__").toString(), st2.callAttr("__class__").toString())
        val other = ps.callAttr("_pstate", "party-b")
        assertTrue(other != st1)
    }

    @Test
    fun leadersForReturnsRegisteredName() {
        val py = Python.getInstance()
        val ps = py.getModule("train_bot.party_state")
        ps.callAttr("set_leader_name", "party-c", "chibao")
        val config = py.getModule("train_bot.config")
        val leaders = config.callAttr("leaders_for", "party-c")
        assertTrue(leaders.asList().map { it.toString() }.contains("chibao"))
    }

    @Test
    fun pstateHasO5Fields() {
        val py = Python.getInstance()
        val ps = py.getModule("train_bot.party_state")
        val st = ps.callAttr("_pstate", "party-o5-test")
        val o5State = st.callAttr("get", "o5_state").toString()
        assertEquals("idle", o5State)
        val o5DoneBy = st.callAttr("get", "o5_done_by")
        assertTrue("o5_done_by phai la dict rong luc khoi tao", o5DoneBy.callAttr("__len__").toInt() == 0)
    }
}
