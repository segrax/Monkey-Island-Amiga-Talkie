"""Portable linked glyph replay/parser tests, using only synthetic NGP2 fonts."""
from pathlib import Path
import hashlib,json,struct
from glyph_fixture import (Fixture,make_font,resign,META,IMAGE,artifact_dir,
                           OWNER,PRIMARY,MASK,FONT,T,unicorn)

def main():
    specs=[]
    for h in (1,9,15,103):
        for w in range(2,10):
            specs.append((w,h,lambda x,y,w=w,h=h:(x+3*y+w+h)&3))
    font,data,records=make_font(specs)
    f=Fixture(font,data);f.load();cases=0
    for i,(off,n,code) in enumerate(records):
        for phase in range(8):
            for mode in (0,1):
                seed=i*16+phase*2+mode
                f.setup(off,phase,mode);assert f.lookup(),(i,phase,mode)
                expected=f.draw(True,seed)
                f.setup(off,phase,mode);actual=f.draw(False,seed)
                assert expected==actual,(i,phase,mode,[k for k,(a,b) in enumerate(zip(expected,actual)) if a!=b])
                cases+=1
    off=records[0][0]
    # Corrupt checksummed structural fields, recomputing checksum independently.
    negatives=[]
    def put(a,p,v,n):a[p:p+n]=v.to_bytes(n,'big')
    mutations=[
        ('version',lambda a:put(a,4,3,2)),('header size',lambda a:put(a,6,34,2)),
        ('total zero',lambda a:put(a,8,0,4)),('total odd',lambda a:put(a,8,len(a)|1,4)),
        ('total capacity',lambda a:put(a,8,64550,4)),
        ('font id',lambda a:put(a,12,3,2)),('count257',lambda a:put(a,14,257,2)),
        ('index',lambda a:put(a,16,38,4)),('source extent',lambda a:put(a,20,len(a)+2,4)),
        ('source size',lambda a:put(a,24,len(a),4)),('code extent',lambda a:put(a,28,len(a),4)),
        ('source offset',lambda a:put(a,36,65535,2)),('source span',lambda a:put(a,38,65535,2)),
        ('code before',lambda a:put(a,40,36,4)),('code beyond',lambda a:put(a,40,len(a),4)),
        ('code odd',lambda a:put(a,40,int.from_bytes(a[40:44],'big')|1,4)),
        ('code zero',lambda a:put(a,44,0,2)),('reserved',lambda a:put(a,46,1,2)),
        ('duplicate directory',lambda a:a.__setitem__(slice(48,50),a[36:38])),
    ]
    for name,mut in mutations:
        a=bytearray(data);mut(a);a=resign(a)
        q=Fixture(font,a);q.load();q.setup(off);assert not q.lookup(),name
        assert q.closed==1,name
        negatives.append(name)
    for name,asset,missing in (
            ('missing',data,True),('short header',data[:35],False),
            ('short body',data[:-2],False),('trailing',data+b'X',False),
            ('checksum',data[:100]+bytes((data[100]^1,))+data[101:],False)):
        q=Fixture(font,asset,missing);q.load();q.setup(off);assert not q.lookup(),name
        assert q.closed==(0 if missing else 1),name
        negatives.append(name)

    guards=[
        ('owner missing',lambda q:T.put32(q.c,q.g+0x27a8+FONT*4,0)),
        ('owner id',lambda q:q.c.mem_write(OWNER+5,b'\0')),
        ('owner extent',lambda q:q.c.mem_write(OWNER,struct.pack('<I',len(font)+21))),
        ('source mutation',lambda q:q.c.mem_write(OWNER+6+off+4,bytes((font[off+4]^1,)))),
        ('initial latch',lambda q:q.c.mem_write(q.g+0x6f40,b'\0\xff')),
        ('primary id',lambda q:q.c.mem_write(PRIMARY+5,b'\x05')),
        ('mask id',lambda q:q.c.mem_write(MASK+5,b'\x05')),
        ('source destination alias',lambda q:T.put32(q.c,q.g+0x5c1e,OWNER+6)),
        ('stack dirty alias',lambda q:T.put32(q.c,q.g+0x5c26,T.STACK)),
        ('invalid phase',lambda q:q.c.mem_write(q.g+0x6f5c,b'\x03')),
        ('vertical clipping',lambda q:q.c.mem_write(q.g+0x6f50,b'\0\x0d')),
        ('lease revoke',lambda q:q.call('_nv_costume_cache_begin',(0xffffffff,))),
        ('global remap',lambda q:T.put32(q.c,q.t.addr('_nv_control')+16,0xdff000)),
        ('ART arena remap',lambda q:T.put32(q.c,q.t.addr('_nv_art'),PRIMARY)),
    ]
    for name,mut in guards:
        q=Fixture(font,data);q.load();q.setup(off);assert q.lookup()
        mut(q);assert not q.lookup(),name
        negatives.append(name)

    # Same-address reuse still compares source bytes even on a warm memo.
    q=Fixture(font,data);q.load();q.setup(off);assert q.lookup()
    calls=[]
    hook=q.c.hook_add(unicorn.UC_HOOK_CODE,lambda c,pc,n,_:calls.append(pc) if pc==q.t.addr('_nv_art_runtime_overlap') else None)
    assert q.lookup() and not calls
    q.c.mem_write(PRIMARY,struct.pack('<I',64005));assert q.lookup();assert len(calls)==3
    calls.clear();q.c.mem_write(MASK,struct.pack('<I',8005));assert q.lookup();assert len(calls)==3
    q.c.hook_del(hook)
    q.c.mem_write(OWNER+6+off+4,bytes((font[off+4]^1,)));assert not q.lookup()

    # Fifteen keys share the exact initial hash slot and occupy a long chain.
    offsets=[1028+i*4096 for i in range(15)]
    cf,cd,cr=make_font([(2,1,lambda x,y:0)]*15,offsets)
    q=Fixture(cf,cd);q.load();codes=[]
    for i,(at,n,code) in enumerate(cr):
        q.setup(at);codes.append(q.lookup());assert codes[-1]
        for phase in range(8):
            q.setup(at,phase,i&1);expected=q.draw(True,i*8+phase)
            q.setup(at,phase,i&1);assert expected==q.draw(False,i*8+phase)
            cases+=1
    assert len(set(codes))==15
    # Valid in-bounds header absent from directory, with occupied initial slot.
    missing=1029
    assert (missing>>3)&511 == (offsets[0]>>3)&511
    q.c.mem_write(OWNER+6+missing,bytes((2,1,0,0,0)))
    q.setup(offsets[0]);T.put32(q.c,q.g+0x6f48,OWNER+6+missing+5)
    q.c.mem_write(q.g+0x6f40,b'\0\0');assert not q.lookup()

    # Successful repeated load and stop/restart revoke/replace lease safely.
    q=Fixture(font,data);q.load();q.setup(off);assert q.lookup()
    q.load();q.setup(off);assert q.lookup()
    q.call('_nv_costume_cache_stop');assert not q.lookup()
    q.call('_nv_costume_cache_start');q.load();q.setup(off);assert q.lookup()
    for field in (0,56,60):
        q=Fixture(font,data)
        T.put32(q.c,q.t.addr('_nv_costume_cache')+field,1)
        q.load();q.setup(off);assert not q.lookup(),('busy lease',field)
        T.put32(q.c,q.t.addr('_nv_costume_cache')+field,0)
        q.load();q.setup(off);assert q.lookup()
    result=dict(pass_=True,module_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),
                synthetic_only=True,owned_font_assets=False,draw_cases=cases,
                glyph_dimensions=32,phases=8,modes=2,all_GPR_CCR_globals_frame_dirty_palette_exact=True,
                negative_cases=negatives,hash_collision_keys=15,warm_memo_cases=4,lifecycle=True)
    output=artifact_dir('glyph')/'glyph-test-results.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
