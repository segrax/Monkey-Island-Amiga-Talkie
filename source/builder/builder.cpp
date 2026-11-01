// SPDX-License-Identifier: GPL-3.0-or-later
#include "builder.hpp"
#include <algorithm>
#include <chrono>
#include <random>
#include <sstream>
#include <stdexcept>

namespace talkie {
static std::string lower(std::string text) {
    for (char &c : text)
        if (c >= 'A' && c <= 'Z')
            c += 32;
    return text;
}
static bool within(const fs::path &path, const fs::path &parent) {
    auto a = path.begin(), b = parent.begin();
    for (; b != parent.end(); ++a, ++b) {
        if (a == path.end())
            return false;
#ifdef _WIN32
        if (lower(a->u8string()) != lower(b->u8string()))
            return false;
#else
        if (*a != *b)
            return false;
#endif
    }
    return true;
}
static void text_file(const fs::path &path, const std::string &text) {
    write_file(path, Bytes(text.begin(), text.end()));
}
std::string build(const Options &o, const std::function<void(const std::string &)> &progress) {
    auto source = fs::weakly_canonical(o.amiga), output = fs::weakly_canonical(o.output);
    if (fs::is_directory(source / "Rooms"))
        source /= "Rooms";
    if (fs::exists(output))
        throw std::runtime_error("Output already exists. Choose a new folder.");
    for (auto input : {source, fs::weakly_canonical(o.sou).parent_path(),
                       fs::weakly_canonical(o.engine).parent_path()})
        if (within(input, output) || within(output, input))
            throw std::runtime_error("Choose an output folder separate from your input folders.");
    auto pins = payload_json("supported-inputs.json");
    std::map<std::string, fs::path> available;
    for (const auto &file : fs::directory_iterator(source))
        if (file.is_regular_file())
            available.emplace(lower(file.path().filename().u8string()), file.path());
    std::map<std::string, Bytes> rooms;
    for (auto it = pins["rooms"].begin(); it != pins["rooms"].end(); ++it) {
        auto found = available.find(lower(it.key()));
        if (found == available.end())
            throw std::runtime_error("Missing Amiga file: " + it.key());
        auto data = read_file(found->second);
        if (sha(data) != it.value().get<std::string>())
            throw std::runtime_error("Unsupported or damaged Amiga file: " + it.key());
        rooms.emplace(it.key(), std::move(data));
    }
    progress("[1/4] Original Amiga files verified.");
    auto engine =
        patch_engine(original_engine(o.engine, pins["original_engine"].get<std::string>()));
    if (sha(engine) != pins["hybrid_engine"].get<std::string>())
        throw std::runtime_error("Patched engine checksum failed.");
    auto archive = read_file(o.sou);
    auto archive_hash = sha(archive);
    Json profile;
    for (const auto &candidate : pins["profiles"])
        if (candidate["source_sha256"] == archive_hash) {
            profile = candidate;
            break;
        }
    if (profile.is_null())
        throw std::runtime_error("Unsupported monster.sou. Select the uncompressed English "
                                 "Ultimate Talkie archive listed in assets/supported-inputs.json.");
    auto map = reconstruct_map(rooms, static_cast<std::uint32_t>(archive.size()));
    if (sha(map.bytes) != profile["map_sha256"].get<std::string>())
        throw std::runtime_error("Dialogue map checksum failed.");
    progress("[2/4] Hybrid engine and dialogue map verified.");
    // Publish only a verified, complete folder; do not replace installations.
    fs::create_directories(output.parent_path());
    std::random_device random;
    auto staging = output;
    staging +=
        fs::u8path(".building-" + std::to_string(random()) + "-" +
                   std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    if (!fs::create_directory(staging))
        throw std::runtime_error("Cannot create a new build staging folder.");
    fs::create_directory(staging / "Rooms");
    for (const auto &room : rooms)
        write_file(staging / "Rooms" / fs::u8path(room.first), room.second);
    write_file(staging / "Monkey_Talkie", engine);
    write_file(staging / "amiga-talkie.dat", map.bytes);
    for (const std::string name : {"MonkeyTalkie", "module.json"})
        write_file(staging / name, payload("runtime/" + name));
    write_file(staging / "VoiceServer", payload(profile["worker"].get<std::string>()));
    progress("[3/4] Preparing and verifying speech...");
    prepare_pcm(archive, map, staging / "native-voice.pcm",
                profile["pcm_sha256"].get<std::string>());
    text_file(staging / "PreparedOnly", "NPC1\n");
    text_file(staging / "VoiceBoost", "4\n");
    const std::string command = "MonkeyTalkie --skip-pirate-check\n";
    text_file(staging / "Play", command);
    fs::create_directory(staging / "S");
    text_file(staging / "S" / "startup-sequence", command);
    std::ostringstream coverage;
    coverage << "Profile: " << profile["label"].get<std::string>() << "\nMapped keys: " << map.count
             << "\nSupplemental recording keys unavailable in this SOU: " << map.omitted
             << "\nExisting dialogue coverage limitations still apply. No substitute audio was "
                "invented.\n";
    text_file(staging / "VOICE-COVERAGE.txt", coverage.str());
    Json manifest = {{"complete", true},
                     {"profile", profile["label"]},
                     {"source_sha256", archive_hash},
                     {"files", Json::object()}};
    for (const auto &file : fs::recursive_directory_iterator(staging))
        if (file.is_regular_file())
            manifest["files"][fs::relative(file.path(), staging).generic_u8string()] =
                sha_file(file.path());
    text_file(staging / "build-manifest.json", manifest.dump(2) + "\n");
    if (fs::exists(output))
        throw std::runtime_error(
            "Output appeared during the build; the verified .building folder was retained.");
    fs::rename(staging, output);
    progress("[4/4] Finished. All output checksums passed.");
    std::string summary =
        "Created: " + output.u8string() +
        "\n\nCopy its contents to your Amiga. In that folder, run:\nExecute Play\n";
    if (map.omitted)
        summary +=
            "\nNote: " + std::to_string(map.omitted) +
            " supplemental speech mappings are unavailable in this SOU. See VOICE-COVERAGE.txt.\n";
    return summary;
}
} // namespace talkie
