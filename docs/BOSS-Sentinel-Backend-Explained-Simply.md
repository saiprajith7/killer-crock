# BOSS-Sentinel — How It Works Behind the Scenes

**A simple guide for everyone**  
Version covered: **1.2.8**  
Audience: Non-technical readers, managers, and new team members

---

## What this document is about

BOSS-Sentinel is a PC health monitor for Debian/Ubuntu.  
This guide explains **what happens inside the computer** when you open the app — in plain language.

You do **not** need to be a programmer to understand this.

Think of your PC like a **human body**.  
BOSS-Sentinel is like a **nurse with a checklist**: it checks pulse, temperature, and energy, then asks before giving medicine.

---

## The big picture (one minute)

When you run `boss-sentinel`, three kinds of work can happen:

1. **Watch** — Read how healthy the PC is (CPU, memory, disk, heat, and more).
2. **Show** — Draw those numbers on the screen every few seconds.
3. **Heal** — Only if you say Yes, try a safe fix (sometimes needing your password).

Most of the time, the app is only **watching and showing**.  
It does **not** silently change your system unless you approve a heal.

---

## Simple analogy: hospital for your computer

| Real life | BOSS-Sentinel |
|-----------|----------------|
| Patient | Your PC |
| Nurse with clipboard | The **monitor** (collects readings) |
| Doctor reviewing charts | The **health engine** (decides OK / Warning / Critical) |
| Waiting room screen | The **window** you see |
| Asking “Should we treat?” | The **Yes / No** heal dialog |
| Pharmacy that needs ID | The **helper** + password prompt (`pkexec`) |
| Night-shift pager | The **background daemon** (optional) |

---

## What runs on your computer (roles)

### 1) The main app (what you usually open)

- Command: `boss-sentinel`
- What it is: A normal desktop window app (like System Monitor)
- Who it runs as: **You** (your user account), not the administrator all the time
- Job: Show health, refresh the screen, ask Yes/No before healing

### 2) The background watcher (optional)

- Service name: `boss-sentinel-daemon`
- What it is: A small program that can keep checking even when the window is closed
- Who it runs as: Still **you** (a “user service,” not a full system root service)
- Job: If something looks critical, send a desktop notification and open the main app so **you** can decide

### 3) The privileged helper (only when healing needs admin power)

- Path: `/usr/libexec/boss-sentinel/boss-sentinel-helper`
- What it is: A small tool that can do admin-only cleanup (like clearing system caches)
- Who it runs as: **Administrator (root), but only for that one action**, after you approve
- Job: Do the requested heal, then exit and report success or failure

**Important:** The helper is not always running in the background as root.  
It starts only when needed, asks for permission, does one job, and finishes.

---

## How a health check works (step by step)

Every few seconds, the main window asks the **Health Engine** for a fresh report.

### Step A — Collect readings (“take vitals”)

The engine asks several small specialists. Each one looks at a specific part of Linux:

| Specialist | What it checks | Where it looks (simple meaning) |
|------------|----------------|----------------------------------|
| CPU | How busy the processor is | System “heartbeat” counters |
| Memory | How full RAM is | Memory status file |
| Swap | Overflow memory usage | Same memory status |
| Disk | How full storage is | Mounted folders like `/` and `/home` |
| Inodes | File-slot pressure | Same disk checks (many tiny files can fill slots) |
| Temperature | Hottest sensor | Hardware sensor folders |
| GPU | Graphics load (if present) | NVIDIA tools or graphics system folders |
| Network | Data speed (info) | Network traffic counters |
| Processes | “Zombie” stuck processes | Process list |
| Hardware tab | Component health including USB | Device identity + earlier metrics |
| Updates tab | Available package upgrades | Apt sources + simulated upgrade list |

**Plain English:** Linux already keeps notebooks about the machine’s health.  
BOSS-Sentinel reads those notebooks. It does not invent numbers from nowhere.

### Step B — Grade each reading

Each reading gets a traffic-light style grade:

- **OK** — Fine
- **Warning** — Getting high; keep an eye on it
- **Critical** — Too high; healing may be offered

Examples of warning / critical levels (percentages unless noted):

| Check | Warning | Critical |
|-------|---------|----------|
| CPU | 80% | 95% |
| Memory (RAM) | 85% | 95% |
| Disk / Inodes | 85% | 95% |
| Temperature | 80°C | 95°C |
| GPU | 85% | 95% |
| Swap | 50% | 80% |
| Zombie processes | 5 | 20 |

### Step C — Build a score (0 to 100)

Start at **100**, then subtract:

- **−8** for each Warning reading  
- **−20** for each Critical reading  

The score cannot go below 0.

So: more problems → lower score. Easy.

### Step D — Create “issues” with suggested fixes

If a reading is Warning or Critical, the engine may create an **Issue**, like:

- “CPU overload” → suggested fix: throttle heavy apps  
- “Memory high” → suggested fix: drop caches  
- “Disk full” → suggested fix: purge temp/cache  
- “Too hot” → suggested fix: powersave cooling  

Network speed is tracked for display, but it does **not** create heal issues.

---

## How the screen stays up to date

1. App opens.
2. Immediately takes one health snapshot.
3. Then repeats about every **3 seconds**.
4. Each snapshot updates the graphs, labels, Hardware tab, and Logs.

That is why numbers move while the window is open.

**CPU note (simple):** Measuring CPU honestly needs two samples a short time apart (about 1 second). So each refresh includes that short wait — like checking pulse for a full second, not guessing.

---

## Autoheal: how Yes / No really works

### The Autoheal switch

- Location: Top of the window (and Overview)
- Default: **OFF**
- Saved in: `~/.config/boss-sentinel/settings.json`

When Autoheal is **OFF**:

- Monitoring still works.
- The app does **not** pop up heal prompts by itself.
- You can still press **HEAL** manually on an issue.

When Autoheal is **ON**:

- If a **Critical** issue appears, the app asks: **Yes — Heal Now** or **No**.

### The heal conversation (always human-approved)

```
Problem detected
        ↓
App asks: “Heal this?”
        ↓
   You choose
   /        \
 NO          YES
  ↓           ↓
Do nothing   Ask for admin permission if needed
             ↓
           Helper runs one fix
             ↓
           Show result (toast + log)
```

If you say **No**, the app remembers for about a minute so it does not nag you immediately.

### Why a password / admin prompt sometimes appears

Some fixes need more power than a normal user has (example: clearing system page caches).

Linux has a permission gate called **Polkit**.  
BOSS-Sentinel uses it like this:

1. App calls: “Please run the helper to do action X.”
2. System asks you to confirm (password / fingerprint, depending on your setup).
3. Helper runs **as admin for that action only**.
4. Helper prints a short success/failure message.
5. App shows you the result.

If you cancel the password prompt, nothing privileged happens.

---

## What each heal action means (plain English)

| Action name (inside the app) | What it tries to do |
|------------------------------|---------------------|
| Throttle CPU hogs | Make the busiest heavy programs nicer / lower priority |
| Drop page caches | Free memory that Linux is using as temporary file cache |
| Reset swap | Turn swap off and on again to clear stuck swap pressure |
| Purge caches & temp | Clean package caches, shrink logs a bit, remove scratch temp files |
| Prune temp inodes | Remove known scratch folders/files that waste file slots |
| Force powersave cooling | Ask CPUs to use a cooler, lower-power mode |
| Force GPU powersave | Ask the GPU to run cooler / lower performance mode |
| Reap zombie parents | Nudge parent processes that left stuck “zombie” children |
| Pause user timers | Pause some background maintenance timers (like apt daily) |
| Apt update / upgrade | Refresh package lists or install upgrades (Updates tab) |

These are **maintenance-style** actions.  
They are not magic “repair any broken PC” tools. They try common safe cleanups after you approve.

---

## Hardware tab (how that part works)

The Hardware tab builds a simple “component health report”:

- CPU, memory, storage, network adapters, USB devices, and related info
- Each component gets a health percentage
- If health is **below 45%**, the app advises: **Replace this hardware**

This is guidance based on status signals — not a lab certification.

---

## Updates tab (how that part works)

Separately from the 3-second vitals loop:

1. App reads software update sources.
2. It can ask apt what upgrades would happen (preview).
3. If you choose to update/upgrade, you get a Yes/No confirm.
4. If needed, the privileged helper runs the apt command after admin approval.

So updates are **manual and confirmed**, not silent.

---

## Background daemon (night-shift pager)

If enabled, the daemon:

- Checks health on a timer (about every **20 seconds** in the packaged service)
- If it sees a **Critical** issue, it can:
  - Send a desktop notification
  - Open the main BOSS-Sentinel window (so you can approve a heal)

The daemon itself does **not** auto-heal without you.  
It pages you. You decide.

It remembers which issues it already notified about (a small list in your cache folder), so it does not spam forever.

---

## Where your settings and notes are saved

| What | Where | Notes |
|------|-------|-------|
| Autoheal ON/OFF | `~/.config/boss-sentinel/settings.json` | Small text file in your home folder |
| Daemon “already notified” list | `~/.cache/vitaheal/notified.ids` | Avoids repeat spam |
| Event log in the app | In memory / on screen | Session activity you can read in Logs |

There is **no big hidden database**.  
The app is mostly live readings + a tiny preference file.

---

## What gets installed on the system (map)

When you install the `.deb` package, key pieces land here:

| Piece | Typical location | Purpose |
|-------|------------------|---------|
| Launcher | `/usr/bin/boss-sentinel` | Starts the app quietly |
| Python program | `/usr/lib/python3/dist-packages/vitaheal/` | The actual brain and UI code |
| Helper | `/usr/libexec/boss-sentinel/boss-sentinel-helper` | Privileged heal tool |
| Menu icon | `/usr/share/applications/…` | Shows in your app menu |
| Permission rules | `/usr/share/polkit-1/actions/…` | Defines when the helper may run |
| User service | `/usr/lib/systemd/user/boss-sentinel-daemon.service` | Optional background watcher |

You launch a **user app**.  
Only the helper briefly becomes admin when you approve a heal.

---

## Different ways to run it

| Mode | How | What happens |
|------|-----|--------------|
| Normal window | `boss-sentinel` | Full UI, refreshes every ~3 seconds |
| One snapshot | `boss-sentinel --once` | Prints one health report as text/JSON, then exits |
| Background | `boss-sentinel-daemon` | Watches quietly, notifies on critical issues |
| Demo / test | `--simulate-issue memory` (example) | Pretends a critical problem so you can practice Yes/No |

---

## Security & privacy in plain words

**What it can see**

- Normal system health information that Linux already exposes to your user
- Hardware names and USB device names for the Hardware tab
- Package update information when you use the Updates tab

**What it does not do**

- It does not upload your data to a cloud in this design
- It does not stay permanently logged in as root
- It does not heal without a Yes (Autoheal OFF = no auto prompts; even ON still asks)

**Password prompts mean**

- “This next step needs administrator power.”
- Cancel = no change from the helper.

---

## A full walk-through example

**Scene:** Your RAM is almost full.

1. Every 3 seconds, Memory specialist reads memory status.
2. Value crosses the Critical line (95%).
3. Health Engine lowers the score and creates a Memory issue.
4. Screen turns more urgent; Overview shows the issue.
5. If Autoheal is ON, a dialog appears: heal now?
6. You click **Yes**.
7. App asks the system to run the helper action `drop_caches`.
8. You approve the admin prompt.
9. Helper clears reclaimable caches and reports success.
10. Next refresh shows improved memory (if caches were the main pressure).
11. Logs record what happened.

If you clicked **No**, nothing privileged runs. Monitoring continues.

---

## How to explain it to someone else in 20 seconds

> “BOSS-Sentinel is a local health dashboard for your Linux PC.  
> It reads system vitals, scores them, and only tries fixes after you say Yes.  
> Everyday work runs as your user. Admin power is borrowed briefly through a password prompt for specific cleanups.”

---

## Glossary (tiny dictionary)

| Word | Meaning |
|------|---------|
| Backend | The hidden work: collecting data, scoring, healing |
| Snapshot | One full set of health readings at a moment in time |
| Issue | A named problem with a suggested fix |
| Autoheal | Feature that offers Yes/No heal prompts for critical issues |
| Daemon | Background program without the main window |
| Polkit / pkexec | Linux permission gate for admin actions |
| Helper | Small privileged program that performs one approved fix |
| `.deb` | Debian/Ubuntu install package |

---

## Summary

BOSS-Sentinel’s backend is a **loop of reading → grading → showing → (optional) asking → (optional) fixing**.

- **Reading** uses Linux’s own status files and sensors.  
- **Grading** uses clear warning/critical thresholds and a 0–100 score.  
- **Showing** happens in a desktop window every few seconds.  
- **Fixing** is interactive, preferenced by Autoheal ON/OFF, and admin-gated when needed.

That is the whole heart of the system — kept simple on purpose.

---

*Document for Google Docs / sharing · BOSS-Sentinel backend explained simply · v1.2.8*
