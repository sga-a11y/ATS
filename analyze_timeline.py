import struct, sys

def load_ordered(fn):
    d=open(fn,'rb').read()
    linktype=struct.unpack('<I',d[20:24])[0]
    L=16 if linktype==113 else 14
    off=24; pkts=[]
    while off+16<=len(d):
        _,_,incl,_=struct.unpack('<IIII',d[off:off+16]); off+=16
        pkts.append(d[off:off+incl]); off+=incl
    xor=lambda b: bytes(x^0xAD for x in b)
    # reassemble per direction but emit frames in packet order
    bufs={'C2S':b'','S2C':b''}
    events=[]
    def emit(dirn):
        s=bufs[dirn]; i=0
        while i+7<=len(s):
            if s[i]==0xc0 and s[i+1]==0x91:
                ln=struct.unpack('<H',s[i+2:i+4])[0]
                if 7<=ln<=2000 and i+ln<=len(s):
                    events.append((dirn,s[i+6],s[i+7:i+ln])); i+=ln; continue
            i+=1
        bufs[dirn]=s[i:]
    for p in pkts:
        if len(p)<L+20 or p[L+9]!=6: continue
        ihl=(p[L]&0x0f)*4; t=L+ihl; doff=(p[t+12]>>4)*4
        pay=p[t+doff:]
        if not pay: continue
        sp=struct.unpack('>H',p[t:t+2])[0]; dp=struct.unpack('>H',p[t+2:t+4])[0]
        if dp==6614: bufs['C2S']+=xor(pay); emit('C2S')
        elif sp==6614: bufs['S2C']+=xor(pay); emit('S2C')
    return events

if __name__=="__main__":
    fn=sys.argv[1] if len(sys.argv)>1 else 'digioi_new.pcap'
    for dirn,op,b in load_ordered(fn):
        if op==0x0a: continue  # bo heartbeat
        h=b.hex()
        if len(h)>80: h=h[:80]+'..'
        print(f'{dirn} 0x{op:02x} len={len(b):<3} {h}')
