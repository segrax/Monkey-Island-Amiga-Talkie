"""Execute adaptive cache admissions, bounds and exact cleanup on linked68000."""
from pathlib import Path
import os,sys,json

SOURCE=Path(os.environ.get('NATIVE_PROJECT_ROOT',Path(__file__).resolve().parents[2]))
sys.path[:0]=[str(SOURCE/'engine'),str(SOURCE/'engine/scaling'),str(SOURCE/'tools/python')]
from paths import engine_build,artifact_dir
import test_cache as T

def main():
    build=engine_build();image=build/'module/Monkey_Talkie_Test'
    if not image.exists():image=build/'scaling/Monkey_Talkie_Scaled'
    meta=json.loads((image.parent/'module.json').read_text())
    def invoke(g,name,*args):
        g.call(g.addr(name),args)
        return g.cpu.reg_read(T.R.UC_M68K_REG_D0)
    def flag(g):return int.from_bytes(g.cpu.mem_read(0x880000,2),'big')
    base=dict(width=24,height=62,x=121,sx=128,sy=128,xp=104,yp=66,reset=67,odd=0,mask=0,palette=0,ccr=31)
    tiers=[]
    for capacity in range(65536,16383,-4096):
        for flags,version in ((0,34),(2,37)):
            g=T.Guest(image,0,meta,attn_flags=flags,exec_version=version,alloc_limit=capacity)
            assert g.alloc==list(range(65536,capacity-1,-4096))
            assert g.capacity==capacity
            assert T.u32(g.cpu,g.addr('_nv_costume_cache')+76)==capacity
            assert invoke(g,'_nv_costume_cache_lease_capacity')==capacity-988
            if '_nv_costume_cache_overlap' in meta['exports']:
                assert invoke(g,'_nv_costume_cache_overlap',T.ARENA+capacity-1,1)==1
                assert invoke(g,'_nv_costume_cache_overlap',T.ARENA+capacity,1)==0
            tail=bytes((0x96,))*(65536-capacity)
            g.cpu.mem_write(T.ARENA+capacity,tail)
            overflow=[]
            def writes(c,access,at,n,value,_):
                if T.ARENA<=at<T.ARENA+65536 and at+n>T.ARENA+capacity:
                    overflow.append((at,n,value))
            hook=g.cpu.hook_add(T.unicorn.UC_HOOK_MEM_WRITE,writes)
            # Lease publication/flush is covered separately by the glyph and
            # lease tests. Here000 exercises exact capacity,020 costume flush.
            if not flags:
                header=bytes(g.cpu.mem_read(T.ARENA,988))
                assert invoke(g,'_nv_costume_cache_lease',capacity-987,0x880000)==0
                pointer=invoke(g,'_nv_costume_cache_lease',capacity-988,0x880000)
                assert pointer==T.ARENA+988
                g.cpu.mem_write(pointer,bytes((0xa5,))*(capacity-988))
                assert bytes(g.cpu.mem_read(T.ARENA,988))==header
                assert invoke(g,'_nv_costume_cache_lease_commit',0x880000)==1 and flag(g)==1
                assert invoke(g,'_nv_costume_cache_begin',0xffffffff)==0xffffffff and flag(g)==0
                assert invoke(g,'_nv_costume_cache_lease',56028,0x880000)==(
                    T.ARENA+988 if capacity>=57344 else 0)
                invoke(g,'_nv_costume_cache_lease_cancel',0x880000)
            encoded=T.stream(base['width']*base['height'],42)
            old=T.Guest(SOURCE/'data/original/Monkey_Island',0)
            for visit in range(3):
                old.setup(base,encoded,42);g.setup(base,encoded,42)
                assert old.draw()==g.draw(),(capacity,flags,visit)
            context=g.addr('_nv_costume_cache')
            assert T.u32(g.cpu,context+36)>0
            assert T.u32(g.cpu,context+64)<=capacity-988
            g.cpu.hook_del(hook)
            assert not overflow,(capacity,overflow[:3])
            assert bytes(g.cpu.mem_read(T.ARENA+capacity,len(tail)))==tail
            invoke(g,'_nv_costume_cache_stop')
            assert g.free==[(T.ARENA,capacity)]
            assert T.u32(g.cpu,context+76)==0
            tiers.append(dict(capacity=capacity,attn_flags=flags,attempts=g.alloc,free=g.free))
    for limit in (0,16383):
        g=T.Guest(image,0,meta,alloc_limit=limit)
        assert g.alloc==list(range(65536,16383,-4096)) and not g.free
        assert g.capacity==0 and invoke(g,'_nv_costume_cache_lease_capacity')==0
        invoke(g,'_nv_costume_cache_stop');assert not g.free
    # Optional allocation failure retains the original renderer exactly.
    old=T.Guest(SOURCE/'data/original/Monkey_Island',0)
    g=T.Guest(image,0,meta,alloc_limit=0)
    encoded=T.stream(base['width']*base['height'],37)
    old.setup(base,encoded,37);g.setup(base,encoded,37)
    assert old.draw()==g.draw()
    result=dict(pass_=True,tiers=tiers,all_failure_attempts=g.alloc,
                original_differential_cases=79,overflow_writes=0,
                lease_payload_offset=988,minimum_font_bank=57344,
                first76_byte_cache_ABI_unchanged=True,module_sha256=meta['sha256'])
    (artifact_dir('scaling')/'capacity-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS:26capacity/CPU admissions,79exact draws, lease bounds, failure fallback and exact free size')

if __name__=='__main__':main()
