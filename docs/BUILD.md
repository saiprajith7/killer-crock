# Building BOSS-Sentinel

## Target platform

BOSS Linux ≈ **Debian 12 (bookworm)** with **glibc 2.36**.

Build the release `.deb` **inside Debian 12**. Ubuntu 24.04 builds need `GLIBC_2.38+` and will not run on BOSS.

### Bookworm chroot (recommended)

```bash
sudo debootstrap bookworm /opt/bookworm-root http://deb.debian.org/debian
sudo mount --bind "$PWD" /opt/bookworm-root/workspace
sudo chroot /opt/bookworm-root bash -lc '
  apt-get update
  apt-get install -y build-essential cmake pkg-config g++ \
    libgtkmm-4.0-dev libglibmm-2.68-dev libgtk-4-dev \
    python3 python3-gi python3-cairo gir1.2-gtk-3.0 libgtk-3-0 fakeroot
  cd /workspace && ./packaging/build-deb.sh
'
```

## Runtime dependencies (BOSS install)

```bash
sudo apt-get install -y python3 python3-gi python3-cairo gir1.2-gtk-3.0 libgtk-3-0
```

gtkmm-4 packages are **optional** (only for `BOSS_SENTINEL_UI=cpp`).

## Configure and compile (optional C++ binary)

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build build -j"$(nproc)"
```

Binary: `build/boss-sentinel-bin`

## Package `.deb`

```bash
./packaging/build-deb.sh
# → releases/boss-sentinel_<version>-1_amd64.deb
```

The script:

1. Builds the C++ binary  
2. Rejects glibc > 2.36 symbols  
3. Stages GTK3 UI + helper + docs + desktop/polkit  
4. Runs `dpkg-deb --build`

## Local run without installing

```bash
chmod +x scripts/boss-sentinel scripts/boss-sentinel-helper scripts/boss-sentinel-gtk3.py
./scripts/boss-sentinel
```

## Docs in the package

Installed under `/usr/share/doc/boss-sentinel/`:

- `DOCUMENTATION_INDEX.md`
- `FILE_STRUCTURE.md`
- `SYSTEM_DESIGN.md`
- `CODE_WALKTHROUGH.md`
- `USER_GUIDE.md`
- `BUILD.md`
- `README.md`

## Version

Set in `CMakeLists.txt` (`project(boss-sentinel VERSION …)`). `packaging/build-deb.sh` reads it.
