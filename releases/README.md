# Local packages

This folder may hold built `.deb` files for convenience.

Install from the distribution zip (quiet — no apt `_apt` home-dir notice):

```bash
cd install
bash install.sh
boss-sentinel
```

If you must clear a half-installed older package first:

```bash
sudo dpkg --remove --force-remove-reinstreq boss-sentinel
```
