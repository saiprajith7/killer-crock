#include "app/application.hpp"

#include "core/logger.hpp"
#include "ui/main_window.hpp"

namespace boss {

Application::Application()
    : Gtk::Application("org.bosssentinel.BossSentinel", Gio::Application::Flags::DEFAULT_FLAGS) {}

Glib::RefPtr<Application> Application::create() {
  return Glib::make_refptr_for_instance<Application>(new Application());
}

void Application::on_activate() {
  Logger::instance().info("Application activate");
  auto* win = new MainWindow();
  add_window(*win);
  win->signal_hide().connect([win]() { delete win; });
  win->present();
}

}  // namespace boss
