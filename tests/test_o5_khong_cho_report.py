"""o5 (pho ban to doi): KHONG cho report, va member co loi ra khi leader khong vao PB.

Ca that 07/09 party 15 - 26 PHUT (14:40:59 -> 15:06:32), user: "p15 bi lam sao ma ko lap pt va
member bi quai danh le":

    [trusauu] (LEADER) CHO ca party report o5 (4/5)...       <- lap moi 30s, tu 14:40:59
    [trutam]  (member) CHO leader danh xong team dungeon...
    [truchin] im tu 14:40:40 - khong bao gio report
    [trubay] / [trumuoi]  BO CHAY (flee_mode)                <- dung tai bai quai, bi danh le

Trong khi DIEU PHOI ra lenh deu dan moi 2 phut ma KHONG AI NGHE:

    14:57:37 / 14:59:37 / 15:01:38 / 15:03:38 / 15:05:38
      [party 15] DIEU PHOI: ca party da chung kenh 1 nhung doi chi con 0/3 -> LAP LAI PARTY

Hai barrier long nhau:
  - leader: `while True` cho MOI member "report o5" (L2 bat bao cao + L9 cho vo han). Ket o day thi
    leader khong quay lai vong chinh -> diec voi moi lenh dieu phoi.
  - member: `while True` cho leader danh xong PB - hop le KHI PB DANG CHAY THAT, con leader ket cho
    khac thi member dung tai bai quai voi flee_mode, bi quai danh le ma khong danh tra.

Sua:
  - leader DOC MOT PHAT; acc chua bao thi coi nhu DA XONG o5 (mat nhieu nhat mot luot PB, lan chay
    sau van check binh thuong) - khong dung cho.
  - member co hai loi ra cap party: dieu phoi ra lenh moi (`reform_gen` doi), hoac qua 90s ma pha
    PB VAN CHUA BAT (`dang_pha_pho_ban`) -> leader khong he vao PB.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestLeaderKhongChoReport(unittest.TestCase):
    def test_bo_vong_cho_report(self):
        s = _src()
        for d in s.splitlines():
            if "log." in d:
                self.assertNotIn("CHO ca party report o5", d, d.strip())

    def test_acc_chua_bao_thi_coi_nhu_XONG(self):
        s = _src()
        i = s.find("_thieu = [m for m in members if m not in statuses]")
        self.assertGreater(i, 0, "van con doi du report moi quyet")
        khoi = s[i:i + 700]
        self.assertIn("statuses[m] = True", khoi)
        self.assertIn("khong dung cho", khoi)

    def test_doc_mot_phat_khong_lap_vong(self):
        s = _src()
        i = s.find("_thieu = [m for m in members if m not in statuses]")
        truoc = s[max(0, i - 900):i]
        self.assertNotIn("while True:", truoc, "van con vong cho truoc khi doc")


class TestMemberCoLoiRa(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("CHO leader danh xong team dungeon")
        self.assertGreater(i, 0)
        self.khoi = s[max(0, i - 1600):i + 200]

    def test_thoat_khi_dieu_phoi_ra_lenh_moi(self):
        self.assertIn('st.get("reform_gen", 0) != _gen0', self.khoi,
                      "member diec voi lenh dieu phoi")

    def test_thoat_khi_pha_PB_khong_he_bat(self):
        self.assertIn("not dang_pha_pho_ban(pidx)", self.khoi,
                      "leader khong vao PB thi member cho vinh vien")

    def test_ha_co_truoc_khi_thoat(self):
        """Thoat ma con om co PB thi `go_to_town` cua no van bail (L1b)."""
        self.assertGreaterEqual(self.khoi.count("_clear_o5_client_flags(c)"), 2)

    def test_van_giu_nhanh_dong_doi_ROT(self):
        s = _src()
        self.assertIn("dong doi ROT trong team dungeon -> THOAT PB", s)


class TestKhongConBarrierNaoKhac(unittest.TestCase):
    def test_o5_khong_con_vong_cho_vo_han(self):
        """Neo chung cho ca hai nhanh o5: moi `while True` trong ham nay phai co loi ra cap party
        (reform_gen / pha PB / reconnecting), khong chi `stopped` + `c.running`."""
        s = _src()
        i = s.find("def _run_auto_team_dungeons_if_needed")
        if i < 0:
            i = s.find("o5_done_by")
        self.assertGreater(i, 0)
        j = s.find("\ndef ", s.find("CHO leader danh xong team dungeon"))
        than = s[i:j if j > 0 else len(s)]
        for k, d in enumerate(than.splitlines()):
            if d.strip() != "while True:":
                continue
            sau = "\n".join(than.splitlines()[k:k + 40])
            self.assertTrue(
                ('reform_gen' in sau) or ('dang_pha_pho_ban' in sau) or ('reconnecting' in sau),
                "vong cho khong co loi ra cap party:\n" + sau[:400])


if __name__ == "__main__":
    unittest.main()
