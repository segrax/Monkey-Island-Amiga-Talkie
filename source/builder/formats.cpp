// SPDX-License-Identifier: GPL-3.0-or-later
#include "builder.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <fstream>
#include <limits>
#include <picosha2.h>
#include <set>
#include <stdexcept>

namespace talkie {
static void require(bool value, const std::string &message) {
    if (!value)
        throw std::runtime_error(message);
}
Bytes payload(const std::string &name) {
    for (const auto &asset : assets())
        if (name == asset.name)
            return Bytes(asset.data, asset.data + asset.size);
    throw std::runtime_error("Missing embedded payload: " + name);
}
Json payload_json(const std::string &name) {
    auto bytes = payload(name);
    return Json::parse(bytes.begin(), bytes.end());
}
std::string sha(const Bytes &bytes) {
    return picosha2::hash256_hex_string(bytes);
}
std::string sha_file(const fs::path &path) {
    std::ifstream file(path, std::ios::binary);
    require(bool(file), "Cannot open file for verification: " + path.u8string());
    picosha2::hash256_one_by_one hasher;
    std::array<char, 65536> buffer{};
    while (file) {
        file.read(buffer.data(), buffer.size());
        auto n = file.gcount();
        hasher.process(buffer.begin(), buffer.begin() + n);
    }
    require(file.eof(), "File read failed: " + path.u8string());
    hasher.finish();
    return picosha2::get_hash_hex_string(hasher);
}
Bytes read_file(const fs::path &path) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    require(bool(file), "Cannot open file: " + path.u8string());
    auto size = file.tellg();
    require(size >= 0 && size <= std::numeric_limits<std::int32_t>::max(),
            "Unsupported file size.");
    Bytes bytes(static_cast<std::size_t>(size));
    file.seekg(0);
    if (!bytes.empty())
        file.read(reinterpret_cast<char *>(bytes.data()), bytes.size());
    require(bool(file), "File read failed: " + path.u8string());
    return bytes;
}
void write_file(const fs::path &path, const Bytes &bytes) {
    std::ofstream file(path, std::ios::binary);
    require(bool(file), "Cannot create file: " + path.u8string());
    if (!bytes.empty())
        file.write(reinterpret_cast<const char *>(bytes.data()), bytes.size());
    file.flush();
    require(bool(file), "File write failed: " + path.u8string());
}
void verify_payload() {
    auto manifest = payload_json("sha256.json");
    for (auto it = manifest.begin(); it != manifest.end(); ++it)
        require(sha(payload(it.key())) == it.value().get<std::string>(),
                "Embedded payload checksum failed: " + it.key());
}
Bytes unhex(const std::string &text) {
    require(text.size() % 2 == 0, "Invalid hex string.");
    Bytes out;
    auto digit = [](char c) -> unsigned {
        if (c >= '0' && c <= '9')
            return c - '0';
        if (c >= 'a' && c <= 'f')
            return c - 'a' + 10;
        if (c >= 'A' && c <= 'F')
            return c - 'A' + 10;
        throw std::runtime_error("Invalid hex digit.");
    };
    for (std::size_t i = 0; i < text.size(); i += 2)
        out.push_back(static_cast<std::uint8_t>((digit(text[i]) << 4) | digit(text[i + 1])));
    return out;
}
std::uint32_t be32(const Bytes &data, std::size_t at) {
    require(at <= data.size() && data.size() - at >= 4, "Truncated binary structure.");
    return (std::uint32_t(data[at]) << 24) | (std::uint32_t(data[at + 1]) << 16) |
           (std::uint32_t(data[at + 2]) << 8) | data[at + 3];
}
void be32(Bytes &data, std::size_t at, std::uint32_t value) {
    require(at <= data.size() && data.size() - at >= 4, "Binary write out of bounds.");
    for (unsigned i = 0; i < 4; ++i)
        data[at + i] = static_cast<std::uint8_t>(value >> (24 - 8 * i));
}
static void le(Bytes &bytes, std::uint32_t value, unsigned n) {
    for (unsigned i = 0; i < n; ++i)
        bytes.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
}
static std::uint16_t le16(const Bytes &b, std::size_t at) {
    require(at <= b.size() && b.size() - at >= 2, "Truncated little-endian field.");
    return b[at] | (std::uint16_t(b[at + 1]) << 8);
}
static void append(Bytes &a, const Bytes &b) {
    a.insert(a.end(), b.begin(), b.end());
}
static std::string lower(std::string text) {
    for (char &c : text)
        if (c >= 'A' && c <= 'Z')
            c += 32;
    return text;
}

Bytes original_engine(const fs::path &path, const std::string &expected) {
    auto data = read_file(path);
    if (sha(data) == expected)
        return data;
    if (data.size() == 901120 && std::memcmp(data.data(), "DOS\0", 4) == 0) {
        for (std::size_t at = 0; at < data.size(); at += 512) {
            auto n = data[at + 432];
            if (n > 30 ||
                lower(std::string(data.begin() + at + 433, data.begin() + at + 433 + n)) !=
                    "monkey_island" ||
                be32(data, at) != 2 || be32(data, at + 508) != 0xfffffffd)
                continue;
            auto size = be32(data, at + 324), block = be32(data, at + 16);
            Bytes result;
            std::set<std::uint32_t> seen;
            while (block) {
                require(block < data.size() / 512 && seen.insert(block).second,
                        "Invalid ADF block chain.");
                std::size_t pos = std::size_t(block) * 512;
                auto len = be32(data, pos + 12);
                require(be32(data, pos) == 8 && len > 0 && len <= 488, "Invalid OFS block.");
                result.insert(result.end(), data.begin() + pos + 24, data.begin() + pos + 24 + len);
                block = be32(data, pos + 16);
            }
            require(size <= result.size(), "Truncated ADF executable.");
            result.resize(size);
            if (sha(result) == expected)
                return result;
        }
    }
    throw std::runtime_error(
        "Select the supported original Monkey_Island executable or original DOS0 disk 1 ADF.");
}
static Bytes base64(const std::string &text) {
    static const std::string alphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    Bytes result;
    std::uint32_t bits = 0;
    unsigned count = 0;
    for (char c : text) {
        if (c == '=')
            break;
        auto n = alphabet.find(c);
        require(n != std::string::npos, "Invalid patch base64.");
        bits = (bits << 6) | static_cast<unsigned>(n);
        count += 6;
        if (count >= 8) {
            count -= 8;
            result.push_back(static_cast<std::uint8_t>(bits >> count));
        }
    }
    return result;
}
Bytes patch_engine(const Bytes &original) {
    Bytes result;
    for (const auto &op : payload_json("patches/engine.json")) {
        if (op[0] == "copy") {
            auto at = op[1].get<std::size_t>(), n = op[2].get<std::size_t>();
            require(at <= original.size() && n <= original.size() - at, "Invalid patch range.");
            result.insert(result.end(), original.begin() + at, original.begin() + at + n);
        } else if (op[0] == "add")
            append(result, base64(op[1].get<std::string>()));
        else
            throw std::runtime_error("Unknown patch operation.");
    }
    return result;
}
Map reconstruct_map(const std::map<std::string, Bytes> &rooms, std::uint32_t archive_size) {
    auto r = payload_json("patches/map-recipe.json");
    std::vector<Bytes> streams, suffixes;
    for (const auto &s : r["streams"]) {
        Bytes stream;
        auto raw = rooms.at(s[0].get<std::string>());
        auto x = s[1].get<unsigned>();
        for (auto v : raw) {
            unsigned b = v ^ x;
            if (b >= 'A' && b <= 'Z')
                b += 32;
            if ((b >= 'a' && b <= 'z') || (b >= '0' && b <= '9'))
                stream.push_back(static_cast<std::uint8_t>(b));
        }
        streams.push_back(std::move(stream));
    }
    for (const auto &pieces : r["suffixes"]) {
        Bytes suffix;
        for (const auto &p : pieces) {
            auto &stream = streams.at(p[0].get<std::size_t>());
            auto at = p[1].get<std::size_t>(), n = p[2].get<std::size_t>();
            require(at <= stream.size() && n <= stream.size() - at,
                    "Invalid dialogue source range.");
            suffix.insert(suffix.end(), stream.begin() + at, stream.begin() + at + n);
        }
        suffixes.push_back(std::move(suffix));
    }
    struct Entry {
        Bytes key;
        VoiceRef voice;
    };
    std::vector<Entry> entries;
    std::set<VoiceRef> refs;
    std::size_t omitted = 0;
    for (const auto &e : r["entries"]) {
        auto off = e[2].get<std::uint32_t>();
        if (off >= archive_size) {
            ++omitted;
            continue;
        }
        auto prefix = e[0].get<std::string>();
        Bytes key(prefix.begin(), prefix.end());
        append(key, suffixes.at(e[1].get<std::size_t>()));
        VoiceRef voice{off, e[3].get<std::uint32_t>()};
        entries.push_back({std::move(key), voice});
        refs.insert(voice);
    }
    Bytes header = unhex(r["header"].get<std::string>()),
          policy = unhex(r["policy"].get<std::string>()), records;
    std::size_t start = 64 + entries.size() * 8 + policy.size();
    std::vector<std::pair<std::uint32_t, std::uint32_t>> index;
    for (const auto &e : entries) {
        std::uint32_t hash = 2166136261;
        for (auto b : e.key)
            hash = (hash ^ b) * 16777619U;
        index.push_back({hash, static_cast<std::uint32_t>(start + records.size())});
        require(e.key.size() < 2048, "Oversize dialogue key.");
        le(records, static_cast<std::uint32_t>(e.key.size()), 2);
        append(records, e.key);
        le(records, e.voice.offset, 4);
        le(records, e.voice.header, 4);
    }
    std::uint32_t fields[] = {archive_size,
                              static_cast<std::uint32_t>(entries.size()),
                              64,
                              static_cast<std::uint32_t>(64 + entries.size() * 8),
                              static_cast<std::uint32_t>(policy.size() / 16),
                              static_cast<std::uint32_t>(start),
                              static_cast<std::uint32_t>(start + records.size()),
                              static_cast<std::uint32_t>(records.size())};
    for (unsigned i = 0; i < 8; ++i)
        be32(header, 8 + 4 * i, fields[i]);
    Bytes output = header;
    std::sort(index.begin(), index.end());
    for (const auto &item : index) {
        Bytes row(8);
        be32(row, 0, item.first);
        be32(row, 4, item.second);
        append(output, row);
    }
    append(output, policy);
    append(output, records);
    return {std::move(output), std::vector<VoiceRef>(refs.begin(), refs.end()), entries.size(),
            omitted};
}
std::pair<std::size_t, std::size_t> voc(const Bytes &archive, VoiceRef ref) {
    std::size_t off = ref.offset, head = ref.header;
    require(head >= 8 && head <= 132 && !(head & 1) && off <= archive.size() &&
                archive.size() - off >= head + 32,
            "Invalid speech reference.");
    require(std::memcmp(archive.data() + off, "VCTL", 4) == 0 && be32(archive, off + 4) == head,
            "VCTL reference mismatch.");
    auto start = off + head;
    require(std::memcmp(archive.data() + start, "Creative Voice File\x1a", 20) == 0,
            "Missing VOC signature.");
    auto data = le16(archive, start + 20), version = le16(archive, start + 22),
         checksum = le16(archive, start + 24);
    require(data >= 26 && checksum == ((~version + 0x1234) & 65535), "Invalid VOC header.");
    auto block = start + data;
    require(block <= archive.size() && archive.size() - block >= 6, "Truncated VOC block.");
    unsigned length = archive[block + 1] | (unsigned(archive[block + 2]) << 8) |
                      (unsigned(archive[block + 3]) << 16);
    require(archive[block] == 1 && length >= 3 && archive[block + 4] == 0xd3 &&
                archive[block + 5] == 0,
            "Expected 22050 Hz PCM8 VOC.");
    std::size_t size = length - 2, at = block + 6;
    require(at < archive.size() && size < archive.size() - at && archive[at + size] == 0,
            "Invalid VOC end.");
    return {at, size};
}
void prepare_pcm(const Bytes &archive, const Map &map, const fs::path &path,
                 const std::string &expected) {
    std::array<std::uint8_t, 256> table{};
    for (int i = 0; i < 256; ++i) {
        int s = i - 128, m = std::abs(s), limit = s < 0 ? 128 : 127,
            scaled = m * 4 * limit / (limit + 3 * m);
        table[i] = static_cast<std::uint8_t>(s < 0 ? -scaled : scaled);
    }
    require(!fs::exists(path), "Prepared speech output already exists.");
    std::fstream out(path, std::ios::binary | std::ios::out | std::ios::in | std::ios::trunc);
    require(bool(out), "Cannot create prepared speech.");
    std::uint32_t start = 128 + 16 * static_cast<std::uint32_t>(map.references.size());
    Bytes zero(start);
    out.write(reinterpret_cast<const char *>(zero.data()), zero.size());
    struct Row {
        VoiceRef ref;
        std::uint32_t at, size;
    };
    std::vector<Row> rows;
    for (auto ref : map.references) {
        auto location = voc(archive, ref);
        Bytes converted(location.second);
        for (std::size_t i = 0; i < converted.size(); ++i)
            converted[i] = table[archive[location.first + i]];
        auto pos = out.tellp();
        require(pos >= 0 && pos <= std::numeric_limits<std::int32_t>::max(),
                "Speech output exceeds limit.");
        rows.push_back(
            {ref, static_cast<std::uint32_t>(pos), static_cast<std::uint32_t>(converted.size())});
        out.write(reinterpret_cast<const char *>(converted.data()), converted.size());
    }
    auto size = out.tellp();
    require(size >= 0 && size <= std::numeric_limits<std::int32_t>::max(),
            "Speech output exceeds limit.");
    Bytes h(128);
    std::memcpy(h.data(), "NPC1", 4);
    h[5] = 1;
    h[7] = 128;
    std::uint32_t fields[] = {22050,
                              4,
                              static_cast<std::uint32_t>(archive.size()),
                              static_cast<std::uint32_t>(map.bytes.size()),
                              static_cast<std::uint32_t>(rows.size()),
                              128,
                              start,
                              static_cast<std::uint32_t>(size)};
    for (unsigned i = 0; i < 8; ++i)
        be32(h, 8 + 4 * i, fields[i]);
    auto a = unhex(sha(archive)), b = unhex(sha(map.bytes));
    std::copy(a.begin(), a.end(), h.begin() + 40);
    std::copy(b.begin(), b.end(), h.begin() + 72);
    out.seekp(0);
    out.write(reinterpret_cast<const char *>(h.data()), h.size());
    for (auto r : rows) {
        Bytes row(16);
        be32(row, 0, r.ref.offset);
        be32(row, 4, r.ref.header);
        be32(row, 8, r.at);
        be32(row, 12, r.size);
        out.write(reinterpret_cast<const char *>(row.data()), row.size());
    }
    out.flush();
    require(bool(out), "Speech write failed.");
    for (auto r : rows) {
        out.seekg(r.at);
        Bytes check(r.size);
        out.read(reinterpret_cast<char *>(check.data()), check.size());
        require(bool(out), "Speech verification read failed.");
        auto location = voc(archive, r.ref);
        for (std::size_t i = 0; i < check.size(); ++i)
            require(check[i] == table[archive[location.first + i]],
                    "Speech sample verification failed.");
    }
    out.close();
    require(sha_file(path) == expected, "Prepared speech checksum failed.");
}
void self_test() {
    require(sha(Bytes{}) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "Empty SHA256 vector failed.");
    require(sha(Bytes{'a', 'b', 'c'}) ==
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "SHA256 vector failed.");
    Bytes b(4);
    be32(b, 0, 0x12345678);
    require(be32(b, 0) == 0x12345678, "Endian round trip failed.");
    require(base64("YWJj") == Bytes({'a', 'b', 'c'}), "Base64 vector failed.");
    bool rejected = false;
    try {
        voc(Bytes(8), {0, 10});
    } catch (const std::exception &) {
        rejected = true;
    }
    require(rejected, "Malformed VOC accepted.");
    verify_payload();
}
} // namespace talkie
