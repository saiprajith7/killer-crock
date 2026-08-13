# Building BOSS-Sentinel

## Target platform

BOSS Linux is based on **Debian 12 (bookworm)** with **glibc 2.36**.

Build the release `.deb` **inside a Debian 12 environment** (chroot or container).
Building on Ubuntu 24.04 produces binaries that require `GLIBC_2.38+` and will not run on BOSS.

### Bookworm chroot (recommended)

```bash
sudo debootstrap bookworm /opt/bookworm-root http://deb.debian.org/debian
sudo mount --bind "$PWD" /opt/bookworm-root/workspace
sudo chroot /opt/bookworm-root bash -lc '
  apt-get update
  apt-get install -y build-essential cmake pkg-config g++ \
    libgtkmm-4.0-dev libglibmm-2.68-dev libgtk-4-dev python3 fakeroot
  cd /workspace && ./packaging/build-deb.sh
'
```

## Dependencies (Ubuntu / Debian build host)


```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential cmake pkg-config g++ \
  libgtkmm-4.0-dev libglibmm-2.68-dev libgtk-4-dev \
  python3 policykit-1 fakeroot dpkg-dev
```

## Configure and compile

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build build -j"$(nproc)"
```

Binary: `build/boss-sentinel-bin`  
CSS is copied next to the binary under `build/share/boss-sentinel/style.css`.

Run locally:

```bash
chmod +x scripts/boss-sentinel scripts/boss-sentinel-helper
./scripts/boss-sentinel
# or
./build/boss-sentinel-bin
```

The healer/optimizer look for the helper at:

1. `/usr/libexec/boss-sentinel/boss-sentinel-helper`
2. `scripts/boss-sentinel-helper` (dev tree)

## Produce the `.deb`

```bash
./packaging/build-deb.sh
```

Output:

- `releases/boss-sentinel_2.0.0-1_<arch>.deb`
- copy in `dist/`

Install:

```bash
sudo apt-get install -y ./releases/boss-sentinel_2.0.0-1_amd64.deb
```

## Alternative: debhelper

```bash
dpkg-buildpackage -us -uc -b
```

Uses `debian/rules` with the CMake buildsystem.

## Runtime data

| Path | Purpose |
|------|---------|
| `~/.config/boss-sentinel/settings.json` | Auto-heal prompt toggle, poll interval |
| `~/.local/share/boss-sentinel/boss-sentinel.log` | Full event log |

## Version

Set in `CMakeLists.txt` (`project(boss-sentinel VERSION 2.0.0 …)`). The packaging script reads that version for the `.deb` name.
