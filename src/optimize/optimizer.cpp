#include "optimize/optimizer.hpp"

#include <array>
#include <cstdio>

#include "core/logger.hpp"
#include "core/paths.hpp"

namespace boss {
namespace {

ActionResult run_helper(const std::string& action) {
  std::string helper = find_helper_path();
  ActionResult r;
  r.action = action;
  if (helper.empty()) {
    r.ok = false;
    r.message = "Helper missing";
    return r;
  }
  std::string cmd = "pkexec " + helper + " " + action + " 2>/dev/null";
  std::array<char, 512> buf{};
  std::string out;
  FILE* pipe = popen(cmd.c_str(), "r");
  if (!pipe) {
    cmd = helper + " " + action + " 2>/dev/null";
    pipe = popen(cmd.c_str(), "r");
  }
  if (!pipe) {
    r.ok = false;
    r.message = "Could not launch helper";
    return r;
  }
  while (fgets(buf.data(), buf.size(), pipe)) out += buf.data();
  int rc = pclose(pipe);
  r.ok = (out.find("\"ok\": true") != std::string::npos || out.find("\"ok\":true") != std::string::npos ||
          rc == 0);
  auto pos = out.find("\"message\"");
  if (pos != std::string::npos) {
    auto q1 = out.find('"', pos + 10);
    auto q2 = out.find('"', q1 + 1);
    if (q1 != std::string::npos && q2 != std::string::npos) r.message = out.substr(q1 + 1, q2 - q1 - 1);
  }
  if (r.message.empty()) r.message = r.ok ? "done" : "failed";
  Logger::instance().event("optimize", action + " → " + r.message);
  return r;
}

}  // namespace

std::string OptimizeReport::summary_text() const {
  std::string s = "Performance optimized:\n";
  for (const auto& r : results) {
    s += " • ";
    s += r.action;
    s += ": ";
    s += r.message;
    s += r.ok ? "\n" : " (failed)\n";
  }
  return s;
}

OptimizeReport Optimizer::run_all() {
  OptimizeReport report;
  Logger::instance().info("Starting performance optimization suite");
  for (const char* action : {"cpu_performance", "io_boost", "drop_caches", "power_performance"}) {
    report.results.push_back(run_helper(action));
  }
  Logger::instance().info("Optimization suite finished");
  return report;
}

}  // namespace boss
