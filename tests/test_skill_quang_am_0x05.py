"""Skill Quang/Am (chuyen sinh 3) nam o DANH SACH THU 2 cua 0x05 sub03 (KNOWLEDGE muc 7).

Khong chia theo ban: char chua chuyen sinh 3 -> Turn3Element=0 + list 2 rong -> khong co skill.
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import client as C


def _goi(ds1, t3_elem, ds2):
    body = bytearray(b"\x03\x00") + bytes(94)
    body += len(ds1).to_bytes(2, "little")
    for sid, lv in ds1:
        body += sid.to_bytes(2, "little") + bytes([lv])
    body += bytes([t3_elem]) + bytes(8) + bytes(12)
    body += len(ds2).to_bytes(2, "little")
    for sid, lv in ds2:
        body += sid.to_bytes(2, "little") + bytes([lv])
    body += bytes(20)
    return b"\xc0\x91\x00\x00\x00\x00\x05" + bytes(body)


def _client():
    c = C.GameClient.__new__(C.GameClient)
    c._label = "t"
    c.state = types.SimpleNamespace(skills_char=[])
    c.char_skill_lv = {}
    c.char_turn3_element = 0
    return c


class TestSkillQuangAm(unittest.TestCase):
    def test_char_quang_co_ca_skill_list_2(self):
        c = _client()
        c._parse_skill_list_0x05(_goi([(10001, 1), (11013, 10)], 7, [(22015, 10), (22002, 5)]))
        self.assertEqual(c.char_turn3_element, 7)
        self.assertEqual(c.state.skills_char, [10001, 11013, 22015, 22002])
        self.assertEqual(c.char_skill_lv[22002], 5)

    def test_char_chua_chuyen_sinh_3_khong_co_skill_quang(self):
        c = _client()
        c._parse_skill_list_0x05(_goi([(10001, 1), (11013, 10)], 0, []))
        self.assertEqual(c.char_turn3_element, 0)
        self.assertEqual(c.state.skills_char, [10001, 11013])


if __name__ == "__main__":
    unittest.main()
