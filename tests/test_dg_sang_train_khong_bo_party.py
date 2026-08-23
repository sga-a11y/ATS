"""HET GIO DI GIOI -> phai chuyen sang TRAIN, KHONG duoc bo party.

BUG THAT (party 19, log 13:46-13:57):
  13:46:47 leader: "roster phong pho ban chi 1/4 member sau 8.0s -> THIEU nguoi, HUY danh"
           (dung rule "phai du pt moi danh PB")
  13:48-13:57 member ket "PB lv20: cho leader xu ly", watchdog ep dong bo 4 lan
  13:57:50 ">>> PARTY 19 DA THOAT HET vi: het gio Di Gioi hom nay; leader gone/bad -> THOAT theo"

Chuoi nhan qua:
  _run_auto_team_dungeons_if_needed() tra False (PB huy)
    -> _finish_digioi_train_after_dg() `return False`
    -> _dt["relogin_train"] KHONG duoc set
    -> reconnectable = False
    -> st["leader_gone"].set()
    -> member thay leader chet THAT -> thoat theo -> CA PARTY CHET.

Luat dung: PB/viec vat hong KHONG phai ly do giet party. DG het gio thi viec tiep theo LUON la
TRAIN. Chi GUI Stop moi duoc dung han.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")


def than_ham(ten):
    """Cat than mot ham long nhau theo thut le (den dong cung thut hoac it hon)."""
    m = re.search(r"^([ 	]*)def %s\(" % re.escape(ten), SRC, re.M)
    assert m, "khong thay ham %s" % ten
    thut = len(m.group(1))
    dong = SRC[m.start():].split("\n")
    ra = [dong[0]]
    for d in dong[1:]:
        if d.strip() and (len(d) - len(d.lstrip())) <= thut:
            break
        ra.append(d)
    return "\n".join(ra)


class TestBanGiaoDGSangTrain(unittest.TestCase):
    def setUp(self):
        self.than = than_ham("_finish_digioi_train_after_dg")

    def test_PB_hong_van_chuyen_sang_TRAIN(self):
        """Nhanh pho ban that bai PHAI set relogin_train, khong duoc `return False` tran."""
        i = self.than.index("_run_auto_team_dungeons_if_needed")
        sau = self.than[i:i + 1200]
        self.assertIn('_dt["relogin_train"] = True', sau,
                      "PB hong ma khong set relogin_train -> leader_gone -> ca party chet")

    def test_khong_con_return_False_tran_o_nhanh_PB(self):
        i = self.than.index("_run_auto_team_dungeons_if_needed")
        # doan tu do den `if do_daily` la nhanh xu ly PB
        j = self.than.index("if do_daily", i)
        # BO chu thich truoc khi kiem: doan comment co ke lai bug cu (trong do co chu
        # "return False") - kiem tra tho se bat nham chinh loi giai thich.
        nhanh = "\n".join(d for d in self.than[i:j].split("\n")
                          if not d.strip().startswith("#"))
        self.assertNotIn("return False", nhanh,
                         "van con return False o nhanh PB -> bug cu quay lai")

    def test_relogin_train_la_dieu_kien_de_supervisor_bat_lai(self):
        """Chot lai day chuyen: relogin_train -> reconnectable -> KHONG set leader_gone."""
        self.assertIn('_dt["relogin_train"]', SRC)
        m = re.search(r"reconnectable = \(not _stopped\(\)(.{0,300})", SRC, re.S)
        self.assertIsNotNone(m)
        self.assertIn('_dt["relogin_train"]', m.group(1),
                      "relogin_train khong con nam trong dieu kien reconnectable")

    def test_leader_gone_chi_set_khi_KHONG_reconnectable(self):
        m = re.search(r"if is_leader and not reconnectable.{0,200}", SRC, re.S)
        self.assertIsNotNone(m, "cau truc set leader_gone da doi - xem lai")
        self.assertIn('st["leader_gone"].set()', m.group(0))

    def test_nhanh_back_to_dg_van_giu_relogin_train(self):
        """Con gio DG -> quay lai DG: cung phai relogin, khong duoc coi la leader chet."""
        i = self.than.index("back_to_dg")
        self.assertIn('_dt["relogin_train"] = True', self.than[i:i + 600])


if __name__ == "__main__":
    unittest.main()
