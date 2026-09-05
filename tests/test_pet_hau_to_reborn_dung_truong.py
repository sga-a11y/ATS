"""Hau to rb0/rb1/rb2 cua ten pet phai lay tu `turn` (ip+58), KHONG phai `canBeCatch` (ip+22).

User hoi 05/09: "sao con Luc Ton ko co chu rb0". Truy ra: `tools/crack_pets.py` lay hau to tu
ip+22 = `canBeCatch` (抓捕否) - chinh file do DA co chu thich canh bao la SAI NGHIA nhung chua sua
vi "doi offset lam DOI TEN 2306/4566 pet".

Bang chung `turn` (ip+58) moi la doi chuyen sinh, do tren chinh Npc_C.dat (8360 ban ghi):
  - ip+22 chi nhan {0, 1}          -> khong the la 3 doi (rb0/rb1/rb2)
  - ip+58 nhan {0, 1, 2}           -> du 3 doi
  - khop dai id da biet tu du lieu chuyen sinh (`client.py::_load_chuyen_sinh_map`):
        0xA0xx (41xxx) = rb1 -> turn=1 o CA 572/572 ban ghi
        0xB0xx (45xxx) = rb2 -> turn=2 o 595/596
        0x27xx (10xxx) = rb0 -> turn=0 o 735/773

Quy uoc dat ten user chot 05/09 (GIU NGUYEN nhu truoc, chi doi nguon doc):
    turn 0 -> "ten rb0" | turn 1 -> "ten" (khong hau to) | turn 2 -> "ten rb2"
"""
from __future__ import annotations

import io
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPC = os.path.join(ROOT, "gamedata", "Data", "Npc_C.dat")


def _src():
    with io.open(os.path.join(ROOT, "tools", "crack_pets.py"), encoding="utf-8") as fh:
        return fh.read()


def _pets():
    with io.open(os.path.join(ROOT, "pets.json"), encoding="utf-8") as fh:
        return json.load(fh)["pets"]


class TestNguonDocDungTruong(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_lay_rb_tu_turn_khong_phai_canBeCatch(self):
        i = self.src.find("def parse_pets_seq(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        m = re.search(r'pets\[pid\] = \{"name": name, "skills": sk, "rb": (\w+)\}', than)
        self.assertIsNotNone(m, "khong tim thay cho gan rb")
        self.assertEqual(m.group(1), "turn",
                         "van lay canBeCatch lam doi chuyen sinh -> hau to rb sai nghia")

    def test_quy_uoc_dat_ten_giu_nguyen(self):
        i = self.src.find("def _form_name(")
        than = self.src[i:self.src.find("\ndef ", i + 10)]
        self.assertIn("if rb == 1:", than, "rb1 phai la KHONG hau to")
        self.assertIn('return "%s rb%d" % (base, rb)', than)


class TestDuLieuNpcDat(unittest.TestCase):
    """Do thang tren gamedata - test nay chi chay khi may co Npc_C.dat (khong nam trong git)."""

    def setUp(self):
        if not os.path.exists(NPC):
            self.skipTest("khong co gamedata/Data/Npc_C.dat")
        import struct
        with io.open(NPC, "rb") as fh:
            d = fh.read()
        count = struct.unpack_from("<i", d, 0)[0]
        self.recs, i = [], 4
        for _ in range(count):
            nl = struct.unpack_from("<H", d, i)[0]
            j = i + 2 + nl
            ip = j + 1
            pid = struct.unpack_from("<H", d, ip)[0]
            self.recs.append((pid, d[ip + 22], d[ip + 58]))
            i = ip + 80

    def test_canBeCatch_chi_co_2_gia_tri(self):
        """2 gia tri thi KHONG THE bieu dien 3 doi chuyen sinh."""
        self.assertEqual(sorted({c for _p, c, _t in self.recs}), [0, 1])

    def test_turn_co_du_3_doi(self):
        self.assertEqual(sorted({t for _p, _c, t in self.recs}), [0, 1, 2])

    def test_turn_khop_dai_id_chuyen_sinh(self):
        """Doi chieu doc lap: dai id lay tu du lieu item chuyen sinh, khong lien quan Npc_C.dat."""
        def ty_le(lo, hi, mong_doi):
            ds = [t for p, _c, t in self.recs if lo <= p <= hi]
            self.assertTrue(ds, "khong co ban ghi nao trong dai 0x%04x-0x%04x" % (lo, hi))
            return sum(1 for t in ds if t == mong_doi) / len(ds)
        self.assertEqual(ty_le(0xa000, 0xa3ff, 1), 1.0, "0xA0xx phai la rb1 (turn=1) TOAN BO")
        self.assertGreater(ty_le(0xafc8, 0xb3ff, 2), 0.99, "0xB0xx phai la rb2 (turn=2)")
        self.assertGreater(ty_le(0x2710, 0x2fff, 0), 0.94, "0x27xx phai la rb0 (turn=0)")


class TestPetsJsonDaSinhLai(unittest.TestCase):
    def setUp(self):
        self.pets = _pets()

    def test_pet_dai_0xA0xx_KHONG_co_hau_to(self):
        """rb1 = khong hau to. Truoc khi sua, dai nay lan lon co/khong."""
        sai = [k for k, v in self.pets.items()
               if 0xa000 <= int(k, 16) <= 0xa3ff and " rb" in v.get("name", "")]
        self.assertEqual(sai[:5], [], "%d pet rb1 van dinh hau to" % len(sai))

    def test_pet_dai_0xB0xx_deu_la_rb2(self):
        ds = [v["name"] for k, v in self.pets.items() if 0xafc8 <= int(k, 16) <= 0xb3ff]
        self.assertTrue(ds)
        sai = [n for n in ds if not n.endswith(" rb2")]
        self.assertLessEqual(len(sai), max(1, len(ds) // 100),
                             "qua nhieu pet dai 0xB0xx khong phai rb2: %s" % sai[:5])

    def test_vi_du_cua_user(self):
        """Luc Ton 0x32dd: turn=0 -> phai co 'rb0' (truoc khi sua thi KHONG co, user hoi vi vay)."""
        self.assertEqual(self.pets["0x32dd"]["name"], "Lục Tốn rb0")
        self.assertEqual(self.pets["0x36b9"]["name"], "Lữ Bố rb0")
        self.assertEqual(self.pets["0xa05a"]["name"], "Quan Vũ")        # turn=1 -> khong hau to
        self.assertEqual(self.pets["0xa0db"]["name"], "Tưởng Nghĩa Cừ")

    def test_doi_ten_KHONG_lam_mat_skill(self):
        """Sua nay chi duoc doi TEN. Skill/he/doanh doi la hong bang tra cua bot."""
        self.assertEqual(self.pets["0xa05a"]["skills"], [13009, 13011, 13013])
        self.assertEqual(self.pets["0x32dd"]["skills"], [11005, 11011, 11016])
        self.assertEqual(self.pets["0x32dd"].get("he"), "Thuy")


class TestKhongPhaVungKhac(unittest.TestCase):
    def test_pet_hedoanh_khoa_theo_TEN_GOC(self):
        """`pet_hedoanh.json` khoa la ten KHONG hau to, va crack_pets join bang `p["name"]`
        (ten goc, truoc khi them hau to) -> doi hau to KHONG lam hong join."""
        with io.open(os.path.join(ROOT, "pet_hedoanh.json"), encoding="utf-8") as fh:
            hd = json.load(fh)
        co_hau_to = [k for k in hd if k.endswith(" rb0") or k.endswith(" rb2")]
        self.assertEqual(co_hau_to, [], "khoa pet_hedoanh dinh hau to -> join se lech khi doi ten")
        src = _src()
        self.assertIn('hedoanh.get(p["name"])', src, "join phai dung TEN GOC, khong dung ten da gan hau to")

    def test_lo_chuyen_sinh_so_theo_ID_khong_theo_ten(self):
        """`client._ly_do_bo_qua_*` so `info[bac] in co` voi npc id -> doi ten pet khong anh huong."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("info = _load_chuyen_sinh_map().get(int(item_id))")
        self.assertGreater(i, 0)
        khoi = src[i:i + 900]
        self.assertIn("info[bac] in co", khoi)
        self.assertNotIn('name', khoi.split("return")[0])


if __name__ == "__main__":
    unittest.main()
