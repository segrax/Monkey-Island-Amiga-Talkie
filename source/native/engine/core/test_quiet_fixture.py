from pathlib import Path
import os,sys,json,hashlib
HERE=Path(__file__).resolve().parent
B=HERE
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
here=HERE

def fixture():
 n={'__file__':str(here/'test_hybrid_driver.py'),'__name__':'quiet_fixture','NATIVE_START':True};exec(compile(prefix,str(here/'test_hybrid_driver.py'),'exec'),n)
 return n
