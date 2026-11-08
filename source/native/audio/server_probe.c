/* GPL-3.0-or-later. Silent Exec IPC/ring integration probe. */
#include "native_server.h"
#include <exec/tasks.h>
#include <dos/dosextens.h>
#include <workbench/startup.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <stdio.h>
#include <string.h>
#include "worker_startup.h"
#ifndef NATIVE_GAME_LOADER
#include "native_client.h"
#include "persona_fixture.h"
#endif

static struct MsgPort replies;
static struct NativeSpeechMessage packet;
static struct NvWorkerStartup worker_startup;
#define startup worker_startup.wb
static struct WBArg argument;
static struct MsgPort *server;

#ifdef NATIVE_GAME_LOADER
#include "native_driver.h"
#include "module_exports.h"
#include "workbench_launch.h"
extern long call_game(__reg("a1") void *entry, __reg("a0") const char *args, __reg("d0") long length);
static NvU32 loader_flags;
static char game_args[8] = "\n";
static long game_args_length = 1;

static int boot_parameter(const char *text) {
 unsigned long value = 0;
 unsigned n = 0;
 if (!*text) return 0;
 while (text[n]) {
  if (text[n] < '0' || text[n] > '9' || n >= 5) return 0;
  value = value * 10 + (unsigned)(text[n] - '0');
  if (value > 32767) return 0;
  ++n;
 }
 memcpy(game_args, text, n);
 game_args[n] = '\n'; game_args[n+1] = 0;
 game_args_length = n+1;
 return 1;
}

static NvU8 *segment_address(BPTR segment, unsigned index) {
	while (segment && index--)
		segment = *(BPTR *)BADDR(segment);
	return segment ? (NvU8 *)BADDR(segment) + 4 : 0;
}

static int run_game(void) {
	BPTR segments;
	NvU8 *base, *code, *globals, *end, *shutdown;
	struct NvControl *control;
	long result;
	unsigned char bytes[512];
	unsigned int used, i;
	NvU32 hash = 2166136261UL, total = 0;
	FILE *image = fopen("Monkey_Talkie", "rb");
	if (!image) {
		puts("Cannot open Monkey_Talkie; run from the game folder.");
		return 0;
	}
	while ((used = fread(bytes, 1, sizeof(bytes), image)) != 0) {
		for (i = 0; i < used; ++i) {
			hash ^= bytes[i];
			hash = (hash << 24) + (hash << 8) + (hash << 7) + (hash << 4) + (hash << 1) + hash;
		}
		total += used;
		if (total > NV_MODULE_BYTES)
			break;
	}
	result = ferror(image);
	fclose(image);
	if (result || total != NV_MODULE_BYTES || hash != NV_MODULE_FNV) {
		puts("Native game and launcher differ; rebuild both together.");
		return 0;
	}
	segments = LoadSeg("Monkey_Talkie");
	if (!segments) {
		printf("Cannot load Monkey_Talkie (DOS error %ld).\n", IoErr());
		return 0;
	}
	base = segment_address(segments, NV_CONTROL_HUNK);
	code = segment_address(segments, 0);
	globals = segment_address(segments, 2);
	end = segment_address(segments, NV_END_HUNK);
	shutdown = segment_address(segments, NV_SHUTDOWN_HUNK);
	if (!base || !code || !globals || !end || !shutdown) {
		UnLoadSeg(segments);
		return 0;
	}
	control = (struct NvControl *)(base + NV_CONTROL_OFFSET);
	if (control->magic != NV_CONTROL_MAGIC || control->version != NV_CONTROL_VERSION ||
	    control->size != sizeof(*control)) {
		UnLoadSeg(segments);
		return 0;
	}
	control->voice = packet.voice;
	control->game_code = code;
	control->game_globals = globals;
#if NV_CONTROL_VERSION >= 2
	control->policy = packet.policy;
#endif
#ifdef NV_PRESENCE_HUNK
	{
		NvU8 *presence = segment_address(segments, NV_PRESENCE_HUNK);
		FILE *mode = fopen("PreparedOnly", "rb");
		unsigned char marker[5];
		int enabled = mode && fread(marker, 1, 5, mode) == 5 &&
			!memcmp(marker, "NPC1\n", 5) && fgetc(mode) == EOF;
		if (mode) fclose(mode);
		if (presence) *(NvU16 *)(presence + NV_PRESENCE_OFFSET) = enabled;
	}
#endif
	control->flags = NV_CONTROL_ENABLE | loader_flags;
	puts("Starting native Monkey Island");
	fflush(stdout);
	result = call_game(code, game_args, game_args_length);
	((void (*)(void))(end + NV_END_OFFSET))();
	((void (*)(void))(shutdown + NV_SHUTDOWN_OFFSET))();
	control->flags = 0;
	UnLoadSeg(segments);
	printf("Native game returned %ld\n", result);
	return result == 0;
}
#endif

static int request(NvU16 command) {
	packet.command = command;
	PutMsg(server, &packet.message);
	WaitPort(&replies);
	return GetMsg(&replies) == &packet.message && packet.result == NS_OK;
}

#ifndef NATIVE_GAME_LOADER
static int drain_client(NvU16 generation, NvU32 expected_bytes, NvU32 expected_hash) {
	struct NativeVoice *voice = packet.voice;
	NvU32 hash = 2166136261UL, total = 0;
	NvU16 read, write, i;
	if (!nv_game_play(&packet.context))
		return 0;
	while (nv_game_active()) {
		nv_game_poll();
		if (voice->generation == generation && voice->state >= NATIVE_VOICE_READY && voice->state <= NATIVE_VOICE_DRAINING) {
			read = voice->read_cursor;
			write = voice->write_cursor;
			for (i = 0; i < (NvU16)(write - read); ++i) {
				hash ^= (NvU8)voice->pcm[(read + i) & (voice->capacity - 1)];
				hash = (hash << 24) + (hash << 8) + (hash << 7) + (hash << 4) + (hash << 1) + hash;
				++total;
			}
			voice->read_cursor = write;
			if (voice->eof && voice->read_cursor == voice->write_cursor)
				voice->state = NATIVE_VOICE_DONE;
			else
				Signal(voice->worker_task, voice->signal_mask);
		}
		Delay(1);
	}
	printf("Async PCM %u %lu %08lx\n", generation, total, hash);
	return total == expected_bytes && hash == expected_hash;
}

static int probe_client(void) {
	NvU16 value, attempts;
	if (!nv_game_set_policy(packet.policy) || nv_game_program(NATIVE_GLOBAL, 0, 111, 0) != 1 ||
	    packet.policy->selector_count != 1 || packet.policy->selectors[0].index >= 3)
		return 0;
	memset(&packet.context, 0, sizeof(packet.context));
	packet.context.room = packet.context.resource_room = 38;
	packet.context.actor = 1;
	packet.context.kind = NATIVE_LOCAL;
	packet.context.script = 203;
	packet.context.text_length = 3;
	memcpy(packet.context.text, "Hi!", 3);
	if (!drain_client(1, 7572, 0x1fa4e8d1UL))
		return 0;
	packet.context.room = packet.context.resource_room = 49;
	packet.context.actor = 8;
	packet.context.script = 200;
	packet.context.message_offset = 88;
	strcpy((char *)packet.context.text, NV_PERSONA_TEXT);
	packet.context.text_length = strlen(NV_PERSONA_TEXT);
	for (value = 0; value < 3; ++value) {
		for (attempts = 0; attempts < 100; ++attempts) {
			if (nv_game_program(NATIVE_GLOBAL, 0, 111, 0) != 1)
				return 0;
			if (packet.policy->selectors[0].index == value)
				break;
		}
		if (attempts == 100 || !drain_client(2 + value, persona_bytes[value], persona_hashes[value]))
			return 0;
	}
	if (!nv_game_play(&packet.context))
		return 0;
	nv_game_cancel();
	if (nv_game_active())
		return 0;
	nv_game_shutdown();
	puts("Async client queue/cancel/shutdown PASS");
	return 1;
}
#endif

static int drain(const char *text, NvU16 generation, NvU32 expected_bytes, NvU32 expected_hash) {
	struct NativeVoice *voice;
	NvU32 hash = 2166136261UL, total = 0;
	NvU16 read, write;
	unsigned i;
	packet.context.text_length = strlen(text);
	memcpy(packet.context.text, text, packet.context.text_length);
	packet.generation = generation;
	if (!request(NS_PLAY))
		return 0;
	voice = packet.voice;
	for (;;) {
		read = voice->read_cursor;
		write = voice->write_cursor;
		if ((NvU16)(write - read) > voice->capacity)
			return 0;
		for (i = 0; i < (NvU16)(write - read); ++i) {
			hash ^= (NvU8)voice->pcm[(read + i) & (voice->capacity - 1)];
			hash = (hash << 24) + (hash << 8) + (hash << 7) + (hash << 4) + (hash << 1) + hash;
			++total;
		}
		voice->read_cursor = write;
		if (voice->eof && voice->read_cursor == voice->write_cursor)
			break;
		if (voice->state == NATIVE_VOICE_FAILED)
			return 0;
		Signal(voice->worker_task, voice->signal_mask);
		Delay(1);
	}
	printf("PCM %u %lu %08lx\n", generation, total, hash);
	return total == expected_bytes && hash == expected_hash;
}

int main(int argc, char **argv) {
	struct MsgPort *child;
	struct Process *self = (struct Process *)FindTask(0);
	BPTR segment;
	LONG signal;
	int success = 0, attached = 0;
#ifdef NATIVE_GAME_LOADER
	int option;
	if (argc == 0)
		return launch_workbench((struct WBStartup *)argv);
	for (option = 1; option < argc; ++option) {
		if (!strcmp(argv[option], "--skip-pirate-check"))
			loader_flags |= NV_CONTROL_SKIP_PIRATE_CHECK;
		else if (!strncmp(argv[option], "--boot-param=", 13) &&
		         !(loader_flags & NV_CONTROL_DEBUG_BOOT) && boot_parameter(argv[option]+13))
			loader_flags |= NV_CONTROL_DEBUG_BOOT;
		else {
			puts("Usage: MonkeyTalkie [--skip-pirate-check] [--boot-param=0..32767]");
			return 20;
		}
	}
#else
	(void)argc;
	(void)argv;
#endif
	puts("Probe started");
	fflush(stdout);
	if (FindPort(NATIVE_SERVER_PORT)) {
		puts("Server already active; probe requires isolated session");
		return 20;
	}
	signal = AllocSignal(-1);
	if (signal < 0)
		return 20;
	replies.mp_Node.ln_Type = NT_MSGPORT;
	replies.mp_Flags = PA_SIGNAL;
	replies.mp_SigBit = signal;
	replies.mp_SigTask = self;
	replies.mp_MsgList.lh_Head = (struct Node *)&replies.mp_MsgList.lh_Tail;
	replies.mp_MsgList.lh_TailPred = (struct Node *)&replies.mp_MsgList.lh_Head;
	segment = LoadSeg("VoiceServer");
	printf("Worker loaded %08lx\n", segment);
	fflush(stdout);
	if (!segment)
		goto finish;
	argument.wa_Lock = DupLock(self->pr_CurrentDir);
	if (self->pr_CurrentDir && !argument.wa_Lock) {
		puts("Cannot duplicate the game directory lock.");
		goto unload;
	}
	argument.wa_Name = "VoiceServer";
	startup.sm_Message.mn_Node.ln_Type = NT_MESSAGE;
	startup.sm_Message.mn_ReplyPort = &replies;
	startup.sm_Message.mn_Length = sizeof(worker_startup);
	worker_startup.magic = NV_STARTUP_MAGIC;
	nv_startup_error(&worker_startup, "VoiceServer stopped before its main routine; check free memory and NIL:.");
	startup.sm_Segment = segment;
	startup.sm_NumArgs = 1;
	startup.sm_ArgList = &argument;
	child = CreateProc("Monkey voice worker", 0, segment, 16384);
	if (!child)
		goto unload;
	startup.sm_Process = child;
	PutMsg(child, &startup.sm_Message);
	puts("Worker startup sent");
	fflush(stdout);
	while (!(server = FindPort(NATIVE_SERVER_PORT))) {
		if (GetMsg(&replies)) {
			puts("Worker exited before initialization");
			puts(worker_startup.error);
			goto unload;
		}
		Delay(1);
	}
	packet.message.mn_Node.ln_Type = NT_MESSAGE;
	puts("Worker registered");
	fflush(stdout);
	packet.message.mn_ReplyPort = &replies;
	packet.message.mn_Length = sizeof(packet);
	packet.version = NATIVE_SERVER_VERSION;
	packet.client_task = self;
	attached = request(NS_ATTACH);
	printf("Attach %d\n", attached);
	fflush(stdout);
	if (attached) {
#ifdef NATIVE_GAME_LOADER
		success = run_game();
#else
		memset(&packet.context, 0, sizeof(packet.context));
		packet.context.room = packet.context.resource_room = 38;
		packet.context.actor = 1;
		packet.context.kind = NATIVE_LOCAL;
		packet.context.script = 203;
		success = drain("Hi!", 1, 7572, 0x1fa4e8d1UL);
		memset(&packet.context, 0, sizeof(packet.context));
		if (!drain("As you can probably imagine, it's one of the most caustic, volatile substances known to man.",
		           2, 239003, 0x42cb4e8eUL))
			success = 0;
		packet.context.room = 59;
		packet.context.actor = 3;
		packet.context.kind = NATIVE_GLOBAL;
		packet.context.script = 56;
		packet.context.message_offset = 14417;
		if (!drain("You could sail this puppy away TODAY, for just 3050 pieces of eight.",
		           3, 133783, 0x664729cfUL))
			success = 0;
		memset(&packet.context, 0, sizeof(packet.context));
		strcpy((char *)packet.context.text, "As you can probably imagine, it's one of the most caustic, volatile substances known to man.");
		packet.context.text_length = strlen((char *)packet.context.text);
		packet.generation = 4;
		if (!request(NS_PLAY) || packet.voice->eof || !request(NS_CANCEL) ||
		    packet.voice->state != NATIVE_VOICE_CANCELLED || !packet.voice->eof ||
		    packet.voice->read_cursor != packet.voice->write_cursor)
			success = 0;
		packet.context.room = packet.context.resource_room = 38;
		packet.context.actor = 1;
		packet.context.kind = NATIVE_LOCAL;
		packet.context.script = 203;
		if (!drain("Hi!", 5, 7572, 0x1fa4e8d1UL))
			success = 0;
		strcpy((char *)packet.context.text, "deliberately unmapped probe phrase");
		packet.context.text_length = strlen((char *)packet.context.text);
		packet.generation = 6;
		request(NS_PLAY);
		if (packet.result != NS_NO_VOICE || packet.voice->state != NATIVE_VOICE_DONE || !packet.voice->eof)
			success = 0;
		if (!request(NS_CANCEL))
			success = 0;
		if (!probe_client())
			success = 0;
#endif
		if (!request(NS_DETACH))
			success = 0;
	}
	if (!request(NS_QUIT))
		success = 0;
	WaitPort(&replies);
	if (GetMsg(&replies) != &startup.sm_Message)
		success = 0;
unload:
	if (argument.wa_Lock)
		UnLock(argument.wa_Lock);
	UnLoadSeg(segment);
finish:
	FreeSignal(signal);
	printf("Voice IPC probe: %s\n", success ? "PASS" : "FAIL");
	return success ? 0 : 20;
}
