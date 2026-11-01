#include "native_metadata_store.h"
#include "native_md5.h"
static struct NvPolicy policy;
static struct NvMd5 md5;
struct NvPolicy *probe_policy(void) { return &policy; }
struct NvMd5 *probe_md5(void) { return &md5; }
