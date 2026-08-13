#pragma once

#include <deque>
#include <string>

#include <gtkmm.h>

namespace boss::ui {

// Software-safe metric panel (no Cairo DrawingArea — BOSS EGL/DRI2 crashes custom draw).
class DeviceGraph : public Gtk::Box {
 public:
  explicit DeviceGraph(const Glib::ustring& title = "DEVICE");
  void update(double value, const Glib::ustring& unit = "%", const Glib::ustring& detail = "",
              double warn = 85.0, double crit = 95.0);
  void set_content_height(int height);

 private:
  void apply_severity(double pct);

  Gtk::Label title_;
  Gtk::Label value_;
  Gtk::Label detail_;
  Gtk::LevelBar bar_;
  double warn_ = 85.0;
  double crit_ = 95.0;
};

class HeroVitality : public Gtk::Box {
 public:
  HeroVitality();
  void set_score(int score, const Glib::ustring& overall = "ok");

 private:
  int score_value_ = 100;
  Gtk::Label score_;
  Gtk::Label caption_;
};

class BreathWave : public Gtk::Box {
 public:
  BreathWave();
  void push(double score);

 private:
  Gtk::LevelBar bar_;
  Gtk::Label label_;
  std::deque<double> samples_;
};

}  // namespace boss::ui
