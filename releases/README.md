Built Debian packages land here.

Keep only the current unified package:
- `boss-sentinel_<ver>-1_amd64.deb`
- `boss-sentinel_latest_amd64.deb` (copy of current)

Older `boss-sentinel_*.deb` and any `boss-optimize_*.deb` files are removed
from this folder; use `scripts/install-unified.sh` on BOSS to purge old packages
and leftover `.deb` files on the machine as well.
