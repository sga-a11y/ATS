# -*- coding: utf-8 -*-
"""MODE TRAIN: ca party DA o map train roi thi KHONG teleport ve thanh de keo len lai.

User chot 27/08:
  "cung o map train roi thi check kenh, neu cung kenh roi thi lap party keo ra train,
   ko cung kenh thi sync kenh thoi, ko can ve thanh"
  "ca reform va ca di train luc dau"

Truoc day moi lan thieu nguoi trong party (moi 20s chua du, cho member san sang qua lau, reform_gen
tang...) la _do_reform() -> CA PARTY teleport ve thanh roi di route len lai, du tat ca dang dung
san o bai train. Mat vai phut moi vong va de lac them nguoi giua duong.
"""
import io
import os
import re
import unittest

import run_party_digioi as rp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestPhanLoaiTaiCho(unittest.TestCase):
    def test_cung_map_train_cung_kenh(self):
        self.assertEqual(rp._party_train_tai_cho([700, 700, 700], [2, 2, 2], 700), "cung_kenh")

    def test_cung_map_train_lech_kenh(self):
        self.assertEqual(rp._party_train_tai_cho([700, 700], [2, 3], 700), "lech_kenh")

    def test_co_dua_o_map_khac(self):
        self.assertEqual(rp._party_train_tai_cho([700, 12061], [2, 2], 700), "lech_map")

    def test_ca_party_o_map_KHAC_train_van_la_lech_map(self):
        """Cung nhau o nham map (vd ca lu con trong thanh) thi VAN phai gom ve, khong lap party."""
        self.assertEqual(rp._party_train_tai_cho([12061, 12061], [1, 1], 700), "lech_map")

    def test_chua_biet_kenh_thi_coi_la_LECH(self):
        """Doc chua ra kenh ma dam ket luan 'cung kenh' la lap party xong moi khong toi noi."""
        self.assertEqual(rp._party_train_tai_cho([700, 700], [2, None], 700), "lech_kenh")

    def test_khong_co_du_lieu_thi_khong_dam_xu_ly_tai_cho(self):
        self.assertEqual(rp._party_train_tai_cho([], [], 700), "lech_map")
        self.assertEqual(rp._party_train_tai_cho([700], [1], 0), "lech_map")


def _than_tai_cho(s, bo_docstring=False, bo_comment=False):
    """Than DAY DU cua `_party_tai_cho_xu_ly` - neo theo HAM, khong theo cua so ky tu co dinh.

    Cac test duoi tung cat `s[i:i + 5600]`. Them mot khoi comment vao ham la truot het, va truot
    kieu do bao "code sai" trong khi hanh vi khong doi gi - dung cai bay ghi o L3i.

    `bo_comment=True` khi test kiem MA CHAY (vd "khong duoc goi `_do_reform` o day"): nhac ten ham
    trong ghi chu de giai thich la chuyen binh thuong, khong phai vi pham.
    """
    i = s.find("def _party_tai_cho_xu_ly(")
    assert i > 0
    # Ham ket thuc khi THUT LE GIAM, khong phai khi gap `def` ke tiep: giua than con nhieu ham long
    # nhau, va sau than con code khac truoc `def` mức 8 tiep theo (lay theo `def` ra 100k ky tu).
    dong = s[i:].split("\n")
    het = len(dong)
    for k, d in enumerate(dong[1:], start=1):
        if d.strip() and not d.startswith(" " * 12):
            het = k
            break
    than = "\n".join(dong[:het])
    if bo_docstring:
        _q = '"' * 3
        k = than.find(_q, than.find(_q) + 3)
        than = than[k + 3:] if k > 0 else than
    if bo_comment:
        than = re.sub(r"#.*", "", than)
    return than






if __name__ == "__main__":
    unittest.main()
