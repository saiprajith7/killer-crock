# BOSS-Optimize

Native Debian **GTK4 / libadwaita** app that shows:

- Running **services**
- **Processes** with CPU, RAM, disk I/O, GPU
- **Packages** and whether they are running / background
- **Storage** HDD/SSD/NVMe usage + throughput
- **Optimize** tab — Yes/No to allot hardware (CPU governor, renice, ionice, caches, power profile)

## Run from source

```bash
PYTHONPATH=src python3 -m bossoptimize --once
PYTHONPATH=src python3 -m bossoptimize
```

## Install .deb

```bash
sudo dpkg -i releases/boss-optimize_1.0.2-1_all.deb
sudo apt-get install -f -y
boss-optimize
```

Launch: `boss-optimize`
