#pragma once

#include <gtkmm.h>

#include "core/settings.hpp"
#include "core/types.hpp"
#include "heal/healer.hpp"
#include "monitor/engine.hpp"
#include "optimize/optimizer.hpp"

namespace boss {

class MainWindow : public Gtk::ApplicationWindow {
 public:
  MainWindow();

 private:
  void build_ui();
  void load_css();
  void refresh();
  void render_snapshot(const Snapshot& snap);
  void maybe_prompt_autoheal(const Snapshot& snap);
  void run_heal_and_optimize(const Snapshot& snap);
  void append_log_lines();
  void on_manual_optimize();
  void on_toggle_autoheal();

  MonitorEngine engine_;
  Healer healer_;
  Optimizer optimizer_;
  Settings settings_;

  Gtk::Label brand_label_;
  Gtk::Label score_label_;
  Gtk::Label status_label_;
  Gtk::Label cpu_chip_;
  Gtk::Label mem_chip_;
  Gtk::Label disk_chip_;
  Gtk::Label load_chip_;
  Gtk::Label issues_label_;
  Gtk::TextView proc_view_;
  Gtk::TextView svc_view_;
  Gtk::TextView log_view_;
  Gtk::Switch autoheal_switch_;
  Gtk::Button optimize_btn_;
  Gtk::Button refresh_btn_;
  Gtk::ProgressBar score_bar_;

  bool prompt_open_ = false;
  bool busy_ = false;
  double last_prompt_ts_ = 0;
  Glib::RefPtr<Gtk::TextBuffer> proc_buf_;
  Glib::RefPtr<Gtk::TextBuffer> svc_buf_;
  Glib::RefPtr<Gtk::TextBuffer> log_buf_;
};

}  // namespace boss
