"""40NPC phai doc DUNG "thua tran" - `state.allies` da bi xoa luc doc thi khong bao gio thay thua.

`state.allies` bi `clear()` moi `0x34` (vao tran moi) va co luc rong sau khi tran ket. Doc no O
THOI DIEM dialog sau tran -> `known` rong -> `party_defeated` tra `(False, 0, 0)` -> `consec_loss`
khong bao gio tang -> luat "thua 2 tran lien tiep -> tat acc" CHUA TUNG chay mot lan.

Do tren party.log 31/08: 1079/1079 lan ket tran cua acc THAT deu la `alive=0/0 defeated=False`,
ke ca van party 1 luc 21:44:45 leader `CHAR HP=0 (da chet)` roi ca party ngoi hoi mau va ket o
"40NPC: cho dialog sau tran timeout".
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import npc40, protocol      # noqa: E402
from bot.client import GameClient    # noqa: E402


class _U:
    def __init__(self, hp, hp_max):
        self.hp, self.hp_max = hp, hp_max


class _St:
    def __init__(self, allies):
        self.allies = allies


def _bot(allies):
    c = GameClient.__new__(GameClient)
    c._label = "t"
    c._npc40_started = True
    c._npc40_hp_snap = None
    c._npc40_prompt_pending = False
    c._npc40_prompt_pending_at = 0.0
    c._battle_start_seq = 0
    c._npc40_prompt_seq = 0
    c._npc40_last_defeated = False
    c._npc40_last_alive = 0
    c._npc40_last_total = 0
    c.state = _St(allies)
    c._set_battle_end_grace = lambda: None
    return c


class TestChotHPTrongTran(unittest.TestCase):
    def test_chot_khi_allies_con_du_lieu(self):
        c = _bot({(3, 0): _U(0, 100), (3, 1): _U(0, 100)})
        c._observe_npc40_packet(0x33, b"")
        self.assertEqual(c._npc40_hp_snap, (True, 0, 2), "khong chot -> mat du lieu khi allies bi xoa")

    def test_KHONG_chot_khi_allies_rong(self):
        c = _bot({})
        c._npc40_hp_snap = (True, 0, 2)
        c._observe_npc40_packet(0x33, b"")
        self.assertEqual(c._npc40_hp_snap, (True, 0, 2), "ghi de bang du lieu rong = mat chot")

    def test_tran_MOI_thi_BO_chot_cu(self):
        """Khong bo thi tran moi thang lai bi tinh la thua theo chot tran truoc."""
        c = _bot({})
        c._npc40_hp_snap = (True, 0, 2)
        c._observe_npc40_packet(protocol.OP_BATTLE_START, b"")
        self.assertIsNone(c._npc40_hp_snap)

    def test_khoi_tao_trong_ham_dung(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("self._npc40_hp_snap = None", s)


class TestDocKetQuaDungLucKetTran(unittest.TestCase):
    def test_allies_RONG_thi_lay_CHOT(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("defeated, alive, total = npc40.party_defeated(self.state.allies)")
        self.assertGreater(i, 0)
        khoi = s[i:i + 400]
        self.assertIn('if not total and getattr(self, "_npc40_hp_snap", None):', khoi,
                      "allies rong ma khong lay chot -> defeated LUON False")
        self.assertIn("defeated, alive, total = self._npc40_hp_snap", khoi)

    def test_party_defeated_van_dung_nhu_cu(self):
        self.assertEqual(npc40.party_defeated({}), (False, 0, 0))
        self.assertEqual(npc40.party_defeated({1: _U(0, 10), 2: _U(0, 10)}), (True, 0, 2))
        self.assertEqual(npc40.party_defeated({1: _U(5, 10), 2: _U(0, 10)}), (False, 1, 2))


if __name__ == "__main__":
    unittest.main()
