#include "monitor/engine.hpp"

#include <sys/statvfs.h>
#include <unistd.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <thread>

#include "core/logger.hpp"

namespace boss {
namespace {

Severity grade(double v, double warn, double crit) {
  if (v >= crit) return Severity::Critical;
  if (v >= warn) return Severity::Warn;
  return Severity::Ok;
}

}  // namespace

double MonitorEngine::sample_cpu() {
  std::ifstream in("/proc/stat");
  std::string cpu;
  unsigned long long user = 0, nice = 0, system = 0, idle = 0, iowait = 0, irq = 0, softirq = 0, steal = 0;
  in >> cpu >> user >> nice >> system >> idle >> iowait >> irq >> softirq >> steal;
  unsigned long long busy = user + nice + system + iowait + irq + softirq + steal;
  unsigned long long total = busy + idle;
  if (!have_cpu_) {
    prev_busy_ = busy;
    prev_total_ = total;
    have_cpu_ = true;
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    return sample_cpu();
  }
  double db = static_cast<double>(busy - prev_busy_);
  double dt = static_cast<double>(total - prev_total_);
  prev_busy_ = busy;
  prev_total_ = total;
  if (dt <= 0) return 0;
  return std::clamp(db / dt * 100.0, 0.0, 100.0);
}

void MonitorEngine::fill_memory(Snapshot& snap) {
  std::ifstream in("/proc/meminfo");
  std::map<std::string, double> kv;
  std::string key, unit;
  double val = 0;
  while (in >> key >> val) {
    if (!key.empty() && key.back() == ':') key.pop_back();
    in >> unit;
    kv[key] = val;
  }
  double total = kv["MemTotal"];
  double avail = kv.count("MemAvailable") ? kv["MemAvailable"] : kv["MemFree"];
  double used = std::max(0.0, total - avail);
  snap.mem_total_gb = total / 1024.0 / 1024.0;
  snap.mem_used_gb = used / 1024.0 / 1024.0;
  snap.mem_percent = total > 0 ? used / total * 100.0 : 0;
  char detail[64];
  std::snprintf(detail, sizeof(detail), "%.1f / %.1f GB", snap.mem_used_gb, snap.mem_total_gb);
  snap.metrics.push_back({"memory", "Memory", snap.mem_percent, "%",
                          grade(snap.mem_percent, 85, 95), detail});
}

void MonitorEngine::fill_disk(Snapshot& snap) {
  struct statvfs st {};
  if (::statvfs("/", &st) == 0) {
    double total = static_cast<double>(st.f_blocks) * st.f_frsize;
    double freeb = static_cast<double>(st.f_bavail) * st.f_frsize;
    double used = std::max(0.0, total - freeb);
    snap.disk_percent = total > 0 ? used / total * 100.0 : 0;
    snap.metrics.push_back({"disk", "Disk /", snap.disk_percent, "%",
                            grade(snap.disk_percent, 85, 95), "root filesystem"});
  }
  snap.io_read_bps = 0;
  snap.io_write_bps = 0;
}

void MonitorEngine::fill_processes(Snapshot& snap) {
  for (auto& ent : std::filesystem::directory_iterator("/proc")) {
    if (!ent.is_directory()) continue;
    const auto name = ent.path().filename().string();
    if (name.empty() || !std::isdigit(static_cast<unsigned char>(name[0]))) continue;
    int pid = 0;
    try {
      pid = std::stoi(name);
    } catch (...) {
      continue;
    }
    std::ifstream status("/proc/" + std::to_string(pid) + "/status");
    if (!status) continue;
    ProcessRow row;
    row.pid = pid;
    std::string line;
    while (std::getline(status, line)) {
      if (line.rfind("Name:", 0) == 0) {
        row.name = line.substr(5);
        while (!row.name.empty() && row.name.front() == '\t') row.name.erase(row.name.begin());
      }
      if (line.rfind("VmRSS:", 0) == 0) {
        std::istringstream ss(line.substr(6));
        double kb = 0;
        ss >> kb;
        row.mem_mb = kb / 1024.0;
      }
      if (line.rfind("Uid:", 0) == 0) {
        std::istringstream ss(line.substr(4));
        int uid = 0;
        ss >> uid;
        row.user = std::to_string(uid);
        row.background = (uid == 0);
      }
    }
    if (row.name.empty()) continue;
    snap.processes.push_back(row);
  }
  std::sort(snap.processes.begin(), snap.processes.end(),
            [](const ProcessRow& a, const ProcessRow& b) { return a.mem_mb > b.mem_mb; });
  if (snap.processes.size() > 40) snap.processes.resize(40);
}

void MonitorEngine::fill_services(Snapshot& snap) {
  FILE* pipe = popen(
      "systemctl list-units --type=service --state=running --no-pager --no-legend --plain 2>/dev/null",
      "r");
  if (!pipe) return;
  char buf[512];
  while (fgets(buf, sizeof(buf), pipe)) {
    std::istringstream ss(buf);
    ServiceRow s;
    std::string load;
    ss >> s.name >> load >> s.active >> s.sub;
    if (s.name.empty()) continue;
    s.running = true;
    snap.services.push_back(s);
    if (snap.services.size() >= 60) break;
  }
  pclose(pipe);
}

void MonitorEngine::derive_issues(Snapshot& snap) {
  for (const auto& m : snap.metrics) {
    if (m.severity == Severity::Ok) continue;
    Issue issue;
    issue.id = m.kind + ":" + m.label;
    issue.title = m.label + " pressure";
    issue.description = m.detail.empty() ? (m.label + " is elevated") : m.detail;
    issue.severity = m.severity;
    if (m.kind == "cpu") {
      issue.heal_action = "renice_hogs";
      issue.heal_label = "Throttle CPU hogs";
    } else if (m.kind == "memory") {
      issue.heal_action = "drop_caches";
      issue.heal_label = "Drop page caches";
    } else if (m.kind == "disk") {
      issue.heal_action = "purge_disk";
      issue.heal_label = "Purge caches & temp";
    } else {
      issue.heal_action = "drop_caches";
      issue.heal_label = "Reclaim resources";
    }
    snap.issues.push_back(issue);
  }

  snap.score = 100;
  for (const auto& m : snap.metrics) {
    if (m.severity == Severity::Warn) snap.score -= 8;
    if (m.severity == Severity::Critical) snap.score -= 20;
  }
  snap.score = std::clamp(snap.score, 0, 100);
  snap.overall = Severity::Ok;
  for (const auto& i : snap.issues) {
    if (i.severity == Severity::Critical) {
      snap.overall = Severity::Critical;
      break;
    }
    if (i.severity == Severity::Warn) snap.overall = Severity::Warn;
  }
}

Snapshot MonitorEngine::snapshot() {
  Snapshot snap;
  snap.timestamp = static_cast<double>(std::time(nullptr));
  snap.threads = static_cast<int>(std::max(1u, std::thread::hardware_concurrency()));
  double loads[3] = {0, 0, 0};
  if (getloadavg(loads, 3) == 3) snap.load1 = loads[0];

  snap.cpu_percent = sample_cpu();
  snap.metrics.push_back({"cpu", "CPU", snap.cpu_percent, "%",
                          grade(snap.cpu_percent, 80, 95), "overall utilization"});
  fill_memory(snap);
  fill_disk(snap);
  fill_processes(snap);
  fill_services(snap);
  derive_issues(snap);
  Logger::instance().info("Snapshot score=" + std::to_string(snap.score) +
                          " cpu=" + std::to_string((int)snap.cpu_percent) +
                          " mem=" + std::to_string((int)snap.mem_percent));
  return snap;
}

}  // namespace boss
