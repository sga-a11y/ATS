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
        # dong doi trong party (entity_id -> Unit), khong gom char/pet cua minh
        self.allies = {}
        self.mobs = []  # list HP_max cua quai (theo thu tu xuat hien)
        self.in_battle = False
        # vi tri quai con song (slot B2) - decode tu 0x33; dung lam target combat
        self.enemy_slots = []          # vd [2] = co 1 quai o slot 2
        self.enemy_hp = {}             # slot -> curHP
        self.self_slot = None          # B2 cua minh (xac dinh qua maxHP pet)

    def reset_battle(self):
        self.mobs = []
        self.in_battle = False

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
            if a == 0x00 and b1 in (0x00, 0x02, 0x03) and tt in (T_HP_CUR, T_SP_CUR, T_HP_MAX):
                val = int.from_bytes(p[i + 4:i + 6], "little")
                groups.setdefault((b1, b2), {})[tt] = val
                i += 7
            else:
                i += 1
        # quai = B1==0. Neu goi nay co liet ke quai -> cap nhat lai danh sach song
        enemies = []
        saw_enemy_group = False
        for (b1, b2), d in groups.items():
            if b1 == 0x00:
                saw_enemy_group = True
                hp = d.get(T_HP_CUR, 0)
                self.enemy_hp[b2] = hp
                if hp > 0:
                    enemies.append(b2)
        if saw_enemy_group:
            self.enemy_slots = sorted(enemies)   # ke ca rong (het quai) -> tranh target o chet
        # xac dinh slot cua minh qua maxHP pet (doc tu 0x0b), roi cap nhat HP/SP
        for (b1, b2), d in groups.items():
            hpmax = d.get(T_HP_MAX)
            if b1 == 0x02 and self.pet.hp_max and hpmax == self.pet.hp_max:
                self.self_slot = b2
                if T_HP_CUR in d: self.pet.hp = d[T_HP_CUR]
                if T_SP_CUR in d: self.pet.sp = d[T_SP_CUR]
        # char cua minh: cung B2 voi pet
        if self.self_slot is not None:
            d = groups.get((0x03, self.self_slot))
            if d:
                if T_HP_MAX in d and not self.char.hp_max:
                    self.char.hp_max = d[T_HP_MAX]
                if T_HP_CUR in d: self.char.hp = d[T_HP_CUR]
                if T_SP_CUR in d: self.char.sp = d[T_SP_CUR]

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
        """Tra ve (target_ref, hp_pct) cua dong doi/pet thap mau nhat. None neu khong co."""
        candidates = [self.pet] + list(self.allies.values())
        alive = [u for u in candidates if u.hp_max > 0]
        if not alive:
            return None
        return min(alive, key=lambda u: u.hp_pct)

    def any_ally_low(self, threshold: float):
        """Co dong doi/pet nao HP% <= threshold khong."""
        for u in [self.pet] + list(self.allies.values()):
            if u.hp_max > 0 and u.hp_pct <= threshold:
                return True
        return False
