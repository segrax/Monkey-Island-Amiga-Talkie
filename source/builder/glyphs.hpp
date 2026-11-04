#pragma once
#include "builder.hpp"
namespace talkie {
Bytes prepare_font(const Bytes &font, unsigned id);
std::map<std::string, Bytes> prepare_fonts(const std::map<std::string, Bytes> &rooms);
}
