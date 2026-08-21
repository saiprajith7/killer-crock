/*
 * BOSS Health — Cinnamon panel applet (BOSS GNU/Linux 10+)
 * Click → open BOSS Health System Readiness dashboard
 *
 * Compatible with older Cinnamon: no spawnCommandLineAsync, safe gettext.
 */
const Applet = imports.ui.applet;
const GLib = imports.gi.GLib;
const Gio = imports.gi.Gio;
const Util = imports.misc.util;
const Lang = imports.lang;
const PopupMenu = imports.ui.popupMenu;
const Gettext = imports.gettext;

Gettext.bindtextdomain("boss-health", GLib.get_home_dir() + "/.local/share/locale");
function _(str) {
    try {
        return Gettext.dgettext("boss-health", str);
    } catch (e) {
        return str;
    }
}

function BossHealthApplet(metadata, orientation, panel_height, instance_id) {
    this._init(metadata, orientation, panel_height, instance_id);
}

BossHealthApplet.prototype = {
    __proto__: Applet.IconApplet.prototype,

    _init: function (metadata, orientation, panel_height, instance_id) {
        Applet.IconApplet.prototype._init.call(this, orientation, panel_height, instance_id);
        this.metadata = metadata;

        // Prefer applet-local icon.png (works on BOSS 10 / older Cinnamon)
        try {
            if (metadata && metadata.path) {
                this.set_applet_icon_path(metadata.path + "/icon.png");
            } else {
                this.set_applet_icon_name("boss-health");
            }
        } catch (e1) {
            try {
                this.set_applet_icon_name("utilities-system-monitor");
            } catch (e2) {}
        }

        this.set_applet_tooltip("BOSS Health — System Readiness");

        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this.menuManager.addMenu(this.menu);

        let openItem = new PopupMenu.PopupMenuItem("Open BOSS Health dashboard");
        openItem.connect("activate", Lang.bind(this, this._launchDashboard));
        this.menu.addMenuItem(openItem);
    },

    on_applet_clicked: function (event) {
        this._launchDashboard();
    },

    _launchDashboard: function () {
        let cmd = null;
        if (GLib.find_program_in_path("boss-health")) {
            cmd = "boss-health";
        } else if (GLib.find_program_in_path("python3")) {
            cmd = "python3 -m boss_health";
        }

        if (!cmd) {
            global.logError("BOSS Health: boss-health command not found");
            return;
        }

        // Older Cinnamon has spawnCommandLine only (not Async)
        try {
            if (typeof Util.spawnCommandLine === "function") {
                Util.spawnCommandLine(cmd);
                return;
            }
        } catch (e) {}

        try {
            GLib.spawn_command_line_async(cmd);
        } catch (e2) {
            global.logError("BOSS Health launch failed: " + e2);
        }
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    return new BossHealthApplet(metadata, orientation, panel_height, instance_id);
}
