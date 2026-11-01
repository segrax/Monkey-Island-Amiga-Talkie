/* Local native experiment, GPL-3.0-or-later. */
#include "native_metadata.h"
#include "native_provenance.h"
#include "native_driver.h"
#include "native_client.h"

extern struct NativeSpeechContext nv_dialogue_context;
extern NvU16 nv_dialogue_valid, nv_dialogue_next_segment;
static NvU8 metadata[NV_METADATA_BYTES];
volatile NvU32 nv_metadata_saves, nv_metadata_loads, nv_metadata_rejected;
static void put(NvU8 **p, NvU16 value) {
	*(*p)++ = (NvU8)(value >> 8); *(*p)++ = (NvU8)value;
}
static NvU16 get(const NvU8 **p) {
	NvU16 value = (NvU16)((*p)[0] << 8) | (*p)[1]; *p += 2; return value;
}
static void context_write(NvU8 *p) {
	struct NativeSpeechContext *c = &nv_dialogue_context;
	unsigned i;
	put(&p, nv_dialogue_valid); put(&p, nv_dialogue_next_segment);
	put(&p, c->room); put(&p, c->resource_room); put(&p, c->actor);
	put(&p, c->kind); put(&p, c->script); put(&p, c->segment);
	put(&p, (NvU16)(c->message_offset >> 16)); put(&p, (NvU16)c->message_offset);
	for (i = 0; i < NATIVE_ORIGIN_BYTES; ++i) *p++ = (NvU8)c->origin[i];
	put(&p, c->text_length);
	for (i = 0; i < NATIVE_TEXT_BYTES; ++i) *p++ = c->text[i];
}
static int context_read(const NvU8 *p, int apply) {
	struct NativeSpeechContext *c = &nv_dialogue_context;
	NvU16 values[8], length, active, next;
	NvU32 offset;
	const NvU8 *origin, *text;
	unsigned i, terminated = 0;
	active = get(&p); next = get(&p);
	for (i = 0; i < 8; ++i) values[i] = get(&p);
	offset = ((NvU32)values[6] << 16) | values[7];
	origin = p;
	for (i = 0; i < NATIVE_ORIGIN_BYTES; ++i) if (!*p++) terminated = 1;
	length = get(&p); text = p;
	if (active > 1 || length > NATIVE_TEXT_BYTES || !terminated ||
		(active && (values[0] > 255 || values[1] > 255 || values[2] > 255 ||
		values[3] < NATIVE_GLOBAL || values[3] > NATIVE_EXCD || offset > 0x7fffffffUL))) return 0;
	if (apply) {
		c->room = values[0]; c->resource_room = values[1]; c->actor = values[2];
		c->kind = values[3]; c->script = values[4]; c->segment = values[5]; c->message_offset = offset;
		for (i = 0; i < NATIVE_ORIGIN_BYTES; ++i) c->origin[i] = (char)origin[i];
		c->text_length = length;
		for (i = 0; i < NATIVE_TEXT_BYTES; ++i) c->text[i] = text[i];
		nv_dialogue_valid = active; nv_dialogue_next_segment = next;
	}
	return 1;
}
NvU32 nv_metadata_export(NvU8 *output, NvU32 capacity) {
	if (!output || capacity < NV_METADATA_BYTES || !nv_provenance_export(output, 5784)) return 0;
	context_write(output + 5784);
	return NV_METADATA_BYTES;
}
int nv_metadata_import(const NvU8 *input, NvU32 bytes) {
	if (!input || bytes != NV_METADATA_BYTES || !nv_provenance_import(input, 5784, 0) ||
		!context_read(input + 5784, 0)) return 0;
	nv_provenance_import(input, 5784, 1);
	context_read(input + 5784, 1);
	return 1;
}
void nv_metadata_clear(void) {
	nv_provenance_clear(); nv_dialogue_valid = nv_dialogue_next_segment = 0;
}
void nv_metadata_save(NvU32 slot) {
	NvU32 bytes;
	if (!slot || slot > 26 || !(nv_control.flags & NV_CONTROL_RUNNING)) return;
	nv_game_cancel();
	bytes = nv_metadata_export(metadata, sizeof(metadata));
	if (bytes && nv_game_metadata_save((const char *)(nv_control.game_globals + 0x3a4),
		metadata, bytes, NV_METADATA_VERSION) == 1) ++nv_metadata_saves;
	else ++nv_metadata_rejected;
}
void nv_metadata_load_begin(void) {
	if (nv_control.flags & NV_CONTROL_RUNNING) nv_game_cancel();
}
void nv_metadata_load(NvU32 slot) {
	NvU32 bytes = 0;
	if (!slot || slot > 26 || !(nv_control.flags & NV_CONTROL_RUNNING)) return;
	if (nv_game_metadata_load((const char *)(nv_control.game_globals + 0x3a4),
		metadata, sizeof(metadata), &bytes, NV_METADATA_VERSION) == 1 && nv_metadata_import(metadata, bytes) &&
		nv_game_metadata_commit(1))
		++nv_metadata_loads;
	else { nv_game_metadata_commit(0); nv_metadata_clear(); ++nv_metadata_rejected; }
}
