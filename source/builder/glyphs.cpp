#include "glyphs.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iterator>
#include <map>
#include <stdexcept>
#include <vector>

namespace talkie {
namespace {
static void require(bool condition) {
    if (!condition) throw std::runtime_error("Invalid packed font.");
}
static void word(Bytes &b, unsigned v) {
    require(v <= 65535);
    b.push_back(static_cast<std::uint8_t>(v >> 8));
    b.push_back(static_cast<std::uint8_t>(v));
}
static void longword(Bytes &b, std::uint32_t v) {
    word(b, v >> 16); word(b, v & 65535);
}
static unsigned little(const Bytes &b, std::size_t p) {
    require(p <= b.size() && 4 <= b.size() - p);
    return b[p] | (unsigned(b[p + 1]) << 8) |
           (unsigned(b[p + 2]) << 16) | (unsigned(b[p + 3]) << 24);
}

// The replay reads the live palette and handles dirty/plain output and all phases.
static Bytes program(const Bytes &font, unsigned off, unsigned w, unsigned h) {
    const std::array<std::uint8_t, 26> row_prefix = {
        0x4a,0x44,0x66,0x16,0x3c,0x3c,0,0,0xe6,0x6e,0xe0,0x5e,
        0x8d,0x2c,0,0,0xe0,0x5e,0x4a,0x06,0x67,0x04,0x8d,0x2c,0,0};
    Bytes result;
    for (unsigned y = 0; y < h; ++y) {
        unsigned mask = 0;
        std::array<unsigned, 9> colors{};
        for (unsigned x = 0; x < w; ++x) {
            auto pixel = y * w + x;
            colors[x] = (font[off + 4 + pixel / 4] >> (6 - 2 * (pixel % 4))) & 3;
            if (colors[x]) mask |= 0x8000 >> x;
        }
        if (!mask) continue;
        Bytes prefix(row_prefix.begin(), row_prefix.end());
        for (auto pair : {std::pair<unsigned,unsigned>{6,mask}, {14,y * 40}, {24,y * 40 + 1}}) {
            prefix[pair.first] = static_cast<std::uint8_t>(pair.second >> 8);
            prefix[pair.first + 1] = static_cast<std::uint8_t>(pair.second);
        }
        result.insert(result.end(), prefix.begin(), prefix.end());
        for (unsigned x = 0; x < w; ++x) if (colors[x]) {
            word(result, 0x116a); word(result, colors[x]); word(result, y * 320 + x);
        }
    }
    word(result, 0x4ed5);
    return result;
}

} // namespace

Bytes prepare_font(const Bytes &font, unsigned id) {
    require(font.size() >= 1028 && font.size() <= 65535 && id >= 1 && id <= 4);
    if (font[0] != 2) return {};
    struct Record { unsigned off, source_bytes; Bytes code; };
    std::map<unsigned, Record> records;
    for (unsigned c = 0; c < 256; ++c) {
        unsigned off = little(font, 4 + c * 4);
        if (!off) continue;
        require(off >= 1028 && off <= font.size() && 4 <= font.size() - off);
        unsigned w = font[off], h = font[off + 1];
        unsigned n = 4 + w * h / 4 + 1;
        require(n <= font.size() - off);
        if (w < 2 || w > 9 || !h || (h - 1) * 320 + w - 1 > 32767) continue;
        records.emplace(off, Record{off,n,program(font,off,w,h)});
    }
    require(records.size() <= 256);
    const unsigned source = 36 + 12 * unsigned(records.size());
    const unsigned code_start = (source + unsigned(font.size()) + 1) & ~1u;
    unsigned at = code_start;
    for (const auto &pair : records) {
        require(pair.second.code.size() <= 65535);
        at += unsigned(pair.second.code.size());
    }
    if (at > 64548) return {};
    Bytes out{'N','G','P','2'};
    word(out,2); word(out,36); longword(out,at); word(out,id); word(out,unsigned(records.size()));
    longword(out,36); longword(out,source); longword(out,unsigned(font.size())); longword(out,code_start); longword(out,0);
    at = code_start;
    for (const auto &pair : records) {
        const auto &r = pair.second;
        word(out,r.off); word(out,r.source_bytes); longword(out,at); word(out,unsigned(r.code.size())); word(out,0);
        at += unsigned(r.code.size());
    }
    out.insert(out.end(),font.begin(),font.end());
    if (out.size() & 1) out.push_back(0);
    require(out.size() == code_start);
    for (const auto &pair : records) out.insert(out.end(),pair.second.code.begin(),pair.second.code.end());
    require(out.size() == at && !(out.size() & 1));
    std::uint32_t a = 65535, sum = 65535;
    for (std::size_t pos = 0; pos < out.size();) {
        auto stop = std::min(out.size(), pos + 718);
        while (pos < stop) {
            a += (unsigned(out[pos]) << 8) | out[pos + 1];
            sum += a;
            pos += 2;
        }
        a = (a & 65535) + (a >> 16);
        sum = (sum & 65535) + (sum >> 16);
    }
    a = (a & 65535) + (a >> 16);
    sum = (sum & 65535) + (sum >> 16);
    auto checksum = (sum << 16) | a;
    for (unsigned i = 0; i < 4; ++i) out[32 + i] = static_cast<std::uint8_t>(checksum >> (24 - 8 * i));
    return out;
}


std::map<std::string, Bytes> prepare_fonts(const std::map<std::string, Bytes> &rooms) {
    std::map<std::string, Bytes> files;
    for (unsigned id = 1; id <= 4; ++id) {
        auto it = rooms.find(std::to_string(900 + id) + ".LFL");
        if (it == rooms.end()) throw std::runtime_error("Missing Amiga font resource.");
        const auto &file = it->second;
        require(file.size() >= 21 && little(file,0) == file.size() - 15);
        auto prepared = prepare_font(Bytes(file.begin() + 21,file.end()),id);
        if (!prepared.empty()) files.emplace("native-font-" + std::to_string(id) + ".dat",std::move(prepared));
    }
    return files;
}
} // namespace talkie
