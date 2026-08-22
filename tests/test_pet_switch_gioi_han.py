"""Doi pet: thu toi da PET_SWITCH_MAX_TRY lan roi THOI, giu pet hien tai.

BUG USER BAO: pet HET DO TRUNG THANH -> server tu choi doi -> switch_pet khong bao gio confirm.
Ma ensure_pet_role duoc goi MOI lan vao hoat dong (decorator @_pet_role) -> bot thu lai VO HAN,
moi lan phi 4s cho + log rac.

Dem theo PET ID chu khong theo VAI: nguyen nhan chan nam o CON PET, mot con gan 2 vai khong duoc
an 6 lan thu. "Dang trong tran" la ly do TAM THOI -> khong tinh vao so lan thu.
"""
import unittest

from bot.client import GameClient


class _State:
    def __init__(self, carried=(), active=None, in_battle=False):
        self.carried_pets = list(carried)
        self.active_pet_id = active
        self.active_pet_confirmed = active is not None
        self.in_battle = in_battle


def make_client(carried=((0x1111, "A"), (0x2222, "B")), active=0x1111, in_battle=False,
                confirm=False):
    c = GameClient.__new__(GameClient)
    c._label = "sw"
    c.running = True
    c.state = _State(carried, active, in_battle)
    c._pet_switch_fail = {}
    c.pet_faith = {0x2222: 0}
    c.sent = []
    c.heal_full = lambda force=False: None

    def _send(op, payload=b""):
        c.sent.append((op, payload))
        if confirm:                       # gia lap server XAC NHAN doi pet
            c.state.active_pet_id = int.from_bytes(payload[2:4], "little")
    c.send = _send
    return c


class TestPetSwitchGioiHan(unittest.TestCase):
    def test_thu_dung_3_lan_roi_THOI(self):
        c = make_client()
        for lan in range(GameClient.PET_SWITCH_MAX_TRY):
            self.assertFalse(c.switch_pet(0x2222, wait=0.01), "lan %d" % (lan + 1))
        self.assertEqual(len(c.sent), GameClient.PET_SWITCH_MAX_TRY)

        # Lan 4 tro di: KHONG gui goi nua, giu pet hien tai
        for _ in range(5):
            self.assertFalse(c.switch_pet(0x2222, wait=0.01))
        self.assertEqual(len(c.sent), GameClient.PET_SWITCH_MAX_TRY, "van con gui goi doi pet")
        self.assertEqual(c.state.active_pet_id, 0x1111, "pet hien tai bi doi mat")

    def test_log_RO_MOT_LAN_khi_bo_cuoc_chu_khong_spam(self):
        c = make_client()
        with self.assertLogs("bot", level="WARNING") as cap:
            for _ in range(6):
                c.switch_pet(0x2222, wait=0.01)
        bo_cuoc = [d for d in cap.output if "THOI doi" in d]
        self.assertEqual(len(bo_cuoc), 1, "log bo cuoc bi spam: %s" % bo_cuoc)
        self.assertIn("trung thanh=0", bo_cuoc[0], "khong ghi do trung thanh de user hieu ly do")

    def test_DANG_TRAN_khong_tinh_vao_so_lan_thu(self):
        """Ly do TAM THOI - het tran la doi duoc, khong duoc an mat luot thu."""
        c = make_client(in_battle=True)
        for _ in range(10):
            self.assertFalse(c.switch_pet(0x2222, wait=0.01))
        self.assertEqual(c._pet_switch_fail, {}, "dang tran ma bi tinh la that bai")
        self.assertEqual(c.sent, [])

        c.state.in_battle = False                      # het tran -> van con du 3 lan
        for _ in range(GameClient.PET_SWITCH_MAX_TRY):
            c.switch_pet(0x2222, wait=0.01)
        self.assertEqual(len(c.sent), GameClient.PET_SWITCH_MAX_TRY)

    def test_doi_DUOC_thi_xoa_bo_dem(self):
        """That bai 2 lan roi doi duoc -> lan sau van con du quota, khong dinh bo dem cu."""
        c = make_client()
        c.switch_pet(0x2222, wait=0.01)
        c.switch_pet(0x2222, wait=0.01)
        self.assertEqual(c._pet_switch_fail.get(0x2222), 2)

        c2 = make_client(confirm=True)
        c2._pet_switch_fail[0x2222] = 2
        self.assertTrue(c2.switch_pet(0x2222, wait=0.5))
        self.assertNotIn(0x2222, c2._pet_switch_fail, "doi duoc roi ma van giu bo dem")

    def test_bo_dem_RIENG_tung_pet(self):
        """Con nay het quota khong duoc lam con KHAC bi chan theo."""
        c = make_client(carried=((0x1111, "A"), (0x2222, "B"), (0x3333, "C")))
        for _ in range(GameClient.PET_SWITCH_MAX_TRY):
            c.switch_pet(0x2222, wait=0.01)
        n = len(c.sent)
        c.switch_pet(0x3333, wait=0.01)
        self.assertEqual(len(c.sent), n + 1, "pet khac bi chan lay")

    def test_pet_KHONG_co_trong_tui_cung_bi_gioi_han(self):
        """Cung la 'khong doi duoc' -> khong duoc spam log moi hoat dong."""
        c = make_client()
        for _ in range(6):
            self.assertFalse(c.switch_pet(0x9999, wait=0.01))
        self.assertEqual(c._pet_switch_fail.get(0x9999), GameClient.PET_SWITCH_MAX_TRY)

    def test_ensure_pet_role_an_theo_gioi_han(self):
        """Duong that ma bot dung: decorator @_pet_role -> ensure_pet_role -> switch_pet."""
        c = make_client()
        c.state.battle_config = {"pet_roles": {"boss": 0x2222}}
        # ensure_pet_role goi switch_pet voi wait MAC DINH 4s -> 3 lan = 12s. Do chinh la khoan
        # phi ma fix nay chan (truoc day la VO HAN 4s/lan). Test thi ep wait nho cho nhanh.
        c.switch_pet = lambda pid, wait=0.01: GameClient.switch_pet(c, pid, 0.01)
        for _ in range(10):
            self.assertFalse(c.ensure_pet_role("boss"))
        self.assertEqual(len(c.sent), GameClient.PET_SWITCH_MAX_TRY)


if __name__ == "__main__":
    unittest.main()
