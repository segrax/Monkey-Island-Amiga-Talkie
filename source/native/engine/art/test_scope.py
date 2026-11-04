from pathlib import Path
import sys,json,struct,random
HERE=Path(__file__).resolve().parent
helper=HERE/'test_game.py';ns={'__file__':str(helper),'__name__':'batch_fixture'};exec(compile(helper.read_text().split('RESULTS=[]',1)[0],str(helper),'exec'),ns);globals().update({k:v for k,v in ns.items()if not k.startswith('__')})
P=artifact_dir('art')
results=[]
def result(n,**kw):results.append(dict(name=n,**kw));print(n,kw,flush=True)
def bind(f,scope=True):
 c=f.cpu;be32(c,STACK+48,C+0x51F8)
 count=[0];h=c.hook_add(unicorn.UC_HOOK_CODE,lambda *a:count.__setitem__(0,count[0]+1))
 f.call('_nv_art_game_bind',(0,STACK));c.hook_del(h)
 return bool(u16(c,addr('_nv_art_decode_ready'))),count[0]
def arm(f):
 be32(f.cpu,STACK+48,C+0x51F8);f.call('_nv_art_game_scope_begin',(STACK+58,))
f=Fixture();f.setup();arm(f);cold=bind(f);warm=bind(f);assert cold[0]and warm[0]and warm[1]<cold[1]/2,(cold,warm);result('scope cold then warm',cold=cold[1],warm=warm[1])
for label,action in [('cancel',lambda f:f.call('_nv_art_game_scope_cancel')),('room',lambda f:f.call('_nv_art_game_room')),('object',lambda f:f.call('_nv_art_game_object',(STACK,))),('stop',lambda f:f.call('_nv_art_game_stop'))]:
 f=Fixture();f.setup();arm(f);bind(f);action(f);a,n=bind(f)
 assert n>warm[1]+100 or not a,(label,a,n);result('cancels '+label,accepted=a,instructions=n)
for label,change in [('changed globals',lambda c:be32(c,addr('_nv_control')+16,G+2)),('changed code',lambda c:be32(c,addr('_nv_control')+12,C+2))]:
 f=Fixture();f.setup();arm(f);bind(f);change(f.cpu);a,n=bind(f)
 assert n>warm[1]+100 or not a,(label,n)
 result(label,accepted=a,instructions=n)
f=Fixture();f.setup();arm(f);bind(f);be32(f.cpu,STACK+48,C+0xDCAE);f.call('_nv_art_game_bind',(0,STACK));a,n=bind(f);assert n>warm[1]+100;result('alternate saved return cancels',instructions=n)
f=Fixture();f.setup();arm(f);bind(f);f.call('_nv_art_game_bind',(0,STACK+2));a,n=bind(f);assert n>warm[1]+100;result('different bind SP cancels',instructions=n)
for table in(PRIMARY+1000,G+0x1000):
 f=Fixture();f.setup();c=f.cpu;c.mem_write(table,bytes(1024));be32(c,table+ROOM*4,OWNER);be32(c,G+0x2368,table);arm(f);a=bind(f);b=bind(f)
 assert a[0]and b[0]and b[1]>warm[1]+100,(table,a,b);result('mutable table never warms '+hex(table),first=a[1],second=b[1])
# Actual new entry and epilogue hooks, compared with original instructions.
for ccr in range(32):
 states=[]
 for patched in(False,True):
  f=Fixture();f.setup();c=f.cpu;arm(f);bind(f)
  if not patched:c.mem_write(C+0x5104,bytes.fromhex('4e55fff448e73f20'));c.ctl_remove_cache(C+0x5104,C+0x510C)
  rng=random.Random(100+ccr);vals=[rng.getrandbits(32)for _ in REGS];vals[15]=STACK;vals[13]=STACK+0x200
  c.reg_write(R.UC_M68K_REG_SR,0x2000|ccr)
  for r,v in zip(REGS,vals):c.reg_write(r,v)
  c.emu_start(C+0x5104,C+0x510C,count=100000)
  states.append((tuple(c.reg_read(r)for r in REGS),f.regs()[1]))
 assert states[0]==states[1],('entry',ccr,states)
 result('entry ABI CCR '+str(ccr))
 states=[]
 for patched in(False,True):
  f=Fixture();f.setup();c=f.cpu;arm(f);bind(f)
  if not patched:c.mem_write(C+0x5208,bytes.fromhex('4cdf04fc4e5d'));c.ctl_remove_cache(C+0x5208,C+0x520E)
  rng=random.Random(200+ccr);vals=[rng.getrandbits(32)for _ in REGS];vals[15]=STACK-44;vals[13]=STACK-4
  c.mem_write(STACK-44,bytes(rng.getrandbits(8)for _ in range(48)))
  c.reg_write(R.UC_M68K_REG_SR,0x2000|ccr)
  for r,v in zip(REGS,vals):c.reg_write(r,v)
  c.emu_start(C+0x5208,C+0x520E,count=100000)
  states.append((tuple(c.reg_read(r)for r in REGS),f.regs()[1]))
 assert states[0]==states[1],('end',ccr,states)
 result('epilogue ABI CCR '+str(ccr))
report=dict(module_sha256=META['sha256'],cases=len(results),results=results)
(P/'scope-validation.json').write_text(json.dumps(report,indent=2)+'\n')

