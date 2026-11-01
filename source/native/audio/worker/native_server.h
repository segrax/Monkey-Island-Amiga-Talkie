/* GPL-3.0-or-later. All requests run in task context, never from IRQ code. */
#ifndef NATIVE_SPEECH_SERVER_H
#define NATIVE_SPEECH_SERVER_H
#include <exec/ports.h>
#include "native_lookup.h"
#include "native_policy.h"

#define NATIVE_SERVER_PORT "MonkeyAmigaTalkie"
#define NATIVE_SERVER_VERSION 2
enum NativeServerCommand { NS_ATTACH = 1, NS_PLAY, NS_CANCEL, NS_DETACH, NS_QUIT, NS_METADATA_SAVE, NS_METADATA_LOAD };
enum NativeServerResult { NS_OK = 0, NS_NO_VOICE, NS_INVALID, NS_BUSY, NS_IO_ERROR };

struct NativeSpeechMessage {
	struct Message message;
	NvU16 version, command, generation, result;
	void *client_task;
	struct NativeVoice *voice;
	struct NativeSpeechContext context;
	struct NvPolicy *policy;
	NvU16 selector_count;
	struct NvSelector selectors[NV_POLICY_LIMIT];
};


struct NativeMetadataMessage {
 struct NativeSpeechMessage speech;
 char filename[256];
 NvU8 *blob;
 NvU32 capacity, bytes;
 NvU16 blob_version, reserved;
 NvS32 metadata_result;
 NvU32 random_seed;
 NvU16 selector_count;
 struct NvSelector selectors[NV_POLICY_LIMIT];
};

#ifdef __VBCC__
#include <stddef.h>
typedef char MetadataWireLayout[
 sizeof(struct NativeSpeechMessage) == 956 && sizeof(struct NativeMetadataMessage) == 1366 &&
 offsetof(struct NativeMetadataMessage, filename) == 956 &&
 offsetof(struct NativeMetadataMessage, blob) == 1212 &&
 offsetof(struct NativeMetadataMessage, metadata_result) == 1228 &&
 offsetof(struct NativeMetadataMessage, selectors) == 1238 ? 1 : -1];
#endif

/* ATTACH returns stable shared voice state. PLAY carries copied, bounded text;
 * origin is an optional full r:/c: key prefix including definition segment.
 * The caller owns the packet until ReplyMsg and must not reuse queued packets.
 * DETACH is sent only after game audio hooks/IRQs stop referencing shared state.
 * QUIT fails while a client remains attached. No task is terminated externally.
 */
#endif
