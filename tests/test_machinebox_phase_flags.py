"""2 co "chet ve thanh" cua HOP MAY doi THEO PHA: BAT khi train, TAT khi PB/quest/event.

Ly do (user): chet giua PB/quest/event ma bi server keo ve thanh = VO LUOT (mat luot pho ban, ca
party phai lam lai). Train thi nguoc lai - ve thanh la dung (hoi mau, khoi nam do giua bai quai).

2 co nay nam o byte 6/7 cua payload C:065-001 (xem GameClient.machinebox_payload).
User van co tick rieng trong Cai dat nang cao: BO TICK la tat han o MOI pha (tick chi la gioi han
tren, khong bao gio bat nguoc lai o PB/quest/event).
"""
import time
import unittest

from bot.client import GameClient


class _State:
    def __init__(self, quest=False, battle=False):
        self.quest_mode = quest
        self.in_battle = battle


def make_client(tick_char=True, tick_pet=True, td_until=0.0, cur_map=14823,
                quest=False, battle=False):
    c = GameClient.__new__(GameClient)
    c._label = "chumuoi"
    c.running = True
    c.death_return_town = tick_char
    c.pet_death_return_town = tick_pet
    c._team_dungeon_until = td_until
    c.current_map = cur_map
    c.state = _State(quest, battle)
    c.sent = []
    c.send = lambda op, pl=b"": c.sent.append((op, pl))
    return c


class TestMachineboxPhaseFlags(unittest.TestCase):
    def test_train_thi_BAT(self):
        pl = make_client().machinebox_payload()
        self.assertEqual((pl[6], pl[7]), (1, 1))

    def test_PB_quest_event_thi_TAT(self):
        # 3 cach nhan biet dang o PB/quest/event
        for ten, kw in (("con han _team_dungeon_until", {"td_until": time.time() + 300}),
                        ("dung tren map PB", {"cur_map": 62011}),
                        ("quest_mode (gom ca event)", {"quest": True})):
            pl = make_client(**kw).machinebox_payload()
            self.assertEqual((pl[6], pl[7]), (0, 0), "sai o ca: %s" % ten)

    def test_user_BO_TICK_thi_tat_o_MOI_pha(self):
        """Tick la GIOI HAN TREN: bo tick thi khong pha nao bat lai."""
        pl = make_client(tick_char=False, tick_pet=False).machinebox_payload()
        self.assertEqual((pl[6], pl[7]), (0, 0))

    def test_chi_gui_khi_THUC_SU_DOI(self):
        c = make_client()
        self.assertTrue(c.sync_machinebox_flags())     # lan dau -> gui
        self.assertEqual(len(c.sent), 1)
        self.assertFalse(c.sync_machinebox_flags())    # khong doi -> KHONG gui
        self.assertEqual(len(c.sent), 1)

        c._team_dungeon_until = time.time() + 300      # vao PB -> doi -> gui
        self.assertTrue(c.sync_machinebox_flags())
        self.assertEqual(len(c.sent), 2)
        self.assertEqual(c.sent[-1][0], 0x41)
        self.assertEqual(c.sent[-1][1][:2], b"\x01\x00")
        self.assertEqual((c.sent[-1][1][2 + 6], c.sent[-1][1][2 + 7]), (0, 0))

    def test_KHONG_chen_goi_giua_tran(self):
        """Dang danh thi hoan lai, xong tran moi gui - tranh chen goi vao giua luot."""
        c = make_client()
        c.sync_machinebox_flags()                      # dat moc ban dau
        n = len(c.sent)
        c._team_dungeon_until = 0.0
        c.state.quest_mode = True                      # doi pha...
        c.state.in_battle = True                       # ...nhung dang danh
        self.assertFalse(c.sync_machinebox_flags())
        self.assertEqual(len(c.sent), n, "da chen goi giua tran")
        c.state.in_battle = False                      # het tran -> gui
        self.assertTrue(c.sync_machinebox_flags())
        self.assertEqual(len(c.sent), n + 1)

    def test_duoc_goi_tu_vong_keepalive(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "run_party_digioi.py").read_text(
            encoding="utf-8")
        self.assertIn("c.sync_machinebox_flags()", src)


if __name__ == "__main__":
    unittest.main()
