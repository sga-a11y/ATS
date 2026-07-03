"""Cau noi Python (Chaquopy) -> protocol-native (C++) qua JNI. Python KHONG tu lam XOR/frame
nua - moi thu di qua ProtocolBridge (Kotlin) de mac dinh dung 1 nguon that duy nhat, tranh
lech logic giua 2 ngon ngu (day la lop bao ve chinh cho giao thuc)."""
from java import jclass


def _bridge():
    return jclass("com.tsbot.android.ProtocolBridge")


def encode_frame(opcode: int, payload: bytes) -> bytes:
    result = _bridge().INSTANCE.encodeFrame(opcode, bytearray(payload))
    return bytes(result)


def decode_stream(wire_buf: bytes):
    """Tra ve (list[bytes frame hoan chinh], so byte da tieu thu tu dau wire_buf).

    decodeStream() ben Kotlin tra ve data class DecodeStreamResult (getFrames()/getConsumed())
    thay vi kotlin.Pair - Chaquopy khong proxy on dinh .first()/.second() cua Pair, nhung
    property cua data class (frames/consumed) thi luon truy cap duoc.
    """
    result = _bridge().INSTANCE.decodeStream(bytearray(wire_buf))
    # Chaquopy khong proxy property Kotlin (result.frames) truc tiep tren doi tuong
    # tra ve tu ham external/JNI-backed - phai goi getter kieu Java (getFrames()/getConsumed()).
    frames_list = result.getFrames()
    consumed = result.getConsumed()
    # Dung size()/get(i) thay vi "for f in frames_list": mot so kieu java.util.List
    # (vd Collections$SingletonList khi Kotlin List co 1 phan tu) khong duoc Chaquopy
    # proxy iterable truc tiep, nhung size()/get() luon dung.
    frames = [bytes(frames_list.get(i)) for i in range(frames_list.size())]
    return frames, consumed
