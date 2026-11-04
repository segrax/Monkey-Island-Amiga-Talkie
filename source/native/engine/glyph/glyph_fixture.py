"""Synthetic NGP2 data and linked guest fixture; no captured font inputs."""
from pathlib import Path
import json, os, random, struct, sys

SOURCE = Path(os.environ.get('NATIVE_PROJECT_ROOT', Path(__file__).resolve().parents[2]))
sys.path[:0] = [str(SOURCE/'engine'), str(SOURCE/'engine/scaling'), str(SOURCE/'tools/python')]
from paths import engine_build, artifact_dir
import test_cache as T
import unicorn
from unicorn import m68k_const as R

BUILD = engine_build()
MODULE = BUILD/'module'
META = json.loads((MODULE/'module.json').read_text())
IMAGE = MODULE/'Monkey_Talkie_Test'
OWNER, PRIMARY, MASK = 0x900000, 0xa00000, 0xb00000
FONT = 2

def checksum(data):
    """Independent unbounded-integer Fletcher32, checksum field treated as0."""
    b = bytearray(data)
    b[32:36] = bytes(4)
    a = s = 65535
    for i in range(0, len(b), 2):
        a += int.from_bytes(b[i:i+2], 'big')
        s += a
    return ((s % 65535 or 65535) << 16) | (a % 65535 or 65535)

def resign(data):
    data[32:36] = checksum(data).to_bytes(4, 'big')
    return bytes(data)

def compile_pixels(rows):
    """Emit palette-relative stores from independent integer pixel rows."""
    out = bytearray()
    for y, row in enumerate(rows):
        mask = sum(0x8000 >> x for x, color in enumerate(row) if color)
        if not mask:
            continue
        out += struct.pack('>13H', 0x4a44, 0x6616, 0x3c3c, mask,
                           0xe66e, 0xe05e, 0x8d2c, y*40,
                           0xe05e, 0x4a06, 0x6704, 0x8d2c, y*40+1)
        for x, color in enumerate(row):
            if color:
                out += struct.pack('>3H', 0x116a, color, y*320+x)
    return bytes(out)+bytes.fromhex('4ed5')

def make_font(specs, offsets=None):
    """spec=(width,height,pattern), each pattern returns a2bit source color."""
    font = bytearray(1028)
    font[:4] = bytes((2, 9, 0, 1))
    records = []
    for i, (w, h, pattern) in enumerate(specs):
        assert 2 <= w <= 9 and 1 <= h and (h-1)*320+w-1 <= 32767
        off = offsets[i] if offsets else len(font)
        n = 5+w*h//4
        if len(font) < off+n:
            font.extend(bytes(off+n-len(font)))
        font[4+(32+i)*4:8+(32+i)*4] = off.to_bytes(4, 'little')
        font[off:off+4] = bytes((w, h, i&7, (-i)&255))
        rows = [[pattern(x,y)&3 for x in range(w)] for y in range(h)]
        for pixel in range(w*h):
            font[off+4+pixel//4] |= rows[pixel//w][pixel%w] << (6-2*(pixel%4))
        records.append((off, n, compile_pixels(rows)))
    return bytes(font), make_block(bytes(font), records), records

def make_block(font, records):
    records = sorted(records)
    source = 36+12*len(records)
    code = (source+len(font)+1)&~1
    size = code+sum(len(r[2]) for r in records)
    assert size <= 64548 and not size&1
    data = bytearray(size)
    struct.pack_into('>4sHHIHHIIII', data, 0, b'NGP2',2,36,size,FONT,len(records),36,source,len(font),code)
    data[source:source+len(font)] = font
    for i, (off, n, program) in enumerate(records):
        struct.pack_into('>HHIHH', data,36+12*i,off,n,code,len(program),0)
        data[code:code+len(program)] = program
        code += len(program)
    return resign(data)

class Fixture:
    def __init__(self,font,data,missing=False,layout=0):
        self.t=T.Guest(IMAGE,layout,META)
        self.c=self.t.cpu;self.g=self.t.g;self.font=font;self.data=data
        self.cursor=0;self.reads=[];self.closed=0;self.opened=0
        c=self.c
        T.put32(c,self.t.addr('_nv_control')+12,self.t.bases[0])
        c.mem_write(OWNER,struct.pack('<I',len(font)+20)+bytes((4,10+FONT))+font+bytes(14))
        T.put32(c,self.g+0x27a8+4*FONT,OWNER)
        for base,n,id in ((PRIMARY,64006,1),(MASK,8006,9)):
            c.mem_write(base,struct.pack('<I',n)+bytes((4,id))+bytes(n-6))
        T.put32(c,self.g+0x2784,PRIMARY);T.put32(c,self.g+0x27a4,MASK)
        io={self.t.addr('_nv_glyph_'+name):name for name in ('open','read','close')}
        def hook(c,pc,size,_):
            if pc not in io:return
            sp=c.reg_read(R.UC_M68K_REG_A7)
            args=[T.u32(c,sp+4*i) for i in (1,2,3)]
            name=io[pc];result=0
            if name=='open':
                assert bytes(c.mem_read(args[0],18)).split(b'\0')[0]==b'native-font-2.dat'
                self.cursor=0;self.opened+=1;result=0 if missing else 1
            elif name=='read':
                n=min(args[2],len(self.data)-self.cursor)
                self.reads.append(n)
                if n:c.mem_write(args[1],self.data[self.cursor:self.cursor+n])
                self.cursor+=n;result=n
            else:self.closed+=1
            c.reg_write(R.UC_M68K_REG_D0,result)
            c.reg_write(R.UC_M68K_REG_PC,T.u32(c,sp));c.reg_write(R.UC_M68K_REG_A7,sp+4)
        c.hook_add(unicorn.UC_HOOK_CODE,hook)
    def call(self,name,args=()):
        self.t.call(self.t.addr(name) if isinstance(name,str) else name,args)
        return self.c.reg_read(R.UC_M68K_REG_D0)
    def load(self):
        self.call('_nv_glyph_load',(FONT,T.STACK))
    def setup(self,off,phase=0,mode=0):
        c,g=self.c,self.g;w,h=self.font[off:off+2]
        c.mem_write(PRIMARY+6,bytes((0x5a,))*64000);c.mem_write(MASK+6,bytes((0x55,))*8000)
        for a,v,n in ((0x5c1e,PRIMARY+6+1234,4),(0x5c22,MASK+6,4),(0x5c26,MASK+17,4),
                      (0x6f48,OWNER+6+off+5,4),(0x6f58,w,2),(0x6f5a,h,1),
                      (0x6f54,13,2),(0x6f50,200,2),(0x6f5c,128>>phase,1),
                      (0x6f5f,2,1),(0x6f60,6,1),(0x6f61,192,1),(0x6f3a,8,2),
                      (0x6f40,self.font[off+4],2),(0x5d40,mode,2),(0x66e9,0,1)):
            c.mem_write(g+a,v.to_bytes(n,'big'))
        c.mem_write(g+0x5920,bytes((7,64,128,255)))
    def lookup(self):return self.call('_nv_glyph_lookup',(T.STACK,))
    def draw(self,reference,seed):
        c=self.c;rng=random.Random(seed)
        values=[rng.getrandbits(32) for _ in T.REGS];values[-1]=T.STACK
        c.reg_write(R.UC_M68K_REG_SR,seed&31)
        for reg,value in zip(T.REGS,values):c.reg_write(reg,value)
        reads=[]
        def palette(c,access,at,n,value,_):
            if self.g+0x5920<=at<self.g+0x5924:reads.append((at-self.g-0x5920,n))
        hook=c.hook_add(unicorn.UC_HOOK_MEM_READ,palette)
        c.mem_write(T.STACK,struct.pack('>I',T.STOP))
        pc=self.t.addr('_engine_font2') if reference else self.t.bases[0]+0x16020
        c.emu_start(pc,T.STOP,count=3000000);c.hook_del(hook)
        assert c.reg_read(R.UC_M68K_REG_PC)==T.STOP
        c.mem_write(T.STOP,bytes.fromhex('40f900e00100'))
        c.emu_start(T.STOP,T.STOP+6,count=1)
        return (tuple(c.reg_read(reg) for reg in T.REGS),bytes(c.mem_read(T.STOP+256,2)),
                bytes(c.mem_read(self.g,29312)),bytes(c.mem_read(PRIMARY,64006)),
                bytes(c.mem_read(MASK,8006)),reads)
