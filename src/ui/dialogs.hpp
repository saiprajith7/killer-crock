#pragma once

#include <functional>
#include <string>

#include <gtkmm.h>

namespace boss::ui {

void ask_autoheal(Gtk::Window& parent, const std::string& issue_summary,
                  std::function<void(bool accepted)> on_answer);

void show_optimize_result(Gtk::Window& parent, const std::string& summary,
                          int autoclose_ms = 4500);

}  // namespace boss::ui
