"""RULE (user, tuyet doi): "tran >6 quai thi PHAI vao quest mode".

BUG THAT (party 1, map 12930 thap 2K, 12 phut / 66 tran khong lan nao vao quest mode):
latch cu chi cham DUNG MOT LAN, o lan DAU thay quai (`not self._battle_counted`). Nhung quai xep
theo HANG, moi hang toi da 5 con -> goi 0x33 dau thuong chi mang 1 hang (<=5) -> cham False roi
KHOA LUON; 5 con hang sau den cung khong xet lai.
=> Dung nhung tran 10 quai (2 hang) - tuc dung luc rule >6 CAN chay nhat - thi no khong bao gio
chay. Bang chung trong log: char `minh` co CC 11014 Bang Phong ma 0 lan dung trong 66 tran, va
quai@ ghi ro [0,1,2,3,4,10,11,12,13,14].

Nay: xet MOI lan du lieu quai doi; chi BAT len True, khong bao gio ha (giet bot quai con <=6 van
giu quest ca tran - dung y dinh cu cua latch).
"""
import unittest

from bot.state import BattleState


def goi_0x33(quai, hp=1000):
    """Dung goi 0x33 THAT: [00][B1][B2][type][val 2B LE][00] moi block.
    B1: 0 = quai hang truoc, 1 = quai hang sau. `quai` = list slot noi bo (b1*10 + b2)."""
    body = bytes([0x01, 0x00])
    for pos in quai:
        b1, b2 = divmod(pos, 10)
        body += bytes([0x00, b1, b2, 0x19]) + int(hp).to_bytes(2, "little") + bytes([0x00])
    return bytes(6) + bytes([0x33]) + body


def them_quai(st, quai, hp=1000):
    """Goi HAM THAT update_0x33 - KHONG chep lai luat latch vao test (test chep lai luat thi
    luon xanh du code sai; da dinh dung loi do trong repo nay)."""
    st.update_0x33(goi_0x33(quai, hp))


class TestQuestModeLatch(unittest.TestCase):
    def setUp(self):
        self.st = BattleState()

    def test_quai_den_theo_2_HANG_van_phai_vao_quest_mode(self):
        """Ca CUA USER: hang 1 (5 con) den truoc, hang 0 (5 con) den sau -> tong 10 > 6."""
        them_quai(self.st, [10, 11, 12, 13, 14])
        self.assertFalse(self.st.quest_mode, "moi 5 con ma da vao quest mode")

        them_quai(self.st, [0, 1, 2, 3, 4])
        self.assertEqual(len(self.st.enemy_slots), 10)
        self.assertTrue(self.st.quest_mode, "10 quai ma khong vao quest mode (bug cu)")

    def test_mot_goi_co_san_tren_6_con(self):
        them_quai(self.st, [0, 1, 2, 3, 4, 10, 11])
        self.assertTrue(self.st.quest_mode)

    def test_tu_6_tro_xuong_thi_KHONG_vao(self):
        them_quai(self.st, [0, 1, 2, 3, 4, 10])
        self.assertFalse(self.st.quest_mode, "dung 6 con - rule la > 6")

    def test_giet_bot_con_duoi_6_van_GIU_quest_mode(self):
        """Y dinh cu cua latch: da vao quest thi giu ca tran, khong tut ve train giua chung."""
        them_quai(self.st, [0, 1, 2, 3, 4, 10, 11, 12, 13, 14])
        self.assertTrue(self.st.quest_mode)

        # giet 7 con = server gui 0x33 voi HP 0 cho may slot do (khong sua tay enemy_hp)
        them_quai(self.st, [0, 1, 2, 3, 4, 10, 11], hp=0)
        self.assertEqual(len(self.st.enemy_slots), 3)
        self.assertTrue(self.st.quest_mode, "tut ve train mode giua tran")

    def test_start_enemy_slots_van_la_LAN_DAU_thay_quai(self):
        """Thong ke block train (_record_train_block_stats) can dung nghia 'luc START tran' ->
        khong duoc gop chung voi latch."""
        self.assertFalse(self.st._battle_counted)
        them_quai(self.st, [10, 11])
        self.assertTrue(self.st._battle_counted)

    def test_tran_MOI_thi_latch_nap_lai(self):
        them_quai(self.st, [0, 1, 2, 3, 4, 10, 11, 12, 13, 14])
        self.assertTrue(self.st.quest_mode)

        self.st.reset_enemies(reset_quest=True)          # ket tran
        self.assertFalse(self.st.quest_mode)
        self.assertFalse(self.st._battle_counted)

        them_quai(self.st, [0, 1])                       # tran moi it quai
        self.assertFalse(self.st.quest_mode)

    def test_force_quest_mode_van_thang_moi_truong_hop(self):
        self.st.force_quest_mode = True
        them_quai(self.st, [0])
        self.assertTrue(self.st.quest_mode)


class TestLuatNamTrongCodeThat(unittest.TestCase):
    def test_update_0x33_khong_con_khoa_latch_sau_lan_dau(self):
        """Chan tai pham: neu ai do gan lai dieu kien latch vao `not self._battle_counted` thi
        bug cu quay lai ngay."""
        import inspect
        src = inspect.getsource(BattleState.update_0x33)
        i = src.index("LATCH quest_mode")
        doan = src[i:i + 1400]
        self.assertIn("if self.force_quest_mode or len(self.enemy_slots) > 6:", doan)
        vt_latch = doan.index("len(self.enemy_slots) > 6")
        vt_counted = doan.index("if not self._battle_counted:")
        self.assertLess(vt_counted, vt_latch, "cau truc doi - xem lai")
        # dieu kien latch KHONG duoc nam trong than cua `if not self._battle_counted:`
        than = doan[vt_counted:vt_latch]
        self.assertIn("start_enemy_slots", than)
        self.assertLessEqual(than.count("\n"), 4, "latch bi long vao trong nhanh lan-dau")


if __name__ == "__main__":
    unittest.main()
