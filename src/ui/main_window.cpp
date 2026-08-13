#include "ui/main_window.hpp"

#include <unistd.h>

#include <cmath>
#include <ctime>
#include <filesystem>
#include <sstream>

#include <gdkmm/display.h>

#include "core/logger.hpp"
#include "ui/dialogs.hpp"

namespace fs = std::filesystem;

namespace boss {
namespace {

std::string severity_css(Severity s) {
  switch (s) {
    case Severity::Critical: return "sev-crit";
    case Severity::Warn: return "sev-warn";
    default: return "sev-ok";
  }
}

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
  // Relative to binary
  char buf[4096];
  ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
  if (n > 0) {
    buf[n] = 0;
    fs::path p = fs::path(buf).parent_path() / "share/boss-sentinel/style.css";
    if (fs::exists(p)) return p.string();
  }
  return {};
}

}  // namespace

MainWindow::MainWindow() {
  settings_ = Settings::load();
  set_title("BOSS-Sentinel");
  set_default_size(1080, 720);
  add_css_class("boss-window");
  load_css();
  build_ui();
  Logger::instance().info("BOSS-Sentinel UI started");
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
    if (!path.empty()) {
      provider->load_from_path(path);
    } else {
      provider->load_from_data(
          "window.boss-window { background: #0b1c24; color: #e8f4f2; }"
          ".brand { font-size: 28px; font-weight: 800; letter-spacing: 2px; color: #5eead4; }");
    }
    auto display = Gdk::Display::get_default();
    if (display) {
      Gtk::StyleContext::add_provider_for_display(display, provider, GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    }
  } catch (const Glib::Error& e) {
    Logger::instance().error(std::string("CSS load failed: ") + e.what());
  }
}

void MainWindow::build_ui() {
  auto* root = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 0);
  set_child(*root);

  // Hero header — brand first
  auto* hero = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 8);
  hero->add_css_class("hero");
  hero->set_margin_start(28);
  hero->set_margin_end(28);
  hero->set_margin_top(22);
  hero->set_margin_bottom(8);
  root->append(*hero);

  brand_label_.set_text("BOSS-SENTINEL");
  brand_label_.add_css_class("brand");
  brand_label_.set_xalign(0);
  hero->append(brand_label_);

  auto* tagline = Gtk::make_managed<Gtk::Label>("Unified health monitor · auto-heal · performance optimization");
  tagline->add_css_class("tagline");
  tagline->set_xalign(0);
  hero->append(*tagline);

  auto* controls = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 14);
  controls->set_margin_top(10);
  hero->append(*controls);

  auto* ah_box = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 8);
  auto* ah_lab = Gtk::make_managed<Gtk::Label>("Auto-heal prompts");
  ah_lab->add_css_class("muted");
  ah_box->append(*ah_lab);
  autoheal_switch_.set_active(settings_.prompt_on_issue);
  autoheal_switch_.property_active().signal_changed().connect(sigc::mem_fun(*this, &MainWindow::on_toggle_autoheal));
  ah_box->append(autoheal_switch_);
  controls->append(*ah_box);

  optimize_btn_.set_label("Optimize now");
  optimize_btn_.add_css_class("accent-btn");
  optimize_btn_.signal_clicked().connect(sigc::mem_fun(*this, &MainWindow::on_manual_optimize));
  controls->append(optimize_btn_);

  refresh_btn_.set_label("Refresh");
  refresh_btn_.add_css_class("ghost-btn");
  refresh_btn_.signal_clicked().connect([this]() { refresh(); });
  controls->append(refresh_btn_);

  // Score strip
  auto* strip = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 16);
  strip->add_css_class("score-strip");
  strip->set_margin_start(28);
  strip->set_margin_end(28);
  strip->set_margin_bottom(12);
  root->append(*strip);

  score_label_.set_text("Score —");
  score_label_.add_css_class("score");
  strip->append(score_label_);

  score_bar_.set_fraction(1.0);
  score_bar_.set_hexpand(true);
  score_bar_.add_css_class("score-bar");
  strip->append(score_bar_);

  status_label_.set_text("OK");
  status_label_.add_css_class("status-pill");
  status_label_.add_css_class("sev-ok");
  strip->append(status_label_);

  // Metric chips
  auto* chips = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 12);
  chips->set_margin_start(28);
  chips->set_margin_end(28);
  chips->set_margin_bottom(12);
  root->append(*chips);
  for (Gtk::Label* lab : {&cpu_chip_, &mem_chip_, &disk_chip_, &load_chip_}) {
    lab->add_css_class("metric-chip");
    lab->set_hexpand(true);
    chips->append(*lab);
  }
  cpu_chip_.set_text("CPU —");
  mem_chip_.set_text("Memory —");
  disk_chip_.set_text("Disk —");
  load_chip_.set_text("Load —");

  // Notebook
  auto* nb = Gtk::make_managed<Gtk::Notebook>();
  nb->add_css_class("main-tabs");
  nb->set_hexpand(true);
  nb->set_vexpand(true);
  nb->set_margin_start(18);
  nb->set_margin_end(18);
  nb->set_margin_bottom(18);
  root->append(*nb);

  // Overview tab
  auto* overview = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 12);
  overview->set_margin(16);
  issues_label_.set_text("No active issues.");
  issues_label_.set_wrap(true);
  issues_label_.set_xalign(0);
  issues_label_.add_css_class("issues");
  overview->append(issues_label_);
  auto* ov_hint = Gtk::make_managed<Gtk::Label>(
      "When pressure is detected, BOSS-Sentinel asks Yes/No. Yes runs auto-heal and performance "
      "optimization, then shows what was optimized.");
  ov_hint->set_wrap(true);
  ov_hint->set_xalign(0);
  ov_hint->add_css_class("muted");
  overview->append(*ov_hint);
  nb->append_page(*overview, "Overview");

  // Processes
  auto* proc_scroll = Gtk::make_managed<Gtk::ScrolledWindow>();
  proc_buf_ = Gtk::TextBuffer::create();
  proc_view_.set_buffer(proc_buf_);
  proc_view_.set_editable(false);
  proc_view_.set_monospace(true);
  proc_view_.add_css_class("mono-pane");
  proc_scroll->set_child(proc_view_);
  proc_scroll->set_vexpand(true);
  nb->append_page(*proc_scroll, "Processes");

  // Services
  auto* svc_scroll = Gtk::make_managed<Gtk::ScrolledWindow>();
  svc_buf_ = Gtk::TextBuffer::create();
  svc_view_.set_buffer(svc_buf_);
  svc_view_.set_editable(false);
  svc_view_.set_monospace(true);
  svc_view_.add_css_class("mono-pane");
  svc_scroll->set_child(svc_view_);
  nb->append_page(*svc_scroll, "Services");

  // Logs
  auto* log_scroll = Gtk::make_managed<Gtk::ScrolledWindow>();
  log_buf_ = Gtk::TextBuffer::create();
  log_view_.set_buffer(log_buf_);
  log_view_.set_editable(false);
  log_view_.set_monospace(true);
  log_view_.add_css_class("mono-pane");
  log_scroll->set_child(log_view_);
  nb->append_page(*log_scroll, "Logs");
}

void MainWindow::on_toggle_autoheal() {
  settings_.prompt_on_issue = autoheal_switch_.get_active();
  settings_.save();
  Logger::instance().event("settings",
                           settings_.prompt_on_issue ? "Auto-heal prompts ON" : "Auto-heal prompts OFF");
}

void MainWindow::on_manual_optimize() {
  if (busy_) return;
  Snapshot snap = engine_.snapshot();
  ui::ask_autoheal(*this, "Manual optimize requested from the Optimize control.",
                   [this, snap](bool yes) {
                     if (yes) run_heal_and_optimize(snap);
                   });
}

void MainWindow::refresh() {
  if (busy_) {
    append_log_lines();
    return;
  }
  try {
    Snapshot snap = engine_.snapshot();
    render_snapshot(snap);
    maybe_prompt_autoheal(snap);
  } catch (const std::exception& e) {
    Logger::instance().error(std::string("Refresh failed: ") + e.what());
  }
  append_log_lines();
}

void MainWindow::render_snapshot(const Snapshot& snap) {
  char buf[128];
  std::snprintf(buf, sizeof(buf), "Score %d", snap.score);
  score_label_.set_text(buf);
  score_bar_.set_fraction(snap.score / 100.0);

  status_label_.set_text(severity_name(snap.overall));
  status_label_.remove_css_class("sev-ok");
  status_label_.remove_css_class("sev-warn");
  status_label_.remove_css_class("sev-crit");
  status_label_.add_css_class(severity_css(snap.overall));

  std::snprintf(buf, sizeof(buf), "CPU\n%.0f%%", snap.cpu_percent);
  cpu_chip_.set_text(buf);
  std::snprintf(buf, sizeof(buf), "Memory\n%.0f%%  (%.1f/%.1f GB)", snap.mem_percent, snap.mem_used_gb,
                snap.mem_total_gb);
  mem_chip_.set_text(buf);
  std::snprintf(buf, sizeof(buf), "Disk /\n%.0f%%", snap.disk_percent);
  disk_chip_.set_text(buf);
  std::snprintf(buf, sizeof(buf), "Load\n%.2f · %d thr", snap.load1, snap.threads);
  load_chip_.set_text(buf);

  if (snap.issues.empty()) {
    issues_label_.set_text("No active issues. System looks healthy.");
  } else {
    std::ostringstream ss;
    ss << "Active issues (" << snap.issues.size() << "):\n";
    for (const auto& i : snap.issues) {
      ss << " • [" << severity_name(i.severity) << "] " << i.title << " — " << i.description
         << "  → " << i.heal_label << "\n";
    }
    issues_label_.set_text(ss.str());
  }

  {
    std::ostringstream ss;
    ss << "PID     NAME                 MEM(MB)   USER\n";
    ss << "------------------------------------------------\n";
    for (const auto& p : snap.processes) {
      char line[160];
      std::snprintf(line, sizeof(line), "%-6d  %-18.18s  %7.1f   %s\n", p.pid, p.name.c_str(), p.mem_mb,
                    p.user.c_str());
      ss << line;
    }
    proc_buf_->set_text(ss.str());
  }

  {
    std::ostringstream ss;
    ss << "SERVICE                          ACTIVE   SUB\n";
    ss << "-----------------------------------------------\n";
    for (const auto& s : snap.services) {
      char line[160];
      std::snprintf(line, sizeof(line), "%-30.30s  %-7s  %s\n", s.name.c_str(), s.active.c_str(),
                    s.sub.c_str());
      ss << line;
    }
    if (snap.services.empty()) ss << "(no running services listed — systemd unavailable?)\n";
    svc_buf_->set_text(ss.str());
  }
}

void MainWindow::append_log_lines() {
  auto lines = Logger::instance().recent(180);
  std::ostringstream ss;
  ss << "Log file: " << Logger::instance().log_path() << "\n\n";
  for (const auto& l : lines) ss << l << '\n';
  log_buf_->set_text(ss.str());
}

void MainWindow::maybe_prompt_autoheal(const Snapshot& snap) {
  if (!settings_.prompt_on_issue) return;
  if (prompt_open_ || busy_) return;
  if (snap.issues.empty()) return;
  if (snap.overall == Severity::Ok) return;

  const double now = static_cast<double>(std::time(nullptr));
  if (last_prompt_ts_ > 0 && (now - last_prompt_ts_) < settings_.dialog_cooldown_sec) return;

  std::ostringstream summary;
  for (const auto& i : snap.issues) {
    summary << "• " << i.title << " (" << severity_name(i.severity) << ")\n";
  }

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
  optimize_btn_.set_sensitive(false);
  Logger::instance().info("User confirmed: starting auto-heal + performance optimization");

  // Run off the UI thread-ish: keep simple sync with busy cursor — GTK events still process on pkexec wait
  std::vector<ActionResult> heals = healer_.run_issue_heals(snap.issues);
  OptimizeReport report = optimizer_.run_all();

  std::ostringstream summary;
  summary << "Healing actions:\n";
  for (const auto& h : heals) {
    summary << " • " << h.action << ": " << h.message << (h.ok ? "\n" : " (failed)\n");
    Logger::instance().event("heal-result", h.action + " " + h.message);
  }
  summary << "\n" << report.summary_text();

  busy_ = false;
  optimize_btn_.set_sensitive(true);
  append_log_lines();
  ui::show_optimize_result(*this, summary.str(), 5000);
}

}  // namespace boss
