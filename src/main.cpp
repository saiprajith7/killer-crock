#include "app/application.hpp"

#include <cstdlib>

#include "core/logger.hpp"

namespace {

void force_safe_graphics() {
  // Always force software path on BOSS — EGL/DRI2 auth failures segfault GTK GPU backends.
  // Must run before any GTK init; launcher also exports these for early loader probes.
  setenv("GSK_RENDERER", "cairo", 1);
  setenv("LIBGL_ALWAYS_SOFTWARE", "1", 1);
  setenv("GALLIUM_DRIVER", "llvmpipe", 1);
  setenv("MESA_LOADER_DRIVER_OVERRIDE", "swrast", 1);
  setenv("LIBGL_DRI3_DISABLE", "1", 1);
  setenv("GDK_DEBUG", "gl-disable", 1);
  setenv("GTK_A11Y", "none", 1);
  if (!getenv("GDK_BACKEND") && getenv("DISPLAY")) {
    setenv("GDK_BACKEND", "x11", 1);
  }
}

}  // namespace

int main(int argc, char* argv[]) {
  force_safe_graphics();

  boss::Logger::instance().info(
      std::string("BOSS-Sentinel 2.1.4 starting (GSK_RENDERER=") +
      (std::getenv("GSK_RENDERER") ? std::getenv("GSK_RENDERER") : "?") + ")");

  auto app = boss::Application::create();
  const int code = app->run(argc, argv);
  boss::Logger::instance().info("BOSS-Sentinel exiting code=" + std::to_string(code));
  return code;
}
