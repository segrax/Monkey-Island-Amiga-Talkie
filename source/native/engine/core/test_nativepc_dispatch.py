"""Original opcode dispatch to each literal resource call; GPL-3.0-or-later."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
fixture = (HERE/'test_context.py').read_text().split('\nput(g+0x19f8,38,1)',1)[0]
cases = [('verb',bytes([0x7a,1,2])+b'Name\0\xff'),
         ('string',bytes([0x27,1,35])+b'Name\0'),
         ('actor',bytes([0x13,1,15])+b'Name\0\xff')]
results = []
for name,bytecode in cases:
    n = {'__file__':str(HERE/'test_context.py'),'__name__':'nativepc_dispatch_fixture'}
    exec(compile(fixture,str(HERE/'test_context.py'),'exec'),n)
    cpu,g,put,sym,bases,r = [n[x] for x in ('cpu','g','put','sym','bases','r')]
    put(g+0x19f8,38,1);put(g+0x19f9,38,1);put(g+0x2024,6,1)
    put(g+0x20ee+12,203,2);put(g+0x20da+6,2,1);put(g+0x5980,200,1)
    put(g+0x5a56,0x600000,4);put(g+0x5a50,0x600040,4)
    cpu.mem_write(0x600040,bytecode)
    seen = []
    def trace(uc,pc,size,data):
        if pc == sym('_nv_resource_begin'):
            sp=uc.reg_read(r.UC_M68K_REG_A7)
            index=int.from_bytes(uc.mem_read(sp+4,4),'big')
            source=int.from_bytes(uc.mem_read(sp+8,4),'big')
            seen.append(dict(index=index,source=source,
                             native_pc=int.from_bytes(uc.mem_read(g+0x66fa,4),'big'),
                             current_pc=int.from_bytes(uc.mem_read(g+0x5a50,4),'big')))
        if pc == bases[0]+0xccca:
            uc.emu_stop()
    cpu.hook_add(n['unicorn'].UC_HOOK_CODE,trace)
    cpu.reg_write(r.UC_M68K_REG_A4,g);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    try:
        cpu.emu_start(bases[0]+0x92a4,0x600000,count=20000)
    except n['unicorn'].UcError:
        print(name,hex(cpu.reg_read(r.UC_M68K_REG_PC)),seen)
        raise
    assert cpu.reg_read(r.UC_M68K_REG_PC)==bases[0]+0xccca,(name,hex(cpu.reg_read(r.UC_M68K_REG_PC)))
    assert len(seen)==1 and seen[0]['source']==0 and seen[0]['native_pc']==0x600041,seen
    assert seen[0]['current_pc']>seen[0]['native_pc']
    # Model only the allocation after entry, then retain the actual captured origin.
    index=seen[0]['index'];put(g+0x2780+4*index,0x600800,4)
    cpu.mem_write(0x600800,b'\0'*6+b'Name\0')
    n['call']('_nv_resource_end')
    put(g+0x5ed0,g+0x5ed4,4)
    put(0x50f004,0x600806,4);n['call']('_nv_conversion_begin')
    cpu.mem_write(g+0x5ed4,b'Name\0');put(g+0x5ed0,g+0x5ed4+4,4)
    n['call']('_nv_conversion_end')
    put(0x50f004,0,4);put(0x50f008,0x600e00,4);put(0x50f00c,256,4)
    n['call']('_nv_provenance_origin')
    origin=bytes(cpu.mem_read(0x600e00,256)).split(b'\0',1)[0].decode()
    assert origin=='r:l:38:203:%d:0' % (seen[0]['current_pc']-0x600000),origin
    result=dict(kind=name,**seen[0],original_dispatch_and_handler_executed=True,origin=origin)
    results.append(result)
report=dict(checks=len(results),results=results,module_sha256=n['meta']['sha256'],
            original92aa_restored=True,limitation='Stops before allocation; pending-site capture is real compiled code, allocation alone is modeled.')
(BUILD / 'nativepc-dispatch-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
