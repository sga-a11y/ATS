# -*- coding: utf-8 -*-
"""KHOA `documents/CORE_FLOW.md` - Claude khong duoc tu y sua.

User 21/09/2026:
  "t nghi la can viet ra 1 core flow, cai flow chuan cua game, co rule may bat buoc phai doc file
   nay truoc khi lam hay sua 1 flow nao do, m ko duoc tu y sua file nay ma ko co su cho phep cua t"

Luat mom thi Claude quen sau vai tuan. Bai test nay la RANG cua luat do: no giu VAN TAY (sha256)
cua file. Claude sua mot chu la test DO ngay, user khong phai ngoi canh.

== KHI USER CHO PHEP SUA ==
Sua file xong thi chay:

    python tools/khoa_core_flow.py

roi commit ca hai (file va van tay moi) trong CUNG mot commit. Cap nhat van tay MA KHONG co lenh
cua user chinh la cai bai test nay cam - dung lam.

Vi sao dung file van tay rieng chu khong nhung thang so vao day: de `git log` cua rieng file van
tay tra loi duoc "file core flow da duoc phep doi bao nhieu lan, luc nao".
"""
from __future__ import annotations

import hashlib
import io
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "documents", "CORE_FLOW.md")
VAN_TAY = os.path.join(ROOT, "documents", ".core_flow.sha256")


def _bam(path):
    with io.open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class TestKhoaCoreFlow(unittest.TestCase):
    def test_file_con_do(self):
        self.assertTrue(os.path.exists(FILE),
                        "XOA `documents/CORE_FLOW.md` - file nay la cua user, khong duoc xoa")

    def test_van_tay_KHOP(self):
        self.assertTrue(os.path.exists(VAN_TAY), "mat file van tay `documents/.core_flow.sha256`")
        with io.open(VAN_TAY, encoding="utf-8") as fh:
            luu = fh.read().strip().split()[0]
        self.assertEqual(
            _bam(FILE), luu,
            "\n\n  `documents/CORE_FLOW.md` DA BI SUA.\n"
            "  File nay la CUA USER - chi duoc sua khi user cho phep trong chinh luot do.\n"
            "  Neu user DA cho phep: chay `python tools/khoa_core_flow.py` roi commit ca hai.\n"
            "  Neu KHONG: hoan tac thay doi (`git checkout -- documents/CORE_FLOW.md`).\n")


class TestLuatVanCon(unittest.TestCase):
    """Van tay chi chan SUA TRAI PHEP. Con day la mot vai dieu du co phep cung khong duoc bo -
    chung la ly do file ton tai."""

    @classmethod
    def setUpClass(cls):
        with io.open(FILE, encoding="utf-8") as fh:
            cls.doc = fh.read()

    def test_con_du_BA_NHAN_nguon(self):
        for nhan in ("[CAPTURE]", "[LOG]", "[SUY ĐOÁN]"):
            self.assertIn(nhan, self.doc, "mat nhan nguon %s" % nhan)

    def test_SUY_DOAN_khong_co_quyen_doi_hanh_vi_dang_dung(self):
        """Cai chot quan trong nhat: suy doan cua Claude khong duoc dung de pha do dang chay dung."""
        self.assertIn("KHÔNG được dùng làm căn cứ để đổi một hành vi đang chạy đúng", self.doc)

    def test_con_tach_SERVER_DOI_va_BOT_TU_DAT(self):
        """Nham hai cai nay chinh la goc cua ca 21/09 (tuong 'cung map' la luat game)."""
        self.assertIn("SERVER ĐÒI", self.doc)
        self.assertIn("BOT TỰ ĐẶT", self.doc)

    def test_con_luat_doc_log_truoc_khi_sua(self):
        self.assertIn("party.log", self.doc)


if __name__ == "__main__":
    unittest.main()
