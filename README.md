# TermGPS 🧭

A terminal-based GPS navigation app with **turn-by-turn directions** and radar display.

![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)

## Features

- 📍 **Real GPS Location** - Uses macOS Location Services
- 🗺️ **Turn-by-Turn Navigation** - Actual road paths like Google Maps
- 🧭 **Radar Display** - Visual compass with route overlay
- 📏 **Distance & ETA** - Real-time route information
- 🔄 **Step-by-Step Directions** - Navigate through each turn
- 🔔 **Arrival Detection** - Notifies when you reach destination

## Screenshot

```
                        N
                        │
              ·  ·   ·  │  ·   ·  ·
             ·    ·····│·····    ·
            ·  ·····   │   ·····  ·
    W───────────●──────╋◉YOU────────────E
            ·         ·│·         ·
             ·    ◆···•│         ·
              ·  Dest  │  ·   ·  ·
                        │
                        S

┌─ DIRECTIONS ──────────────────────────────────────────┐
│ ➡️ Mathura Road                                  2.1km │
│   ⬆️ NH 44                                       45.2km │
│   ⬅️ Fatehabad Road                              3.5km │
│ Step 1/12                  [n]ext [p]revious          │
└───────────────────────────────────────────────────────┘

┌─ NAVIGATION ──────────────────────────────────────────┐
│ 📍 GPS: Excellent (±5m)                               │
│ YOUR LOCATION: 28.61390, 77.20900                     │
│ DESTINATION: Taj Mahal                                │
│ DISTANCE: 233.5 km  |  ETA: 3h 45m                    │
└───────────────────────────────────────────────────────┘
```

## Installation

```bash
# Clone
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps

# Setup
python -m venv venv
source venv/bin/activate
pip install -e .

# For real GPS (macOS)
pip install pyobjc-framework-CoreLocation
```

## Usage

```bash
python -m termgps.app
```

### Controls

| Key | Action |
|-----|--------|
| `r` | **Get GPS location** |
| `d` | **Search destination** |
| `n` | Next direction step |
| `p` | Previous direction step |
| `c` | Clear route |
| Mouse drag | Pan radar view |
| `q` | Quit |

## How It Works

1. Press `r` to get your GPS location
2. Press `d` and search for a destination
3. Route is calculated automatically using **OSRM** (OpenStreetMap routing)
4. Follow turn-by-turn directions with `n`/`p` keys

## Route API

Uses **OSRM (Open Source Routing Machine)** - free, no API key required.
- Same road data as OpenStreetMap
- Accurate driving directions
- Distance and time estimates

## Requirements

- Python 3.9+
- macOS (for GPS)
- textual, rich, requests, geocoder

## License

MIT
