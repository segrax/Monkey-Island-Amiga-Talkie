#include <stddef.h>
#include "native_voice.h"
const unsigned long voice_offsets[]={sizeof(struct NativeVoice),offsetof(struct NativeVoice,state),offsetof(struct NativeVoice,generation),offsetof(struct NativeVoice,read_cursor),offsetof(struct NativeVoice,pcm),offsetof(struct NativeVoice,worker_task),offsetof(struct NativeVoice,signal_mask)};
#include "native_driver.h"
const unsigned long control_offsets[]={sizeof(struct NvControl),offsetof(struct NvControl,voice),offsetof(struct NvControl,game_code),offsetof(struct NvControl,game_globals),offsetof(struct NvControl,flags)};
