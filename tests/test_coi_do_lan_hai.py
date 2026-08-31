"""COI DO lan hai: mon vua coi phai VAO `bag_slots`, khong thi lan sau tro trung o cu.

`unequip_item` phai chi RO o tui de nhet mon vao (client tu chon, server khong tim ho) - no lay
`bag_first_empty_slot()`. Neu mon vua coi khong duoc ghi vao `bag_slots` thi o do van "trong",
lan coi thu hai tro dung o do -> server nuot im -> user thay "khong co gi xay ra".

SERVER KHONG GUI 023-008 cho mon vua coi. CHINH CLIENT chuyen no vao tui
(`_lua_dec/Common/protocal.lua`, `protocolTable[23][16]`):
    local fitType  = data:ReadByte();
    local bagIndex = data:ReadByte();
    Item.SetBagItem(EThings.Bag, bagIndex, Item.GetBagItem(EThings.Equip, fitType, 0), true);
    Item.DelBagItem(EThings.Equip, fitType);
Pet: `protocolTable[23][22]` (S:023-022 <武將卸下裝備到背包>) y het, them followIndex.

Log 31/08: quan809 15:49:51 `Da coi do: vi tri 3 cua nhan vat (Ngự Thiên Pháp Trượng)` ma KHONG
he co dong `Nhan item` di kem - dung la mon khong vao `bag_slots`.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


def _bot():
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.running = True
    c.bag_slots = {1: [0xAAAA, 5]}
    c.bag_counts = {0xAAAA: 5}
    c.bag_items = {}
    c.equip_by_fit = {3: 0x1111, 5: 0x2222}
    c.pet_equip_by_fit = {}
    c.equipped_items = [{"id": 0x1111}, {"id": 0x2222}]
    c._equip_seq = 0
    c.da_gui = []
    c.send = lambda op, body: c.da_gui.append((op, body))
    c._recalc_char_equip_stats = lambda: None
    c._cap_nhat_do_trong_ban_ghi_pet = lambda *a, **k: None
    c._mount_item_name = lambda tid: "mon"
    c.bag_capacity = lambda: 30
    return c


class TestCoiDoLanHai(unittest.TestCase):
    def test_mon_vua_coi_VAO_bag_slots(self):
        c = _bot()
        c._on_unequip_done(3, follow=0, o_tui=2)
        self.assertIn(2, c.bag_slots, "mon vua coi khong vao tui -> o do van bi coi la TRONG")
        self.assertEqual(c.bag_slots[2][0], 0x1111)

    def test_lan_coi_THU_HAI_chon_O_KHAC(self):
        c = _bot()
        o1 = c.bag_first_empty_slot()
        c._on_unequip_done(3, follow=0, o_tui=o1)
        o2 = c.bag_first_empty_slot()
        self.assertNotEqual(o1, o2, "van tro trung o cu -> server nuot lenh coi thu hai")

    def test_KHONG_de_len_o_dang_co_do(self):
        c = _bot()
        c._on_unequip_done(3, follow=0, o_tui=1)   # o 1 dang co san item khac
        self.assertEqual(c.bag_slots[1], [0xAAAA, 5], "ghi de mat item dang co trong tui")

    def test_pet_cung_the(self):
        c = _bot()
        c.pet_equip_by_fit = {2: {4: 0x3333}}
        c._on_unequip_done(4, follow=2, o_tui=3)
        self.assertEqual(c.bag_slots.get(3, [None])[0], 0x3333)

    def test_bat_goi_S023_022_cua_pet(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('pkt[7:9] == b"\\x16\\x00"', s,
                      "khong bat S:023-022 -> coi do pet cung ket y het")
        i = s.find('pkt[7:9] == b"\\x16\\x00"')
        self.assertIn("o_tui=pkt[11]", s[i:i + 250])

    def test_nhanh_char_doc_o_tui_tu_goi(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find('pkt[7:9] == b"\\x10\\x00"')
        self.assertGreater(i, 0)
        self.assertIn("o_tui=", s[i:i + 250], "bo qua truong 'o tui' ma server da chi san")


if __name__ == "__main__":
    unittest.main()
