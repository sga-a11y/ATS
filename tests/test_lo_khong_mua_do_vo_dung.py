"""Soi lo tab CHUYEN SINH: khong tu mua mon DA VO DUNG voi acc (ton slot tui).

User chot 01/09: "mua no cung re thoi, nhung mua vat pham ko can dung nua no ton slot do la chinh".

  - Kim Toa <X>: trong 4 pet MANG THEO hoac NHA TRO da co <X> o rb1 / rb2 -> khong mua.
  - Me <X>: <X> DA HOC dac ky -> khong mua.
  - Tuong Tinh: giu nguyen, mua khong gioi han.

GHEP ITEM VOI VO TUONG: ten item bi viet tat ("K.Toa Ma Ng.Nghia" vs vo tuong "Ma Nguyen Nghia")
nen KHONG duoc ghep bang ten. `items_gamedata.json` co san npc_id:
    a1k = 65 Kim Toa (a1v = rb0, a2v = rb1) | 66 Me | 67 T.Tinh  (Me/T.Tinh: a1v = rb1, a2v = rb2)

DAC KY CUA PET NHA TRO KHONG DOC DUOC: co `specialSkillLearned` chi co trong goi `0x0f` (vo tuong
mang theo, `Role.lua:857`); nha tro ve qua `S:031-006` -> `Inn.SaveNpc` chi co npcId/level/exp/hp/
name/status (`Logic/Inn.lua:25`) - CHINH CLIENT cung khong biet. Nen bot NHO LAI vao cache luc no
con mang theo (`load_dac_ky_cache`).
"""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as bc              # noqa: E402
from bot.client import GameClient         # noqa: E402

KIM_TOA_VU_DOC = 0xB79F      # a1v=10098 (Vu Doc rb0) -> a2v=41010 (rb1), rb2 = 45230
VU_DOC_RB1, VU_DOC_RB2 = 41010, 45230


def _mot_mon_me():
    """(item_id Me, rb1 cua vo tuong do). KHONG phai vo tuong nao cung co ca Me lan T.Tinh -
    Vu Doc chi co T.Tinh - nen lay dong tu bang thay vi viet cung mot ten."""
    for tid, v in sorted(bc._load_chuyen_sinh_map().items()):
        if v["loai"] == bc.CS_ME and v["rb1"]:
            return tid, v["rb1"]
    return None, 0


class _St:
    def __init__(self, carried=()):
        self.carried_pets = list(carried)


class _Bot:
    _lo_da_du_khoi_mua = GameClient._lo_da_du_khoi_mua
    vo_tuong_dang_co = GameClient.vo_tuong_dang_co
    dac_ky_da_hoc = GameClient.dac_ky_da_hoc

    def __init__(self, carried=(), inn=(), special=(), cache=()):
        self._label = "t"
        self._username = None            # khong doc/ghi file cache that
        self.state = _St(carried)
        self.vantieu_roster_ids = {i + 1: v for i, v in enumerate(inn)}
        self.pet_special_skill = {p: True for p in special}
        self._dac_ky_biet = set(cache)


class TestBangMapItemChuyenSinh(unittest.TestCase):
    def setUp(self):
        self.m = bc._load_chuyen_sinh_map()

    def test_du_ca_3_loai(self):
        loai = {v["loai"] for v in self.m.values()}
        self.assertEqual(loai, {bc.CS_KIM_TOA, bc.CS_ME, bc.CS_TUONG_TINH})

    def test_kim_toa_ghep_dung_npc_id(self):
        """K.Toa Vu Doc -> Vu Doc rb0 (0x2772) va rb1 (0xa032). Ghep bang ID, khong bang ten."""
        v = self.m[KIM_TOA_VU_DOC]
        self.assertEqual(v["loai"], bc.CS_KIM_TOA)
        self.assertEqual(v["rb0"], 0x2772)
        self.assertEqual(v["rb1"], VU_DOC_RB1)
        self.assertEqual(v["rb2"], VU_DOC_RB2, "rb2 phai suy duoc tu item Me/T.Tinh cung rb1")

    def test_ten_item_viet_tat_van_ghep_duoc(self):
        """'K.Toa Ma Ng.Nghia' vs vo tuong 'Ma Nguyen Nghia' - ghep bang ten la truot."""
        with open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            gd = json.load(fh)
        with open(os.path.join(ROOT, "pets.json"), encoding="utf-8") as fh:
            pets = json.load(fh)["pets"]
        tid = 0xB7FB
        self.assertIn("Ng.Nghĩa", gd["0x%04x" % tid]["name"])
        self.assertEqual(pets["0x%04x" % self.m[tid]["rb0"]]["name"], "Mã Nguyên Nghĩa rb0")

    def test_moi_item_chi_thuoc_MOT_loai(self):
        """a1k luon == a2k -> khong co item nao vua Kim Toa vua Me."""
        self.assertTrue(all(v["loai"] in (65, 66, 67) for v in self.m.values()))

    def test_KHONG_lot_id_rac_vao_bang(self):
        """`a1v`/`a2v` khong phai luc nao cung la npc_id: 'Me Nhan Dieu Tuyet' co a1v=100 (LEVEL
        yeu cau), 'K.Toa Ngoc Tho' co a1v/a2v khong he nam trong pets.json - 50/938 mon dinh kieu
        nay. Lay bua vao la co the CHAN NHAM mon dang can mua."""
        with open(os.path.join(ROOT, "pets.json"), encoding="utf-8") as fh:
            hop_le = {int(k, 16) for k in json.load(fh)["pets"]}
        rac = [(t, v) for t, v in self.m.items()
               for bac in ("rb0", "rb1", "rb2") if v[bac] and v[bac] not in hop_le]
        self.assertEqual(rac, [], "con id khong phai vo tuong trong bang")

    def test_mon_khong_lan_ra_vo_tuong_thi_BO_KHOI_BANG(self):
        """Bo khoi bang = giu hanh vi cu (van mua), an toan hon la doan bua."""
        self.assertTrue(all(v["rb1"] or v["rb2"] for v in self.m.values()))


class TestKimToa(unittest.TestCase):
    def test_chua_co_tuong_thi_VAN_MUA(self):
        self.assertIsNone(_Bot()._lo_da_du_khoi_mua(KIM_TOA_VU_DOC))

    def test_chi_co_rb0_thi_VAN_MUA(self):
        """rb0 chinh la con can Kim Toa de reborn - co no thi cang phai mua."""
        b = _Bot(carried=[(0x2772, "Vu Độc rb0")])
        self.assertIsNone(b._lo_da_du_khoi_mua(KIM_TOA_VU_DOC))

    def test_da_co_rb1_MANG_THEO_thi_khong_mua(self):
        b = _Bot(carried=[(VU_DOC_RB1, "Vu Độc")])
        self.assertIsNotNone(b._lo_da_du_khoi_mua(KIM_TOA_VU_DOC))

    def test_da_co_rb1_o_NHA_TRO_thi_khong_mua(self):
        b = _Bot(inn=[VU_DOC_RB1])
        self.assertIsNotNone(b._lo_da_du_khoi_mua(KIM_TOA_VU_DOC))

    def test_da_co_rb2_thi_khong_mua(self):
        b = _Bot(inn=[VU_DOC_RB2])
        self.assertIsNotNone(b._lo_da_du_khoi_mua(KIM_TOA_VU_DOC))

    def test_tuong_KHAC_khong_anh_huong(self):
        b = _Bot(inn=[41099])            # Ma Nguyen Nghia rb1
        self.assertIsNone(b._lo_da_du_khoi_mua(KIM_TOA_VU_DOC))


class TestMe(unittest.TestCase):
    def setUp(self):
        self.tid, self.rb1 = _mot_mon_me()
        self.assertIsNotNone(self.tid, "khong tim thay item Me nao trong bang")

    def test_chua_hoc_dac_ky_thi_VAN_MUA(self):
        """Co tuong nhung chua hoc dac ky -> Me van can."""
        self.assertIsNone(_Bot(carried=[(self.rb1, "x")])._lo_da_du_khoi_mua(self.tid))

    def test_DA_HOC_dac_ky_thi_khong_mua(self):
        b = _Bot(carried=[(self.rb1, "x")], special=[self.rb1])
        self.assertIsNotNone(b._lo_da_du_khoi_mua(self.tid))

    def test_CACHE_nho_du_da_cat_vao_nha_tro(self):
        """Cat vao nha tro -> khong con doc duoc co dac ky nua; phai nho lai tu truoc."""
        b = _Bot(inn=[self.rb1], cache=[self.rb1])
        self.assertIsNotNone(b._lo_da_du_khoi_mua(self.tid))

    def test_CO_tuong_nhung_chua_hoc_thi_KHONG_bi_chan_oan(self):
        """Khac Kim Toa: Me chan theo DA HOC DAC KY, khong phai theo 'da co tuong'."""
        self.assertIsNone(_Bot(inn=[self.rb1])._lo_da_du_khoi_mua(self.tid))


class TestTuongTinhGiuNguyen(unittest.TestCase):
    def test_khong_gioi_han(self):
        """User chot: Tuong Tinh mua khong gioi han."""
        tid = next(t for t, v in bc._load_chuyen_sinh_map().items()
                   if v["loai"] == bc.CS_TUONG_TINH and v["rb1"] == VU_DOC_RB1)
        b = _Bot(carried=[(VU_DOC_RB1, "Vu Độc")], inn=[VU_DOC_RB2], special=[VU_DOC_RB1])
        self.assertIsNone(b._lo_da_du_khoi_mua(tid), "T.Tinh bi chan -> sai y user")


class TestKhongLamHongItemKhac(unittest.TestCase):
    def test_item_ngoai_bang_thi_bo_qua(self):
        self.assertIsNone(_Bot()._lo_da_du_khoi_mua(0x1234))


class TestGhiCacheDacKy(unittest.TestCase):
    def test_ca_hai_nguon_dac_ky_deu_ghi_cache(self):
        """`S:020-049` (vua hoc) va goi `0x0f` (login) - bo sot cho nao la cat kho di la quen."""
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertEqual(s.count("self._nho_dac_ky("), 2)

    def test_cache_KHONG_XOA_id_cu(self):
        """Dac ky hoc roi la vinh vien; ghi de danh sach moi la mat tri nho cua cac lan truoc."""
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def save_dac_ky_cache(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn('entry["dac_ky"] = sorted(cu | moi)', than)


class TestApVaoProcessFurnace(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_chi_ap_cho_tab_chuyen_sinh(self):
        i = self.src.find("_thua = self._lo_da_du_khoi_mua(")
        self.assertGreater(i, 0, "chua ap luat vao process_furnace")
        # `nhom` = kind lo THUONG tuong ung; lo hoang kim gui kind 6 nhung van thuoc nhom 5
        # (chung pool) -> luat phai bam `nhom`, xem tests/test_lo_hoang_kim.py.
        self.assertIn("if nhom == 5 else None", self.src[i:i + 120])

    def test_nam_trong_nhanh_AUTO(self):
        """User chi noi ve muc 'tu mua'; nhanh thong bao giu nguyen de khong nuot canh bao."""
        i_auto = self.src.find('if mode == "auto":')
        i_thua = self.src.find("_thua = self._lo_da_du_khoi_mua(")
        i_notify = self.src.find("else:   # notify")
        self.assertLess(i_auto, i_thua)
        self.assertLess(i_thua, i_notify)


if __name__ == "__main__":
    unittest.main()
