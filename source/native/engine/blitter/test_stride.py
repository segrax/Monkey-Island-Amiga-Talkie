"""Original and actual linked blitter-stride tests with synthetic input only."""
import sys, json, hashlib, random, struct, importlib.util
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
from paths import engine_build, artifact_dir
spec = importlib.util.spec_from_file_location('cache_fixture', ROOT/'engine/scaling/test_cache.py')
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
R = T.R
SITES = {0x15c52: ('dbc5','dac5'), 0x15c54: ('ddc5','dcc5'),
         0x15c56: ('d3c5','d2c5'), 0x15c58: ('d5c5','d4c5'),
         0x15c6a: ('d7c6','d6c6'), 0x15c6c: ('d9c6','d8c6')}
ORIGINAL = ROOT/'data/original/Monkey_Island'
r = T.reader(ORIGINAL)
body = next(h['data'] for h in r.hunks if h.get('hunk_no') == 0 and 'data' in h)
for pc, (old, new) in SITES.items():
    assert body[pc:pc+2] == bytes.fromhex(old), (hex(pc), body[pc:pc+2].hex(), old)

def run(ccr, high5, high6, flip, busy, patched, seed, actual=False):
    image=engine_build()/'module/Monkey_Talkie_Test'
    a = T.Guest(image if actual else ORIGINAL, 0)
    c, g, base = a.cpu, a.g, a.bases[0]
    if patched:
        for pc, (old, new) in SITES.items():
            c.mem_write(base+pc, bytes.fromhex(new))
    T.put32(c, g+0x706e, 0x700000)
    T.put32(c, g+0x7072, 0x710000)
    c.mem_write(g+0x16f4, bytes([flip]))
    # Twenty independently dirty/non-dirty columns, including both screen edges.
    rng = random.Random(seed)
    lo = [rng.randrange(0, 199) if i % 3 else 200 for i in range(20)]
    hi = [min(199, y+rng.randrange(0, 200-y)) if y < 200 else 0xffff for y in lo]
    for i, (y0, y1) in enumerate(zip(lo, hi)):
        c.mem_write(g+0x707a+2*i, struct.pack('>H', y0))
        c.mem_write(g+0x70a2+2*i, struct.pack('>H', y1))
    values = [rng.randrange(1 << 32) for _ in T.REGS]
    values[5] = (high5 << 16) | 0x7654
    values[6] = (high6 << 16) | 0x1234
    values[12] = g
    values[15] = T.STACK
    # Start both caller stack regions alike before checking saved registers and
    # the bounded callee stack writes.
    c.mem_write(T.STACK-64, bytes(128))
    c.reg_write(R.UC_M68K_REG_SR, ccr)
    for reg, value in zip(T.REGS, values):
        c.reg_write(reg, value)
    hardware, launches = [], []
    remaining = [0]
    def write(cpu, access, p, size, value, unused):
        if 0xdff000 <= p < 0xe00000:
            hardware.append((p, size, value))
        if p == 0xdff058:
            launches.append((T.u32(c, 0xdff048), T.u32(c, 0xdff054), value))
            remaining[0] = busy
    def instruction(cpu, pc, size, unused):
        if pc == base+0x15c7a:
            c.mem_write(0xdff002, b'\x40\x00' if remaining[0] else b'\x00\x00')
            remaining[0] = max(0, remaining[0]-1)
    c.hook_add(T.unicorn.UC_HOOK_MEM_WRITE, write)
    c.hook_add(T.unicorn.UC_HOOK_CODE, instruction)
    a.call(base+0x15b9c)
    # Independent intended address oracle: positive fixed column/plane strides.
    source, destination = ((0x710000, 0x700000) if flip else (0x700000, 0x710000))
    expected = [(source+2*x+40*y+8000*plane,
                 destination+2*x+40*y+8000*plane, ((z-y)<<6)+1)
                for x, (y,z) in enumerate(zip(lo,hi)) if y <= z and y < 200
                for plane in range(5)]
    if patched or actual or (high5 == high6 == 0):
        assert launches == expected
    for index in (2,3,4,5,6,10,11,12,13,14):
        assert c.reg_read(T.REGS[index]) == values[index], index
    assert c.reg_read(R.UC_M68K_REG_A7) == T.STACK+4
    # Store real CCR, including X, through an executed MOVE SR instruction.
    c.mem_write(T.STOP, bytes.fromhex('40f900e00100'))
    c.emu_start(T.STOP, T.STOP+6, count=1)
    regs = [c.reg_read(reg) for reg in T.REGS]
    # Caller values are deliberately different between trials, not callee results.
    regs[5] &= 0xffff
    regs[6] &= 0xffff
    stack = bytearray(c.mem_read(T.STACK-64, 128))
    # Saved caller D5/D6 words necessarily retain their differing upper halves.
    stack[64-28:64-26] = b'\0\0'
    stack[64-24:64-22] = b'\0\0'
    return (regs, bytes(c.mem_read(T.STOP+0x100,2)), hardware,
            bytes(c.mem_read(g,29312)), bytes(stack)), launches

def main():
    image=engine_build()/'module/Monkey_Talkie_Test'
    linked_reader=T.reader(image)
    linked_body=next(h['data'] for h in linked_reader.hunks if h.get('hunk_no')==0 and 'data' in h)
    expected_body=bytearray(body[0x15b9c:0x15c84])
    for at,(old,new) in SITES.items():
        expected_body[at-0x15b9c:at-0x15b9c+2]=bytes.fromhex(new)
    assert linked_body[0x15b9c:0x15c84]==expected_body
    count = 0
    rng = random.Random(0x15b9c)
    for ccr in range(32):
        for flip in (0,1):
            for busy in (0,3):
                seed = ccr*4+flip*2+bool(busy)
                baseline,_ = run(ccr,0,0,flip,busy,False,seed)
                for h5,h6 in ((0,0),(0xffff,0xffff),(rng.randrange(65536),rng.randrange(65536))):
                    candidate,_ = run(ccr,h5,h6,flip,busy,True,seed)
                    assert candidate == baseline, (ccr,flip,busy,h5,h6)
                    linked,_ = run(ccr,h5,h6,flip,busy,False,seed,actual=True)
                    assert linked == baseline, ('linked',ccr,flip,busy,h5,h6)
                    count += 1
    _, good = run(0,0,0,0,0,False,2)
    _, bad = run(0,0,0xffff,0,0,False,2)
    assert good != bad, 'Regression fixture must expose inherited upper-word bug'
    report = dict(cases=count, sites={hex(k):v for k,v in SITES.items()},
                  original_sha256=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
                  body_sha256=hashlib.sha256(body[0x15b9c:0x15c84]).hexdigest(),
                  ordered_hardware_writes=True, independent_address_oracle=True,
                  mock_busy_polls=[0,3], original_high_garbage_regression=True,
                  production_adoption=False)
    (artifact_dir('blitter')/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
