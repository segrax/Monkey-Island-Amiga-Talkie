// Test the production startup extension and memory fallback with Exec mocks.
#include <cstring>
#include <stdexcept>
#include <vector>
struct WBStartup { struct { unsigned short mn_Length; } sm_Message; };
#include "../native/audio/worker_startup.h"
constexpr unsigned long MEMF_PUBLIC = 1, MEMF_FAST = 4, MEMF_CLEAR = 65536;
constexpr unsigned long NATIVE_VOICE_CAPACITY = 16384;
static std::vector<unsigned long> requests;
static bool have_fast, have_any;
static char ring[NATIVE_VOICE_CAPACITY];
static void require(bool ok) { if (!ok) throw std::runtime_error("Worker startup check failed"); }
static void *AllocMem(unsigned long size, unsigned long flags) {
    require(size == sizeof(ring)); requests.push_back(flags);
    return (flags & MEMF_FAST ? have_fast : have_any) ? ring : nullptr;
}
#include "../native/audio/worker_memory.h"
int main() {
    NvWorkerStartup startup{};
    auto argv = reinterpret_cast<char **>(&startup);
    require(!nv_worker_startup(0, nullptr));
    require(!nv_worker_startup(1, argv));
    startup.wb.sm_Message.mn_Length = sizeof(WBStartup);
    require(!nv_worker_startup(0, argv));
    startup.wb.sm_Message.mn_Length = sizeof(startup);
    require(!nv_worker_startup(0, argv));
    startup.magic = NV_STARTUP_MAGIC;
    require(nv_worker_startup(0, argv) == &startup);
    nv_startup_error(nullptr, "ordinary CLI launch");
    nv_startup_error(&startup, "Missing map");
    require(!std::strcmp(startup.error, "Missing map"));
    char long_error[256]; std::memset(long_error, 'x', sizeof(long_error));
    long_error[255] = 0;
    nv_startup_error(&startup, long_error);
    require(std::strlen(startup.error) == sizeof(startup.error) - 1);
    for (bool fast : {false, true}) for (bool any : {false, true}) {
        requests.clear(); have_fast = fast; have_any = any;
        require(nv_alloc_voice_ring() == (fast || any ? ring : nullptr));
        require(requests[0] == (MEMF_PUBLIC | MEMF_FAST | MEMF_CLEAR));
        require(requests.size() == (fast ? 1u : 2u));
        if (!fast) require(requests[1] == (MEMF_PUBLIC | MEMF_CLEAR));
    }
}
