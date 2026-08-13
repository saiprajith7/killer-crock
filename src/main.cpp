#include "app/application.hpp"

#include "core/logger.hpp"

int main(int argc, char* argv[]) {
  boss::Logger::instance().info("BOSS-Sentinel 2.0.0 starting");
  auto app = boss::Application::create();
  const int code = app->run(argc, argv);
  boss::Logger::instance().info("BOSS-Sentinel exiting code=" + std::to_string(code));
  return code;
}
