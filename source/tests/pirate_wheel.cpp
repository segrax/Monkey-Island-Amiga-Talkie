#include "builder.hpp"
#include <stdexcept>

using namespace talkie;
static void require(bool ok) {
    if (!ok) throw std::runtime_error("Pirate-wheel patch test failed");
}
static void rejected(const Bytes &data, const Json &recipe) {
    bool failed = false;
    try { patch_game_data(data, recipe); }
    catch (const std::exception &) { failed = true; }
    require(failed);
}
int main() {
    const Bytes input{0x69, 0x68, 0x6b, 0x6a, 0x6d};
    const Bytes output{0x69, 0x61, 0x60, 0x6a, 0x6d};
    const Json recipe = {{"source_sha256", sha(input)}, {"sha256", sha(output)},
                         {"xor", 0x69}, {"patches", Json::array({
                             {{"offset", 1}, {"expected", "0102"}, {"replacement", "0809"}}
                         })}};
    require(patch_game_data(input, recipe) == output);
    require(input == Bytes({0x69, 0x68, 0x6b, 0x6a, 0x6d}));
    auto bad = recipe;
    bad["source_sha256"] = sha(output); rejected(input, bad);
    bad = recipe; bad["sha256"] = sha(input); rejected(input, bad);
    bad = recipe; bad["xor"] = 256; rejected(input, bad);
    bad = recipe; bad["patches"][0]["offset"] = 4; rejected(input, bad);
    bad = recipe; bad["patches"][0]["offset"] = 99; rejected(input, bad);
    bad = recipe; bad["patches"][0]["expected"] = "0000"; rejected(input, bad);
    bad = recipe; bad["patches"][0]["replacement"] = "08"; rejected(input, bad);
    bad = recipe; bad["patches"][0]["replacement"] = "0x"; rejected(input, bad);
}
