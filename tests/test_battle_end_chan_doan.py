"""Goi KET TRAN S:011-000 bi BO thi phai LOG ly do, khong duoc im lang.

BUG THAT (party 1, map thap 2K): tu 11:30-11:41 co 2 dong "START" va KHONG dong "END" nao ->
tran bat dau ma khong bao gio ket -> reset_enemies khong chay -> du lieu quai cu ket lai -> cong
chong-danh-mu (last_atk_gen == enemy_gen) chan luon luot sau -> BOT NGOI IM KHONG DANH.

Truoc day ca 3 nhanh loai bo trong _end deu `return ()` KHONG LOG -> khi truot thi khong bao gi,
loi song rat lau vi khong ai thay. Nay moi lan goi 0x0b sub0 ve deu de lai dau: hoac ra event
"end", hoac ra mot dong log neu ro ly do.

Bo cuc goi (protocal.lua): S:011-000 <結束戰鬥> +玩家ID(8) +NPCIndex(2) -> FightManager.FightOver.
Server gui CHO TUNG NGUOI tham chien; guardIndex==0 = nguoi choi; client goc chi coi la "tran cua
MINH xong" khi roleId == Role.playerId.
"""
import unittest

from bot.battle_tracker import BattleTracker

TOI = b"ROLE0001"
NGUOI_KHAC = b"ROLE0002"


def goi_end(role_id=TOI, guard_index=0):
    return bytes(role_id) + int(guard_index).to_bytes(2, "little")


def make_tracker(active=True, local=TOI):
    t = BattleTracker(local_role_id=local)
    t.active = active
    return t


class TestLogKhiBoGoiKetTran(unittest.TestCase):
    def _bo(self, tracker, data):
        with self.assertLogs("bot", level="WARNING") as cap:
            ket_qua = tracker._apply_0x0b(0, data)
        self.assertEqual(ket_qua, (), "dang le phai BO goi nay")
        return "\n".join(cap.output)

    def test_role_id_khac_thi_log_RO_ca_hai_gia_tri(self):
        """Nhanh dang nghi nhat: local_role_id dang duoc gan = self_entity, con goi mang
        玩家ID (Int64) - chua chung minh duoc la mot. Log ra de doi chieu."""
        t = make_tracker()
        out = self._bo(t, goi_end(role_id=NGUOI_KHAC))
        self.assertIn("role_id KHAC", out)
        self.assertIn(NGUOI_KHAC.hex(), out, "thieu role_id nhan duoc")
        self.assertIn(TOI.hex(), out, "thieu local_role_id dang giu")

    def test_guard_index_khac_0_thi_log(self):
        t = make_tracker()
        out = self._bo(t, goi_end(guard_index=7))
        self.assertIn("guard_index=7", out)

    def test_do_dai_sai_thi_log(self):
        t = make_tracker()
        out = self._bo(t, b"\x01\x02\x03")
        self.assertIn("do dai", out)

    def test_tracker_khong_active_thi_log(self):
        t = make_tracker(active=False)
        out = self._bo(t, goi_end())
        self.assertIn("khong active", out)

    def test_local_role_id_RONG_van_log_duoc(self):
        """Acc chua kip set self_entity -> khong duoc no khi log."""
        t = make_tracker(local=b"")
        out = self._bo(t, goi_end())
        self.assertIn("role_id KHAC", out)
        self.assertIn("(rong)", out)


class TestGoiDungThiVanKetTran(unittest.TestCase):
    def test_dung_role_id_va_guard_0_thi_KET_TRAN(self):
        t = make_tracker()
        su_kien = t._apply_0x0b(0, goi_end())
        self.assertEqual([e.kind for e in su_kien], ["end"])
        self.assertFalse(t.active)

    def test_ket_tran_KHONG_sinh_log_canh_bao(self):
        t = make_tracker()
        with self.assertNoLogs("bot", level="WARNING"):
            t._apply_0x0b(0, goi_end())


class TestKhongSpamLog(unittest.TestCase):
    def test_cung_ly_do_trong_cung_tran_chi_log_MOT_lan(self):
        t = make_tracker()
        with self.assertLogs("bot", level="WARNING") as cap:
            for _ in range(20):
                t._apply_0x0b(0, goi_end(role_id=NGUOI_KHAC))
        self.assertEqual(len(cap.output), 1, "log bi spam: %d dong" % len(cap.output))

    def test_TRAN_MOI_thi_log_lai(self):
        """Khong duoc im vinh vien: tran sau van phai bao neu lai truot."""
        t = make_tracker()
        with self.assertLogs("bot", level="WARNING"):
            t._apply_0x0b(0, goi_end(role_id=NGUOI_KHAC))

        t.generation += 1                       # sang tran moi
        t.active = True
        with self.assertLogs("bot", level="WARNING") as cap:
            t._apply_0x0b(0, goi_end(role_id=NGUOI_KHAC))
        self.assertEqual(len(cap.output), 1)

    def test_bo_dem_khong_phinh_vo_han(self):
        t = make_tracker()
        for g in range(300):
            t.generation = g
            t.active = True
            t._apply_0x0b(0, goi_end(role_id=NGUOI_KHAC))
        self.assertLessEqual(len(t._end_warned), 201)


if __name__ == "__main__":
    unittest.main()
