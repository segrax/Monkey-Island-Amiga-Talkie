#include "native_server.h"
#include "native_metadata_store.h"
#include "native_md5.h"
#include "native_map.h"
#include "native_pcm.h"
#include "metadata_bindings.h"
#include "prepared_bindings.h"
#include <dos/dos.h>
#include <proto/dos.h>
#include <string.h>
struct DosLibrary *DOSBase;
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


void probe_map(const char *path) {
 metadata_map_path=path; metadata_digest_valid=0;
 metadata_identity_valid=map_identity(path,&metadata_identity);
}
struct NvPolicy *probe_policy(void) { return &policy; }
void probe_request(struct NativeMetadataMessage *packet,void *client) { metadata_request(packet,client); }

void probe_prepared(const struct NativeMap *map,int prepared,int status,unsigned int gain,const struct NativePcm *pcm) { metadata_prepare(map,prepared,status,gain,pcm); }
int probe_trusted(void) { return metadata_trusted_prepared; }
