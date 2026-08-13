# BOSS-Sentinel — Documentation Index

**Start here.** This is your map to every document and the source tree.

## Word / Google Docs (recommended for reading)

| File | What it gives you |
|------|-------------------|
| [BOSS-Sentinel-Source-Code-and-Explanation.docx](BOSS-Sentinel-Source-Code-and-Explanation.docx) | ALL source code + explanations (Word / Google Docs) |
| [BOSS-Sentinel-Complete-Guide.docx](BOSS-Sentinel-Complete-Guide.docx) | Shorter technical guide (no full code dump) |


### Upload to Google Docs
1. Download the `.docx`
2. Go to [Google Drive](https://drive.google.com) → **New** → **File upload**
3. Right-click the file → **Open with** → **Google Docs**

## Markdown docs

| Document | What it gives you |
|----------|-------------------|
| [USER_GUIDE.md](USER_GUIDE.md) | Install, use, purge, troubleshoot |
| [FILE_STRUCTURE.md](FILE_STRUCTURE.md) | Full directory tree + install paths |
| [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) | Architecture, flows, privilege model |
| [BUILD.md](BUILD.md) | How to compile & package `.deb` |
| [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md) | Step-by-step explanation of every module |
| [../README.md](../README.md) | Short project landing page |

## Source of truth (runtime)

1. **Default product UI:** `scripts/boss-sentinel-gtk3.py` + `scripts/gauges_gtk3.py`
2. **Privileged engine:** `scripts/boss-sentinel-helper`
3. **Launcher:** `scripts/boss-sentinel`
4. **Optional C++ port:** `src/`

## Package

```text
releases/boss-sentinel_2.2.2-1_amd64.deb
```

Branch: `cursor/boss-sentinel-cpp-unified-02f6`
