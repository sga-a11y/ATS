"""CANH GAC TOAN FILE: khong duoc co vong cho nao DIEC voi lenh dieu phoi.

Day la bai hoc dat nhat cua ngay 07/09. Dieu phoi chay dung, ra lenh dung, in ra ro rang - va
KHONG AI NGHE, vi acc dang ket trong mot vong cho o cho khac:

    party 15, 26 PHUT (14:40:59 -> 15:06:32)
      [trusauu] (LEADER) CHO ca party report o5 (4/5)...
      [trutam]  (member) CHO leader danh xong team dungeon...
      trong khi:
      14:57:37 / 14:59:37 / 15:01:38 / 15:03:38 / 15:05:38
        [party 15] DIEU PHOI: ca party da chung kenh 1 nhung doi chi con 0/3 -> LAP LAI PARTY

    party 1, 44 PHUT: brub ket o `while not (leader_ok or leader_bad)`; ca nam dua deu da o
      Truong Sa ma van cho nhau.

    party 42/23: barrier "cho ca party relogin sau PB vo" / "cho ca party xong daily".

Va cai gia khong chi la thoi gian: member ket o bai quai voi `flee_mode` thi "BO CHAY" lien tuc,
tuc BI QUAI DANH LE ma khong danh tra (user: "member bi quai danh le").

Vi vay: **moi vong cho acc khac deu phai co LOI RA CAP PARTY.** `stopped()` va `c.running` KHONG
tinh - do chi la "bot tat" / "minh rot", khong pha duoc the ket. Loi ra hop le la mot trong:
`reform_gen` doi · `_ab()` · `_resync_ck` · `dang_pha_pho_ban` · `disc_gen` · `reconnecting` ·
`_barrier_watchdog` · doc `ke_hoach` · co giveup cua pha.

Test nay quet CA FILE. Them mot vong cho moi ma quen loi ra thi no do ngay - dung sua test, hay
them loi ra.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Loi ra CAP PARTY - thu pha duoc the ket, khac han `stopped()` / `c.running`.
LOI_RA = (
    "reform_gen", "_ab()", "_resync_ck", "dang_pha_pho_ban", "disc_gen", "reconnecting",
    "_barrier_watchdog", "ke_hoach", "_dg_giveup", "_dg_solo_bail", "_sync_gen_moved",
)

# Vong cho: `while True`, `while not <co>.is_set()`, `while <dem> < <ky vong>`.
VONG = re.compile(r"while (True:|not .*is_set\(\)|.*<\s*st\[|.*<\s*expected)")

# Vong duoc mien tru phai TU KHAI trong code bang dong "MIEN TRU vong cho diec: <ly do>" dat ngay
# tren no - de nguoi doc diff thay ngay ai xin mien va vi sao.
MIEN = ("MIEN TRU vong cho diec",)


def _src(ten="run_party_digioi.py"):
    with io.open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


class TestKhongCoVongDiec(unittest.TestCase):
    def test_moi_vong_cho_deu_nghe_duoc_lenh(self):
        dong = _src().splitlines()
        xau = []
        for i, d in enumerate(dong):
            if not VONG.match(d.strip()):
                continue
            # doc nguoc vai dong de bat duoc dong "MIEN TRU vong cho diec" dat ngay tren vong
            than = chr(10).join(dong[max(0, i - 12):i + 45])
            if any(k in than for k in LOI_RA):
                continue
            if any(k in than for k in MIEN):
                continue
            xau.append("%d: %s" % (i + 1, d.strip()[:90]))
        self.assertEqual(xau, [], "vong cho DIEC voi lenh dieu phoi:\n  " + "\n  ".join(xau))

    def test_stopped_va_running_KHONG_tinh_la_loi_ra(self):
        """Neo chinh dinh nghia: neu ai do them 'stopped' vao LOI_RA thi test tren thanh vo dung."""
        for k in ("stopped", "c.running", "_stopped()"):
            self.assertNotIn(k, LOI_RA)


class TestCacBarrierDaBo(unittest.TestCase):
    """Nhung barrier da giet party trong ngay 07/09 - khong duoc quay lai."""

    def test_da_bo_han(self):
        # chu thich lich su van duoc phep nhac ten - chi cam DUNG lai
        code = [d for d in _src().splitlines()
                if d.strip() and not d.strip().startswith("#")]
        code = chr(10).join(code)
        # `o5_done_by` van con nhung KHONG con la barrier: leader doc MOT PHAT roi quyet
        # (acc chua bao thi coi nhu da xong), khong ai cho ai - xem test_o5_khong_cho_report.py.
        for m in ("team_dungeon_recover_seen", "team_dungeon_recover_ready",
                  "channel_map_reports"):
            self.assertNotIn('st["%s"]' % m, code, m)
        for m in ("_pb_vo_diem_danh", "_record_channel_map_report"):
            self.assertNotIn("%s(st" % m, code, m)

    def test_khong_con_dong_log_cho_nao(self):
        s = _src()
        cam = ("CHO ca party report o5", "cho ca party relogin sau PB vo",
               "CHO leader quyet dinh", "cho acc bao cao map")
        for d in s.splitlines():
            if "log." not in d:
                continue
            for m in cam:
                self.assertNotIn(m, d, d.strip())


if __name__ == "__main__":
    unittest.main()
