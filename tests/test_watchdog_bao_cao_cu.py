"""Watchdog KHONG duoc ep dong bo dua tren BAO CAO CU.

BUG THAT (party 19 va 35): acc roi vong cho roi di lam viec khac ma KHONG AI doi pha -> bao cao
ket lai o "reform: da ve thanh..., cho ca party" mai mai. Watcher khong xet TUOI bao cao nen thay
"ca party deu cho" -> cu 120s ep dong bo mot lan, KEO CA PARTY DANG CHAY TOT ve thanh.

Log chung minh party khong he ket:
    10:05:12 watcher: "CA PARTY DEU DANG CHO"
    10:05:16 leader : "sync kenh/map OK: 5/5 acc o map 21011"
    10:05:24 leader : "reform: 4/4 member join lai -> KEO qua cong ra train map"
    10:05:40          dang danh nhau binh thuong
    10:07:12 watcher: "cho nhau 120s -> DEADLOCK, EP DONG BO"   <- oan

PHAN BIET: acc cho THAT lam moi bao cao MOI VONG LAP (~1-2s) nen tuoi luon ~1s; bao cao GIA thi
tuoi tang vo han.

LUU Y THIET KE (de khong ai "don dep" nham): `waiting` van GIU nguyen cho LA CHAN (muc 3, chan bo
do "lech viec"), chi luat DEADLOCK (muc 1) moi dung `waiting_tuoi`. Vong cho DG
("xong Di Gioi - cho ca party xong") set bao cao DUNG 1 LAN roi ngu 5s/vong, cho co the toi 2
TIENG -> bao cao luon "gia"; doi la chan sang waiting_tuoi se lam acc do mat che chan.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")


def cau_lenh(than, bat_dau):
    """Lay tron cau gan bat dau bang `bat_dau` (gom ca dong noi tiep).

    KHONG dung regex \[.*?\]: no dung ngay o dau `]` cua `d["age"]` -> cat cut cau, test bat nham.
    """
    dong = than.split(chr(10))
    for i, d in enumerate(dong):
        if d.strip().startswith(bat_dau):
            ra = [d]
            while ra[-1].count("[") > ra[-1].count("]") or ra[-1].rstrip().endswith(","):
                i += 1
                ra.append(dong[i])
            return chr(10).join(ra)
    raise AssertionError("khong thay cau %r" % bat_dau)


def khoi_watcher():
    i = SRC.index("def _party_watcher(")
    j = SRC.index("\ndef ", i + 10)
    return SRC[i:j]


class TestLuatDeadlockDungBaoCaoTuoi(unittest.TestCase):
    def setUp(self):
        self.than = khoi_watcher()

    def test_co_danh_sach_rieng_cho_bao_cao_tuoi(self):
        self.assertIn("waiting_tuoi", self.than)
        cau = cau_lenh(self.than, "waiting_tuoi =")
        self.assertIn("WATCH_WAIT_FRESH_SEC", cau)
        self.assertIn('d["age"]', cau, "khong he xet tuoi bao cao")

    def test_luat_DEADLOCK_dung_waiting_tuoi(self):
        m = re.search(r"if waiting\w* and len\(waiting\w*\) == len\(live\):", self.than)
        self.assertIsNotNone(m, "khong tim thay dieu kien deadlock")
        self.assertIn("waiting_tuoi", m.group(0),
                      "luat deadlock van dung `waiting` (bao cao cu) -> ep dong bo oan")

    def test_LA_CHAN_van_dung_waiting_DAY_DU(self):
        """Muc (3) phai giu `waiting`: acc cho DG ca tieng co bao cao 'gia' nhung VAN phai che
        chan khoi bo do 'lech viec'."""
        i = self.than.index("cho la HOP LE")
        doan = self.than[i:i + 700]
        m = re.search(r"^\s*if (waiting\w*):", doan, re.M)
        self.assertIsNotNone(m, "khong tim thay la chan")
        self.assertEqual(m.group(1), "waiting",
                         "la chan bi doi sang waiting_tuoi -> acc cho DG ca tieng mat che chan")

    def test_nguong_tuoi_rong_hon_han_nhip_lam_moi(self):
        m = re.search(r"WATCH_WAIT_FRESH_SEC = (\d+)", SRC)
        self.assertIsNotNone(m)
        nguong = int(m.group(1))
        # cac vong cho lam moi ~1-2s -> nguong phai rong hon nhieu de khong cat oan
        self.assertGreaterEqual(nguong, 10)
        self.assertLess(nguong, int(re.search(r"WATCH_ALLWAIT_SEC = (\d+)", SRC).group(1)))

    def test_stuck_van_mien_tru_pha_wait(self):
        """Khong duoc nhan tien bat acc cho lam 'treo' - do la thay doi KHAC, khong nam trong
        pham vi sua nay."""
        self.assertIn("_PHASE_WAIT", cau_lenh(self.than, "stuck ="))


class TestKhongLamWatchdogHANH_DONG_THEM(unittest.TestCase):
    """Thay doi nay chi duoc lam watchdog BOT hanh dong, khong duoc them."""

    def test_waiting_tuoi_luon_la_tap_con_cua_waiting(self):
        than = khoi_watcher()
        m = re.search(r"for u, d in (\w+)", cau_lenh(than, "waiting_tuoi ="))
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "waiting",
                         "waiting_tuoi phai loc TU waiting, khong duoc lay tu live")


class TestChayWatcherTHAT(unittest.TestCase):
    """Khong chi quet ma: cho _party_watcher CHAY THAT roi xem no co ep dong bo khong."""

    PIDX = 77

    def _chay(self, tuoi, so_acc=3, giay_cho=200):
        """tuoi = tuoi bao cao (giay). Tra ve so lan request_party_resync duoc goi."""
        import sys
        import threading
        from unittest import mock
        with mock.patch.object(sys, "argv", [sys.argv[0]]):
            import run_party_digioi as R

        accs = ["acc%d" % i for i in range(so_acc)]
        goi = []
        t0 = [0.0]

        def _task(u):
            return {"task": "reform: da ve thanh, cho ca party", "phase": "wait", "age": tuoi}

        # dong ho gia: moi lan goi nhay 30s -> vuot WATCH_ALLWAIT_SEC(120) sau vai vong
        def _time():
            t0[0] += 30.0
            return t0[0]

        st = R._pstate(self.PIDX)
        st["reconnecting"] = set()
        dung = threading.Event()

        def _sleep(_s):
            if dung.is_set():
                raise SystemExit
        with mock.patch.object(R, "party_accounts",
                               return_value=[(u, "", "", "") for u in accs]),              mock.patch.object(R, "is_account_running", return_value=True),              mock.patch.object(R, "get_account_task", side_effect=_task),              mock.patch.object(R, "request_party_resync",
                               side_effect=lambda *a, **k: goi.append(a)),              mock.patch.object(R.time, "sleep", side_effect=_sleep),              mock.patch.object(R.time, "time", side_effect=_time),              mock.patch.object(R, "account_clients", {}):
            def _chay_thread():
                try:
                    R._party_watcher(self.PIDX)
                except SystemExit:
                    pass
            th = threading.Thread(target=_chay_thread, daemon=True)
            th.start()
            th.join(timeout=3)
            dung.set()
            th.join(timeout=3)
        return len(goi)

    def test_bao_cao_CU_thi_KHONG_ep_dong_bo(self):
        """Ca cua party 19/35: bao cao ket lai, tuoi tang vo han -> khong duoc coi la deadlock."""
        self.assertEqual(self._chay(tuoi=600), 0, "van ep dong bo dua tren bao cao cu")

    def test_bao_cao_TUOI_thi_VAN_ep_dong_bo(self):
        """Khong duoc lam mat kha nang cuu party ket THAT."""
        self.assertGreater(self._chay(tuoi=1), 0, "party ket that ma khong con duoc cuu")


if __name__ == "__main__":
    unittest.main()
