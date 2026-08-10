# BOSS-Sentinel releases

Current package: **boss-sentinel 1.2.11**

## Install on a running PC (recommended)

`dpkg -i` alone **cannot** download dependencies. Use the installer (or apt):

```bash
cd ~/Downloads
curl -L -o boss-sentinel_1.2.11-1_all.deb \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/fix-invalid-class-name-02f6/releases/boss-sentinel_1.2.11-1_all.deb
curl -L -o install.sh \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/fix-invalid-class-name-02f6/scripts/install-boss-sentinel.sh
bash install.sh
boss-sentinel
```

The installer prints each dependency as **installed / not installed**, installs
anything missing with apt, then configures the package.

### Alternative (apt resolves Depends for you)

```bash
sudo apt-get install -y ./boss-sentinel_1.2.11-1_all.deb
```

## ISO seed packages

Include `boss-sentinel_1.2.11-1_all.deb` plus:

- python3-gi python3-gi-cairo python3-cairo
- gir1.2-gtk-4.0 gir1.2-adw-1
- pkexec polkitd
- libnotify-bin
- fonts-hack (or fonts-firacode / fonts-jetbrains-mono)
