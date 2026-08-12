# BOSS-Optimize releases

Current package: **boss-optimize 1.0.2**

## Install

```bash
cd ~/Downloads
curl -L -o boss-optimize_1.0.2-1_all.deb \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-optimize-performance-02f6/releases/boss-optimize_1.0.2-1_all.deb
sudo apt-get install -y ./boss-optimize_1.0.2-1_all.deb
boss-optimize
```

## Tabs

- Overview — live CPU/RAM/I/O/GPU chips + top apps
- Services — systemd services (running first)
- Processes — CPU, RAM, I/O, GPU, background/foreground
- Packages — installed packages mapped to running/background status
- Storage I/O — HDD/SSD/NVMe usage + top I/O processes
- Optimize — Yes/No hardware allotment (CPU governor, renice, ionice, caches, power profile)
