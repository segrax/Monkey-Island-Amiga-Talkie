from pathlib import Path
import sys,json,struct,random
HERE=Path(__file__).resolve().parent
helper=HERE/'test_game.py';ns={'__file__':str(helper),'__name__':'batch_fixture'};exec(compile(helper.read_text().split('RESULTS=[]',1)[0],str(helper),'exec'),ns);globals().update({k:v for k,v in ns.items()if not k.startswith('__')})
P=artifact_dir('art')

# Two synthetic columns: both original codecs are valid independent repeat packets.
height=8; source=struct.pack('<I',26)+b'OI'+struct.pack('<H',113)+bytes(4)+struct.pack('<II',12,15)+bytes((10,2,64))*2
DICT=80;INDICES=94;SOURCE=126;STRIPS=64;CODECOFF=20;SOURCEBYTES=len(source);SIZE=154;HEIGHT=8;WIDTH=16
payload=bytearray(SIZE);struct.pack_into('>4sHHIHHHHIIIIIIHH',payload,0,b'NPD1',1,64,SIZE,WIDTH,HEIGHT,1,14,16,DICT,INDICES,SOURCE,SOURCEBYTES,STRIPS,2,3)
palette=bytes([16,0]+list(range(18,32)));payload[48:64]=palette
for i in range(2):struct.pack_into('>IHH',payload,64+8*i,20+i*3,3,0)
payload[DICT:DICT+14]=bytes([18])*8+bytes((0,255,0,255,0))+b'\0';payload[SOURCE:SOURCE+SOURCEBYTES]=source
PAYLOAD=bytes(payload);ART=struct.pack('>8sHHIIIII',b'NVPART01',1,24,1,32,56,56+SIZE,0)+struct.pack('>HHIIIHHI',10,113,56,SIZE,SOURCEBYTES,WIDTH,HEIGHT,0)+PAYLOAD
ns.update({k:globals()[k]for k in('ART','PAYLOAD','DICT','INDICES','SOURCE','STRIPS','CODECOFF','SOURCEBYTES','SIZE','HEIGHT','WIDTH')})
results=[]
for ccr in range(32):
 states=[];calls=[]
 for fast in(False,True):
  f=Fixture();f.setup();c=f.cpu
  if not fast:
   for a,b in [(0x5104,'4e55fff448e73f20'),(0x516a,'3b40fff66000008e'),(0x5208,'4cdf04fc4e5d')]:
    c.mem_write(C+a,bytes.fromhex(b));c.ctl_remove_cache(C+a,C+a+len(bytes.fromhex(b)))
  # Real object metadata: width two strips, height one eight-pixel unit.
  c.mem_write(G+0x1a1f+1,b'\0');c.mem_write(G+0x1a1f+0x46+1,b'\0');c.mem_write(G+0x1a1f+0x8c+1,b'\x02');c.mem_write(G+0x1a1f+0xd2+1,b'\x01')
  be16(c,G+0x5994,39);c.mem_write(G+0x5c49,palette)
  rng=random.Random(ccr+600);vals=[rng.getrandbits(32)for _ in REGS];vals[12]=G;vals[15]=STACK;vals[0]=0
  c.reg_write(R.UC_M68K_REG_SR,0x2000|ccr)
  for r,v in zip(REGS,vals):c.reg_write(r,v)
  c.mem_write(STACK,struct.pack('>II',STOP,0));entries=[];current=[None,0]
  def code(c,pc,size,u):
   if current[0] is not None:
    if pc==current[0]:entries.append(current[1]);current[:]=[None,0]
    else:current[1]+=1
   if pc==addr('_nv_art_game_bind'):
    current[:]=[u32(c,c.reg_read(R.UC_M68K_REG_A7)),1]
  hook=c.hook_add(unicorn.UC_HOOK_CODE,code)
  c.emu_start(C+0x5104,STOP,count=1000000);c.hook_del(hook)
  assert c.reg_read(R.UC_M68K_REG_PC)==STOP
  states.append((f.regs(),bytes(c.mem_read(G,29312)),bytes(c.mem_read(PRIMARY,64006)),bytes(c.mem_read(BACKUP,64006)),bytes(c.mem_read(MASK,8006))))
  calls.append(entries)
 assert states[0]==states[1],('whole object',ccr,[(x[0][0],x[0][1])for x in states])
 assert len(calls[0])==len(calls[1])==2,(ccr,calls)
 assert calls[1][1]<calls[0][1]*0.6,(ccr,calls)
 results.append(dict(ccr=ccr,bind_instructions_full=calls[0],bind_instructions_scoped=calls[1]));print('whole original object loop CCR',ccr,calls,flush=True)
(P/'loop-validation.json').write_text(json.dumps(dict(module_sha256=META['sha256'],cases=len(results),results=results),indent=2)+'\n')

