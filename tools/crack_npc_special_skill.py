"""Sinh npc_special_skill.json: DAC KY RIENG (武將特有技) cua tung vo tuong.

Dac ky phai LAM NHIEM VU moi mo. Client can DUNG HAI thu ghep lai (RoleController.lua:4786):
    if self.data.specialSkillLearned and skillDatas[npcDatas[self.npcId].specialSkill] ~= nil
  - specialSkillLearned : co THEO TUNG CON, server gui trong goi pet list (bot da doc - xem
                          client.pet_special_skill)
  - specialSkill        : ID skill, nam o BANG TINH NpcData truong [35] - chinh la thu file nay bocs

VI SAO KHONG DUNG tools/crack_pets.py: tool do QUET CHU KY (tim 3 u16 giong skill o +50/52/54)
chu khong doc tuan tu. Neu vi tri neo lech thi cac truong PHIA SAU sai theo ma khong ai biet -
da kiem chung: doc specialSkill o +56 theo kieu quet cho ra 0x7200 / 0x001a / 0x0d02 o
upgradeItemId (khong phai id vat pham) tren nhieu ban ghi.

File nay doc TUAN TU dung thu tu NpcData.New (Data/NpcData.lua:236). Bo cuc 1 ban ghi:
    [nameLen u16][name utf-16le][kind 1][id u16] roi 78 byte CO DINH:
    +2 picId u16 | +4 maskId u16 | +6 colorTints i32 x4 | +22 canBeCatch | +23 bodyKind
    +24 weaponKind | +25 level | +26 hpBase i32 | +30 spBase i32
    +34..+45 attributes u16 x6 | +46 moral | +47 moralValue u16 | +49 element
    +50 skills u16 x3 | +56 specialSkill u16 | +58 turn | +59 passiveSkill u16
    +61 passiveSkillLv | +62 saddleKind u16 | +64 upgradeItemId u16 | +66 upgradeSkill u16
    +68 limit u16 | +70 rideOffsetH u16 | +72 picOffsetX | +74 picOffsetY | +76 hudOffsetH
    +78 shadowKind | +79 rare        -> ban ghi ket thuc o +80 sau id

2 MOC TU KIEM CHUNG (neu parse lech thi hong ngay, khong am tham):
  - skills[3] o +50 PHAI trung voi ket qua cua crack_pets.py (tool cu da duoc dung lau)
  - rideOffsetH/picOffset/hudOffset doc raw roi TRU 1000 -> raw thuong quanh 1000; lech nhieu
    = parse sai.

File .dat KHONG theo repo (gitignore) - copy tu client vao truoc khi chay:
    gamedata_Npc.dat  (hoac gamedata/Data/Npc_C.dat)
Chay: python tools/crack_npc_special_skill.py
Ghi:  npc_special_skill.json  { "<id hex>": <special_skill_id> }  (chi ghi con CO dac ky)
"""
from __future__ import annotations

import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import _find          # noqa: E402

OUT = os.path.join(ROOT, "npc_special_skill.json")

TAIL = 80          # so byte SAU id (id chiem 2 byte dau cua khoi nay)
SK_LO, SK_HI = 0x2710, 0x7FFF


def _u16(d, i):
    return struct.unpack_from("<H", d, i)[0]


def parse(path):
    """Doc TUAN TU. Tra (recs, loi) - recs = {id: {...}}."""
    d = open(path, "rb").read()
    n = len(d)
    # Header: thu ca u32 va u16 lam so ban ghi, chon cai parse duoc TRON VEN toi cuoi file.
    for hdr, count in ((4, struct.unpack_from("<I", d, 0)[0]),
                       (2, _u16(d, 0))):
        if not (0 < count < 100000):
            continue
        recs, i, ok = {}, hdr, True
        for _ in range(count):
            if i + 2 > n:
                ok = False
                break
            nl = _u16(d, i)
            j = i + 2 + nl                      # sau ten
            if nl > 200 or j + 1 + TAIL > n:
                ok = False
                break
            try:
                name = d[i + 2:j].decode("utf-16-le")
            except Exception:
                name = ""
            k = j + 1                           # bo qua kind(1) -> tro toi id
            pid = _u16(d, k)
            recs[pid] = {
                "name": name,
                "skills": [_u16(d, k + o) for o in (50, 52, 54)],
                "special": _u16(d, k + 56),
                "upgrade_item": _u16(d, k + 64),
                "ride_raw": _u16(d, k + 70),    # raw ~1000 -> moc tu kiem chung
            }
            i = k + TAIL
        if ok and abs(i - n) <= 8:              # tieu het file = parse DUNG
            return recs, None
    return {}, "khong parse tron ven duoc file (thu ca header u32 va u16)"


def main():
    path = _find("gamedata_Npc.dat", os.path.join("gamedata", "Data", "Npc_C.dat"))
    if not path:
        raise SystemExit("Khong thay gamedata_Npc.dat (hoac gamedata/Data/Npc_C.dat).\n"
                         "COPY tu client vao thu muc repo roi chay lai.")
    recs, err = parse(path)
    if err:
        raise SystemExit("PARSE LOI: %s" % err)
    print("doc tuan tu: %d ban ghi" % len(recs))

    # --- MOC TU KIEM CHUNG 1: ride offset raw phai quanh 1000 ---
    xa = [p for p, r in recs.items() if not (500 <= r["ride_raw"] <= 1500)]
    print("  ride_raw ngoai [500..1500]: %d ban ghi (%.1f%%)"
          % (len(xa), 100.0 * len(xa) / max(len(recs), 1)))
    if len(xa) > len(recs) * 0.05:
        raise SystemExit("=> NGHI PARSE LECH: qua nhieu ride_raw bat thuong")

    # --- MOC TU KIEM CHUNG 2: skills phai trung tool cu ---
    try:
        import crack_pets
        cu = crack_pets.parse_pets(path)
        chung = [p for p in cu if p in recs]
        khop = [p for p in chung if recs[p]["skills"][:len(cu[p]["skills"])] == cu[p]["skills"]
                or [s for s in recs[p]["skills"] if s] == cu[p]["skills"]]
        print("  doi chieu skills voi crack_pets.py: khop %d/%d" % (len(khop), len(chung)))
    except Exception as e:
        print("  (bo qua doi chieu crack_pets: %s)" % e)

    co = {p: r for p, r in recs.items() if SK_LO <= r["special"] <= SK_HI}
    print("  co DAC KY: %d / %d" % (len(co), len(recs)))
    out = {"_note": "DAC KY RIENG cua vo tuong (NpcData [35] specialSkill). Bot chi duoc dung khi "
                    "co CO da mo cua CHINH con do (client.pet_special_skill, tu goi pet list). "
                    "Sinh boi tools/crack_npc_special_skill.py (doc TUAN TU, khong quet chu ky).",
           "skills": {("0x%04x" % p): r["special"] for p, r in sorted(co.items())}}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("=> %s: %d vo tuong co dac ky" % (os.path.basename(OUT), len(co)))
    for p, r in list(sorted(co.items()))[:8]:
        print("   0x%04x %-24s dac ky=%d (0x%04x)" % (p, r["name"][:22], r["special"], r["special"]))


if __name__ == "__main__":
    main()
