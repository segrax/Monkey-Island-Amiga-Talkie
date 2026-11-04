#include "planar.hpp"
#include <algorithm>
#include <array>
#include <stdexcept>

namespace talkie {
namespace {
void check(bool valid) {
    if (!valid)
        throw std::runtime_error("Invalid Amiga image resource.");
}
std::uint32_t little(const Bytes &b, std::size_t p, unsigned n) {
    check(p <= b.size() && n <= b.size() - p);
    std::uint32_t value = 0;
    for (unsigned i = 0; i < n; ++i)
        value |= std::uint32_t(b[p + i]) << (8 * i);
    return value;
}
void word(Bytes &b, std::size_t p, unsigned value) {
    check(p <= b.size() && 2 <= b.size() - p && value <= 65535);
    b[p] = static_cast<std::uint8_t>(value >> 8);
    b[p + 1] = static_cast<std::uint8_t>(value);
}
bool tag(const Bytes &b, std::size_t p, char a, char c) {
    return p <= b.size() && 6 <= b.size() - p && b[p + 4] == a && b[p + 5] == c;
}
std::size_t end(const Bytes &b, std::size_t p, std::size_t limit) {
    auto n = little(b, p, 4);
    check(p <= limit && n >= 6 && n <= limit - p);
    return p + n;
}
void align(Bytes &b) {
    if (b.size() & 1)
        b.push_back(0);
}
struct Image {
    unsigned room, object, width, height;
    Bytes payload;
};
std::uint32_t checksum(const Bytes &b) {
    check(!(b.size() & 1));
    std::uint32_t a = 65535, sum = 65535;
    std::size_t p = 0;
    while (p < b.size()) {
        auto stop = std::min(b.size(), p + 359 * 2);
        while (p < stop) {
            a += (b[p] << 8) | b[p + 1];
            sum += a;
            p += 2;
        }
        a = (a & 65535) + (a >> 16);
        sum = (sum & 65535) + (sum >> 16);
    }
    a = (a & 65535) + (a >> 16);
    sum = (sum & 65535) + (sum >> 16);
    return (sum << 16) | a;
}
Bytes image(const Bytes &source, unsigned width, unsigned height, unsigned parity = 0) {
    const unsigned columns = width / 8, mask_bytes = (height + 7) / 8;
    if (source.size() < 8 + 4 + columns * 4)
        return {};
    std::array<std::uint8_t, 16> palette{};
    for (unsigned i = 0; i < 16; ++i)
        palette[i] = static_cast<std::uint8_t>(16 + i);
    palette[1] = 0;
    Bytes history(height), pixels(width * height), masks(columns * mask_bytes);
    Bytes descriptors(columns * 8);
    for (unsigned strip = 0; strip < columns; ++strip) {
        const auto offset = little(source, 12 + strip * 4, 4);
        if (offset > source.size() - 8)
            return {};
        std::size_t start = 8 + offset, p = start;
        if (p >= source.size() || source[p++] != 10)
            return {};
        unsigned remaining = 0, mode = 0, a = 0, b = 0;
        bool dependent = false;
        auto byte = [&]() {
            check(p < source.size());
            return source[p++];
        };
        for (unsigned x = 0; x < 8; ++x) {
            for (unsigned y = 0; y < height; ++y) {
                if (!remaining) {
                    auto token = byte();
                    if (token < 128) {
                        mode = 0;
                        a = token & 15;
                        remaining = token >> 4;
                    } else if (token < 192) {
                        mode = 1;
                        remaining = token & 63;
                    } else {
                        mode = 2;
                        remaining = token & 63;
                        auto pair = byte();
                        a = pair >> 4;
                        b = pair & 15;
                    }
                    if (!remaining) {
                        remaining = byte();
                        if (!remaining)
                            remaining = 256;
                    }
                }
                auto color = mode == 1 ? history[y] : static_cast<std::uint8_t>(a);
                if (mode == 1 && x == 0) {
                    masks[strip * mask_bytes + y / 8] |= 1U << (7 - (y & 7));
                    dependent = true;
                }
                if (mode == 2)
                    std::swap(a, b);
                history[y] = color;
                pixels[y * width + strip * 8 + x] = palette[color];
                --remaining;
            }
        }
        if (remaining || p - start > 65535)
            return {};
        be32(descriptors, strip * 8, static_cast<std::uint32_t>(start));
        word(descriptors, strip * 8 + 4, static_cast<unsigned>(p - start));
        // The decoder's final flags are not assumed by the conversion cache.
        word(descriptors, strip * 8 + 6, dependent ? 128 : 0);
    }
    std::map<std::array<std::uint8_t, 8>, unsigned> dictionary;
    Bytes records, indices(columns * height * 2);
    for (unsigned x = 0; x < columns; ++x) {
        for (unsigned y = 0; y < height; ++y) {
            std::array<std::uint8_t, 8> raw{};
            std::copy_n(pixels.begin() + y * width + x * 8, 8, raw.begin());
            auto found = dictionary.find(raw);
            unsigned offset;
            if (found == dictionary.end()) {
                offset = static_cast<unsigned>(records.size());
                if (offset > 65535)
                    return {};
                dictionary.emplace(raw, offset);
                records.insert(records.end(), raw.begin(), raw.end());
                for (unsigned bit : {0U, 1U, 3U, 4U, 2U}) {
                    unsigned plane = 0;
                    for (unsigned i = 0; i < 8; ++i)
                        plane |= ((raw[i] >> bit) & 1) << (7 - i);
                    records.push_back(static_cast<std::uint8_t>(plane));
                }
                records.push_back(0);
            } else {
                offset = found->second;
            }
            word(indices, 2 * (x * height + y), offset);
        }
    }
    Bytes out(64);
    std::copy_n("NPD1", 4, out.begin());
    word(out, 4, parity ? 2 : 1);
    word(out, 6, 64);
    word(out, 12, width);
    word(out, 14, height);
    word(out, 16, static_cast<unsigned>(dictionary.size()));
    word(out, 18, 14);
    be32(out, 20, columns * height);
    be32(out, 40, 64);
    word(out, 44, columns);
    word(out, 46, 3);
    std::copy(palette.begin(), palette.end(), out.begin() + 48);
    out.insert(out.end(), descriptors.begin(), descriptors.end());
    be32(out, 24, static_cast<std::uint32_t>(out.size()));
    out.insert(out.end(), records.begin(), records.end());
    be32(out, 28, static_cast<std::uint32_t>(out.size()));
    out.insert(out.end(), indices.begin(), indices.end());
    if ((out.size() & 1) != parity)
        out.push_back(0);
    be32(out, 32, static_cast<std::uint32_t>(out.size()));
    be32(out, 36, static_cast<std::uint32_t>(source.size()));
    out.insert(out.end(), source.begin(), source.end());
    align(out);
    out.insert(out.end(), masks.begin(), masks.end());
    align(out);
    if (out.size() > 32768)
        return {};
    be32(out, 8, static_cast<std::uint32_t>(out.size()));
    return out;
}
void room_images(const Bytes &b, unsigned room, std::size_t begin, std::size_t limit,
                 std::vector<Image> &images) {
    check(tag(b, begin, 'R', 'O'));
    auto stop = end(b, begin, limit);
    std::map<unsigned, std::pair<unsigned, unsigned>> dimensions;
    std::map<unsigned, std::pair<Bytes, unsigned>> sources;
    for (auto p = begin + 6; p < stop;) {
        auto next = end(b, p, stop);
        if (tag(b, p, 'O', 'C')) {
            check(next - p >= 18);
            unsigned object = little(b, p + 6, 2);
            check(dimensions.emplace(object, std::make_pair(b[p + 11] * 8U,
                                                           b[p + 17] & 0xf8U)).second);
        } else if (tag(b, p, 'O', 'I')) {
            check(next - p >= 8);
            unsigned object = little(b, p + 6, 2);
            auto parity = static_cast<unsigned>((p - begin) & 1);
            check(sources.emplace(object, std::make_pair(
                Bytes(b.begin() + p, b.begin() + next), parity)).second);
        }
        p = next;
    }
    for (const auto &source : sources) {
        auto dim = dimensions.find(source.first);
        if (dim == dimensions.end())
            continue;
        auto width = dim->second.first, height = dim->second.second;
        if (!width || width > 320 || !height || height > 200)
            continue;
        Bytes bytes;
        try {
            bytes = image(source.second.first, width, height, source.second.second);
        } catch (const std::runtime_error &e) {
            throw std::runtime_error("Room " + std::to_string(room) + ", object " +
                                     std::to_string(source.first) + ": " + e.what());
        }
        if (!bytes.empty())
            images.push_back({room, source.first, width, height, std::move(bytes)});
    }
}
} // namespace
Bytes prepare_planar(const std::map<std::string, Bytes> &rooms) {
    std::vector<Image> images;
    for (const auto &file : rooms) {
        Bytes b = file.second;
        for (auto &v : b)
            v ^= 0x69;
        if (!tag(b, 0, 'L', 'E'))
            continue;
        auto stop = end(b, 0, b.size());
        check(tag(b, 6, 'F', 'O'));
        auto table_end = end(b, 6, stop);
        check(table_end >= 13 && 5U * b[12] <= table_end - 13);
        for (unsigned i = 0; i < b[12]; ++i) {
            auto p = 13 + 5 * i;
            unsigned room = b[p];
            auto offset = little(b, p + 1, 4);
            check(offset >= table_end && tag(b, offset, 'L', 'F'));
            auto room_end = end(b, offset, stop);
            check(room_end - offset >= 8 && little(b, offset + 6, 2) == room);
            room_images(b, room, offset + 8, room_end, images);
        }
    }
    std::sort(images.begin(), images.end(), [](const Image &a, const Image &b) {
        return std::make_pair(a.room, a.object) < std::make_pair(b.room, b.object);
    });
    std::vector<Image> unique;
    for (auto &im : images) {
        if (!unique.empty() && unique.back().room == im.room && unique.back().object == im.object) {
            check(unique.back().width == im.width && unique.back().height == im.height &&
                  unique.back().payload == im.payload);
        } else {
            unique.push_back(std::move(im));
        }
    }
    images = std::move(unique);
    Bytes out(32 + 24 * images.size());
    std::copy_n("NVPART01", 8, out.begin());
    word(out, 8, 1);
    word(out, 10, 24);
    be32(out, 12, static_cast<std::uint32_t>(images.size()));
    be32(out, 16, 32);
    be32(out, 20, static_cast<std::uint32_t>(out.size()));
    for (std::size_t i = 0; i < images.size(); ++i) {
        const auto &im = images[i];
        if (i)
            check(std::make_pair(images[i - 1].room, images[i - 1].object) !=
                  std::make_pair(im.room, im.object));
        auto p = 32 + 24 * i;
        word(out, p, im.room);
        word(out, p + 2, im.object);
        be32(out, p + 4, static_cast<std::uint32_t>(out.size()));
        be32(out, p + 8, static_cast<std::uint32_t>(im.payload.size()));
        be32(out, p + 12, be32(im.payload, 36));
        word(out, p + 16, im.width);
        word(out, p + 18, im.height);
        be32(out, p + 20, checksum(im.payload));
        out.insert(out.end(), im.payload.begin(), im.payload.end());
    }
    check(out.size() <= 0x7fffffff);
    be32(out, 24, static_cast<std::uint32_t>(out.size()));
    return out;
}
void test_planar() {
    // One strip contains literal, alternating and previous-column packets.
    Bytes source = {0, 0, 0, 0, 'O', 'I', 7, 0, 0, 0, 0, 0, 8, 0, 0, 0,
                    10, 0x20, 0xc2, 0x23, 0x84, 0x24, 0xc2, 0x56, 0x84};
    auto payload = image(source, 8, 2);
    check(!payload.empty());
    auto dict = be32(payload, 24), index = be32(payload, 28);
    const std::array<std::array<std::uint8_t, 8>, 2> expected = {{
        {{16, 18, 18, 18, 20, 21, 21, 21}},
        {{16, 19, 19, 19, 20, 22, 22, 22}}
    }};
    for (unsigned y = 0; y < 2; ++y) {
        unsigned off = (payload[index + y * 2] << 8) | payload[index + y * 2 + 1];
        check(std::equal(expected[y].begin(), expected[y].end(), payload.begin() + dict + off));
    }
    auto odd = image(source, 8, 2, 1);
    auto even_source = be32(payload, 32), odd_source = be32(odd, 32);
    check(odd[5] == 2 && (odd_source & 1) && odd[odd_source - 1] == 0);
    check(odd_source == even_source + 1);
    check(std::equal(source.begin(), source.end(), odd.begin() + odd_source));
    check(std::equal(payload.begin() + dict, payload.begin() + even_source,
                     odd.begin() + dict));
    source[16] = 9;
    check(image(source, 8, 2).empty());
    auto strip = [](const Bytes &encoded, unsigned height) {
        Bytes resource(16);
        resource[12] = 8;
        for (auto byte : encoded)
            resource.push_back(byte);
        return image(resource, 8, height);
    };
    auto solid = strip({10, 0x0f, 0}, 32);
    auto solid_dict = be32(solid, 24);
    check(std::all_of(solid.begin() + solid_dict, solid.begin() + solid_dict + 8,
                      [](std::uint8_t v) { return v == 31; }));
    check(std::all_of(solid.begin() + solid_dict + 8, solid.begin() + solid_dict + 13,
                      [](std::uint8_t v) { return v == 255; }));
    auto alternating = strip({10, 0xc0, 0x2c, 0}, 32);
    auto alternating_dict = be32(alternating, 24);
    check(alternating[alternating_dict] == 18 && alternating[alternating_dict + 14] == 28);
    auto copy = strip({10, 0x80, 0}, 32);
    auto dependency = (be32(copy, 32) + be32(copy, 36) + 1) & ~1U;
    check(std::all_of(copy.begin() + dependency, copy.begin() + dependency + 4,
                      [](std::uint8_t v) { return v == 255; }));
    bool rejected = false;
    try {
        (void)strip({10, 0xc0}, 32);
    } catch (const std::runtime_error &) {
        rejected = true;
    }
    check(rejected);
    check(prepare_planar({}).size() == 32);
    check(checksum({}) == 0xffffffff && checksum(Bytes(720)) == 0xffffffff);
    // Independent wide accumulators check the folding/block boundary cases.
    for (unsigned count : {1U, 358U, 359U, 360U, 1024U, 16384U}) {
        Bytes bytes(count * 2);
        std::uint64_t a = 65535, sum = 65535;
        for (unsigned i = 0; i < count; ++i) {
            unsigned value = (i * 1973U + count * 17U) & 65535;
            bytes[i * 2] = static_cast<std::uint8_t>(value >> 8);
            bytes[i * 2 + 1] = static_cast<std::uint8_t>(value);
            a += value;
            sum += a;
        }
        auto low = static_cast<std::uint32_t>(a % 65535);
        auto high = static_cast<std::uint32_t>(sum % 65535);
        if (!low) low = 65535;
        if (!high) high = 65535;
        check(checksum(bytes) == ((high << 16) | low));
    }
}
} // namespace talkie
