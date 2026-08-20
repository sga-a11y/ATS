"""Member KHONG duoc thoat han khi leader chi dang LOGIN LAI.

Bug that (party.log 20/08, party 20 - server dai_kieu/dieu_thuyen dut lien tuc):
  22:49:27 [dieubon] Server dong ket noi
  22:49:27 [dieubon] (member) leader gone/bad khi cho reform -> THOAT     <- CHET HAN
  22:50:34 [dieumot] (LEADER) RECONNECT o map 14001 ...                   <- leader VAN SONG
  22:51:04 [dieumot] (LEADER) reform: CHO ca party ve thanh 14001 (1/5, reconnecting=2)
Server dut ket noi la loi cua SERVER, nhung member tu ket lieu thread la loi cua BOT: acc chet
toi khi user tu bat lai, trong khi leader vai chuc giay sau da chay tiep binh thuong.

Nhanh tuong tu o cuoi run_account DA co guard `_leader_thread_active()`; cho nay bi SOT.

Test KHONG viet lai logic: RUT DUNG doan ma tu run_party_digioi.py roi exec.
"""
import textwrap
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")

_START = '                        if st["leader_gone"].is_set() or st["leader_bad"].is_set():'
_END = "                        _do_reform(to_spot=False)"
_i = SRC.index(_START)
BLOCK = textwrap.dedent(SRC[_i:SRC.index(_END, _i)])
# co `return` -> phai boc trong ham moi exec duoc
FUNC = "def _member_step():\n" + textwrap.indent(BLOCK, "    ") + "    return 'CHAY TIEP'\n"


class Quit(Exception):
    pass


def run_step(leader_alive):
    st = {"leader_gone": threading.Event(), "leader_bad": threading.Event()}
    st["leader_gone"].set()
    st["leader_bad"].set()
    logs = []
    ns = {
        "st": st,
        "label": "dieubon",
        "_leader_thread_active": lambda: leader_alive,
        "_reason": lambda *a, **k: None,
        "_quit": lambda: (_ for _ in ()).throw(Quit()),
        "log": type("L", (), {
            "warning": staticmethod(lambda f, *a: logs.append(f % a if a else f)),
            "info": staticmethod(lambda f, *a: logs.append(f % a if a else f)),
        }),
    }
    exec(FUNC, ns)
    try:
        return ns["_member_step"](), st, logs
    except Quit:
        return "THOAT", st, logs


class TestMemberLeaderGoneStale(unittest.TestCase):
    def test_leader_dang_login_lai_thi_member_KHONG_thoat(self):
        ket_qua, st, logs = run_step(leader_alive=True)
        self.assertEqual(ket_qua, "CHAY TIEP")
        self.assertFalse(st["leader_gone"].is_set())   # co cu phai duoc xoa
        self.assertFalse(st["leader_bad"].is_set())
        self.assertTrue(any("STALE" in x for x in logs), logs)

    def test_leader_thoat_that_thi_member_van_thoat_theo(self):
        ket_qua, _st, logs = run_step(leader_alive=False)
        self.assertEqual(ket_qua, "THOAT")
        self.assertTrue(any("THOAT" in x for x in logs), logs)

    def test_guard_dung_chung_ham_voi_nhanh_kia(self):
        """Ca 2 nhanh phai dung CUNG mot phep kiem tra, khong moi noi mot kieu."""
        self.assertEqual(SRC.count("if _leader_thread_active():"), 2)   # 2 CHO GOI
        self.assertEqual(SRC.count("def _leader_thread_active():"), 1)  # 1 dinh nghia dung chung


if __name__ == "__main__":
    unittest.main()
