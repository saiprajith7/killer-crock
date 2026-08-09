# BOSS-Sentinel

**Lightweight minimal blue PC health monitor with interactive autohealing for Debian.**

Native GTK4 (not Electron/web). Low overhead: vitals poll every 3s, apt only on demand.

## Install

```bash
curl -fL -o ~/Downloads/boss-sentinel_1.2.0-1_all.deb \
  https://github.com/saiprajith7/killer-crock/raw/cursor/vitaheal-pc-monitor-02f6/releases/boss-sentinel_1.2.0-1_all.deb

sudo apt install --reinstall ~/Downloads/boss-sentinel_1.2.0-1_all.deb
boss-sentinel
```

Zip: https://github.com/saiprajith7/killer-crock/raw/cursor/vitaheal-pc-monitor-02f6/releases/boss-sentinel-deb.zip

## Tabs

| Tab | Contents |
|-----|----------|
| Overview | Device graphs + active issues |
| CPU | Cores, threads, model, per-core bars |
| Memory | RAM + Swap |
| Disk | Volumes + graph |
| GPU | Util / VRAM / temp / power |
| Thermal | All sensors |
| **Updates** | Reads `/etc/apt/sources.list*`, checks repos, Yes/No install |
| Logs | Trouble · Heal · **Update Log** |

Autoheal and upgrades always ask **Yes / No** before changing the system.
