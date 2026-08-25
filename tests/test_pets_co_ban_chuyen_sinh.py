"""pets.json phai chua ca vo tuong CHI CO 1 (hoac 0) SKILL.

Bo loc cu ">=2 skill" loai nham vo tuong that: 0x3710 "Cuu Soi" (1 skill) -> GUI hien tro
"Pet (0x3710)" khong ten, va bot cung khong biet skill/he/doanh cua no.
Khong the noi thanh ">=1 skill" vi 2468 ban ghi 1-skill phan lon la QUAI. Dau hieu tach dung:
vo tuong that CO BAN CHUYEN SINH (cot `turn` ip+58 nhan 0/1/2), quai thi khong.
"""
from __future__ import annotations

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PETS = os.path.join(ROOT, "pets.json")


class TestPetsJson(unittest.TestCase):
    def setUp(self):
        with open(PETS, encoding="utf-8") as fh:
            self.p = json.load(fh)["pets"]

    def test_co_pet_1_skill_bi_sot_truoc_day(self):
        """Cuu Soi - con pet that cua user lam lo ra bug nay."""
        d = self.p.get("0x3710")
        self.assertIsNotNone(d, "0x3710 Cuu Soi lai bi loai khoi pets.json")
        self.assertIn("Cửu Sởi", d["name"])
        self.assertEqual(d["skills"], [11003])
        self.assertEqual((d.get("he"), d.get("doanh")), ("Thuy", "Du"))

    def test_van_loai_quai_khong_co_ban_chuyen_sinh(self):
        """Neu ai do noi bo loc thanh '>=1 skill' thi 2032 quai se tran vao - bat o day."""
        for tid, ten in (("0x273d", "Du Binh"), ("0x2738", "Tiêu Võ Sĩ"),
                         ("0x3a99", "Ngô Phổ")):
            self.assertNotIn(tid, self.p, "%s (%s) khong co ban chuyen sinh -> khong phai pet"
                                          % (tid, ten))

    def test_khong_mat_pet_nao_so_voi_bo_loc_cu(self):
        """Moi muc >=2 skill (bo loc cu) phai con nguyen - noi bo loc chi duoc THEM."""
        nhieu_skill = [k for k, v in self.p.items() if len(v["skills"]) >= 2]
        self.assertGreaterEqual(len(nhieu_skill), 4566)

    def test_pet_moc_van_dung_skill(self):
        self.assertEqual(self.p["0xa05a"]["skills"], [13009, 13011, 13013])   # Quan Vu
        self.assertEqual(self.p["0xa051"]["skills"], [12003, 12009, 12010])


class TestToolBoLoc(unittest.TestCase):
    def test_tool_dung_cot_chuyen_sinh_chu_khong_phai_canBeCatch(self):
        """ip+22 la canBeCatch (chi 0/1); doi chuyen sinh o ip+58. Dung nham la bo loc vo tac dung."""
        with open(os.path.join(ROOT, "tools", "crack_pets.py"), encoding="utf-8") as fh:
            src = fh.read()
        than = src.split("def parse_pets_seq", 1)[1].split("\ndef ", 1)[0]
        than = than.split('"""', 2)[2]        # bo docstring, tranh bay "khop trong chu thich"
        self.assertIn("ip + 58", than, "khong doc cot chuyen sinh")
        self.assertIn("co_chuyen_sinh", than)


if __name__ == "__main__":
    unittest.main()
