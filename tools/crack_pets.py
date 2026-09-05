"""Crack pets.json tu gamedata Npc_C.dat.

Vung pet (pet_id 0xa0xx) trong Npc_C.dat: moi entry
  [namelen 2B LE][name UTF-16LE][0x20][pet_id 2B LE][...][skill1 2B][skill2 2B][skill3 2B]
  skill o offset pet_id+50/+52/+54 (cap nhat thu cong neu game doi format).
he/doanh join tu pet_hedoanh.json theo ten (Npc co he/doanh nhung pet_hedoanh da parse san).

Chay: python tools/crack_pets.py   (doc gamedata/Data/Npc_C.dat -> ghi pets.json)
"""
import struct, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPC = os.path.join(ROOT, "gamedata", "Data", "Npc_C.dat")
HEDOANH = os.path.join(ROOT, "pet_hedoanh.json")
OUT = os.path.join(ROOT, "pets.json")

SKILL_OFF = (50, 52, 54)   # offset 3 skill so voi pet_id (giong nhau MOI section/form)
# Dai skill pet. SK_HI PHAI theo game: game them skill MOI (0x34xx-0x5fxx) + pet moi (reborn) dung
# chung -> neu chan o 0x33ff thi cac pet do KHONG match anchor -> BI SOT khoi pets.json -> user
# "khong set duoc skill pet" (bug thuc te: Lu Bo nhieu ban reborn skill 0x55xx/0x59xx bi thieu).
SK_LO, SK_HI = 0x2710, 0x7fff


def parse_pets_seq(path):
    """Doc TUAN TU theo dung NpcData.New (Data/NpcData.lua:236) - CHINH XAC, thay cho quet chu ky.

    Ban ghi: [nameLen u16][name utf-16le][kind 1][id u16] + 78 byte CO DINH (het o +80 sau id).
    Cac offset tinh tu vi tri id (ip): ip+22 canBeCatch (KHONG dung - xem ghi chu 05/09),
    ip+50/52/54 skills, ip+56 specialSkill, ip+58 turn (DOI CHUYEN SINH that, xem duoi),
    ip+70 rideOffset raw (~1000 -> moc tu kiem chung).

    VI SAO BO KIEU QUET: header file ghi 8360 ban ghi. Kieu quet chu ky (tim 3 u16 giong skill o
    +50/52/54) SOT 59 pet - trong do co pet co ten hallo nhu 0x399e "Dieu Thuyen Khuynh Quoc" -
    va BIA them 13 muc khong co that. Pet bi sot = bot khong biet skill cua no.

    BO LOC "co ban chuyen sinh" (2026-08-25): bo loc cu ">=2 skill" LOAI NHAM vo tuong that chi
    co 1 skill - vd 0x3710 "Cuu Soi" (user dang nuoi, GUI hien tro "Pet (0x3710)"), va ca vo
    tuong 0 skill nhu Tao Thao/Bang Thong/Dang Ngai. Khong the noi thanh ">=1 skill": 2468 ban
    ghi 1-skill phan lon la QUAI (Du Binh, Tieu Vo Si...) -> do rac vao bang tra.
    Dau hieu tach dung: vo tuong THAT co BAN CHUYEN SINH, quai thi khong. Cot `turn` (--[36]
    判斷有無轉生限制) o ip+58 nhan 0/1/2 = doi chuyen sinh. Nen: nhan ban ghi neu >=2 skill
    HOAC ten do co it nhat mot ban `turn > 0`. Ket qua: +436 muc 1-skill va +126 muc 0-skill
    (deu la vo tuong), van loai 2032 quai 1-skill.

    DA SUA 05/09: `rb` gio doc ip+58 (`turn` = doi chuyen sinh THAT), KHONG con doc ip+22
    (`canBeCatch` --[10] 抓捕否, chi nhan 0/1 nen khong the la 3 doi). Truoc do hau to
    "rb0/rb1/rb2" SAI NGHIA suot - xem chu thich tai cho gan `pets[pid] = ...` ben duoi.
    """
    import struct
    d = open(path, "rb").read()
    count = struct.unpack_from("<i", d, 0)[0]
    if not (0 < count < 100000):
        raise SystemExit("header so ban ghi bat thuong: %s" % count)
    ban_ghi, i, xa = [], 4, 0
    for _ in range(count):
        nl = struct.unpack_from("<H", d, i)[0]
        j = i + 2 + nl
        if nl > 400 or j + 1 + 80 > len(d):
            raise SystemExit("parse lech tai ban ghi thu %d" % len(ban_ghi))
        ip = j + 1                       # bo kind(1) -> tro toi id
        pid = struct.unpack_from("<H", d, ip)[0]
        raw = [struct.unpack_from("<H", d, ip + o)[0] for o in SKILL_OFF]
        sk = [v for v in raw if SK_LO <= v <= SK_HI]
        ride = struct.unpack_from("<H", d, ip + 70)[0]
        if not (500 <= ride <= 1500):
            xa += 1
        try:
            name = d[i + 2:j].decode("utf-16-le")
        except Exception:
            name = ""
        ban_ghi.append((pid, name, sk, raw, d[ip + 22], d[ip + 58]))
        i = ip + 80
    if abs(i - len(d)) > 8:              # TIEU HET FILE = parse dung
        raise SystemExit("parse xong con du %d byte -> nghi lech" % (len(d) - i))
    if xa > count * 0.05:                # rideOffset raw phai quanh 1000
        raise SystemExit("nghi parse lech: %d/%d ban ghi co rideOffset bat thuong" % (xa, count))

    # Ten nao co ban CHUYEN SINH -> ten do la vo tuong that (xem docstring).
    co_chuyen_sinh = {nm for _p, nm, _s, _r, _c, turn in ban_ghi if turn > 0}

    pets = {}
    for pid, name, sk, raw, _canbecatch, turn in ban_ghi:
        if not pid or not all(SK_LO <= v <= SK_HI or v == 0 for v in raw):
            continue
        if len(sk) < 2 and name not in co_chuyen_sinh:
            continue
        # DOI CHUYEN SINH = `turn` (ip+58), KHONG phai `canBeCatch` (ip+22).
        # SUA 05/09 (user hoi "sao con Luc Ton ko co chu rb0"): ban cu lay ip+22 lam "doi reborn"
        # - do la `canBeCatch` (抓捕否), chi nhan 0/1 nen KHONG THE la doi chuyen sinh (phai co ca
        # gia tri 2). Hau to rb0/rb1/rb2 vi vay SAI NGHIA suot: co hay khong co "rb0" chi noi len
        # con do bat duoc hay khong.
        # Bang chung `turn` moi dung (do tren chinh Npc_C.dat, 8360 ban ghi):
        #   ip+22 -> chi {0: 3149, 1: 5211}          (2 gia tri -> khong the la 3 doi)
        #   ip+58 -> {0: 5800, 1: 1075, 2: 1485}     (du 3 doi)
        # va khop dai id da biet tu du lieu chuyen sinh (xem client.py `_load_chuyen_sinh_map`):
        #   0xA0xx (41xxx) = rb1 -> turn=1 o CA 572/572 ban ghi
        #   0xB0xx (45xxx) = rb2 -> turn=2 o 595/596
        #   0x27xx (10xxx) = rb0 -> turn=0 o 735/773
        pets[pid] = {"name": name, "skills": sk, "rb": turn}
    return pets


def parse_pets(path):
    """Quet TOAN BO dai id (KHONG gioi han 0xa0xx) -> bat het cac DANG pet: ban goc + reborn +
    reborn2 (id khac dai, skills khac nhau). Anchor = chu ky skill @+50/52/54 (ca 3 slot phai
    skill HOAC 0, >=2 skill that) + co TEN truoc id. Vai quai co the lan vao (vo hai - bot chi
    tra dung pet_id no co)."""
    d = open(path, "rb").read()
    n = len(d)
    pets = {}
    i = 2
    while i < n - 60:
        raw = [int.from_bytes(d[i + o:i + o + 2], "little") for o in SKILL_OFF]
        sk = [v for v in raw if SK_LO <= v <= SK_HI]
        if len(sk) >= 2 and all(SK_LO <= v <= SK_HI or v == 0 for v in raw):
            pid = int.from_bytes(d[i:i + 2], "little")
            if pid not in pets:
                # ten: [namelen 2B][name][1B sep] ngay truoc id (sep khac nhau: 0x20 / 0x03...)
                for nl in range(4, 42, 2):
                    if i - 3 - nl < 0:
                        break
                    if int.from_bytes(d[i - 3 - nl:i - 1 - nl], "little") == nl:
                        try:
                            name = d[i - 1 - nl:i - 1].decode("utf-16-le")
                        except Exception:
                            name = None
                        if name and all(0x20 <= ord(c) < 0x2200 for c in name) \
                                and any(c.isalpha() for c in name):
                            # HAM NAY main() KHONG DUNG (da thay bang parse_pets_seq). Neu
                            # dung lai thi PHAI doi sang ip+58 (`turn`) nhu parse_pets_seq -
                            # i+22 la `canBeCatch`, khong phai doi chuyen sinh.
                            pets[pid] = {"name": name, "skills": sk, "rb": d[i + 22]}
                            break
        i += 1
    return pets


def _form_name(base, rb):
    """Nhan theo DOI CHUYEN SINH (`turn`, ip+58): 0=base -> 'ten rb0'; 1 -> 'ten' (KHONG hau
    to); 2 -> 'ten rb2'. Quy uoc nay do user chot 05/09, giu y nguyen nhu cu - lan sua 05/09 chi
    doi NGUON doc (ip+22 -> ip+58), khong doi cach dat ten."""
    if rb == 1:
        return base
    return "%s rb%d" % (base, rb)


def main():
    pets = parse_pets_seq(NPC)
    hedoanh = {}
    try:
        hedoanh = json.load(open(HEDOANH, encoding="utf-8"))
    except Exception:
        pass
    out = {}
    for pid in sorted(pets):
        p = pets[pid]
        rec = {"name": _form_name(p["name"], p["rb"]), "skills": p["skills"]}
        hd = hedoanh.get(p["name"])   # join he/doanh theo TEN GOC
        if not hd:
            # DU PHONG theo HAU TO: pet_hedoanh.json khoa theo ten sinh tu ban CU (quet chu ky) nen
            # co khoa bi CUT DAU. Vd pet 0xb1b4 ten that "Am Hoang Nguyet Anh" nhung bang chi co
            # "Hoang Nguyet Anh" -> khop theo hau to CO RANH GIOI TU (dung dau cach) de khong ghep bua.
            for _k, _v in hedoanh.items():
                if _k and p["name"].endswith(" " + _k):
                    hd = _v
                    break
        if hd:
            rec["he"], rec["doanh"] = hd.get("he", ""), hd.get("doanh", "")
        out["0x%04x" % pid] = rec
    data = {
        "_note": "AUTO-SINH tu tools/crack_pets.py (Npc_C.dat). pet_id hex -> name (hau to theo DOI "
                 "CHUYEN SINH doc tu `turn` ip+58: rb0=base, KHONG hau to=rb1, rb2). Truoc 05/09 "
                 "doc nham ip+22 (canBeCatch) nen hau to sai nghia. skills (FULL), he/doanh (join "
                 "pet_hedoanh.json theo ten goc). boss/combo tu suy o combat tu skills_data.json.",
        "pets": out,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Da crack %d pet -> %s" % (len(out), OUT))
    # verify vai con da biet
    known = {"0xa05a": [13009, 13011, 13013], "0xa051": [12003, 12009, 12010],
             "0xa058": [13009, 13010, 13013]}
    for k, exp in known.items():
        got = out.get(k, {}).get("skills")
        print("  %s skills=%s %s" % (k, got, "OK" if got == exp else "SAI"))


if __name__ == "__main__":
    main()
