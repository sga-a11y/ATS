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
SK_LO, SK_HI = 0x2710, 0x33ff


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
                            # idx22 (so voi id) = DOI REBORN: 0=base, 1=reborn(rb1), 2=rb2
                            pets[pid] = {"name": name, "skills": sk, "rb": d[i + 22]}
                            break
        i += 1
    return pets


def _form_name(base, rb):
    """Nhan theo DOI REBORN (idx22 trong record): 0=base -> 'ten rb0'; 1=reborn -> 'ten' (khong
    hau to, = rb1); 2 -> 'ten rb2'. (Data chi tach chac base vs reborn; rb1/rb2 it phan biet.)"""
    if rb == 1:
        return base
    return "%s rb%d" % (base, rb)


def main():
    pets = parse_pets(NPC)
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
        if hd:
            rec["he"], rec["doanh"] = hd.get("he", ""), hd.get("doanh", "")
        out["0x%04x" % pid] = rec
    data = {
        "_note": "AUTO-SINH tu tools/crack_pets.py (Npc_C.dat). pet_id hex -> name (nhan DOI tu idx22: "
                 "rb0=base, ten=reborn/rb1, rb2), skills (FULL), he/doanh (join pet_hedoanh.json theo "
                 "ten goc). boss/combo tu suy o combat tu skills_data.json.",
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
