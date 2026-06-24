import struct, sys
from collections import Counter

def load(fn):
    d=open(fn,'rb').read()
    linktype=struct.unpack('<I',d[20:24])[0]
    L=16 if linktype==113 else 14
    off=24; pkts=[]
    while off+16<=len(d):
        _,_,incl,_=struct.unpack('<IIII',d[off:off+16]); off+=16
        pkts.append(d[off:off+incl]); off+=incl
    xor=lambda b: bytes(x^0xAD for x in b)
    c2s=b''; s2c=b''
    for p in pkts:
        if len(p)<L+20 or p[L+9]!=6: continue
        ihl=(p[L]&0x0f)*4; t=L+ihl; doff=(p[t+12]>>4)*4
        pay=p[t+doff:]
        if not pay: continue
        sp=struct.unpack('>H',p[t:t+2])[0]; dp=struct.unpack('>H',p[t+2:t+4])[0]
        if dp==6614: c2s+=xor(pay)
        elif sp==6614: s2c+=xor(pay)
    return c2s,s2c

def frames(s):
    i=0;o=[]
    while i+7<=len(s):
        if s[i]==0xc0 and s[i+1]==0x91:
            ln=struct.unpack('<H',s[i+2:i+4])[0]
            if 7<=ln<=65535 and i+ln<=len(s): o.append((s[i+6],s[i+7:i+ln])); i+=ln; continue
        i+=1
    return o

if __name__=="__main__":
    fn=sys.argv[1] if len(sys.argv)>1 else 'digioi_new.pcap'
    c2s,s2c=load(fn)
    cf=frames(c2s)
    print('C2S opcodes:', dict(Counter(hex(o) for o,_ in cf)))
    print('Tong C2S frames:', len(cf))
    print('--- Chuoi C2S (op: body) ---')
    for op,b in cf:
        print(f'  0x{op:02x} {b.hex()}')
