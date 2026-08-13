#include "ui/dialogs.hpp"

#include <glibmm.h>

#include "core/logger.hpp"

namespace boss::ui {
namespace {

class ResultPopup : public Gtk::Window {
 public:
  ResultPopup(Gtk::Window& parent, const std::string& summary, int autoclose_ms) {
    set_transient_for(parent);
    set_modal(true);
    set_title("Performance optimized");
    set_default_size(440, 300);
    set_resizable(false);
    add_css_class("result-popup");

    auto* outer = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::VERTICAL, 14);
    outer->set_margin(22);
    set_child(*outer);

    auto* brand = Gtk::make_managed<Gtk::Label>("BOSS-SENTINEL");
    brand->add_css_class("brand-sm");
    brand->set_xalign(0);
    outer->append(*brand);

    auto* title = Gtk::make_managed<Gtk::Label>("Performance optimized");
    title->add_css_class("popup-title");
    title->set_xalign(0);
    outer->append(*title);

    auto* scroll = Gtk::make_managed<Gtk::ScrolledWindow>();
    scroll->set_policy(Gtk::PolicyType::NEVER, Gtk::PolicyType::AUTOMATIC);
    scroll->set_vexpand(true);
    scroll->set_min_content_height(120);
    outer->append(*scroll);

    auto* body = Gtk::make_managed<Gtk::Label>(summary);
    body->set_wrap(true);
    body->set_xalign(0);
    body->set_yalign(0);
    body->add_css_class("popup-body");
    scroll->set_child(*body);

    auto* row = Gtk::make_managed<Gtk::Box>(Gtk::Orientation::HORIZONTAL, 10);
    outer->append(*row);

    auto* hint = Gtk::make_managed<Gtk::Label>("Closing shortly…");
    hint->add_css_class("muted");
    hint->set_hexpand(true);
    hint->set_xalign(0);
    row->append(*hint);

    auto* close_btn = Gtk::make_managed<Gtk::Button>("Close");
    close_btn->add_css_class("accent-btn");
    close_btn->signal_clicked().connect([this]() { close(); });
    row->append(*close_btn);

    present();

    Glib::signal_timeout().connect_seconds(
        [this]() {
          close();
          return false;
        },
        std::max(2, autoclose_ms / 1000));
  }
};

}  // namespace

void ask_autoheal(Gtk::Window& parent, const std::string& issue_summary,
                  std::function<void(bool accepted)> on_answer) {
  Logger::instance().event("ui", "Prompting autoheal + optimize");

  // Gtk::AlertDialog needs GTK ≥ 4.10; Debian 12 / BOSS ships 4.8 → MessageDialog
  auto* dialog = new Gtk::MessageDialog(
      parent, "Auto-heal and optimize performance?", false, Gtk::MessageType::QUESTION,
      Gtk::ButtonsType::YES_NO, true);
  dialog->set_secondary_text(
      "BOSS-Sentinel detected system pressure:\n\n" + issue_summary +
      "\n\nYes — auto-heal issues and run performance optimization.\n"
      "No — keep monitoring only.");
  dialog->set_default_response(Gtk::ResponseType::YES);
  dialog->set_modal(true);

  dialog->signal_response().connect([dialog, on_answer](int response) {
    const bool yes = (response == Gtk::ResponseType::YES);
    Logger::instance().event("ui", yes ? "User accepted autoheal" : "User declined autoheal");
    dialog->hide();
    delete dialog;
    if (on_answer) on_answer(yes);
  });
  dialog->present();
}

void show_optimize_result(Gtk::Window& parent, const std::string& summary, int autoclose_ms) {
  Logger::instance().event("ui", "Showing optimize result popup");
  auto* popup = new ResultPopup(parent, summary, autoclose_ms);
  popup->signal_hide().connect([popup]() {
    Logger::instance().event("ui", "Optimize result popup closed");
    delete popup;
  });
}

}  // namespace boss::ui
