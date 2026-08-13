#pragma once

#include <deque>
#include <string>

#include <gtkmm.h>

namespace boss::ui {

class DeviceGraph : public Gtk::DrawingArea {
 public:
  explicit DeviceGraph(const Glib::ustring& title = "DEVICE");
  void update(double value, const Glib::ustring& unit = "%", const Glib::ustring& detail = "",
              double warn = 85.0, double crit = 95.0);

 private:
  void on_draw(const Cairo::RefPtr<Cairo::Context>& cr, int width, int height);
  bool on_tick();

  Glib::ustring title_;
  double value_ = 0;
  Glib::ustring unit_ = "%";
  Glib::ustring detail_;
  double warn_ = 85;
  double crit_ = 95;
  std::deque<double> history_;
  double phase_ = 0;
};

class HeroVitality : public Gtk::DrawingArea {
 public:
  HeroVitality();
  void set_score(int score, const Glib::ustring& overall = "ok");

 private:
  void on_draw(const Cairo::RefPtr<Cairo::Context>& cr, int width, int height);
  bool on_tick();

  int score_ = 100;
  Glib::ustring overall_ = "ok";
  double phase_ = 0;
};

class BreathWave : public Gtk::DrawingArea {
 public:
  BreathWave();
  void push(double score);

 private:
  void on_draw(const Cairo::RefPtr<Cairo::Context>& cr, int width, int height);
  bool on_tick();

  std::deque<double> samples_;
  double phase_ = 0;
};

}  // namespace boss::ui
