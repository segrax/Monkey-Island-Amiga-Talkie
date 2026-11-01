/* GPL-3.0-or-later */
#include "native_client.h"
#include <exec/tasks.h>
#include <exec/execbase.h>
#include <proto/exec.h>

static struct MsgPort reply;
static struct NativeSpeechMessage packet;
static struct NativeSpeechContext pending;
static int initialized, busy, queued, cancelling, attached, stopped;
static NvU16 generation;
static struct NativeVoice *voice;
static struct NvPolicy *policy;
static struct NvSelector pending_selectors[NV_POLICY_LIMIT];
static NvU16 pending_selector_count;

int nv_game_set_policy(struct NvPolicy *candidate) {
	policy = 0;
	if (!candidate || candidate->magic != NV_POLICY_MAGIC || candidate->version != NV_POLICY_VERSION ||
	    candidate->size != sizeof(*candidate) || candidate->trigger_count > NV_POLICY_LIMIT ||
	    candidate->selector_count > NV_POLICY_LIMIT)
		return 0;
	policy = candidate;
	return 1;
}

int nv_game_program(NvU16 kind, NvU16 room, NvU16 script, NvU32 offset) {
	return policy ? nv_policy_enter(policy, kind, room, script, offset) : 0;
}

static void copy_bytes(void *destination, const void *source, unsigned count) {
	NvU8 *out = destination;
	const NvU8 *in = source;
	while (count--)
		*out++ = *in++;
}

static int initialize(void) {
	LONG signal;
	if (initialized)
		return 1;
	signal = AllocSignal(-1);
	if (signal < 0)
		return 0;
	reply.mp_Node.ln_Type = NT_MSGPORT;
	reply.mp_Flags = PA_SIGNAL;
	reply.mp_SigBit = signal;
	reply.mp_SigTask = FindTask(0);
	reply.mp_MsgList.lh_Head = (struct Node *)&reply.mp_MsgList.lh_Tail;
	reply.mp_MsgList.lh_Tail = 0;
	reply.mp_MsgList.lh_TailPred = (struct Node *)&reply.mp_MsgList.lh_Head;
	packet.message.mn_Node.ln_Type = NT_MESSAGE;
	packet.message.mn_ReplyPort = &reply;
	packet.message.mn_Length = sizeof(packet);
	packet.version = NATIVE_SERVER_VERSION;
	packet.client_task = reply.mp_SigTask;
	initialized = 1;
	return 1;
}

static int submit(NvU16 command) {
	struct MsgPort *server;
	packet.command = command;
	packet.generation = generation;
	Forbid();
	server = FindPort(NATIVE_SERVER_PORT);
	if (server) {
		busy = 1;
		PutMsg(server, &packet.message);
	}
	Permit();
	return server != 0;
}

static void complete_reply(void) {
 busy = 0;
 if (packet.command == NS_ATTACH) {
  attached = packet.result == NS_OK;
  voice = attached ? packet.voice : 0;
  if (attached) nv_game_set_policy(packet.policy);
  if (!attached) queued = 0;
 }
 if (packet.command == NS_DETACH) attached = 0;
}

void nv_game_poll(void) {
	if (!initialized)
		return;
	if (busy && GetMsg(&reply)) {
		complete_reply();
	}
	if (busy)
		return;
	if (!attached) {
		if (queued && !submit(NS_ATTACH))
			queued = 0;
		return;
	}
	if (cancelling) {
		if (submit(NS_CANCEL))
			cancelling = 0;
	} else if (queued) {
		copy_bytes(&packet.context, &pending, sizeof(pending));
		packet.selector_count = pending_selector_count;
		copy_bytes(packet.selectors, pending_selectors, pending_selector_count * sizeof(*pending_selectors));
		if (submit(NS_PLAY))
			queued = 0;
	}
}

int nv_game_active(void) {
	NvU16 state;
	if (stopped)
		return 0;
	if (queued || (busy && (packet.command == NS_PLAY || packet.command == NS_ATTACH)))
		return 1;
	if (!voice || voice->generation != generation || cancelling)
		return 0;
	state = voice->state;
	return state >= NATIVE_VOICE_PENDING && state <= NATIVE_VOICE_DRAINING;
}

int nv_game_play(const struct NativeSpeechContext *context) {
	if (!context || context->text_length > NATIVE_TEXT_BYTES || !initialize())
		return 0;
	copy_bytes(&pending, context, sizeof(pending));
	pending_selector_count = policy && policy->selector_count <= NV_POLICY_LIMIT ? policy->selector_count : 0;
	if (pending_selector_count)
		copy_bytes(pending_selectors, policy->selectors, pending_selector_count * sizeof(*pending_selectors));
	if (!++generation)
		++generation;
	queued = 1;
	cancelling = 0;
	stopped = 0;
	nv_game_poll();
	return 1;
}

void nv_game_cancel(void) {
	stopped = 1;
	queued = 0;
	cancelling = 1;
	nv_game_poll();
}

void nv_game_shutdown(void) {
	if (!initialized)
		return;
	queued = cancelling = 0;
	if (busy) {
		WaitPort(&reply);
		GetMsg(&reply);
		busy = 0;
		if (packet.command == NS_ATTACH)
			attached = packet.result == NS_OK;
	}
	if (attached && submit(NS_DETACH)) {
		WaitPort(&reply);
		GetMsg(&reply);
	}
	FreeSignal(reply.mp_SigBit);
	initialized = busy = attached = 0;
	voice = 0;
	policy = 0;
}

static struct NativeMetadataMessage metadata_packet;
static int metadata_pending;
static NvU16 metadata_interrupts_enabled(void) = "\tmove.w\t$dff01c,d0\n\tandi.w\t#$4000,d0";
static int wait_pending(void) {
 while (busy) {
  WaitPort(&reply);
  if (GetMsg(&reply) != &packet.message) return 0;
  complete_reply();
 }
 return 1;
}
static int metadata_exchange(const char *filename, NvU8 *blob, NvU32 capacity,
 NvU32 *bytes, NvU16 blob_version, NvU16 command) {
 struct MsgPort *server;
 unsigned i;
 metadata_pending = 0;
 if (SysBase->IDNestCnt >= 0 || SysBase->TDNestCnt >= 0 || !metadata_interrupts_enabled()) return -2;
 if (!filename || !blob || !blob_version || capacity > 65536UL ||
     !initialize() || !wait_pending()) return -2;
 if (!attached) {
  if (!submit(NS_ATTACH) || !wait_pending() || !attached) return -2;
 }
 if (cancelling) {
  if (!submit(NS_CANCEL) || !wait_pending()) return -2;
  cancelling = 0;
 }
 for (i = 0; i < sizeof(metadata_packet.filename); ++i) {
  metadata_packet.filename[i] = filename[i];
  if (!filename[i]) break;
 }
 if (i == sizeof(metadata_packet.filename)) return -1;
 metadata_packet.speech.message.mn_Node.ln_Type = NT_MESSAGE;
 metadata_packet.speech.message.mn_ReplyPort = &reply;
 metadata_packet.speech.message.mn_Length = sizeof(metadata_packet);
 metadata_packet.speech.version = NATIVE_SERVER_VERSION;
 metadata_packet.speech.command = command;
 metadata_packet.speech.client_task = reply.mp_SigTask;
 metadata_packet.blob = blob;
 metadata_packet.capacity = capacity;
 metadata_packet.bytes = command == NS_METADATA_SAVE ? capacity : 0;
 metadata_packet.blob_version = blob_version;
 metadata_packet.reserved = 0;
 metadata_packet.metadata_result = -1;
 metadata_packet.selector_count = 0;
 metadata_packet.random_seed = 0;
 Forbid();
 server = FindPort(NATIVE_SERVER_PORT);
 if (server) PutMsg(server, &metadata_packet.speech.message);
 Permit();
 if (!server) return -2;
 WaitPort(&reply);
 if (GetMsg(&reply) != &metadata_packet.speech.message) return -2;
 if (bytes) *bytes = metadata_packet.bytes;
 return metadata_packet.metadata_result;
}
int nv_game_metadata_save(const char *filename, const unsigned char *blob,
 unsigned long bytes, unsigned short blob_version) {
 return metadata_exchange(filename, (NvU8 *)blob, bytes, 0, blob_version, NS_METADATA_SAVE);
}
int nv_game_metadata_load(const char *filename, unsigned char *blob,
 unsigned long capacity, unsigned long *bytes, unsigned short blob_version) {
 if (!bytes) return -1;
 *bytes = 0;
 queued = 0; stopped = 1; pending_selector_count = 0;
 {
  int result = metadata_exchange(filename, blob, capacity, bytes, blob_version, NS_METADATA_LOAD);
  metadata_pending = result == 1;
  return result;
 }
}

int nv_game_metadata_commit(int accepted) {
 unsigned i, j;
 int valid = accepted && metadata_pending && policy &&
  policy->magic == NV_POLICY_MAGIC && policy->version == NV_POLICY_VERSION &&
  policy->size == sizeof(*policy) && metadata_packet.random_seed &&
  metadata_packet.selector_count <= NV_POLICY_LIMIT;
 for (i = 0; valid && i < metadata_packet.selector_count; ++i) {
  valid = nv_policy_selector_valid(policy, &metadata_packet.selectors[i]);
  for (j = 0; j < i; ++j)
   if (metadata_packet.selectors[j].id == metadata_packet.selectors[i].id) valid = 0;
 }
 if (policy) {
  Disable();
  if (valid) {
   copy_bytes(policy->selectors, metadata_packet.selectors,
    metadata_packet.selector_count * sizeof(*policy->selectors));
   policy->random_seed = metadata_packet.random_seed;
   policy->selector_count = metadata_packet.selector_count;
  } else policy->selector_count = 0;
  Enable();
 }
 metadata_pending = 0;
 return valid;
}
