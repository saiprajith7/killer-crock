# BOSS-Sentinel

**Minimal blue PC health monitor with interactive autohealing for Debian.**

Native GTK4 app (not web). Tabbed UI: Overview · CPU · Memory · Disk · GPU · Thermal · Logs.

## Install

```bash
curl -fL -o ~/Downloads/boss-sentinel_1.1.0-1_all.deb \
  https://github.com/saiprajith7/killer-crock/raw/cursor/vitaheal-pc-monitor-02f6/releases/boss-sentinel_1.1.0-1_all.deb

sudo apt install --reinstall ~/Downloads/boss-sentinel_1.1.0-1_all.deb
boss-sentinel
```

Or zip: https://github.com/saiprajith7/killer-crock/raw/cursor/vitaheal-pc-monitor-02f6/releases/boss-sentinel-deb.zip

## Run from source

```bash
sudo apt install -y python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1 libnotify-bin fonts-jetbrains-mono
PYTHONPATH=src python3 -m vitaheal
```

## Tabs

| Tab | Contents |
|-----|----------|
| Overview | Device graphs + active issues |
| CPU | Cores, threads, model, per-core bars |
| Memory | RAM + Swap |
| Disk | Volumes + graph |
| GPU | Util / VRAM / temp / power |
| Thermal | All sensors |
| Logs | Trouble Log · Heal Log |

Autoheal always asks **Yes / No** before repairing.
