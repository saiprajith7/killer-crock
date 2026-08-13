#pragma once

#include <fstream>
#include <mutex>
#include <string>
#include <vector>

namespace boss {

class Logger {
 public:
  static Logger& instance();

  void info(const std::string& msg);
  void warn(const std::string& msg);
  void error(const std::string& msg);
  void event(const std::string& category, const std::string& msg);

  std::vector<std::string> recent(std::size_t n = 200) const;
  std::string log_path() const { return path_; }

 private:
  Logger();
  void write(const std::string& level, const std::string& msg);

  mutable std::mutex mu_;
  std::string path_;
  std::vector<std::string> ring_;
};

}  // namespace boss
