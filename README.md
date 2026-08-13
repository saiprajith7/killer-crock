# BOSS-Sentinel

Unified **health monitoring**, **auto-heal**, and **performance optimization**.

Default UI is **Python GTK3** (stable on BOSS). Optional C++ GTK4 binary is included
but not used by default (`BOSS_SENTINEL_UI=cpp` to force it).

## Remove completely

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/purge-boss-sentinel.sh | bash
```

## Install (BOSS Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/install-unified.sh | bash
boss-sentinel
```

**v2.2.0** restores the confirmed rich UI on stable GTK3:
Overview / CPU / Memory / Disk (pie chart) / Processes / Services / Optimize / Logs,
live Cairo graphs, vitality ring, and an ON/OFF autoheal control.

Package: `releases/boss-sentinel_2.2.0-1_amd64.deb`
