"""Tao goi auth TCP (opcode 0x01). Copy tu bot/auth.py, doi sang dung protocol.encode
(native header+xor qua bot_native_bridge) thay vi tu dung frame + xor thuan Python.

Cau truc (xac nhan tu 2 lan capture, xem bot/auth.py):
  prefix(13B) + UTF16LE(user_id) + UTF16LE('f') + UTF16LE(access_token)
"""
from .protocol import OP_LOGIN


def build_auth_packet(user_id: str, access_token: str, server_id: int = 1) -> bytes:
    """Tra ve packet auth da encode (header+xor qua native), san sang gui.
    server_id theo server (Trieu Van=1, Tao Thao=2)."""
    from . import protocol
    prefix = bytes([0x00, 0x00, 0x02, 0x01, server_id & 0xFF,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x19, 0x14, 0x00])
    cred = (user_id + "f" + access_token).encode("utf-16-le")
    return protocol.encode(OP_LOGIN, prefix + cred)   # protocol.encode tu goi native (header+xor)
