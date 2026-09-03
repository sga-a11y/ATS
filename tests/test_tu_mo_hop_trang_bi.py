# -*- coding: utf-8 -*-
"""TU MO HOP/TUI TRANG BI -> phan giai hoac donate quan doan (user chot 03/09).

Luat user chot:
  - Mo toi da min(ca stack, so o trong).
  - CHI chay khi CO quan doan va da vao >24h (bo hoan toan nhanh ban shop).
  - Do phan giai duoc -> phan giai lay manh; khong phan giai duoc -> donate quan doan.
  - Duyet HAI LUOT: tui thuong truoc, tui tinh/cao sau (khong mo de quy).
  - CHI dung vao mon VUA ROI RA; do co san trong tui giu nguyen.

Crack client (03/09):
  - Mo hop = DUNG ITEM binh thuong; `specialAbility` 48 chi la chot kiem tra trong Logic_Item.lua
    (chan mo khi o trong < kindCount -> "您身上的物品欄空間不足哦!").
  - Donate TRANG BI: C:039-053 <存入武器> = 0x27 sub 0x35 + <<slot 1B>> (KHONG co truong tien).
    Donate NGUYEN LIEU: C:039-015 = 0x27 sub 0x0f + [tien i32] + <<slot>>.
  - Du 24h hay chua: client KHONG biet, khong co truong thoi gian gia nhap o dau ca. Server tra
    S:039-015 ma 32 = "加入軍團未滿24小時，無法捐獻" (TextData 21215).
"""
import io
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than(ten):
    s = _doc("bot", "client.py")
    i = s.find("def %s(" % ten)
    assert i > 0, ten
    j = s.find("\n    def ", i + 10)
    return s[i:j if j > 0 else i + 4000]


class TestDuLieuHop(unittest.TestCase):
    def test_bliss_bag_json_co_du_hop(self):
        with io.open(os.path.join(ROOT, "bliss_bag.json"), encoding="utf-8") as fh:
            d = json.load(fh)["boxes"]
        self.assertEqual(len(d), 14)
        ten = {v["name"] for v in d.values()}
        for x in ("Hộp Trang Bị Cấp 20", "Túi Thập Thường", "Túi Thảo Phạt", "Hộp Vũ Khí Sơ",
                  "Trang Bị Dũng Sĩ", "Túi Bộc Dương Cao"):
            self.assertIn(x, ten)

    def test_moi_hop_co_kindCount_va_items(self):
        with io.open(os.path.join(ROOT, "bliss_bag.json"), encoding="utf-8") as fh:
            d = json.load(fh)["boxes"]
        for k, v in d.items():
            self.assertGreaterEqual(v["kindCount"], 1, k)
            self.assertTrue(v["items"], k)
            self.assertIn(v["luot"], ("thuong", "tinh"), k)

    def test_4_tui_tinh_cao_deu_100_phan_tram_phan_giai(self):
        """Neu game doi bang thi luat 'tui tinh dang mo nhat' khong con dung."""
        with io.open(os.path.join(ROOT, "bliss_bag.json"), encoding="utf-8") as fh:
            d = json.load(fh)["boxes"]
        for tid in ("0xb53a", "0xb532", "0xb53f", "0xb546"):
            v = d[tid]
            self.assertTrue(all(i["fc"] > 0 for i in v["items"]),
                            "%s khong con 100%% phan giai duoc" % v["name"])


class TestDieuKienQuanDoan(unittest.TestCase):
    def test_khong_co_quan_doan_thi_KHONG_chay(self):
        t = _than("tu_mo_hop_trang_bi")
        self.assertIn("if self.has_legion is False:", t)
        self.assertIn('"khong co quan doan"', t)

    def test_chua_du_24h_thi_KHONG_chay(self):
        t = _than("tu_mo_hop_trang_bi")
        self.assertIn("if not self.co_the_donate_quan_doan():", t)

    def test_ma_32_hoan_12h(self):
        s = _doc("bot", "client.py")
        self.assertIn("LEGION_DONATE_RETRY = 12 * 3600", s)
        t = _than("_on_legion_msg")
        self.assertIn("if ma != 32:", t)
        self.assertIn("self.legion_donate_next = time.time() + self.LEGION_DONATE_RETRY", t)

    def test_co_bat_goi_S039_015_trong_dispatch(self):
        s = _doc("bot", "client.py")
        self.assertIn('if pkt[7:9] == b"\\x0f\\x00" and len(pkt) >= 10:', s)
        self.assertIn("self._on_legion_msg(pkt[9])", s)


class TestGoiDonateTrangBi(unittest.TestCase):
    """SUA 03/09: truoc do dung C:039-053 (0x27 sub 0x35) LA SAI.

    Goi do ten <存入武器> = "gui vu khi vao kho quan doan" (kho quan bi), khong phai quyen gop ->
    server BO QUA IM LANG, do van nam trong tui (log that 18:55: mo 21 hop, log "DONATE" 21 mon,
    ngay sau do "tui day (con 0 o)"). Client dung DUNG MOT nut "Dong gop" cho ca nguyen lieu lan
    trang bi: UIArmy chi mo UIBag voi MOT bo loc ArmyFilter, va trang bi CO qua duoc bo loc do.
    """

    def test_dung_CHUNG_goi_voi_nguyen_lieu(self):
        t = _than("donate_legion_equip")
        self.assertIn(r'self.send(0x27, b"\x0f\x00\x00\x00\x00\x00" + bytes(ds))', t)
        self.assertNotIn(r'b"\x35\x00"', t, "sub 0x35 la kho vu khi quan doan, KHONG phai donate")

    def test_nhieu_slot_mot_lenh(self):
        t = _than("donate_legion_equip")
        self.assertIn("bytes(ds)", t)


class TestLuatMo(unittest.TestCase):
    def test_mo_toi_da_min_stack_va_o_trong(self):
        t = _than("tu_mo_hop_trang_bi")
        self.assertIn("min(int(self.bag_slots[slot][1]), trong // can)", t)

    def test_dung_khi_thieu_o_trong(self):
        """Client chan mo khi o trong < kindCount -> bot gui la server tu choi IM LANG."""
        t = _than("tu_mo_hop_trang_bi")
        self.assertIn("if trong < can:", t)
        self.assertIn("tui day", t)

    def test_hai_luot_thuong_truoc_tinh_sau(self):
        t = _than("tu_mo_hop_trang_bi")
        self.assertIn('for luot in ("thuong", "tinh"):', t)

    def test_CHI_dung_vao_mon_vua_roi_ra(self):
        """Do co san trong tui phai giu nguyen: mon trong hop deu la trang bi thuong cua game,
        cung roi khi train / mua o lo / user de danh -> dung vao la mat do cua user."""
        t = _than("tu_mo_hop_trang_bi")
        self.assertIn("truoc = dict(self.bag_slots)", t)
        self.assertIn("moi = self._cho_tui_doi(truoc", t)
        self.assertIn("self._xu_ly_do_vua_mo(moi", t)
        # KHONG duoc quet ca tui theo danh sach item cua hop
        self.assertNotIn("for s, (t, c) in list(self.bag_slots.items()) if t in", t)


class TestXuLyDoRoiRa(unittest.TestCase):
    def test_fc_lon_hon_0_thi_phan_giai(self):
        t = _than("_xu_ly_do_vua_mo")
        self.assertIn('if int(r.get("fc") or 0) > 0:', t)
        self.assertIn("self.decompose_slot(s)", t)

    def test_con_lai_thi_donate(self):
        t = _than("_xu_ly_do_vua_mo")
        self.assertIn("self.donate_legion_equip(donate)", t)

    def test_KHONG_con_nhanh_ban_shop(self):
        """User bo hoan toan nhanh tu ban (03/09)."""
        t = _than("_xu_ly_do_vua_mo")
        for cam in ("sell_noi_dat", "sell_", "NOI_DAT_SELL_CITY"):
            self.assertNotIn(cam, t)


class TestGomNhieuSlotMotLenh(unittest.TestCase):
    """User chot 03/09: "gom luon di cho giong client that".

    UIArmy.OnClick_DonateResource / OnClick_DonateWeapon deu duyet UIBag.GetSelect() roi WriteByte
    TUNG slot da chon vao CUNG mot sendBuffer -> MOT goi nhieu slot. Bot gui tung slot mot thi moi
    lenh nghi `wait`; van tieu ra nhieu rac nen co acc donate ca chuc slot.
    """

    def test_nguyen_lieu_gom_mot_lenh(self):
        t = _than("donate_legion")
        self.assertIn(r'self.send(0x27, b"\x0f\x00\x00\x00\x00\x00" + bytes(_slots))', t)
        # KHONG con gui trong vong lap
        i = t.find("for slot, tid, cnt in targets:")
        j = t.find("if _slots:")
        self.assertGreater(i, 0)
        self.assertGreater(j, i)
        self.assertNotIn("self.send(0x27", t[i:j], "van con gui tung slot trong vong lap")

    def test_trang_bi_gom_mot_lenh(self):
        t = _than("donate_legion_equip")
        self.assertIn(r'self.send(0x27, b"\x0f\x00\x00\x00\x00\x00" + bytes(ds))', t)

    def test_van_log_tung_mon(self):
        """Gom goi nhung phai giu log tung mon - khong thi khong biet bot vua donate cai gi."""
        t = _than("donate_legion")
        self.assertIn("donate quan doan slot=%d tid=0x%04x", t)


class TestListRuongTrenGUI(unittest.TestCase):
    """User chot 03/09: tick "Tu don ruong trang bi va Pho ban" + nut "List ruong",
    MAC DINH KHONG TICK."""

    def test_co_tick_va_nut_list(self):
        s = _doc("gui.py")
        self.assertIn('text="Tự dọn rương trang bị và Phó bản"', s)
        self.assertIn('text="List rương", command=self._open_box_list', s)

    def test_tick_nam_GIUA_donate_QD_va_phan_giai_cuon(self):
        """User chot 03/09 - dung thu tu bot chay that (mo ruong ngay sau donate quan doan)."""
        s = _doc("gui.py")
        i_qd = s.find('text="Tự đóng góp nguyên liệu cho quân đoàn"')
        i_bx = s.find('text="Tự dọn rương trang bị và Phó bản"')
        i_cuon = s.find('text="Tự phân giải cuộn võ tướng rác"')
        self.assertGreater(i_qd, 0)
        self.assertLess(i_qd, i_bx, "phai nam SAU donate quan doan")
        self.assertLess(i_bx, i_cuon, "phai nam TRUOC phan giai cuon")

    def test_giai_thich_nam_TRONG_dialog_list_ruong(self):
        """De ngoai bang 'Don dep tui do' thi doan text dai lam roi mat (user chot 03/09)."""
        s = _doc("gui.py")
        i = s.find("def _open_box_list")
        self.assertGreater(i, 0)
        doan = s[i:i + 2500]
        self.assertIn("đồ phân giải được thì phân giải lấy mảnh", doan)
        # KHONG con o bang cha
        i_bang = s.find("def _open_bag_clean")
        if i_bang > 0:
            self.assertNotIn("chỉ đụng đồ vừa mở ra", s[i_bang:i_bang + 3000].lower())

    def test_mac_dinh_TAT(self):
        s = _doc("gui.py")
        self.assertIn('self._preset.get("auto_open_boxes", False)', s)

    def test_khong_tick_ruong_nao_thi_KHONG_lam_gi(self):
        t = _than("tu_mo_hop_trang_bi")
        self.assertIn("if not _tick:", t)
        self.assertIn("chua tick ruong nao", t)

    def test_chay_NGAY_SAU_donate_nguyen_lieu(self):
        s = _doc("run_party_digioi.py")
        i = s.find("c.donate_legion()")
        j = s.find("c.tu_mo_hop_trang_bi(")
        self.assertGreater(i, 0)
        self.assertGreater(j, i, "phai chay SAU donate quan doan")
        self.assertLess(j - i, 1200, "phai NGAY SAU, khong xen viec khac vao giua")

    def test_khai_bao_du_CA_HAI_noi(self):
        """CLAUDE.md: file du lieu dung chung phai khai o SHARED_ASSETS (APK) VA DATA_JSON (exe)."""
        self.assertIn('"bliss_bag.json"', _doc("tools", "sync_apk_python.py"))
        self.assertIn('"bliss_bag.json"', _doc("build_product.py"))


class TestVutMonKet(unittest.TestCase):
    """User chot 03/09: "do nao ko phan giai ko donate duoc thi m vut bo luon".

    Mon KET = fc==0 VA truot ArmyFilter. Vi du: Hoai Nam Tu / Tam Luoc / Kim Quy Kinh - sach
    (kind=9, material=37): fc=0 nen khong phan giai, material 37 nam ngoai dai 1..36 nen khong
    donate. Khong vut thi no nam li lam day tui (log 18:55: tui day sau 21 hop).
    """

    def test_co_nhanh_vut(self):
        t = _than("_xu_ly_do_vua_mo")
        self.assertIn("self.discard_item(s, rec[1])", t)
        self.assertIn("VUT BO", t)

    def test_thu_tu_phan_giai_donate_roi_moi_vut(self):
        t = _than("_xu_ly_do_vua_mo")
        i_pg = t.find("self.decompose_slot(s)")
        i_dn = t.find("elif self._donate_quan_doan_duoc(")
        i_vut = t.find("self.discard_item(")
        self.assertGreater(i_pg, 0)
        self.assertLess(i_pg, i_dn, "phan giai phai truoc donate")
        self.assertLess(i_dn, i_vut, "vut la lua chon CUOI CUNG")

    def test_bo_loc_donate_sao_y_ArmyFilter(self):
        s = _doc("bot", "client.py")
        self.assertIn("_DONATE_MAT_OK = set(range(1, 9)) | set(range(10, 23)) | set(range(24, 37))", s)
        self.assertIn("_DONATE_KIND_CAM = {20, 21, 22}", s)
        t = _than("_donate_quan_doan_duoc")
        self.assertIn('if int(rec.get("kd") or 0) == 53:', t)
        self.assertIn('if int(rec.get("lv") or 0) == 0:', t)

    def test_items_gamedata_co_material_va_level(self):
        """Khong co 2 truong nay thi bot KHONG THE biet mon nao qua noi ArmyFilter."""
        with io.open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        r = d["0xa42e"]          # Kinh Truc Phien (nguyen lieu)
        self.assertEqual(r.get("mat"), 21)
        self.assertEqual(r.get("lv"), 17)

    def test_bliss_bag_co_co_dn(self):
        with io.open(os.path.join(ROOT, "bliss_bag.json"), encoding="utf-8") as fh:
            d = json.load(fh)["boxes"]
        for v in d.values():
            for it in v["items"]:
                self.assertIn("dn", it, v["name"])

    def test_sach_Hoai_Nam_Tu_dung_la_mon_KET(self):
        """Neu game sua material/furnaceCount cua sach thi luat vut phai xem lai."""
        with io.open(os.path.join(ROOT, "bliss_bag.json"), encoding="utf-8") as fh:
            d = json.load(fh)["boxes"]
        hnt = [i for i in d["0xb534"]["items"] if i["name"] == "Hoài Nam Tử"]
        self.assertTrue(hnt, "khong con Hoai Nam Tu trong Hop Trang Bi Cap 20")
        self.assertEqual(hnt[0]["fc"], 0)
        self.assertFalse(hnt[0]["dn"])


if __name__ == "__main__":
    unittest.main()
