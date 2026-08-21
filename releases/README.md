# Local packages

## BOSS Health 1.3.3 (recommended — click fix)

```bash
cd ~/Downloads
wget -O boss-sentinel_1.3.3-1_all.deb \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-health-readiness-02f6/releases/boss-sentinel_1.3.3-1_all.deb
sudo dpkg -i boss-sentinel_1.3.3-1_all.deb
sudo apt -f install
```

Then restart Cinnamon so the panel applet reloads:
- Press **Alt+F2**, type **r**, press Enter

Or test directly:

```bash
boss-health
```

If it fails, check:

```bash
cat ~/.cache/boss-health/launch.log
```
