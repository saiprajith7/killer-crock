# Local packages

## BOSS Health 1.3.2 (recommended)

After `dpkg -i`, a **BOSS Health icon appears in the menu bar** automatically.
Click it → System Readiness dashboard opens.

```bash
cd ~/Downloads
sudo dpkg -i boss-sentinel_1.3.2-1_all.deb
sudo apt -f install
```

If the icon is not visible yet:

```bash
boss-health-tray &
# or log out / log in once
```

Manual dashboard:

```bash
boss-health
```

Download:
https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-health-readiness-02f6/releases/boss-sentinel_1.3.2-1_all.deb
