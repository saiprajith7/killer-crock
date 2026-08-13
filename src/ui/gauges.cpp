#include "ui/gauges.hpp"

#include <cairomm/context.h>
#include <cairomm/fontface.h>

#include <cmath>
#include <cstdio>

namespace boss::ui {
namespace {

constexpr double CANVAS[3] = {0.945, 0.961, 0.976};
constexpr double SURFACE[3] = {1.0, 1.0, 1.0};
constexpr double BLUE[3] = {0.145, 0.388, 0.922};
constexpr double OK[3] = {0.02, 0.588, 0.412};
constexpr double AMBER[3] = {0.851, 0.467, 0.024};
constexpr double FAULT[3] = {0.863, 0.149, 0.149};
constexpr double MIST[3] = {0.20, 0.255, 0.333};
constexpr double MUTED[3] = {0.392, 0.455, 0.545};

void color_for(double pct, double warn, double crit, double out[3]) {
  const double* c = BLUE;
  if (pct >= crit)
    c = FAULT;
  else if (pct >= warn)
    c = AMBER;
  out[0] = c[0];
  out[1] = c[1];
  out[2] = c[2];
}

}  // namespace

DeviceGraph::DeviceGraph(const Glib::ustring& title) : title_(title) {
  set_content_width(280);
  set_content_height(150);
  set_hexpand(true);
  history_.assign(60, 0.0);
  set_draw_func(sigc::mem_fun(*this, &DeviceGraph::on_draw));
  Glib::signal_timeout().connect(sigc::mem_fun(*this, &DeviceGraph::on_tick), 100);
}

void DeviceGraph::update(double value, const Glib::ustring& unit, const Glib::ustring& detail, double warn,
                         double crit) {
  value_ = value;
  unit_ = unit;
  detail_ = detail;
  warn_ = warn;
  crit_ = crit;
  double plotted = value;
  if (unit == "°C")
    plotted = std::min(100.0, value);
  else if (unit != "%")
    plotted = std::min(100.0, value);
  history_.push_back(std::clamp(plotted, 0.0, 100.0));
  if (history_.size() > 60) history_.pop_front();
  queue_draw();
}

bool DeviceGraph::on_tick() {
  phase_ = std::fmod(phase_ + 0.05, M_PI * 2);
  queue_draw();
  return true;
}

void DeviceGraph::on_draw(const Cairo::RefPtr<Cairo::Context>& cr, int w, int h) {
  if (w < 32 || h < 32) return;
  cr->set_source_rgb(SURFACE[0], SURFACE[1], SURFACE[2]);
  cr->rectangle(0, 0, w, h);
  cr->fill();

  double color[3];
  color_for(unit_ == "%" || unit_ == "°C" ? value_ : history_.back(), warn_, crit_, color);

  cr->select_font_face("Sans", Cairo::ToyFontFace::Slant::NORMAL, Cairo::ToyFontFace::Weight::NORMAL);
  cr->set_font_size(11);
  cr->set_source_rgb(MUTED[0], MUTED[1], MUTED[2]);
  cr->move_to(14, 22);
  cr->show_text(title_.uppercase());

  char text[64];
  std::snprintf(text, sizeof(text), "%.0f%s", value_, unit_.c_str());
  cr->select_font_face("Sans", Cairo::ToyFontFace::Slant::NORMAL, Cairo::ToyFontFace::Weight::BOLD);
  cr->set_font_size(28);
  cr->set_source_rgb(color[0], color[1], color[2]);
  cr->move_to(14, 54);
  cr->show_text(text);

  if (!detail_.empty()) {
    cr->select_font_face("Sans", Cairo::ToyFontFace::Slant::NORMAL, Cairo::ToyFontFace::Weight::NORMAL);
    cr->set_font_size(10);
    cr->set_source_rgba(MIST[0], MIST[1], MIST[2], 0.7);
    cr->move_to(14, 72);
    Glib::ustring clipped = detail_.size() > 48 ? detail_.substr(0, 48) : detail_;
    cr->show_text(clipped);
  }

  const double top = 84, bottom = h - 14, left = 14, right = w - 14;
  const double gh = bottom - top;
  const double gw = right - left;

  cr->set_source_rgba(BLUE[0], BLUE[1], BLUE[2], 0.12);
  cr->set_line_width(1);
  cr->move_to(left, bottom);
  cr->line_to(right, bottom);
  cr->stroke();

  if (history_.size() < 2) return;
  const size_t n = history_.size();

  cr->move_to(left, bottom);
  for (size_t i = 0; i < n; ++i) {
    double x = left + (static_cast<double>(i) / (n - 1)) * gw;
    double y = bottom - (history_[i] / 100.0) * gh;
    y += std::sin(phase_ + i * 0.15) * 0.5;
    cr->line_to(x, y);
  }
  cr->line_to(right, bottom);
  cr->close_path();
  cr->set_source_rgba(color[0], color[1], color[2], 0.12);
  cr->fill();

  cr->set_line_width(2);
  cr->set_source_rgb(color[0], color[1], color[2]);
  for (size_t i = 0; i < n; ++i) {
    double x = left + (static_cast<double>(i) / (n - 1)) * gw;
    double y = bottom - (history_[i] / 100.0) * gh;
    y += std::sin(phase_ + i * 0.15) * 0.5;
    if (i == 0)
      cr->move_to(x, y);
    else
      cr->line_to(x, y);
  }
  cr->stroke();

  double x = right;
  double y = bottom - (history_.back() / 100.0) * gh;
  cr->set_source_rgba(color[0], color[1], color[2], 0.95);
  cr->arc(x, y, 3.0, 0, M_PI * 2);
  cr->fill();
}

HeroVitality::HeroVitality() {
  set_content_width(150);
  set_content_height(150);
  set_draw_func(sigc::mem_fun(*this, &HeroVitality::on_draw));
  Glib::signal_timeout().connect(sigc::mem_fun(*this, &HeroVitality::on_tick), 50);
}

void HeroVitality::set_score(int score, const Glib::ustring& overall) {
  score_ = std::clamp(score, 0, 100);
  overall_ = overall;
  queue_draw();
}

bool HeroVitality::on_tick() {
  phase_ = std::fmod(phase_ + 0.035, M_PI * 2);
  queue_draw();
  return true;
}

void HeroVitality::on_draw(const Cairo::RefPtr<Cairo::Context>& cr, int w, int h) {
  if (w < 20 || h < 20) return;
  cr->set_source_rgb(CANVAS[0], CANVAS[1], CANVAS[2]);
  cr->rectangle(0, 0, w, h);
  cr->fill();

  const double cx = w / 2.0, cy = h / 2.0;
  const double* color = OK;
  if (overall_ == "warn")
    color = AMBER;
  else if (overall_ == "crit" || overall_ == "critical")
    color = FAULT;
  const double breath = 0.94 + 0.06 * std::sin(phase_);

  cr->set_source_rgba(color[0], color[1], color[2], 0.18);
  cr->set_line_width(2);
  cr->arc(cx, cy, std::min(w, h) * 0.42 * breath, 0, M_PI * 2);
  cr->stroke();

  cr->set_source_rgb(color[0], color[1], color[2]);
  cr->set_line_width(2.5);
  cr->arc(cx, cy, std::min(w, h) * 0.36, 0, M_PI * 2);
  cr->stroke();

  cr->select_font_face("Sans", Cairo::ToyFontFace::Slant::NORMAL, Cairo::ToyFontFace::Weight::BOLD);
  cr->set_font_size(40);
  char text[16];
  std::snprintf(text, sizeof(text), "%d", score_);
  Cairo::TextExtents ext;
  cr->get_text_extents(text, ext);
  cr->move_to(cx - ext.width / 2 - ext.x_bearing, cy + ext.height / 2 - 4);
  cr->show_text(text);

  cr->set_font_size(10);
  cr->set_source_rgb(MUTED[0], MUTED[1], MUTED[2]);
  const char* label = "HEALTH";
  cr->get_text_extents(label, ext);
  cr->move_to(cx - ext.width / 2 - ext.x_bearing, cy + 28);
  cr->show_text(label);
}

BreathWave::BreathWave() {
  set_content_height(44);
  set_hexpand(true);
  samples_.assign(100, 100.0);
  set_draw_func(sigc::mem_fun(*this, &BreathWave::on_draw));
  Glib::signal_timeout().connect(sigc::mem_fun(*this, &BreathWave::on_tick), 80);
}

void BreathWave::push(double score) {
  samples_.push_back(std::clamp(score, 0.0, 100.0));
  if (samples_.size() > 100) samples_.pop_front();
}

bool BreathWave::on_tick() {
  phase_ += 0.12;
  queue_draw();
  return true;
}

void BreathWave::on_draw(const Cairo::RefPtr<Cairo::Context>& cr, int w, int h) {
  if (w < 10 || h < 10) return;
  cr->set_source_rgb(CANVAS[0], CANVAS[1], CANVAS[2]);
  cr->rectangle(0, 0, w, h);
  cr->fill();
  if (samples_.size() < 2) return;

  cr->set_line_width(2);
  cr->set_source_rgb(BLUE[0], BLUE[1], BLUE[2]);
  const size_t n = samples_.size();
  for (size_t i = 0; i < n; ++i) {
    double x = static_cast<double>(i) / (n - 1) * w;
    double y = h - (samples_[i] / 100.0) * (h - 10) - 5;
    y += std::sin(phase_ + i * 0.12) * 0.6;
    if (i == 0)
      cr->move_to(x, y);
    else
      cr->line_to(x, y);
  }
  cr->stroke();
}

}  // namespace boss::ui
