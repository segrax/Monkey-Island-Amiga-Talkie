 section mocks,code
 xdef _malloc
_malloc:
 rts
 xdef _free
_free:
 rts
 xdef _fread
_fread:
 rts
 xdef _fwrite
_fwrite:
 rts
 xdef _fclose
_fclose:
 rts
 xdef _fopen
_fopen:
 rts
 xdef _fseek
_fseek:
 rts
 xdef _ftell
_ftell:
 rts
 xdef _ferror
_ferror:
 rts
 xdef _clearerr
_clearerr:
 rts
 xdef _memcmp
_memcmp:
 rts
 xdef _memcpy
_memcpy:
 rts
 xdef _memset
_memset:
 rts
 xdef _strlen
_strlen:
 rts
 xdef _strcpy
_strcpy:
 rts
 xdef _strcat
_strcat:
 rts
 xdef _remove
_remove:
 rts
 xdef _rename
_rename:
 rts
 section BSS,bss
 xdef _errno
_errno:
 ds.l 1
