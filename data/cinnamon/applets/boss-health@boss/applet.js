/*
 * BOSS Health — Cinnamon panel applet (BOSS GNU/Linux 10+)
 * Left-click → open System Readiness dashboard (no menu hijack).
 */
const Applet = imports.ui.applet;
const GLib = imports.gi.GLib;
const Main = imports.ui.main;
const Util = imports.misc.util;
const Lang = imports.lang;

function BossHealthApplet(metadata, orientation, panel_height, instance_id) {
    this._init(metadata, orientation, panel_height, instance_id);
}

BossHealthApplet.prototype = {
    __proto__: Applet.IconApplet.prototype,

    _init: function (metadata, orientation, panel_height, instance_id) {
        Applet.IconApplet.prototype._init.call(this, orientation, panel_height, instance_id);
        this.metadata = metadata;

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

        this.set_applet_tooltip("BOSS Health — click to open System Readiness");
    },

    on_applet_clicked: function (event) {
        this._launchDashboard();
    },

    _notify: function (msg) {
        try {
            Main.notify("BOSS Health", msg);
        } catch (e) {
            global.logError("BOSS Health: " + msg);
        }
    },

    _launchDashboard: function () {
        // Always use absolute path — PATH is unreliable from Cinnamon
        let candidates = [
            "/usr/bin/boss-health",
            "/usr/local/bin/boss-health"
        ];
        let exe = null;
        for (let i = 0; i < candidates.length; i++) {
            if (GLib.file_test(candidates[i], GLib.FileTest.IS_EXECUTABLE)) {
                exe = candidates[i];
                break;
            }
        }
        if (!exe) {
            let p = GLib.find_program_in_path("boss-health");
            if (p) exe = p;
        }
        if (!exe) {
            this._notify("boss-health not found. Reinstall the package.");
            return;
        }

        try {
            // argv spawn is more reliable than shell command line on BOSS 10
            GLib.spawn_async(
                null,
                [exe],
                null,
                GLib.SpawnFlags.SEARCH_PATH,
                null
            );
            return;
        } catch (e1) {
            global.logError("BOSS Health spawn_async failed: " + e1);
        }

        try {
            if (typeof Util.spawnCommandLine === "function") {
                Util.spawnCommandLine(exe);
                return;
            }
        } catch (e2) {
            global.logError("BOSS Health spawnCommandLine failed: " + e2);
        }

        try {
            GLib.spawn_command_line_async(exe);
        } catch (e3) {
            this._notify("Could not open dashboard: " + e3);
        }
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    return new BossHealthApplet(metadata, orientation, panel_height, instance_id);
}
