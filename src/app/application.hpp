#pragma once

#include <gtkmm.h>

namespace boss {

class Application : public Gtk::Application {
 public:
  Application();
  static Glib::RefPtr<Application> create();

 protected:
  void on_activate() override;
};

}  // namespace boss
