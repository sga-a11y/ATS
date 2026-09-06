"""PHA PHO BAN TO DOI do DIEU PHOI giu - acc khong om timer rieng, khong ai di "clear" cho ai.

Truoc day moi acc tu dat `self._phoban_until = time.time() + 600` NGAY luc accept loi moi PB, va
`go_to_town()` BAIL khi co con han:

    if time.time() < getattr(self, "_phoban_until", 0):
        log.info("... go_to_town: dang vao pho ban -> ngung teleport (theo + danh pho ban)")
        return False

PB vo giua chung (phong thieu nguoi / co dis) thi KHONG AI ha co: leader ha cua rieng no, member
nao da roi vong cho `o5_state` thi om du 10 phut.

Ca that 07/09 - 651 dong log "dang vao pho ban -> ngung teleport":

    p53  02:40:32 [vumhai] (LEADER) roster phong pho ban chi 3/4 member sau 8.3s -> HUY danh
         02:40:33 [vumhai] THOAT PHO BAN TO DOI (C:047-010) - khong relogin
         02:40:33 [vumhai] -> da ra khoi pho ban (map 62002 -> 12001)
         02:40:39..02:45:41  qv813/qv814/qv815 spam "dang vao pho ban -> ngung teleport"
         02:45:46  RECONNECT: relogin HANG LOAT (ca party bi ep)
    p51  02:51:33..02:51:56  mh212 dang ket y het

User chot 07/09: "clear voi giu cai lon gi nua, bot dieu phoi het di". Nen bo han timer per-acc:
pha PB gio la MOT o trong `bot/client._PARTY_PB_PHA` - dieu phoi GHI (`dat_pha_pho_ban`), moi acc
DOC (`dang_pha_pho_ban`). Bat khi vao pha, tat o `finally` - xong/thieu nguoi/dis deu mot duong.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import dat_pha_pho_ban, dang_pha_pho_ban   # noqa: E402


def _src(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestKhongConTimerPerAcc(unittest.TestCase):
    def test_da_bo_han_phoban_until(self):
        for f in (("bot", "client.py"), ("run_party_digioi.py",)):
            for d in _src(*f).splitlines():
                t = d.strip()
                if t.startswith("#") or t.startswith('"""'):
                    continue   # chu thich lich su duoc phep nhac ten
                self.assertNotIn("_phoban_until", d, "%s: %s" % (f[-1], t))

    def test_go_to_town_doc_pha_cua_dieu_phoi(self):
        s = _src("bot", "client.py")
        i = s.find('log.info("[%s] go_to_town: dang vao pho ban')   # CHO GOI, khong phai chu thich
        self.assertGreater(i, 0)
        self.assertIn("dang_pha_pho_ban(self.party_idx)", s[max(0, i - 300):i])


class TestChiDieuPhoiGhi(unittest.TestCase):
    def test_chi_MOT_cho_bat_va_MOT_cho_tat(self):
        s = _src("run_party_digioi.py")
        bat = [d for d in s.splitlines() if "dat_pha_pho_ban(pidx, True)" in d]
        tat = [d for d in s.splitlines() if "dat_pha_pho_ban(pidx, False)" in d]
        self.assertEqual(len(bat), 1, bat)
        self.assertEqual(len(tat), 1, tat)

    def test_tat_nam_trong_finally(self):
        """Xong / thieu nguoi / co dis / ngoai le - MOT duong tat, khong sot nhanh nao."""
        s = _src("run_party_digioi.py")
        i = s.find("dat_pha_pho_ban(pidx, False)")
        self.assertGreater(i, 0)
        self.assertIn("finally:", s[max(0, i - 700):i])

    def test_acc_khong_tu_bat_pha(self):
        """Acc accept loi moi PB thi KHONG duoc tu bat pha cho ca party (L1: mot cho quyet)."""
        s = _src("bot", "client.py")
        self.assertNotIn("dat_pha_pho_ban(", s.split("def dat_pha_pho_ban")[-1],
                         "client tu bat/tat pha PB")


class TestHanhVi(unittest.TestCase):
    PIDX = 4242

    def tearDown(self):
        dat_pha_pho_ban(self.PIDX, False)

    def test_bat_roi_tat(self):
        self.assertFalse(dang_pha_pho_ban(self.PIDX))
        dat_pha_pho_ban(self.PIDX, True)
        self.assertTrue(dang_pha_pho_ban(self.PIDX))
        dat_pha_pho_ban(self.PIDX, False)
        self.assertFalse(dang_pha_pho_ban(self.PIDX))

    def test_tat_hai_lan_khong_loi(self):
        dat_pha_pho_ban(self.PIDX, False)
        dat_pha_pho_ban(self.PIDX, False)
        self.assertFalse(dang_pha_pho_ban(self.PIDX))

    def test_party_khac_khong_anh_huong(self):
        dat_pha_pho_ban(self.PIDX, True)
        self.assertFalse(dang_pha_pho_ban(self.PIDX + 1))

    def test_party_idx_None_an_toan(self):
        dat_pha_pho_ban(None, True)
        self.assertFalse(dang_pha_pho_ban(None))


if __name__ == "__main__":
    unittest.main()
