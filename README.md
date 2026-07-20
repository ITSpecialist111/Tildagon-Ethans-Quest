# Ethan's Quest for Tildagon

Ethan's Quest is a single-player reflex RPG for the EMF Camp Tildagon badge.
Watch each A-E combat sequence, then repeat it before the response bar expires.
Completed sequences damage the enemy; mistakes and timeouts damage Ethan.

- **Author:** Graham Hosking
- **License:** MIT
- **Tildagon OS:** 2.0.0 or newer

## Features

- Animated shield-bearing hero and five enemy types
- Increasingly long and fast combat sequences
- Player and enemy health, XP, score, healing, and critical hits
- Button-adjacent LED cues for every A-E input
- Gold strike, green/gold victory, and red damage and game-over effects
- Optional Space Unicorn colour mirroring with state restoration on exit

Level 1 allows 1.5 seconds per cue and 3 seconds per response. The timing
gradually tightens as the level rises.

## Controls

| Button | Action |
| --- | --- |
| A | Up sequence cue |
| B | Right sequence cue |
| C | Confirm sequence cue, start, or restart |
| D | Down sequence cue |
| E | Left sequence cue |
| F | Exit |

## Install

Ethan's Quest is listed at
[apps.badge.emfcamp.org/apps/41134142](https://apps.badge.emfcamp.org/apps/41134142/)
with install code **`41134142`**.

1. Connect the badge to Wi-Fi.
2. Open **App Store > CodeInstall** (called **Use Code** on some firmware).
3. Enter `41134142` and install **Ethan's Quest**.

The App Store discovers this repository through the `tildagon-app` topic. New
releases normally appear within 15 minutes.

For a direct USB development install, copy `app.py`, `quest.py`, `lights.py`,
and development launcher metadata into an isolated `/apps/ethans_quest`
directory. Do not flash or erase the badge.

## Development

```sh
python -m pip install pytest
python -m pytest -q
python -m py_compile app.py quest.py lights.py
```

The release archive contains only the three badge runtime modules,
`tildagon.toml`, and `LICENSE`. Documentation, tests, CI, and repository
configuration are excluded with `.gitattributes`.