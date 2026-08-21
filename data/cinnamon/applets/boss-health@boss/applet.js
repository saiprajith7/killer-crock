/*
 * BOSS Health Cinnamon applet
 * Click → run readiness checks → open BOSS Health dashboard
 */
const Applet = imports.ui.applet;
const Main = imports.ui.main;
const GLib = imports.gi.GLib;
const Util = imports.misc.util;
const Lang = imports.lang;
const PopupMenu = imports.ui.popupMenu;
const St = imports.gi.St;

function BossHealthApplet(orientation, panel_height, instance_id) {
    this._init(orientation, panel_height, instance_id);
}

BossHealthApplet.prototype = {
    __proto__: Applet.IconApplet.prototype,

    _init: function (orientation, panel_height, instance_id) {
        Applet.IconApplet.prototype._init.call(this, orientation, panel_height, instance_id);

        try {
            this.set_applet_icon_name("boss-health");
        } catch (e) {
            this.set_applet_icon_symbolic_name("utilities-system-monitor");
        }
        this.set_applet_tooltip(_("BOSS Health — System Readiness"));

        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this.menuManager.addMenu(this.menu);

        let openItem = new PopupMenu.PopupMenuItem(_("Open BOSS Health dashboard"));
        openItem.connect("activate", Lang.bind(this, this._launchDashboard));
        this.menu.addMenuItem(openItem);

        let againItem = new PopupMenu.PopupMenuItem(_("Run check & open"));
        againItem.connect("activate", Lang.bind(this, this._launchDashboard));
        this.menu.addMenuItem(againItem);
    },

    on_applet_clicked: function (event) {
        this._launchDashboard();
    },

    _launchDashboard: function () {
        // Prefer installed binary; fall back to module for source installs.
        let cmd = "boss-health";
        let path = GLib.find_program_in_path(cmd);
        if (path) {
            Util.spawnCommandLineAsync(cmd);
            return;
        }
        Util.spawnCommandLineAsync("python3 -m boss_health");
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    return new BossHealthApplet(orientation, panel_height, instance_id);
}
