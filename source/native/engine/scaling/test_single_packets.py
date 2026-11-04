"""Check fresh single-pixel packets with palette/output aliasing and exact reads."""
from pathlib import Path

root=Path(__file__).resolve().parents[2]
path=root/'engine/scaling/test_kernels.py'
source=path.read_text()
a=source.index('cases=[]');b=source.index('profiles=[];checks=0',a)
source=source[:a]+"cases=[dict(width=16,height=1,phase=p,sy=s,sx=256,resume=0,ccr=p&31) for p in range(256) for s in (128,256)]\n"+source[b:]
source=source.replace('encoded=stream();','encoded=bytes((color<<4)|1 for color in range(1,16))*1000;')
source=source.replace("mask=bytes(rng.randrange(256)for _ in range(0x8000))","mask=bytes(0x8000)")
source=source.replace("(0x5c16,0x600410,4)","(0x5c16,g+0x5cdd,4)")
source=source.replace('direction=rng.choice((1,65535))','direction=1')
source=source.replace('x=rng.choice((0,1,100,319));y=rng.choice((0,1,100,65535));clip=rng.choice((1,100,256))','x=0;y=0;clip=200')
source=source.replace('or 0x600010<=address and address+size<=0x630010','or 0x600010<=address and address+size<=0x630010 or g+0x5cdb<=address and address+size<=g+0x5cf0')
source=source.replace('assert bytes(cpu.mem_read(g,29312))==glob and ', 'assert ')
source=source.replace('bytes(cpu.mem_read(0x90ee00,0x204))))','bytes(cpu.mem_read(0x90ee00,0x204)),bytes(cpu.mem_read(g,29312)),reads))')
source=source.replace('wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard);','reads=[]\n    def read(uc,access,address,size,value,unused):\n     if g+0x5cdb<=address<g+0x5ceb:reads.append((address-g,size))\n    rh=cpu.hook_add(unicorn.UC_HOOK_MEM_READ,read)\n    wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard);')
source=source.replace('cpu.hook_del(wh);cpu.hook_del(ch)','cpu.hook_del(wh);cpu.hook_del(ch);cpu.hook_del(rh)')
source=source.replace("'kernel-validation.json'","'single-packet-validation.json'")
source=source.replace('signed_fullscale_boundaries=True','palette_output_aliases=True,exact_palette_read_addresses_and_sizes=True')
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
