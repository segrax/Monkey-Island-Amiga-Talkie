/* GPL-3.0-or-later. Optional extension to the ordinary Workbench message.
 * The parent owns this storage until the worker replies and is unloaded. */
#ifndef NV_WORKER_STARTUP_H
#define NV_WORKER_STARTUP_H
/* Include after <workbench/startup.h>. */
#define NV_STARTUP_MAGIC 0x4e565331UL
struct NvWorkerStartup {
 struct WBStartup wb;
 unsigned long magic;
 char error[192];
};
static struct NvWorkerStartup *nv_worker_startup(int argc, char **argv) {
 struct NvWorkerStartup *startup;
 if (argc || !argv) return 0;
 startup = (struct NvWorkerStartup *)argv;
 if (startup->wb.sm_Message.mn_Length != sizeof(*startup) ||
     startup->magic != NV_STARTUP_MAGIC) return 0;
 return startup;
}
static void nv_startup_error(struct NvWorkerStartup *startup, const char *text) {
 unsigned int i = 0;
 if (!startup) return;
 while (text[i] && i < sizeof(startup->error) - 1) {
  startup->error[i] = text[i];
  ++i;
 }
 startup->error[i] = 0;
}
#endif
