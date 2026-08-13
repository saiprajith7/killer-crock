# BOSS-Sentinel

Unified **health monitoring**, **autoheal**, and **performance optimization**.

Default UI: **Python GTK3** (stable on BOSS). Optional C++ GTK4 via `BOSS_SENTINEL_UI=cpp`.

---

## Documentation (start here)

| Doc | Description |
|-----|-------------|
| [docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md) | **Master index** |
| [docs/BOSS-Sentinel-Complete-Guide.docx](docs/BOSS-Sentinel-Complete-Guide.docx) | **Word/Google Docs full guide** |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Install, use, purge |
| [docs/FILE_STRUCTURE.md](docs/FILE_STRUCTURE.md) | Full file tree |
| [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | Architecture & flows |
| [docs/CODE_WALKTHROUGH.md](docs/CODE_WALKTHROUGH.md) | **Step-by-step code explanation** |
| [docs/BUILD.md](docs/BUILD.md) | Build & package `.deb` |

---

## Remove completely

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/purge-boss-sentinel.sh | bash
```

## Install (BOSS Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/install-unified.sh | bash
boss-sentinel
```

**v2.2.5** — Autoheal + Updates tabs, Logs sub-tabs, GNOME per-CPU graph, disk pie, full docs.

Package: `releases/boss-sentinel_2.2.5-1_amd64.deb`

After install, docs are also at `/usr/share/doc/boss-sentinel/`.
