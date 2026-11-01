"""Check each compiled field notification without synchronizing unrelated data."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json
here=Path(__file__).resolve().parent
exec(compile((here/'test_direct_driver.py').read_text(),str(here/'test_direct_driver.py'),'exec'))
put(control+20,3,4)
checks=0
for speech in (0,1):
    put(driver+layout['speech_active'],speech,2)
    for offset,raw,logical,size in ((0,0x612345,0x612344,4),(4,0,131072,4),
        (4,65535,131070,4),(6,0,65536,4),(6,428,428,4),(8,127,64,2),(8,63,63,2)):
        # All bank fields differ from the current shadow, to detect an accidental
        # full synchronize rather than notification of only the actual write.
        put(bank,0x612345,4);put(bank+4,0,2);put(bank+6,0,2);put(bank+8,127,2)
        put(driver,0x605000,4);put(driver+4,200,4);put(driver+24,322,4);put(driver+36,17,2)
        if offset:put(bank+offset,raw,2)
        before=bytearray(cpu.mem_read(driver,54));expected=bytearray(before)
        changed={0:0,4:4,6:24,8:36}[offset]
        expected[changed:changed+size]=logical.to_bytes(size,'big')
        for address,value in ((0xdff0a0,0x604000),(0xdff0a4,23),(0xdff0a6,567),(0xdff0a8,29)):
            put(address,value,4 if address==0xdff0a0 else 2)
        hardware_before=bytes(cpu.mem_read(0xdff0a0,10))
        call('_nv_driver_write',bank,offset)
        assert bytes(cpu.mem_read(driver,54))==bytes(expected),(speech,offset)
        hardware_after=bytearray(hardware_before)
        if not speech:
            value=logical if not offset else raw
            width=4 if not offset else 2
            hardware_after[offset:offset+width]=value.to_bytes(width,'big')
        assert bytes(cpu.mem_read(0xdff0a0,10))==bytes(hardware_after),(speech,offset)
        checks+=1
    # The defensive unknown-offset route still synchronizes all four fields.
    put(bank,0x605004,4);put(bank+4,23,2);put(bank+6,428,2);put(bank+8,127,2)
    call('_nv_driver_write',bank,10)
    assert (get(driver,4),get(driver+4,4),get(driver+24,4),get(driver+36,2))==(0x605004,46,428,64)
    checks+=1
print(json.dumps(dict(compiled_field_notifications=checks,unrelated_shadow_unchanged=True,
    idle_hardware_mirror_exact=True,speech_hardware_untouched=True,
    zero_length_period_and_volume_bit6=True,unknown_offset_full_sync=True,
    normal_restore_and_cancellation_tested_in_driver_fixture=True)))
