#include "app/application.hpp"

#include <cstdlib>

#include "core/logger.hpp"

int main(int argc, char* argv[]) {
  // Must be set before GTK initializes — prevents EGL/DRI segfaults on BOSS VMs
  if (!std::getenv("GSK_RENDERER")) {
    setenv("GSK_RENDERER", "cairo", 1);
  }

  boss::Logger::instance().info("BOSS-Sentinel 2.1.1 starting (GSK_RENDERER=" +
                                std::string(std::getenv("GSK_RENDERER") ? std::getenv("GSK_RENDERER") : "?") +
                                ")");
  auto app = boss::Application::create();
  const int code = app->run(argc, argv);
  boss::Logger::instance().info("BOSS-Sentinel exiting code=" + std::to_string(code));
  return code;
}
