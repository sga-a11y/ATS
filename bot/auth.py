"""Tao goi auth TCP (opcode 0x01).

Cau truc (xac nhan tu 2 lan capture):
  prefix(20B) + UTF16LE(user_id) + UTF16LE('f') + UTF16LE(access_token)

prefix = c0 91 [len] 00 00 01 | 00 00 02 01 01 00 00 00 00 00 | 19 14 00
  - byte[18]=0x14=20 = len(user_id)*2  (user_id 10 chu so)
  - byte[17]=0x19=25 = hang so (token luon dinh dang 51 ky tu)
len duoc tinh lai theo do dai chuoi thuc te.
"""
import struct
from .protocol import xor, OP_LOGIN

# 13 byte payload-prefix sau opcode (truoc chuoi credential)
# 00 00 | 02 01 [SERVER_ID] 00 00 00 00 00 | 19 14 00
# byte thu 5 (index 4) = SERVER ID: Trieu Van=1 (.98), Tao Thao=2 (.99). Sai -> KHONG vao world.


def build_auth_packet(user_id: str, access_token: str, server_id: int = 1) -> bytes:
    """Tra ve packet auth da XOR, san sang gui. server_id theo server (xem servers.json)."""
    prefix = bytes([0x00, 0x00, 0x02, 0x01, server_id & 0xFF,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x19, 0x14, 0x00])
    cred = (user_id + "f" + access_token).encode("utf-16-le")
    payload = prefix + cred
    total = 7 + len(payload)
    frame = b"\xc0\x91" + struct.pack("<H", total) + b"\x00\x00" + bytes([OP_LOGIN]) + payload
    return xor(frame)
