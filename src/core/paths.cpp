#include "core/paths.hpp"

#include <cstdlib>
#include <filesystem>
#include <unistd.h>

namespace fs = std::filesystem;

namespace boss {

std::string find_helper_path() {
  if (const char* env = std::getenv("BOSS_SENTINEL_HELPER")) {
    if (fs::exists(env)) return env;
  }
  const char* candidates[] = {
      "/usr/libexec/boss-sentinel/boss-sentinel-helper",
      "scripts/boss-sentinel-helper",
      "../scripts/boss-sentinel-helper",
  };
  for (const char* c : candidates) {
    if (fs::exists(c)) return c;
  }
  char buf[4096];
  ssize_t n = ::readlink("/proc/self/exe", buf, sizeof(buf) - 1);
  if (n > 0) {
    buf[n] = 0;
    fs::path exe = fs::path(buf).parent_path();
    for (const auto& rel : {fs::path("../scripts/boss-sentinel-helper"),
                            fs::path("../../scripts/boss-sentinel-helper"),
                            fs::path("boss-sentinel-helper")}) {
      fs::path p = exe / rel;
      if (fs::exists(p)) return fs::weakly_canonical(p).string();
    }
  }
  return {};
}

}  // namespace boss
