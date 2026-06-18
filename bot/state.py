"""Theo doi trang thai tran dau: HP/SP cua char, pet, dong doi, quai.

Phan tich tu cac packet S2C:
  - 0x0b: full stats 1 entity (HP/SP max+cur)
  - 0x33: cap nhat HP/SP theo luot (block 03 02 = char, 03 01 = pet)
  - 0x0c: thong tin quai luc vao tran
"""
import struct

# Stat type trong 0x33 / 0x0b
T_HP_CUR = 0x19
T_SP_CUR = 0x1A
T_HP_MAX = 0xCD


class Unit:
    def __init__(self, name=""):
        self.name = name
        self.hp = 0
        self.hp_max = 0
        self.sp = 0
        self.sp_max = 0

    @property
    def hp_pct(self):
        return self.hp / self.hp_max if self.hp_max else 1.0

    def __repr__(self):
        return f"{self.name}(HP={self.hp}/{self.hp_max} SP={self.sp}/{self.sp_max})"


class BattleState:
    def __init__(self):
        self.char = Unit("char")
        self.pet = Unit("pet")
        self.self_entity = None   # entity 8 byte cua nhan vat minh (set tu client)
        self.skills_char = set()  # skill ID char co (tu 0x28 login)
        self.skills_pet  = set()  # skill ID pet co (tu 0x28 login)
        self.my_atype = 3         # atype = vi tri formation cua minh (leader o giua)
        self.label = ""           # nhan account (de tao key dieu phoi heal)
        self.pet_skills = set()   # TAT CA skill cua pet dang dung (tra tu pets.json theo pet_id)
        self.active_pet_id = None # id pet dang dung (tu S2C 0x13)
        self.pet_boss_skill = None # skill danh don cua pet dung khi danh BOSS (pets.json boss_skill)
        self.boss_mode = False    # True = dang trong dungeon danh boss -> pet dung boss_skill (danh don)
        # dong doi trong party (entity_id -> Unit), khong gom char/pet cua minh
        self.allies = {}
        self.mobs = []  # list HP_max cua quai (theo thu tu xuat hien)
        self.in_battle = False
        # vi tri quai con song (slot B2) - decode tu 0x33; dung lam target combat
        self.enemy_slots = []          # vd [2] = co 1 quai o slot 2
        self.enemy_hp = {}             # slot -> curHP
        self.self_slot = None          # B2 (vi tri tran) cua minh - tu 0x0b battle (entity-based)

    def reset_battle(self):
        self.mobs = []
        self.in_battle = False

    def reset_enemies(self):
        """Xoa HP/slot quai (goi luc battle moi bat dau, tranh dinh quai tran cu)."""
        self.enemy_hp = {}
        self.enemy_slots = []

    # ---- parse 0x33 (stat update theo luot) ----
    def update_0x33(self, pkt: bytes):
        """Block 7 byte: [00][B1][B2][type][val 2B LE][00].
          B1: 3=nhan vat, 2=pet, 0=QUAI(dich). B2: slot/vi tri (1..n).
          type: 0x19=curHP, 0x1a=SP, 0xcd=maxHP.
        -> lay danh sach quai (B1=0, curHP>0) de target; cap nhat HP/SP char/pet cua minh.
        """
        body = pkt[7:] if len(pkt) > 7 and pkt[6] == 0x33 else pkt
        # bo 2 byte prefix (01 00)
        p = body[2:]
        groups = {}  # (B1,B2) -> {type: val}
        i = 0
        while i + 7 <= len(p):
            a, b1, b2, tt = p[i], p[i + 1], p[i + 2], p[i + 3]
            # b1: 0=quai hang truoc, 1=quai hang sau, 2=pet, 3=nhan vat
            if a == 0x00 and b1 in (0x00, 0x01, 0x02, 0x03) and tt in (T_HP_CUR, T_SP_CUR, T_HP_MAX):
                val = int.from_bytes(p[i + 4:i + 6], "little")
                groups.setdefault((b1, b2), {})[tt] = val
                i += 7
            else:
                i += 1
        # QUAI = b1 in (0,1): hang truoc b1=0, hang sau b1=1; cot = b2.
        # Vi tri noi bo = b1*10 + b2 -> hang=pos//10, cot=pos%10 (gui combat: b=hang, target=cot)
        saw_enemy_group = False
        for (b1, b2), d in groups.items():
            if b1 in (0x00, 0x01):
                saw_enemy_group = True
                pos = b1 * 10 + b2
                self.enemy_hp[pos] = d.get(T_HP_CUR, 0)
        if saw_enemy_group:
            # enemy_slots = TAT CA slot con song theo enemy_hp TICH LUY (khong chi goi nay).
            # Tranh mat con khong bi danh trong turn (vd giet 1-2-3 con con o slot 7 van song).
            self.enemy_slots = sorted(s for s, hp in self.enemy_hp.items() if hp > 0)
        # self_slot xac dinh tu 0x0b battle (entity-based, o client) hoac roster. KHONG dua HP.
        # Doc HP/SP char+pet cua minh theo slot (uu tien roster -> chinh xac, KHONG can 0x0b)
        if self.self_slot is not None:
            pd = groups.get((0x02, self.self_slot))
            if pd:
                if T_HP_MAX in pd: self.pet.hp_max = pd[T_HP_MAX]
                if T_HP_CUR in pd: self.pet.hp = pd[T_HP_CUR]
                if T_SP_CUR in pd: self.pet.sp = pd[T_SP_CUR]
            cd = groups.get((0x03, self.self_slot))
            if cd:
                if T_HP_MAX in cd: self.char.hp_max = cd[T_HP_MAX]
                if T_HP_CUR in cd: self.char.hp = cd[T_HP_CUR]
                if T_SP_CUR in cd: self.char.sp = cd[T_SP_CUR]
        # Cap nhat HP TAT CA dong doi (char B1=3, pet B1=2 cua moi slot) -> de quyet dinh hoi mau
        for (b1, b2), d in groups.items():
            if b1 in (0x02, 0x03) and (T_HP_CUR in d or T_HP_MAX in d):
                u = self.allies.get((b1, b2))
                if u is None:
                    u = Unit(f"{'char' if b1==3 else 'pet'}{b2}")
                    self.allies[(b1, b2)] = u
                if T_HP_MAX in d: u.hp_max = d[T_HP_MAX]
                if T_HP_CUR in d: u.hp = d[T_HP_CUR]
                u.slot = b2

    # ---- parse 0x0b (full stats char/pet) ----
    def update_0x0b(self, pkt: bytes):
        """Char/pet: [self_entity] [02 00=char / 02 01=pet] [HP_max][SP_max][HP_cur][SP_cur] (4B/field)."""
        if not self.self_entity:
            return
        idx = pkt.find(self.self_entity)
        if idx < 0:
            return
        off = idx + 8
        if off + 2 + 16 > len(pkt):
            return
        slot = pkt[off:off + 2]
        if slot == b"\x02\x00":
            who = self.char
        elif slot == b"\x02\x01":
            who = self.pet
        else:
            return
        hp_max = struct.unpack_from("<I", pkt, off + 2)[0]
        if not (0 < hp_max < 1_000_000):   # loc gia tri rac
            return
        who.hp_max = hp_max
        who.sp_max = struct.unpack_from("<I", pkt, off + 6)[0]
        who.hp = struct.unpack_from("<I", pkt, off + 10)[0]
        who.sp = struct.unpack_from("<I", pkt, off + 14)[0]

    def lowest_hp_ally(self):
        """Unit (char/pet bat ky thanh vien) thap mau nhat - CHI con SONG (hp>0). None neu khong co.
        Con HP=0 da CHET -> bo qua (hoi mau vo dung)."""
        alive = [u for u in self.allies.values() if u.hp_max > 0 and u.hp > 0]
        if not alive:
            return None
        return min(alive, key=lambda u: u.hp_pct)

    def any_ally_low(self, threshold: float):
        """Co thanh vien nao (char/pet) HP% <= threshold + CON SONG (hp>0) khong (gom ca minh).
        Con HP=0 da CHET -> KHONG tinh (hoi mau vo dung)."""
        for u in self.allies.values():
            if u.hp_max > 0 and u.hp > 0 and u.hp_pct <= threshold:
                return True
        return False
