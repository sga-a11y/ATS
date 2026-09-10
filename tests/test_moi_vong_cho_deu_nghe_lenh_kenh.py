"""LENH KENH phai nghe duoc o MOI VONG CHO, khong rieng keepalive.

Truoc day `st["kenh_dich"]` chi duoc doc o MOT cho - vong keepalive. Acc nao tut vao mot vong con
la DIEC vong do, ma do lai chinh la noi no o lau nhat:
  - leader: vong MOI party (`dang moi... joined=2/4`) chay lien tuc hang phut,
  - member: cac vong cho du party / cho reconnect / cho dungeon.

Ca that 07/09 party 1 (user: "t thay leader luon o 1 kenh con member o kenh khac" ->
"dm, tuc la no van deo nghe lenh, dieu phoi nhu lon"):

    20:39:21 [chihao] (member) DIEU PHOI chot kenh 45, minh dang o 5 -> tu chuyen
    20:39:21 [minh]   (member) DIEU PHOI chot kenh 45, minh dang o 6 -> tu chuyen
    20:42:33 [xGAx] (LEADER) chua moi 2 member vi chua xac nhan live dung map/kenh:
             ['38d0d2f8:lech kenh live 45!=6', '0c1dd3f8:lech kenh live 45!=6']

Hai member DA sang 45 dung lenh. Leader ket trong vong moi nen van o 6 - roi chinh no doi HO sang
kenh cua no, va ca party khong bao gio gom duoc.

Gio lenh nam trong `_nghe_lenh_kenh()` va duoc goi o MOI vong cho cap party. Test nay quet ca vong
`run_account` de vong moi them vao cung phai goi.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


def _than_run_account():
    d = _src().splitlines()
    i0 = next(i for i, x in enumerate(d) if x.startswith("def run_account("))
    i1 = next(i for i, x in enumerate(d) if i > i0 + 10 and x.startswith("def "))
    return d[i0:i1], i0


# Vong CHO CAP PARTY: acc dung im doi acc khac. Day la nhung cho no o lau nhat.
VONG_CHO = (
    'while joined_member_count(pidx) < st["n_members"]:',
    'while _dem_san_sang(pidx) < st["n_members"]:',
    'while not _dg_solo_bail and joined_member_count(pidx) < st["n_members"]:',
    "while joined_member_count(pidx) < expected - 1:",
    'while not st["invited"].is_set():',
    'while st["reconnecting"] and c.running and not _stopped():',
    "CHO VO HAN: du party moi sync kenh",
    "CHO VO HAN cho ca party xong dungeon",
)


class TestMoiVongChoDeuNgheLenh(unittest.TestCase):
    def test_cac_vong_cho_cap_party_deu_goi(self):
        d, _ = _than_run_account()
        thieu = []
        for moc in VONG_CHO:
            vi_tri = [i for i, x in enumerate(d) if moc in x]
            self.assertTrue(vi_tri, "khong tim thay vong: " + moc)
            for i in vi_tri:
                _than = chr(10).join(d[i:i + 45])   # co vong co chu thich dai truoc phan than
                if "_nghe_lenh_kenh()" not in _than and "_nhip_moi_party(" not in _than:
                    thieu.append(moc)
        self.assertEqual(thieu, [], "vong cho khong nghe lenh kenh:" + chr(10)
                         + chr(10).join(thieu))

    def test_ham_dat_o_dau_run_account(self):
        """Phai dinh nghia SOM - cac vong o dau ham cung can goi duoc."""
        d, _ = _than_run_account()
        i_def = max(i for i, x in enumerate(d)
                    if "def _nghe_lenh_kenh():" in x or "def _nhip_moi_party(" in x)
        i_vong = min(i for i, x in enumerate(d)
                     if any(m in x for m in VONG_CHO))
        self.assertLess(i_def, i_vong, "dinh nghia sau vong dau tien -> vong do khong goi duoc")


class TestNoiDungLenh(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _nghe_lenh_kenh():")
        self.assertGreater(i, 0)
        self.than = s[i:i + 3200]

    def test_doc_kenh_dich_cua_dieu_phoi(self):
        self.assertIn('st.get("kenh_dich")', self.than)

    def test_KHONG_doi_kenh_giua_tran(self):
        """Ba moc an toan da rut vao `_kenh_doi_duoc_ngay` - dung chung voi duong dieu phoi tu
        gui (09/09). Neo theo ham chung chu khong theo mot ban sao."""
        self.assertIn("_kenh_doi_duoc_ngay(c, st)", self.than)

    def test_dung_kenh_roi_thi_khong_gui_lai(self):
        self.assertIn('int(getattr(c, "current_channel", 0) or 0) == int(_kd)', self.than)

    def test_loi_khong_lam_dut_vong_goi(self):
        self.assertIn("except Exception", self.than)

    def test_KHONG_bao_cao_gi_len(self):
        """Dieu phoi doc thang `_chan_switch_result` o nhip sau - khong acc nao bao ket qua."""
        for cam in ('st["', "bao_", "report"):
            self.assertNotIn(cam + "kenh", self.than.replace("kenh_dich", ""), cam)


if __name__ == "__main__":
    unittest.main()
