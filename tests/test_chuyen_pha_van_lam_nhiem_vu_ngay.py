"""CHUYEN PHA (Di Gioi -> train) phai lam nhiem vu hang ngay phan NANG.

User bao 02/09: "co user bao la no ko lam daily quest ... nhin bang quest cua ho thi thieu nhiem
vu 1 2 5".

DO LOG THAT (party.log 01-02/09):
  - 115/115 acc mode `digioi_train` deu dung o `o xong=[3, 4, 6, 7, 8]` - tuc chi cac o NHE
    (gacha pet/card, hop vat pham) do keepalive lam moi gio; thieu dung o 1 (dungeon solo),
    2 (boss the gioi), 5 (pho ban to doi).
  - 700/700 luot "CHUYEN PHA train": trong 5 phut sau do KHONG co mot dong daily hay boss nao.
  - `grep "het gio DG, truoc pho ban doi"` = 0 lan.

BA CUA CHAN (deu trong `run_account`):
  1. pha Di Gioi     -> `_do_startup_* = ... and not is_digioi`
  2. het gio DG      -> hai khoi do nam sau `if not dt_mode:` (dt_mode CHINH LA DG+Train)
  3. pha train       -> `_run_account_supervised` goi `run_account(is_reconnect=not first)` nen
                        pha train luon la `is_reconnect=True`

Cua 3 la cua sai ve NGHIA: chuyen pha KHONG PHAI reconnect - do la lan DAU chay pha train trong
phien, chua he lam viec nao. Reconnect THAT thi van chan nhu cu (tranh churn).
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _quyet_dinh(is_digioi, is_reconnect, chuyen_pha, td_redo=False, o5_redo=False,
                auto_world_boss=True, auto_team_dungeon=True, do_daily=True):
    """Ban sao DUNG cong thuc trong `run_account` - doi cong thuc o do thi bai test nay do."""
    lan_dau = (not is_reconnect) or chuyen_pha
    return (
        bool(auto_world_boss and not is_digioi and lan_dau),
        bool(auto_team_dungeon and not is_digioi and (lan_dau or td_redo)),
        bool(not is_digioi and do_daily and (lan_dau or o5_redo)),
    )


class TestCongThucKhopMaNguon(unittest.TestCase):
    """Neo cong thuc that trong `run_party_digioi.py` (bai test tinh tay o duoi moi co nghia)."""

    def setUp(self):
        self.src = _src()

    def test_chuyen_pha_neo_theo_reuse_client(self):
        self.assertIn("_chuyen_pha = reuse_client is not None", self.src)
        self.assertIn("_lan_dau = (not is_reconnect) or _chuyen_pha", self.src)

    def test_ca_BA_viec_deu_dung_lan_dau(self):
        for ten in ("_do_startup_world_boss", "_do_startup_team", "_do_startup_daily"):
            i = self.src.find(ten + " = bool(")
            self.assertGreater(i, 0, ten)
            self.assertIn("_lan_dau", self.src[i:i + 160], ten)

    def test_KHONG_con_chan_thang_bang_is_reconnect(self):
        for xau in ("and not is_reconnect)", "(not is_reconnect or _td_redo)",
                    "(not is_reconnect or _o5_redo)"):
            self.assertNotIn(xau, self.src, "van con chan thang theo is_reconnect")


class TestLuongDiGioiTrain(unittest.TestCase):
    def test_pha_DI_GIOI_van_KHONG_lam(self):
        """Trong DG thi boss/PB deu phai teleport ra ngoai -> van de sau, khong doi."""
        self.assertEqual(_quyet_dinh(is_digioi=True, is_reconnect=False, chuyen_pha=False),
                         (False, False, False))

    def test_pha_TRAIN_sau_DG_thi_LAM_DU_CA_BA(self):
        """Day la ca hong that: 700/700 luot chuyen pha khong lam gi."""
        self.assertEqual(_quyet_dinh(is_digioi=False, is_reconnect=True, chuyen_pha=True),
                         (True, True, True))

    def test_login_dau_van_lam_nhu_cu(self):
        self.assertEqual(_quyet_dinh(is_digioi=False, is_reconnect=False, chuyen_pha=False),
                         (True, True, True))


class TestReconnectThatVanBiChan(unittest.TestCase):
    """Reconnect that = da lam roi o phien truoc -> khong lam lai (tranh churn teleport)."""

    def test_reconnect_thuong_KHONG_lam(self):
        self.assertEqual(_quyet_dinh(is_digioi=False, is_reconnect=True, chuyen_pha=False),
                         (False, False, False))

    def test_reconnect_do_PB_VO_van_lam_lai_PB(self):
        _b, _pb, _d = _quyet_dinh(is_digioi=False, is_reconnect=True, chuyen_pha=False,
                                  td_redo=True)
        self.assertTrue(_pb)

    def test_reconnect_do_team_dungeon_VO_van_lam_lai_daily(self):
        _b, _pb, _d = _quyet_dinh(is_digioi=False, is_reconnect=True, chuyen_pha=False,
                                  o5_redo=True)
        self.assertTrue(_d)


class TestKhongDungToiCacCoKhac(unittest.TestCase):
    def test_tat_auto_boss_thi_van_khong_danh(self):
        _b, _, _ = _quyet_dinh(is_digioi=False, is_reconnect=True, chuyen_pha=True,
                               auto_world_boss=False)
        self.assertFalse(_b)

    def test_tat_do_daily_thi_van_khong_lam(self):
        _, _, _d = _quyet_dinh(is_digioi=False, is_reconnect=True, chuyen_pha=True,
                               do_daily=False)
        self.assertFalse(_d)

    def test_tat_auto_team_dungeon_thi_van_khong_lam(self):
        _, _pb, _ = _quyet_dinh(is_digioi=False, is_reconnect=True, chuyen_pha=True,
                                auto_team_dungeon=False)
        self.assertFalse(_pb)


class TestChuyenPhaChiTuDuongReuseClient(unittest.TestCase):
    def test_chi_co_MOT_cho_truyen_reuse_client(self):
        """`reuse_client` chi duoc dung cho chuyen pha DG->train; them duong khac la `_lan_dau`
        mat y nghia."""
        src = _src()
        # bo dong khai bao tham so `reuse_client=None` cua chinh `run_account`
        goi = [m for m in re.findall(r"reuse_client=(\w+)", src) if m != "None"]
        self.assertEqual(goi, ["_tiep"], "co duong khac truyen reuse_client -> xem lai `_lan_dau`")


if __name__ == "__main__":
    unittest.main()
