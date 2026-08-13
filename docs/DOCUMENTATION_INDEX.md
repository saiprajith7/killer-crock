# BOSS-Sentinel — Documentation Index

**Start here.** This is your map to every document and the source tree.

| Document | What it gives you |
|----------|-------------------|
| [USER_GUIDE.md](USER_GUIDE.md) | Install, use, purge, troubleshoot |
| [FILE_STRUCTURE.md](FILE_STRUCTURE.md) | Full directory tree + install paths |
| [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) | Architecture, flows, privilege model |
| [BUILD.md](BUILD.md) | Compile C++ binary & build `.deb` on Debian 12 |
| [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md) | **Step-by-step explanation of every module / line of logic** |
| [../README.md](../README.md) | Short project landing page |

## Source of truth (runtime)

1. **Default product UI:** `scripts/boss-sentinel-gtk3.py` + `scripts/gauges_gtk3.py`  
2. **Privileged engine:** `scripts/boss-sentinel-helper`  
3. **Launcher:** `scripts/boss-sentinel`  
4. **Optional C++ port:** `src/`  

## How to study the code

1. Read [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) (10 minutes).  
2. Skim [FILE_STRUCTURE.md](FILE_STRUCTURE.md).  
3. Open [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md) and follow sections **in order** (launcher → helper → gauges → main UI → C++ mirror).  
4. Keep the matching source file open beside the walkthrough.

## Package

```text
releases/boss-sentinel_2.2.2-1_amd64.deb
```

Branch: `cursor/boss-sentinel-cpp-unified-02f6`
