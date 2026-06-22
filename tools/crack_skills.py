"""Crack skills_data.json tu gamedata Skill_C.dat.

Record (parse theo MO NEO TEN - moi skill co ten, tin cay hon d.find):
  [namelen 2B LE][name UTF-16LE][1B gap][id 2B][cost 2B][...][cat=id+11][splash=id+12]
  cat (idx11): LOAI skill -> 1 = DAME combo duoc (NemDa/DaLan/HoaTien/LoanKich)
                             2 = DAME khong combo (MuaDa, ThaiSonApDinh, all-target)
                             4..15 = SUPPORT (buff/giai/hoi MP/heal/hoi sinh/debuff)
  splash (idx12): 1=don | 2=trai doc | 3=trai ngang | 4=don dap (multi-hit 1 muc tieu) | 8=TOAN BO quai
combat: DAME = cat in {1,2}; COMBO duoc = cat==1; ALL-TARGET = splash==8.

Chay: python tools/crack_skills.py   (-> ghi skills_data.json)
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "gamedata", "Data", "Skill_C.dat")
OUT = os.path.join(ROOT, "skills_data.json")
SK_LO, SK_HI = 0x2710, 0x33ff


def parse_skills(path):
    d = open(path, "rb").read()
    n = len(d)
    out = {}
    i = 4   # bo count 4B
    while i < n - 8:
        nl = int.from_bytes(d[i:i + 2], "little")
        if 2 <= nl <= 60 and nl % 2 == 0 and i + 2 + nl + 15 <= n:
            try:
                name = d[i + 2:i + 2 + nl].decode("utf-16-le")
            except Exception:
                name = None
            if name and all(0x20 <= ord(c) < 0x2200 for c in name) and any(c.isalpha() for c in name):
                ip = i + 2 + nl + 1   # id sau name + 1B gap
                sid = int.from_bytes(d[ip:ip + 2], "little")
                cost = int.from_bytes(d[ip + 2:ip + 4], "little")
                if SK_LO <= sid <= SK_HI and cost <= 300:
                    if sid not in out:
                        out[sid] = {"cost": cost, "cat": d[ip + 11], "splash": d[ip + 12]}
                    i = ip + 2
                    continue
        i += 1
    # Skill ten co dau thanh GHEP (combining) -> namelen lech -> anchor bo sot. Them tay (da verify
    # tai vi tri record dung trong Skill_C). Pet dung nhung mo neo khong bat.
    for sid, rec in MANUAL.items():
        out.setdefault(sid, rec)
    return out


# Skill mo neo bo sot (ten combining) - gia tri doc TAI VI TRI RECORD DUNG (da verify):
MANUAL = {
    0x2f05: {"cost": 84, "cat": 1, "splash": 1},   # Liet Tram (combo)
    0x2f0a: {"cost": 54, "cat": 7, "splash": 3},   # heal
}


def main():
    sk = parse_skills(SKILL)
    data = {
        "_note": "AUTO-SINH tu tools/crack_skills.py (Skill_C.dat, mo neo ten). skill_id hex -> "
                 "cost (SP), cat (idx11: LOAI - 1=dame combo duoc, 2=dame khong combo, 4..15=support), "
                 "splash (idx12: 1=don,2=trai doc,3=trai ngang,4=don dap,8=toan bo quai). "
                 "combat: DAME=cat in{1,2}; COMBO=cat==1; ALL-TARGET=splash==8.",
        "skills": {"0x%04x" % k: sk[k] for k in sorted(sk)},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    print("Da crack %d skill -> %s" % (len(sk), OUT))
    # verify: (cost, cat, splash)
    known = {12003: (15, 1, 3), 13013: (49, 1, 4), 12009: (30, 1, 1), 10005: (22, 1, 3),
             10007: (34, 1, 2), 10012: (50, 2, 8), 12014: (60, 2, 8), 11010: (42, 7, 1),
             13011: (33, 15, 1), 10000: (0, 1, 1)}
    for sid, (c, ca, sp) in known.items():
        g = sk.get(sid)
        ok = g and g["cost"] == c and g["cat"] == ca and g["splash"] == sp
        print("  %d: %s %s" % (sid, g, "OK" if ok else "SAI(mong cost=%d cat=%d sp=%d)" % (c, ca, sp)))


if __name__ == "__main__":
    main()
