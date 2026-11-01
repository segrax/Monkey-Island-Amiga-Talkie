/* Local native experiment, GPL-3.0-or-later. */
#include "native_server.h"
#include "native_gain.h"
#include "native_pcm.h"
#include "native_profile.h"
#include "native_metadata_store.h"
#include "native_md5.h"
#include "metadata_bindings.h"
#include "prepared_bindings.h"
#ifdef NATIVE_ASM_LUT
#include "ring_lut.h"
#endif
#include <exec/memory.h>
#include <exec/tasks.h>
#include <dos/dos.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <stdio.h>
#include <string.h>

static struct NativeVoice voice;
static struct NativePcm prebuilt;
static unsigned char staging[2048];
static signed char amplified_pcm[256];
static struct NativeSpeechSequence sequence;
static NvU16 sequence_index;
static int prepared_only;
static struct NvPolicy policy;

struct MapIdentity { LONG disk_key, bytes; struct DateStamp date; };
static struct MapIdentity metadata_identity;
static NvU8 metadata_map_digest[16];
static int metadata_identity_valid, metadata_digest_valid;
static int metadata_trusted_prepared;
static const char *metadata_map_path;
static int map_identity(const char *path, struct MapIdentity *identity) {
 NvU8 storage[sizeof(struct FileInfoBlock) + 3];
 struct FileInfoBlock *info = (struct FileInfoBlock *)(((NvU32)storage + 3) & ~3UL);
 BPTR lock = Lock((STRPTR)path, ACCESS_READ);
 int result = 0;
 if (lock) {
  if (Examine(lock, info)) {
   identity->disk_key = info->fib_DiskKey; identity->bytes = info->fib_Size;
   identity->date = info->fib_Date; result = 1;
  }
  UnLock(lock);
 }
 return result;
}
static int same_map(const struct MapIdentity *a, const struct MapIdentity *b) {
 return a->disk_key == b->disk_key && a->bytes == b->bytes &&
  a->date.ds_Days == b->date.ds_Days && a->date.ds_Minute == b->date.ds_Minute &&
  a->date.ds_Tick == b->date.ds_Tick;
}
static void metadata_prepare(const struct NativeMap *map, int prepared, int status,
                             unsigned int gain, const struct NativePcm *pcm) {
 metadata_trusted_prepared = prepared == 1 && status == 1 && gain == NPC_PREPARED_GAIN &&
  pcm && pcm->file && pcm->count == NPC_PREPARED_CLIPS && pcm->file_bytes == NPC_PREPARED_BYTES &&
  map && map->preindexed == 1 && map->count == NV_META_MAP_COUNT &&
  map->file_bytes == NV_META_MAP_BYTES && map->archive_size == NV_META_SOURCE_BYTES &&
  metadata_identity_valid && metadata_identity.bytes == NV_META_MAP_BYTES;
 metadata_digest_valid = 0;
}
static int metadata_digest(void) {
 struct MapIdentity current;
 if (!metadata_identity_valid || !map_identity(metadata_map_path, &current) ||
     !same_map(&metadata_identity, &current)) return 0;
 if (!metadata_digest_valid) {
  if (metadata_trusted_prepared) memcpy(metadata_map_digest, nv_meta_map_md5, 16);
  else if (!nv_md5_file(metadata_map_path, metadata_map_digest)) return 0;
  if (!map_identity(metadata_map_path, &current) || !same_map(&metadata_identity, &current)) return 0;
  metadata_digest_valid = 1;
 }
 return 1;
}
static int native_save_name(const char *name) {
 return !memcmp(name, "savegame._", 10) && name[10] >= 'a' && name[10] <= 'z' &&
  name[11] == '_' && !name[12];
}
static void metadata_request(struct NativeMetadataMessage *packet, void *client) {
 struct NvPolicy candidate;
 packet->metadata_result = NV_META_INVALID;
 packet->random_seed = 0; packet->selector_count = 0;
 if (packet->speech.message.mn_Length != sizeof(*packet) ||
     !client || packet->speech.client_task != client || !native_save_name(packet->filename) ||
     !packet->blob_version || packet->reserved || packet->capacity > NV_METADATA_MAX_BLOB ||
     (packet->capacity && !packet->blob)) return;
 if (packet->speech.command == NS_METADATA_LOAD) {
  int present = nv_metadata_presence(packet->filename);
  packet->bytes = 0;
  if (present != NV_META_OK) {
   packet->metadata_result = present;
   packet->speech.result = NS_INVALID;
   return;
  }
 }
 if (!metadata_digest()) { packet->metadata_result = NV_META_IO; return; }
 if (packet->speech.command == NS_METADATA_SAVE) {
  if (packet->bytes > packet->capacity) return;
  packet->metadata_result = nv_metadata_save(packet->filename, metadata_map_digest,
   &policy, packet->blob, packet->bytes, packet->blob_version);
 } else {
  candidate = policy;
  packet->bytes = 0;
  packet->metadata_result = nv_metadata_load(packet->filename, metadata_map_digest,
   &candidate, packet->blob, packet->capacity, &packet->bytes, packet->blob_version);
  if (packet->metadata_result == NV_META_OK) {
   packet->random_seed = candidate.random_seed;
   packet->selector_count = candidate.selector_count;
   memcpy(packet->selectors, candidate.selectors, candidate.selector_count * sizeof(*candidate.selectors));
  }
 }
 packet->speech.result = packet->metadata_result == NV_META_OK ? NS_OK : NS_INVALID;
}


static void cancel_voice(void) {
	Disable();
	voice.cancel_generation = voice.generation;
	voice.state = NATIVE_VOICE_CANCELLED;
	voice.eof = 1;
	voice.write_cursor = voice.read_cursor;
	Enable();
	sequence.count = 0;
	voice.remaining = 0;
}

static int next_clip(FILE *archive) {
	NvU16 rate;
	NvU32 remaining;
	if (sequence_index >= sequence.count)
		return 0;
	if (prebuilt.file) {
		if (!native_pcm_select(&prebuilt, sequence.offset[sequence_index],
		                       sequence.header_length[sequence_index], &remaining)) {
			if (prepared_only) puts("PreparedOnly: mapped clip unavailable; refusing speech.");
			return -1;
		}
		rate = 22050;
	} else if (prepared_only || !archive) {
		puts("PreparedOnly: native PCM unavailable; no SOU fallback.");
		return -1;
	} else if (!native_voc_open(archive, sequence.offset[sequence_index],
	                           sequence.header_length[sequence_index], &remaining, &rate) || rate != 22050)
		return -1;
	++sequence_index;
	voice.remaining = remaining;
	voice.clip_rate = rate;
	return 1;
}

static void refill(FILE *archive) {
	NvU16 generation = voice.generation;
	if (voice.state != NATIVE_VOICE_PREFILL && voice.state != NATIVE_VOICE_READY && voice.state != NATIVE_VOICE_PLAYING)
		return;
	while (voice.generation == generation && voice.cancel_generation != generation) {
		NvU16 used = (NvU16)(voice.write_cursor - voice.read_cursor);
		NvU16 count, index, i;
		int next;
		if (used > voice.capacity) {
			voice.state = NATIVE_VOICE_FAILED;
			return;
		}
		if (!voice.remaining) {
			next = next_clip(archive);
			if (next < 0) {
				voice.state = NATIVE_VOICE_FAILED;
				return;
			}
			if (!next) {
				voice.eof = 1;
				break;
			}
		}
		count = voice.capacity - used;
		if (!count)
			break;
		index = voice.write_cursor;
		if (prebuilt.file) {
			NvU16 tail = voice.capacity - (index & (NATIVE_VOICE_CAPACITY - 1));
			if (count > tail) count = tail;
		} else if (count > sizeof(staging)) count = sizeof(staging);
		if (count > voice.remaining) count = voice.remaining;
		if (prebuilt.file) {
			if (fread(voice.pcm + (index & (NATIVE_VOICE_CAPACITY - 1)), 1, count, prebuilt.file) != count) {
				voice.state = NATIVE_VOICE_FAILED;
				return;
			}
		} else if (prepared_only || !archive || fread(staging, 1, count, archive) != count) {
			voice.state = NATIVE_VOICE_FAILED;
			return;
		}
		if (voice.generation != generation || voice.cancel_generation == generation || voice.state == NATIVE_VOICE_PENDING)
			return;
		if (!prebuilt.file) {
#ifdef NATIVE_ASM_LUT
			native_ring_lut_copy(voice.pcm, index, staging, count, amplified_pcm);
#else
			for (i = 0; i < count; ++i)
				voice.pcm[(index + i) & (NATIVE_VOICE_CAPACITY - 1)] = amplified_pcm[staging[i]];
#endif
		}
		voice.remaining -= count;
		voice.write_cursor = index + count;
	}
	if (voice.state == NATIVE_VOICE_PREFILL)
		voice.state = NATIVE_VOICE_READY;
}

int main(int argc, char **argv) {
	struct NativeMap map;
	struct MsgPort port;
	struct NativeSpeechMessage *packet;
	FILE *archive;
	LONG signal;
	long archive_size;
	int quit = 0, result = 20;
	void *client = 0;
	const char *map_path = argc == 3 ? argv[1] : "amiga-talkie.dat";
	const char *archive_path = argc == 3 ? argv[2] : "monster.sou";
	struct DateStamp stamp;
#ifdef NATIVE_DIAGNOSTIC
	FILE *trace = fopen("voice-worker.log", "w");
	if (trace) { fputs("main entered\n", trace); fflush(trace); }
#endif
	if (argc != 0 && argc != 1 && argc != 3) {
		puts("VoiceServer [amiga-talkie.dat monster.sou]");
		return 20;
	}
	prepared_only = native_profile_mode();
	if (prepared_only < 0) {
		puts("Invalid PreparedOnly marker; expected NPC1 newline.");
		return 20;
	}
	if (!native_profile_archive(prepared_only, archive_path, &archive, &archive_size)) {
		puts("Original monster.sou unavailable; use a validated PreparedOnly profile explicitly.");
		return 20;
	}

#ifdef NATIVE_DIAGNOSTIC
	if (trace) { fprintf(trace, "archive opened %ld\n", archive_size); fflush(trace); }
#endif
	DateStamp(&stamp);
	nv_policy_init(&policy, ((NvU32)stamp.ds_Days << 17) ^ ((NvU32)stamp.ds_Minute << 6) ^
	               (NvU32)stamp.ds_Tick ^ (NvU32)FindTask(0));
	if (!native_map_open_policy(&map, map_path, archive_size, &policy)) {
		if (archive) fclose(archive);
		return 20;
	}
	metadata_map_path = map_path;
	metadata_identity_valid = map_identity(map_path, &metadata_identity);
#ifdef NATIVE_DIAGNOSTIC
	if (trace) { fputs("map indexed\n", trace); fflush(trace); }
#endif
	{
		unsigned int gain = 4, configured;
		int status;
		if (prepared_only) {
			if (!native_profile_gain(&gain)) {
				puts("PreparedOnly supports VoiceBoost4 only; rebuild prepared PCM for another gain.");
				goto close_files;
			}
		} else {
			FILE *settings = fopen("VoiceBoost", "r");
			if (settings) {
				if (fscanf(settings, "%u", &configured) == 1 && configured >= 1 && configured <= 8)
					gain = configured;
				fclose(settings);
			}
		}
		status = native_pcm_open(&prebuilt, "native-voice.pcm", gain, archive_size, map.file_bytes);
		if (prepared_only && !native_profile_ready(prepared_only, status, gain, &prebuilt)) {
			puts("PreparedOnly requires the complete matched native-voice.pcm and VoiceBoost4; no SOU fallback.");
			goto close_files;
		}
		if (status < 0) {
			puts("Invalid native-voice.pcm; rebuild the matched native PCM package.");
			goto close_files;
		}
		metadata_prepare(&map, prepared_only, status, gain, &prebuilt);
		if (!status) puts("Native PCM unavailable; using original SOU and runtime LUT.");
		if (status == 2) puts("Native PCM gain differs from VoiceBoost; using original SOU and runtime LUT.");
		if (status == 1) puts("Native PCM ready: signed8 mono22050, direct ring reads.");
		else native_gain_table(amplified_pcm, (unsigned short)gain);
	}
	signal = AllocSignal(-1);
	if (signal < 0)
		goto close_files;
	memset(&voice, 0, sizeof(voice));
	voice.magic = NATIVE_VOICE_MAGIC;
	voice.version = NATIVE_VOICE_VERSION;
	voice.capacity = NATIVE_VOICE_CAPACITY;
	voice.speech_gain = 64;
	voice.clip_rate = 22050;
	voice.output_period = 161;
	voice.worker_task = FindTask(0);
	voice.signal_mask = 1UL << signal;
	voice.pcm = AllocMem(NATIVE_VOICE_CAPACITY, MEMF_PUBLIC | MEMF_FAST | MEMF_CLEAR);
	if (!voice.pcm)
		goto free_signal;
	memset(&port, 0, sizeof(port));
	port.mp_Node.ln_Type = NT_MSGPORT;
	port.mp_Node.ln_Name = NATIVE_SERVER_PORT;
	port.mp_Flags = PA_SIGNAL;
	port.mp_SigBit = signal;
	port.mp_SigTask = voice.worker_task;
	port.mp_MsgList.lh_Head = (struct Node *)&port.mp_MsgList.lh_Tail;
	port.mp_MsgList.lh_TailPred = (struct Node *)&port.mp_MsgList.lh_Head;
	Forbid();
	if (FindPort(NATIVE_SERVER_PORT)) {
		Permit();
		goto free_pcm;
	}
	AddPort(&port);
	Permit();
#ifdef NATIVE_DIAGNOSTIC
	if (trace) { fputs("port registered\n", trace); fclose(trace); }
#endif
	if (argc)
		printf("VoiceServer ready: %lu mappings\n", map.count);
	while (!quit) {
		ULONG signals = Wait(voice.signal_mask | SIGBREAKF_CTRL_C);
		while ((packet = (struct NativeSpeechMessage *)GetMsg(&port)) != 0) {
			if (packet->message.mn_Length < sizeof(*packet)) {
				ReplyMsg(&packet->message);
				continue;
			}
			packet->result = NS_INVALID;
			if (packet->version != NATIVE_SERVER_VERSION || quit) {
				ReplyMsg(&packet->message);
				continue;
			}
			packet->voice = &voice;
			packet->policy = &policy;
			switch (packet->command) {
			case NS_ATTACH:
				if (packet->client_task && (!client || client == packet->client_task)) {
					client = packet->client_task;
					packet->result = NS_OK;
				} else {
					packet->result = NS_BUSY;
				}
				break;
			case NS_PLAY:
				if (client != packet->client_task || !client || !packet->generation)
					break;
				cancel_voice();
				Disable();
				voice.generation = packet->generation;
				voice.cancel_generation = packet->generation - 1;
				voice.read_cursor = voice.write_cursor = 0;
				voice.eof = 0;
				voice.rendered_generation = voice.played_generation = 0;
				voice.state = NATIVE_VOICE_PENDING;
				Enable();
				{
					NvU16 i, j;
					int valid = packet->selector_count <= NV_POLICY_LIMIT;
					int found = -1;
					for (i = 0; valid && i < packet->selector_count; ++i) {
						valid = nv_policy_selector_valid(&policy, &packet->selectors[i]);
						for (j = 0; j < i; ++j)
							if (packet->selectors[i].id == packet->selectors[j].id)
								valid = 0;
					}
					if (valid)
						found = native_speech_lookup_selected(&map, &packet->context, &sequence,
						                                       packet->selectors, packet->selector_count);
					if (found == 1) {
						sequence_index = 0;
						voice.remaining = 0;
						voice.state = NATIVE_VOICE_PREFILL;
						refill(archive);
						packet->result = voice.state == NATIVE_VOICE_FAILED ? NS_IO_ERROR : NS_OK;
					} else {
						voice.eof = 1;
						voice.state = found ? NATIVE_VOICE_FAILED : NATIVE_VOICE_DONE;
						packet->result = found ? NS_INVALID : NS_NO_VOICE;
					}
				}
				break;
			case NS_CANCEL:
			case NS_DETACH:
				if (packet->command == NS_DETACH && !client && packet->client_task) {
					packet->result = NS_OK;
					break;
				}
				if (client == packet->client_task && client) {
					cancel_voice();
					if (packet->command == NS_DETACH)
						client = 0;
					packet->result = NS_OK;
				}
				break;
			case NS_METADATA_SAVE:
			case NS_METADATA_LOAD:
				if (packet->message.mn_Length == sizeof(struct NativeMetadataMessage))
					metadata_request((struct NativeMetadataMessage *)packet, client);
				break;
			case NS_QUIT:
				packet->result = client ? NS_BUSY : NS_OK;
				quit = client == 0;
				break;
			}
			ReplyMsg(&packet->message);
		}
		if ((signals & SIGBREAKF_CTRL_C) && !client)
			quit = 1;
		if (!quit)
			refill(archive);
	}
	Forbid();
	RemPort(&port);
	while ((packet = (struct NativeSpeechMessage *)GetMsg(&port)) != 0) {
		if (packet->message.mn_Length >= sizeof(*packet))
			packet->result = NS_INVALID;
		ReplyMsg(&packet->message);
	}
	Permit();
	result = 0;
free_pcm:
	FreeMem(voice.pcm, NATIVE_VOICE_CAPACITY);
free_signal:
	FreeSignal(signal);
close_files:
	native_pcm_close(&prebuilt);
	native_map_close(&map);
	if (archive) fclose(archive);
	return result;
}


#include <stddef.h>
typedef char NativeMapMustBe32Bytes[sizeof(struct NativeMap) == 32 ? 1 : -1];
typedef char NativeEntryMustBe8Bytes[sizeof(struct NativeMapEntry) == 8 ? 1 : -1];
typedef char NativeMapTailMustMatch[
    offsetof(struct NativeMap, data_start) == 20 &&
    offsetof(struct NativeMap, file_bytes) == 24 &&
    offsetof(struct NativeMap, preindexed) == 28 ? 1 : -1];
