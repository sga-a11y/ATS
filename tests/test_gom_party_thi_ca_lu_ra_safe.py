"""Leader ho "lap lai party tai cho" -> CA PARTY ra safe, va phai KIEM CHUNG da ra that.

Su co party 11 (30/08 15:39-15:52):
    15:39:05 [luusau] (LEADER) pos=(1530, 620) map=23821          <- leader mot noi
    15:48:43 [luubay] (member) pos=(950, 1100) map=23821 combat=True
    15:48:43 [luutam] (member) pos=(940, 1080) map=23821 combat=True
    ... moi 21s: "(LEADER) moi 21s chua du party: ca party DA o map train 23821 va CUNG KENH
                  -> lap lai party tai cho, KHONG ve thanh"
    ... suot 13 phut, `da join=1 | roster server=1`: CHI luuchin vao doi - dua duy nhat luon
        combat=False. Ba dua con lai bi quai danh lien tuc, khong bao gio nhan duoc loi moi.

Nguyen nhan: `_ra_rally_gom_lai` chi di chuyen ACC GOI NO, ma no nam trong
`_party_tai_cho_xu_ly` - ham CHI LEADER chay. Member khong he biet co lenh gom -> dung nguyen o
diem quai. Moi luc dang trong tran = loi moi khong toi noi.

Hai thu bat buoc:
  1. Leader BAO ca party (`rally_gen`), member nghe thay thi chay ra safe.
  2. Leader KIEM CHUNG (toa do + het tran) truoc khi moi - khong tin la bao xong la ho da ra.
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestCoRallyGen(unittest.TestCase):
    def test_state_co_rally_gen(self):
        self.assertIn('"rally_gen": 0,', _src())

    def test_leader_BUMP_truoc_khi_moi(self):
        s = _src()
        i = s.find("def _party_tai_cho_xu_ly(")
        self.assertGreater(i, 0)
        than = re.sub(r"#.*", "", s[i:i + 7400])
        i_bump = than.find('st["rally_gen"] += 1')
        i_moi = than.find("_invite_party_participants(")
        self.assertGreater(i_bump, 0, "khong ho cho ca party -> member dung im o diem quai")
        self.assertGreater(i_moi, 0)
        self.assertLess(i_bump, i_moi, "bao SAU khi moi thi vo nghia")

    def test_member_nghe_o_CA_HAI_cho_bi_ket(self):
        """CA LU phai di, nen lenh phai toi duoc ca acc dang ket o vong startup.

        Party 28 (30/08 16:35-16:36): 3/4 member log "leader GOM LAI PARTY", rieng honagtba
        khong dong nao - no dang ket trong vong "CHO leader moi vao party" (startup), ma nhanh
        nghe lenh luc do chi nam o VONG CHINH (chay SAU khi da vao party).
        """
        s = _src()
        vt = [m.start() for m in re.finditer(r'st\["rally_gen"\] > rally_gen_handled', s)]
        self.assertGreaterEqual(len(vt), 2,
                                "chi mot cho nghe lenh -> acc ket o vong kia khong bao gio nghe")
        for i in vt:
            khoi = re.sub(r"#.*", "", s[i:i + 900])
            self.assertIn("_ra_rally_gom_lai(", khoi)
            self.assertIn('st["rally_done"][username] = rally_gen_handled', khoi,
                          "thi hanh xong ma khong bao cao thi leader van phai doan")
        # Vong chinh chay cho CA leader lan member -> phai co chot not is_leader
        khoi_chinh = re.sub(r"#.*", "", s[vt[-1] - 200:vt[-1] + 200])
        self.assertIn("not is_leader", khoi_chinh, "leader tu chay rally rieng, khong qua nhanh nay")

    def test_member_KHOI_TAO_gen_TRUOC_phan_startup(self):
        """Khoi tao muon (sau startup) = nuot mat lenh leader phat trong luc minh con startup."""
        s = _src()
        i_init = s.find('rally_gen_handled = st["rally_gen"]')
        i_cho_moi = s.find('while not st["invited"].is_set():')
        self.assertGreater(i_init, 0)
        self.assertGreater(i_cho_moi, 0)
        self.assertLess(i_init, i_cho_moi, "khoi tao SAU vong cho moi -> nuot lenh")
        # Chi dem cac dong KHOI TAO (thut 8 = than run_account), khong dem cac dong danh dau
        # da-xu-ly ben trong tung nhanh nghe lenh (thut sau hon).
        self.assertEqual(s.count('\n        rally_gen_handled = st["rally_gen"]'), 1,
                         "khoi tao lan hai = nuot lenh vua phat")


class TestBaoCaoDaThiHanh(unittest.TestCase):
    """"Ca lu deu phai di" chi kiem chung duoc khi tung dua BAO CAO da thi hanh."""

    def test_state_co_rally_done(self):
        self.assertIn('"rally_done": {},', _src())

    def test_leader_doi_du_bao_cao_cua_dung_vong_nay(self):
        s = _src()
        i = s.find("def _vi_sao_chua_san_sang(")
        than = re.sub(r"#.*", "", s[i:s.find("def _cho_ca_party_ve_rally(", i)])
        self.assertIn('st.get("rally_done", {}).get(ten_acc, -1)', than)
        self.assertIn("_da < int(gen)", than, "khong so voi gen hien tai = an bao cao cua vong CU")

    def test_gen_chup_MOT_LAN_truoc_vong_cho(self):
        """Doc st['rally_gen'] moi vong lap: chinh minh bump gen moi la tu doi mai khong xong."""
        s = _src()
        i = s.find("def _cho_ca_party_ve_rally(")
        than = re.sub(r"#.*", "", s[i:i + 1600])
        i_gen = than.find('_gen = int(st["rally_gen"])')
        i_while = than.find("while time.time() - t0 <")
        self.assertGreater(i_gen, 0)
        self.assertLess(i_gen, i_while, "chup gen BEN TRONG vong lap = moc chay theo, vo nghia")

    def test_log_timeout_NOI_RO_dua_nao_vuong_gi(self):
        s = _src()
        i = s.find("def _vi_sao_chua_san_sang(")
        than = s[i:s.find("def _party_tai_cho_xu_ly(", i)]
        for ly_do in ("chua thi hanh lenh gom", "con dang trong tran",
                      "cong nhan loi moi con DONG", "cach rally qua xa"):
            self.assertIn(ly_do, than, "thieu ly do: %s" % ly_do)


class TestKiemChungDaRaSafe(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("def _vi_sao_chua_san_sang(")
        self.assertGreater(i, 0, "khong co ham kiem chung da ra safe chua")
        j = s.find("def _party_tai_cho_xu_ly(", i)
        self.assertGreater(j, i)
        self.than = re.sub(r"#.*", "", s[i:j])
        self.src = s

    def test_kiem_TOA_DO(self):
        self.assertIn("RALLY_BAN_KINH", self.than)
        self.assertIn('getattr(cli, "pos", None)', self.than)

    def test_kiem_CA_trang_thai_TRAN(self):
        """Dung dung safe ma con dinh tran thi loi moi van khong toi noi."""
        self.assertIn("in_battle", self.than)

    def test_kiem_CA_CONG_NHAN_LOI_MOI(self):
        """Party 28 (30/08): hoangt303 bi da ra lien tuc (ma 14 - di chuyen QUA XA); moi lan vao
        lai la `party_invite_ready=False` (con lam viec vat dau phien) -> loi moi chi bi GIU
        ("Chua san sang vao party -> GIU loi moi"). No DA dung o rally nen leader moi luon -> 3/4
        -> "MAT PARTY giua chung" -> gom lai -> vong lai, ca party troi ra danh le.
        """
        self.assertIn('getattr(cli, "party_invite_ready", True)', self.than,
                      "dung o rally ma cong con dong thi moi bao nhieu cung vo ich")

    def test_KHONG_doi_cong_moi_o_LEADER(self):
        """`set_party_invite_ready(True)` chi goi cho member; bat leader phai mo cong = ket cung."""
        self.assertIn("la_leader", self.than)
        i = self.than.find('getattr(cli, "party_invite_ready", True)')
        self.assertIn("not la_leader", self.than[max(0, i - 120):i])
        self.assertIn("la_leader=_il", self.src, "khong truyen co leader vao thi chot tren vo dung")

    def test_chua_biet_toa_do_thi_XIN_LAI_tu_server(self):
        """Doan mo la sai ca hai chieu: doan 'chua ra' thi cho het 45s vo ich, doan 'da ra' thi
        moi party luc no con giua bay quai. Co san `0x0C 0100` de xin lai toa do."""
        i = self.than.find('p = getattr(cli, "pos", None)')
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 700]
        self.assertIn("refresh_server_position(", khoi, "khong xin lai toa do, chi ngoi doan")
        self.assertIn("xin lai van khong ro toa do", khoi, "xin roi van khong co thi phai coi la CHUA ra")

    def test_leader_CHO_truoc_khi_moi(self):
        i = self.src.find("def _party_tai_cho_xu_ly(")
        than = re.sub(r"#.*", "", self.src[i:i + 7400])
        i_cho = than.find("_cho_ca_party_ve_rally(")
        i_moi = than.find("_invite_party_participants(")
        self.assertGreater(i_cho, 0, "moi ngay sau khi bao = member con dang giua tran")
        self.assertLess(i_cho, i_moi)

    def test_HET_GIO_CHO_thi_VAN_MOI_khong_chan_cung(self):
        """"Chua xac nhan" KHONG dong nghia "chac chan chua ra". Tu choi moi = party KHONG BAO GIO
        lap duoc: log 30/08 23:30-23:50 co 65 lan chan o day (41 lan vi `rally_done=-1`), bucket
        23:40 dat 0 party 4/4 trong khi 64 lan "MAT PARTY giua chung"."""
        s = self.src
        i = s.find("van chua xac nhan du o diem tap ket")
        self.assertGreater(i, 0, "van con chan cung khi het gio cho")
        khoi = s[i:i + 400]
        self.assertIn("VAN MOI (khong chan)", khoi)
        self.assertIn("return True", khoi, "het gio ma tra False = chan mời")

    def test_BAO_CAO_da_ra_dat_trong_ham_ra_rally(self):
        """`rally_done` phai duoc ghi o MOI duong ra rally. Truoc day chi ghi o 2 nhanh NGHE LENH
        -> member ra rally bang duong khac (reform cua chinh no, sau viec vat) khong bao gio bao
        cao -> leader thay `rally_done=-1` -> cho het 45s -> khong moi."""
        s = self.src
        i = s.find("def _ra_rally_gom_lai(")
        than = s[i:s.find("\n        RALLY_BAN_KINH", i)]
        self.assertIn("def _bao_da_ra():", than)
        self.assertIn('st["rally_done"][username] = int(st["rally_gen"])', than)
        # phai goi o CA HAI cho tra True
        self.assertEqual(than.count("_bao_da_ra()"), 4, "thieu cho goi bao cao (dinh nghia + 3 goi)")

    def test_chua_ra_du_thi_KHONG_moi_va_KHONG_ve_thanh(self):
        i = self.src.find("def _party_tai_cho_xu_ly(")
        than = re.sub(r"#.*", "", self.src[i:i + 7400])
        i_cho = than.find("if is_leader and not _cho_ca_party_ve_rally(")
        self.assertGreater(i_cho, 0)
        khoi = than[i_cho:i_cho + 300]
        self.assertIn("return True", khoi, "tra False = roi xuong nhanh ve thanh, sai rule")

    def test_co_cap_thoi_gian_cho(self):
        """Cho vo han = mot acc chet/ket la ca party dung hinh."""
        self.assertIn("RALLY_CHO_CAP", self.src)


class TestDiRaRallyPhaiXacNhan(unittest.TestCase):
    """`navigate_to` bi tran chien xen ngang thi ve giua duong ma KHONG bao loi."""

    def setUp(self):
        s = _src()
        i = s.find("def _ra_rally_gom_lai(")
        self.assertGreater(i, 0)
        j = s.find("\n        RALLY_BAN_KINH", i)
        self.assertGreater(j, i)
        self.than = re.sub(r"#.*", "", s[i:j])
        self.src = s

    def test_BO_CHAY_chu_khong_vua_di_vua_danh(self):
        """Party HONG (dang gom lai) -> bo chay. Con duong "party VAN DU, chi di ra safe truoc khi
        giai tan de doi kenh" thi truyen `bo_chay=False` - xem tests/test_lenh_doi_kenh_tay.py."""
        self.assertIn("if bo_chay:", self.than)
        self.assertIn("c.flee_mode = True", self.than)
        self.assertIn("flee=bo_chay", self.than)
        self.assertIn('def _ra_rally_gom_lai(ly_do="", bo_chay=True):', self.than,
                      "mac dinh phai VAN la bo chay (duong gom party hong)")

    def test_DOC_LAI_toa_do_de_xac_nhan(self):
        self.assertIn("def _da_toi():", self.than)
        self.assertIn("RALLY_BAN_KINH", self.than)
        self.assertIn("refresh_server_position(", self.than, "pos rong thi phai xin lai")

    def test_THU_LAI_khi_chua_toi(self):
        self.assertIn("for _lan in range(1, 4):", self.than)

    def test_TUONG_o_rally_ma_dang_danh_thi_KHONG_tin_toa_do(self):
        """`c.pos` la so bot TU NHO (dead-reckoning) va no sai duoc; sai roi thi duong tat
        "da o rally roi" lam acc KHONG BAO GIO di, pos giu nguyen gia tri sai -> ket vinh vien.

        Log 30/08 23:33 party 3: laochin bao pos=(990,480) [dung rally], combat=True lien tuc,
        trong khi 3 member kia cung cho do combat=False suot -> thuc te no van dung o diem quai.

        NHUNG cach xu ly "khong tin toa do -> DI LAI" (ban dau) la sai va da bi bo (31/08): xem
        `test_o_safe_roi_thi_dung_di_lai.py`. Gio: dinh tran tai rally thi DANH XONG TAI CHO roi
        kiem lai toa do - khong bang qua vung quai them lan nao.
        """
        i = self.than.find("if _da_toi():")
        self.assertGreater(i, 0)
        khoi = self.than[i:i + 900]
        self.assertIn("c.in_combat(", khoi,
                      "duong tat 'da o rally' khong kiem tran -> tin toa do sai vinh vien")
        i_ret = khoi.find("return True")
        self.assertGreater(i_ret, khoi.find("c.in_combat("),
                           "phai kiem tran TRUOC khi ket luan da toi")

    def test_TRA_KET_QUA(self):
        self.assertIn("return True", self.than)
        self.assertIn("return False", self.than)

    def test_LOGIN_dung_chung_duong_nay(self):
        """Truoc day login goi `navigate_to` tran: khong flee, khong kiem lai."""
        i = self.src.find("MAP-TRAIN map=%s -> ve safe tap ket chung")
        self.assertGreater(i, 0)
        khoi = re.sub(r"#.*", "", self.src[i:i + 1200])
        self.assertIn('_ra_rally_gom_lai("login")', khoi)
        self.assertNotIn("c.navigate_to(*_jitter(rally))", khoi,
                         "van navigate_to tran -> vua di vua danh, khong xac nhan da toi")


if __name__ == "__main__":
    unittest.main()
