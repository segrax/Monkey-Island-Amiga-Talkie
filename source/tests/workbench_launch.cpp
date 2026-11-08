// Exercise the production Workbench adapter with mocked AmigaDOS calls.
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
using BPTR = long;
using LONG = long;
using APTR = void *;
constexpr long MODE_NEWFILE = 1006;
struct WBArg { BPTR wa_Lock; };
struct WBStartup { long sm_NumArgs; WBArg *sm_ArgList; };
static std::vector<std::string> calls;
static BPTR directory, console;
static LONG execute_result;
static void require(bool ok) { if (!ok) throw std::runtime_error("Workbench launch check failed"); }
static BPTR CurrentDir(BPTR next) {
    calls.push_back("dir:" + std::to_string(next));
    auto old = directory; directory = next; return old;
}
static BPTR Open(const char *name, LONG mode) {
    require(directory == 123 && mode == MODE_NEWFILE);
    require(std::string(name) == "CON:0/20/640/160/Monkey Island Talkie");
    calls.push_back("open"); return console;
}
static LONG Execute(const char *command, BPTR input, BPTR output) {
    require(directory == 123 && input == 0 && output == console);
    require(std::string(command) == "Stack 65536\nMonkeyTalkie\n");
    calls.push_back("execute"); return execute_result;
}
static LONG Write(BPTR file, APTR bytes, LONG size) {
    require(file == console);
    std::string text(static_cast<char *>(bytes), size);
    require(text.find("Press Return") != std::string::npos);
    require((text.find("C:Run") != std::string::npos) == (execute_result == 0));
    calls.push_back("write"); return size;
}
static LONG Read(BPTR file, APTR, LONG size) {
    require(file == console && size > 0); calls.push_back("read"); return 1;
}
static LONG Close(BPTR file) { require(file == console); calls.push_back("close"); return 1; }
#include "../native/audio/workbench_launch.h"

int main() {
    WBArg arg{123}; WBStartup wb{1, &arg};
    require(launch_workbench(nullptr) == 20 && calls.empty());
    for (WBStartup bad : {WBStartup{0, &arg}, WBStartup{1, nullptr}})
        require(launch_workbench(&bad) == 20 && calls.empty());
    arg.wa_Lock = 0;
    require(launch_workbench(&wb) == 20 && calls.empty());
    arg.wa_Lock = 123;
    directory = 456; console = 0;
    require(launch_workbench(&wb) == 20 && directory == 456);
    require(calls == std::vector<std::string>{"dir:123", "open", "dir:456"});
    for (LONG result : {0L, -1L}) {
        calls.clear(); console = 789; execute_result = result;
        require(launch_workbench(&wb) == (result ? 0 : 20) && directory == 456);
        require(calls == std::vector<std::string>{"dir:123", "open", "execute", "write", "read", "close", "dir:456"});
    }
}
