"""Thoat PHO BAN TO DOI bang lenh cua client, KHONG dung relogin.

Nen cu: trong pho ban khong teleport/ve thanh duoc, nen khi PB vo (co dong doi rot / phong thieu
nguoi) bot dung relogin() lam phuong tien thoat instance - "relogin xong la ca lu tu thoat PB".
Cach do dung cho toi khi server CHAN TOC DO DANG NHAP (S:000-000 ma 90): login lai rat kho, acc
ket vong dang nhap hang phut (log that party 6, 23:15-23:25).

Lenh dung (crack client): UIDungeon.OnClickTeamExit -> Dungeon.SendLeaveTeam() ->
Network.Send(47, 10) = C:047-010, KHONG payload. Server tra S:047-010 [roleId i64][result 1B]
voi result 3 = 離開副本, 4 = 斷線重登後離開副本 (Logic/Dungeon.lua RecivePlayerLeave).

Thoat xong van dong bo + danh lai PB theo rule retry cu (o5_need_redo) - khong bo buoc nao.
"""
import time
import unittest
from pathlib import Path

from bot.client import GameClient

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")


class Fake(GameClient):
    pass


def goi_thoat(doi_map_sau):
    """doi_map_sau = server day ra khoi instance sau N giay; None = khong day ra."""
    o = Fake.__new__(Fake)
    o._label = "ttbon"
    o.running = True
    sent = []
    o.send = lambda op, pl=b"": sent.append((op, pl))
    t0 = time.time()

    class Map:                       # DATA descriptor -> khong bi thuoc tinh instance che
        def __get__(self, obj, _):
            if doi_map_sau is None:
                return 62013
            return 21826 if time.time() - t0 > doi_map_sau else 62013

        def __set__(self, obj, v):
            pass

    Fake.current_map = Map()
    try:
        return GameClient.leave_team_dungeon(o, wait=1.0), sent
    finally:
        del Fake.current_map


class TestLeaveTeamDungeon(unittest.TestCase):
    def test_gui_dung_goi_C047_010(self):
        _r, sent = goi_thoat(0.2)
        self.assertEqual(sent, [(0x2f, b"\x0a\x00")])

    def test_ra_duoc_thi_True_khong_ra_thi_False(self):
        self.assertIs(goi_thoat(0.2)[0], True)
        self.assertIs(goi_thoat(None)[0], False)

    def test_KHONG_tu_relogin_bu_khi_that_bai(self):
        """That bai thi tra False cho caller quyet dinh, khong am tham quay ve cach cu."""
        o_calls = []
        Fake.relogin = lambda self: o_calls.append("relogin")
        try:
            goi_thoat(None)
        finally:
            del Fake.relogin
        self.assertEqual(o_calls, [])

    def test_moi_duong_thoat_PB_deu_da_bo_relogin(self):
        """Moi duong thoat instance phai THU THOAT TRUOC, chi relogin khi thoat khong duoc."""
        # 4 cho goi thang + 1 trong helper _exit_pb_or_reconnect = 5
        self.assertEqual(SRC.count("c.leave_team_dungeon()"), 5)
        # 4 duong con lai dung _force_supervisor_reconnect (relogin) -> phai qua helper
        self.assertEqual(SRC.count("return _exit_pb_or_reconnect("), 4)
        # helper KHONG duoc goi lai chinh no (de quy vo han)
        _i = SRC.index("def _exit_pb_or_reconnect")
        _than = SRC[SRC.index(":", _i):_i + 1200]
        self.assertNotIn("_exit_pb_or_reconnect(", _than)
        # relogin con lai chi duoc dung cho viec KHAC (resync vi tri), khong con o duong PB
        for dong in SRC.splitlines():
            if "c.relogin()" in dong:
                self.assertIn("resync pos", dong.lower() + " ",
                              "con duong PB nao do van dung relogin: %s" % dong.strip())


if __name__ == "__main__":
    unittest.main()
