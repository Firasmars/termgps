# TermGPS 🧭

**Terminal-based GPS Navigation with Turn-by-Turn Directions**

A cross-platform terminal navigation app with radar display, route visualization, and real-time tracking.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- 📍 **GPS Location** - Real GPS on macOS, IP-based fallback everywhere
- 🗺️ **Turn-by-Turn Navigation** - Step-by-step directions with distance
- 🧭 **Radar Display** - Visual map with route and direction arrow
- 🔵 **Route Visualization** - Blue route line from start to destination
- 🔴 **Direction Arrow** - Points from your location toward destination
- 🔄 **Live Tracking** - Auto-updates GPS every 5 seconds
- 🎨 **4 Themes** - Matrix, Dark, Ocean, Sunset
- 🇮🇳 **India Optimized** - Built-in Indian cities, Tamil Nadu focus

---

## 📸 Screenshot

```
┌─ NEXT TURN ─┐ ┌────────────────────────────────────────────────┐
│             │ │              N                                 │
│   ⬅  500m   │ │              │                                 │
│             │ │     ·    ·   │   ·    ·                        │
│  Main Road  │ │    ·         │     ●●●▶                        │
│  Step 1/5   │ │   W──────────╋ ◉ YOU──━━━━━◆──E                │
├─ UPCOMING ──┤ │    ·         │         ·                       │
│ ⬅ Main Rd  │  │     ·    ·   │   ·    ·                        │
│ ➡ NH 44    │  │              S                                 │
│ ⬆ Continue │  │                                                │
├─ INFO ──────┤ │                MAP                             │
│ GPS: 13.08  │ │                                                │
│ TO: Chennai │ └────────────────────────────────────────────────┘
│ 🔄 TRACKING │
├─ THEME ─────┤
│ [matrix]    │
└─────────────┘
```

---

## 🚀 Installation

### Requirements
- Python 3.9+
- Internet connection (for routing)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps

# Install dependencies
pip install textual rich requests

# Run
python -m src.termgps.app
```

### Full Install (with GPS support)

```bash
# Clone
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
pip install -e .

# Run
termgps
```

### Optional: Real GPS (macOS only)
```bash
pip install pyobjc-framework-CoreLocation
```

---

## 🎮 Controls

| Key | Action |
|-----|--------|
| `r` | Get GPS location |
| `t` | Toggle live tracking (every 5s) |
| `d` | Search destination |
| `n` | Next navigation step |
| `p` | Previous navigation step |
| `c` | Clear route |
| `1-4` | Change theme |
| `q` | Quit |

| Mouse | Action |
|-------|--------|
| Drag | Pan the map |

---

## 🎨 Themes

Press `1`, `2`, `3`, or `4` to switch:

| Key | Theme | Style |
|-----|-------|-------|
| `1` | Matrix | Green on black |
| `2` | Dark | Cyan/white on dark |
| `3` | Ocean | Blue tones |
| `4` | Sunset | Orange/gold |

---

## 🗺️ Map Legend

| Symbol | Color | Meaning |
|--------|-------|---------|
| `╋` | Red | Your location (center) |
| `◉ YOU` | Yellow | Your position label |
| `●●●▶` | Magenta→Red | Direction to destination |
| `━━━` | Blue | Route path |
| `◆` | Red | Destination |
| `▼` | Red | Next turn |
| `N S E W` | White | Compass |

---

## 🌍 Cross-Platform Support

| Platform | GPS Method | Notes |
|----------|------------|-------|
| **macOS** | CoreLocation | Real GPS (requires permission) |
| **Windows** | IP Geolocation | ~10km accuracy |
| **Linux** | IP Geolocation | ~10km accuracy |

On all platforms, IP geolocation provides city-level accuracy (~10km).

---

## 📡 APIs Used

- **Routing**: [OSRM](https://project-osrm.org/) - Free, OpenStreetMap-based
- **Search**: [Nominatim](https://nominatim.openstreetmap.org/) - Free, no API key
- **IP Location**: [IP-API](http://ip-api.com/) - Free

No API keys required!

---

## 📁 Project Structure

```
termgps/
├── src/
│   └── termgps/
│       ├── __init__.py
│       └── app.py          # Main application
├── pyproject.toml          # Package config
├── README.md
├── LICENSE
└── .gitignore
```

---

## 🛠️ Development

```bash
# Clone and setup
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps
python -m venv venv
source venv/bin/activate
pip install -e .

# Run in development
python -m src.termgps.app
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

## 👨‍💻 Author

**Aditya Giri** - [@Aditya-Giri-4356](https://github.com/Aditya-Giri-4356)

---

## 🙏 Acknowledgments

- [Textual](https://textual.textualize.io/) - TUI framework
- [OSRM](https://project-osrm.org/) - Routing engine
- [OpenStreetMap](https://www.openstreetmap.org/) - Map data
