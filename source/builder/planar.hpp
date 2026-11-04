#pragma once
#include "builder.hpp"

namespace talkie {
Bytes prepare_planar(const std::map<std::string, Bytes> &rooms);
void test_planar();
}
