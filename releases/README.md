# Local packages

Built packages for BOSS Health / BOSS-Sentinel.

## BOSS Health 1.3.0 (recommended)

```bash
sudo dpkg -i ./releases/boss-sentinel_1.3.0-1_all.deb
sudo apt -f install
boss-health
```

Cinnamon: add applet **BOSS Health** to the panel, then click the icon.

Also includes the existing full monitor:

```bash
boss-sentinel
```

Rebuild locally:

```bash
make deb-local
```
