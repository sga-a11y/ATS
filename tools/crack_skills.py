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
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "gamedata", "Data", "Skill_C.dat")
OUT = os.path.join(ROOT, "skills_data.json")
SK_LO, SK_HI = 0x2710, 0x5000


def parse_skills_seq(path):
    """Doc TUAN TU theo dung SkillData.New (Data/SkillData.lua:4) - CHINH XAC, thay cho quet chu ky.

    Bo cuc 1 ban ghi:
      [nameLen u16][name utf-16le][kind 1][id u16][34 byte co dinh][descLen u16][desc utf-16le]
    Trong 34 byte tinh tu vi tri id (ip):
      ip+2 requireSp(u16) | ip+4 element | ip+5 numerical(u32) | ip+9 attribute | ip+10 level
      ip+11 fightWay | ip+12 fightArea | ip+13 round | ip+14 spendSecond | ip+15 hitStatus
      ip+16 howMuchTimes | ip+17 limitLv | ip+18 learnPoint | ip+19 levelUpPoint | ip+20 maxLv
      ip+21 preSkill(u16) | ip+23 atkKind(u16) | ip+25 turnKind | ip+26 preSkill2(u16)
      ip+28 learnLimit | ip+29 useLimit(u16) | ip+31 fightWayGrowType(u16)  -> het o ip+33
    6 moc ip+11/12/17/18/19/20 TRUNG voi cac offset tool quet cu da dung lau -> bo cuc dung.

    VI SAO BO KIEU QUET: header file ghi 541 ban ghi, quet chu ky chi ra 377 (sot 164, trong do co
    TOAN BO dac ky vo tuong 21001..21025), lai con ghep NHAM ten (skill 12042 bi gan ten "Tri Lieu"
    cat=7 support, thuc te la "Xa Mau Hon Phe Kich Ao Dieu" cat=1 dame) va BIA ra skill 16640
    khong co trong file.
    """
    import struct
    d = open(path, "rb").read()
    count = struct.unpack_from("<i", d, 0)[0]
    if not (0 < count < 100000):
        raise SystemExit("header so ban ghi bat thuong: %s" % count)
    out, i = {}, 4
    for _ in range(count):
        nl = struct.unpack_from("<H", d, i)[0]
        j = i + 2 + nl
        if nl > 400 or j + 34 + 2 > len(d):
            raise SystemExit("parse lech tai ban ghi thu %d" % len(out))
        ip = j + 1                       # bo kind(1) -> tro toi id
        sid = struct.unpack_from("<H", d, ip)[0]
        if sid:
            out[sid] = {
                "name": d[i + 2:j].decode("utf-16-le", "replace"),
                "cost": struct.unpack_from("<H", d, ip + 2)[0],
                "cat": d[ip + 11], "splash": d[ip + 12],
                "needLv": d[ip + 17], "learnPt": d[ip + 18],
                "lvUpPt": d[ip + 19], "maxLv": d[ip + 20],
            }
        k = j + 34
        i = k + 2 + struct.unpack_from("<H", d, k)[0]
    if abs(i - len(d)) > 8:              # TIEU HET FILE = parse dung
        raise SystemExit("parse xong con du %d byte -> nghi lech" % (len(d) - i))
    return out


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
                        # Layout SkillData.New (client): ip+17=limitLv (level can de HOC), ip+18=learnPoint
                        # (gia hoc cap 1), ip+19=levelUpPoint (gia moi cap sau), ip+20=maxLv (1/5/6/8/10).
                        out[sid] = {"name": name, "cost": cost, "cat": d[ip + 11], "splash": d[ip + 12],
                                    "needLv": d[ip + 17], "learnPt": d[ip + 18], "lvUpPt": d[ip + 19],
                                    "maxLv": d[ip + 20]}
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
    0x2f05: {"name": "Liệt Trảm", "cost": 84, "cat": 1, "splash": 1,
             "needLv": 0, "learnPt": 1, "lvUpPt": 1, "maxLv": 10},   # combo
    0x2f0a: {"name": "Trị Liệu", "cost": 54, "cat": 7, "splash": 3,
             "needLv": 0, "learnPt": 1, "lvUpPt": 1, "maxLv": 5},    # heal
}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sk = parse_skills_seq(SKILL)
    data = {
        "_note": "AUTO-SINH tu tools/crack_skills.py (Skill_C.dat, mo neo ten). skill_id hex -> "
                 "name, cost (SP), cat (idx11: LOAI - 1=dame combo duoc, 2=dame khong combo, 4..15=support), "
                 "splash (idx12: 1=don,2=trai doc,3=trai ngang,4=don dap,8=toan bo quai). "
                 "combat: DAME=cat in{1,2}; COMBO=cat==1; ALL-TARGET=splash==8. "
                 "needLv (ip+17)=level can de hoc, learnPt (ip+18)=diem hoc cap 1, "
                 "lvUpPt (ip+19)=diem moi cap sau, maxLv (ip+20)=cap toi da (1/5/6/8/10).",
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
        g_txt = json.dumps(g, ensure_ascii=False) if g else None
        print("  %d: %s %s" % (sid, g_txt, "OK" if ok else "SAI(mong cost=%d cat=%d sp=%d)" % (c, ca, sp)))


if __name__ == "__main__":
    main()
