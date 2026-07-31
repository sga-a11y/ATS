import sys
import unittest
from unittest import mock


with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    from run_party_digioi import _average_party_levels


class TestPartyAverageLevel(unittest.TestCase):
    def test_averages_five_characters_and_five_active_pets(self):
        rows = [
            {"char_level": 155, "pet_name": "Quan Vu", "pet_level": 122},
            {"char_level": 150, "pet_name": "Quan Vu", "pet_level": 126},
            {"char_level": 149, "pet_name": "Thai Van Co", "pet_level": 125},
            {"char_level": 148, "pet_name": "Luu Bi", "pet_level": 120},
            {"char_level": 147, "pet_name": "Tao Thao", "pet_level": 118},
        ]

        self.assertEqual(_average_party_levels(rows), 136)

    def test_account_without_active_pet_only_contributes_character_level(self):
        rows = [
            {"char_level": 100, "pet_name": "", "pet_level": None},
            {"char_level": 80, "pet_name": "Quan Vu", "pet_level": 60},
        ]

        self.assertEqual(_average_party_levels(rows), 80)

    def test_waits_until_all_character_and_active_pet_levels_are_known(self):
        self.assertIsNone(_average_party_levels([
            {"char_level": None, "pet_name": "", "pet_level": None},
        ]))
        self.assertIsNone(_average_party_levels([
            {"char_level": 100, "pet_name": "Quan Vu", "pet_level": None},
        ]))


if __name__ == "__main__":
    unittest.main()
