"""Recv-loop phai theo doi THOAI trong thap 2K, khong chi trong pho ban to doi.

Ca that 20/09 (user: "event nhi kieu tuan truoc co loi deo dau"): CA NGAY khong mot acc nao danh
duoc tran 2K nao, khong ai len duoc tang nao - o CA engine cu lan engine moi.

    16:47:25 [ttmmot] 2K: bam idx=3 tai pos=(987, 439) map=12922 kenh=1
    16:47:28 [ttmmot] 2K: idx=3 khong mo thoai sau 3s -> coi nhu diem da het quai

Doi chieu capture MuMu cung ngay: nguoi that bam DUNG goi do thi server tra thoai sau 0.06s roi
vao tran. Tuc bot gui dung, nhung KHONG NGHE THAY tra loi.

Goc: `_fight_one` biet "thoai da mo" qua `client._last_dialog_evt`, ma recv-loop chi cap nhat moc
do khi `in_team_dungeon()`. Ngay 14/09 `in_team_dungeon()` doi tu "doc `_team_dungeon_until`"
sang "doc `current_map` in TEAM_DUNGEON_MAPS" (sua bug party 44 tu nhan dang o PB khi da ve thanh
- doi la dung). Nhung 2K dung nho chinh cai moc thoi gian do, va `run_floor_crawl` van dat no kem
chu thich "BAT BUOC cho 2K vi recv-loop CHI cap nhat _last_dialog_evt trong cua so nay".
Tu 14/09 khong ai doc moc ay nua -> trong thap 2K, `_last_dialog_evt` DONG BANG.

Loi nam trong `client.py` nen dung cho ca hai engine - day la ly do doi engine khong cuu duoc gi.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


class TestMapThap2KDuocTinhLaKichBanThoai(unittest.TestCase):
    def test_map_trong_thap_2k(self):
        for m in (12922, 12930, 12959):
            self.assertTrue(C.in_floor_crawl_map(m), "map %s phai duoc tinh la trong thap 2K" % m)

    def test_map_NGOAI_thap_thi_khong(self):
        for m in (12001, 12003, 12921, 62002, 0, None):
            self.assertFalse(C.in_floor_crawl_map(m), "map %s khong phai thap 2K" % m)

    def test_khong_lam_hong_pho_ban_to_doi(self):
        """4 map PB van phai duoc `in_team_dungeon()` nhan - khong duoc vi them 2K ma doi no."""
        self.assertEqual(C.TEAM_DUNGEON_MAPS, frozenset({62002, 62011, 62012, 62013}))


class TestRecvLoopTheoDoiThoaiTrongThap(unittest.TestCase):
    def test_cua_cap_nhat_last_dialog_evt_phu_ca_thap_2K(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("self._last_dialog_evt = time.time()")
        self.assertGreater(i, 0)
        # cua `if` gan nhat NGAY TRUOC cho gan moc thoi gian do
        truoc = src[:i]
        j = truoc.rfind("opcode == 0x14")
        self.assertGreater(j, 0)
        khoi = truoc[j - 200:]
        self.assertIn("in_floor_crawl_map", khoi,
                      "thieu cua nay = trong thap 2K khong bao gio biet thoai da mo")

    def test_tra_cuu_phai_RE_vi_nam_trong_recv_loop(self):
        """Duyet ca `config.EVENTS` moi goi 0x14 la qua ton - phai co cache theo map_id."""
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def in_floor_crawl_map(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("_THAP_SU_KIEN_CACHE", than)


if __name__ == "__main__":
    unittest.main()
