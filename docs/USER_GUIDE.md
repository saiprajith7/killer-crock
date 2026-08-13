# BOSS-Sentinel — User Guide

**Version 2.2.2** — for BOSS Linux / Debian 12.

---

## Install (recommended)

Removes old Sentinel/Optimize packages and leftover `.deb` files, then installs the unified app:

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/install-unified.sh | bash
boss-sentinel
```

The new package is kept at:

```text
~/boss-sentinel/boss-sentinel_2.2.2-1_amd64.deb
```

### Manual `.deb`

```bash
curl -L -o boss-sentinel_2.2.2-1_amd64.deb \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/releases/boss-sentinel_2.2.2-1_amd64.deb

sudo dpkg -i ./boss-sentinel_2.2.2-1_amd64.deb
sudo apt-get install -f -y   # pulls python3-gi / python3-cairo if needed
boss-sentinel
```

> On BOSS, prefer `dpkg -i` over `apt-get install ./file.deb` when DebVerify blocks local packages.

---

## Complete removal

Wipe packages, `/usr` files, configs, logs, and leftover `.deb`s:

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/purge-boss-sentinel.sh | bash
```

---

## Using the app

### Top bar

- **BOSS-SENTINEL** brand on the left  
- **AUTOHEAL GUARD** ON / OFF segmented buttons on the right  
- × closes the window  

### Tabs

| Tab | What you do |
|-----|-------------|
| Overview | Glance at live graphs + issues |
| CPU | GNOME-style per-CPU history + meters |
| Memory | RAM / swap graphs |
| Disk | Pie chart + usage trend |
| Processes | Top memory consumers |
| Services | Running systemd services |
| Autoheal | Toggle + heal log + “Run heal now” |
| Optimize | YES / NO performance suite |
| Updates | CHECK UPDATES / INSTALL UPDATES |
| Logs | Trouble · Heal · Update · Full file |

### Autoheal behavior

- **ON:** when CPU/RAM/disk/swap/temp pressure rises, a Yes/No dialog appears. Yes runs heal + optimize.  
- **OFF:** monitor only (you can still use Autoheal / Optimize tabs manually).

### Logs & settings locations

```text
~/.config/boss-sentinel/settings.json
~/.local/share/boss-sentinel/boss-sentinel.log
```

---

## Optional C++ GTK4 UI

Only if you need it (often crashes on BOSS GPU/EGL):

```bash
BOSS_SENTINEL_UI=cpp boss-sentinel
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: gi` | `sudo apt-get install -y python3-gi gir1.2-gtk-3.0 python3-cairo` |
| Window never opens | Confirm `dpkg -l boss-sentinel` shows **2.2.2-1**; run `boss-sentinel` from a terminal |
| Helper password prompts | Expected — polkit/`pkexec` for privileged actions |
| Old Optimize still listed | Run `purge-boss-sentinel.sh`, then reinstall |

---

## Verify version

```bash
dpkg -l boss-sentinel
head -5 ~/.local/share/boss-sentinel/boss-sentinel.log
```

Log should mention `rich GTK3 UI 2.2.2`.
