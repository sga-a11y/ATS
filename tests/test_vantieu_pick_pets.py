"""Chon PET nao duoc di van tieu (yeu cau user: don EXP cho vai con thay vi dan deu ca nha tro).

Luat:
  - roster rong (acc khong co pet trong nha tro)     -> khong co ung vien
  - khong tick con nao, HOAC tick HET                -> dung TAT CA (y het hanh vi cu)
  - tick le                                          -> chi nhung con duoc tick
Tick luu theo PET ID chu KHONG theo index nha tro (index xe dich khi them/bot pet).
"""
import json
import unittest
from pathlib import Path

from bot.client import GameClient

ROOT = Path(__file__).resolve().parents[1]


def make_client(roster=None, ids=None, pick=(), enable=True):
    c = GameClient.__new__(GameClient)
    c._label = "vt"
    c._username = "acc1"
    c.vantieu_roster = dict(roster or {})
    c.vantieu_roster_ids = dict(ids or {})
    c.vantieu_pick_ids = tuple(pick)
    c.vantieu_enable = enable
    return c


ROSTER = {1: "Cửu Sởi", 2: "Giản Ung", 3: "Châu Tĩnh", 4: "Đỗ Viễn"}
IDS = {1: 0x3710, 2: 0x2f07, 3: 0x3712, 4: 0x272d}


class TestVantieuCandidates(unittest.TestCase):
    def test_khong_tick_con_nao_thi_dung_TAT_CA(self):
        """Mac dinh cua tinh nang moi -> KHONG duoc lam doi thoi quen user dang chay bot."""
        c = make_client(ROSTER, IDS, pick=())
        self.assertEqual([i for i, _ in c.vantieu_candidates()], [1, 2, 3, 4])

    def test_tick_HET_cung_la_dung_tat_ca(self):
        c = make_client(ROSTER, IDS, pick=tuple(IDS.values()))
        self.assertEqual([i for i, _ in c.vantieu_candidates()], [1, 2, 3, 4])

    def test_tick_le_thi_CHI_nhung_con_duoc_tick(self):
        c = make_client(ROSTER, IDS, pick=(0x2f07, 0x272d))
        self.assertEqual(c.vantieu_candidates(), [(2, "Giản Ung"), (4, "Đỗ Viễn")])

    def test_acc_KHONG_co_pet_trong_nha_tro(self):
        self.assertEqual(make_client({}, {}, pick=(0x2f07,)).vantieu_candidates(), [])

    def test_tick_pet_KHONG_con_trong_nha_tro_thi_coi_nhu_khong_tick(self):
        """User ban/lay pet ra khoi nha tro -> tick tro thanh vo nghia. Khong duoc de bot dung
        hinh: roi ve dung TAT CA (giong khong tick) chu khong phai khong gui gi."""
        c = make_client(ROSTER, IDS, pick=(0xdead,))
        self.assertEqual([i for i, _ in c.vantieu_candidates()], [1, 2, 3, 4])

    def test_tick_theo_PET_ID_nen_them_pet_KHONG_lam_truot_tick(self):
        """Them 1 con vao dau nha tro -> moi index dich 1. Tick theo id thi van dung con cu."""
        c = make_client(ROSTER, IDS, pick=(0x3712,))
        self.assertEqual(c.vantieu_candidates(), [(3, "Châu Tĩnh")])

        roster2 = {1: "Pet Moi", 2: "Cửu Sởi", 3: "Giản Ung", 4: "Châu Tĩnh", 5: "Đỗ Viễn"}
        ids2 = {1: 0x1111, 2: 0x3710, 3: 0x2f07, 4: 0x3712, 5: 0x272d}
        c2 = make_client(roster2, ids2, pick=(0x3712,))
        self.assertEqual(c2.vantieu_candidates(), [(4, "Châu Tĩnh")],
                         "tick bi truot sang con khac khi nha tro doi")


class TestVantieuRosterParser(unittest.TestCase):
    """Doc pet id tu goi THAT S:031-006 (vt_kholog.pcap) - xem KNOWLEDGE.md muc van tieu."""

    GOI = bytes.fromhex(
        "060001103728167a070081000000124300ed1e750020005300df1e690000006e000002072f29868b0800"
        "180100001247006900a31e6e00200055006e0067000000000312372056340300160100001443006800e2"
        "0075002000540029016e006800000000042d272356ab040053010000121001d71e200056006900c51e6e"
        "000000000000")

    def test_boc_dung_ten_va_pet_id_tu_goi_that(self):
        c = make_client()
        c._on_vantieu_roster(b"\x00" * 7 + self.GOI)

        self.assertEqual(c.vantieu_roster, ROSTER)
        self.assertEqual(c.vantieu_roster_ids, IDS)

    def test_pet_id_doi_chieu_KHOP_bang_ten_npc(self):
        """Moc tu kiem chung: pet id boc ra phai tra dung TEN trong npc_names.json. Neu offset
        lech thi khong the khop ca 4/4 duoc."""
        names = json.loads((ROOT / "npc_names.json").read_text(encoding="utf-8"))
        names = names.get("names", names)
        c = make_client()
        c._on_vantieu_roster(b"\x00" * 7 + self.GOI)

        for idx, pid in c.vantieu_roster_ids.items():
            self.assertEqual(names.get("0x%04x" % pid), c.vantieu_roster[idx],
                             "pet id 0x%04x khong khop ten" % pid)

    def test_goi_CAP_NHAT_1_con_KHONG_duoc_xoa_cac_con_khac(self):
        """BUG THAT (user: "chi nhan dung 1 con"): server gui list DAY DU luc login, roi moi khi
        mot con doi trang thai (vd vua gui di van tieu) lai gui GOI CAP NHAT chi chua con do.
        Client ghi vao O this.npcs[index] (Inn.SaveNpc) va GIU cac o khac; bot truoc day THAY SACH
        ca bang -> con dung 1 con. Bang chung trong log: CUNG acc luc du 3 con luc chi 1 con, va
        acc quanmot con moi index 3 (khong phai con dau) -> khong phai parse hong."""
        c = make_client()
        c._on_vantieu_roster(b"\x00" * 7 + self.GOI)
        self.assertEqual(len(c.vantieu_roster), 4)

        goi_1_con = bytes(7) + bytes([0x06, 0x00]) + self._ban_ghi()[1]

        # 1) Goi 1 con TU NO phai parse ra dung 1 con -> chung minh phan 2 khong xanh OAN
        #    (merge giu san 4 con, nen chi assert "van du 4" thi parse hong cung PASS).
        c2 = make_client()
        c2._on_vantieu_roster(goi_1_con)
        self.assertEqual(c2.vantieu_roster, {2: "Giản Ung"})

        # 2) Goi 1 con den SAU list day du: chi ghi de o do, KHONG xoa cac con khac
        c._on_vantieu_roster(goi_1_con)
        self.assertEqual(len(c.vantieu_roster), 4, "goi cap nhat 1 con da xoa mat cac con khac")
        self.assertEqual(c.vantieu_roster[1], "Cửu Sởi")
        self.assertEqual(c.vantieu_roster[4], "Đỗ Viễn")
        self.assertEqual(c.vantieu_roster_ids[2], 0x2f07)

    def _ban_ghi(self):
        """Cat goi that thanh tung ban ghi (14 + L byte moi cai)."""
        b, pos, recs = self.GOI, 2, []
        for _ in range(4):
            ln = b[pos + 12]
            recs.append(b[pos:pos + 13 + ln + 1])
            pos += 13 + ln + 1
        return recs

    def test_khong_cat_cut_ten(self):
        """L la do dai VUNG ten chu khong phai do dai ten; ten ket thuc bang \\0 BEN TRONG vung,
        phan du la RAC. Tim \\0\\0 bang bytes.find() se bat trung cap LECH (ten ket thuc 'i' =
        69 00 roi 00 00 -> ...69 00 00 00) -> mat ky tu cuoi."""
        c = make_client()
        c._on_vantieu_roster(b"\x00" * 7 + self.GOI)

        self.assertEqual(c.vantieu_roster[1], "Cửu Sởi")     # khong phai "Cửu Sở"
        self.assertEqual(c.vantieu_roster[3], "Châu Tĩnh")   # khong phai "Châu Tĩn"


if __name__ == "__main__":
    unittest.main()
