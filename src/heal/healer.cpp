#include "heal/healer.hpp"

#include <array>
#include <cstdio>
#include <set>

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
    Logger::instance().error("Heal helper missing for " + action);
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
  Logger::instance().event("heal", action + " → " + r.message);
  return r;
}

}  // namespace

ActionResult Healer::run(const std::string& action) { return run_helper(action); }

std::vector<ActionResult> Healer::run_issue_heals(const std::vector<Issue>& issues) {
  std::vector<ActionResult> out;
  std::set<std::string> seen;
  for (const auto& issue : issues) {
    if (issue.severity != Severity::Critical && issue.severity != Severity::Warn) continue;
    if (seen.count(issue.heal_action)) continue;
    seen.insert(issue.heal_action);
    out.push_back(run(issue.heal_action));
  }
  if (out.empty()) {
    out.push_back(run("drop_caches"));
  }
  return out;
}

}  // namespace boss
