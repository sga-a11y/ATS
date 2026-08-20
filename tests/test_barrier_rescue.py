"""Barrier reform: cuu acc KET nhung KHONG pha ngang acc dang BAN THAT.

Bug that dan toi co che nay:
  - party 38 (18/08): t1709 im 16667s (luong chet) -> ca party ket 4h38'.
  - party 4  (20/08): 4 member im hon 2' trong khi DANG DUNG dung map leader muon tu;
    leader in "CHO ca party ve thanh 23001 (1/5)" moi 30s.

Test KHONG viet lai logic: RUT DUNG doan ma tu run_party_digioi.py roi exec voi du lieu gia.
Sua code -> test chay theo code moi. Neu ai do doi cau truc doan do, test bao loi ngay (khong
tim thay moc) chu khong am tham pass.
"""
import re
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")

_START = "                        _barrier_el = time.time() - _barrier_t0"
_END = "                            for _u in _stuck:"
BLOCK = textwrap.dedent(SRC[SRC.index(_START):SRC.index(_END, SRC.index(_START))])

CONSTS = {}
for _n in ("BARRIER_RESCUE_SEC", "BARRIER_STALE_RESCUE_SEC", "BARRIER_STALE_SEC"):
    _m = re.search(r"^%s\s*=\s*(\d+)" % _n, SRC, re.M)
    assert _m, "khong tim thay hang so " + _n
    CONSTS[_n] = int(_m.group(1))


def run_block(elapsed, accs, arrived=None, reconnecting=(), is_leader=True):
    """accs = {user: (age, done, xong_cach_day) hoac None}. Tra ve danh sach acc BI CUU.

    age          = giay tu lan CAP NHAT cuoi (nhip tim tu vong recv - chi chung minh socket song)
    done         = da xong viec hien tai chua
    xong_cach_day= xong tu bao lau (chi co nghia khi done=True)
    """
    NOW = 1000.0                       # DONG HO GIA duy nhat cho ca khoi ma
    ns = dict(CONSTS)
    ns.update({
        "time": type("T", (), {"time": staticmethod(lambda: NOW)}),
        "_barrier_t0": NOW - elapsed,
        "is_leader": is_leader,
        "pidx": 4,
        "_arr_gen": arrived or {},
        "_target_city": 23001,
        "st": {"reconnecting": set(reconnecting)},
        "party_accounts": lambda _p: [(u, "pw", False, False) for u in accs],
        "get_account_task": lambda u: (None if accs[u] is None else {
            "task": "viec gi do", "phase": "train", "age": accs[u][0],
            "done": accs[u][1], "done_at": NOW - accs[u][2]}),
        "_stuck": None,
    })
    exec(BLOCK, ns)
    return ns["_stuck"]


PARTY4 = {u: (130, False, 0) for u in ("thha", "thba", "thbon", "thnam")}
# party 11: XONG pho ban don roi dung im, nhung nhip tim tu vong recv van dap ->
# age chi 1s. Chi co "done tu 200s truoc" moi to cao la ket.
PARTY11 = {u: (1, True, 200) for u in ("luutam", "luuchin")}
BUSY = {"thha": (3, False, 0)}   # dang danh dungeon: viec CHUA xong -> khong duoc dung


class TestBarrierRescue(unittest.TestCase):
    def test_acc_ket_duoc_cuu_som_khong_phai_doi_han_cung(self):
        self.assertIsNone(run_block(60, PARTY4))                 # chua toi moc som
        self.assertEqual(sorted(run_block(91, PARTY4)), sorted(PARTY4))
        self.assertEqual(run_block(91, {"t1709": (16667, False, 0)}), ["t1709"])
        # party 11: nhip tim con moi (1s) nhung XONG viec tu 200s truoc -> VAN phai cuu
        self.assertEqual(sorted(run_block(91, PARTY11)), sorted(PARTY11))
        self.assertLess(CONSTS["BARRIER_STALE_RESCUE_SEC"], CONSTS["BARRIER_RESCUE_SEC"])

    def test_acc_dang_ban_that_khong_bi_pha_ngang(self):
        self.assertEqual(run_block(91, BUSY), [])
        self.assertEqual(run_block(239, BUSY), [])
        self.assertEqual(run_block(241, BUSY), ["thha"])          # han cung van phai toi

    def test_loc_dung_doi_tuong(self):
        mix = {"da_ve": (5, False, 0), "ket": (999, False, 0), "dang_relogin": (999, False, 0)}
        self.assertEqual(
            run_block(91, mix, arrived={"da_ve": 23001}, reconnecting=["dang_relogin"]), ["ket"])
        self.assertEqual(run_block(91, {"x": (999, False, 0)}, arrived={"x": 12061}), ["x"])  # ve NHAM map
        self.assertEqual(run_block(91, {"x": None}), ["x"])       # chua he report
        self.assertIsNone(run_block(300, PARTY4, is_leader=False))  # member khong cuu ai

    def test_reset_moc_chi_khi_thuc_su_cuu_ai_do(self):
        """Reset `_barrier_t0` VO DIEU KIEN -> moi vong lai lui moc -> han cung KHONG BAO GIO toi."""
        guard = SRC[SRC.index("                            if _stuck:"):]
        guard = guard[:guard.index("time.sleep(1)")]
        self.assertIn("_barrier_t0 = time.time()", guard)

        def mo_phong(reset_vo_dieu_kien):
            t0 = now = 0.0
            for _ in range(600):
                now += 1
                if run_block(now - t0, BUSY):
                    return now - t0
                if reset_vo_dieu_kien:
                    t0 = now
            return None

        self.assertIsNone(mo_phong(True))            # ban SAI: khong bao gio cuu
        self.assertLessEqual(mo_phong(False), 245)   # ban DUNG: han cung van toi


if __name__ == "__main__":
    unittest.main()
