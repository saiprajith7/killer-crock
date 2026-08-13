#pragma once

#include <vector>

#include <gtkmm.h>

#include "core/settings.hpp"
#include "core/types.hpp"
#include "heal/healer.hpp"
#include "monitor/engine.hpp"
#include "optimize/optimizer.hpp"
#include "ui/gauges.hpp"

namespace boss {

class MainWindow : public Gtk::ApplicationWindow {
 public:
  MainWindow();

 private:
  void build_ui();
  void load_css();
  void refresh();
  void render_snapshot(const Snapshot& snap);
  void rebuild_core_meters(const Snapshot& snap);
  void rebuild_process_table(const Snapshot& snap);
  void rebuild_service_list(const Snapshot& snap);
  void rebuild_issues(const Snapshot& snap);
  void maybe_prompt_autoheal(const Snapshot& snap);
  void run_heal_and_optimize(const Snapshot& snap);
  void append_log_lines();
  void on_optimize_yes();
  void on_optimize_no();
  void on_toggle_autoheal();
  Gtk::Box* make_chip(const Glib::ustring& title, Gtk::Label*& value_out);
  Gtk::Box* make_stat_tile(const Glib::ustring& title, Gtk::Label*& value_out, Gtk::Label*& detail_out);

  MonitorEngine engine_;
  Healer healer_;
  Optimizer optimizer_;
  Settings settings_;

  ui::HeroVitality hero_;
  ui::BreathWave wave_;
  ui::DeviceGraph graph_cpu_{"CPU"};
  ui::DeviceGraph graph_mem_{"MEMORY"};
  ui::DeviceGraph graph_disk_{"DISK /"};
  ui::DeviceGraph graph_swap_{"SWAP"};
  ui::DeviceGraph graph_cpu_big_{"CPU UTILIZATION"};
  ui::DeviceGraph graph_mem_big_{"RAM"};
  ui::DeviceGraph graph_swap_big_{"SWAP"};
  ui::DeviceGraph graph_disk_big_{"DISK /"};

  Gtk::Label hero_status_;
  Gtk::Label hero_line_;
  Gtk::Label autoheal_state_;
  Gtk::Switch autoheal_switch_;
  Gtk::Label* chip_cpu_ = nullptr;
  Gtk::Label* chip_mem_ = nullptr;
  Gtk::Label* chip_disk_ = nullptr;
  Gtk::Label* chip_load_ = nullptr;
  Gtk::Label* tile_util_ = nullptr;
  Gtk::Label* tile_util_d_ = nullptr;
  Gtk::Label* tile_cores_ = nullptr;
  Gtk::Label* tile_cores_d_ = nullptr;
  Gtk::Label* tile_threads_ = nullptr;
  Gtk::Label* tile_threads_d_ = nullptr;
  Gtk::Label* tile_load_ = nullptr;
  Gtk::Label* tile_load_d_ = nullptr;
  Gtk::Label* tile_ram_ = nullptr;
  Gtk::Label* tile_ram_d_ = nullptr;
  Gtk::Label* tile_swap_ = nullptr;
  Gtk::Label* tile_swap_d_ = nullptr;
  Gtk::Label model_line_;
  Gtk::Label opt_plan_label_;
  Gtk::Label footer_;
  Gtk::Box cores_box_{Gtk::Orientation::VERTICAL, 2};
  Gtk::Box issues_box_{Gtk::Orientation::VERTICAL, 0};
  Gtk::Box proc_rows_{Gtk::Orientation::VERTICAL, 0};
  Gtk::Box svc_list_{Gtk::Orientation::VERTICAL, 0};
  Gtk::TextView log_view_;
  Glib::RefPtr<Gtk::TextBuffer> log_buf_;
  std::vector<Gtk::LevelBar*> core_bars_;
  std::vector<Gtk::Label*> core_vals_;

  bool prompt_open_ = false;
  bool busy_ = false;
  double last_prompt_ts_ = 0;
  Snapshot last_snap_;
};

}  // namespace boss
