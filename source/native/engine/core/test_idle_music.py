from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
n={'__file__':str(HERE/'test_direct_driver.py'),'__name__':'idle_fixture'}
prefix=(HERE/'test_direct_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
exec(compile(prefix,str(HERE/'test_direct_driver.py'),'exec'),n)
cpu,put,get,call=(n[k] for k in ('cpu','put','get','call'))
events=[]
def write(uc,access,address,size,value,_):
    if 0xdff0a0<=address<0xdff0e0 or address in (0xdff096,0xdff09a,0xdff09c):
        events.append((address,size,value))
cpu.hook_add(n['unicorn'].UC_HOOK_MEM_WRITE,write)
call('_nv_driver_start')
sample=0x605000;cpu.mem_write(sample,bytes(range(256))*8)
n['write'](0,sample,4);n['write'](4,1000);n['write'](6,428);n['write'](8,51)
call('_nv_driver_control',0,0x820f)
call('_nv_driver_control',1,0x8080)
for i in range(120):
    # Clock time can advance across several nominal samples/loops. While not
    # speaking, only real physical pending bits may trigger a music event.
    n['ticks']+=1000+i*7
    call('_nv_driver_service')
    assert n['field']('speech_active')==0
    assert get(0xdff0a6,2)==428 and get(0xdff0a8,2)==51
    assert get(n['bases'][0]+0x17e2,1)==0
    if i%12==0:
        n['irq']()
        assert get(n['bases'][0]+0x17e2,1)==255
        put(n['bases'][0]+0x17e2,0,1)
        call('_nv_driver_control',1,0x8080)
digest=hashlib.sha256(json.dumps(events).encode()).hexdigest()
report={'module_sha256':n['meta']['sha256'],'hardware_writes':len(events),
        'hardware_trace_sha256':digest,'idle_updates':120,'physical_music_irqs':10,
        'speech_activations':0,'sample_period_unchanged':428,'volume_unchanged':51,
        'scope':'compiled 68000 with mocked clock and hardware registers; not DAC timing'}
out=Path(n['BUILD'])/'idle-music-validation.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
