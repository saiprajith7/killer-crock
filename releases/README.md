# BOSS-Sentinel releases

Current package: **boss-sentinel 1.2.12** (single-file install)

## One command install

```bash
cd ~/Downloads
curl -L -o boss-sentinel_1.2.12-1_all.deb \
  https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/fix-invalid-class-name-02f6/releases/boss-sentinel_1.2.12-1_all.deb
sudo dpkg -i boss-sentinel_1.2.12-1_all.deb
boss-sentinel
```

This `.deb` **bundles** `fonts-hack` and `libnotify-bin`. On install, postinst
prints each as installed / not installed and installs missing ones from inside
the package — no separate apt dependency step for those.

Core desktop stack still required (normally already on Ubuntu Desktop / ISO):
`python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `pkexec`/`polkitd`.
