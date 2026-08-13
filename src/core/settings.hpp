#pragma once

#include <string>

namespace boss {

struct Settings {
  bool autoheal_enabled = false;  // master switch; still prompts Yes/No
  bool prompt_on_issue = true;
  int poll_ms = 2500;
  int dialog_cooldown_sec = 90;

  static Settings load();
  void save() const;
};

}  // namespace boss
