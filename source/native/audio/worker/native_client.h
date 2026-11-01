/* GPL-3.0-or-later */
#ifndef NATIVE_SPEECH_CLIENT_H
#define NATIVE_SPEECH_CLIENT_H
#include "native_server.h"

int nv_game_play(const struct NativeSpeechContext *context);
void nv_game_cancel(void);
void nv_game_poll(void);
int nv_game_active(void);
int nv_game_set_policy(struct NvPolicy *policy);
int nv_game_program(NvU16 kind, NvU16 resource_room, NvU16 script, NvU32 offset);
void nv_game_shutdown(void);

/* Called from game task context only, with interrupts/task switching enabled.
 * No DOS I/O, CRT state or blocking waits occur in play/cancel/poll.
 * Shutdown runs after audio IRQ hooks stop using the shared voice.
 */
int nv_game_metadata_save(const char *filename, const unsigned char *blob,
 unsigned long bytes, unsigned short blob_version);
int nv_game_metadata_load(const char *filename, unsigned char *blob,
 unsigned long capacity, unsigned long *bytes, unsigned short blob_version);
int nv_game_metadata_commit(int accepted);
#endif
