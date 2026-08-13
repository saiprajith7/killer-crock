#include "core/settings.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>

#include "core/logger.hpp"

namespace fs = std::filesystem;

namespace boss {
namespace {

fs::path settings_path() {
  const char* home = std::getenv("HOME");
  fs::path dir = home ? fs::path(home) / ".config/boss-sentinel" : fs::path("/tmp/boss-sentinel");
  std::error_code ec;
  fs::create_directories(dir, ec);
  return dir / "settings.json";
}

bool extract_bool(const std::string& json, const std::string& key, bool fallback) {
  auto pos = json.find("\"" + key + "\"");
  if (pos == std::string::npos) return fallback;
  auto colon = json.find(':', pos);
  if (colon == std::string::npos) return fallback;
  auto rest = json.substr(colon + 1, 32);
  if (rest.find("true") != std::string::npos) return true;
  if (rest.find("false") != std::string::npos) return false;
  return fallback;
}

int extract_int(const std::string& json, const std::string& key, int fallback) {
  auto pos = json.find("\"" + key + "\"");
  if (pos == std::string::npos) return fallback;
  auto colon = json.find(':', pos);
  if (colon == std::string::npos) return fallback;
  try {
    return std::stoi(json.substr(colon + 1));
  } catch (...) {
    return fallback;
  }
}

}  // namespace

Settings Settings::load() {
  Settings s;
  std::ifstream in(settings_path());
  if (!in) return s;
  std::ostringstream ss;
  ss << in.rdbuf();
  const std::string json = ss.str();
  s.autoheal_enabled = extract_bool(json, "autoheal_enabled", s.autoheal_enabled);
  s.prompt_on_issue = extract_bool(json, "prompt_on_issue", s.prompt_on_issue);
  s.poll_ms = extract_int(json, "poll_ms", s.poll_ms);
  s.dialog_cooldown_sec = extract_int(json, "dialog_cooldown_sec", s.dialog_cooldown_sec);
  return s;
}

void Settings::save() const {
  std::ofstream out(settings_path());
  if (!out) {
    Logger::instance().error("Could not save settings");
    return;
  }
  out << "{\n"
      << "  \"autoheal_enabled\": " << (autoheal_enabled ? "true" : "false") << ",\n"
      << "  \"prompt_on_issue\": " << (prompt_on_issue ? "true" : "false") << ",\n"
      << "  \"poll_ms\": " << poll_ms << ",\n"
      << "  \"dialog_cooldown_sec\": " << dialog_cooldown_sec << "\n"
      << "}\n";
  Logger::instance().event("settings", "Settings saved");
}

}  // namespace boss
