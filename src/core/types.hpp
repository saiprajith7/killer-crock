#pragma once

#include <chrono>
#include <sstream>
#include <string>
#include <vector>

namespace boss {

enum class Severity { Ok, Warn, Critical };

inline const char* severity_name(Severity s) {
  switch (s) {
    case Severity::Ok: return "OK";
    case Severity::Warn: return "WARN";
    case Severity::Critical: return "CRITICAL";
  }
  return "OK";
}

struct Metric {
  std::string kind;
  std::string label;
  double value = 0;
  std::string unit;
  Severity severity = Severity::Ok;
  std::string detail;
};

struct Issue {
  std::string id;
  std::string title;
  std::string description;
  Severity severity = Severity::Ok;
  std::string heal_action;
  std::string heal_label;
};

struct ProcessRow {
  int pid = 0;
  std::string name;
  std::string user;
  double cpu = 0;
  double mem_mb = 0;
  double io_bps = 0;
  bool background = false;
};

struct ServiceRow {
  std::string name;
  std::string active;
  std::string sub;
  bool running = false;
};

struct Snapshot {
  double timestamp = 0;
  int score = 100;
  Severity overall = Severity::Ok;
  double cpu_percent = 0;
  double mem_percent = 0;
  double mem_used_gb = 0;
  double mem_total_gb = 0;
  double disk_percent = 0;
  double io_read_bps = 0;
  double io_write_bps = 0;
  double load1 = 0;
  int threads = 1;
  std::vector<Metric> metrics;
  std::vector<Issue> issues;
  std::vector<ProcessRow> processes;
  std::vector<ServiceRow> services;
};

struct ActionResult {
  bool ok = false;
  std::string action;
  std::string message;
};

inline std::string now_iso() {
  using clock = std::chrono::system_clock;
  auto t = clock::to_time_t(clock::now());
  std::tm tm{};
  localtime_r(&t, &tm);
  char buf[64];
  std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d",
                tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday,
                tm.tm_hour, tm.tm_min, tm.tm_sec);
  return buf;
}

inline std::string bytes_human(double n) {
  const char* units[] = {"B/s", "KB/s", "MB/s", "GB/s"};
  int i = 0;
  while (n >= 1024.0 && i < 3) {
    n /= 1024.0;
    ++i;
  }
  char buf[64];
  std::snprintf(buf, sizeof(buf), "%.1f %s", n, units[i]);
  return buf;
}

}  // namespace boss
