/* GPL-3.0-or-later. Fixed-size policy shared by the worker and game task. */
#include "native_policy.h"

static int literal(const char **cursor, const char *value) {
	const char *at = *cursor;
	while (*value)
		if (*at++ != *value++)
			return 0;
	*cursor = at;
	return 1;
}

static int number(const char **cursor, NvU32 *value, int last) {
	const char *at = *cursor;
	NvU32 result = 0, digit;
	if (*at < '0' || *at > '9')
		return 0;
	do {
		digit = *at++ - '0';
		if (result > 214748364UL || (result == 214748364UL && digit > 7))
			return 0;
		result = (result << 3) + (result << 1) + digit;
	} while (*at >= '0' && *at <= '9');
	if (last ? *at != 0 : *at++ != ':')
		return 0;
	*cursor = at;
	*value = result;
	return 1;
}

static int word(const char **cursor, NvU16 *value, int last) {
	NvU32 result;
	if (!number(cursor, &result, last) || result > 65535)
		return 0;
	*value = (NvU16)result;
	return 1;
}

void nv_policy_init(struct NvPolicy *policy, NvU32 seed) {
	NvU8 *bytes = (NvU8 *)policy;
	unsigned int i;
	for (i = 0; i < sizeof(*policy); ++i)
		bytes[i] = 0;
	policy->magic = NV_POLICY_MAGIC;
	policy->version = NV_POLICY_VERSION;
	policy->size = sizeof(*policy);
	policy->random_seed = seed ? seed : 0x6d2b79f5UL;
}

int nv_policy_collect(void *context, const char *key, unsigned long offset, unsigned long length) {
	struct NvPolicy *policy = context;
	struct NvTrigger trigger;
	const char *at = key;
	NvU16 i;
	if (!literal(&at, "v:init:"))
		return 1;
	if (length < 8 || length > 132 || (length & 1) || offset > 0x7fffffffUL)
		return 0;
	trigger.resource_room = trigger.script = 0;
	if (literal(&at, "g:")) {
		trigger.kind = NATIVE_GLOBAL;
		if (!word(&at, &trigger.script, 0)) return 0;
	} else if (literal(&at, "l:")) {
		trigger.kind = NATIVE_LOCAL;
		if (!word(&at, &trigger.resource_room, 0) || !word(&at, &trigger.script, 0)) return 0;
	} else if (literal(&at, "o:")) {
		trigger.kind = NATIVE_OBJECT;
		if (!word(&at, &trigger.script, 0)) return 0;
	} else if (literal(&at, "e:")) {
		if (!word(&at, &trigger.resource_room, 0)) return 0;
		if (literal(&at, "ENCD:")) trigger.kind = NATIVE_ENCD;
		else if (literal(&at, "EXCD:")) trigger.kind = NATIVE_EXCD;
		else return 0;
	} else return 0;
	if (!number(&at, &trigger.offset, 0) || !word(&at, &trigger.room, 0) ||
	    !word(&at, &trigger.selector, 0) || !word(&at, &trigger.count, 1) ||
	    !trigger.room || trigger.room > 255 || !trigger.count || trigger.count > 16)
		return 0;
	for (i = 0; i < policy->trigger_count; ++i) {
		const struct NvTrigger *existing = &policy->triggers[i];
		if (existing->kind == trigger.kind && existing->resource_room == trigger.resource_room &&
		    existing->script == trigger.script && existing->offset == trigger.offset &&
		    existing->selector == trigger.selector)
			return 0;
	}
	if (policy->trigger_count >= NV_POLICY_LIMIT)
		return 0;
	policy->triggers[policy->trigger_count++] = trigger;
	return 1;
}

static NvU16 draw(struct NvPolicy *policy, NvU16 count) {
	NvU32 seed;
	NvU16 value, limit = 256, remainder;
	remainder = limit;
	while (remainder >= count) remainder -= count;
	limit -= remainder;
	do {
		seed = policy->random_seed;
		seed ^= seed << 13;
		seed ^= seed >> 17;
		seed ^= seed << 5;
		policy->random_seed = seed;
		value = seed & 255;
	} while (value >= limit);
	while (value >= count) value -= count;
	return value;
}

int nv_policy_enter(struct NvPolicy *policy, NvU16 kind, NvU16 room, NvU16 script, NvU32 offset) {
	NvU16 i, slot;
	int changed = 0;
	if (!policy || policy->magic != NV_POLICY_MAGIC || policy->version != NV_POLICY_VERSION ||
	    policy->size != sizeof(*policy) || policy->trigger_count > NV_POLICY_LIMIT ||
	    policy->selector_count > NV_POLICY_LIMIT || !policy->random_seed)
		return -1;
	for (i = 0; i < policy->trigger_count; ++i) {
		const struct NvTrigger *trigger = &policy->triggers[i];
		struct NvSelector *selector;
		if (trigger->kind != kind || trigger->script != script || trigger->offset != offset ||
		    (kind != NATIVE_GLOBAL && kind != NATIVE_OBJECT && trigger->resource_room != room))
			continue;
		if (!trigger->count || trigger->count > 16)
			return -1;
		for (slot = 0; slot < policy->selector_count; ++slot)
			if (policy->selectors[slot].id == trigger->selector)
				break;
		if (slot == NV_POLICY_LIMIT)
			return -1;
		if (slot == policy->selector_count)
			++policy->selector_count;
		selector = &policy->selectors[slot];
		selector->id = trigger->selector;
		selector->room = trigger->room;
		selector->count = trigger->count;
		selector->index = draw(policy, trigger->count);
		++changed;
	}
	return changed;
}

int nv_policy_selector_valid(const struct NvPolicy *policy, const struct NvSelector *selector) {
	NvU16 i;
	if (!policy || !selector || policy->magic != NV_POLICY_MAGIC || policy->version != NV_POLICY_VERSION ||
	    policy->size != sizeof(*policy) || policy->trigger_count > NV_POLICY_LIMIT ||
	    !selector->count || selector->index >= selector->count)
		return 0;
	for (i = 0; i < policy->trigger_count; ++i)
		if (policy->triggers[i].selector == selector->id && policy->triggers[i].room == selector->room &&
		    policy->triggers[i].count == selector->count)
			return 1;
	return 0;
}

#include <stddef.h>
typedef char NativeMapMustBe32Bytes[sizeof(struct NativeMap) == 32 ? 1 : -1];
typedef char NativeEntryMustBe8Bytes[sizeof(struct NativeMapEntry) == 8 ? 1 : -1];
typedef char NativeMapTailMustMatch[
    offsetof(struct NativeMap, data_start) == 20 &&
    offsetof(struct NativeMap, file_bytes) == 24 &&
    offsetof(struct NativeMap, preindexed) == 28 ? 1 : -1];
