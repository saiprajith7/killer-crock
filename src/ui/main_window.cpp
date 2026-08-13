#include "ui/main_window.hpp"

#include <ctime>
#include <filesystem>
#include <sstream>
#include <unistd.h>

#include <gdkmm/display.h>

#include "core/logger.hpp"
#include "ui/dialogs.hpp"

namespace fs = std::filesystem;

namespace boss {
namespace {

std::string find_css() {
  const char* candidates[] = {
      "/usr/share/boss-sentinel/style.css",
      "share/boss-sentinel/style.css",
      "src/ui/style.css",
      "../src/ui/style.css",
  };
  for (const char* c : candidates) {
    if (fs::exists(c)) return c;
  }
  char buf[4096];
  ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
  if (n > 0) {
    buf[n] = 0;
    fs::path p = fs::path(buf).parent_path() / "share/boss-sentinel/style.css";
    if (fs::exists(p)) return p.string();
  }
  return {};
}

Glib::ustring overall_css(Severity s) {
  if (s == Severity::Critical) return "crit";
  if (s == Severity::Warn) return "warn";
  return "ok";
}

Glib::ustring overall_text(Severity s) {
  if (s == Severity::Critical) return "CRITICAL · ACTION NEEDED";
  if (s == Severity::Warn) return "WARNING · WATCH CLOSELY";
  return "HEALTHY · SYSTEMS NOMINAL";
}

}  // namespace

MainWindow::MainWindow() {
  settings_ = Settings::load();
  set_title("BOSS-Sentinel");
  set_default_size(1280, 860);
  add_css_class("boss-window");
  load_css();
  build_ui();
  Logger::instance().info("BOSS-Sentinel rich UI started");
  refresh();
  Glib::signal_timeout().connect(
      [this]() {
        refresh();
        return true;
      },
      settings_.poll_ms);
}

void MainWindow::load_css() {
  auto provider = Gtk::CssProvider::create();
  const std::string path = find_css();
  try {
    if (!path.empty()) provider->load_from_path(path);
    auto display = Gdk::Display::get_default();
    if (display)
      Gtk::StyleContext::add_provider_for_display(display, provider, GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
  } catch (const Glib::Error& e) {
    Logger::instance().error(std::string("CSS load failed: ") + e.what());
  }
}

Gtk::Box* MainWindow::make_chip(const Glib::ustring& title, Gtk::Label*& value_out) {
  auto* box = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 2);
  box->add_css_class("metric-chip");
  box->set_hexpand(true);
  auto* t = Gtk::make_managed<Gtk::Label>(title);
  t->set_xalign(0);
  t->add_css_class("metric-title");
  value_out = Gtk::make_managed<Gtk::Label>("—");
  value_out->set_xalign(0);
  value_out->add_css_class("metric-value");
  box->append(*t);
  box->append(*value_out);
  return box;
}

Gtk::Box* MainWindow::make_stat_tile(const Glib::ustring& title, Gtk::Label*& value_out, Gtk::Label*& detail_out) {
  auto* box = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 4);
  box->add_css_class("stat-tile");
  box->set_hexpand(true);
  auto* t = Gtk::make_managed<Gtk::Label>(title);
  t->set_xalign(0);
  t->add_css_class("stat-title");
  value_out = Gtk::make_managed<Gtk::Label>("—");
  value_out->set_xalign(0);
  value_out->add_css_class("stat-value");
  detail_out = Gtk::make_managed<Gtk::Label>("");
  detail_out->set_xalign(0);
  detail_out->add_css_class("stat-detail");
  box->append(*t);
  box->append(*value_out);
  box->append(*detail_out);
  return box;
}

void MainWindow::build_ui() {
  auto* root = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 0);
  set_child(*root);

  // Topbar
  auto* top = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 12);
  top->add_css_class("topbar");
  root->append(*top);
  auto* brand_col = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 2);
  auto* brand = Gtk::make_managed<Gtk::Label>("BOSS-SENTINEL");
  brand->set_xalign(0);
  brand->add_css_class("brand");
  auto* sub = Gtk::make_managed<Gtk::Label>("SYSTEM HEALTH · AUTOHEAL · PERFORMANCE");
  sub->set_xalign(0);
  sub->add_css_class("brand-sub");
  brand_col->append(*brand);
  brand_col->append(*sub);
  brand_col->set_hexpand(true);
  top->append(*brand_col);

  auto* ah = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
  ah->add_css_class("autoheal-wrap");
  auto* ah_lab = Gtk::make_managed<Gtk::Label>("AUTOHEAL");
  ah_lab->add_css_class("autoheal-label");
  autoheal_state_.set_text(settings_.prompt_on_issue ? "ON" : "OFF");
  autoheal_state_.add_css_class(settings_.prompt_on_issue ? "autoheal-on" : "autoheal-off");
  autoheal_switch_.set_active(settings_.prompt_on_issue);
  autoheal_switch_.property_active().signal_changed().connect(sigc::mem_fun(*this, &MainWindow::on_toggle_autoheal));
  ah->append(*ah_lab);
  ah->append(autoheal_state_);
  ah->append(autoheal_switch_);
  top->append(*ah);

  // Status strip with vitality ring
  auto* status = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 16);
  status->add_css_class("status-strip");
  root->append(*status);
  status->append(hero_);
  auto* status_text = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 6);
  status_text->set_valign(Gtk::Align::CENTER);
  status_text->set_hexpand(true);
  hero_status_.set_text("HEALTHY · SYSTEMS NOMINAL");
  hero_status_.set_xalign(0);
  hero_status_.add_css_class("hero-status");
  hero_line_.set_text("Live sensors online. Autoheal prompts ready.");
  hero_line_.set_xalign(0);
  hero_line_.set_wrap(true);
  hero_line_.add_css_class("hero-line");
  status_text->append(hero_status_);
  status_text->append(hero_line_);
  status->append(*status_text);

  root->append(wave_);

  // Metric chips
  auto* chips = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
  chips->add_css_class("metric-row");
  root->append(*chips);
  chips->append(*make_chip("CPU", chip_cpu_));
  chips->append(*make_chip("RAM", chip_mem_));
  chips->append(*make_chip("DISK", chip_disk_));
  chips->append(*make_chip("LOAD", chip_load_));

  // Stack + switcher
  auto* tab_bar = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 0);
  tab_bar->add_css_class("tab-bar");
  root->append(*tab_bar);
  auto* stack = Gtk::make_managed<Gtk::Stack>();
  stack->set_transition_type(Gtk::StackTransitionType::SLIDE_LEFT_RIGHT);
  stack->set_vexpand(true);
  auto* switcher = Gtk::make_managed<Gtk::StackSwitcher>();
  switcher->set_stack(*stack);
  switcher->add_css_class("tab-switcher");
  switcher->set_halign(Gtk::Align::START);
  tab_bar->append(*switcher);

  auto wrap_scroll = [](Gtk::Widget& child) {
    auto* sc = Gtk::make_managed<Gtk::ScrolledWindow>();
    sc->set_policy(Gtk::PolicyType::NEVER, Gtk::PolicyType::AUTOMATIC);
    sc->set_vexpand(true);
    sc->set_child(child);
    return sc;
  };

  // ---- Overview ----
  auto* overview = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 8);
  overview->add_css_class("tab-page");
  auto* ov_label = Gtk::make_managed<Gtk::Label>("LIVE DEVICE GRAPHS");
  ov_label->set_xalign(0);
  ov_label->add_css_class("section-label");
  overview->append(*ov_label);
  auto* grid = Gtk::make_managed<Gtk::Grid>();
  grid->set_column_homogeneous(true);
  grid->set_row_homogeneous(true);
  auto cell = [](ui::DeviceGraph& g) {
    auto* c = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 0);
    c->add_css_class("device-cell");
    c->append(g);
    return c;
  };
  grid->attach(*cell(graph_cpu_), 0, 0);
  grid->attach(*cell(graph_mem_), 1, 0);
  grid->attach(*cell(graph_disk_), 0, 1);
  grid->attach(*cell(graph_swap_), 1, 1);
  overview->append(*grid);
  auto* iss_lab = Gtk::make_managed<Gtk::Label>("ACTIVE ISSUES");
  iss_lab->set_xalign(0);
  iss_lab->add_css_class("section-label");
  overview->append(*iss_lab);
  issues_box_.add_css_class("list-frame");
  overview->append(issues_box_);
  stack->add(*wrap_scroll(*overview), "overview", "Overview");

  // ---- CPU ----
  auto* cpu_page = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 8);
  cpu_page->add_css_class("tab-page");
  auto* cpu_tiles = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
  cpu_tiles->append(*make_stat_tile("UTILIZATION", tile_util_, tile_util_d_));
  cpu_tiles->append(*make_stat_tile("CORES", tile_cores_, tile_cores_d_));
  cpu_tiles->append(*make_stat_tile("THREADS", tile_threads_, tile_threads_d_));
  cpu_tiles->append(*make_stat_tile("LOAD AVERAGE", tile_load_, tile_load_d_));
  cpu_page->append(*cpu_tiles);
  model_line_.set_xalign(0);
  model_line_.add_css_class("model-line");
  cpu_page->append(model_line_);
  auto* cpu_graph_cell = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 0);
  cpu_graph_cell->add_css_class("device-cell");
  graph_cpu_big_.set_content_height(180);
  cpu_graph_cell->append(graph_cpu_big_);
  cpu_page->append(*cpu_graph_cell);
  auto* cores_lab = Gtk::make_managed<Gtk::Label>("PER-CPU METERS");
  cores_lab->set_xalign(0);
  cores_lab->add_css_class("section-label");
  cpu_page->append(*cores_lab);
  cores_box_.add_css_class("list-frame");
  cpu_page->append(cores_box_);
  stack->add(*wrap_scroll(*cpu_page), "cpu", "CPU");

  // ---- Memory ----
  auto* mem_page = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 8);
  mem_page->add_css_class("tab-page");
  auto* mem_tiles = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
  mem_tiles->append(*make_stat_tile("RAM", tile_ram_, tile_ram_d_));
  mem_tiles->append(*make_stat_tile("SWAP", tile_swap_, tile_swap_d_));
  mem_page->append(*mem_tiles);
  auto* mem_grid = Gtk::make_managed<Gtk::Grid>();
  mem_grid->set_column_homogeneous(true);
  mem_grid->attach(*cell(graph_mem_big_), 0, 0);
  mem_grid->attach(*cell(graph_swap_big_), 1, 0);
  mem_page->append(*mem_grid);
  stack->add(*wrap_scroll(*mem_page), "memory", "Memory");

  // ---- Disk ----
  auto* disk_page = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 8);
  disk_page->add_css_class("tab-page");
  auto* disk_cell = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 0);
  disk_cell->add_css_class("device-cell");
  graph_disk_big_.set_content_height(220);
  disk_cell->append(graph_disk_big_);
  disk_page->append(*disk_cell);
  stack->add(*wrap_scroll(*disk_page), "disk", "Disk");

  // ---- Processes ----
  auto* proc_page = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 0);
  proc_page->add_css_class("tab-page");
  auto* proc_head = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
  proc_head->add_css_class("app-header");
  for (const char* h : {"PROCESS", "PID", "RAM(MB)", "USER", "STATE"}) {
    auto* l = Gtk::make_managed<Gtk::Label>(h);
    l->set_xalign(0);
    l->set_width_chars(h[0] == 'P' && h[1] == 'R' ? 22 : 10);
    l->set_hexpand(h[0] == 'P' && h[1] == 'R');
    proc_head->append(*l);
  }
  proc_page->append(*proc_head);
  proc_rows_.add_css_class("app-grid");
  proc_page->append(*wrap_scroll(proc_rows_));
  stack->add(*proc_page, "processes", "Processes");

  // ---- Services ----
  auto* svc_page = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 8);
  svc_page->add_css_class("tab-page");
  auto* svc_lab = Gtk::make_managed<Gtk::Label>("RUNNING SYSTEMD SERVICES");
  svc_lab->set_xalign(0);
  svc_lab->add_css_class("section-label");
  svc_page->append(*svc_lab);
  svc_list_.add_css_class("list-frame");
  svc_page->append(*wrap_scroll(svc_list_));
  stack->add(*svc_page, "services", "Services");

  // ---- Optimize ----
  auto* opt_page = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 10);
  opt_page->add_css_class("tab-page");
  auto* card = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 10);
  card->add_css_class("optimize-card");
  auto* ot = Gtk::make_managed<Gtk::Label>("Allot hardware for peak performance?");
  ot->set_xalign(0);
  ot->add_css_class("optimize-title");
  opt_plan_label_.set_text(
      "Plan:\n"
      " • Set CPU governor → performance\n"
      " • Boost I/O schedulers\n"
      " • Drop reclaimable page caches\n"
      " • Set power profile → performance\n"
      " • Heal any active pressure issues\n\n"
      "YES runs auto-heal and optimization. A popup lists what changed, then closes.");
  opt_plan_label_.set_xalign(0);
  opt_plan_label_.set_wrap(true);
  opt_plan_label_.add_css_class("optimize-body");
  auto* btns = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 10);
  auto* yes = Gtk::make_managed<Gtk::Button>("YES — Optimize now");
  yes->add_css_class("opt-yes");
  yes->signal_clicked().connect(sigc::mem_fun(*this, &MainWindow::on_optimize_yes));
  auto* no = Gtk::make_managed<Gtk::Button>("NO — Keep current");
  no->add_css_class("opt-no");
  no->signal_clicked().connect(sigc::mem_fun(*this, &MainWindow::on_optimize_no));
  btns->append(*yes);
  btns->append(*no);
  card->append(*ot);
  card->append(opt_plan_label_);
  card->append(*btns);
  opt_page->append(*card);
  stack->add(*wrap_scroll(*opt_page), "optimize", "Optimize");

  // ---- Logs ----
  auto* log_page = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 8);
  log_page->add_css_class("tab-page");
  log_buf_ = Gtk::TextBuffer::create();
  log_view_.set_buffer(log_buf_);
  log_view_.set_editable(false);
  log_view_.set_monospace(true);
  log_view_.add_css_class("mono-pane");
  log_page->append(*wrap_scroll(log_view_));
  stack->add(*log_page, "logs", "Logs");

  tab_bar->append(*stack);

  footer_.set_xalign(0);
  footer_.add_css_class("footer-meta");
  root->append(footer_);
}

void MainWindow::on_toggle_autoheal() {
  settings_.prompt_on_issue = autoheal_switch_.get_active();
  settings_.save();
  autoheal_state_.set_text(settings_.prompt_on_issue ? "ON" : "OFF");
  autoheal_state_.remove_css_class("autoheal-on");
  autoheal_state_.remove_css_class("autoheal-off");
  autoheal_state_.add_css_class(settings_.prompt_on_issue ? "autoheal-on" : "autoheal-off");
  Logger::instance().event("settings", settings_.prompt_on_issue ? "Autoheal ON" : "Autoheal OFF");
}

void MainWindow::on_optimize_yes() {
  if (busy_) return;
  ui::ask_autoheal(*this, "Manual optimize requested from the Optimize tab.", [this](bool yes) {
    if (yes) run_heal_and_optimize(last_snap_);
  });
}

void MainWindow::on_optimize_no() {
  Logger::instance().event("ui", "User declined optimize from Optimize tab");
  hero_line_.set_text("Optimization skipped. Monitoring continues.");
}

void MainWindow::refresh() {
  if (busy_) {
    append_log_lines();
    return;
  }
  try {
    Snapshot snap = engine_.snapshot();
    last_snap_ = snap;
    render_snapshot(snap);
    maybe_prompt_autoheal(snap);
  } catch (const std::exception& e) {
    Logger::instance().error(std::string("Refresh failed: ") + e.what());
  }
  append_log_lines();
}

void MainWindow::rebuild_core_meters(const Snapshot& snap) {
  // Rebuild only when core count changes
  if (core_bars_.size() != snap.per_cpu.size()) {
    while (auto* child = cores_box_.get_first_child()) cores_box_.remove(*child);
    core_bars_.clear();
    core_vals_.clear();
    for (size_t i = 0; i < snap.per_cpu.size(); ++i) {
      auto* row = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
      row->add_css_class("core-row");
      auto* lab = Gtk::make_managed<Gtk::Label>("CPU" + std::to_string(i + 1));
      lab->set_xalign(0);
      lab->add_css_class("core-label");
      auto* bar = Gtk::make_managed<Gtk::LevelBar>();
      bar->set_min_value(0);
      bar->set_max_value(100);
      bar->set_mode(Gtk::LevelBar::Mode::CONTINUOUS);
      bar->set_hexpand(true);
      bar->add_css_class("core-bar");
      auto* val = Gtk::make_managed<Gtk::Label>("0%");
      val->set_xalign(1);
      val->add_css_class("core-val");
      row->append(*lab);
      row->append(*bar);
      row->append(*val);
      cores_box_.append(*row);
      core_bars_.push_back(bar);
      core_vals_.push_back(val);
    }
  }
  for (size_t i = 0; i < snap.per_cpu.size() && i < core_bars_.size(); ++i) {
    double v = snap.per_cpu[i];
    core_bars_[i]->set_value(v);
    core_bars_[i]->remove_css_class("core-warn");
    core_bars_[i]->remove_css_class("core-crit");
    if (v >= 95)
      core_bars_[i]->add_css_class("core-crit");
    else if (v >= 80)
      core_bars_[i]->add_css_class("core-warn");
    char buf[16];
    std::snprintf(buf, sizeof(buf), "%.0f%%", v);
    core_vals_[i]->set_text(buf);
  }
}

void MainWindow::rebuild_process_table(const Snapshot& snap) {
  while (auto* child = proc_rows_.get_first_child()) proc_rows_.remove(*child);
  for (const auto& p : snap.processes) {
    auto* row = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
    row->add_css_class("app-row");
    auto* name = Gtk::make_managed<Gtk::Label>(p.name);
    name->set_xalign(0);
    name->set_hexpand(true);
    name->set_width_chars(22);
    name->add_css_class("app-row-title");
    auto* pid = Gtk::make_managed<Gtk::Label>(std::to_string(p.pid));
    pid->set_width_chars(10);
    pid->set_xalign(0);
    pid->add_css_class("app-row-cell");
    char mem[32];
    std::snprintf(mem, sizeof(mem), "%.1f", p.mem_mb);
    auto* ram = Gtk::make_managed<Gtk::Label>(mem);
    ram->set_width_chars(10);
    ram->set_xalign(0);
    ram->add_css_class("app-row-cell");
    auto* user = Gtk::make_managed<Gtk::Label>(p.user);
    user->set_width_chars(10);
    user->set_xalign(0);
    user->add_css_class("app-row-cell");
    auto* badge = Gtk::make_managed<Gtk::Label>(p.background ? "BG" : "FG");
    badge->add_css_class("badge");
    if (p.background) badge->add_css_class("badge-bg");
    row->append(*name);
    row->append(*pid);
    row->append(*ram);
    row->append(*user);
    row->append(*badge);
    proc_rows_.append(*row);
  }
}

void MainWindow::rebuild_service_list(const Snapshot& snap) {
  while (auto* child = svc_list_.get_first_child()) svc_list_.remove(*child);
  for (const auto& s : snap.services) {
    auto* row = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 10);
    row->add_css_class("app-row");
    auto* name = Gtk::make_managed<Gtk::Label>(s.name);
    name->set_xalign(0);
    name->set_hexpand(true);
    name->add_css_class("row-title");
    auto* badge = Gtk::make_managed<Gtk::Label>(s.active.empty() ? "RUNNING" : Glib::ustring(s.active).uppercase());
    badge->add_css_class("badge");
    row->append(*name);
    row->append(*badge);
    svc_list_.append(*row);
  }
  if (snap.services.empty()) {
    auto* empty = Gtk::make_managed<Gtk::Label>("No running services listed (systemd unavailable?)");
    empty->add_css_class("muted");
    empty->set_xalign(0);
    svc_list_.append(*empty);
  }
}

void MainWindow::rebuild_issues(const Snapshot& snap) {
  while (auto* child = issues_box_.get_first_child()) issues_box_.remove(*child);
  if (snap.issues.empty()) {
    auto* ok = Gtk::make_managed<Gtk::Label>("No active issues. System looks healthy.");
    ok->set_xalign(0);
    ok->add_css_class("muted");
    issues_box_.append(*ok);
    return;
  }
  for (const auto& issue : snap.issues) {
    auto* row = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 10);
    row->add_css_class("issue-inline");
    auto* col = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 2);
    col->set_hexpand(true);
    auto* title = Gtk::make_managed<Gtk::Label>("[" + Glib::ustring(severity_name(issue.severity)) + "] " +
                                                issue.title);
    title->set_xalign(0);
    title->add_css_class("row-title");
    auto* detail = Gtk::make_managed<Gtk::Label>(issue.description + " → " + issue.heal_label);
    detail->set_xalign(0);
    detail->add_css_class("row-sub");
    col->append(*title);
    col->append(*detail);
    auto* heal = Gtk::make_managed<Gtk::Button>("HEAL");
    heal->add_css_class("cta-danger");
    heal->signal_clicked().connect([this]() {
      ui::ask_autoheal(*this, "Heal selected issue and optimize performance?", [this](bool yes) {
        if (yes) run_heal_and_optimize(last_snap_);
      });
    });
    row->append(*col);
    row->append(*heal);
    issues_box_.append(*row);
  }
}

void MainWindow::render_snapshot(const Snapshot& snap) {
  const char* overall = snap.overall == Severity::Critical   ? "crit"
                        : snap.overall == Severity::Warn     ? "warn"
                                                             : "ok";
  hero_.set_score(snap.score, overall);
  wave_.push(snap.score);

  hero_status_.set_text(overall_text(snap.overall));
  hero_status_.remove_css_class("warn");
  hero_status_.remove_css_class("crit");
  if (snap.overall != Severity::Ok) hero_status_.add_css_class(overall_css(snap.overall));

  char blurb[160];
  std::snprintf(blurb, sizeof(blurb),
                "%d sensors · score %d/100 · %zu issue(s) · autoheal %s",
                4 + static_cast<int>(snap.per_cpu.size()), snap.score, snap.issues.size(),
                settings_.prompt_on_issue ? "on" : "off");
  hero_line_.set_text(blurb);

  char buf[64];
  std::snprintf(buf, sizeof(buf), "%.0f%%", snap.cpu_percent);
  chip_cpu_->set_text(buf);
  std::snprintf(buf, sizeof(buf), "%.0f%%", snap.mem_percent);
  chip_mem_->set_text(buf);
  std::snprintf(buf, sizeof(buf), "%.0f%%", snap.disk_percent);
  chip_disk_->set_text(buf);
  std::snprintf(buf, sizeof(buf), "%.2f", snap.load1);
  chip_load_->set_text(buf);

  // Graphs
  graph_cpu_.update(snap.cpu_percent, "%", snap.cpu_model.empty() ? "overall" : snap.cpu_model);
  std::snprintf(buf, sizeof(buf), "%.1f / %.1f GB", snap.mem_used_gb, snap.mem_total_gb);
  graph_mem_.update(snap.mem_percent, "%", buf);
  std::snprintf(buf, sizeof(buf), "%.1f / %.1f GB", snap.disk_used_gb, snap.disk_total_gb);
  graph_disk_.update(snap.disk_percent, "%", buf);
  std::snprintf(buf, sizeof(buf), "%.2f / %.2f GB", snap.swap_used_gb, snap.swap_total_gb);
  graph_swap_.update(snap.swap_percent, "%", buf);

  graph_cpu_big_.update(snap.cpu_percent, "%", "live utilization");
  char detail[64];
  std::snprintf(detail, sizeof(detail), "%.1f / %.1f GB", snap.mem_used_gb, snap.mem_total_gb);
  graph_mem_big_.update(snap.mem_percent, "%", detail);
  std::snprintf(detail, sizeof(detail), "%.2f / %.2f GB", snap.swap_used_gb, snap.swap_total_gb);
  graph_swap_big_.update(snap.swap_percent, "%", detail);
  std::snprintf(detail, sizeof(detail), "%.1f / %.1f GB", snap.disk_used_gb, snap.disk_total_gb);
  graph_disk_big_.update(snap.disk_percent, "%", detail);

  // CPU tiles
  std::snprintf(buf, sizeof(buf), "%.0f%%", snap.cpu_percent);
  tile_util_->set_text(buf);
  tile_util_d_->set_text("overall");
  tile_cores_->set_text(std::to_string(snap.per_cpu.empty() ? snap.threads : (int)snap.per_cpu.size()));
  tile_cores_d_->set_text("logical");
  tile_threads_->set_text(std::to_string(snap.threads));
  tile_threads_d_->set_text("hw concurrency");
  std::snprintf(buf, sizeof(buf), "%.2f", snap.load1);
  tile_load_->set_text(buf);
  std::snprintf(buf, sizeof(buf), "%.2f / %.2f / %.2f", snap.load1, snap.load5, snap.load15);
  tile_load_d_->set_text(buf);
  model_line_.set_text(snap.cpu_model.empty() ? "CPU model unavailable" : snap.cpu_model);

  std::snprintf(buf, sizeof(buf), "%.0f%%", snap.mem_percent);
  tile_ram_->set_text(buf);
  std::snprintf(buf, sizeof(buf), "%.1f / %.1f GB", snap.mem_used_gb, snap.mem_total_gb);
  tile_ram_d_->set_text(buf);
  std::snprintf(buf, sizeof(buf), "%.0f%%", snap.swap_percent);
  tile_swap_->set_text(buf);
  std::snprintf(buf, sizeof(buf), "%.2f / %.2f GB", snap.swap_used_gb, snap.swap_total_gb);
  tile_swap_d_->set_text(buf);

  rebuild_core_meters(snap);
  rebuild_process_table(snap);
  rebuild_service_list(snap);
  rebuild_issues(snap);

  footer_.set_text("score " + std::to_string(snap.score) + "/100 · " +
                   std::to_string(snap.processes.size()) + " processes · " +
                   std::to_string(snap.services.size()) + " services · autoheal " +
                   (settings_.prompt_on_issue ? "on" : "off"));
}

void MainWindow::append_log_lines() {
  auto lines = Logger::instance().recent(200);
  std::ostringstream ss;
  ss << "Log file: " << Logger::instance().log_path() << "\n\n";
  for (const auto& l : lines) ss << l << '\n';
  log_buf_->set_text(ss.str());
}

void MainWindow::maybe_prompt_autoheal(const Snapshot& snap) {
  if (!settings_.prompt_on_issue) return;
  if (prompt_open_ || busy_) return;
  if (snap.issues.empty() || snap.overall == Severity::Ok) return;
  const double now = static_cast<double>(std::time(nullptr));
  if (last_prompt_ts_ > 0 && (now - last_prompt_ts_) < settings_.dialog_cooldown_sec) return;

  std::ostringstream summary;
  for (const auto& i : snap.issues) summary << "• " << i.title << " (" << severity_name(i.severity) << ")\n";
  prompt_open_ = true;
  last_prompt_ts_ = now;
  ui::ask_autoheal(*this, summary.str(), [this, snap](bool yes) {
    prompt_open_ = false;
    if (yes) run_heal_and_optimize(snap);
  });
}

void MainWindow::run_heal_and_optimize(const Snapshot& snap) {
  if (busy_) return;
  busy_ = true;
  Logger::instance().info("Starting auto-heal + performance optimization");

  std::vector<ActionResult> heals = healer_.run_issue_heals(snap.issues);
  OptimizeReport report = optimizer_.run_all();

  std::ostringstream summary;
  summary << "Healing actions:\n";
  for (const auto& h : heals)
    summary << " • " << h.action << ": " << h.message << (h.ok ? "\n" : " (failed)\n");
  summary << "\n" << report.summary_text();

  busy_ = false;
  append_log_lines();
  ui::show_optimize_result(*this, summary.str(), 5000);
}

}  // namespace boss
