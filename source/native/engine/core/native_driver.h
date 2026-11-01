/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_DRIVER_H
#define NATIVE_DRIVER_H
#include "paula_mix.h"

#define NV_CONTROL_MAGIC 0x4e564252UL
#define NV_CONTROL_VERSION 2
#define NV_CONTROL_ENABLE 1
#define NV_CONTROL_RUNNING 2
#define NV_CONTROL_FAILED 4
#define NV_CONTROL_SKIP_PIRATE_CHECK 8

struct NvPolicy;
/* Loader publishes all pointers before original entry. */
struct NvControl {
	NvU32 magic;
	NvU16 version;
	NvU16 size;
	struct NativeVoice *voice;
	NvU8 *game_code;
	NvU8 *game_globals;
	volatile NvU32 flags;
	struct NvPolicy *policy;
};

extern struct NvControl nv_control;
void nv_driver_service(void);

#endif
