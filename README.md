# BOSS-Sentinel

Unified **health monitoring**, **auto-heal**, and **performance optimization**.

Default UI is **Python GTK3** (stable on BOSS). Optional C++ GTK4 binary is included
but not used by default (`BOSS_SENTINEL_UI=cpp` to force it).

## Remove completely from the system

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/purge-boss-sentinel.sh | bash
```

## Install (BOSS Linux / Debian 12)

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/install-unified.sh | bash
```

Or install the package directly:

```bash
curl -L -o boss-sentinel_2.1.4-1_amd64.deb \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/releases/boss-sentinel_2.1.4-1_amd64.deb
sudo dpkg -i ./boss-sentinel_2.1.4-1_amd64.deb
sudo apt-get install -f -y   # if python3-gi / gir1.2-gtk-3.0 missing
boss-sentinel
```

## Build

See [docs/BUILD.md](docs/BUILD.md). System design: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).
