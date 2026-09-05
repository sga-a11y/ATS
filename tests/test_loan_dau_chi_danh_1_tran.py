"""LOAN DAU: tick "Chi danh 1 tran" -> danh xong tran dau la ra khoi map event + tat acc.

User chot 01/09: "khi chon event Loan dau -> m them cai tick 'Chi danh 1 tran'. Mac dinh la ko
tick, tick cai nay thi chi vao danh 1 tran roi thoat event (chay ra ngoai roi tat acc)".

Ket thuc y het nhanh HET GIO da co san: dat `client._loandau_done = True` -> vong chinh trong
`run_party_digioi` goi `_loandau_ra_khoi_map()` roi `c.close()`.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import loandau                  # noqa: E402


class _Bot:
    """Client gia: moi lan 'dang ky' la vao tran roi het tran ngay."""

    def __init__(self):
        self._label = "t"
        self.running = True
        self._loandau_create_seq = 0
        self._loandau_end_seq = 0
        self._loandau_wins = 0
        self._loandau_done = False
        self.so_tran = 0

    def navigate_to(self, *a, **k):
        return True

    def _wait_combat_clear(self, **k):
        return True

    def rearm_ready(self):
        pass


class _Stop:
    def is_set(self):
        return False


def _chay(mot_tran, so_tran_toi_da=4):
    """Chay run_loop THAT, chi gia lap `dang_ky` + dong ho.

    `_cho()` dung `time.time()` that va chi ngu bang `sleep_fn` -> sleep_fn KHONG duoc rong, neu
    khong vong cho se quay khong (busy-loop) den het `wait_battle_sec` giay THAT.
    Nen `sleep_fn` o day dong vai "thoi gian troi": moi nhip thi ket thuc tran dang danh.
    """
    bot = _Bot()
    goi = {"n": 0}

    def _dang_ky(client, stop_event, sleep_fn, poll_interval, ev=None):
        # `ev` = bien the theo THU (t3/t7) - stub phai nhan de khong vo khi run_loop truyen.
        client._loandau_create_seq += 1      # da ghep tran -> vao tran
        client.so_tran += 1
        goi["n"] += 1
        return True

    def _sleep(_giay=0.0):
        # het tran ngay o nhip cho dau tien
        bot._loandau_end_seq = bot._loandau_create_seq

    cu = loandau.dang_ky
    loandau.dang_ky = _dang_ky
    try:
        loandau.run_loop(
            bot, (0, 0), _Stop(), None, sleep_fn=_sleep,
            window_fn=lambda: goi["n"] < so_tran_toi_da,   # "het gio" sau N tran
            mot_tran=mot_tran,
        )
    finally:
        loandau.dang_ky = cu
    return bot


class TestChiDanh1Tran(unittest.TestCase):
    def test_KHONG_tick_thi_danh_toi_het_gio(self):
        bot = _chay(mot_tran=False, so_tran_toi_da=4)
        self.assertEqual(bot.so_tran, 4)
        self.assertTrue(bot._loandau_done)

    def test_CO_tick_thi_dung_sau_tran_DAU(self):
        bot = _chay(mot_tran=True, so_tran_toi_da=4)
        self.assertEqual(bot.so_tran, 1, "danh qua 1 tran -> tick khong co tac dung")

    def test_CO_tick_van_dat_loandau_done(self):
        """`_loandau_done` la tin hieu DUY NHAT de vong chinh ra khoi map + tat acc."""
        self.assertTrue(_chay(mot_tran=True)._loandau_done)


class TestNoiDayDuTuGUI(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.rpd = fh.read()
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            self.gui = fh.read()
        with io.open(os.path.join(ROOT, "bot", "config.py"), encoding="utf-8") as fh:
            self.cfg = fh.read()

    def test_config_doc_tu_accounts_json(self):
        self.assertIn('"loandau_mot_tran": bool(_party.get("loandau_mot_tran", False))', self.cfg)

    def test_runner_truyen_xuong_vong_loan_dau(self):
        self.assertIn('_mot_tran = bool(pcfg.get("loandau_mot_tran"))', self.rpd)
        self.assertIn("mot_tran=_mot_tran", self.rpd)

    def test_gui_luu_khi_bam_OK(self):
        self.assertIn('data["loandau_mot_tran"] = bool(self.loandau_mot_tran_var.get())', self.gui)

    def test_gui_mac_dinh_KHONG_tick(self):
        i = self.gui.find("self.loandau_mot_tran_var = tk.BooleanVar(")
        self.assertGreater(i, 0)
        self.assertIn('self._preset.get("loandau_mot_tran", False)', self.gui[i:i + 220])

    def test_tick_nam_NGAY_BEN_PHAI_o_chon_event(self):
        """User chot: "them dau tick ngay ben phai cho chon Loan dau"."""
        i_cb = self.gui.find("self.event_cb.pack(side=\"left\")")
        i_tick = self.gui.find('text="Chỉ đánh 1 trận"')
        self.assertGreater(i_tick, i_cb)
        self.assertIn('pack(side="left"', self.gui[i_tick:i_tick + 260])

    def test_chi_bat_cho_event_LOAN_DAU(self):
        """Neo theo du lieu (`party_battle.kind`), khong hardcode key/nhan."""
        self.assertIn('(_ev.get("party_battle") or {}).get("kind") == "chaos_vs"', self.gui)


class TestAPKCoDuTinhNang(unittest.TestCase):
    def _kt(self, ten):
        with io.open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                                  "android", ten), encoding="utf-8") as fh:
            return fh.read()

    def test_Events_kt_DOC_JSON_khong_chep_tay(self):
        """Ban chep tay da lam APK THIEU HAN event Loan dau (PC 3 event, APK 2)."""
        s = self._kt("Events.kt")
        self.assertIn('context.assets.open("train_bot_data/events.json")', s)
        self.assertIn("fun init(", s)

    def test_FALLBACK_phu_du_event_cua_PC(self):
        import json
        with io.open(os.path.join(ROOT, "events.json"), encoding="utf-8") as fh:
            keys = set((json.load(fh).get("events") or {}))
        s = self._kt("Events.kt")
        i = s.find("private val FALLBACK")
        for k in keys:
            self.assertIn('"%s" to Info(' % k, s[i:], "FALLBACK thieu event %s" % k)

    def test_init_duoc_goi_o_ca_hai_diem_vao(self):
        for ten in ("MainActivity.kt", "BotForegroundService.kt"):
            self.assertIn("Events.init(applicationContext)", self._kt(ten), ten)

    def test_party_co_truong_va_luu_xuong_json(self):
        self.assertIn("val loanDauMotTran: Boolean = false", self._kt("Party.kt"))
        st = self._kt("PartyStore.kt")
        self.assertIn('o.optBoolean("loandau_mot_tran", false)', st)
        self.assertIn('o.put("loandau_mot_tran", p.loanDauMotTran)', st)

    def test_truyen_xuong_python_o_CUOI_signature(self):
        """`setup_party_runtime` nhan theo VI TRI -> chen vao giua la lech het tham so sau."""
        s = self._kt("BotForegroundService.kt")
        i = s.find("party.diGioiPick,")
        self.assertGreater(i, 0)
        self.assertIn("party.loanDauMotTran,", s[i:i + 260])

    def test_python_nhan_them_tham_so_o_CUOI(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def setup_party_runtime(")
        than = s[i:s.find("):", i)]
        self.assertIn("loandau_mot_tran=False", than)
        self.assertLess(than.find("di_gioi_pick"), than.find("loandau_mot_tran"))

    def test_UI_co_tick_va_chi_hien_voi_loan_dau(self):
        s = self._kt("MainActivity.kt")
        self.assertIn("Chỉ đánh 1 trận", s)
        self.assertIn("Events.ALL[selectedCity]?.motTranDuoc == true", s)


if __name__ == "__main__":
    unittest.main()
