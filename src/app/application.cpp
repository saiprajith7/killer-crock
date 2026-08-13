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
  // Defer delete so we never free the window mid-present/hide during startup failures
  win->signal_close_request().connect(
      [win]() {
        win->hide();
        Glib::signal_idle().connect_once([win]() { delete win; });
        return true;
      },
      false);
  try {
    win->present();
  } catch (const Glib::Error& e) {
    Logger::instance().error(std::string("present failed: ") + e.what());
  } catch (...) {
    Logger::instance().error("present failed with unknown error");
  }
}

}  // namespace boss
