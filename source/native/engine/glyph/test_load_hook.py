"""Portable full-register/CCR proof of the actual post-font-load hook."""
import json,random,struct
from glyph_fixture import Fixture,make_font,T,artifact_dir,META

def main():
    font,asset,records=make_font([(2,1,lambda x,y:x+1)])
    for seed in range(32):
        f=Fixture(font,asset);c=f.c
        frame=T.STACK-512;entry_sp=frame-100
        reference=T.STOP+0x800
        c.mem_write(reference,bytes.fromhex('4ced00e0ffec4e5d4e75'))
        rng=random.Random(seed)
        initial=[rng.getrandbits(32) for _ in T.REGS]
        initial[-3]=frame;initial[-1]=entry_sp
        c.mem_write(frame-20,b''.join(struct.pack('>I',rng.getrandbits(32)) for _ in range(3)))
        c.mem_write(frame,struct.pack('>IIH',0x76543210,T.STOP,2))
        def run(pc):
            c.reg_write(T.R.UC_M68K_REG_SR,seed)
            for reg,value in zip(T.REGS,initial):c.reg_write(reg,value)
            c.emu_start(pc,T.STOP,count=5000000)
            assert c.reg_read(T.R.UC_M68K_REG_PC)==T.STOP
            c.mem_write(T.STOP,bytes.fromhex('40f900e00100'))
            c.emu_start(T.STOP,T.STOP+6,count=1)
            return tuple(c.reg_read(reg) for reg in T.REGS),bytes(c.mem_read(T.STOP+256,2))
        expected=run(reference)
        assert expected==run(f.t.bases[0]+0x2508),seed
        assert f.opened==1 and f.closed==1
        f.setup(records[0][0]);assert f.lookup()
    result=dict(pass_=True,cases=32,synthetic_only=True,
                actual_patched_entry='H0+2508',all16_GPR_CCR_SP_exact=True,
                module_sha256=META['sha256'])
    (artifact_dir('glyph')/'load-hook-test-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS:32CCR states, actual font-load epilogue hook, allGPR/SP preserved')

if __name__=='__main__':main()
