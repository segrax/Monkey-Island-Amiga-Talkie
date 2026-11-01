/* GPL-3.0-or-later */
#ifndef NATIVE_SPEECH_POLICY_H
#define NATIVE_SPEECH_POLICY_H
#include "native_lookup.h"

#define NV_POLICY_MAGIC 0x4e565059UL
#define NV_POLICY_VERSION 1
#define NV_POLICY_LIMIT 16

struct NvTrigger {
	NvU16 kind, resource_room, script, room, selector, count;
	NvU32 offset;
};

struct NvSelector {
	NvU16 id, room, index, count;
};

struct NvPolicy {
	NvU32 magic;
	NvU16 version, size, trigger_count, selector_count;
	NvU32 random_seed;
	struct NvTrigger triggers[NV_POLICY_LIMIT];
	struct NvSelector selectors[NV_POLICY_LIMIT];
};

void nv_policy_init(struct NvPolicy *policy, NvU32 seed);
int nv_policy_collect(void *policy, const char *key, unsigned long offset, unsigned long length);
int nv_policy_enter(struct NvPolicy *policy, NvU16 kind, NvU16 resource_room,
                    NvU16 script, NvU32 offset);
int nv_policy_selector_valid(const struct NvPolicy *policy, const struct NvSelector *selector);
#endif
