#pragma once

#include <string>

namespace boss {

/** Resolve path to boss-sentinel-helper (env, installed, or source tree). */
std::string find_helper_path();

}  // namespace boss
