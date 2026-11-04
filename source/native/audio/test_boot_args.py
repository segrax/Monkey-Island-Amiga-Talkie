"""Host-GCC check of the exact loader parser; run on Linux/WSL with gcc."""
from pathlib import Path
import ctypes,json,subprocess,tempfile
source=Path(__file__).with_name('server_probe.c').read_text()
a=source.index('static char game_args');z=source.index('static NvU8 *segment_address')
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);(root/'parse.c').write_text('#include <string.h>\n'+source[a:z].replace('static ',''))
    subprocess.run(['gcc','-shared','-fPIC','-O2',str(root/'parse.c'),'-o',str(root/'parse.so')],check=True)
    lib=ctypes.CDLL(str(root/'parse.so'));f=lib.boot_parameter;f.argtypes=[ctypes.c_char_p]
    args=(ctypes.c_char*8).in_dll(lib,'game_args');length=ctypes.c_long.in_dll(lib,'game_args_length')
    assert bytes(args)[:2]==b'\n\0' and length.value==1
    n=0
    for value in range(32768):
        s=str(value).encode();assert f(s)==1 and bytes(args)[:len(s)+2]==s+b'\n\0' and length.value==len(s)+1;n+=1
    for s in (b'',b'-1',b'+1',b'32768',b'65535',b'999999',b'28x',b'2 8',b'28\n',b'--boot-param=28'):
        before=bytes(args);old=length.value;assert f(s)==0 and bytes(args)==before and length.value==old;n+=1
print(json.dumps(dict(PASS=True,cases=n,scope='Exact extracted current C parser; target register ABI is separate')))
