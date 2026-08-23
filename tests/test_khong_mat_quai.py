"""BOT VAO TRAN MA KHONG DANH: dung quai bi XOA SACH truoc khi kip danh.

User chan doan: "m bat thieu 1 hang quai, quai la hang 0 va 1". Dung huong - tracker khong co con
quai nao ca.

Chuoi that (party 1, map thap 2K, log 11:30-12:12):
  1. Roster quai den trong S:011-005. Neu MOT ban ghi lam lech con tro thi _parse_roles cu
     `return None` -> _spawn BO SACH ca danh sach, KHONG log gi -> tracker.units chi con phe minh
     (log: SPAWN toan hang 2 va 3, khong mot dong hang 0/1 nao).
  2. update_0x33 van doc quai DUNG (ca 2 hang: pos = b1*10 + b2).
  3. NHUNG sync_from_tracker() ghi de VO DIEU KIEN tu tracker.units -> xoa luon ket qua cua (2)
     -> enemy_slots = [] -> khong con muc tieu -> bot dung im du in_battle = True
     (user: "no da biet battle = true roi ma van khong lam gi").

Sua: (a) _parse_roles GIU cac ban ghi doc duoc truoc cho hong + LOG ro hong o dau;
     (b) sync_from_tracker chi ghi de khi tracker THUC SU co ban ghi quai.
"""
import unittest

from bot.state import BattleState


class _Unit:
    def __init__(self, hp=100):
        self.hp = hp
        self.alive = hp > 0
        self.sp = 0
        self.sp_max = 0
        self.hp_max = hp or 1
        self.name = ""
        self.role_id = b""


class _Tracker:
    def __init__(self, units, active=True, revision=1):
        self.units = units
        self.active = active
        self.revision = revision
        self.statuses = {}
        self.local_role_id = b""


def goi_0x33(quai, hp=1000):
    """[00][B1][B2][type][val 2B][00]. B1: 0 = hang truoc, 1 = hang sau."""
    body = bytes([0x01, 0x00])
    for pos in quai:
        b1, b2 = divmod(pos, 10)
        body += bytes([0x00, b1, b2, 0x19]) + int(hp).to_bytes(2, "little") + bytes([0x00])
    return bytes(6) + bytes([0x33]) + body


class TestKhongXoaQuaiKhiTrackerRong(unittest.TestCase):
    def test_tracker_KHONG_co_quai_thi_GIU_du_lieu_tu_0x33(self):
        """Dung ca cua user: tracker chi co phe minh (hang 2,3)."""
        st = BattleState()
        st.update_0x33(goi_0x33([0, 1, 2, 3, 4, 10, 11, 12, 13, 14]))
        self.assertEqual(len(st.enemy_slots), 10)

        st.attach_tracker(_Tracker({(3, 0): _Unit(), (2, 0): _Unit()}))   # KHONG co hang 0/1
        st.sync_from_tracker()

        self.assertEqual(len(st.enemy_slots), 10, "sync_from_tracker da xoa sach quai")

    def test_tran_MOT_HANG_cung_khong_bi_xoa(self):
        st = BattleState()
        st.update_0x33(goi_0x33([10, 11, 12]))
        st.attach_tracker(_Tracker({(3, 2): _Unit()}))
        st.sync_from_tracker()
        self.assertEqual(st.enemy_slots, [10, 11, 12])

    def test_tracker_CO_quai_thi_van_la_nguon_chinh(self):
        """Tracker co du lieu that thi phai theo tracker (no moi la ban dong bo dung)."""
        st = BattleState()
        st.update_0x33(goi_0x33([0, 1, 2, 3, 4, 10, 11, 12, 13, 14]))

        st.attach_tracker(_Tracker({(0, 1): _Unit(500), (1, 3): _Unit(700), (3, 0): _Unit()}))
        st.sync_from_tracker()

        self.assertEqual(st.enemy_slots, [1, 13], "khong lay theo tracker khi tracker co quai")

    def test_tracker_co_quai_CHET_HET_thi_van_ghi_de(self):
        """Giet sach quai: tracker co ban ghi nhung hp=0 -> enemy_slots rong la DUNG."""
        st = BattleState()
        st.update_0x33(goi_0x33([0, 1]))
        st.attach_tracker(_Tracker({(0, 0): _Unit(0), (0, 1): _Unit(0)}))
        st.sync_from_tracker()
        self.assertEqual(st.enemy_slots, [])

    def test_0x33_doc_DU_CA_HAI_HANG(self):
        """Chan tai pham cho chan doan cua user: hang 0 VA hang 1 deu phai vao."""
        st = BattleState()
        st.update_0x33(goi_0x33([0, 1, 2, 3, 4]))          # chi hang 0
        self.assertEqual(st.enemy_slots, [0, 1, 2, 3, 4])

        st2 = BattleState()
        st2.update_0x33(goi_0x33([10, 11, 12, 13, 14]))    # chi hang 1
        self.assertEqual(st2.enemy_slots, [10, 11, 12, 13, 14])

        st3 = BattleState()
        st3.update_0x33(goi_0x33([0, 1, 2, 3, 4, 10, 11, 12, 13, 14]))   # ca 2 hang
        self.assertEqual(len(st3.enemy_slots), 10, "mat mot hang quai")


class TestRoleKindTheoClient(unittest.TestCase):
    """GOC that cua "vao tran ma bot khong danh" (log 12:31:25).

    role_kind = EHuman (RoleController.lua). FightField.RoleAppear chi doc DU LIEU THEM cho:
        Player=1, Players=2, Divide=9, AutomanualPlayer=28  -> ngoai hinh nguoi choi
        FollowNpc=4, AutomanualNpc=29                       -> [L][ten]
    Con lai, KE CA MapNpc=3 (QUAI), khong co gi them.

    Bot cu khai PLAYER_ROLE_KINDS = (1,2,3,5): co 3 = QUAI -> di doc ngoai hinh KHONG TON TAI ->
    goi 42 byte (dung bang ROLE_HEADER_SIZE) parse hong -> vut sach ca roster -> tracker rong ->
    available rong -> _arm_decision khong duoc goi -> bot dung im.
    """

    # 24 byte dau LAY TU LOG THAT, dem 0 cho du 42 byte (ROLE_HEADER_SIZE)
    GOI_QUAI = bytes.fromhex("0303122b0000000000000200000000000000000000020b06") + bytes(18)

    def test_quai_MapNpc_kind3_phai_parse_duoc(self):
        from bot.battle_tracker import BattleTracker
        u = BattleTracker._parse_roles(self.GOI_QUAI, tag="test")
        self.assertEqual(len(u or []), 1, "van vut ban ghi quai (bug cu)")
        self.assertEqual(u[0].role_kind, 3)
        self.assertEqual((u[0].row, u[0].col), (0, 2), "quai phai o HANG 0")

    def test_kind3_KHONG_duoc_coi_la_nguoi_choi(self):
        from bot.battle_tracker import PLAYER_ROLE_KINDS, NAMED_NPC_ROLE_KINDS
        self.assertNotIn(3, PLAYER_ROLE_KINDS, "MapNpc(3) = QUAI, khong phai nguoi choi")
        self.assertNotIn(3, NAMED_NPC_ROLE_KINDS)

    def test_cac_kind_khop_dung_client(self):
        from bot.battle_tracker import PLAYER_ROLE_KINDS, NAMED_NPC_ROLE_KINDS
        self.assertEqual(PLAYER_ROLE_KINDS, frozenset((1, 2, 9, 28)))
        self.assertEqual(NAMED_NPC_ROLE_KINDS, frozenset((4, 29)))


if __name__ == "__main__":
    unittest.main()
