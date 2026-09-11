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

# 11/09: khoi nay TRUOC day nam trong vong "member sai map - cho leader keo". Vong do da bi XOA
# (acc tu chon buoc vao, va trong do no diec voi moi lenh dieu phoi - ttmuoi nam trong do mot tieng
# ruoi). Luat "leader dang login lai thi member KHONG thoat" van con nguyen, o VONG CHINH - dung
# cho, vi o do acc nghe duoc moi lenh.
_START = '            if ((not is_leader) and has_leader and st["leader_gone"].is_set()'
# Moc cuoi khoi: dong ngay sau vong xu ly `leader_gone/bad`. Truoc day neo vao
# `_do_reform(to_spot=False)` - dong do da bi XOA 11/09 (member khong tu goi reform nua), va vi no
# con xuat hien o cho khac trong file nen `index()` van tim thay -> khoi trich ra dai qua, sai thut
# le. Neo vao mot dong DUY NHAT trong ca file thay vi mot dong de trung.
_END = "            if stop_ev is not None and stop_ev.is_set():"
_i = SRC.index(_START)
BLOCK = textwrap.dedent(SRC[_i:SRC.index(_END, _i)])
# Khoi nay nam trong VONG CHINH va thoat bang `break` -> phai boc trong MOT VONG, khong phai boc
# tran trong `def` (se ra SyntaxError: 'break' outside loop).
FUNC = ("def _member_step():\n"
        "    while True:\n"
        + textwrap.indent(BLOCK, "        ")
        + "        return 'CHAY TIEP'\n"
        "    return 'THOAT'\n")


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
        # Khoi o VONG CHINH nen dieu kien co them cac bien canh: member cua party co bot-leader,
        # mode train thuong (khong phai DG solo / event).
        "is_leader": False,
        "has_leader": True,
        "digioi_solo": False,
        "event_stand_mode": False,
        "event_solo_kind": None,
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
    """Leader mat ket noi -> supervisor cua no DANG login lai, chua he bo cuoc. Member thay co
    `leader_gone` ma thoat han thi acc chet toi khi user tu bat lai, trong khi vai chuc giay sau
    leader da chay tiep binh thuong (party 20: dieubon/dieunam THOAT luc 22:49:27, leader dieumot
    RECONNECT xong 22:50:34 va van reform).

    11/09: khoi nay tung co HAI ban - mot trong vong "member sai map - cho leader keo", mot o vong
    chinh. Vong kia da bi XOA (acc tu chon buoc vao, va trong do no diec voi moi lenh dieu phoi),
    nen gio chi con MOT ban duy nhat - o vong chinh, dung cho, vi o do acc nghe duoc moi lenh.
    """

    def test_leader_dang_login_lai_thi_member_KHONG_thoat(self):
        ket_qua, st, logs = run_step(leader_alive=True)
        self.assertEqual(ket_qua, "CHAY TIEP")
        self.assertFalse(st["leader_gone"].is_set(), "co cu phai duoc xoa")
        self.assertTrue(any("stale" in x.lower() for x in logs), logs)

    def test_leader_thoat_that_thi_member_van_thoat_theo(self):
        ket_qua, _st, logs = run_step(leader_alive=False)
        self.assertEqual(ket_qua, "THOAT")
        self.assertTrue(any("thoat theo" in x.lower() for x in logs), logs)

    def test_chi_con_MOT_ban_dung_chung_mot_phep_kiem(self):
        """Hai ban = som muon lech nhau. Gio mot cho goi, mot dinh nghia."""
        self.assertEqual(SRC.count("if _leader_thread_active():"), 1)
        self.assertEqual(SRC.count("def _leader_thread_active():"), 1)


if __name__ == "__main__":
    unittest.main()
