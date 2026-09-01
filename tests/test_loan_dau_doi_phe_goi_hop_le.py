"""LOAN DAU bi xep sang phe kia -> moi gia tri HANG trong goi `0x32` phai theo phe THAT.

Su co 01/09/2026 party 7 (acc `ttsau`, server tao_thao): vao tran loan dau, danh mot luot roi bi
`S:000-000` ly do **42** = `修改戰鬥封包` ("sua goi chien dau", `protocal.lua` cause 42, `quit=true`
nen bi da han). Lap lai 2 lan lien.

SOI CLIENT (`FightRoleController.lua:2655-2667`) thi goi that la:

    sendBuffer:WriteByte(fightRole.colm);   -- nguon
    sendBuffer:WriteByte(fightRole.row);
    sendBuffer:WriteByte(self.colm);        -- dich  (fightRole = nguoi hanh dong, self = muc tieu:
    sendBuffer:WriteByte(self.row);         --        thay ro o `fightRole.party_Kind ~= self.party_Kind`)
    sendBuffer:WriteUInt16(useID);
    sendBuffer:WriteByte(checkByte);        -- math.random(220)  <-- CHI TOI 220
    sendBuffer:WriteByte(math.random(256));

`MaxChipColm = 4` / `MaxChipRow = 5` (FightField.lua:10-13) chung minh client dat ten NGUOC: `colm`
chinh la HANG (0..3), `row` la COT (0..4). Nen bo cuc that = [nguon.hang][nguon.cot][dich.hang]
[dich.cot] - DUNG y bo cuc bot dang gui (khong he hoan vi).

Hai loi THAT tim ra:
  1. `checkByte` bot random toi 255. Goi pet luc 20:34:10 co checkByte = 234 (> 220) - gia tri ma
     client THAT khong bao gio gui.
  2. Buff/hoi mau/bo chay viet CUNG `b=3` (char) va `b=2` (pet). Doi phe thi char ta o hang 0,
     pet ta o hang 1 -> `b=3` thanh HOI MAU CHO DICH, con `SKILL_FLEE` thi nham vao o khong phai
     cua minh.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import combat, config          # noqa: E402
from bot.state import BattleState       # noqa: E402


def _state(doi_phe):
    st = BattleState.__new__(BattleState)
    st.enemy_rows, st.ally_rows, st.char_row = ((2, 3), (0, 1), 0) if doi_phe else ((0, 1), (2, 3), 3)
    return st


class TestHangTheoPhe(unittest.TestCase):
    def test_tran_thuong_giu_nguyen_3_va_2(self):
        st = _state(False)
        self.assertEqual(combat._hang_char_ta(st), 3)
        self.assertEqual(combat._hang_pet_ta(st), 2)

    def test_loan_dau_doi_phe_thanh_0_va_1(self):
        st = _state(True)
        self.assertEqual(combat._hang_char_ta(st), 0)
        self.assertEqual(combat._hang_pet_ta(st), 1)

    def test_doi_phe_theo_o_cua_minh(self):
        st = _state(False)
        self.assertTrue(st.doi_phe_theo_hang_cua_minh(0))
        self.assertEqual((st.ally_rows, st.char_row), ((0, 1), 0))
        self.assertTrue(st.doi_phe_theo_hang_cua_minh(3))
        self.assertEqual((st.ally_rows, st.char_row), ((2, 3), 3))


class TestKhongCon_HANG_VIET_CUNG(unittest.TestCase):
    """Bo sot mot cho la cho do hoi mau cho DICH khi doi phe."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "combat.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_khong_con_Decision_b_3_hay_b_2(self):
        for xau in ("b=3)", "b=2)"):
            self.assertNotIn(xau, self.src, "con hang dich viet cung -> doi phe la nham muc tieu")

    def test_khoa_claim_cung_theo_hang_that(self):
        """Khoa `_claim_support_action` phai cung he quy chieu voi hang gui di."""
        self.assertNotIn('"heal_hp", (3, _ht)', self.src)
        self.assertNotIn('"heal_sp", (3, low_slot)', self.src)

    def test_heal_dung_hang_CHAR_ta(self):
        self.assertGreaterEqual(self.src.count("_hc = _hang_char_ta(state)"), 3)

    def test_FLEE_nham_dung_hang_cua_chinh_minh(self):
        """Bo chay = nham CHINH MINH: char phai b = hang char ta, pet b = hang pet ta."""
        self.assertIn("config.SKILL_FLEE, b=_hang_char_ta(state)", self.src)
        self.assertEqual(self.src.count("config.SKILL_FLEE, b=_hang_pet_ta(state)"), 2)


class TestCheckByteGiongClient(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_checkbyte_toi_da_220(self):
        """`math.random(220)` ben client -> 1..220. Bot tung gui 234 va bi da ma 42."""
        self.assertIn("random.randint(1, 220)", self.src)

    def test_KHONG_con_random_ca_2_byte_toi_0xFFFF(self):
        self.assertNotIn("random.randint(1, 0xFFFF)", self.src)

    def test_byte_cuoi_van_random_day_du(self):
        self.assertIn("random.randint(0, 255)", self.src)


class TestDumpGoiTronTheoThoiGian(unittest.TestCase):
    """Lan van sau phai truy duoc thu tu: bot gui 0x32 TRUOC hay SAU khi nhan 0x35 offer."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        i = self.src.find("def _dump_recent(")
        self.than = self.src[i:self.src.find("\n    def ", i + 10)]

    def test_tron_chung_hai_chieu_va_sap_theo_thoi_gian(self):
        self.assertIn("sorted(_goi, key=lambda x: x[0])", self.than)
        self.assertIn(">>gui", self.than)
        self.assertIn("<<nhan", self.than)

    def test_moc_thoi_gian_co_MILI_GIAY(self):
        """Moc chi toi GIAY thi ca chuc goi cung mot giay -> khong suy duoc thu tu."""
        self.assertIn("int(ts * 1000) % 1000", self.than)

    def test_luu_moc_dang_SO_khong_phai_chuoi(self):
        self.assertIn("self._recent_sends.append((time.time(), opcode", self.src)
        self.assertIn("self._recent_recvs.append((time.time(), opcode", self.src)


if __name__ == "__main__":
    unittest.main()
