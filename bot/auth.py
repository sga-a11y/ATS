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
# 00 00 | 02 01 01 00 00 00 00 00 | 19 14 00
_PAYLOAD_PREFIX = bytes.fromhex("000002010100000000001914") + b"\x00"


def build_auth_packet(user_id: str, access_token: str) -> bytes:
    """Tra ve packet auth da XOR, san sang gui."""
    cred = (user_id + "f" + access_token).encode("utf-16-le")
    payload = _PAYLOAD_PREFIX + cred
    total = 7 + len(payload)
    frame = b"\xc0\x91" + struct.pack("<H", total) + b"\x00\x00" + bytes([OP_LOGIN]) + payload
    return xor(frame)
