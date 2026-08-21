# Local packages

Built packages for BOSS Health / BOSS-Sentinel.

## BOSS Health 1.3.1 (recommended)

```bash
sudo dpkg -i ./releases/boss-sentinel_1.3.1-1_all.deb
sudo apt -f install
boss-health
```

### Cinnamon panel icon

The **lock** on BOSS Health in Applets is normal (system applet — cannot uninstall from that dialog).

1. Select **BOSS Health**
2. Click the **+** button at the bottom to add it to the panel
3. Click the new panel icon to open the dashboard

If the icon still does not appear, restart Cinnamon: `Alt+F2` → type `r` → Enter

Also includes the existing full monitor:

```bash
boss-sentinel
```

Rebuild locally:

```bash
make deb-local
```
