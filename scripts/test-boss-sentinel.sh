#!/usr/bin/env bash
# BOSS-Sentinel application test suite
# Usage:
#   bash scripts/test-boss-sentinel.sh
#   bash scripts/test-boss-sentinel.sh --quick
#   bash scripts/test-boss-sentinel.sh --installed   # also probe system install
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

QUICK=0
INSTALLED=0
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    --installed) INSTALLED=1 ;;
    -h|--help)
      echo "Usage: $0 [--quick] [--installed]"
      exit 0
      ;;
  esac
done

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export BOSS_SENTINEL_CPU_SAMPLE="${BOSS_SENTINEL_CPU_SAMPLE:-0.05}"
export BOSS_SENTINEL_CPU_EMA="${BOSS_SENTINEL_CPU_EMA:-0.85}"

PASS=0
FAIL=0
SKIP=0

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
cyan()  { printf '\033[36m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

ok()   { green "  PASS  $*"; PASS=$((PASS + 1)); }
bad()  { red   "  FAIL  $*"; FAIL=$((FAIL + 1)); }
skip() { printf '  SKIP  %s\n' "$*"; SKIP=$((SKIP + 1)); }

section() {
  echo
  bold "==> $*"
}

run_check() {
  local name="$1"
  shift
  if "$@"; then
    ok "$name"
  else
    bad "$name"
  fi
}

# ---------------------------------------------------------------------------
section "1. Environment"
# ---------------------------------------------------------------------------
run_check "python3 available" bash -c 'command -v python3 >/dev/null'
run_check "project src/ exists" test -d "$ROOT/src/vitaheal"
run_check "helper script exists" test -f "$ROOT/scripts/vitaheal-helper"
python3 - <<'PY' && ok "import vitaheal package" || bad "import vitaheal package"
import vitaheal
print(f"    version={vitaheal.__version__} name={vitaheal.APP_NAME}")
PY

# ---------------------------------------------------------------------------
section "2. Syntax / compile"
# ---------------------------------------------------------------------------
if python3 -m compileall -q "$ROOT/src" "$ROOT/scripts" "$ROOT/tests"; then
  ok "compileall src scripts tests"
else
  bad "compileall src scripts tests"
fi

# ---------------------------------------------------------------------------
section "3. Unit tests (unittest)"
# ---------------------------------------------------------------------------
if python3 -m unittest discover -s tests -v; then
  ok "unittest discover"
else
  bad "unittest discover"
fi

# ---------------------------------------------------------------------------
section "4. CLI smoke: --once snapshot"
# ---------------------------------------------------------------------------
ONCE_JSON="$(mktemp)"
cleanup() { rm -f "$ONCE_JSON"; }
trap cleanup EXIT

if python3 -m vitaheal --once >"$ONCE_JSON" 2>/tmp/boss-once.err; then
  ok "boss-sentinel --once exits 0"
else
  bad "boss-sentinel --once exits 0"
  cat /tmp/boss-once.err || true
fi

python3 - <<PY && ok "snapshot JSON is valid with CPU/memory" || bad "snapshot JSON is valid with CPU/memory"
import json
from pathlib import Path
raw = Path("$ONCE_JSON").read_text()
data = json.loads(raw)
assert "metrics" in data and "score" in data and "overall" in data
kinds = {m["kind"] for m in data["metrics"]}
assert "cpu" in kinds, kinds
assert "memory" in kinds, kinds
assert 0 <= data["score"] <= 100
print(f"    score={data['score']} overall={data['overall']} metrics={len(data['metrics'])}")
PY

# ---------------------------------------------------------------------------
section "5. CPU monitor (per-CPU + GNOME accounting)"
# ---------------------------------------------------------------------------
python3 - <<'PY' && ok "per-CPU samples + accounting" || bad "per-CPU samples + accounting"
from vitaheal.monitor.cpu import CpuCollector, _idle_total

# GNOME-style: iowait is busy
vals = [100, 10, 50, 800, 40, 5, 5, 0, 20, 2]
idle, total = _idle_total(vals)
assert idle == 800, idle
assert total == 1010, total

c = CpuCollector()
readings = c.read()
cpu = next(m for m in readings if m.label == "CPU")
assert 0.0 <= cpu.value <= 100.0, cpu.value
topo = c.topology
assert topo.logical_threads >= 1
assert len(topo.per_core) == topo.logical_threads or len(topo.per_core) >= 1
assert all(0.0 <= p <= 100.0 for p in topo.per_core)
print(
    f"    overall={cpu.value}%  cores={topo.physical_cores}  "
    f"threads={topo.logical_threads}  per_cpu={topo.per_core}"
)
PY

python3 - <<'PY' && ok "simulate cpu critical issue" || bad "simulate cpu critical issue"
from vitaheal.monitor.engine import HealthEngine
from vitaheal.monitor.models import MetricKind, Severity
snap = HealthEngine(simulate="cpu").snapshot()
cpu = next(m for m in snap.metrics if m.kind == MetricKind.CPU)
assert cpu.severity == Severity.CRITICAL
issue = next(i for i in snap.issues if i.kind == MetricKind.CPU)
assert issue.heal_action == "renice_hogs"
print(f"    issue={issue.title!r} heal={issue.heal_action}")
PY

# ---------------------------------------------------------------------------
section "6. Memory / disk / heal smoke"
# ---------------------------------------------------------------------------
python3 - <<'PY' && ok "memory thresholds (warn 85 / crit 95)" || bad "memory thresholds"
from vitaheal.monitor.memory import MemoryCollector
from vitaheal.monitor.models import MetricKind
ms = MemoryCollector().read()
mem = next(m for m in ms if m.kind == MetricKind.MEMORY)
assert mem.threshold_warn == 85
assert mem.threshold_crit == 95
print(f"    RAM={mem.value}% {mem.detail}")
PY

python3 - <<'PY' && ok "hardware inventory + replace threshold" || bad "hardware inventory + replace threshold"
from vitaheal.monitor.engine import HealthEngine
from vitaheal.monitor.hardware import REPLACE_THRESHOLD, HardwareCollector
assert REPLACE_THRESHOLD == 45.0
snap = HealthEngine().snapshot()
comps = HardwareCollector().inventory(snap)
assert any(c.category == "cpu" for c in comps)
assert any(c.category == "memory" for c in comps)
for c in comps:
    if c.health < REPLACE_THRESHOLD:
        assert c.replace and "Replace" in c.advice
summary = HardwareCollector.summary(comps)
print(f"    components={summary['count']} avg={summary['avg_health']}% replace={summary['replace_count']}")
PY

python3 - <<'PY' && ok "local heal simulate_ok" || bad "local heal simulate_ok"
from vitaheal.heal.actions import perform_heal
r = perform_heal("simulate_ok")
assert r.ok, r.message
print(f"    {r.message}")
PY

# ---------------------------------------------------------------------------
section "7. Packaging / install assets"
# ---------------------------------------------------------------------------
run_check "debian/control exists" test -f debian/control
run_check "desktop file exists" test -f data/desktop/vitaheal.desktop
run_check "polkit policy exists" test -f data/polkit/org.vitaheal.policy
run_check "install script exists" test -f scripts/install-boss-sentinel.sh
run_check "quiet launcher exists" test -f scripts/boss-sentinel

if [[ "$QUICK" -eq 0 ]]; then
  if command -v dpkg-deb >/dev/null 2>&1; then
    DEB="$(ls -1 dist/boss-sentinel_*.deb 2>/dev/null | sort -V | tail -1 || true)"
    if [[ -z "$DEB" ]]; then
      DEB="$(ls -1 releases/boss-sentinel_*.deb 2>/dev/null | sort -V | tail -1 || true)"
    fi
    if [[ -n "$DEB" ]]; then
      run_check "deb package readable ($DEB)" dpkg-deb -I "$DEB" >/dev/null
      python3 - <<PY && ok "deb contains PerCpuMonitor / MultiCpuGraph" || bad "deb contains PerCpuMonitor / MultiCpuGraph"
import subprocess, tempfile, pathlib
deb = "$DEB"
with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(["dpkg-deb", "-x", deb, td])
    gauges = next(pathlib.Path(td).rglob("gauges.py"))
    text = gauges.read_text()
    assert "class PerCpuMonitor" in text
    assert "class MultiCpuGraph" in text
    print(f"    checked {gauges}")
PY
    else
      skip "no .deb in dist/ or releases/ (run make deb first)"
    fi
  else
    skip "dpkg-deb not installed"
  fi
else
  skip "packaging checks (--quick)"
fi

# ---------------------------------------------------------------------------
section "8. Optional: installed system package"
# ---------------------------------------------------------------------------
if [[ "$INSTALLED" -eq 1 ]]; then
  if command -v boss-sentinel >/dev/null 2>&1; then
    ok "boss-sentinel on PATH"
    if boss-sentinel --once >/tmp/boss-installed-once.json 2>/tmp/boss-installed-once.err; then
      ok "installed boss-sentinel --once"
    else
      bad "installed boss-sentinel --once"
      cat /tmp/boss-installed-once.err || true
    fi
  else
    bad "boss-sentinel on PATH (package not installed?)"
  fi
  if [[ -x /usr/libexec/boss-sentinel/boss-sentinel-helper ]]; then
    ok "privileged helper installed"
  else
    bad "privileged helper installed"
  fi
else
  skip "system install probes (pass --installed to enable)"
fi

# ---------------------------------------------------------------------------
echo
bold "=============================="
bold " BOSS-Sentinel test summary"
bold "=============================="
echo "  passed : $PASS"
echo "  failed : $FAIL"
echo "  skipped: $SKIP"
echo

if [[ "$FAIL" -gt 0 ]]; then
  red "RESULT: FAILED"
  exit 1
fi
green "RESULT: OK"
exit 0
