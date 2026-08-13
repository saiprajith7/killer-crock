#include "core/logger.hpp"

#include <cstdlib>
#include <filesystem>

#include "core/types.hpp"

namespace fs = std::filesystem;

namespace boss {

Logger& Logger::instance() {
  static Logger lg;
  return lg;
}

Logger::Logger() {
  const char* home = std::getenv("HOME");
  fs::path dir = home ? fs::path(home) / ".local/share/boss-sentinel" : fs::path("/tmp/boss-sentinel");
  std::error_code ec;
  fs::create_directories(dir, ec);
  path_ = (dir / "boss-sentinel.log").string();
}

void Logger::write(const std::string& level, const std::string& msg) {
  std::lock_guard lock(mu_);
  std::string line = "[" + now_iso() + "] [" + level + "] " + msg;
  ring_.push_back(line);
  if (ring_.size() > 500) ring_.erase(ring_.begin(), ring_.begin() + static_cast<long>(ring_.size() - 500));
  std::ofstream out(path_, std::ios::app);
  if (out) out << line << '\n';
}

void Logger::info(const std::string& msg) { write("INFO", msg); }
void Logger::warn(const std::string& msg) { write("WARN", msg); }
void Logger::error(const std::string& msg) { write("ERROR", msg); }
void Logger::event(const std::string& category, const std::string& msg) {
  write("EVENT/" + category, msg);
}

std::vector<std::string> Logger::recent(std::size_t n) const {
  std::lock_guard lock(mu_);
  if (ring_.size() <= n) return ring_;
  return {ring_.end() - static_cast<long>(n), ring_.end()};
}

}  // namespace boss
