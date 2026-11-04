#pragma once
#include <cstdint>
#include <filesystem>
#include <functional>
#include <json.hpp>
#include <map>
#include <string>
#include <vector>
namespace talkie {
namespace fs = std::filesystem;
using Bytes = std::vector<std::uint8_t>;
using Json = nlohmann::ordered_json;
struct Asset {
    const char *name;
    const unsigned char *data;
    std::size_t size;
};
const std::vector<Asset> &assets();
Bytes payload(const std::string &name);
Json payload_json(const std::string &name);
std::string sha(const Bytes &data);
std::string sha_file(const fs::path &path);
Bytes read_file(const fs::path &path);
void write_file(const fs::path &path, const Bytes &data);
void verify_payload();
Bytes unhex(const std::string &value);
std::uint32_t be32(const Bytes &data, std::size_t at);
void be32(Bytes &data, std::size_t at, std::uint32_t value);
struct VoiceRef {
    std::uint32_t offset, header;
    bool operator<(const VoiceRef &b) const {
        return offset < b.offset || (offset == b.offset && header < b.header);
    }
};
struct Map {
    Bytes bytes;
    std::vector<VoiceRef> references;
    std::size_t count, omitted;
};
Bytes original_engine(const fs::path &path, const std::string &expected);
Bytes patch_engine(const Bytes &original);
Map reconstruct_map(const std::map<std::string, Bytes> &rooms, std::uint32_t archive_size);
std::pair<std::size_t, std::size_t> voc(const Bytes &archive, VoiceRef reference);
void prepare_pcm(const Bytes &archive, const Map &map, const fs::path &output,
                 const std::string &expected);
struct Options {
    fs::path amiga, sou, engine, output;
};
std::string build(const Options &options, const std::function<void(const std::string &)> &progress);
void self_test();
} // namespace talkie
