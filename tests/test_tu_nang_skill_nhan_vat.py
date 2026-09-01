"""Tu nang skill NHAN VAT (`C:028-001`). Xem KNOWLEDGE muc 7q.

User chot 01/09: bang rule giong tinh nang Point (chon skill + cap muon dat, xu ly TU TREN XUONG,
co o "diem de danh"), chay MOT LAN luc login trong viec vat.

Va: "hoc skill moi thi ton nhieu diem, nang skill thi mat 1 diem, m can biet duoc hoc skill mat
bao nhieu diem" -> gia lay tu `skills_data.json`:
    cap 0 -> 1 : `learnPt`  (GAP DOI neu skill KHAC HE nhan vat)
    cac cap sau: `lvUpPt` moi cap (hau het = 1)

BA BAY da neo lai o day:
  1. opcode la `0x1c` (28), KHONG phai `0x08`.
  2. gui CAP DICH, KHONG phai so cap cong them (nguoc voi `C:008-001` tang diem tiem nang).
  3. mot goi mang NHIEU skill, khong co truong dem o dau.
"""
from __future__ import annotations

import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import config                   # noqa: E402
from bot.client import GameClient        # noqa: E402


class _Bot:
    SKILL_TAB_028_005 = GameClient.SKILL_TAB_028_005
    skill_point_left = GameClient.skill_point_left
    skill_cap_hien_tai = GameClient.skill_cap_hien_tai
    _skill_co_the_nang = GameClient._skill_co_the_nang
    _tien_quyet = GameClient._tien_quyet
    _tien_quyet_da_du = GameClient._tien_quyet_da_du
    _chuoi_hoc_toi = GameClient._chuoi_hoc_toi
    nang_skill_char = GameClient.nang_skill_char
    _ten_skill = GameClient._ten_skill
    he_nhan_vat = GameClient.he_nhan_vat
    ATTR_ELEMENT = GameClient.ATTR_ELEMENT

    def __init__(self, diem=100, he=2, lv=99, da_hoc=None):
        self._label = "t"
        self.char_attrs = {}
        self.char_element = he
        self.char_skill_point = diem
        self.char_skill_lv = dict(da_hoc or {})
        self.char_level = lv
        self.goi = []

    def send(self, op, payload):
        self.goi.append((op, payload))

    @property
    def goi_skill(self):
        """[(id, cap)] doc lai tu goi da gui."""
        assert len(self.goi) == 1 and self.goi[0][0] == 0x1C
        b = self.goi[0][1]
        assert b[:2] == b"\x01\x00"
        b = b[2:]
        return [(int.from_bytes(b[i:i + 2], "little"), b[i + 2]) for i in range(0, len(b), 3)]


# Lay tu skills_data.json that:
#   11010 Toan Tri Lieu Thuat: he 2 (Thuy), learnPt 9, lvUpPt 1, maxLv 10, pre 11007
#   12014 Lieu Nguyen Hoa    : he 3 (Hoa), learnPt 16, lvUpPt 1, maxLv 10, pre 12011
TRI_LIEU, PRE_TRI_LIEU = 11010, 11007
LIEU_NGUYEN, PRE_LIEU_NGUYEN = 12014, 12011


class TestDuLieuSkillDayDu(unittest.TestCase):
    def test_skills_data_co_du_truong_moi(self):
        info = config.SKILL_INFO[TRI_LIEU]
        for k in ("learnPt", "lvUpPt", "maxLv", "needLv", "element", "pre", "tree"):
            self.assertIn(k, info, "skills_data.json thieu '%s' -> chay lai crack_skills.py" % k)

    def test_gia_hoc_khac_han_gia_nang(self):
        """Dung cai user nhan manh: hoc moi ton nhieu, nang cap ton 1."""
        info = config.SKILL_INFO[TRI_LIEU]
        self.assertEqual(info["learnPt"], 9)
        self.assertEqual(info["lvUpPt"], 1)


class TestTinhGia(unittest.TestCase):
    def test_hoc_moi_CUNG_HE(self):
        b = _Bot(he=2, da_hoc={PRE_TRI_LIEU: 1})
        (gia, cap), _ = b._skill_co_the_nang(TRI_LIEU, 1)
        self.assertEqual((gia, cap), (9, 1))

    def test_hoc_moi_KHAC_HE_thi_GAP_DOI(self):
        b = _Bot(he=1, da_hoc={PRE_TRI_LIEU: 1})       # nhan vat he Dia, skill he Thuy
        (gia, _c), _ = b._skill_co_the_nang(TRI_LIEU, 1)
        self.assertEqual(gia, 18)

    def test_hoc_moi_ROI_NANG_luon_len_cap_3(self):
        """9 diem hoc + 2 cap x 1 diem = 11."""
        b = _Bot(he=2, da_hoc={PRE_TRI_LIEU: 1})
        (gia, cap), _ = b._skill_co_the_nang(TRI_LIEU, 3)
        self.assertEqual((gia, cap), (11, 3))

    def test_DA_HOC_roi_thi_chi_ton_lvUpPt(self):
        b = _Bot(he=2, da_hoc={TRI_LIEU: 4})
        (gia, cap), _ = b._skill_co_the_nang(TRI_LIEU, 7)
        self.assertEqual((gia, cap), (3, 7), "da hoc roi ma con tinh tien hoc lan dau")

    def test_vuot_maxLv_thi_CAT_ve_tran(self):
        b = _Bot(he=2, da_hoc={TRI_LIEU: 9})
        (gia, cap), _ = b._skill_co_the_nang(TRI_LIEU, 99)
        self.assertEqual((gia, cap), (1, 10))

    def test_da_dat_cap_thi_bo_qua(self):
        b = _Bot(he=2, da_hoc={TRI_LIEU: 10})
        ket, ly_do = b._skill_co_the_nang(TRI_LIEU, 10)
        self.assertIsNone(ket)
        self.assertIn("da dat cap", ly_do)


class TestRangBuoc(unittest.TestCase):
    def test_chua_hoc_SKILL_TIEN_QUYET_thi_khong_nang(self):
        b = _Bot(he=2)                                  # chua hoc 11007
        ket, ly_do = b._skill_co_the_nang(TRI_LIEU, 1)
        self.assertIsNone(ket)
        self.assertIn("tien quyet", ly_do)

    def test_da_hoc_tien_quyet_thi_qua(self):
        b = _Bot(he=2, da_hoc={PRE_TRI_LIEU: 1})
        ket, _ = b._skill_co_the_nang(TRI_LIEU, 1)
        self.assertIsNotNone(ket)

    def test_tien_quyet_KHONG_can_hoc_het(self):
        """Client: chi can MOT skill tien quyet da hoc la duoc (checkCount == failCount moi chan)."""
        info = config.SKILL_INFO[TRI_LIEU]
        self.assertTrue(info.get("pre"))
        b = _Bot(he=2, da_hoc={PRE_TRI_LIEU: 1})
        self.assertIsNotNone(b._skill_co_the_nang(TRI_LIEU, 1)[0])

    def test_thieu_LEVEL_nhan_vat_thi_khong_nang(self):
        sid = next((s for s, v in config.SKILL_INFO.items()
                    if v.get("tree") and (v.get("needLv") or 0) > 5), None)
        self.assertIsNotNone(sid)
        can = config.SKILL_INFO[sid]["needLv"]
        b = _Bot(lv=can - 1, da_hoc={sid: 1})
        ket, ly_do = b._skill_co_the_nang(sid, 2)
        self.assertIsNone(ket)
        self.assertIn("can level", ly_do)

    def test_skill_KHONG_RO_TAB_thi_KHONG_dung_toi(self):
        """Skill pet / dac ky / 2 chuyen deu roi vao day - gui 028-001 cho chung la sai gói."""
        sid = next(s for s, v in config.SKILL_INFO.items() if not v.get("tree"))
        ket, ly_do = _Bot()._skill_co_the_nang(sid, 1)
        self.assertIsNone(ket)
        self.assertIn("tab", ly_do)

    def test_tab_2_CHUYEN_bi_chan(self):
        self.assertIn("Turn2", GameClient.SKILL_TAB_028_005)


# Chuoi that trong cay he Thuy: 11001 -> 11002 (Bang Tuong) -> 11004 (Thanh Luu) -> 11006 (Hoi Ma)
AAA, BBB, CCC, DDD = 11006, 11004, 11002, 11001


class TestLanTheoCaySkill(unittest.TestCase):
    """User chot 01/09: "neu de AAA cap 5 ma AAA chua duoc hoc, can hoc BBB truoc, de hoc BBB thi
    can hoc CCC truoc thi m cu lan theo skill tree de tien dan den skill mong muon"."""

    def test_du_lieu_dung_chuoi_3_tang(self):
        self.assertEqual(config.SKILL_INFO[AAA]["pre"], BBB)
        self.assertEqual(config.SKILL_INFO[BBB]["pre"], CCC)
        self.assertEqual(config.SKILL_INFO[CCC]["pre"], DDD)

    def test_lan_ra_dung_thu_tu_tu_GOC(self):
        b = _Bot(da_hoc={DDD: 1})
        self.assertEqual(b._chuoi_hoc_toi(AAA), [CCC, BBB])

    def test_da_hoc_giua_chuoi_thi_chi_lan_phan_con_thieu(self):
        b = _Bot(da_hoc={CCC: 3})
        self.assertEqual(b._chuoi_hoc_toi(AAA), [BBB])

    def test_du_tien_quyet_thi_chuoi_RONG(self):
        b = _Bot(da_hoc={BBB: 1})
        self.assertEqual(b._chuoi_hoc_toi(AAA), [])

    def test_HOC_CA_CHUOI_roi_moi_nang_skill_dich(self):
        b = _Bot(diem=100, da_hoc={DDD: 1})
        b.nang_skill_char([(AAA, 3)])
        self.assertEqual(b.goi_skill, [(CCC, 1), (BBB, 1), (AAA, 3)],
                         "phai hoc CCC -> BBB roi moi toi AAA, trong CUNG mot goi")

    def test_mat_xich_chi_hoc_CAP_1(self):
        """Mat xich chi can cap 1 de mo duong; diem con lai danh cho skill DICH."""
        b = _Bot(diem=100, da_hoc={DDD: 1})
        b.nang_skill_char([(AAA, 5)])
        self.assertEqual([cap for _sid, cap in b.goi_skill[:-1]], [1, 1])
        self.assertEqual(b.goi_skill[-1], (AAA, 5))

    def test_thieu_diem_giua_chuoi_thi_BAO_ro(self):
        b = _Bot(diem=2, da_hoc={DDD: 1})
        da, ly_do = b.nang_skill_char([(AAA, 5)])
        self.assertEqual(da, [])
        self.assertIn("dang hoc dan", ly_do)
        self.assertIn("thieu diem", ly_do)

    def test_khong_lan_duoc_thi_bao_ro(self):
        """Goc cay chua hoc va chinh goc cung co tien quyet khong lan noi."""
        b = _Bot(diem=100)                      # chua hoc gi ca
        duong = b._chuoi_hoc_toi(AAA)
        self.assertTrue(duong is None or DDD in duong)


class TestHeNhanVat(unittest.TestCase):
    """Dialog phai mo dung tab HE cua char; gia hoc skill khac he cung phu thuoc cai nay."""

    @staticmethod
    def _c(el=None, attrs=None):
        c = GameClient.__new__(GameClient)
        c.char_element = el
        c.char_attrs = dict(attrs or {})
        return c

    def test_lay_tu_char_attrs_24_khi_CHUA_co_S008_013(self):
        """`S:008-013` server KHONG gui san luc login, con `char_attrs[24]` (EAttribute.Element)
        thi co ngay -> khong co fallback nay la dialog khong biet mo tab nao."""
        self.assertEqual(self._c(el=None, attrs={24: 3}).he_nhan_vat(), 3)

    def test_S008_013_duoc_uu_tien(self):
        self.assertEqual(self._c(el=2, attrs={24: 3}).he_nhan_vat(), 2)

    def test_khong_biet_thi_tra_None(self):
        self.assertIsNone(self._c().he_nhan_vat())

    def test_gia_khac_he_tinh_theo_he_suy_duoc(self):
        """He chi nam o char_attrs -> van phai nhan doi dung."""
        b = _Bot(he=None, da_hoc={PRE_TRI_LIEU: 1})
        b.char_attrs = {GameClient.ATTR_ELEMENT: 1}      # char he Dia, skill he Thuy
        (gia, _c), _ = b._skill_co_the_nang(TRI_LIEU, 1)
        self.assertEqual(gia, 18)


class TestDocDiemSkillLucLogin(unittest.TestCase):
    """"Diem skill: ?" tren dialog = bot chua doc duoc diem.

    `S:008-013` mang diem NHUNG server khong gui san luc login. Diem con nam ngay trong goi
    `0x05 sub03` o offset +26 (canh AttrPoint +28) - xem KNOWLEDGE "Bo cuc 0x05 sub03".
    """

    @staticmethod
    def _goi_login(element=2, diem_skill=41, dai=80):
        """Goi `0x05 sub03` that (bo cuc trong KNOWLEDGE "Bo cuc 0x05 sub03")."""
        import struct as _s
        body = bytearray(dai)
        body[0:2] = b"\x03\x00"
        body[2] = element
        _s.pack_into("<I", body, 3, 500)          # hp
        _s.pack_into("<H", body, 7, 200)          # sp
        _s.pack_into("<H", body, 26, diem_skill)  # SkillPoint
        _s.pack_into("<I", body, 39, 500)         # hp_max
        _s.pack_into("<H", body, 43, 200)         # sp_max
        return b"\xc0\x91\x00\x00\x00\x00\x05" + bytes(body)

    @staticmethod
    def _client():
        c = GameClient.__new__(GameClient)
        c._label = "t"
        c.char_element = None
        c.char_skill_point = None
        c.char_attrs = {}
        c.state = type("S", (), {"char": type("U", (), {"hp": 0, "hp_max": 0,
                                                        "sp": 0, "sp_max": 0})()})()
        return c

    def test_doc_duoc_HE_va_DIEM_SKILL_tu_goi_login(self):
        c = self._client()
        c._parse_char_login_int(self._goi_login(element=2, diem_skill=41))
        self.assertEqual((c.char_element, c.char_skill_point), (2, 41))

    def test_KHONG_bi_chan_boi_rao_do_dai_98(self):
        """He (+2) va diem skill (+26) nam rat som; rao `len(body) < 98` la de chan phan TRANG BI
        o cuoi goi - de sau rao do thi goi ngan la mat ca hai (loi that: dialog khong focus dung
        tab he, va hien "Diem skill: ?")."""
        c = self._client()
        c._parse_char_login_int(self._goi_login(dai=60))     # ngan hon 98
        self.assertEqual(c.char_element, 2)
        self.assertEqual(c.char_skill_point, 41)

    def test_he_LA_thi_khong_nhan(self):
        c = self._client()
        c._parse_char_login_int(self._goi_login(element=9))
        self.assertIsNone(c.char_element)

    def test_uu_tien_S008_013_hon_char_attrs(self):
        b = _Bot(diem=7)
        b.char_attrs = {37: 99}
        self.assertEqual(b.skill_point_left(), 7)

    def test_char_attrs_37_la_du_phong(self):
        b = _Bot()
        b.char_skill_point = None
        b.char_attrs = {37: 12}
        self.assertEqual(b.skill_point_left(), 12)

    def test_khong_biet_thi_None_chu_khong_doan_0(self):
        """Tra 0 la bot tuong het diem -> khong nang gi ma cung khong bao loi."""
        b = _Bot()
        b.char_skill_point = None
        b.char_attrs = {}
        self.assertIsNone(b.skill_point_left())


class TestTabGiongGame(unittest.TestCase):
    """User chot 01/09: "cac he doi thanh dia thuy hoa phong tam cho giong game",
    "1 chuyen doi thanh Chuyen sinh cho giong game"."""

    def setUp(self):
        import io as _io
        with _io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            self.gui = fh.read()

    def test_du_5_he_va_ten_giong_game(self):
        i = self.gui.find("    TABS = [")
        khoi = self.gui[i:i + 400]
        for ten in ('"Địa"', '"Thủy"', '"Hỏa"', '"Phong"', '"Tâm"'):
            self.assertIn(ten, khoi)

    def test_o_cap_va_nut_TU_BAT_TAT_theo_skill_chon(self):
        """User chot 01/09: chua chon skill / skill da max -> hai o do XAM; chon skill chua max ->
        enable va o so nhay ve CAP HIEN TAI + 1."""
        i = self.gui.find("def _doi_skill_chon(")
        self.assertGreater(i, 0, "khong co ham cap nhat trang thai -> nut luon bam duoc")
        khoi = self.gui[i:i + 900]
        self.assertIn("cap < max_lv", khoi, "khong xet skill da max")
        self.assertIn('"normal" if _bat else "disabled"', khoi)
        self.assertIn("self.var_cap_tay.set(str(cap + 1))", khoi)

    def test_bat_su_kien_doi_skill_VA_doi_tab(self):
        """Doi tab cung phai cap nhat: moi tab co lua chon rieng."""
        self.assertIn('_tv.bind("<<TreeviewSelect>>", self._doi_skill_chon', self.gui)
        self.assertIn('self.nb.bind("<<NotebookTabChanged>>", self._doi_skill_chon', self.gui)

    def test_luc_MOI_MO_dialog_da_o_trang_thai_xam(self):
        i = self.gui.find("def _ve_cay(")
        khoi = self.gui[i:i + 2000]
        self.assertIn("self._doi_skill_chon()", khoi)

    def test_bang_auto_toi_da_5_dong_roi_CUON(self):
        """User chot 01/09: "t add nhieu dong auto qua lam cai bang no tran luon, m de toi da 5
        cai, nhieu hon thi thanh bang scroll"."""
        self.assertIn("SO_DONG_HIEN = 5", self.gui)
        i = self.gui.find("self._rules_canvas = tk.Canvas(")
        self.assertGreater(i, 0, "khong co vung cuon -> bang tran ra ngoai dialog")
        self.assertIn("height=self.CAO_DONG * self.SO_DONG_HIEN", self.gui[i:i + 200])

    def test_thanh_cuon_CHI_hien_khi_that_su_tran(self):
        i = self.gui.find("_can = len(self.rules) > self.SO_DONG_HIEN")
        self.assertGreater(i, 0)
        khoi = self.gui[i:i + 320]
        self.assertIn("pack_forget()", khoi)

    def test_them_va_XOA_dong_deu_tinh_lai_vung_cuon(self):
        i = self.gui.find("class SkillDialog")
        khoi = self.gui[i:self.gui.find(chr(10) + "class ", i + 10)]
        self.assertGreaterEqual(khoi.count("self.after(10, self._rules_fit)"), 2)

    def test_dong_DA_DAT_hien_Done_mau_xanh(self):
        """User chot 01/09: "cai dong nao da dat thi m them chu Done mau xanh ngay ben phai"."""
        i = self.gui.find("class SkillDialog")
        khoi = self.gui[i:self.gui.find(chr(10) + "class ", i + 10)]
        self.assertIn('tk.Label(row, text="", fg="#1a7f37")', khoi)
        self.assertIn('text="Done" if xong else ""', khoi)

    def test_Done_tinh_lai_khi_doi_skill_hoac_cap(self):
        i = self.gui.find("class SkillDialog")
        khoi = self.gui[i:self.gui.find(chr(10) + "class ", i + 10)]
        self.assertIn('var.trace_add("write", _kiem_done)', khoi)
        self.assertIn('var_cap.trace_add("write", _kiem_done)', khoi)

    def test_Done_tinh_lai_sau_khi_doc_lai_so(self):
        i = self.gui.find("class SkillDialog")
        khoi = self.gui[i:self.gui.find(chr(10) + "class ", i + 10)]
        self.assertIn("self._cap_nhat_done_tat_ca()", khoi)

    def test_lan_chuot_KHONG_doi_gia_tri_combobox_spinbox(self):
        """User chot 01/09: "chi chuot vao day va cuon chuot thi no doi skill, lam t bi doi nham,
        m bo cai do di, tuong tu ben point cung the"."""
        self.assertIn("def _chan_cuon_doi_gia_tri(", self.gui)
        i = self.gui.find("def _chan_cuon_doi_gia_tri(")
        khoi = self.gui[i:i + 1400]
        self.assertIn('return "break"', khoi, "khong chan thi widget van xu ly tiep")
        for _ev in ('"<MouseWheel>"', '"<Button-4>"', '"<Button-5>"'):
            self.assertIn(_ev, khoi)

    def test_ap_cho_CA_HAI_dialog(self):
        for ten_class in ("class PointDialog", "class SkillDialog"):
            i = self.gui.find(ten_class)
            khoi = self.gui[i:self.gui.find(chr(10) + "class ", i + 10)]
            self.assertIn("_chan_cuon_doi_gia_tri(", khoi, ten_class)

    def test_trong_bang_skill_van_CUON_BANG_duoc(self):
        """Chan thang thi lan chuot trong vung bang khong cuon duoc nua - phai chuyen tiep."""
        i = self.gui.find("class SkillDialog")
        khoi = self.gui[i:self.gui.find(chr(10) + "class ", i + 10)]
        self.assertIn("self._rules_canvas.yview_scroll(-1 if d > 0 else 1", khoi)

    def test_ben_POINT_cung_co_Done(self):
        """User chot 01/09: "ben point cung them text Done tuong tu"."""
        i = self.gui.find("class PointDialog")
        khoi = self.gui[i:self.gui.find(chr(10) + "class ", i + 10)]
        self.assertIn('fg="#1a7f37"', khoi)
        self.assertIn("def _cap_nhat_done(self, rec):", khoi)
        self.assertIn("goc >= dich", khoi, "Point chot theo diem GOC, khong phai TONG")

    def test_BO_tab_Quang_Am(self):
        """User chot 01/09: "tab Quang am cung bo vi game chua mo"."""
        i = self.gui.find("    TABS = [")
        khoi = self.gui[i:i + 400]
        self.assertNotIn("LightDark", khoi)
        self.assertNotIn("Quang/Ám", khoi)

    def test_tab_TAM_chi_hien_skill_DA_HOC(self):
        """Tab Tam co 104 skill sinh hoat, acc chi dung vai cai -> hien het thi khong tim noi."""
        self.assertIn('TAB_CHI_HIEN_DA_HOC = ("Mind",)', self.gui)
        i = self.gui.find("if tab in self.TAB_CHI_HIEN_DA_HOC:")
        self.assertGreater(i, 0)
        self.assertIn("self.cap.get(sid, 0) > 0", self.gui[i:i + 200])

    def test_bang_auto_dung_TEN_TIENG_VIET(self):
        """Truoc day combobox hien "Toan Tri Lieu Thuat — Water"."""
        i = self.gui.find("nhan = [\"%s — %s\"")
        self.assertGreater(i, 0)
        self.assertIn("self.TEN_TAB.get(v.get(\"tree\")", self.gui[i:i + 200])

    def test_bang_auto_LOC_theo_tab_dang_hien(self):
        """Bo Quang/Am + bo skill Tam chua hoc; rule DA LUU thi van giu."""
        i = self.gui.find("def _duoc_chon(_sid, _v):")
        self.assertGreater(i, 0)
        khoi = self.gui[i:i + 420]
        self.assertIn("_t not in self.TEN_TAB", khoi)
        self.assertIn("self.cap.get(_sid, 0) <= 0", khoi)
        self.assertIn("return _sid == sid", khoi)

    def test_doc_so_TRUOC_khi_dung_bang_rule(self):
        """`self.cap` phai co truoc `_nap_rules()`, khong thi loc skill Tam se bo sach."""
        i = self.gui.find("class SkillDialog")
        khoi = self.gui[i:self.gui.find("\nclass ", i + 10)]
        self.assertLess(khoi.find("self._nap()" + chr(10)), khoi.find("self._nap_rules()"))

    def test_doi_1_chuyen_thanh_Chuyen_sinh(self):
        self.assertIn('("Turn1", "Chuyển sinh"', self.gui)
        self.assertNotIn('"1 chuyển"', self.gui)

    def test_tab_TAM_suy_tu_element_5(self):
        """Client dien tab Tam DONG luc chay -> khong co danh sach tinh; skill Tam deu element=5."""
        tam = [s for s, v in config.SKILL_INFO.items() if v.get("tree") == "Mind"]
        self.assertGreater(len(tam), 50)
        self.assertTrue(all(config.SKILL_INFO[s].get("element") == 5 for s in tam))

    def test_skill_da_co_tab_KHONG_bi_gan_de_sang_Tam(self):
        """"Trieu Goi" co element 5 nhung nam trong cay he -> phai giu tab cu."""
        trung = [s for s, v in config.SKILL_INFO.items()
                 if v.get("element") == 5 and v.get("tree") not in (None, "Mind")]
        self.assertTrue(trung, "khong con ca trung -> bai test nay het y nghia, xem lai du lieu")


class TestCacheXemLucAccTat(unittest.TestCase):
    """User chot 01/09: "can co cache de xem skill luc off, ko hoc duoc thoi nhung co the set up
    tu dong tang (giong ben point)"."""

    def setUp(self):
        import io as _io
        with _io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.rpd = _io.StringIO(fh.read()).read()

    def test_acc_chay_thi_GHI_cache(self):
        i = self.rpd.find("def skill_char_info(")
        than = self.rpd[i:self.rpd.find("\ndef ", i + 10)]
        self.assertIn("save_skill_char_cache(username, out)", than)

    def test_acc_tat_thi_DOC_cache_va_danh_dau(self):
        i = self.rpd.find("def skill_char_info(")
        than = self.rpd[i:self.rpd.find("\ndef ", i + 10)]
        self.assertIn("load_skill_char_cache(username)", than)
        self.assertIn("cache=True", than)

    def test_dialog_bao_ro_la_so_CU(self):
        import io as _io
        with _io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            gui = fh.read()
        i = gui.find("class SkillDialog")
        khoi = gui[i:gui.find("\nclass ", i + 10)]
        self.assertIn("acc đang TẮT", khoi)

    def test_nang_TAY_khi_acc_tat_thi_bao_loi_chu_khong_im(self):
        i = self.rpd.find("def nang_skill_ngay(")
        than = self.rpd[i:self.rpd.find("\ndef ", i + 10)]
        self.assertIn('return False, "acc chưa chạy"', than)


class TestGuiGoi(unittest.TestCase):
    def test_gui_dung_opcode_0x1c(self):
        b = _Bot(da_hoc={TRI_LIEU: 1})
        b.nang_skill_char([(TRI_LIEU, 3)])
        self.assertEqual(b.goi[0][0], 0x1C, "sai opcode -> 0x08 chi la XIN LAI du lieu")

    def test_gui_CAP_DICH_khong_phai_so_cap_cong_them(self):
        b = _Bot(da_hoc={TRI_LIEU: 4})
        b.nang_skill_char([(TRI_LIEU, 7)])
        self.assertEqual(b.goi_skill, [(TRI_LIEU, 7)], "gui 3 (so cap them) la SAI")

    def test_MOT_goi_mang_NHIEU_skill(self):
        b = _Bot(diem=100, da_hoc={TRI_LIEU: 1, LIEU_NGUYEN: 1})
        b.nang_skill_char([(TRI_LIEU, 3), (LIEU_NGUYEN, 2)])
        self.assertEqual(len(b.goi), 1, "moi skill mot goi -> khong giong client")
        self.assertEqual(b.goi_skill, [(TRI_LIEU, 3), (LIEU_NGUYEN, 2)])

    def test_than_goi_KHONG_co_truong_dem(self):
        b = _Bot(da_hoc={TRI_LIEU: 1})
        b.nang_skill_char([(TRI_LIEU, 2)])
        self.assertEqual(b.goi[0][1], b"\x01\x00" + struct.pack("<HB", TRI_LIEU, 2))

    def test_khong_co_gi_de_nang_thi_KHONG_gui_goi_rong(self):
        b = _Bot(da_hoc={TRI_LIEU: 10})
        b.nang_skill_char([(TRI_LIEU, 10)])
        self.assertEqual(b.goi, [], "client chan goi rong (ShowCenterMessage 20571)")


class TestNganSachVaThuTu(unittest.TestCase):
    def test_DIEM_DE_DANH_duoc_giu_lai(self):
        b = _Bot(diem=10, da_hoc={TRI_LIEU: 1})
        b.nang_skill_char([(TRI_LIEU, 10)], de_danh=8)   # con tieu duoc 2 -> len cap 3
        self.assertEqual(b.goi_skill, [(TRI_LIEU, 3)])

    def test_khong_du_toi_cap_dich_thi_NANG_TOI_DA_trong_ngan_sach(self):
        """Rule "len cap 10" ton 9 diem; moi lan login chi duoc vai diem -> bo han la rule do
        KHONG BAO GIO chay. Phai di dan tung lan."""
        b = _Bot(diem=4, da_hoc={TRI_LIEU: 1})
        b.nang_skill_char([(TRI_LIEU, 10)])
        self.assertEqual(b.goi_skill, [(TRI_LIEU, 5)])

    def test_HOC_MOI_thi_khong_chia_nho_duoc(self):
        """Thieu `learnPt` thi khong hoc duoc phan nao ca."""
        b = _Bot(diem=5, da_hoc={PRE_TRI_LIEU: 1})       # can 9 diem de hoc
        da, _ = b.nang_skill_char([(TRI_LIEU, 3)])
        self.assertEqual((da, b.goi), ([], []))

    def test_de_danh_het_thi_khong_lam_gi(self):
        b = _Bot(diem=5, da_hoc={TRI_LIEU: 1})
        da, _ = b.nang_skill_char([(TRI_LIEU, 10)], de_danh=5)
        self.assertEqual((da, b.goi), ([], []))

    def test_xu_ly_TU_TREN_XUONG(self):
        """Rule tren an het diem thi rule duoi nhin."""
        b = _Bot(diem=3, da_hoc={TRI_LIEU: 1, LIEU_NGUYEN: 1})
        b.nang_skill_char([(TRI_LIEU, 4), (LIEU_NGUYEN, 9)])
        self.assertEqual(b.goi_skill, [(TRI_LIEU, 4)], "rule dau phai duoc uu tien")

    def test_rule_TREN_nang_duoc_toi_dau_lay_toi_do_roi_DUNG(self):
        b = _Bot(diem=2, da_hoc={TRI_LIEU: 1, LIEU_NGUYEN: 1})
        b.nang_skill_char([(TRI_LIEU, 9), (LIEU_NGUYEN, 3)])
        self.assertEqual(b.goi_skill, [(TRI_LIEU, 3)], "chua toi cap dich ma da xuong dong duoi")

    def test_rule_dau_THIEU_DIEM_thi_DUNG_khong_xuong_dong_duoi(self):
        """User chot 01/09: "phai hoan thanh duoc dong tren thi moi xuong dong duoi chu".
        Truoc day dong tren thieu diem thi bi bo qua va dong duoi (re hon) an mat diem - dung cai
        user bat duoc: "Hoa Tien de tan cuoi ma da nang len 2 roi, tu Hoi Sinh xuong duoi la chua
        hoc"."""
        b = _Bot(diem=3, da_hoc={PRE_TRI_LIEU: 1, LIEU_NGUYEN: 1})
        da, ly_do = b.nang_skill_char([(TRI_LIEU, 5), (LIEU_NGUYEN, 3)])
        self.assertEqual(da, [], "dong tren chua xong ma dong duoi da an diem")
        self.assertIn("DUNG", ly_do)

    def test_dong_tren_KHONG_BAO_GIO_DAT_thi_van_xuong_dong_duoi(self):
        """Chan vinh vien la sai: rule dat skill can level 90 ma acc level 30 se khoa het bang."""
        sid_cao = next(s for s, v in config.SKILL_INFO.items()
                       if v.get("tree") and (v.get("needLv") or 0) > 50)
        b = _Bot(diem=9, lv=5, da_hoc={sid_cao: 1, LIEU_NGUYEN: 1})
        b.nang_skill_char([(sid_cao, 5), (LIEU_NGUYEN, 3)])
        self.assertEqual(b.goi_skill, [(LIEU_NGUYEN, 3)])

    def test_dong_tren_DA_DAT_CAP_thi_xuong_dong_duoi(self):
        b = _Bot(diem=9, da_hoc={TRI_LIEU: 10, LIEU_NGUYEN: 1})
        b.nang_skill_char([(TRI_LIEU, 10), (LIEU_NGUYEN, 3)])
        self.assertEqual(b.goi_skill, [(LIEU_NGUYEN, 3)])

    def test_KHONG_hoc_mat_xich_roi_bo_do_de_dong_duoi_an_diem(self):
        """Log that 23:21:30: hoc 'Bang Kiem' 3 diem (mat xich cua Bang Phong) roi bo do, con
        'Hoa Tien' o DONG DUOI thi duoc nang."""
        b = _Bot(diem=6, da_hoc={DDD: 1, LIEU_NGUYEN: 1})
        b.nang_skill_char([(AAA, 5), (LIEU_NGUYEN, 3)])
        _ids = [sid for sid, _c in b.goi_skill]
        self.assertNotIn(LIEU_NGUYEN, _ids, "dong duoi van an diem trong khi dong tren chua xong")

    def test_chua_biet_diem_thi_KHONG_gui_bua(self):
        b = _Bot()
        b.char_skill_point = None
        da, ly_do = b.nang_skill_char([(TRI_LIEU, 3)])
        self.assertEqual((da, b.goi), ([], []))
        self.assertIn("chua doc duoc diem", ly_do)


class TestDocGoiS008_013(unittest.TestCase):
    """`S:008-013` = nguon DUY NHAT co cap tung skill + diem con lai."""

    @staticmethod
    def _c():
        c = GameClient.__new__(GameClient)
        c._label = "t"
        c.char_element = None
        c.char_skill_point = None
        c.char_skill_lv = {}
        c.state = type("S", (), {"skills_char": []})()
        return c

    @staticmethod
    def _goi(el, diem, skills):
        b = bytes([el]) + struct.pack("<HH", diem, len(skills))
        for sid, lv in skills:
            b += struct.pack("<HB", sid, lv)
        return b"\xc0\x91\x00\x00\x00\x00\x08\x0d\x00" + b

    def test_doc_dung_he_diem_va_cap(self):
        c = self._c()
        c._on_char_skill_data(self._goi(2, 37, [(TRI_LIEU, 4), (LIEU_NGUYEN, 1)]))
        self.assertEqual((c.char_element, c.char_skill_point), (2, 37))
        self.assertEqual(c.char_skill_lv, {TRI_LIEU: 4, LIEU_NGUYEN: 1})

    def test_count_la_2_BYTE(self):
        """Chu thich giao thuc ghi 技能數量(1) nhung Role.lua doc ReadUInt16 - code moi dung."""
        c = self._c()
        c._on_char_skill_data(self._goi(1, 5, [(TRI_LIEU, 2)]))
        self.assertEqual(c.char_skill_lv, {TRI_LIEU: 2})

    def test_goi_cut_thi_KHONG_ghi_de(self):
        c = self._c()
        c.char_skill_lv = {TRI_LIEU: 9}
        c._on_char_skill_data(b"\xc0\x91\x00\x00\x00\x00\x08\x0d\x00" + b"\x02\x05\x00\xff\x00")
        self.assertEqual(c.char_skill_lv, {TRI_LIEU: 9}, "goi cut ma van xoa du lieu dang dung")


if __name__ == "__main__":
    unittest.main()
