#include "ui/gauges.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>

namespace boss::ui {

DeviceGraph::DeviceGraph(const Glib::ustring& title)
    : Gtk::Box(Gtk::Orientation::VERTICAL, 6), title_(title) {
  add_css_class("device-graph");
  set_hexpand(true);
  set_margin_start(10);
  set_margin_end(10);
  set_margin_top(10);
  set_margin_bottom(10);

  title_.set_xalign(0);
  title_.add_css_class("device-graph-title");
  title_.set_text(title.uppercase());

  value_.set_xalign(0);
  value_.add_css_class("device-graph-value");
  value_.set_text("0%");

  detail_.set_xalign(0);
  detail_.add_css_class("device-graph-detail");
  detail_.set_ellipsize(Pango::EllipsizeMode::END);

  bar_.set_min_value(0.0);
  bar_.set_max_value(100.0);
  bar_.set_value(0.0);
  bar_.set_mode(Gtk::LevelBar::Mode::CONTINUOUS);
  bar_.set_hexpand(true);
  bar_.add_css_class("device-graph-bar");

  append(title_);
  append(value_);
  append(detail_);
  append(bar_);
  set_content_height(140);
}

void DeviceGraph::set_content_height(int height) {
  set_size_request(-1, std::max(100, height));
}

void DeviceGraph::apply_severity(double pct) {
  remove_css_class("sev-ok");
  remove_css_class("sev-warn");
  remove_css_class("sev-crit");
  if (pct >= crit_)
    add_css_class("sev-crit");
  else if (pct >= warn_)
    add_css_class("sev-warn");
  else
    add_css_class("sev-ok");
}

void DeviceGraph::update(double value, const Glib::ustring& unit, const Glib::ustring& detail, double warn,
                         double crit) {
  warn_ = warn;
  crit_ = crit;
  char text[64];
  std::snprintf(text, sizeof(text), "%.0f%s", value, unit.c_str());
  value_.set_text(text);
  detail_.set_text(detail);

  double plotted = value;
  if (unit == "°C")
    plotted = std::min(100.0, value);
  else if (unit != "%")
    plotted = std::min(100.0, value);
  plotted = std::clamp(plotted, 0.0, 100.0);
  bar_.set_value(plotted);
  apply_severity(plotted);
}

HeroVitality::HeroVitality() : Gtk::Box(Gtk::Orientation::VERTICAL, 2) {
  add_css_class("hero-vitality");
  set_valign(Gtk::Align::CENTER);
  set_size_request(120, 120);

  score_.set_text("100");
  score_.add_css_class("hero-score");
  score_.set_halign(Gtk::Align::CENTER);

  caption_.set_text("HEALTH");
  caption_.add_css_class("hero-caption");
  caption_.set_halign(Gtk::Align::CENTER);

  append(score_);
  append(caption_);
  add_css_class("sev-ok");
}

void HeroVitality::set_score(int score, const Glib::ustring& overall) {
  score_value_ = std::clamp(score, 0, 100);
  char text[16];
  std::snprintf(text, sizeof(text), "%d", score_value_);
  score_.set_text(text);

  remove_css_class("sev-ok");
  remove_css_class("sev-warn");
  remove_css_class("sev-crit");
  if (overall == "warn")
    add_css_class("sev-warn");
  else if (overall == "crit" || overall == "critical")
    add_css_class("sev-crit");
  else
    add_css_class("sev-ok");
}

BreathWave::BreathWave() : Gtk::Box(Gtk::Orientation::VERTICAL, 4) {
  add_css_class("breath-wave");
  set_hexpand(true);
  set_margin_start(20);
  set_margin_end(20);
  set_margin_top(4);
  set_margin_bottom(4);
  samples_.assign(20, 100.0);

  label_.set_xalign(0);
  label_.add_css_class("breath-label");
  label_.set_text("VITALITY TREND  ·  100");

  bar_.set_min_value(0.0);
  bar_.set_max_value(100.0);
  bar_.set_value(100.0);
  bar_.set_mode(Gtk::LevelBar::Mode::CONTINUOUS);
  bar_.set_hexpand(true);
  bar_.add_css_class("breath-bar");

  append(label_);
  append(bar_);
}

void BreathWave::push(double score) {
  samples_.push_back(std::clamp(score, 0.0, 100.0));
  if (samples_.size() > 20) samples_.pop_front();
  double avg = 0.0;
  for (double s : samples_) avg += s;
  avg /= static_cast<double>(samples_.size());
  bar_.set_value(avg);
  char text[64];
  std::snprintf(text, sizeof(text), "VITALITY TREND  ·  %.0f", avg);
  label_.set_text(text);
}

}  // namespace boss::ui
